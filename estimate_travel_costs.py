"""
Approximate competition travel cost estimates.

Default behavior is a deterministic dry-run estimate. It does not scrape
airline, hotel, or booking sites, and its output is not booking advice. A
custom HTTP travel-cost API may be configured explicitly with environment
variables, but live lookups are never used by default.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Iterable

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SOURCE = "estimate_travel_costs"
BATCH_SIZE = 100
DEFAULT_CURRENCY = "USD"
DISCLAIMER = (
    "Approximate dry-run travel cost estimate for planning context only; "
    "not booking advice."
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

DEFAULT_RATES_TO_USD = {
    "USD": Decimal("1"),
    "EUR": Decimal("1.08"),
    "GBP": Decimal("1.27"),
    "CHF": Decimal("1.10"),
    "CAD": Decimal("0.74"),
    "AUD": Decimal("0.66"),
    "JPY": Decimal("0.0064"),
}

HOTEL_NIGHTLY_USD = {
    "france": 150.0,
    "switzerland": 210.0,
    "united states": 170.0,
    "usa": 170.0,
    "great britain": 165.0,
    "united kingdom": 165.0,
    "japan": 140.0,
    "china": 120.0,
    "south korea": 125.0,
    "hong kong": 155.0,
    "canada": 145.0,
    "australia": 150.0,
    "germany": 145.0,
    "italy": 145.0,
    "spain": 130.0,
}


@dataclass(frozen=True)
class TravelOrigin:
    country: str
    city: str
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class TravelEvent:
    tournament_id: str
    name: str | None
    destination_city: str
    destination_country: str
    start_date: date
    end_date: date
    latitude: float | None = None
    longitude: float | None = None
    venue_id: str | None = None
    venue_name: str | None = None
    limitations: tuple[str, ...] = ()

    @property
    def destination(self) -> str:
        return f"{self.destination_city}, {self.destination_country}"

    @property
    def date_range(self) -> str:
        return f"{self.start_date.isoformat()}/{self.end_date.isoformat()}"

    @property
    def hotel_nights(self) -> int:
        return max(1, (self.end_date - self.start_date).days + 1)


@dataclass(frozen=True)
class CostEstimate:
    flight: float
    hotel: float
    currency: str
    source: str
    confidence: float
    metadata: dict[str, Any]

    def to_cache(self) -> dict[str, Any]:
        return {
            "flight": self.flight,
            "hotel": self.hotel,
            "currency": self.currency,
            "source": self.source,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_cache(cls, value: dict[str, Any]) -> "CostEstimate":
        return cls(
            flight=float(value["flight"]),
            hotel=float(value["hotel"]),
            currency=str(value["currency"]),
            source=str(value["source"]),
            confidence=float(value["confidence"]),
            metadata=dict(value.get("metadata") or {}),
        )


class CurrencyConverter:
    def __init__(self, rates_to_usd: dict[str, Decimal | str | float] | None = None):
        rates = rates_to_usd or DEFAULT_RATES_TO_USD
        self.rates_to_usd = {
            code.upper(): Decimal(str(value)) for code, value in rates.items()
        }

    def convert(self, amount: float | Decimal, from_currency: str, to_currency: str) -> float:
        source = from_currency.upper()
        target = to_currency.upper()
        if source not in self.rates_to_usd:
            raise ValueError(f"Missing conversion rate for {source}")
        if target not in self.rates_to_usd:
            raise ValueError(f"Missing conversion rate for {target}")

        amount_decimal = Decimal(str(amount))
        usd = amount_decimal * self.rates_to_usd[source]
        converted = usd / self.rates_to_usd[target]
        return float(converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def normalized_key(value: Any) -> str:
    return clean_text(value).casefold()


def parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def country_hotel_rate(country: str) -> float:
    return HOTEL_NIGHTLY_USD.get(normalized_key(country), 130.0)


def metadata_venue_id(row: dict[str, Any]) -> str | None:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("venue_id")
    return str(value) if value else None


def venues_by_id(venues: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(venue["id"]): venue for venue in venues if venue.get("id")}


def find_venue_for_tournament(
    tournament: dict[str, Any],
    venues: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    venue_id = metadata_venue_id(tournament)
    if venue_id and venue_id in by_id:
        return by_id[venue_id]

    city = normalized_key(tournament.get("city") or tournament.get("location"))
    country = normalized_key(tournament.get("country"))
    if not city or not country:
        return None
    for venue in venues:
        if normalized_key(venue.get("city")) == city and normalized_key(venue.get("country")) == country:
            return venue
    return None


def normalize_event(
    tournament: dict[str, Any],
    venue: dict[str, Any] | None,
) -> tuple[TravelEvent | None, str | None]:
    venue = venue or {}
    city = clean_text(
        tournament.get("city") or tournament.get("location") or venue.get("city")
    )
    country = clean_text(tournament.get("country") or venue.get("country"))
    if not city or not country:
        return None, "missing_destination"

    start = parse_date(tournament.get("start_date"))
    if not start:
        return None, "missing_start_date"

    end = parse_date(tournament.get("end_date")) or start
    limitations: list[str] = []
    if end < start:
        end = start
        limitations.append("invalid_end_date")
    if not tournament.get("end_date"):
        limitations.append("missing_end_date")

    latitude = parse_float(tournament.get("latitude"))
    longitude = parse_float(tournament.get("longitude"))
    if latitude is None or longitude is None:
        latitude = parse_float(venue.get("latitude"))
        longitude = parse_float(venue.get("longitude"))
    if latitude is None or longitude is None:
        limitations.append("missing_coordinates")

    tournament_id = tournament.get("id")
    if not tournament_id:
        return None, "missing_tournament_id"

    return (
        TravelEvent(
            tournament_id=str(tournament_id),
            name=clean_text(tournament.get("name")) or None,
            destination_city=city,
            destination_country=country,
            start_date=start,
            end_date=end,
            latitude=latitude,
            longitude=longitude,
            venue_id=metadata_venue_id(tournament) or (str(venue["id"]) if venue.get("id") else None),
            venue_name=clean_text(venue.get("name")) or None,
            limitations=tuple(limitations),
        ),
        None,
    )


def parse_origins(value: str | None = None) -> list[TravelOrigin]:
    raw = value if value is not None else os.environ.get("TRAVEL_ORIGINS", "")
    if not raw.strip():
        return [
            TravelOrigin(
                country="United States",
                city="New York",
                latitude=40.7128,
                longitude=-74.0060,
            )
        ]

    origins: list[TravelOrigin] = []
    for item in raw.split(";"):
        parts = [clean_text(part) for part in item.split("|")]
        parts = [part for part in parts if part]
        if len(parts) < 2:
            continue
        latitude = parse_float(parts[2]) if len(parts) >= 3 else None
        longitude = parse_float(parts[3]) if len(parts) >= 4 else None
        origins.append(
            TravelOrigin(
                country=parts[0],
                city=parts[1],
                latitude=latitude,
                longitude=longitude,
            )
        )
    return origins


class StaticTravelCostProvider:
    source = "static-dry-run"

    def __init__(
        self,
        *,
        converter: CurrencyConverter | None = None,
        cache: dict[str, Any] | None = None,
        min_interval_seconds: float = 0.0,
        now_func: Callable[[], float] = time.monotonic,
        sleep_func: Callable[[float], None] = time.sleep,
    ):
        self.converter = converter or CurrencyConverter()
        self.cache: dict[str, Any] = cache if isinstance(cache, dict) else {}
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.now_func = now_func
        self.sleep_func = sleep_func
        self._last_request_at: float | None = None

    def _rate_limit(self) -> None:
        if self.min_interval_seconds <= 0:
            return
        now = self.now_func()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            wait = self.min_interval_seconds - elapsed
            if wait > 0:
                self.sleep_func(wait)
                now = self.now_func()
        self._last_request_at = now

    def _cache_key(
        self,
        origin: TravelOrigin,
        tournament: dict[str, Any],
        venue: dict[str, Any] | None,
        currency: str,
    ) -> str:
        event, reason = normalize_event(tournament, venue)
        if reason or not event:
            key_payload = {
                "origin": origin.__dict__,
                "tournament": tournament.get("id"),
                "reason": reason,
                "currency": currency.upper(),
            }
        else:
            key_payload = {
                "origin": origin.__dict__,
                "destination": event.destination,
                "date_range": event.date_range,
                "latitude": event.latitude,
                "longitude": event.longitude,
                "currency": currency.upper(),
                "provider": self.source,
            }
        return json.dumps(key_payload, sort_keys=True, default=str)

    def estimate(
        self,
        origin: TravelOrigin,
        tournament: dict[str, Any],
        venue: dict[str, Any] | None = None,
        *,
        currency: str = DEFAULT_CURRENCY,
    ) -> CostEstimate:
        cache_key = self._cache_key(origin, tournament, venue, currency)
        cached = self.cache.get(cache_key)
        if isinstance(cached, dict):
            return CostEstimate.from_cache(cached)

        event, reason = normalize_event(tournament, venue)
        if reason or not event:
            raise ValueError(f"Cannot estimate travel cost: {reason}")

        self._rate_limit()
        estimate = self._estimate_event(origin, event, currency.upper())
        estimate.metadata["cache_key"] = cache_key
        self.cache[cache_key] = estimate.to_cache()
        return estimate

    def _estimate_event(
        self,
        origin: TravelOrigin,
        event: TravelEvent,
        currency: str,
    ) -> CostEstimate:
        origin_country = normalized_key(origin.country)
        destination_country = normalized_key(event.destination_country)
        same_city = (
            normalized_key(origin.city) == normalized_key(event.destination_city)
            and origin_country == destination_country
        )
        same_country = origin_country == destination_country
        limitations = list(event.limitations)

        if same_city:
            distance_km = 0.0
            flight_usd = 0.0
            confidence = 0.72
        elif (
            origin.latitude is not None
            and origin.longitude is not None
            and event.latitude is not None
            and event.longitude is not None
        ):
            distance_km = haversine_km(
                origin.latitude,
                origin.longitude,
                event.latitude,
                event.longitude,
            )
            flight_usd = (
                120.0 + distance_km * 0.18
                if same_country
                else 350.0 + distance_km * 0.12
            )
            confidence = 0.79
        else:
            distance_km = 700.0 if same_country else 6500.0
            flight_usd = (
                120.0 + distance_km * 0.18
                if same_country
                else 350.0 + distance_km * 0.12
            )
            confidence = 0.58
            if "missing_coordinates" not in limitations:
                limitations.append("missing_coordinates")

        hotel_usd = country_hotel_rate(event.destination_country) * event.hotel_nights
        flight = self.converter.convert(round(flight_usd, 2), "USD", currency)
        hotel = self.converter.convert(round(hotel_usd, 2), "USD", currency)
        if limitations:
            confidence = min(confidence, 0.62)

        metadata = {
            "provider": self.source,
            "dry_run": True,
            "estimate_method": "deterministic_static_formula",
            "flight_distance_km": round(distance_km, 1),
            "hotel_nights": event.hotel_nights,
            "hotel_nightly_usd": country_hotel_rate(event.destination_country),
            "venue_id": event.venue_id,
            "venue_name": event.venue_name,
            "estimate_limitations": limitations,
            "not_booking_advice": True,
            "disclaimer": DISCLAIMER,
        }
        return CostEstimate(
            flight=flight,
            hotel=hotel,
            currency=currency,
            source=self.source,
            confidence=round(confidence, 2),
            metadata=metadata,
        )


class CustomApiTravelCostProvider(StaticTravelCostProvider):
    source = "custom-api"

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        timeout: float = 20.0,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout

    def _estimate_event(
        self,
        origin: TravelOrigin,
        event: TravelEvent,
        currency: str,
    ) -> CostEstimate:
        import requests

        payload = {
            "origin": {
                "country": origin.country,
                "city": origin.city,
                "latitude": origin.latitude,
                "longitude": origin.longitude,
            },
            "destination": {
                "city": event.destination_city,
                "country": event.destination_country,
                "latitude": event.latitude,
                "longitude": event.longitude,
            },
            "date_range": event.date_range,
            "currency": currency,
        }
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        source_currency = str(data.get("currency") or currency).upper()
        flight = self.converter.convert(
            float(data.get("flight_estimate") or 0),
            source_currency,
            currency,
        )
        hotel = self.converter.convert(
            float(data.get("hotel_estimate") or 0),
            source_currency,
            currency,
        )
        metadata = dict(data.get("metadata") or {})
        metadata.update(
            {
                "provider": self.source,
                "dry_run": False,
                "estimate_limitations": list(event.limitations),
                "not_booking_advice": True,
                "disclaimer": DISCLAIMER,
            }
        )
        return CostEstimate(
            flight=flight,
            hotel=hotel,
            currency=currency,
            source=self.source,
            confidence=round(float(data.get("confidence") or 0.85), 2),
            metadata=metadata,
        )


def provider_from_env(
    env: dict[str, str] | os._Environ[str] | None = None,
    *,
    cache: dict[str, Any] | None = None,
) -> StaticTravelCostProvider:
    env = env if env is not None else os.environ
    provider_name = env.get("TRAVEL_COST_PROVIDER", "static").strip().lower()
    min_interval = float(env.get("TRAVEL_COST_RATE_LIMIT_SECONDS", "0") or 0)

    if provider_name in {"", "static", "mock", "dry-run", "dry_run"}:
        return StaticTravelCostProvider(
            cache=cache,
            min_interval_seconds=min_interval,
        )

    if provider_name in {"api", "http", "custom-api"}:
        api_url = env.get("TRAVEL_COST_API_URL")
        api_key = env.get("TRAVEL_COST_API_KEY")
        if not api_url or not api_key:
            raise RuntimeError(
                "TRAVEL_COST_API_URL and TRAVEL_COST_API_KEY are required for "
                "TRAVEL_COST_PROVIDER=api. Default static dry-run estimates do "
                "not require credentials."
            )
        return CustomApiTravelCostProvider(
            api_url=api_url,
            api_key=api_key,
            cache=cache,
            min_interval_seconds=min_interval,
        )

    raise ValueError(f"Unsupported TRAVEL_COST_PROVIDER={provider_name!r}")


def build_travel_cost_rows(
    *,
    tournaments: Iterable[dict[str, Any]],
    venues: Iterable[dict[str, Any]],
    origins: Iterable[TravelOrigin] | None = None,
    provider: StaticTravelCostProvider | None = None,
    currency: str = DEFAULT_CURRENCY,
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tournament_rows = list(tournaments)
    venue_rows = list(venues)
    origin_rows = list(origins or parse_origins())
    provider = provider or provider_from_env({})
    updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    currency = currency.upper()

    rows: list[dict[str, Any]] = []
    skip_reasons: dict[str, int] = {}
    venue_lookup = venues_by_id(venue_rows)

    for tournament in tournament_rows:
        venue = find_venue_for_tournament(tournament, venue_rows, venue_lookup)
        event, reason = normalize_event(tournament, venue)
        if reason or not event:
            skip_reasons[reason or "unknown"] = skip_reasons.get(reason or "unknown", 0) + 1
            continue

        for origin in origin_rows:
            estimate = provider.estimate(
                origin,
                tournament,
                venue,
                currency=currency,
            )
            metadata = dict(estimate.metadata)
            metadata.update(
                {
                    "tournament_name": event.name,
                    "origin": {
                        "country": origin.country,
                        "city": origin.city,
                        "latitude": origin.latitude,
                        "longitude": origin.longitude,
                    },
                    "destination": {
                        "city": event.destination_city,
                        "country": event.destination_country,
                        "latitude": event.latitude,
                        "longitude": event.longitude,
                    },
                }
            )
            rows.append(
                {
                    "tournament_id": event.tournament_id,
                    "origin_country": origin.country,
                    "origin_city": origin.city,
                    "destination": event.destination,
                    "date_range": event.date_range,
                    "flight_estimate": estimate.flight,
                    "hotel_estimate": estimate.hotel,
                    "currency": estimate.currency,
                    "source": estimate.source,
                    "confidence": estimate.confidence,
                    "metadata": metadata,
                    "updated_at": updated_at,
                }
            )

    summary = {
        "tournaments": len(tournament_rows),
        "origins": len(origin_rows),
        "estimates": len(rows),
        "skipped": sum(skip_reasons.values()),
        "skip_reasons": skip_reasons,
    }
    return rows, summary


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_all(query: Any, batch_size: int = BATCH_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = query.range(offset, offset + batch_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < batch_size:
            return rows
        offset += batch_size


def fetch_tournaments(client: Any) -> list[dict[str, Any]]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    column_sets = (
        "id,name,city,country,start_date,end_date,metadata",
        "id,name,location,country,start_date,end_date,metadata",
    )
    last_error: Exception | None = None

    for columns in column_sets:
        try:
            rows = fetch_all(client.table("fs_tournaments").select(columns))
        except Exception as exc:
            last_error = exc
            continue
        for row in rows:
            row_id = row.get("id")
            if row_id and str(row_id) not in rows_by_id:
                rows_by_id[str(row_id)] = row
        if rows_by_id:
            return list(rows_by_id.values())

    if last_error:
        raise RuntimeError("Unable to fetch fs_tournaments for travel estimates") from last_error
    return []


def fetch_venues(client: Any) -> list[dict[str, Any]]:
    try:
        return fetch_all(
            client.table("fs_venues").select(
                "id,name,city,country,latitude,longitude,metadata"
            )
        )
    except Exception as exc:
        print(f"[{SOURCE}] venue lookup unavailable, continuing without coordinates: {exc}")
        return []


def upsert_travel_cost_rows(client: Any, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index : index + BATCH_SIZE]
        client.table("fs_travel_cost_estimates").upsert(
            batch,
            on_conflict="tournament_id,origin_country,origin_city",
        ).execute()
    return len(rows)


def load_provider_cache(update_state: bool) -> dict[str, Any]:
    if not update_state:
        return {}
    value = get_state(SOURCE, "provider_cache")
    return value if isinstance(value, dict) else {}


def estimate_travel_costs(
    *,
    client: Any | None = None,
    origins: Iterable[TravelOrigin] | None = None,
    provider: StaticTravelCostProvider | None = None,
    currency: str | None = None,
    updated_at: str | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        if not client:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

        cache = load_provider_cache(update_state)
        provider = provider or provider_from_env(cache=cache)
        target_currency = (
            currency
            or os.environ.get("TRAVEL_ESTIMATE_CURRENCY")
            or DEFAULT_CURRENCY
        ).upper()

        tournaments = fetch_tournaments(client)
        venues = fetch_venues(client)
        rows, summary = build_travel_cost_rows(
            tournaments=tournaments,
            venues=venues,
            origins=origins,
            provider=provider,
            currency=target_currency,
            updated_at=updated_at,
        )
        written = upsert_travel_cost_rows(client, rows)
        summary = {**summary, "written": written, "failed": 0}

        if update_state:
            set_state(SOURCE, "provider_cache", provider.cache)
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "disclaimer": DISCLAIMER,
                },
            )
        if run_log:
            run_log.complete(
                written=written,
                failed=0,
                skipped=summary["skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Travel cost estimation starting - {datetime.now(timezone.utc).isoformat()}")
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous travel estimate state: {previous_state}")
    summary = estimate_travel_costs()
    print(
        "Travel cost estimation complete - "
        f"{summary['estimates']} estimates built, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} tournaments skipped"
    )


if __name__ == "__main__":
    main()

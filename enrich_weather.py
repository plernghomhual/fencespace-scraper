import argparse
import copy
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from statistics import mean
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "enrich_weather"
PAGE_SIZE = 1000
LOOKUP_CACHE_KEY = "weather_lookup_cache"
TOURNAMENT_SELECT = (
    "id,name,start_date,end_date,location,country,venue_details,detail_source"
)
PROBE_BLOCKED_EVIDENCE = "sandbox DNS probe failed; escalated retry unavailable"

OUTDOOR_RE = re.compile(
    r"\b(outdoor|open[- ]air|plaza|park|stadium|beach|courtyard|temporary piste)\b",
    re.IGNORECASE,
)
INDOOR_RE = re.compile(
    r"\b(indoor|arena|hall|gym|gymnasium|center|centre|sports complex|"
    r"pavilion|convention|exhibition|salle|club|velodrome)\b",
    re.IGNORECASE,
)


class OpenMeteoClient:
    source = "open_meteo"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def _get_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "FenceSpace-Scraper/1.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def geocode(self, location: str) -> dict[str, Any] | None:
        query = urllib.parse.urlencode(
            {
                "name": location,
                "count": 1,
                "language": "en",
                "format": "json",
            }
        )
        data = self._get_json(f"https://geocoding-api.open-meteo.com/v1/search?{query}")
        results = data.get("results") or []
        return results[0] if results else None

    def fetch_weather(
        self,
        latitude: float,
        longitude: float,
        event_date: str,
    ) -> dict[str, Any] | None:
        query = urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": event_date,
                "end_date": event_date,
                "hourly": "temperature_2m,relative_humidity_2m",
                "timezone": "UTC",
            }
        )
        return self._get_json(f"https://archive-api.open-meteo.com/v1/archive?{query}")


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def parse_date(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    candidate = text[:10]
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError:
        return None
    return candidate


def event_date_for_tournament(tournament: dict[str, Any]) -> tuple[str | None, str | None]:
    for key in ("start_date", "date", "end_date"):
        parsed = parse_date(tournament.get(key))
        if parsed:
            return parsed, key
    return None, None


def venue_name_for_tournament(tournament: dict[str, Any]) -> str | None:
    for key in ("venue_name", "venue", "venue_details"):
        value = clean_text(tournament.get(key))
        if value:
            return value
    return None


def location_for_tournament(tournament: dict[str, Any]) -> str | None:
    location = clean_text(tournament.get("location"))
    if location:
        return location

    city = clean_text(tournament.get("city") or tournament.get("venue_city"))
    country = clean_text(tournament.get("country") or tournament.get("venue_country"))
    if city and country:
        return f"{city}, {country}"
    return None


def classify_environment(tournament: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        value
        for value in (
            clean_text(tournament.get("name")),
            clean_text(tournament.get("location")),
            clean_text(tournament.get("venue_details")),
            clean_text(tournament.get("detail_source")),
        )
        if value
    )
    if OUTDOOR_RE.search(text):
        return {
            "environment": "outdoor",
            "is_indoor": False,
            "weather_relevance": "possible_context_only",
            "reason": "explicit outdoor venue wording",
        }
    if INDOOR_RE.search(text):
        return {
            "environment": "indoor",
            "is_indoor": True,
            "weather_relevance": "low",
            "reason": "explicit indoor venue wording",
        }
    return {
        "environment": "indoor_assumed",
        "is_indoor": True,
        "weather_relevance": "low",
        "reason": "fencing events are usually indoor; weather kept as context only",
    }


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _mean_numeric(values: list[Any]) -> float | None:
    raw = [_coerce_float(value) for value in values]
    numbers: list[float] = [value for value in raw if value is not None]
    if not numbers:
        return None
    return round(mean(numbers), 1)


def _daily_value(daily: dict[str, Any], key: str, index: int) -> float | None:
    values = daily.get(key)
    if not isinstance(values, list) or index >= len(values):
        return None
    value = _coerce_float(values[index])
    return round(value, 1) if value is not None else None


def normalize_open_meteo_weather(
    data: dict[str, Any] | None,
    event_date: str,
) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None

    hourly = data.get("hourly") if isinstance(data.get("hourly"), dict) else None
    if hourly:
        times = hourly.get("time")
        indexes: list[int]
        if isinstance(times, list) and times:
            indexes = [
                index
                for index, value in enumerate(times)
                if str(value).startswith(event_date)
            ]
        else:
            indexes = []
        if not indexes:
            max_len = max(
                len(value) for value in hourly.values() if isinstance(value, list)
            )
            indexes = list(range(max_len))

        temperatures = hourly.get("temperature_2m") or []
        humidities = hourly.get("relative_humidity_2m") or []
        temperature = _mean_numeric(
            [temperatures[index] for index in indexes if index < len(temperatures)]
        )
        humidity = _mean_numeric(
            [humidities[index] for index in indexes if index < len(humidities)]
        )
        if temperature is not None or humidity is not None:
            return {
                "temperature_celsius": temperature,
                "humidity_percent": humidity,
                "metadata": {
                    "provider": "open_meteo",
                    "weather_status": "found",
                    "date": event_date,
                    "hourly_points": len(indexes),
                    "units": data.get("hourly_units") or {},
                },
            }

    daily = data.get("daily") if isinstance(data.get("daily"), dict) else None
    if daily:
        times = daily.get("time") or []
        index = times.index(event_date) if event_date in times else 0
        temperature = _daily_value(daily, "temperature_2m_mean", index)
        if temperature is None:
            temp_min = _daily_value(daily, "temperature_2m_min", index)
            temp_max = _daily_value(daily, "temperature_2m_max", index)
            if temp_min is not None and temp_max is not None:
                temperature = round(mean([temp_min, temp_max]), 1)
        humidity = _daily_value(daily, "relative_humidity_2m_mean", index)
        if temperature is not None or humidity is not None:
            return {
                "temperature_celsius": temperature,
                "humidity_percent": humidity,
                "metadata": {
                    "provider": "open_meteo",
                    "weather_status": "found",
                    "date": event_date,
                    "units": data.get("daily_units") or {},
                },
            }

    return None


def fetch_all(
    client,
    table: str,
    columns: str,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table(table)
            .select(columns)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def _cache_key(location: str, event_date: str) -> str:
    return f"{location.strip().casefold()}|{event_date}"


def _base_row(
    tournament: dict[str, Any],
    event_date: str | None,
    date_basis: str | None,
    location: str | None,
    environment: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    metadata = {
        "causal_claim": False,
        "reason": environment["reason"],
        "date_basis": date_basis,
    }
    return {
        "tournament_id": tournament["id"],
        "venue_name": venue_name_for_tournament(tournament),
        "location": location,
        "event_date": event_date,
        "is_indoor": environment["is_indoor"],
        "environment": environment["environment"],
        "weather_relevance": environment["weather_relevance"],
        "latitude": None,
        "longitude": None,
        "temperature_celsius": None,
        "humidity_percent": None,
        "source": "indoor_default",
        "metadata": metadata,
        "scraped_at": updated_at,
    }


def _status_row(
    row: dict[str, Any],
    source: str,
    weather_status: str,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = copy.deepcopy(row)
    result["source"] = source
    result["metadata"]["weather_status"] = weather_status
    if extra_metadata:
        result["metadata"].update(extra_metadata)
    return result


def _apply_lookup(
    row: dict[str, Any],
    lookup: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(row)
    for key in (
        "latitude",
        "longitude",
        "temperature_celsius",
        "humidity_percent",
        "source",
    ):
        result[key] = lookup.get(key)
    result["metadata"].update(copy.deepcopy(lookup.get("metadata") or {}))
    return result


def _weather_lookup(
    *,
    location: str,
    event_date: str,
    weather_client,
) -> dict[str, Any]:
    source = getattr(weather_client, "source", "weather_fixture")
    geocode = weather_client.geocode(location)
    if not geocode:
        return {
            "latitude": None,
            "longitude": None,
            "temperature_celsius": None,
            "humidity_percent": None,
            "source": source,
            "metadata": {
                "provider": "open_meteo",
                "weather_status": "missing_geocode",
                "geocode_query": location,
            },
        }

    latitude = _coerce_float(geocode.get("latitude"))
    longitude = _coerce_float(geocode.get("longitude"))
    if latitude is None or longitude is None:
        return {
            "latitude": latitude,
            "longitude": longitude,
            "temperature_celsius": None,
            "humidity_percent": None,
            "source": source,
            "metadata": {
                "provider": "open_meteo",
                "weather_status": "invalid_geocode",
                "geocode": geocode,
            },
        }

    weather_data = weather_client.fetch_weather(latitude, longitude, event_date)
    normalized = normalize_open_meteo_weather(weather_data, event_date)
    metadata = {
        "provider": "open_meteo",
        "weather_status": "missing_weather",
        "geocode": {
            key: geocode.get(key)
            for key in ("name", "country", "admin1", "timezone")
            if geocode.get(key) is not None
        },
    }
    if normalized:
        metadata.update(normalized.get("metadata") or {})

    return {
        "latitude": latitude,
        "longitude": longitude,
        "temperature_celsius": normalized.get("temperature_celsius")
        if normalized
        else None,
        "humidity_percent": normalized.get("humidity_percent") if normalized else None,
        "source": source,
        "metadata": metadata,
    }


def build_weather_context_row(
    tournament: dict[str, Any],
    *,
    weather_client=None,
    allow_network: bool = False,
    lookup_cache: dict[str, Any] | None = None,
    updated_at: str | None = None,
    today: date | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    lookup_cache = lookup_cache if lookup_cache is not None else {}
    updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    today = today or date.today()
    event_date, date_basis = event_date_for_tournament(tournament)
    location = location_for_tournament(tournament)
    environment = classify_environment(tournament)
    row = _base_row(tournament, event_date, date_basis, location, environment, updated_at)
    stats = {"weather_found": 0, "cache_hits": 0, "skipped": 0, "failed": 0}

    if not location:
        stats["skipped"] += 1
        return (
            _status_row(row, "missing_location", "missing_location"),
            stats,
        )
    if not event_date:
        stats["skipped"] += 1
        return _status_row(row, "missing_date", "missing_date"), stats

    if environment["environment"] != "outdoor":
        row["metadata"]["weather_status"] = "not_requested_indoor"
        return row, stats

    parsed_event_date = datetime.strptime(event_date, "%Y-%m-%d").date()
    if parsed_event_date > today:
        stats["skipped"] += 1
        return _status_row(row, "date_not_supported", "future_event"), stats

    if weather_client is None:
        if not allow_network:
            return (
                _status_row(
                    row,
                    "dry_run",
                    "network_disabled",
                    {"probe_evidence": PROBE_BLOCKED_EVIDENCE},
                ),
                stats,
            )
        weather_client = OpenMeteoClient()

    key = _cache_key(location, event_date)
    if key in lookup_cache:
        stats["cache_hits"] += 1
        lookup = copy.deepcopy(lookup_cache[key])
    else:
        lookup = _weather_lookup(
            location=location,
            event_date=event_date,
            weather_client=weather_client,
        )
        lookup_cache[key] = copy.deepcopy(lookup)

    row = _apply_lookup(row, lookup)
    if row["temperature_celsius"] is not None or row["humidity_percent"] is not None:
        stats["weather_found"] += 1
    else:
        stats["skipped"] += 1
    return row, stats


def upsert_weather_row(client, row: dict[str, Any]) -> int:
    client.table("fs_competition_weather").upsert(
        row,
        on_conflict="tournament_id",
    ).execute()
    return 1


def enrich_competition_weather(
    client=None,
    *,
    weather_client=None,
    allow_network: bool = False,
    limit: int | None = None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    updated_at: str | None = None,
    state_get=get_state,
    state_set=set_state,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    lookup_cache = state_get(SOURCE, LOOKUP_CACHE_KEY) if update_state else {}
    if not isinstance(lookup_cache, dict):
        lookup_cache = {}

    summary = {
        "tournaments_read": 0,
        "written": 0,
        "weather_found": 0,
        "cache_hits": 0,
        "skipped": 0,
        "failed": 0,
    }
    try:
        client = client or get_supabase_client()
        tournaments = fetch_all(
            client,
            "fs_tournaments",
            TOURNAMENT_SELECT,
            page_size=page_size,
        )
        if limit is not None:
            tournaments = tournaments[:limit]
        summary["tournaments_read"] = len(tournaments)

        for tournament in tournaments:
            if not tournament.get("id"):
                summary["skipped"] += 1
                continue
            try:
                row, stats = build_weather_context_row(
                    tournament,
                    weather_client=weather_client,
                    allow_network=allow_network,
                    lookup_cache=lookup_cache,
                    updated_at=updated_at,
                )
                upsert_weather_row(client, row)
                summary["written"] += 1
                for key in ("weather_found", "cache_hits", "skipped", "failed"):
                    summary[key] += stats.get(key, 0)
            except Exception as exc:
                summary["failed"] += 1
                print(f"  Weather enrichment failed for {tournament.get('id')}: {exc}")

        if update_state:
            state_set(SOURCE, LOOKUP_CACHE_KEY, lookup_cache)
            state_set(
                SOURCE,
                "last_run",
                {**summary, "updated_at": updated_at},
            )
        if run_log:
            run_log.complete(
                written=summary["written"],
                failed=summary["failed"],
                skipped=summary["skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def probe_open_meteo() -> int:
    client = OpenMeteoClient(timeout=8.0)
    location = "Paris, France"
    event_date = "2024-07-27"
    try:
        geocode = client.geocode(location)
        print(f"Open-Meteo geocode probe for {location}: {bool(geocode)}")
        if not geocode:
            print("Probe evidence: geocoding returned no results")
            return 0
        latitude = _coerce_float(geocode.get("latitude"))
        longitude = _coerce_float(geocode.get("longitude"))
        print(f"Geocode keys: {sorted(geocode.keys())}")
        if latitude is None or longitude is None:
            print("Probe evidence: geocoding result omitted numeric coordinates")
            return 0
        data = client.fetch_weather(latitude, longitude, event_date)
        print(f"Archive keys: {sorted((data or {}).keys())}")
        if isinstance(data, dict) and isinstance(data.get("hourly"), dict):
            print(f"Hourly keys: {sorted(data['hourly'].keys())}")
        normalized = normalize_open_meteo_weather(data, event_date)
        print(f"Normalized weather available: {bool(normalized)}")
    except Exception as exc:
        print(f"Open-Meteo probe failed: {exc}")
        print(f"Probe evidence: {PROBE_BLOCKED_EVIDENCE}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich competition weather context.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow keyless Open-Meteo lookups. Default is dry-run context only.",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Probe Open-Meteo response shape and exit 0 with evidence.",
    )
    args = parser.parse_args()

    if args.probe:
        raise SystemExit(probe_open_meteo())

    summary = enrich_competition_weather(
        allow_network=args.allow_network,
        limit=args.limit,
    )
    print(
        "Weather enrichment complete - "
        f"read={summary['tournaments_read']}, written={summary['written']}, "
        f"weather_found={summary['weather_found']}, skipped={summary['skipped']}, "
        f"failed={summary['failed']}"
    )


if __name__ == "__main__":
    main()

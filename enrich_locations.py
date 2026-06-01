import os
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SOURCE = "enrich_locations"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = os.environ.get(
    "NOMINATIM_USER_AGENT",
    "FenceSpace-Scraper/1.0 (https://fencespace.app)",
)
REQUEST_DELAY = float(os.environ.get("NOMINATIM_REQUEST_DELAY", "1.0"))
BATCH_SIZE = 1000

KNOWN_VENUES = {
    "stade pierre de coubertin": "Stade Pierre de Coubertin",
    "anaheim convention center": "Anaheim Convention Center",
    "long beach convention center": "Long Beach Convention Center",
    "georgia world congress center": "Georgia World Congress Center",
    "cairo stadium indoor halls complex": "Cairo Stadium Indoor Halls Complex",
    "exCeL london".casefold(): "ExCeL London",
}

VENUE_KEYWORDS = (
    "arena",
    "centre",
    "center",
    "club",
    "coliseum",
    "complex",
    "convention",
    "exhibition",
    "expo",
    "forum",
    "gym",
    "hall",
    "institute",
    "messe",
    "palace",
    "palais",
    "palasport",
    "pavilion",
    "sport",
    "sports",
    "stade",
    "stadium",
    "university",
)


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float
    longitude: float
    country_code: str | None
    metadata: dict[str, Any]


@dataclass
class EnrichmentSummary:
    written: int = 0
    failed: int = 0
    skipped: int = 0
    linked: int = 0
    geocoded: int = 0

    def as_metadata(self) -> dict[str, int]:
        return {
            "venues_written": self.written,
            "locations_failed": self.failed,
            "locations_skipped": self.skipped,
            "tournaments_linked": self.linked,
            "locations_geocoded": self.geocoded,
        }


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def fold_text(value: Any) -> str:
    text = clean_text(value).casefold()
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def location_key(city: str, country: str) -> str:
    return f"{fold_text(city)}|{fold_text(country)}"


def venue_key(name: str, city: str, country: str) -> tuple[str, str, str]:
    return (fold_text(name), fold_text(city), fold_text(country))


def known_venue_match(text: str) -> str | None:
    folded = fold_text(text)
    for needle, canonical in KNOWN_VENUES.items():
        if fold_text(needle) in folded:
            return canonical
    return None


def looks_like_venue(text: str, city: str) -> bool:
    candidate = clean_text(text).strip(" ,.;:-")
    if not candidate:
        return False
    if fold_text(candidate) == fold_text(city):
        return False
    if known_venue_match(candidate):
        return True
    folded = fold_text(candidate)
    return any(keyword in folded for keyword in VENUE_KEYWORDS)


def extract_venue_name(tournament_name: str | None, city: str | None) -> str:
    city_name = clean_text(city)
    name = clean_text(tournament_name)
    if name:
        dash_parts = [part.strip(" ,.;:-") for part in name.split(" - ") if part.strip()]
        for part in reversed(dash_parts[1:]):
            known = known_venue_match(part)
            if known:
                return known
            if looks_like_venue(part, city_name):
                return clean_text(part)

        known = known_venue_match(name)
        if known:
            return known

    return city_name or "Unknown"


def parse_nominatim_result(payload: Any) -> GeocodeResult | None:
    if not isinstance(payload, list) or not payload:
        return None

    row = payload[0]
    if not isinstance(row, dict):
        return None

    try:
        latitude = float(row["lat"])
        longitude = float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None

    address = row.get("address") if isinstance(row.get("address"), dict) else {}
    raw_country_code = clean_text(address.get("country_code"))
    country_code = raw_country_code.upper() or None
    nominatim_meta = {
        key: row[key]
        for key in ("display_name", "osm_type", "osm_id", "place_id")
        if key in row
    }

    return GeocodeResult(
        latitude=latitude,
        longitude=longitude,
        country_code=country_code,
        metadata={"nominatim": nominatim_meta},
    )


def _retry_after_seconds(value: str | None) -> float:
    try:
        return max(float(value or REQUEST_DELAY), REQUEST_DELAY)
    except (TypeError, ValueError):
        return REQUEST_DELAY


def geocode_location(
    city: str,
    country: str,
    *,
    session: Any | None = None,
    sleep_func: Callable[[float], None] = time.sleep,
    user_agent: str = NOMINATIM_USER_AGENT,
    max_retries: int = 1,
) -> GeocodeResult | None:
    http = session or requests.Session()
    params = {
        "q": f"{city} {country}",
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
    }
    headers = {"User-Agent": user_agent}

    for attempt in range(max_retries + 1):
        try:
            response = http.get(
                NOMINATIM_URL,
                params=params,
                headers=headers,
                timeout=20,
            )
            if response.status_code == 429 and attempt < max_retries:
                sleep_func(_retry_after_seconds(response.headers.get("Retry-After")))
                continue
            response.raise_for_status()
            return parse_nominatim_result(response.json())
        except Exception as exc:
            print(f"  Geocode failed for {city}, {country}: {exc}")
            return None
    return None


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
    rows_by_id: dict[Any, dict[str, Any]] = {}
    column_sets = (
        ("city", "id,name,city,country,metadata"),
        ("location", "id,name,location,country,metadata"),
    )

    for city_column, columns in column_sets:
        try:
            query = (
                client.table("fs_tournaments")
                .select(columns)
                .not_("country", "is", "null")
                .not_(city_column, "is", "null")
            )
            rows = fetch_all(query)
        except Exception as exc:
            print(f"  Could not fetch tournaments using {city_column}: {exc}")
            continue

        for row in rows:
            city = clean_text(row.get("city") or row.get("location"))
            country = clean_text(row.get("country"))
            row_id = row.get("id")
            if not row_id or not city or not country:
                continue
            if row_id in rows_by_id and rows_by_id[row_id].get("city"):
                continue
            normalized = dict(row)
            normalized["city"] = city
            normalized["country"] = country
            rows_by_id[row_id] = normalized

    return list(rows_by_id.values())


def fetch_existing_venues(client: Any) -> list[dict[str, Any]]:
    query = client.table("fs_venues").select(
        "id,name,city,country,latitude,longitude,country_code,competitions_count,metadata"
    )
    return fetch_all(query)


def existing_geocode_from_row(row: dict[str, Any]) -> GeocodeResult | None:
    try:
        latitude = float(row["latitude"])
        longitude = float(row["longitude"])
    except (KeyError, TypeError, ValueError):
        return None

    return GeocodeResult(
        latitude=latitude,
        longitude=longitude,
        country_code=clean_text(row.get("country_code")) or None,
        metadata=dict(row.get("metadata") or {}),
    )


def group_tournaments(
    tournaments: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
    for tournament in tournaments:
        city = clean_text(tournament.get("city") or tournament.get("location"))
        country = clean_text(tournament.get("country"))
        if not city or not country:
            continue
        venue_name = extract_venue_name(tournament.get("name"), city)
        grouped.setdefault((city, country), {}).setdefault(venue_name, []).append(tournament)
    return grouped


def upsert_venue(
    client: Any,
    *,
    name: str,
    city: str,
    country: str,
    geocode: GeocodeResult,
    competitions_count: int,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "name": name,
        "city": city,
        "country": country,
        "latitude": geocode.latitude,
        "longitude": geocode.longitude,
        "country_code": geocode.country_code,
        "competitions_count": competitions_count,
        "metadata": geocode.metadata,
    }
    result = (
        client.table("fs_venues")
        .upsert(row, on_conflict="name,city,country")
        .execute()
    )
    if result.data:
        return result.data[0]
    if existing:
        merged = dict(existing)
        merged.update(row)
        return merged
    return row


def merge_tournament_metadata(metadata: Any, venue_id: Any) -> dict[str, Any]:
    merged = dict(metadata) if isinstance(metadata, dict) else {}
    merged["venue_id"] = str(venue_id)
    return merged


def link_tournaments_to_venue(
    client: Any,
    tournaments: list[dict[str, Any]],
    venue_id: Any,
) -> int:
    if not venue_id:
        return 0

    linked = 0
    for tournament in tournaments:
        metadata = tournament.get("metadata") if isinstance(tournament.get("metadata"), dict) else {}
        if str(metadata.get("venue_id")) == str(venue_id):
            continue
        merged = merge_tournament_metadata(metadata, venue_id)
        client.table("fs_tournaments").update({"metadata": merged}).eq(
            "id", tournament["id"]
        ).execute()
        tournament["metadata"] = merged
        linked += 1
    return linked


def _state_list(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {clean_text(item) for item in value if clean_text(item)}


def enrich_locations(
    client: Any,
    *,
    geocode_func: Callable[[str, str], GeocodeResult | None] | None = None,
    sleep_func: Callable[[float], None] = time.sleep,
    request_delay: float = REQUEST_DELAY,
    state_get: Callable[[str, str], Any] = get_state,
    state_set: Callable[[str, str, Any], None] = set_state,
) -> EnrichmentSummary:
    session = requests.Session()
    geocode = geocode_func or (
        lambda city, country: geocode_location(city, country, session=session)
    )
    summary = EnrichmentSummary()

    tournaments = fetch_tournaments(client)
    existing_venues = fetch_existing_venues(client)
    existing_by_city: dict[str, dict[str, Any]] = {}
    existing_by_venue: dict[tuple[str, str, str], dict[str, Any]] = {}

    for venue in existing_venues:
        city = clean_text(venue.get("city"))
        country = clean_text(venue.get("country"))
        name = clean_text(venue.get("name"))
        if city and country and name:
            existing_by_city.setdefault(location_key(city, country), venue)
            existing_by_venue[venue_key(name, city, country)] = venue

    processed_locations = _state_list(state_get(SOURCE, "processed_locations"))
    ungeocodable_locations = _state_list(state_get(SOURCE, "ungeocodable_locations"))
    grouped = group_tournaments(tournaments)
    geocode_requests = 0

    for (city, country), venues in sorted(grouped.items()):
        loc_key = location_key(city, country)
        if loc_key in ungeocodable_locations:
            summary.skipped += sum(len(rows) for rows in venues.values())
            continue

        existing_city = existing_by_city.get(loc_key)
        city_geocode = existing_geocode_from_row(existing_city) if existing_city else None
        if city_geocode:
            summary.skipped += 1
        else:
            if geocode_requests > 0:
                sleep_func(request_delay)
            geocode_requests += 1
            city_geocode = geocode(city, country)
            if not city_geocode:
                print(f"  No geocode result for {city}, {country}")
                summary.failed += 1
                summary.skipped += sum(len(rows) for rows in venues.values())
                ungeocodable_locations.add(loc_key)
                continue
            summary.geocoded += 1

        processed_locations.add(loc_key)

        for venue_name, tournament_rows in sorted(venues.items()):
            key = venue_key(venue_name, city, country)
            existing_venue = existing_by_venue.get(key)
            saved = upsert_venue(
                client,
                name=venue_name,
                city=city,
                country=country,
                geocode=city_geocode,
                competitions_count=len(tournament_rows),
                existing=existing_venue,
            )
            summary.written += 1
            existing_by_venue[key] = saved
            existing_by_city.setdefault(loc_key, saved)
            summary.linked += link_tournaments_to_venue(
                client,
                tournament_rows,
                saved.get("id"),
            )

    state_set(SOURCE, "processed_locations", sorted(processed_locations))
    state_set(SOURCE, "ungeocodable_locations", sorted(ungeocodable_locations))
    state_set(
        SOURCE,
        "last_run",
        {
            **summary.as_metadata(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return summary


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY or supabase is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger(SOURCE).start()
    print(f"Location enrichment starting - {datetime.now(timezone.utc).isoformat()}")
    try:
        summary = enrich_locations(supabase)
    except Exception as exc:
        run_log.error(str(exc))
        raise

    run_log.complete(
        written=summary.written,
        failed=summary.failed,
        skipped=summary.skipped,
        metadata=summary.as_metadata(),
    )
    print(
        "Done - "
        f"venues={summary.written}, linked={summary.linked}, "
        f"geocoded={summary.geocoded}, failed={summary.failed}, skipped={summary.skipped}"
    )


if __name__ == "__main__":
    main()

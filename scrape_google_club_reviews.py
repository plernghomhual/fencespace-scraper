import os
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "scrape_google_club_reviews"
REVIEW_SOURCE = "google_maps"
PAGE_SIZE = 1000
UPSERT_BATCH_SIZE = 100
REQUEST_DELAY = 0.25
GOOGLE_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
GOOGLE_PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
PLACE_DETAILS_FIELDS = ",".join(
    [
        "place_id",
        "name",
        "rating",
        "user_ratings_total",
        "url",
        "formatted_address",
        "business_status",
        "types",
        "website",
        "international_phone_number",
        "geometry",
    ]
)
REVIEW_CONFLICT_COLUMNS = "normalized_club_name,city,country,source"
CLUB_REVIEW_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://fencespace.app/fs_club_reviews")
_UNSET = object()

HEADERS = {
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; contact@fencespace.app)",
    "Accept": "application/json",
}


@dataclass(frozen=True)
class ClubCandidate:
    name: str
    city: str
    country: str
    normalized_name: str | None = None
    source_tables: tuple[str, ...] = ()


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def display_club_name(value: Any) -> str | None:
    text = clean_text(str(value or "").replace("-", " "))
    if not text:
        return None
    if text.islower() or text.isupper():
        return text.title()
    return text


def normalize_club_name(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\b(?:a\s*s\s*d|s\s*s\s*d|a\s*s|s\s*c|asd|ssd)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def review_summary_for_rating(rating: float | None, review_count: int | None) -> str | None:
    if rating is None and review_count is None:
        return None
    if rating is None:
        return f"Google Maps review count: {review_count}"
    if review_count is None:
        return f"Google Maps rating {rating:g}"
    noun = "review" if review_count == 1 else "reviews"
    return f"Google Maps rating {rating:g} from {review_count} {noun}"


def metadata_city(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    for key in ("city", "club_city", "location_city", "address_city"):
        city = clean_text(metadata.get(key))
        if city:
            return city
    for key in ("club", "location", "address"):
        nested = metadata.get(key)
        if isinstance(nested, dict):
            city = clean_text(nested.get("city"))
            if city:
                return city
    return None


def row_city(row: dict[str, Any]) -> str | None:
    for key in ("city", "club_city", "location_city"):
        city = clean_text(row.get(key))
        if city:
            return city
    return metadata_city(row.get("metadata"))


def fetch_all_rows(
    client,
    table: str,
    columns: str,
    *,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows = []
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


def fetch_rows_with_column_fallback(
    client,
    table: str,
    column_options: tuple[str, ...],
    *,
    page_size: int,
) -> list[dict[str, Any]]:
    last_error = None
    for columns in column_options:
        try:
            return fetch_all_rows(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    print(f"Skipping {table}: {last_error}")
    return []


def fetch_distinct_clubs(client, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    source_tables = (
        (
            "fs_club_reviews",
            (
                "club_name,normalized_club_name,city,country,metadata,source",
                "club_name,normalized_club_name,city,country,metadata",
                "club_name,city,country",
            ),
        ),
        ("fs_club_rankings", ("club,country,city,metadata", "club,country,metadata", "club,country")),
        ("fs_fencers", ("club,country,city,metadata", "club,country,metadata", "club,country")),
    )
    clubs: dict[tuple[str, str, str], dict[str, Any]] = {}

    for table, column_options in source_tables:
        rows = fetch_rows_with_column_fallback(
            client,
            table,
            column_options,
            page_size=page_size,
        )
        for row in rows:
            raw_name = clean_text(row.get("club_name") or row.get("club") or row.get("name"))
            normalized = clean_text(row.get("normalized_club_name")) or normalize_club_name(raw_name)
            city = row_city(row)
            if not raw_name or not normalized or not city:
                continue
            country = clean_text(row.get("country")) or "Unknown"
            key = (normalized, city.casefold(), country.casefold())
            if key not in clubs:
                clubs[key] = {
                    "name": display_club_name(raw_name),
                    "normalized_name": normalized,
                    "city": city,
                    "country": country,
                    "source_tables": [],
                }
            if table not in clubs[key]["source_tables"]:
                clubs[key]["source_tables"].append(table)

    return sorted(clubs.values(), key=lambda row: (row["country"], row["city"], row["normalized_name"]))


def candidate_from_row(row: dict[str, Any]) -> ClubCandidate:
    return ClubCandidate(
        name=row["name"],
        normalized_name=row["normalized_name"],
        city=row["city"],
        country=row["country"],
        source_tables=tuple(row.get("source_tables") or ()),
    )


def build_search_query(club: ClubCandidate) -> str:
    parts = ["fencing club", club.name, club.city]
    if club.country and club.country != "Unknown":
        parts.append(club.country)
    return " ".join(part for part in parts if clean_text(part))


def place_maps_url(place_id: str | None) -> str | None:
    if not place_id:
        return None
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"


def place_location(place: dict[str, Any]) -> dict[str, Any] | None:
    geometry = place.get("geometry")
    if not isinstance(geometry, dict):
        return None
    location = geometry.get("location")
    return location if isinstance(location, dict) else None


def place_city_text(place: dict[str, Any]) -> str | None:
    return clean_text(place.get("formatted_address") or place.get("vicinity"))


def name_match_score(club: ClubCandidate, place: dict[str, Any]) -> int:
    club_name = club.normalized_name or normalize_club_name(club.name)
    place_name = normalize_club_name(place.get("name"))
    if not club_name or not place_name:
        return 0
    if club_name == place_name:
        return 3
    if club_name in place_name or place_name in club_name:
        return 2
    tokens = [token for token in club_name.split() if len(token) > 2]
    if tokens and all(token in place_name for token in tokens):
        return 2
    return 0


def place_match_score(club: ClubCandidate, place: dict[str, Any]) -> int:
    score = name_match_score(club, place)
    address = place_city_text(place)
    if address and club.city.casefold() in address.casefold():
        score += 2
    return score


def has_review_signal(place: dict[str, Any]) -> bool:
    return to_float(place.get("rating")) is not None or to_int(place.get("user_ratings_total")) is not None


def select_place_result(
    payload: dict[str, Any],
    club: ClubCandidate,
) -> tuple[dict[str, Any] | None, int]:
    if not isinstance(payload, dict):
        return None, 0
    status = payload.get("status")
    if status == "ZERO_RESULTS":
        print(f"No Google Places match for {club.name} in {club.city}")
        return None, 0
    if status != "OK":
        print(f"Google Places lookup for {club.name} returned status {status}")
        return None, 0

    scored = []
    for result in payload.get("results") or []:
        if not isinstance(result, dict) or not has_review_signal(result):
            continue
        score = place_match_score(club, result)
        if score >= 3:
            scored.append((score, result))

    if not scored:
        print(f"No Google Places review match for {club.name} in {club.city}")
        return None, 0

    scored.sort(key=lambda item: (-item[0], clean_text(item[1].get("name")) or ""))
    best_score, best = scored[0]
    tied = [item for item in scored[1:] if item[0] == best_score]
    if tied:
        names = [clean_text(best.get("name")) or clean_text(best.get("place_id")) or "unknown"]
        names.extend(clean_text(item[1].get("name")) or clean_text(item[1].get("place_id")) or "unknown" for item in tied)
        print(f"Ambiguous Google Places match for {club.name}: {', '.join(names)}")
        return None, 0

    return best, best_score


def details_result(details_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(details_payload, dict) or details_payload.get("status") != "OK":
        return None
    result = details_payload.get("result")
    return result if isinstance(result, dict) else None


def merged_place(search_result: dict[str, Any], details_payload: dict[str, Any] | None) -> dict[str, Any]:
    details = details_result(details_payload)
    if not details:
        return dict(search_result)
    merged = dict(search_result)
    merged.update({key: value for key, value in details.items() if value is not None})
    return merged


def parse_google_places_response(
    search_payload: dict[str, Any],
    club: ClubCandidate,
    *,
    search_query: str,
    details_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    selected, match_score = select_place_result(search_payload, club)
    if not selected:
        return None

    place = merged_place(selected, details_payload)
    return review_from_place(place, club, search_query=search_query, match_score=match_score)


def review_from_place(
    place: dict[str, Any],
    club: ClubCandidate,
    *,
    search_query: str,
    match_score: int,
) -> dict[str, Any] | None:
    rating = to_float(place.get("rating"))
    review_count = to_int(place.get("user_ratings_total"))
    if rating is None and review_count is None:
        print(f"Google Places match for {club.name} has no public rating data")
        return None

    place_id = clean_text(place.get("place_id"))
    source_url = clean_text(place.get("url")) or place_maps_url(place_id)
    metadata = {
        "business_status": place.get("business_status"),
        "formatted_address": place.get("formatted_address"),
        "google_name": place.get("name"),
        "international_phone_number": place.get("international_phone_number"),
        "location": place_location(place),
        "match_score": match_score,
        "place_id": place_id,
        "search_query": search_query,
        "types": place.get("types") or [],
        "website": place.get("website"),
    }
    return {
        "source": REVIEW_SOURCE,
        "rating": rating,
        "review_count": review_count,
        "review_summary": review_summary_for_rating(rating, review_count),
        "source_url": source_url,
        "metadata": {key: value for key, value in metadata.items() if value is not None},
    }


def fetch_place_details(
    place_id: str | None,
    *,
    maps_api_key: str,
    session: requests.Session,
    timeout: int,
) -> dict[str, Any] | None:
    if not place_id:
        return None
    response = session.get(
        GOOGLE_PLACE_DETAILS_URL,
        params={"place_id": place_id, "fields": PLACE_DETAILS_FIELDS, "key": maps_api_key},
        headers=HEADERS,
        timeout=timeout,
    )
    if response.status_code != 200:
        print(f"Google Place Details lookup failed for {place_id}: HTTP {response.status_code}")
        return None
    payload = response.json()
    if payload.get("status") != "OK":
        print(f"Google Place Details lookup failed for {place_id}: {payload.get('status')}")
        return None
    return payload


def query_google_places_review(
    club: ClubCandidate,
    *,
    maps_api_key: str | None | object = _UNSET,
    session: requests.Session | None = None,
    timeout: int = 15,
) -> dict[str, Any] | None:
    if maps_api_key is _UNSET:
        maps_api_key = os.environ.get("MAPS_API_KEY")
    if not maps_api_key:
        print("MAPS_API_KEY not set; skipping Google Places lookups")
        return None

    query = build_search_query(club)
    http = session or requests.Session()
    try:
        response = http.get(
            GOOGLE_TEXT_SEARCH_URL,
            params={"query": query, "key": maps_api_key},
            headers=HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            print(f"Google Places lookup failed for {club.name}: HTTP {response.status_code}")
            return None
        search_payload = response.json()
        selected, _match_score = select_place_result(search_payload, club)
        details_payload = None
        if selected:
            details_payload = fetch_place_details(
                clean_text(selected.get("place_id")),
                maps_api_key=maps_api_key,
                session=http,
                timeout=timeout,
            )
            return review_from_place(
                merged_place(selected, details_payload),
                club,
                search_query=query,
                match_score=_match_score,
            )
        return None
    except Exception as exc:
        print(f"Google Places lookup failed for {club.name}: {exc}")
        return None


def review_row_id(
    normalized_club_name: str,
    city: str,
    country: str,
    source: str,
) -> str:
    key = "|".join(
        [
            normalized_club_name.casefold(),
            city.casefold(),
            country.casefold(),
            source.casefold(),
        ]
    )
    return str(uuid.uuid5(CLUB_REVIEW_NAMESPACE, key))


def build_review_row(
    club: ClubCandidate,
    review: dict[str, Any],
    *,
    scraped_at: str | None = None,
) -> dict[str, Any]:
    normalized = club.normalized_name or normalize_club_name(club.name)
    if not normalized:
        raise ValueError(f"Cannot normalize club name: {club.name!r}")
    scraped = scraped_at or datetime.now(timezone.utc).isoformat()
    source = clean_text(review.get("source"))
    if not source:
        raise ValueError("Review source is required")
    metadata = review.get("metadata") if isinstance(review.get("metadata"), dict) else {}
    metadata = dict(metadata)
    if club.source_tables:
        metadata["source_tables"] = list(club.source_tables)
    return {
        "id": review_row_id(normalized, club.city, club.country, source),
        "club_name": club.name,
        "normalized_club_name": normalized,
        "city": club.city,
        "country": club.country,
        "source": source,
        "rating": to_float(review.get("rating")),
        "review_count": to_int(review.get("review_count")),
        "review_summary": clean_text(review.get("review_summary")),
        "source_url": clean_text(review.get("source_url")),
        "metadata": metadata,
        "scraped_at": scraped,
    }


def upsert_review_rows(client, rows: list[dict[str, Any]], *, batch_size: int = UPSERT_BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_club_reviews").upsert(
            batch,
            on_conflict=REVIEW_CONFLICT_COLUMNS,
        ).execute()
        written += len(batch)
    return written


def scrape_google_club_reviews(
    client,
    *,
    maps_api_key: str | None | object = _UNSET,
    session: requests.Session | None = None,
    page_size: int = PAGE_SIZE,
    batch_size: int = UPSERT_BATCH_SIZE,
    request_delay: float = REQUEST_DELAY,
    scraped_at: str | None = None,
) -> dict[str, int]:
    club_rows = fetch_distinct_clubs(client, page_size=page_size)
    clubs = [candidate_from_row(row) for row in club_rows]
    rows = []
    skipped = 0
    failed = 0
    maps_key = os.environ.get("MAPS_API_KEY") if maps_api_key is _UNSET else maps_api_key

    if not maps_key:
        print("MAPS_API_KEY not set; skipping Google Places lookups")
        return {
            "clubs_seen": len(clubs),
            "review_rows": 0,
            "written": 0,
            "failed": 0,
            "skipped": len(clubs),
        }

    for club in clubs:
        try:
            review = query_google_places_review(
                club,
                maps_api_key=maps_key,
                session=session,
            )
            if not review:
                skipped += 1
            else:
                rows.append(build_review_row(club, review, scraped_at=scraped_at))
        except Exception as exc:
            failed += 1
            print(f"Google Places review lookup failed for {club.name}: {exc}")

        if request_delay:
            time.sleep(request_delay)

    written = upsert_review_rows(client, rows, batch_size=batch_size) if rows else 0
    return {
        "clubs_seen": len(clubs),
        "review_rows": len(rows),
        "written": written,
        "failed": failed,
        "skipped": skipped,
    }


def no_key_summary() -> dict[str, int]:
    return {
        "clubs_seen": 0,
        "review_rows": 0,
        "written": 0,
        "failed": 0,
        "skipped": 0,
    }


def main() -> None:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        maps_key = os.environ.get("MAPS_API_KEY")
        if not maps_key:
            summary = no_key_summary()
            print("MAPS_API_KEY not set; skipping Google Places lookups")
            run_log.complete(written=0, failed=0, skipped=0, metadata=summary)
            return

        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous Google club review state: {previous_state}")

        client = get_supabase_client()
        summary = scrape_google_club_reviews(client, maps_api_key=maps_key)
        set_state(
            SOURCE,
            "last_run",
            {
                **summary,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        run_log.complete(
            written=summary["written"],
            failed=summary["failed"],
            skipped=summary["skipped"],
            metadata=summary,
        )
        print(
            "Google club reviews scrape complete: "
            f"{summary['written']} rows written, "
            f"{summary['skipped']} clubs skipped, "
            f"{summary['failed']} failures"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

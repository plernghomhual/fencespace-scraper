import os
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "scrape_club_reviews"
PAGE_SIZE = 1000
UPSERT_BATCH_SIZE = 100
REQUEST_DELAY = 0.25
GOOGLE_MAPS_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
REVIEW_CONFLICT_COLUMNS = "normalized_club_name,city,country,source"
CLUB_REVIEW_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://fencespace.app/fs_club_reviews")
_UNSET = object()

HEADERS = {
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; contact@fencespace.app)",
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
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


def parse_google_maps_response(
    payload: dict[str, Any],
    club: ClubCandidate,
    *,
    search_query: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or payload.get("status") not in {"OK", "ZERO_RESULTS"}:
        return None

    for result in payload.get("results") or []:
        rating = to_float(result.get("rating"))
        review_count = to_int(result.get("user_ratings_total"))
        if rating is None and review_count is None:
            continue

        place_id = clean_text(result.get("place_id"))
        source_url = (
            f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            if place_id
            else clean_text(result.get("url"))
        )
        metadata = {
            "business_status": result.get("business_status"),
            "formatted_address": result.get("formatted_address"),
            "google_name": result.get("name"),
            "place_id": place_id,
            "search_query": search_query,
            "types": result.get("types") or [],
        }
        return {
            "source": "google_maps",
            "rating": rating,
            "review_count": review_count,
            "review_summary": review_summary_for_rating(rating, review_count),
            "source_url": source_url,
            "metadata": metadata,
        }
    return None


def query_google_maps_review(
    club: ClubCandidate,
    *,
    maps_api_key: str | None | object = _UNSET,
    session: requests.Session | None = None,
    timeout: int = 15,
) -> dict[str, Any] | None:
    if maps_api_key is _UNSET:
        maps_api_key = os.environ.get("MAPS_API_KEY")
    if not maps_api_key:
        print("MAPS_API_KEY not set; skipping Google Maps")
        return None

    query = f"fencing club {club.name} {club.city}"
    http = session or requests.Session()
    try:
        response = http.get(
            GOOGLE_MAPS_TEXT_SEARCH_URL,
            params={"query": query, "key": maps_api_key},
            headers=HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            print(f"Google Maps lookup failed for {club.name}: HTTP {response.status_code}")
            return None
        return parse_google_maps_response(response.json(), club, search_query=query)
    except Exception as exc:
        print(f"Google Maps lookup failed for {club.name}: {exc}")
        return None


def mentions_club(text: Any, club_name: str) -> bool:
    haystack = normalize_club_name(text)
    needle = normalize_club_name(club_name)
    if not haystack or not needle:
        return False
    if needle in haystack:
        return True
    tokens = [token for token in needle.split() if len(token) > 2]
    return bool(tokens) and all(token in haystack for token in tokens)


def parse_reddit_search_response(payload: dict[str, Any], club_name: str) -> dict[str, Any] | None:
    threads = []
    children = ((payload or {}).get("data") or {}).get("children") or []
    for child in children:
        data = child.get("data") or {}
        title = clean_text(data.get("title"))
        body = clean_text(data.get("selftext"))
        if not title or not mentions_club(f"{title} {body or ''}", club_name):
            continue
        permalink = clean_text(data.get("permalink"))
        url = clean_text(data.get("url"))
        if permalink:
            url = urljoin("https://www.reddit.com", permalink)
        threads.append(
            {
                "title": title,
                "url": url,
                "comments": to_int(data.get("num_comments")) or 0,
                "score": to_int(data.get("score")) or 0,
            }
        )

    if not threads:
        return None
    summary = "; ".join(thread["title"] for thread in threads[:3])
    return {
        "source": "reddit",
        "rating": None,
        "review_count": len(threads),
        "review_summary": f"Found {len(threads)} r/fencing thread(s): {summary}",
        "source_url": threads[0]["url"],
        "metadata": {"threads": threads},
    }


def parse_fencing_net_search_html(html: str, club_name: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html or "", "html.parser")
    seen = set()
    threads = []
    for link in soup.find_all("a", href=True):
        title = clean_text(link.get_text(" "))
        href = clean_text(link.get("href"))
        if not title or not href or not mentions_club(f"{title} {href}", club_name):
            continue
        url = urljoin("https://fencing.net", href)
        if url in seen:
            continue
        seen.add(url)
        threads.append({"title": title, "url": url})

    if not threads:
        return None
    summary = "; ".join(thread["title"] for thread in threads[:3])
    return {
        "source": "fencing_net",
        "rating": None,
        "review_count": len(threads),
        "review_summary": f"Found {len(threads)} fencing.net thread(s): {summary}",
        "source_url": threads[0]["url"],
        "metadata": {"threads": threads},
    }


def query_reddit_review(
    club: ClubCandidate,
    *,
    session: requests.Session | None = None,
    timeout: int = 15,
) -> dict[str, Any] | None:
    http = session or requests.Session()
    try:
        response = http.get(
            "https://www.reddit.com/r/Fencing/search.json",
            params={
                "q": f"{club.name} fencing club",
                "restrict_sr": "1",
                "sort": "relevance",
                "limit": "10",
                "raw_json": "1",
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            print(f"reddit search skipped for {club.name}: HTTP {response.status_code}")
            return None
        return parse_reddit_search_response(response.json(), club.name)
    except Exception as exc:
        print(f"reddit search skipped for {club.name}: {exc}")
        return None


def query_fencing_net_review(
    club: ClubCandidate,
    *,
    session: requests.Session | None = None,
    timeout: int = 15,
) -> dict[str, Any] | None:
    http = session or requests.Session()
    try:
        response = http.get(
            "https://fencing.net/466/search-fencing-net/",
            params={"q": f"{club.name} fencing club"},
            headers=HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            print(f"fencing.net search skipped for {club.name}: HTTP {response.status_code}")
            return None
        return parse_fencing_net_search_html(response.text, club.name)
    except Exception as exc:
        print(f"fencing.net search skipped for {club.name}: {exc}")
        return None


def query_forum_reviews(
    club: ClubCandidate,
    *,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    reviews = []
    for query_func in (query_reddit_review, query_fencing_net_review):
        review = query_func(club, session=session)
        if review:
            reviews.append(review)
    return reviews


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
        ("fs_fencers", ("club,country,city,metadata", "club,country,metadata", "club,country")),
        ("fs_club_rankings", ("club,country,city,metadata", "club,country,metadata", "club,country")),
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
            raw_name = clean_text(row.get("club") or row.get("club_name") or row.get("name"))
            normalized = normalize_club_name(raw_name)
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
        "metadata": review.get("metadata") if isinstance(review.get("metadata"), dict) else {},
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


def candidate_from_row(row: dict[str, Any]) -> ClubCandidate:
    return ClubCandidate(
        name=row["name"],
        normalized_name=row["normalized_name"],
        city=row["city"],
        country=row["country"],
        source_tables=tuple(row.get("source_tables") or ()),
    )


def scrape_club_reviews(
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
        print("MAPS_API_KEY not set; skipping Google Maps")

    for club in clubs:
        reviews = []
        if maps_key:
            google_review = query_google_maps_review(
                club,
                maps_api_key=maps_key,
                session=session,
            )
            if google_review:
                reviews.append(google_review)
            else:
                skipped += 1
        else:
            skipped += 1

        try:
            reviews.extend(query_forum_reviews(club, session=session))
        except Exception as exc:
            failed += 1
            print(f"Forum review lookup failed for {club.name}: {exc}")

        for review in reviews:
            try:
                rows.append(build_review_row(club, review, scraped_at=scraped_at))
            except Exception as exc:
                failed += 1
                print(f"Could not build review row for {club.name}: {exc}")

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


def main() -> None:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous club review state: {previous_state}")

        client = get_supabase_client()
        summary = scrape_club_reviews(client)
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
            "Club reviews scrape complete: "
            f"{summary['written']} rows written, "
            f"{summary['skipped']} sources skipped, "
            f"{summary['failed']} failures"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

import hashlib
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from supabase import create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "scrape_camp_reviews"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
HEADERS = {"User-Agent": "FenceSpaceBot/1.0 (+https://fencespace.local)"}
BATCH_SIZE = 100
REQUEST_DELAY = 0.25
GOOGLE_MAPS_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
GOOGLE_MAPS_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
REVIEW_CONFLICT_COLUMNS = "source,source_url,source_hash"
CAMP_SELECT_COLUMNS = "id,name,organizer,city,country,start_date,end_date,source_url,metadata"
_UNSET = object()


@dataclass(frozen=True)
class ReviewSource:
    url: str
    organizer: str | None = None
    city: str | None = None
    country: str | None = None
    source_kind: str = "club_page"


@dataclass(frozen=True)
class FetchedContent:
    content: bytes
    content_type: str
    final_url: str


class RateLimiter:
    def __init__(self, delay: float = REQUEST_DELAY, sleep: Callable[[float], None] = time.sleep):
        self.delay = max(0.0, delay)
        self.sleep = sleep
        self._last_request = 0.0

    def wait(self) -> None:
        if not self.delay:
            return
        now = time.monotonic()
        remaining = self.delay - (now - self._last_request)
        if remaining > 0:
            self.sleep(remaining)
        self._last_request = time.monotonic()


DEFAULT_SOURCES = [
    ReviewSource(
        url="https://www.hookedonfencing.org/camp",
        organizer="Hooked on Fencing",
        city="North Royalton",
        country="USA",
        source_kind="club_page",
    ),
    ReviewSource(
        url="https://www.capfencing.com/camps",
        organizer="Capital Fencing Academy",
        city="North Jersey",
        country="USA",
        source_kind="club_page",
    ),
    ReviewSource(
        url="https://www.nwfencing.org/camps/",
        organizer="Northwest Fencing Center",
        city="Portland",
        country="USA",
        source_kind="club_page",
    ),
]


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    return text


def to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def review_snippet(text: Any, *, max_length: int = 500) -> str | None:
    cleaned = clean_text(text)
    if not cleaned:
        return None
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "..."


def parse_rating_from_text(text: str | None) -> float | None:
    if not text:
        return None
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(?:out of|/)\s*5",
        r"rating\s*:?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*stars?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return to_float(match.group(1))
    return None


def extract_jsonld_aggregate(soup: BeautifulSoup) -> dict[str, int | float]:
    aggregate: dict[str, int | float] = {}
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            rating = item.get("aggregateRating")
            if not isinstance(rating, dict):
                continue
            rating_value = to_float(rating.get("ratingValue"))
            review_count = to_int(rating.get("reviewCount") or rating.get("ratingCount"))
            if rating_value is not None:
                aggregate["aggregate_rating"] = rating_value
            if review_count is not None:
                aggregate["aggregate_review_count"] = review_count
            if aggregate:
                return aggregate
    return aggregate


def is_review_card_marker(element) -> bool:
    attrs = " ".join(
        str(value)
        for value in [
            element.get("class") or "",
            element.get("id") or "",
            element.get("data-review") or "",
            element.get("data-testid") or "",
        ]
    ).casefold()
    tokens = {token for token in re.split(r"[^a-z]+", attrs) if token}
    return bool(
        {"review", "reviews", "testimonial", "testimonials"} & tokens
        or element.get("data-review") is not None
        or "review" in (clean_text(element.get("data-testid") or "") or "").casefold()
    )


def review_cards(soup: BeautifulSoup):
    selector = (
        "article, div, li, section, blockquote, [data-review], [data-testid*='review'], "
        "[class*='review'], [class*='testimonial'], [id*='review'], [id*='testimonial']"
    )
    candidates = [element for element in soup.select(selector) if is_review_card_marker(element)]
    candidate_ids = {id(element) for element in candidates}
    cards = []
    for element in candidates:
        has_child_card = any(id(child) in candidate_ids for child in element.select(selector))
        if has_child_card and not element.get("data-review") and not element.get("data-camp"):
            continue
        cards.append(element)
    return cards


def extract_card_rating(card) -> float | None:
    for attr in ("data-rating", "aria-label", "title"):
        rating = parse_rating_from_text(clean_text(card.get(attr)))
        if rating is not None:
            return rating
    for element in card.select("[aria-label], [title], .stars, .rating, [class*='star']"):
        text = " ".join(
            filter(
                None,
                [
                    clean_text(element.get("aria-label")),
                    clean_text(element.get("title")),
                    clean_text(element.get_text(" ", strip=True)),
                ],
            )
        )
        rating = parse_rating_from_text(text)
        if rating is not None:
            return rating
    return parse_rating_from_text(card.get_text(" ", strip=True))


def extract_card_reviewer(card) -> str | None:
    for selector in (
        ".reviewer",
        ".testimonial-author",
        ".author",
        "[class*='reviewer']",
        "[class*='author']",
        "[itemprop='author']",
    ):
        element = card.select_one(selector)
        if element:
            return clean_text(element.get_text(" ", strip=True).lstrip("- "))
    return None


def extract_card_snippet(card) -> str | None:
    for selector in ("blockquote", "[itemprop='reviewBody']", ".review-body", ".testimonial-text"):
        element = card.select_one(selector)
        if element:
            return review_snippet(element.get_text(" ", strip=True))
    text = card.get_text(" ", strip=True)
    reviewer = extract_card_reviewer(card)
    if reviewer:
        text = text.replace(reviewer, "")
    return review_snippet(text)


def extract_card_camp_name(card, source: ReviewSource) -> str | None:
    explicit = clean_text(card.get("data-camp") or card.get("data-camp-name"))
    if explicit:
        return explicit
    for selector in ("h1", "h2", "h3", "h4", "[itemprop='itemReviewed']"):
        element = card.select_one(selector)
        if element:
            heading = clean_text(element.get_text(" ", strip=True))
            if heading:
                return heading.rstrip(":")
    return None


def extract_card_source_url(card, source: ReviewSource) -> str:
    anchor = card.select_one("a[href]")
    if anchor:
        return urljoin(source.url, anchor.get("href"))
    element_id = clean_text(card.get("id"))
    if element_id:
        return f"{source.url.rstrip('/')}#{element_id}"
    return source.url


def parse_public_review_html(html: str, source: ReviewSource) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    aggregate = extract_jsonld_aggregate(soup)
    reviews = []
    for card in review_cards(soup):
        snippet = extract_card_snippet(card)
        rating = extract_card_rating(card)
        if not snippet and rating is None:
            continue
        metadata: dict[str, Any] = {"source_kind": source.source_kind}
        metadata.update(aggregate)  # type: ignore[arg-type]
        reviews.append(
            {
                "camp_name": extract_card_camp_name(card, source),
                "organizer": source.organizer,
                "city": source.city,
                "country": source.country,
                "source": source.source_kind,
                "rating": rating,
                "review_count": 1,
                "review_text_snippet": snippet,
                "reviewer_name": extract_card_reviewer(card),
                "source_url": extract_card_source_url(card, source),
                "metadata": metadata,
            }
        )
    return reviews


def fetch_source(
    source: ReviewSource,
    *,
    session: requests.Session | None = None,
    timeout: int = 20,
    rate_limiter: RateLimiter | None = None,
) -> FetchedContent:
    if rate_limiter:
        rate_limiter.wait()
    http = session or requests.Session()
    response = http.get(source.url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return FetchedContent(
        content=response.content,
        content_type=response.headers.get("content-type", ""),
        final_url=response.url,
    )


def parse_fetched_content(source: ReviewSource, fetched: FetchedContent) -> list[dict[str, Any]]:
    text = fetched.content.decode("utf-8", errors="replace")
    content_type = fetched.content_type.lower()
    if "html" in content_type or text.lstrip().startswith("<"):
        reviews = parse_public_review_html(text, source)
    elif "json" in content_type:
        payload = json.loads(text)
        reviews = parse_public_review_api_payload(payload, source)
    else:
        reviews = []
    for review in reviews:
        if review.get("source_url") == source.url and fetched.final_url:
            review["source_url"] = fetched.final_url
    return reviews


def parse_public_review_api_payload(payload: Any, source: ReviewSource) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("reviews")
    if not isinstance(items, list):
        return []
    reviews = []
    for item in items:
        if not isinstance(item, dict):
            continue
        reviews.append(
            {
                "camp_name": clean_text(item.get("camp_name") or item.get("camp")),
                "organizer": source.organizer,
                "city": source.city,
                "country": source.country,
                "source": source.source_kind,
                "rating": to_float(item.get("rating")),
                "review_count": 1,
                "review_text_snippet": review_snippet(item.get("text") or item.get("review")),
                "reviewer_name": clean_text(item.get("reviewer") or item.get("author")),
                "source_url": clean_text(item.get("url")) or source.url,
                "metadata": {"source_kind": source.source_kind},
            }
        )
    return reviews


def parse_google_places_details_response(
    payload: dict[str, Any],
    camp: dict[str, Any],
    *,
    search_query: str,
) -> list[dict[str, Any]]:
    if payload.get("status") != "OK":
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    source_url = (
        clean_text(result.get("url"))
        or f"https://www.google.com/maps/place/?q=place_id:{clean_text(result.get('place_id'))}"
    )
    metadata = {
        "place_id": clean_text(result.get("place_id")),
        "google_name": clean_text(result.get("name")),
        "search_query": search_query,
        "aggregate_rating": to_float(result.get("rating")),
    }
    metadata = {key: value for key, value in metadata.items() if value is not None}
    aggregate_count = to_int(result.get("user_ratings_total"))
    reviews = result.get("reviews")
    if isinstance(reviews, list) and reviews:
        parsed = []
        for item in reviews:
            if not isinstance(item, dict):
                continue
            item_metadata = dict(metadata)
            if item.get("time") is not None:
                item_metadata["review_time"] = item.get("time")
            parsed.append(
                {
                    "camp_name": camp.get("name"),
                    "organizer": camp.get("organizer"),
                    "city": camp.get("city"),
                    "country": camp.get("country"),
                    "start_date": camp.get("start_date"),
                    "end_date": camp.get("end_date"),
                    "source": "google_places",
                    "rating": to_float(item.get("rating")),
                    "review_count": aggregate_count,
                    "review_text_snippet": review_snippet(item.get("text")),
                    "reviewer_name": clean_text(item.get("author_name")),
                    "source_url": source_url,
                    "metadata": item_metadata,
                }
            )
        return parsed
    if metadata.get("aggregate_rating") is not None or aggregate_count is not None:
        return [
            {
                "camp_name": camp.get("name"),
                "organizer": camp.get("organizer"),
                "city": camp.get("city"),
                "country": camp.get("country"),
                "start_date": camp.get("start_date"),
                "end_date": camp.get("end_date"),
                "source": "google_places",
                "rating": metadata.get("aggregate_rating"),
                "review_count": aggregate_count,
                "review_text_snippet": None,
                "reviewer_name": None,
                "source_url": source_url,
                "metadata": metadata,
            }
        ]
    return []


def query_google_places_camp_reviews(
    camp: dict[str, Any],
    *,
    maps_api_key: str | None | object = _UNSET,
    session: requests.Session | None = None,
    timeout: int = 15,
    rate_limiter: RateLimiter | None = None,
) -> list[dict[str, Any]]:
    if maps_api_key is _UNSET:
        maps_api_key = os.environ.get("MAPS_API_KEY")
    if not maps_api_key:
        print("MAPS_API_KEY not set; skipping Google Places")
        return []

    query = " ".join(
        filter(
            None,
            [
                clean_text(camp.get("name")),
                clean_text(camp.get("organizer")),
                clean_text(camp.get("city")),
                clean_text(camp.get("country")),
            ],
        )
    )
    http = session or requests.Session()
    try:
        if rate_limiter:
            rate_limiter.wait()
        search_response = http.get(
            GOOGLE_MAPS_TEXT_SEARCH_URL,
            params={"query": query, "key": maps_api_key},
            headers=HEADERS,
            timeout=timeout,
        )
        if search_response.status_code != 200:
            print(f"Google Places search failed for {camp.get('name')}: HTTP {search_response.status_code}")
            return []
        search_payload = search_response.json()
        results = search_payload.get("results") or []
        if not results:
            return []
        place_id = clean_text(results[0].get("place_id"))
        if not place_id:
            return []
        if rate_limiter:
            rate_limiter.wait()
        details_response = http.get(
            GOOGLE_MAPS_DETAILS_URL,
            params={
                "place_id": place_id,
                "fields": "name,place_id,rating,user_ratings_total,url,reviews",
                "key": maps_api_key,
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if details_response.status_code != 200:
            print(f"Google Places details failed for {camp.get('name')}: HTTP {details_response.status_code}")
            return []
        return parse_google_places_details_response(
            details_response.json(),
            camp,
            search_query=query,
        )
    except Exception as exc:
        print(f"Google Places lookup skipped for {camp.get('name')}: {exc}")
        return []


def name_matches(review_name: Any, camp_name: Any) -> bool:
    review_key = normalize_key(review_name)
    camp_key = normalize_key(camp_name)
    if not review_key or not camp_key:
        return False
    return review_key == camp_key or review_key in camp_key or camp_key in review_key


def same_value(left: Any, right: Any) -> bool:
    return bool(left and right and normalize_key(left) == normalize_key(right))


def match_review_to_camp(
    review: dict[str, Any],
    camps: Iterable[dict[str, Any]],
    *,
    ambiguity_log: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    candidates = [camp for camp in camps if name_matches(review.get("camp_name"), camp.get("name"))]
    if not candidates:
        return None

    scored: list[tuple[int, dict[str, Any]]] = []
    for camp in candidates:
        score = 4
        if same_value(review.get("organizer"), camp.get("organizer")):
            score += 3
        if same_value(review.get("city"), camp.get("city")):
            score += 2
        if same_value(review.get("country"), camp.get("country")):
            score += 1
        if review.get("start_date") and review.get("start_date") == camp.get("start_date"):
            score += 2
        if review.get("end_date") and review.get("end_date") == camp.get("end_date"):
            score += 2
        if review.get("source_url") and review.get("source_url") == camp.get("source_url"):
            score += 1
        scored.append((score, camp))

    best_score = max(score for score, _camp in scored)
    best = [camp for score, camp in scored if score == best_score]
    if len(best) == 1:
        return best[0]
    if ambiguity_log is not None:
        ambiguity_log.append(
            {
                "camp_name": clean_text(review.get("camp_name")),
                "reason": "ambiguous_match",
                "candidate_ids": [camp.get("id") for camp in best],
            }
        )
    return None


PII_METADATA_RE = re.compile(r"(reviewer|author|email|phone|contact|name)$", flags=re.I)


def sanitized_metadata(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        if PII_METADATA_RE.search(str(key)):
            continue
        if isinstance(value, dict):
            nested = sanitized_metadata(value)
            if nested:
                clean[key] = nested
        elif isinstance(value, list):
            clean[key] = [
                sanitized_metadata(item) if isinstance(item, dict) else item
                for item in value
                if not isinstance(item, str) or "@" not in item
            ]
        else:
            clean[key] = value
    return clean


def stable_hash(*values: Any) -> str:
    joined = "|".join(clean_text(value) or "" for value in values)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def build_review_row(
    review: dict[str, Any],
    camp: dict[str, Any] | None,
    *,
    scraped_at: str | None = None,
) -> dict[str, Any]:
    source = clean_text(review.get("source"))
    source_url = clean_text(review.get("source_url"))
    camp_name = clean_text((camp or {}).get("name") or review.get("camp_name"))
    if not source:
        raise ValueError("Review source is required")
    if not source_url:
        raise ValueError("Review source_url is required")
    if not camp_name:
        raise ValueError("Review camp_name is required")

    reviewer = clean_text(review.get("reviewer_name"))
    reviewer_hash = stable_hash(source, source_url, reviewer) if reviewer else None
    snippet = review_snippet(review.get("review_text_snippet"))
    source_hash = stable_hash(source, source_url, reviewer_hash, snippet, review.get("rating"))
    metadata = sanitized_metadata(review.get("metadata"))

    return {
        "camp_id": (camp or {}).get("id"),
        "camp_name": camp_name,
        "camp_organizer": clean_text((camp or {}).get("organizer") or review.get("organizer")),
        "camp_start_date": (camp or {}).get("start_date") or review.get("start_date"),
        "camp_end_date": (camp or {}).get("end_date") or review.get("end_date"),
        "camp_city": clean_text((camp or {}).get("city") or review.get("city")),
        "camp_country": clean_text((camp or {}).get("country") or review.get("country")),
        "source": source,
        "rating": to_float(review.get("rating")),
        "review_count": to_int(review.get("review_count")),
        "review_text_snippet": snippet,
        "reviewer_hash": reviewer_hash,
        "source_url": source_url,
        "source_hash": source_hash,
        "metadata": metadata,
        "scraped_at": scraped_at or datetime.now(timezone.utc).isoformat(),
    }


def dedupe_review_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped = 0
    for row in rows:
        key = (row["source"], row["source_url"], row["source_hash"])
        if key in deduped:
            skipped += 1
            continue
        deduped[key] = row
    return list(deduped.values()), skipped


def upsert_review_rows(client, rows: list[dict[str, Any]], *, batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_training_camp_reviews").upsert(
            batch,
            on_conflict=REVIEW_CONFLICT_COLUMNS,
        ).execute()
        written += len(batch)
    return written


def fetch_existing_camps(client) -> list[dict[str, Any]]:
    result = client.table("fs_training_camps").select(CAMP_SELECT_COLUMNS).execute()
    return result.data or []


def scrape_camp_reviews(
    *,
    client=None,
    sources: Iterable[ReviewSource] | None = None,
    fetcher: Callable[..., FetchedContent] = fetch_source,
    maps_api_key: str | None | object = _UNSET,
    request_delay: float = REQUEST_DELAY,
    log_run: bool = True,
    update_state: bool = True,
    scraped_at: str | None = None,
) -> dict[str, int]:
    client = client or get_supabase_client()
    sources = list(sources or DEFAULT_SOURCES)
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    limiter = RateLimiter(request_delay)
    failed = 0
    skipped = 0
    ambiguous = 0
    rows: list[dict[str, Any]] = []

    try:
        camps = fetch_existing_camps(client)
        ambiguity_log: list[dict[str, Any]] = []
        for source in sources:
            try:
                fetched = fetcher(source, rate_limiter=limiter)
                reviews = parse_fetched_content(source, fetched)
            except TypeError:
                fetched = fetcher(source)
                reviews = parse_fetched_content(source, fetched)
            except Exception as exc:
                failed += 1
                print(f"[{SOURCE}] source failed {source.url}: {exc}")
                continue

            for review in reviews:
                matched = match_review_to_camp(review, camps, ambiguity_log=ambiguity_log)
                if ambiguity_log and len(ambiguity_log) > ambiguous:
                    ambiguous = len(ambiguity_log)
                    skipped += 1
                    continue
                try:
                    rows.append(build_review_row(review, matched, scraped_at=scraped_at))
                except Exception as exc:
                    failed += 1
                    print(f"[{SOURCE}] could not build review row from {source.url}: {exc}")

        maps_key = os.environ.get("MAPS_API_KEY") if maps_api_key is _UNSET else maps_api_key
        if maps_key:
            for camp in camps:
                api_reviews = query_google_places_camp_reviews(
                    camp,
                    maps_api_key=maps_key,
                    rate_limiter=limiter,
                )
                for review in api_reviews:
                    try:
                        rows.append(build_review_row(review, camp, scraped_at=scraped_at))
                    except Exception as exc:
                        failed += 1
                        print(f"[{SOURCE}] could not build Google Places row for {camp.get('name')}: {exc}")
        else:
            skipped += len(camps)
            print("MAPS_API_KEY not set; skipping Google Places")

        deduped_rows, duplicate_skips = dedupe_review_rows(rows)
        skipped += duplicate_skips
        written = upsert_review_rows(client, deduped_rows) if deduped_rows else 0
        summary = {
            "camps_seen": len(camps),
            "sources_seen": len(sources),
            "review_rows": len(deduped_rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "ambiguous": ambiguous,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {**summary, "updated_at": datetime.now(timezone.utc).isoformat()},
            )
            if ambiguity_log:
                set_state(SOURCE, "last_ambiguities", ambiguity_log[:100])
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


def main() -> None:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous camp review state: {previous_state}")
        summary = scrape_camp_reviews(log_run=False)
        run_log.complete(
            written=summary["written"],
            failed=summary["failed"],
            skipped=summary["skipped"],
            metadata=summary,
        )
        print(
            "Camp reviews scrape complete: "
            f"{summary['written']} rows written, "
            f"{summary['skipped']} skipped, "
            f"{summary['failed']} failures"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

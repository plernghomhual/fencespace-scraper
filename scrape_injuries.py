"""
Public injury and absence scraper.

The scraper stores only source-backed public statements. It does not infer
diagnoses or private medical details beyond what the source states.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from scripts.rate_limiter import RateLimiter
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

STATE_SOURCE = "scrape_injuries"
PAGE_SIZE = 1000
UPSERT_BATCH_SIZE = 100
EXCERPT_LIMIT = int(os.environ.get("INJURY_EXCERPT_LIMIT", "240"))
MAX_ARTICLES_PER_SOURCE = int(os.environ.get("INJURY_MAX_ARTICLES_PER_SOURCE", "40"))
MAX_PROFILE_PROBES = int(os.environ.get("INJURY_MAX_PROFILE_PROBES", "50"))
REFETCH_SEEN = os.environ.get("INJURY_REFETCH_SEEN", "").lower() in {"1", "true", "yes"}

FIE_ARTICLES_URL = "https://fie.org/articles"
BRITISH_FENCING_NEWS_URL = "https://www.britishfencing.com/news/"
FIE_ATHLETE_URL = "https://fie.org/athletes/{fie_id}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_limiter = RateLimiter(default_rps=1.0, jitter=0.2, backoff=5.0)

STATUS_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "suspension",
        (
            r"\bsuspend(?:ed|s|ing)?\b",
            r"\bsuspension\b",
            r"\bsanction(?:ed|s)?\b",
            r"\bbann?ed\b",
            r"\badverse analytical finding\b",
        ),
    ),
    (
        "personal_absence",
        (
            r"\bpersonal reasons?\b",
            r"\bfamily reasons?\b",
            r"\bbereavement\b",
            r"\bstudy abroad\b",
            r"\bmilitary deployment\b",
            r"\bschool requirements?\b",
        ),
    ),
    (
        "illness",
        (
            r"\billness\b",
            r"\bill\b",
            r"\bsick(?:ness)?\b",
            r"\bcovid\b",
            r"\bdehydration\b",
        ),
    ),
    (
        "injury",
        (
            r"\binjur(?:y|ies|ed)\b",
            r"\bsurgery\b",
            r"\bfracture\b",
            r"\bsprain(?:ed)?\b",
            r"\btendinitis\b",
            r"\bmedical withdrawal\b.*\binjur",
        ),
    ),
    (
        "unknown",
        (
            r"\bwithdr(?:aw|awn|ew|awal|awals)\b",
            r"\babsen(?:t|ce)\b",
            r"\bunable to compete\b",
            r"\bwill not compete\b",
            r"\bmiss(?:ed|es|ing)\b",
        ),
    ),
)

FIE_INJURY_STOP_PREFIXES = (
    "awards and honours",
    "sporting philosophy",
    "other information",
    "famous relatives",
    "ambitions",
    "statistics",
    "sanction",
    "occupation",
    "missed olympics",
)


def clean_text(value: Any) -> str:
    text = str(value or "").replace("\u200b", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def source_site_from_url(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def parse_datetime(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.isoformat()
    except ValueError:
        pass

    for fmt in ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC).isoformat()
        except ValueError:
            continue
    return None


def date_only(value: str | None) -> str | None:
    parsed = parse_datetime(value)
    return parsed[:10] if parsed else None


def extract_first_date(text: str) -> str | None:
    patterns = (
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return date_only(match.group(0))
    return None


def make_excerpt(text: str, limit: int = EXCERPT_LIMIT) -> str:
    excerpt = clean_text(text)
    if limit < 4:
        return excerpt[:limit]
    if len(excerpt) <= limit:
        return excerpt
    return f"{excerpt[:limit - 3].rstrip()}..."


def classify_status_type(text: str, default: str | None = None) -> str | None:
    lowered = clean_text(text).casefold()
    for status_type, patterns in STATUS_PATTERNS:
        if any(re.search(pattern, lowered) for pattern in patterns):
            return status_type
    return default


def extract_event_name(text: str) -> str | None:
    statement = clean_text(text)
    patterns = (
        r"\b(?:at|from)\s+the\s+(?P<event>.+?)(?:\s+due to\b|\s+because\b|\s+after\b|\.|\(|$)",
        r"\b(?:at|from)\s+(?P<event>.+?)(?:\s+due to\b|\s+because\b|\s+after\b|\.|\(|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, statement, flags=re.IGNORECASE)
        if not match:
            continue
        event = clean_text(match.group("event"))
        event = re.sub(r"^(?:an?|the)\s+", "", event, flags=re.IGNORECASE)
        return event or None
    return None


def citation_sources(text: str) -> list[str]:
    sources: list[str] = []
    for group in re.findall(r"\(([^()]*(?:\d{4}|profile|media)[^()]*)\)", text):
        for piece in group.split(";"):
            piece = clean_text(piece)
            if piece:
                sources.append(piece)
    return sources


def stable_source_key(*parts: Any) -> str:
    payload = "\n".join(clean_text(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _first_list_value(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return None


def normalize_fencer_record(fencer: dict[str, Any]) -> dict[str, Any]:
    name = (
        clean_text(fencer.get("fencer_name"))
        or clean_text(fencer.get("canonical_name"))
        or clean_text(fencer.get("name"))
    )
    fie_ids = fencer.get("fie_ids")
    if not isinstance(fie_ids, list):
        fie_id = clean_text(fencer.get("fie_id"))
        fie_ids = [fie_id] if fie_id else []
    row_ids = fencer.get("fs_fencer_row_ids")
    if not isinstance(row_ids, list):
        row_id = clean_text(fencer.get("fencer_row_id") or fencer.get("id"))
        row_ids = [row_id] if row_id else []
    return {
        "identity_id": clean_text(fencer.get("identity_id") or fencer.get("id")),
        "fencer_row_id": clean_text(fencer.get("fencer_row_id")) or _first_list_value(row_ids),
        "fencer_name": name,
        "country": clean_text(fencer.get("country")),
        "fie_ids": [clean_text(value) for value in fie_ids if clean_text(value)],
        "fs_fencer_row_ids": [clean_text(value) for value in row_ids if clean_text(value)],
    }


def build_injury_absence_row(
    *,
    fencer: dict[str, Any],
    statement: str,
    status_type: str,
    source_url: str,
    source: str,
    source_site: str | None = None,
    event_name: str | None = None,
    event_date: str | None = None,
    source_published_at: str | None = None,
    scraped_at: str | None = None,
    confidence: float = 0.75,
    metadata: dict[str, Any] | None = None,
    excerpt_limit: int = EXCERPT_LIMIT,
) -> dict[str, Any]:
    normalized_fencer = normalize_fencer_record(fencer)
    fencer_name = normalized_fencer["fencer_name"]
    if not fencer_name:
        raise ValueError("fencer_name is required for injury/absence rows")

    excerpt = make_excerpt(statement, excerpt_limit)
    source_site = source_site or source_site_from_url(source_url)
    row_metadata = {
        "source_citations": citation_sources(statement),
        "medical_speculation_avoided": True,
    }
    if metadata:
        row_metadata.update(metadata)
    if event_date and row_metadata.get("date_basis") is None:
        row_metadata["date_basis"] = "source_or_event_text"

    return {
        "source_key": stable_source_key(source_url, fencer_name, status_type, excerpt),
        "identity_id": normalized_fencer["identity_id"],
        "fencer_row_id": normalized_fencer["fencer_row_id"],
        "fie_id": _first_list_value(normalized_fencer["fie_ids"]),
        "fencer_name": fencer_name,
        "country": normalized_fencer["country"],
        "event_name": clean_text(event_name) or None,
        "event_date": event_date,
        "status_type": status_type,
        "summary": excerpt,
        "source_excerpt": excerpt,
        "source_url": source_url,
        "source_name": source,
        "source_site": source_site,
        "source_published_at": source_published_at,
        "confidence": round(float(confidence), 2),
        "metadata": row_metadata,
        "scraped_at": scraped_at or datetime.now(UTC).isoformat(),
    }


def visible_lines(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        tag.decompose()
    return [
        line
        for line in (clean_text(part) for part in soup.get_text("\n").split("\n"))
        if line
    ]


def extract_fie_injury_statements(html: str) -> list[str]:
    statements: list[str] = []
    collecting = False
    for line in visible_lines(html):
        lowered = line.casefold()
        if lowered.startswith("injuries "):
            collecting = True
            remainder = clean_text(line[len("Injuries ") :])
            if remainder:
                statements.append(remainder)
            continue
        if lowered == "injuries":
            collecting = True
            continue
        if not collecting:
            continue
        if any(lowered.startswith(prefix) for prefix in FIE_INJURY_STOP_PREFIXES):
            break
        if classify_status_type(line, default="injury") == "injury":
            statements.append(line)
    return statements


def parse_fie_athlete_profile(
    html: str,
    *,
    source_url: str,
    fencer: dict[str, Any],
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for statement in extract_fie_injury_statements(html):
        rows.append(
            build_injury_absence_row(
                fencer=fencer,
                statement=statement,
                status_type="injury",
                source_url=source_url,
                source="fie_athlete_profiles",
                source_site="fie.org",
                event_name=extract_event_name(statement),
                event_date=extract_first_date(statement),
                scraped_at=scraped_at,
                confidence=0.95,
                metadata={
                    "source_section": "Injuries",
                    "date_basis": "source_citation_or_statement",
                },
            )
        )
    return rows


def _remove_unwanted(container) -> None:
    for selector in ("script", "style", "noscript", "nav", "header", "footer", ".sidebar", ".Article-links"):
        for tag in container.select(selector):
            tag.decompose()


def body_text(container) -> str:
    if container is None:
        return ""
    _remove_unwanted(container)
    paragraphs = [
        clean_text(p.get_text(" ", strip=True))
        for p in container.find_all("p")
        if clean_text(p.get_text(" ", strip=True))
    ]
    if paragraphs:
        return "\n".join(paragraphs)
    return clean_text(container.get_text(" ", strip=True))


def parse_official_article(url: str, html: str, *, source: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    published_tag = soup.find("meta", attrs={"property": "article:published_time"})
    published_at = parse_datetime(published_tag.get("content") if published_tag else None)
    if published_at is None:
        date_text = soup.find(string=re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"))
        published_at = parse_datetime(str(date_text) if date_text else None)

    container = (
        soup.select_one(".Article-content-body")
        or soup.select_one(".o-contentTxt")
        or soup.select_one(".o-newsDetails")
        or soup.select_one(".entry-content")
        or soup.find("article")
        or soup.find("main")
        or soup.body
    )
    return {
        "source": source,
        "source_site": source_site_from_url(url),
        "url": url,
        "title": clean_text(title_tag.get_text(" ", strip=True) if title_tag else ""),
        "published_at": published_at,
        "body": body_text(container),
    }


def _normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized).casefold()
    return clean_text(normalized)


def _name_aliases(name: str) -> list[str]:
    normalized = _normalize_for_match(name)
    parts = normalized.split()
    if len(parts) < 2:
        return []
    aliases = [normalized]
    if len(parts) == 2:
        aliases.append(f"{parts[1]} {parts[0]}")
    return aliases


def match_fencer_mentions(
    text: str,
    known_fencers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized_text = _normalize_for_match(text)
    by_mention: dict[str, list[dict[str, Any]]] = {}

    for raw_fencer in known_fencers:
        fencer = normalize_fencer_record(raw_fencer)
        name = fencer.get("fencer_name")
        if not name:
            continue
        aliases = _name_aliases(name)
        if not aliases:
            continue
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized_text) for alias in aliases):
            mention = clean_text(name)
            candidates = by_mention.setdefault(mention, [])
            if fencer.get("identity_id") not in {candidate.get("identity_id") for candidate in candidates}:
                candidates.append(fencer)

    matches: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    for mention, candidates in by_mention.items():
        if len(candidates) == 1:
            matches.append(candidates[0])
            continue
        ambiguous.append(
            {
                "mention": mention,
                "reason": "ambiguous_fencer_name",
                "candidate_identity_ids": [candidate.get("identity_id") for candidate in candidates],
            }
        )
    return matches, ambiguous


def split_statements(text: str) -> list[str]:
    statements: list[str] = []
    for paragraph in str(text or "").splitlines():
        paragraph = clean_text(paragraph)
        if not paragraph:
            continue
        pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z])", paragraph)
        statements.extend(clean_text(piece) for piece in pieces if clean_text(piece))
    return statements


def extract_article_mentions(
    article: dict[str, Any],
    *,
    known_fencers: list[dict[str, Any]],
    scraped_at: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    ambiguous_mentions: list[dict[str, Any]] = []

    for statement in split_statements(article.get("body", "")):
        status_type = classify_status_type(statement)
        if not status_type:
            continue
        matches, ambiguous = match_fencer_mentions(statement, known_fencers)
        ambiguous_mentions.extend(ambiguous)
        if ambiguous or not matches:
            continue
        if len(matches) > 1:
            ambiguous_mentions.append(
                {
                    "mention": statement,
                    "reason": "multiple_fencers_in_statement",
                    "candidate_identity_ids": [match.get("identity_id") for match in matches],
                }
            )
            continue
        source_published_at = article.get("published_at")
        rows.append(
            build_injury_absence_row(
                fencer=matches[0],
                statement=statement,
                status_type=status_type,
                source_url=article["url"],
                source=article.get("source") or "official_news",
                source_site=article.get("source_site") or source_site_from_url(article["url"]),
                event_name=extract_event_name(statement),
                event_date=date_only(source_published_at) or extract_first_date(statement),
                source_published_at=source_published_at,
                scraped_at=scraped_at,
                confidence=0.85 if status_type != "unknown" else 0.65,
                metadata={
                    "source_title": article.get("title"),
                    "source_kind": "official_article",
                },
            )
        )
    return rows, ambiguous_mentions


def parse_fie_listing(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    articles: dict[str, dict[str, str]] = {}
    for link in soup.find_all("a", href=True):
        url = urljoin("https://fie.org", link["href"])
        if not re.fullmatch(r"/articles/\d+", urlparse(url).path):
            continue
        title = clean_text(link.get_text(" ", strip=True))
        if title:
            articles.setdefault(url, {"title": title, "url": url})
    return list(articles.values())


def parse_british_fencing_listing(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    articles: dict[str, dict[str, str]] = {}
    for link in soup.find_all("a", href=True):
        href = urljoin(BRITISH_FENCING_NEWS_URL, link["href"])
        parsed = urlparse(href)
        if parsed.netloc.lower().removeprefix("www.") != "britishfencing.com":
            continue
        link_text = clean_text(link.get_text(" ", strip=True))
        if "read full story" not in link_text.casefold() and "continue reading" not in link_text.casefold():
            continue
        title = re.sub(r"^(?:Continue reading|Read Full story)\s+", "", link_text, flags=re.IGNORECASE)
        title = title.strip(" \"'")
        if not title:
            title = href.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
        articles.setdefault(href, {"title": title, "url": href})
    return list(articles.values())


def build_no_public_data_stub(source: str, source_url: str, reason: str) -> dict[str, Any]:
    return {
        "source": source,
        "source_url": source_url,
        "public_data_available": False,
        "reason": reason,
    }


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def load_fencer_identities(client, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    identities: list[dict[str, Any]] = []
    offset = 0
    while True:
        result = (
            client.table("fs_fencer_identities")
            .select("id,canonical_name,country,fie_ids,fs_fencer_row_ids")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = result.data or []
        for row in rows:
            identities.append(
                normalize_fencer_record(
                    {
                        "identity_id": row.get("id"),
                        "canonical_name": row.get("canonical_name"),
                        "country": row.get("country"),
                        "fie_ids": row.get("fie_ids") or [],
                        "fs_fencer_row_ids": row.get("fs_fencer_row_ids") or [],
                    }
                )
            )
        if len(rows) < page_size:
            break
        offset += page_size
    return identities


def fetch_html(session: requests.Session, url: str) -> str:
    domain = source_site_from_url(url)
    _limiter.wait(domain)
    try:
        response = session.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException:
        _limiter.record_failure(domain)
        raise
    if response.status_code == 429 or response.status_code >= 500:
        _limiter.record_failure(domain)
    else:
        _limiter.record_success(domain)
    response.raise_for_status()
    return response.text


def upsert_injury_absences(client, rows: list[dict[str, Any]], batch_size: int = UPSERT_BATCH_SIZE) -> int:
    if not rows:
        return 0
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_key = row.get("source_key")
        if source_key:
            by_key[source_key] = row
    deduped = list(by_key.values())
    written = 0
    for start in range(0, len(deduped), batch_size):
        batch = deduped[start : start + batch_size]
        client.table("fs_fencer_injury_absences").upsert(batch, on_conflict="source_key").execute()
        written += len(batch)
    return written


def _article_source_configs() -> list[dict[str, Any]]:
    return [
        {
            "source": "fie_news",
            "listing_url": FIE_ARTICLES_URL,
            "parse_listing": parse_fie_listing,
        },
        {
            "source": "british_fencing_news",
            "listing_url": BRITISH_FENCING_NEWS_URL,
            "parse_listing": parse_british_fencing_listing,
        },
    ]


def scrape_article_source(
    *,
    session: requests.Session,
    source_config: dict[str, Any],
    known_fencers: list[dict[str, Any]],
    seen_urls: set[str],
) -> tuple[list[dict[str, Any]], int, int, list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    successful_urls: list[str] = []
    ambiguous_mentions: list[dict[str, Any]] = []
    stubs: list[dict[str, Any]] = []
    failed = 0
    skipped = 0
    source = source_config["source"]
    listing_url = source_config["listing_url"]
    parse_listing: Callable[[str], list[dict[str, str]]] = source_config["parse_listing"]

    try:
        refs = parse_listing(fetch_html(session, listing_url))
    except Exception as exc:
        failed += 1
        stubs.append(build_no_public_data_stub(source, listing_url, f"listing_failed: {exc}"))
        return rows, failed, skipped, successful_urls, ambiguous_mentions, stubs

    for ref in refs[:MAX_ARTICLES_PER_SOURCE]:
        url = ref.get("url")
        if not url:
            continue
        if url in seen_urls and not REFETCH_SEEN:
            skipped += 1
            continue
        try:
            article = parse_official_article(url, fetch_html(session, url), source=source)
            source_rows, source_ambiguous = extract_article_mentions(article, known_fencers=known_fencers)
            rows.extend(source_rows)
            ambiguous_mentions.extend(source_ambiguous)
            successful_urls.append(url)
        except Exception as exc:
            failed += 1
            stubs.append(build_no_public_data_stub(source, url, f"article_failed: {exc}"))
    return rows, failed, skipped, successful_urls, ambiguous_mentions, stubs


def scrape_fie_profiles(
    *,
    session: requests.Session,
    known_fencers: list[dict[str, Any]],
    seen_urls: set[str],
) -> tuple[list[dict[str, Any]], int, int, list[str], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    successful_urls: list[str] = []
    stubs: list[dict[str, Any]] = []
    failed = 0
    skipped = 0

    probed = 0
    for fencer in known_fencers:
        fie_id = _first_list_value(fencer.get("fie_ids"))
        if not fie_id:
            continue
        url = FIE_ATHLETE_URL.format(fie_id=fie_id)
        if url in seen_urls and not REFETCH_SEEN:
            skipped += 1
            continue
        if probed >= MAX_PROFILE_PROBES:
            break
        probed += 1
        try:
            profile_rows = parse_fie_athlete_profile(
                fetch_html(session, url),
                source_url=url,
                fencer=fencer,
            )
            rows.extend(profile_rows)
            successful_urls.append(url)
        except Exception as exc:
            failed += 1
            stubs.append(build_no_public_data_stub("fie_athlete_profiles", url, f"profile_failed: {exc}"))
    return rows, failed, skipped, successful_urls, stubs


def scrape_injuries(client=None, session: requests.Session | None = None) -> dict[str, Any]:
    client = client or get_supabase_client()
    session = session or requests.Session()
    known_fencers = load_fencer_identities(client)
    seen_state = get_state(STATE_SOURCE, "seen_urls") or []
    seen_urls = set(seen_state if isinstance(seen_state, list) else [])

    all_rows: list[dict[str, Any]] = []
    successful_urls: list[str] = []
    ambiguous_mentions: list[dict[str, Any]] = []
    stubs: list[dict[str, Any]] = []
    total_failed = 0
    total_skipped = 0

    profile_rows, failed, skipped, urls, profile_stubs = scrape_fie_profiles(
        session=session,
        known_fencers=known_fencers,
        seen_urls=seen_urls,
    )
    all_rows.extend(profile_rows)
    successful_urls.extend(urls)
    stubs.extend(profile_stubs)
    total_failed += failed
    total_skipped += skipped

    for source_config in _article_source_configs():
        rows, failed, skipped, urls, ambiguous, source_stubs = scrape_article_source(
            session=session,
            source_config=source_config,
            known_fencers=known_fencers,
            seen_urls=seen_urls,
        )
        all_rows.extend(rows)
        successful_urls.extend(urls)
        ambiguous_mentions.extend(ambiguous)
        stubs.extend(source_stubs)
        total_failed += failed
        total_skipped += skipped

    for ambiguous_item in ambiguous_mentions:
        print(f"  Ambiguous injury/absence mention skipped: {ambiguous_item}")

    written = upsert_injury_absences(client, all_rows)
    combined_seen = [url for url in seen_state if isinstance(seen_state, list) and url not in successful_urls]
    combined_seen.extend(successful_urls)
    set_state(STATE_SOURCE, "seen_urls", combined_seen[-5000:])
    set_state(STATE_SOURCE, "last_run", datetime.now(UTC).isoformat())
    set_state(STATE_SOURCE, "last_no_public_data_stubs", stubs[-100:])

    return {
        "fetched": len(all_rows),
        "written": written,
        "failed": total_failed,
        "skipped": total_skipped,
        "ambiguous": len(ambiguous_mentions),
        "stubs": stubs,
    }


def main() -> None:
    run_log = ScraperRunLogger("scrape_injuries").start()
    try:
        start = time.time()
        result = scrape_injuries()
        run_log.complete(
            written=result["written"],
            failed=result["failed"],
            skipped=result["skipped"],
            metadata={
                "fetched": result["fetched"],
                "ambiguous": result["ambiguous"],
                "stubs": result["stubs"],
                "elapsed_seconds": round(time.time() - start, 2),
            },
        )
        print(
            "Done - "
            f"fetched={result['fetched']}, written={result['written']}, "
            f"failed={result['failed']}, skipped={result['skipped']}, "
            f"ambiguous={result['ambiguous']}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

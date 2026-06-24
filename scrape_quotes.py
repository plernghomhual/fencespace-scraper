"""
Public fencing interview and media quote scraper.

The scraper stores short quote excerpts and source links only. It deliberately
does not persist full article bodies or transcript text.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from scripts.rate_limiter import RateLimiter as _RateLimiter
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "scrape_quotes"
PAGE_SIZE = 1000
MAX_QUOTE_EXCERPT_CHARS = 280
MAX_ARTICLES_PER_SOURCE = int(os.environ.get("QUOTES_MAX_ARTICLES_PER_SOURCE", "50"))
REFETCH_SEEN = os.environ.get("QUOTES_REFETCH_SEEN", "").lower() in {"1", "true", "yes"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

FIE_ARTICLES_URL = "https://fie.org/articles"
USA_FENCING_NEWS_URL = "https://www.usafencing.org/news"
BRITISH_FENCING_NEWS_URL = "https://www.britishfencing.com/news/"

_quote_limiter = _RateLimiter(default_rps=1.0, jitter=0.2, backoff=5.0)

SAID_VERBS = (
    "said",
    "says",
    "told",
    "added",
    "noted",
    "stated",
    "commented",
    "dijo",
    "dice",
    "afirmo",
    "afirmó",
    "explico",
    "explicó",
    "declaro",
    "declaró",
)
VERB_PATTERN = r"(?:{})".format("|".join(re.escape(verb) for verb in SAID_VERBS))

QUOTE_THEN_VERB_SPEAKER_RE = re.compile(
    rf"[\"“](?P<quote>[^\"“”]{{20,900}})[\"”]\s*,?\s*{VERB_PATTERN}\s+(?P<speaker>[^.?!\"“”]{{2,160}})",
    re.IGNORECASE,
)
QUOTE_THEN_SPEAKER_VERB_RE = re.compile(
    rf"[\"“](?P<quote>[^\"“”]{{20,900}})[\"”]\s*,?\s*(?P<speaker>[^.?!\"“”:;]{{2,100}}?)\s+{VERB_PATTERN}\b",
    re.IGNORECASE,
)
SPEAKER_VERB_THEN_QUOTE_RE = re.compile(
    rf"(?P<speaker>[A-ZÀ-ÖØ-Þ][^.?!\"“”]{{2,140}}?)\s*,?\s+{VERB_PATTERN}\s*[:,]?\s*[\"“](?P<quote>[^\"“”]{{20,900}})[\"”]",
    re.IGNORECASE,
)


@dataclass
class SourceArticle:
    source: str
    source_site: str
    url: str
    title: str
    published_at: str | None
    language: str
    body: str
    paragraphs: list[str]


@dataclass
class QuoteCandidate:
    quote_excerpt: str
    speaker: str
    source_paragraph: str


def clean_text(value) -> str:
    text = str(value or "").replace("\u200b", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


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

    match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    if match:
        return parse_datetime(match.group(1))
    match = re.search(r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", text)
    if match:
        return parse_datetime(match.group(1))
    return None


def _remove_unwanted(container) -> None:
    for selector in (
        "script",
        "style",
        "nav",
        "header",
        "footer",
        ".Article-links",
        ".o-otherContentArea.gray-bg",
        ".o-newsSection",
        ".sidebar",
        ".advertisement",
    ):
        for tag in container.select(selector):
            tag.decompose()


def _body_container(soup: BeautifulSoup):
    return (
        soup.select_one(".Article-content-body")
        or soup.select_one(".o-contentTxt")
        or soup.select_one(".o-newsDetails")
        or soup.select_one(".entry-content")
        or soup.find("article")
        or soup.find("main")
        or soup.body
    )


def _article_paragraphs(container) -> list[str]:
    if container is None:
        return []
    _remove_unwanted(container)
    paragraphs = [
        clean_text(p.get_text(" ", strip=True))
        for p in container.find_all(["p", "li"])
        if clean_text(p.get_text(" ", strip=True))
    ]
    if paragraphs:
        return paragraphs
    text = clean_text(container.get_text(" ", strip=True))
    return [text] if text else []


def _language_from_soup(soup: BeautifulSoup) -> str:
    html = soup.find("html")
    language = clean_text(html.get("lang") if html else "")
    if language:
        return language.split("-", 1)[0].lower()
    meta = soup.find("meta", attrs={"property": "og:locale"}) or soup.find("meta", attrs={"name": "language"})
    language = clean_text(meta.get("content") if meta else "")
    if language:
        return language.replace("_", "-").split("-", 1)[0].lower()
    return "unknown"


def parse_article(*, source: str, source_site: str, url: str, html: str) -> SourceArticle:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1") or soup.find("meta", attrs={"property": "og:title"}) or soup.title
    if title_tag and title_tag.name == "meta":
        title = clean_text(title_tag.get("content"))
    else:
        title = clean_text(title_tag.get_text(" ", strip=True) if title_tag else "")

    published_at = None
    published_meta = soup.find("meta", attrs={"property": "article:published_time"})
    if published_meta:
        published_at = parse_datetime(published_meta.get("content"))
    if published_at is None:
        time_tag = soup.find("time")
        published_at = parse_datetime(time_tag.get("datetime") if time_tag else None)
    if published_at is None:
        date_tag = soup.select_one(".Article-content-label")
        published_at = parse_datetime(date_tag.get_text(" ", strip=True) if date_tag else None)

    container = _body_container(soup)
    paragraphs = _article_paragraphs(container)
    body = clean_text(" ".join(paragraphs))

    return SourceArticle(
        source=source,
        source_site=source_site,
        url=url,
        title=title,
        published_at=published_at,
        language=_language_from_soup(soup),
        body=body,
        paragraphs=paragraphs,
    )


def _truncate_excerpt(text: str, limit: int = MAX_QUOTE_EXCERPT_CHARS) -> str:
    excerpt = clean_text(text)
    if len(excerpt) <= limit:
        return excerpt
    clipped = excerpt[: limit - 3].rstrip()
    boundary = max(clipped.rfind(" "), clipped.rfind(","), clipped.rfind(";"))
    if boundary >= limit * 0.65:
        clipped = clipped[:boundary].rstrip(" ,;")
    return f"{clipped}..."


def _clean_speaker(raw_speaker: str) -> str:
    speaker = clean_text(raw_speaker)
    speaker = re.sub(r"\([^)]*\)", "", speaker)
    speaker = speaker.split(",", 1)[0]
    speaker = speaker.strip(" .,:;")

    changed = True
    while changed:
        before = speaker
        speaker = re.sub(r"^\d+\s*[- ]year[- ]old\s+", "", speaker, flags=re.IGNORECASE)
        speaker = re.sub(
            r"^(?:fie\s+)?(?:interim\s+)?(?:president|vice president|secretary-general|chief executive officer|ceo|director|founder|coach|athlete|sabreur|sabreur|epeeist|épéeist|foilist|fencer)\s+",
            "",
            speaker,
            flags=re.IGNORECASE,
        )
        speaker = re.sub(r"^(?:usa fencing|italian federation|greek)\s+", "", speaker, flags=re.IGNORECASE)
        changed = before != speaker

    return clean_text(speaker.strip(" .,:;"))


def _quote_candidates_from_paragraph(paragraph: str) -> list[QuoteCandidate]:
    candidates: list[QuoteCandidate] = []
    seen: set[tuple[str, str]] = set()

    for regex in (QUOTE_THEN_VERB_SPEAKER_RE, QUOTE_THEN_SPEAKER_VERB_RE, SPEAKER_VERB_THEN_QUOTE_RE):
        for match in regex.finditer(paragraph):
            quote = _truncate_excerpt(match.group("quote"))
            speaker = _clean_speaker(match.group("speaker"))
            if not quote or not speaker:
                continue
            key = (quote, speaker.casefold())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(QuoteCandidate(quote_excerpt=quote, speaker=speaker, source_paragraph=paragraph))

    return candidates


def extract_quote_candidates(article: SourceArticle) -> list[QuoteCandidate]:
    candidates: list[QuoteCandidate] = []
    seen: set[tuple[str, str]] = set()
    for paragraph in article.paragraphs:
        for candidate in _quote_candidates_from_paragraph(paragraph):
            key = (candidate.quote_excerpt, candidate.speaker.casefold())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def _normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized).casefold()
    return clean_text(normalized)


def _name_aliases(name: str) -> list[str]:
    normalized = _normalize_for_match(name)
    if not normalized:
        return []
    aliases = [normalized]
    parts = normalized.split()
    if len(parts) == 2:
        aliases.append(f"{parts[1]} {parts[0]}")
    return aliases


def _fencer_id(row: dict) -> str | None:
    value = row.get("id")
    return str(value) if value else None


def match_speaker_to_fencer(speaker: str, article: SourceArticle, known_fencers: list[dict]) -> tuple[str | None, dict]:
    normalized_speaker = _normalize_for_match(speaker)
    if not normalized_speaker:
        return None, {"status": "unmatched", "speaker": speaker}

    exact_matches: list[dict] = []
    for fencer in known_fencers:
        name = str(fencer.get("name") or "")
        if normalized_speaker in _name_aliases(name):
            exact_matches.append(fencer)

    if len(exact_matches) == 1:
        fencer = exact_matches[0]
        return _fencer_id(fencer), {
            "status": "exact_name",
            "matched_name": fencer.get("name"),
            "matched_fie_id": fencer.get("fie_id"),
        }
    if len(exact_matches) > 1:
        return None, {
            "status": "ambiguous",
            "speaker": speaker,
            "candidate_ids": [_fencer_id(fencer) for fencer in exact_matches if _fencer_id(fencer)],
        }

    speaker_parts = normalized_speaker.split()
    if len(speaker_parts) == 1:
        context = _normalize_for_match(f"{article.title} {article.body}")
        last_name_matches = []
        context_name_matches = []
        for fencer in known_fencers:
            name = str(fencer.get("name") or "")
            normalized_name = _normalize_for_match(name)
            parts = normalized_name.split()
            if parts and parts[-1] == normalized_speaker:
                last_name_matches.append(fencer)
                if re.search(rf"(?<![a-z0-9]){re.escape(normalized_name)}(?![a-z0-9])", context):
                    context_name_matches.append(fencer)
        if len(context_name_matches) == 1:
            fencer = context_name_matches[0]
            return _fencer_id(fencer), {
                "status": "context_full_name",
                "matched_name": fencer.get("name"),
                "matched_fie_id": fencer.get("fie_id"),
            }
        if len(last_name_matches) > 1 or len(context_name_matches) > 1:
            candidates = context_name_matches or last_name_matches
            return None, {
                "status": "ambiguous",
                "speaker": speaker,
                "candidate_ids": [_fencer_id(fencer) for fencer in candidates if _fencer_id(fencer)],
            }

    return None, {"status": "unmatched", "speaker": speaker}


def _canonical_source_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _quote_hash(speaker: str, quote_excerpt: str, language: str) -> str:
    payload = "\n".join(
        [
            _normalize_for_match(speaker),
            _normalize_for_match(quote_excerpt),
            clean_text(language).casefold(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _infer_tournament(article: SourceArticle) -> str | None:
    text = clean_text(f"{article.title}. {article.body}")
    patterns = (
        r"\b(?:Junior and Cadet )?World Championships?\b[^.]{0,80}",
        r"\b(?:Senior |Junior |Cadet )?World Cup\b[^.]{0,80}",
        r"\bGrand Prix\b[^.]{0,80}",
        r"\bOlympic Games\b[^.]{0,80}",
        r"\bEuropean Championships?\b[^.]{0,80}",
        r"\bPan American Championships?\b[^.]{0,80}",
        r"\bAsian Championships?\b[^.]{0,80}",
        r"\bAfrican Championships?\b[^.]{0,80}",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_text(match.group(0).strip(" ."))
    return None


def build_quote_rows(article: SourceArticle, candidates: list[QuoteCandidate], known_fencers: list[dict]) -> list[dict]:
    rows: list[dict] = []
    tournament = _infer_tournament(article)
    canonical_url = _canonical_source_url(article.url)
    for candidate in candidates:
        fencer_id, match_metadata = match_speaker_to_fencer(candidate.speaker, article, known_fencers)
        excerpt = _truncate_excerpt(candidate.quote_excerpt)
        rows.append(
            {
                "quote_hash": _quote_hash(candidate.speaker, excerpt, article.language),
                "quote_excerpt": excerpt,
                "speaker": candidate.speaker,
                "fencer_id": fencer_id,
                "event": tournament,
                "tournament": tournament,
                "source": article.source,
                "source_site": article.source_site,
                "source_title": article.title or article.url,
                "source_url": article.url,
                "published_at": article.published_at,
                "language": article.language,
                "metadata": {
                    "canonical_source_url": canonical_url,
                    "speaker_match": match_metadata,
                    "source_quote_length": len(clean_text(candidate.quote_excerpt)),
                    "excerpt_limit": MAX_QUOTE_EXCERPT_CHARS,
                    "was_truncated": len(clean_text(candidate.quote_excerpt)) > MAX_QUOTE_EXCERPT_CHARS,
                },
            }
        )
    return rows


def dedupe_quote_rows(rows: list[dict]) -> list[dict]:
    by_hash: dict[str, dict] = {}
    for row in rows:
        quote_hash = row.get("quote_hash")
        if not quote_hash:
            continue
        existing = by_hash.get(quote_hash)
        if existing is None:
            row["metadata"] = dict(row.get("metadata") or {})
            by_hash[quote_hash] = row
            continue
        source_url = row.get("source_url")
        if source_url and source_url != existing.get("source_url"):
            duplicates = existing.setdefault("metadata", {}).setdefault("duplicate_source_urls", [])
            if source_url not in duplicates:
                duplicates.append(source_url)
    return list(by_hash.values())


def parse_fie_listing(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    articles: dict[str, dict] = {}
    for link in soup.find_all("a", href=True):
        absolute_url = urljoin("https://fie.org", link["href"])
        if not re.fullmatch(r"/articles/\d+", urlparse(absolute_url).path):
            continue
        title = clean_text(link.get_text(" ", strip=True))
        if title:
            articles.setdefault(absolute_url, {"title": title, "url": absolute_url})
    return list(articles.values())


def parse_usafencing_listing(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    articles: dict[str, dict] = {}
    for link in soup.find_all("a", href=True):
        absolute_url = urljoin(USA_FENCING_NEWS_URL, link["href"])
        if urlparse(absolute_url).netloc.lower().replace("www.", "") != "usafencing.org":
            continue
        if not re.search(r"/news/\d{4}/[a-z]+/\d{2}/", urlparse(absolute_url).path):
            continue
        title = clean_text(link.get_text(" ", strip=True))
        if not title:
            parent = link
            for _ in range(5):
                parent = parent.parent
                if parent is None:
                    break
                heading = parent.find(["h1", "h2", "h3", "h4"])
                if heading:
                    title = clean_text(heading.get_text(" ", strip=True))
                    break
        if title:
            articles.setdefault(absolute_url, {"title": title, "url": absolute_url})
    return list(articles.values())


def parse_british_fencing_listing(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    articles: dict[str, dict] = {}
    for link in soup.find_all("a", href=True):
        absolute_url = urljoin(BRITISH_FENCING_NEWS_URL, link["href"])
        if urlparse(absolute_url).netloc.lower().replace("www.", "") != "britishfencing.com":
            continue
        path = urlparse(absolute_url).path
        if path.rstrip("/") in {"", "/news", "/news/selection-announcements"}:
            continue
        title = clean_text(link.get_text(" ", strip=True))
        if title.lower() == "read full story":
            title = ""
            parent = link
            for _ in range(5):
                parent = parent.parent
                if parent is None:
                    break
                heading = parent.find(["h1", "h2", "h3", "h4"])
                if heading:
                    title = clean_text(heading.get_text(" ", strip=True))
                    break
        if title:
            articles.setdefault(absolute_url, {"title": title, "url": absolute_url})
    return list(articles.values())


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    response.raise_for_status()
    return response.text


def scrape_source(
    *,
    session: requests.Session,
    source_config: dict,
    known_fencers: list[dict],
    seen_hashes: set[str],
) -> tuple[list[dict], int, int, list[str], list[dict]]:
    source = str(source_config["source"])
    source_site = str(source_config["source_site"])
    listing_url = str(source_config["listing_url"])

    if source_config.get("blocked"):
        return (
            [],
            0,
            1,
            [],
            [
                {
                    "source": source,
                    "source_site": source_site,
                    "url": listing_url,
                    "reason": str(source_config.get("block_reason") or "Blocked or unavailable source."),
                }
            ],
        )

    parse_listing: Callable[[str], list[dict]] = source_config["parse_listing"]

    rows: list[dict] = []
    successful_urls: list[str] = []
    stubs: list[dict] = []
    failed = 0
    skipped = 0

    try:
        listing_html = fetch_html(session, listing_url)
        article_refs = parse_listing(listing_html)
    except Exception as exc:
        print(f"  Listing fetch/parse failed for {source}: {exc}")
        return rows, 1, skipped, successful_urls, stubs

    for ref in article_refs[:MAX_ARTICLES_PER_SOURCE]:
        url = ref.get("url")
        if not url:
            continue
        try:
            html = fetch_html(session, str(url))
            article = parse_article(source=source, source_site=source_site, url=str(url), html=html)
            if not article.title:
                article.title = clean_text(ref.get("title"))
            candidates = extract_quote_candidates(article)
            quote_rows = build_quote_rows(article, candidates, known_fencers)
            new_rows = [row for row in quote_rows if REFETCH_SEEN or row["quote_hash"] not in seen_hashes]
            skipped += len(quote_rows) - len(new_rows)
            rows.extend(new_rows)
            successful_urls.append(str(url))
            for row in new_rows:
                if row["metadata"]["speaker_match"]["status"] == "ambiguous":
                    print(f"  Ambiguous quote speaker {row['speaker']!r} in {url}")
        except Exception as exc:
            failed += 1
            print(f"  Article fetch/parse failed for {url}: {exc}")
        _quote_limiter.wait(source_site)

    return rows, failed, skipped, successful_urls, stubs


def upsert_quotes(client, rows: list[dict], batch_size: int = 100) -> int:
    if not rows:
        return 0
    by_hash: dict[str, dict] = {}
    for row in rows:
        quote_hash = row.get("quote_hash")
        if quote_hash:
            by_hash[quote_hash] = row
    deduped = list(by_hash.values())
    written = 0
    for i in range(0, len(deduped), batch_size):
        batch = deduped[i : i + batch_size]
        client.table("fs_quotes").upsert(batch, on_conflict="quote_hash").execute()
        written += len(batch)
    return written


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def load_known_fencers(client) -> list[dict]:
    known: list[dict] = []
    offset = 0
    while True:
        try:
            result = (
                client.table("fs_fencers")
                .select("id,name,fie_id")
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
            )
        except Exception as exc:
            print(f"  Could not load known fencers at offset={offset}: {exc}")
            break
        rows = result.data or []
        known.extend(
            [
                {"id": row.get("id"), "name": row.get("name"), "fie_id": row.get("fie_id")}
                for row in rows
                if row.get("id") and row.get("name")
            ]
        )
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return known


def _source_configs() -> list[dict[str, object]]:
    return [
        {
            "source": "fie_news",
            "source_site": "fie.org",
            "listing_url": FIE_ARTICLES_URL,
            "parse_listing": parse_fie_listing,
        },
        {
            "source": "usa_fencing_news",
            "source_site": "usafencing.org",
            "listing_url": USA_FENCING_NEWS_URL,
            "parse_listing": parse_usafencing_listing,
        },
        {
            "source": "british_fencing_news",
            "source_site": "britishfencing.com",
            "listing_url": BRITISH_FENCING_NEWS_URL,
            "parse_listing": parse_british_fencing_listing,
        },
        {
            "source": "fie_press_conferences",
            "source_site": "fie.org",
            "listing_url": "https://fie.org/media",
            "blocked": True,
            "block_reason": "No public static transcript endpoint found during the 2026-06-02 probe.",
        },
    ]


def scrape_quotes() -> dict:
    client = get_supabase_client()
    session = requests.Session()
    known_fencers = load_known_fencers(client)
    seen_state = get_state(SOURCE, "seen_quote_hashes") or []
    seen_hashes = set(seen_state if isinstance(seen_state, list) else [])

    all_rows: list[dict] = []
    successful_urls: list[str] = []
    blocked_stubs: list[dict] = []
    failed = 0
    skipped = 0

    for source_config in _source_configs():
        rows, source_failed, source_skipped, source_urls, source_stubs = scrape_source(
            session=session,
            source_config=source_config,
            known_fencers=known_fencers,
            seen_hashes=seen_hashes,
        )
        all_rows.extend(rows)
        successful_urls.extend(source_urls)
        blocked_stubs.extend(source_stubs)
        failed += source_failed
        skipped += source_skipped
        _quote_limiter.wait(str(source_config["source_site"]))

    deduped = dedupe_quote_rows(all_rows)
    written = upsert_quotes(client, deduped)
    new_hashes = [row["quote_hash"] for row in deduped if row.get("quote_hash")]
    combined_hashes = [item for item in seen_state if isinstance(seen_state, list) and item not in new_hashes]
    combined_hashes.extend(new_hashes)

    summary = {
        "fetched": len(all_rows),
        "written": written,
        "failed": failed,
        "skipped": skipped,
        "source_urls": successful_urls[-100:],
        "blocked_stubs": blocked_stubs,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    set_state(SOURCE, "seen_quote_hashes", combined_hashes[-5000:])
    set_state(SOURCE, "last_run", summary)
    return summary


def main() -> None:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        result = scrape_quotes()
        run_log.complete(
            written=result["written"],
            failed=result["failed"],
            skipped=result["skipped"],
            metadata={
                "fetched": result["fetched"],
                "blocked_stubs": result["blocked_stubs"],
            },
        )
        print(
            "Done - "
            f"fetched={result['fetched']}, written={result['written']}, "
            f"failed={result['failed']}, skipped={result['skipped']}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

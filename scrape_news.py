"""
Fencing news and injury/absence tracker.

Sources:
  - FIE articles: https://fie.org/articles
  - British Fencing news: https://www.britishfencing.com/news/
"""

from __future__ import annotations

import hashlib
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from supabase import create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

STATE_SOURCE = "scrape_news"
REQUEST_DELAY = float(os.environ.get("NEWS_REQUEST_DELAY", "1.0"))
MAX_ARTICLES_PER_SOURCE = int(os.environ.get("NEWS_MAX_ARTICLES_PER_SOURCE", "50"))
REFETCH_SEEN = os.environ.get("NEWS_REFETCH_SEEN", "").lower() in {"1", "true", "yes"}
PAGE_SIZE = 1000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

FIE_ARTICLES_URL = "https://fie.org/articles"
BRITISH_FENCING_NEWS_URL = "https://www.britishfencing.com/news/"

INJURY_KEYWORDS = ("injury", "sidelined", "surgery", "recovery")
TRANSFER_KEYWORDS = ("transfer", "switches", "new country", "naturalized")
RULE_CHANGE_KEYWORDS = ("rule change", "new format", "fie congress")
TOURNAMENT_KEYWORDS = (
    "world cup",
    "grand prix",
    "world championship",
    "world championships",
    "junior and cadet world championships",
    "olympic games",
    "olympics",
    "european championship",
    "european championships",
    "asian championship",
    "asian championships",
    "pan american championship",
    "pan american championships",
    "african championship",
    "african championships",
    "british championship",
    "british championships",
)
RESULT_KEYWORDS = (
    "result",
    "gold",
    "silver",
    "bronze",
    "medal",
    "podium",
    "won",
    "wins",
    "claim",
    "claims",
    "claimed",
    "triumph",
    "triumphs",
    "victory",
    "defeat",
    "defeats",
    "champion",
    "comeback",
    "final",
)


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
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except ValueError:
        pass

    for fmt in ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue

    match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    if match:
        return parse_datetime(match.group(1))
    match = re.search(r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", text)
    if match:
        return parse_datetime(match.group(1))
    return None


def _is_same_host(url: str, host: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.lower().replace("www.", "") == host.replace("www.", "")


def parse_fie_listing(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    articles: dict[str, dict] = {}
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        absolute_url = urljoin("https://fie.org", href)
        path = urlparse(absolute_url).path
        if not re.fullmatch(r"/articles/\d+", path):
            continue
        title = clean_text(link.get_text(" ", strip=True))
        if not title:
            continue
        articles.setdefault(absolute_url, {"title": title, "url": absolute_url})
    return list(articles.values())


def _find_heading_near(link) -> str | None:
    parent = link
    for _ in range(6):
        parent = parent.parent
        if parent is None:
            break
        heading = parent.find(["h1", "h2", "h3", "h4"])
        if heading:
            text = clean_text(heading.get_text(" ", strip=True))
            if text:
                return text
    return None


def parse_british_fencing_listing(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    articles: dict[str, dict] = {}
    for link in soup.find_all("a", href=True):
        link_text = clean_text(link.get_text(" ", strip=True))
        href = urljoin(BRITISH_FENCING_NEWS_URL, link["href"])
        if not _is_same_host(href, "britishfencing.com"):
            continue
        path = urlparse(href).path
        if path.rstrip("/") in {"", "/news", "/news/selection-announcements"}:
            continue
        if "read full story" not in link_text.lower() and "o-news" not in " ".join(link.get("class", [])):
            continue
        title = _find_heading_near(link)
        if not title and "read full story" not in link_text.lower():
            title = link_text
        if not title:
            continue
        articles.setdefault(href, {"title": title, "url": href})
    return list(articles.values())


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
    ):
        for tag in container.select(selector):
            tag.decompose()


def _body_text(container) -> str:
    if container is None:
        return ""
    _remove_unwanted(container)
    paragraphs = [
        clean_text(p.get_text(" ", strip=True))
        for p in container.find_all("p")
        if clean_text(p.get_text(" ", strip=True))
    ]
    if paragraphs:
        return clean_text(" ".join(paragraphs))
    return clean_text(container.get_text(" ", strip=True))


def parse_fie_article(url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(" ", strip=True) if title_tag else "")

    date_tag = soup.select_one(".Article-content-label")
    published_at = parse_datetime(date_tag.get_text(" ", strip=True) if date_tag else None)

    body_container = soup.select_one(".Article-content-body")
    if body_container is None:
        body_container = soup.find("article") or soup.find("main") or soup.body

    return {
        "url": url,
        "title": title,
        "published_at": published_at,
        "body": _body_text(body_container),
    }


def parse_british_fencing_article(url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(" ", strip=True) if title_tag else "")

    published_tag = soup.find("meta", attrs={"property": "article:published_time"})
    published_at = parse_datetime(published_tag.get("content") if published_tag else None)
    if published_at is None:
        date_text = soup.find(string=re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"))
        published_at = parse_datetime(str(date_text) if date_text else None)

    body_container = (
        soup.select_one(".Article-content-body")
        or soup.select_one(".o-contentTxt")
        or soup.select_one(".o-newsDetails")
        or soup.select_one(".entry-content")
        or soup.find("article")
        or soup.find("main")
        or soup.body
    )

    return {
        "url": url,
        "title": title,
        "published_at": published_at,
        "body": _body_text(body_container),
    }


def classify_article(title: str, body: str) -> str:
    text = f"{title} {body}".casefold()

    if any(keyword in text for keyword in INJURY_KEYWORDS):
        return "injury"
    if any(keyword in text for keyword in TRANSFER_KEYWORDS):
        return "transfer"
    if any(keyword in text for keyword in RULE_CHANGE_KEYWORDS):
        return "rule_change"
    if any(keyword in text for keyword in TOURNAMENT_KEYWORDS) and any(
        keyword in text for keyword in RESULT_KEYWORDS
    ):
        return "competition_report"
    return "general"


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


def extract_related_fencer_ids(text: str, known_fencers: list[dict]) -> list[str]:
    normalized_text = _normalize_for_match(text)
    related: list[str] = []
    seen: set[str] = set()
    for fencer in known_fencers:
        fencer_id = fencer.get("id")
        name = fencer.get("name")
        if not fencer_id or not name:
            continue
        for alias in _name_aliases(str(name)):
            if len(alias) < 3:
                continue
            pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
            if re.search(pattern, normalized_text):
                if fencer_id not in seen:
                    related.append(fencer_id)
                    seen.add(fencer_id)
                break
    return related


def summarize_body(body: str, limit: int = 500) -> str | None:
    text = clean_text(body)
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def content_hash(title: str, published_at: str | None, body: str) -> str:
    payload = "\n".join([clean_text(title), clean_text(published_at), clean_text(body)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_article_row(
    *,
    source: str,
    source_site: str,
    url: str,
    title: str,
    published_at: str | None,
    body: str,
    known_fencers: list[dict],
) -> dict:
    combined_text = f"{title} {body}"
    return {
        "title": clean_text(title),
        "url": url,
        "source": source,
        "source_site": source_site,
        "published_at": published_at,
        "category": classify_article(title, body),
        "summary": summarize_body(body),
        "related_fencer_ids": extract_related_fencer_ids(combined_text, known_fencers),
        "content_hash": content_hash(title, published_at, body),
        "metadata": {
            "body": clean_text(body),
            "body_length": len(clean_text(body)),
        },
    }


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
                .select("id,name")
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
            )
        except Exception as exc:
            print(f"  Could not load known fencers at offset={offset}: {exc}")
            break
        rows = result.data or []
        known.extend([{"id": row.get("id"), "name": row.get("name")} for row in rows if row.get("id") and row.get("name")])
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return known


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    response.raise_for_status()
    return response.text


def upsert_articles(client, rows: list[dict], batch_size: int = 100) -> int:
    if not rows:
        return 0
    by_url: dict[str, dict] = {}
    for row in rows:
        url = row.get("url")
        if url:
            by_url[url] = row
    deduped = list(by_url.values())
    written = 0
    for i in range(0, len(deduped), batch_size):
        batch = deduped[i : i + batch_size]
        client.table("fs_articles").upsert(batch, on_conflict="url").execute()
        written += len(batch)
    return written


def _source_configs() -> list[dict[str, object]]:
    return [
        {
            "source": "fie_news",
            "source_site": "fie.org",
            "listing_url": FIE_ARTICLES_URL,
            "parse_listing": parse_fie_listing,
            "parse_article": parse_fie_article,
        },
        {
            "source": "british_fencing_news",
            "source_site": "britishfencing.com",
            "listing_url": BRITISH_FENCING_NEWS_URL,
            "parse_listing": parse_british_fencing_listing,
            "parse_article": parse_british_fencing_article,
        },
    ]


def scrape_source(
    *,
    session: requests.Session,
    source_config: dict,
    known_fencers: list[dict],
    seen_urls: set[str],
) -> tuple[list[dict], int, int, list[str]]:
    parse_listing: Callable[[str], list[dict]] = source_config["parse_listing"]
    parse_article: Callable[[str, str], dict] = source_config["parse_article"]
    listing_url = str(source_config["listing_url"])
    source = str(source_config["source"])
    source_site = str(source_config["source_site"])

    rows: list[dict] = []
    successful_urls: list[str] = []
    failed = 0
    skipped = 0

    try:
        listing_html = fetch_html(session, listing_url)
        article_refs = parse_listing(listing_html)
    except Exception as exc:
        print(f"  Listing fetch/parse failed for {source}: {exc}")
        return rows, 1, skipped, successful_urls

    for ref in article_refs[:MAX_ARTICLES_PER_SOURCE]:
        url = ref.get("url")
        if not url:
            continue
        if url in seen_urls and not REFETCH_SEEN:
            skipped += 1
            continue
        try:
            article_html = fetch_html(session, url)
            article = parse_article(url, article_html)
            title = article.get("title") or ref.get("title") or ""
            body = article.get("body") or ""
            if not title or not body:
                raise ValueError("missing title or body")
            rows.append(
                build_article_row(
                    source=source,
                    source_site=source_site,
                    url=url,
                    title=title,
                    published_at=article.get("published_at"),
                    body=body,
                    known_fencers=known_fencers,
                )
            )
            successful_urls.append(url)
        except Exception as exc:
            failed += 1
            print(f"  Article fetch/parse failed for {url}: {exc}")
        time.sleep(REQUEST_DELAY)

    return rows, failed, skipped, successful_urls


def scrape_news() -> dict:
    client = get_supabase_client()
    session = requests.Session()
    known_fencers = load_known_fencers(client)
    seen_state = get_state(STATE_SOURCE, "seen_urls") or []
    seen_urls = set(seen_state if isinstance(seen_state, list) else [])

    all_rows: list[dict] = []
    successful_urls: list[str] = []
    total_failed = 0
    total_skipped = 0

    for source_config in _source_configs():
        rows, failed, skipped, source_successful_urls = scrape_source(
            session=session,
            source_config=source_config,
            known_fencers=known_fencers,
            seen_urls=seen_urls,
        )
        all_rows.extend(rows)
        successful_urls.extend(source_successful_urls)
        total_failed += failed
        total_skipped += skipped
        time.sleep(REQUEST_DELAY)

    written = upsert_articles(client, all_rows)
    combined_seen = [url for url in seen_state if isinstance(seen_state, list) and url not in successful_urls]
    combined_seen.extend(successful_urls)
    set_state(STATE_SOURCE, "seen_urls", combined_seen[-5000:])
    set_state(STATE_SOURCE, "last_run", datetime.now(timezone.utc).isoformat())

    return {
        "written": written,
        "failed": total_failed,
        "skipped": total_skipped,
        "fetched": len(all_rows),
    }


def main():
    run_log = ScraperRunLogger("scrape_news").start()
    try:
        result = scrape_news()
        run_log.complete(
            written=result["written"],
            failed=result["failed"],
            skipped=result["skipped"],
            metadata={"fetched": result["fetched"]},
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

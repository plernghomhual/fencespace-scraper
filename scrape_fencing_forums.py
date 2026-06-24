import hashlib
import os
import re
import time
import unicodedata
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "scrape_fencing_forums"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

REDDIT_SUBREDDIT = "Fencing"
REDDIT_RSS_URL = "https://www.reddit.com/r/Fencing/.rss"
REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_API_URL = "https://oauth.reddit.com/r/Fencing/new"
FENCING_NET_FORUMS_URL = "https://fencing.net/forums/"
FENCING_NET_ROBOTS_URL = "https://fencing.net/robots.txt"

REQUEST_TIMEOUT = 20
REQUEST_DELAY = 1.0
UPSERT_BATCH_SIZE = 100
DEFAULT_LIMIT = 25
DISCUSSION_CONFLICT_COLUMNS = "source,thread_id"

HEADERS = {
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; contact@fencespace.app)",
    "Accept": "application/json,application/atom+xml,application/rss+xml,text/html;q=0.9,*/*;q=0.8",
}

PRIVATE_AUTHORS = {"", "[deleted]", "deleted", "none", "null"}
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def parse_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC).isoformat()
    text = clean_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def hash_author(author: Any, *, source: str) -> str | None:
    text = clean_text(author)
    if not text:
        return None
    text = re.sub(r"^(?:/)?u/", "", text, flags=re.IGNORECASE).strip()
    if text.casefold() in PRIVATE_AUTHORS:
        return None
    salt = os.environ.get("FORUM_AUTHOR_HASH_SALT", "fencespace-forum-author-v1")
    digest = hashlib.sha256(f"{salt}:{source}:{text.casefold()}".encode()).hexdigest()
    return f"sha256:{digest}"


def reddit_thread_id(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"/comments/([A-Za-z0-9_]+)/", text)
    if match:
        return match.group(1)
    if text.startswith("t3_"):
        return text[3:]
    return text


def fencing_net_thread_id(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return parsed.netloc
    return re.sub(r"[^A-Za-z0-9_./-]+", "-", path).strip("-")


def absolute_reddit_url(permalink: Any, fallback: Any = None) -> str | None:
    value = clean_text(permalink) or clean_text(fallback)
    if not value:
        return None
    return urljoin("https://www.reddit.com", value)


def parse_reddit_listing(
    payload: dict[str, Any],
    *,
    fetched_via: str,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    scraped = scraped_at or now_utc()
    discussions = []
    children = ((payload or {}).get("data") or {}).get("children") or []

    for child in children:
        data = child.get("data") or {}
        if data.get("over_18"):
            continue
        title = clean_text(data.get("title"))
        thread_id = reddit_thread_id(data.get("id") or data.get("name"))
        url = absolute_reddit_url(data.get("permalink"), data.get("url"))
        if not title or not thread_id or not url:
            continue
        flair = clean_text(data.get("link_flair_text"))
        metadata = {
            "comments": to_int(data.get("num_comments")),
            "fetched_via": fetched_via,
            "score": to_int(data.get("score")),
            "subreddit": clean_text(data.get("subreddit")),
            "upvote_ratio": to_float(data.get("upvote_ratio")),
        }
        discussions.append(
            {
                "source": "reddit",
                "thread_id": thread_id,
                "title": title,
                "url": url,
                "author_hash": hash_author(data.get("author"), source="reddit"),
                "posted_at": parse_timestamp(data.get("created_utc")),
                "tags": [flair] if flair else [],
                "related_fencer_ids": [],
                "summary": title,
                "metadata": metadata,
                "scraped_at": scraped,
            }
        )

    return discussions


def parse_reddit_rss(xml_text: str, *, scraped_at: str | None = None) -> list[dict[str, Any]]:
    scraped = scraped_at or now_utc()
    try:
        root = ET.fromstring(xml_text or "")
    except ET.ParseError:
        return []

    discussions = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title = clean_text(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
        link_node = entry.find("atom:link", ATOM_NS)
        url = clean_text(link_node.get("href")) if link_node is not None else None
        thread_id = reddit_thread_id(url) or reddit_thread_id(
            entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        )
        if not title or not url or not thread_id:
            continue
        author = entry.findtext("atom:author/atom:name", default="", namespaces=ATOM_NS)
        tags = []
        for category in entry.findall("atom:category", ATOM_NS):
            term = clean_text(category.get("term"))
            if term and term not in tags:
                tags.append(term)
        discussions.append(
            {
                "source": "reddit",
                "thread_id": thread_id,
                "title": title,
                "url": url,
                "author_hash": hash_author(author, source="reddit"),
                "posted_at": parse_timestamp(
                    entry.findtext("atom:updated", default="", namespaces=ATOM_NS)
                    or entry.findtext("atom:published", default="", namespaces=ATOM_NS)
                ),
                "tags": tags,
                "related_fencer_ids": [],
                "summary": title,
                "metadata": {"fetched_via": "rss"},
                "scraped_at": scraped,
            }
        )
    return discussions


def reddit_credentials() -> dict[str, str]:
    values = {
        "client_id": os.environ.get("REDDIT_CLIENT_ID", ""),
        "client_secret": os.environ.get("REDDIT_CLIENT_SECRET", ""),
        "user_agent": os.environ.get("REDDIT_USER_AGENT", ""),
    }
    return {key: value for key, value in values.items() if value}


def has_reddit_api_credentials(credentials: dict[str, str] | None) -> bool:
    credentials = credentials or {}
    return all(credentials.get(key) for key in ("client_id", "client_secret", "user_agent"))


def fetch_reddit_api_discussions(
    *,
    session: requests.Session,
    credentials: dict[str, str],
    limit: int,
    scraped_at: str | None,
    timeout: int,
) -> list[dict[str, Any]]:
    token_response = session.post(
        REDDIT_TOKEN_URL,
        auth=(credentials["client_id"], credentials["client_secret"]),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": credentials["user_agent"]},
        timeout=timeout,
    )
    token_response.raise_for_status()
    token = (token_response.json() or {}).get("access_token")
    if not token:
        print("reddit API skipped: no access token returned")
        return []

    response = session.get(
        REDDIT_API_URL,
        params={"limit": str(limit), "raw_json": "1"},
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": credentials["user_agent"],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_reddit_listing(response.json() or {}, fetched_via="api", scraped_at=scraped_at)


def fetch_reddit_rss_discussions(
    *,
    session: requests.Session,
    scraped_at: str | None,
    timeout: int,
) -> list[dict[str, Any]]:
    response = session.get(REDDIT_RSS_URL, headers=HEADERS, timeout=timeout)
    if response.status_code != 200:
        print(f"reddit RSS skipped: HTTP {response.status_code}")
        return []
    return parse_reddit_rss(response.text, scraped_at=scraped_at)


def fetch_reddit_discussions(
    *,
    session: requests.Session | None = None,
    credentials: dict[str, str] | None = None,
    limit: int = DEFAULT_LIMIT,
    scraped_at: str | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> list[dict[str, Any]]:
    http = session or requests.Session()
    creds = reddit_credentials() if credentials is None else credentials
    try:
        if has_reddit_api_credentials(creds):
            return fetch_reddit_api_discussions(
                session=http,
                credentials=creds,
                limit=limit,
                scraped_at=scraped_at,
                timeout=timeout,
            )
        print("REDDIT_CLIENT_ID/SECRET/USER_AGENT not set; using allowed subreddit RSS")
        return fetch_reddit_rss_discussions(
            session=http,
            scraped_at=scraped_at,
            timeout=timeout,
        )
    except Exception as exc:
        print(f"reddit discussions skipped: {exc}")
        return []


def should_keep_fencing_net_link(url: str, title: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc.casefold() != "fencing.net":
        return False
    path = parsed.path.strip("/")
    if not path:
        return False
    excluded_prefixes = (
        "about",
        "advertise",
        "authors",
        "category",
        "disclosure",
        "forums",
        "news",
        "press",
        "write-for-fencing-net",
    )
    if any(path.casefold().startswith(prefix) for prefix in excluded_prefixes):
        return "/forums/threads/" in parsed.path
    if title.casefold() in {"home", "news", "fencing clubs", "learn to fence"}:
        return False
    return True


def parse_fencing_net_forums_page(
    html: str,
    *,
    source_url: str = FENCING_NET_FORUMS_URL,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    scraped = scraped_at or now_utc()
    soup = BeautifulSoup(html or "", "html.parser")
    page_text = clean_text(soup.get_text(" ")) or ""
    retired = "forums retired" in page_text.casefold() or "retired the fencing.net forums" in page_text.casefold()
    container = soup.find("main") or soup.find("article") or soup.body or soup
    discussions = []
    seen_urls = set()

    for link in container.find_all("a", href=True):
        title = clean_text(link.get_text(" "))
        if not title:
            continue
        url = urljoin(source_url, clean_text(link.get("href")) or "")
        if url in seen_urls or not should_keep_fencing_net_link(url, title):
            continue
        seen_urls.add(url)
        is_thread = "/forums/threads/" in urlparse(url).path
        tags = ["forum-thread"] if is_thread else ["legacy-forum", "converted-topic"]
        discussions.append(
            {
                "source": "fencing_net",
                "thread_id": fencing_net_thread_id(url),
                "title": title,
                "url": url,
                "author_hash": None,
                "posted_at": None,
                "tags": tags,
                "related_fencer_ids": [],
                "summary": title,
                "metadata": {
                    "fetched_via": "html",
                    "probe_status": "forums_retired" if retired else "public_listing",
                    "source_kind": "forum_thread" if is_thread else "converted_forum_topic",
                    "source_url": source_url,
                },
                "scraped_at": scraped,
            }
        )

    return discussions


def robots_allows(
    *,
    session: requests.Session,
    robots_url: str,
    target_url: str,
    timeout: int,
) -> bool:
    try:
        response = session.get(robots_url, headers=HEADERS, timeout=timeout)
        if response.status_code >= 400:
            return True
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        return parser.can_fetch(HEADERS["User-Agent"], target_url)
    except Exception as exc:
        print(f"robots probe failed for {target_url}: {exc}")
        return False


def fetch_fencing_net_discussions(
    *,
    session: requests.Session | None = None,
    scraped_at: str | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> list[dict[str, Any]]:
    http = session or requests.Session()
    if not robots_allows(
        session=http,
        robots_url=FENCING_NET_ROBOTS_URL,
        target_url=FENCING_NET_FORUMS_URL,
        timeout=timeout,
    ):
        print("fencing.net forums skipped: robots.txt does not allow this path")
        return []
    try:
        response = http.get(FENCING_NET_FORUMS_URL, headers=HEADERS, timeout=timeout)
        if response.status_code != 200:
            print(f"fencing.net forums skipped: HTTP {response.status_code}")
            return []
        return parse_fencing_net_forums_page(response.text, scraped_at=scraped_at)
    except Exception as exc:
        print(f"fencing.net forums skipped: {exc}")
        return []


def normalize_for_match(value: Any) -> str:
    text = clean_text(value) or ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def build_fencer_index(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        name = clean_text(row.get("name"))
        normalized = normalize_for_match(name)
        if not name or len(normalized.split()) < 2:
            continue
        index.setdefault(normalized, []).append(row)
    return index


def text_contains_normalized_name(text: str, normalized_name: str) -> bool:
    if not text or not normalized_name:
        return False
    pattern = rf"(?<![A-Za-z0-9]){re.escape(normalized_name)}(?![A-Za-z0-9])"
    return re.search(pattern, text) is not None


def unique_fencer_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[Any, dict[str, Any]] = {}
    for candidate in candidates:
        fencer_id = candidate.get("id")
        if fencer_id is not None and fencer_id not in by_id:
            by_id[fencer_id] = candidate
    return list(by_id.values())


def attach_related_fencers(
    discussions: list[dict[str, Any]],
    fencer_index: dict[str, list[dict[str, Any]]],
) -> None:
    for discussion in discussions:
        text = normalize_for_match(
            " ".join(
                [
                    clean_text(discussion.get("title")) or "",
                    clean_text(discussion.get("summary")) or "",
                ]
            )
        )
        related_ids = set()
        for normalized_name, candidates in fencer_index.items():
            if not text_contains_normalized_name(text, normalized_name):
                continue
            unique_candidates = unique_fencer_candidates(candidates)
            display_name = clean_text(candidates[0].get("name")) or normalized_name
            if len(unique_candidates) != 1:
                ids = [candidate.get("id") for candidate in unique_candidates]
                print(f"ambiguous fencer match for {display_name}: {ids}")
                continue
            related_ids.add(unique_candidates[0]["id"])
        discussion["related_fencer_ids"] = sorted(related_ids)


def fetch_fencer_rows(client, *, page_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in range(0, 100000, page_size):
        result = (
            client.table("fs_fencers")
            .select("id,name,country,fie_id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
    return rows


def dedupe_discussions(discussions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for discussion in discussions:
        key = (discussion.get("source"), discussion.get("thread_id"))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        deduped.append(discussion)
    return deduped


def upsert_discussion_rows(
    client,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = UPSERT_BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_forum_discussions").upsert(
            batch,
            on_conflict=DISCUSSION_CONFLICT_COLUMNS,
        ).execute()
        written += len(batch)
    return written


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def scrape_forum_discussions(
    client,
    *,
    session: requests.Session | None = None,
    limit: int = DEFAULT_LIMIT,
    request_delay: float = REQUEST_DELAY,
    scraped_at: str | None = None,
) -> dict[str, int]:
    http = session or requests.Session()
    scraped = scraped_at or now_utc()
    failed = 0
    skipped = 0
    discussions: list[dict[str, Any]] = []

    try:
        reddit_discussions = fetch_reddit_discussions(
            session=http,
            limit=limit,
            scraped_at=scraped,
        )
        if reddit_discussions:
            discussions.extend(reddit_discussions)
        else:
            skipped += 1
    except Exception as exc:
        failed += 1
        print(f"reddit source failed: {exc}")

    if request_delay:
        time.sleep(request_delay)

    try:
        fencing_net_discussions = fetch_fencing_net_discussions(
            session=http,
            scraped_at=scraped,
        )
        if fencing_net_discussions:
            discussions.extend(fencing_net_discussions)
        else:
            skipped += 1
    except Exception as exc:
        failed += 1
        print(f"fencing.net source failed: {exc}")

    discussions = dedupe_discussions(discussions)
    try:
        fencer_index = build_fencer_index(fetch_fencer_rows(client))
        attach_related_fencers(discussions, fencer_index)
    except Exception as exc:
        failed += 1
        print(f"fencer matching skipped: {exc}")

    written = upsert_discussion_rows(client, discussions) if discussions else 0
    return {
        "sources_seen": 2,
        "discussions_found": len(discussions),
        "rows_written": written,
        "failed": failed,
        "skipped": skipped,
    }


def main() -> None:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous forum discussion state: {previous_state}")

        client = get_supabase_client()
        summary = scrape_forum_discussions(client)
        set_state(
            SOURCE,
            "last_run",
            {
                **summary,
                "updated_at": now_utc(),
            },
        )
        run_log.complete(
            written=summary["rows_written"],
            failed=summary["failed"],
            skipped=summary["skipped"],
            metadata=summary,
        )
        print(
            "Forum discussion scraper complete: "
            f"{summary['rows_written']} rows written, "
            f"{summary['skipped']} sources skipped, "
            f"{summary['failed']} failures"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

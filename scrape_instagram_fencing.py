import hashlib
import html
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


SOURCE = "instagram_fencing"
SOURCE_SITE = "instagram.com"
PROVIDER_GRAPH = "instagram_graph_business_discovery"
PROVIDER_FIXTURE = "fixture"
GRAPH_BASE_URL = "https://graph.facebook.com"
DEFAULT_GRAPH_VERSION = "v24.0"
DEFAULT_FEDERATION_HANDLES = ("fencing_fie", "usafencing", "britishfencing")
REQUEST_DELAY = float(os.environ.get("INSTAGRAM_REQUEST_DELAY", "1.0"))
REQUEST_TIMEOUT = int(os.environ.get("INSTAGRAM_REQUEST_TIMEOUT", "20"))
MAX_POSTS_PER_HANDLE = int(os.environ.get("INSTAGRAM_POST_LIMIT", "10"))
BATCH_SIZE = int(os.environ.get("INSTAGRAM_BATCH_SIZE", "100"))
CAPTION_SNIPPET_LIMIT = int(os.environ.get("INSTAGRAM_CAPTION_SNIPPET_LIMIT", "500"))

ACCESS_TOKEN_KEYS = (
    "INSTAGRAM_GRAPH_ACCESS_TOKEN",
    "INSTAGRAM_ACCESS_TOKEN",
    "META_GRAPH_ACCESS_TOKEN",
)
BUSINESS_ACCOUNT_ID_KEYS = (
    "INSTAGRAM_BUSINESS_ACCOUNT_ID",
    "INSTAGRAM_GRAPH_BUSINESS_ACCOUNT_ID",
    "META_INSTAGRAM_BUSINESS_ACCOUNT_ID",
)
RESERVED_INSTAGRAM_PATHS = {"accounts", "explore", "p", "reel", "reels", "stories", "tv"}

DRY_RUN_KNOWN_FENCERS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Lee Kiefer",
        "instagram_handle": "leetothekiefer",
    }
]

DRY_RUN_PAYLOADS = {
    "fencing_fie": {
        "business_discovery": {
            "id": "17841400000000000",
            "username": "fencing_fie",
            "name": "International Fencing Federation",
            "media_count": 1,
            "media": {
                "data": [
                    {
                        "id": "fixture-instagram-post-1",
                        "caption": "Lee Kiefer wins gold. Congrats @leetothekiefer #fencing",
                        "media_type": "IMAGE",
                        "permalink": "https://www.instagram.com/p/FixturePost/",
                        "timestamp": "2026-05-31T18:45:12+0000",
                        "username": "fencing_fie",
                    }
                ]
            },
        }
    }
}


def clean_text(value: Any) -> str | None:
    text = html.unescape(str(value or "")).strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def _env_value(env: dict[str, str] | os._Environ[str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = clean_text(env.get(key))
        if value:
            return value
    return None


def _split_csv(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,;\n]+", text) if part.strip()]


def normalize_handle(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if text.startswith(("http://", "https://")):
        parsed = urlparse(text)
        segments = [part for part in parsed.path.split("/") if part]
        text = segments[0] if segments else ""
    text = text.strip().strip("/").lstrip("@").casefold()
    if not re.fullmatch(r"[a-z0-9._]{1,30}", text):
        return None
    if text in RESERVED_INSTAGRAM_PATHS:
        return None
    return text


def normalize_post_url(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    parsed = urlparse(text)
    host = parsed.netloc.casefold().removeprefix("www.")
    if parsed.scheme not in {"http", "https"} or host != "instagram.com":
        return None
    segments = [part for part in parsed.path.split("/") if part]
    if len(segments) < 2 or segments[0].casefold() not in {"p", "reel", "reels", "tv"}:
        return None
    path = "/" + "/".join(segments[:2]) + "/"
    return urlunparse(("https", "www.instagram.com", path, "", "", ""))


def normalize_timestamp(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    if re.search(r"[+-]\d{4}$", text):
        text = f"{text[:-5]}{text[-5:-2]}:{text[-2:]}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def redact_sensitive_text(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[redacted-email]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", "[redacted-phone]", text)
    return clean_text(text)


def caption_snippet(value: Any, limit: int = CAPTION_SNIPPET_LIMIT) -> str | None:
    text = redact_sensitive_text(value)
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def extract_mention_tags(text: str) -> list[str]:
    mentions: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"(?<![a-zA-Z0-9_.])@([a-zA-Z0-9._]{1,30})", text or ""):
        handle = normalize_handle(match.group(1))
        if handle and handle not in seen:
            mentions.append(handle)
            seen.add(handle)
    return mentions


def _normalize_for_match(value: Any) -> str | None:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized).casefold()
    return clean_text(normalized)


def _name_aliases(name: Any) -> list[str]:
    normalized = _normalize_for_match(name)
    if not normalized:
        return []
    aliases = [normalized]
    parts = normalized.split()
    if len(parts) == 2:
        aliases.append(f"{parts[1]} {parts[0]}")
    return aliases


def _fencer_handles(fencer: dict[str, Any]) -> set[str]:
    handles: set[str] = set()
    for key in ("instagram_handle", "handle"):
        handle = normalize_handle(fencer.get(key))
        if handle:
            handles.add(handle)
    metadata = fencer.get("metadata")
    if isinstance(metadata, dict):
        handle = normalize_handle(metadata.get("instagram_handle"))
        if handle:
            handles.add(handle)
        social_handles = metadata.get("social_handles")
        if isinstance(social_handles, dict):
            handle = normalize_handle(social_handles.get("instagram"))
            if handle:
                handles.add(handle)
    for key in ("instagram_handles", "handles"):
        values = fencer.get(key)
        if isinstance(values, (list, tuple, set)):
            for value in values:
                handle = normalize_handle(value)
                if handle:
                    handles.add(handle)
    return handles


def extract_related_fencer_ids(
    text: str,
    mention_tags: list[str],
    known_fencers: list[dict[str, Any]],
) -> list[str]:
    normalized_text = _normalize_for_match(text) or ""
    mention_set = {normalize_handle(tag) for tag in mention_tags}
    mention_set.discard(None)
    related: list[str] = []
    seen: set[str] = set()

    for fencer in known_fencers:
        fencer_id = fencer.get("id") or fencer.get("fencer_id")
        if not fencer_id:
            continue
        matched = bool(_fencer_handles(fencer) & mention_set)
        if not matched:
            for alias in _name_aliases(fencer.get("name")):
                if len(alias) < 3:
                    continue
                pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
                if re.search(pattern, normalized_text):
                    matched = True
                    break
        if matched and fencer_id not in seen:
            related.append(fencer_id)
            seen.add(fencer_id)
    return related


def parse_business_discovery_payload(
    handle: str,
    payload: dict[str, Any],
    *,
    known_fencers: list[dict[str, Any]],
    provider: str = PROVIDER_GRAPH,
) -> tuple[list[dict[str, Any]], str | None]:
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = str(error.get("message") or "").casefold()
        if any(marker in message for marker in ("missing permissions", "unsupported get request", "private", "login")):
            return [], "provider_unavailable_or_private"
        return [], "provider_error"

    account = payload.get("business_discovery") if isinstance(payload, dict) else None
    if not isinstance(account, dict):
        return [], "provider_unavailable_or_private"

    normalized_handle = normalize_handle(account.get("username") or handle)
    if not normalized_handle:
        return [], "invalid_handle"

    account_metadata = {
        "username": normalized_handle,
        "name": clean_text(account.get("name")),
        "media_count": account.get("media_count") if isinstance(account.get("media_count"), int) else None,
    }
    account_metadata = {key: value for key, value in account_metadata.items() if value is not None}

    media = account.get("media") or {}
    items = media.get("data") if isinstance(media, dict) else media
    if not isinstance(items, list):
        return [], "no_public_posts"

    posts: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        post_url = normalize_post_url(item.get("permalink"))
        timestamp = normalize_timestamp(item.get("timestamp"))
        if not post_url or not timestamp:
            continue
        raw_caption = clean_text(item.get("caption")) or ""
        mentions = extract_mention_tags(raw_caption)
        posts.append(
            {
                "platform": "instagram",
                "handle": normalized_handle,
                "post_id": clean_text(item.get("id")),
                "post_url": post_url,
                "timestamp": timestamp,
                "caption_snippet": caption_snippet(raw_caption),
                "mention_tags": mentions,
                "related_fencer_ids": extract_related_fencer_ids(raw_caption, mentions, known_fencers),
                "media_type": clean_text(item.get("media_type")),
                "account": account_metadata,
                "provider": provider,
            }
        )

    return posts, None if posts else "no_public_posts"


def build_business_discovery_fields(handle: str, limit: int) -> str:
    return (
        f"business_discovery.username({handle})"
        "{id,username,name,media_count,"
        f"media.limit({max(1, limit)})"
        "{id,caption,media_type,permalink,timestamp,username}}"
    )


def fetch_business_discovery_payload(
    session: requests.Session,
    *,
    handle: str,
    access_token: str,
    business_account_id: str,
    graph_version: str,
    limit: int,
) -> dict[str, Any]:
    url = f"{GRAPH_BASE_URL}/{graph_version}/{business_account_id}"
    response = session.get(
        url,
        params={
            "fields": build_business_discovery_fields(handle, limit),
            "access_token": access_token,
        },
        timeout=REQUEST_TIMEOUT,
    )
    try:
        payload = response.json()
    except Exception:
        payload = {"error": {"message": f"HTTP {response.status_code}: non-JSON response"}}
    if response.status_code >= 400 and "error" not in payload:
        payload = {"error": {"message": f"HTTP {response.status_code}"}}
    return payload


def build_article_row(post: dict[str, Any]) -> dict[str, Any]:
    summary = caption_snippet(post.get("caption_snippet"))
    title = f"Instagram post by @{post['handle']}"
    content_payload = "\n".join(
        [
            clean_text(post.get("post_url")) or "",
            clean_text(post.get("timestamp")) or "",
            clean_text(summary) or "",
        ]
    )
    metadata = {
        "platform": "instagram",
        "handle": post.get("handle"),
        "post_id": post.get("post_id"),
        "post_url": post.get("post_url"),
        "caption_snippet": summary,
        "mention_tags": post.get("mention_tags") or [],
        "account": post.get("account") or {},
        "media_type": post.get("media_type"),
        "provider": post.get("provider") or PROVIDER_GRAPH,
    }
    return {
        "title": title,
        "url": post["post_url"],
        "source": SOURCE,
        "source_site": SOURCE_SITE,
        "published_at": post.get("timestamp"),
        "category": "general",
        "summary": summary,
        "related_fencer_ids": post.get("related_fencer_ids") or [],
        "content_hash": hashlib.sha256(content_payload.encode("utf-8")).hexdigest(),
        "metadata": {key: value for key, value in metadata.items() if value is not None},
    }


def upsert_instagram_rows(client: Any, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    by_url: dict[str, dict[str, Any]] = {}
    for row in rows:
        url = row.get("url")
        if url:
            by_url[url] = row
    deduped = list(by_url.values())
    written = 0
    for index in range(0, len(deduped), batch_size):
        batch = deduped[index : index + batch_size]
        client.table("fs_articles").upsert(batch, on_conflict="url").execute()
        written += len(batch)
    return written


def _fetch_table_rows(client: Any, table: str, columns: str, page_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        result = client.table(table).select(columns).range(offset, offset + page_size - 1).execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def load_known_fencers(client: Any) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    try:
        for row in _fetch_table_rows(client, "fs_fencers", "id,name"):
            fencer_id = row.get("id")
            if fencer_id:
                by_id[fencer_id] = {"id": fencer_id, "name": row.get("name")}
    except Exception as exc:
        print(f"  Could not load fencers for Instagram matching: {exc}")

    try:
        query = client.table("fs_fencer_social_media").select("fencer_id,handle,url,metadata").eq("platform", "instagram")
        rows = query.range(0, 999).execute().data or []
        for row in rows:
            fencer_id = row.get("fencer_id")
            handle = normalize_handle(row.get("handle") or row.get("url"))
            if not fencer_id or not handle:
                continue
            fencer = by_id.setdefault(fencer_id, {"id": fencer_id, "name": None})
            fencer["instagram_handle"] = handle
    except Exception as exc:
        print(f"  Could not load Instagram social handles: {exc}")

    return list(by_id.values())


def target_handles(client: Any | None, env: dict[str, str] | os._Environ[str], known_fencers: list[dict[str, Any]]) -> list[str]:
    handles: list[str] = []
    configured = _split_csv(env.get("INSTAGRAM_FENCING_HANDLES"))
    for value in configured or DEFAULT_FEDERATION_HANDLES:
        handle = normalize_handle(value)
        if handle:
            handles.append(handle)
    for fencer in known_fencers:
        handles.extend(_fencer_handles(fencer))
    return list(dict.fromkeys(handles))


def get_supabase_client():
    if supabase is not None:
        return supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set for live Instagram writes.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def scrape_instagram_fencing(
    *,
    client: Any | None = None,
    env: dict[str, str] | os._Environ[str] | None = None,
    session: requests.Session | None = None,
    request_delay: float | None = None,
    dry_run: bool | None = None,
    write: bool = True,
    max_posts_per_handle: int | None = None,
) -> dict[str, Any]:
    env = os.environ if env is None else env
    request_delay = REQUEST_DELAY if request_delay is None else request_delay
    max_posts_per_handle = MAX_POSTS_PER_HANDLE if max_posts_per_handle is None else max_posts_per_handle
    access_token = _env_value(env, ACCESS_TOKEN_KEYS)
    business_account_id = _env_value(env, BUSINESS_ACCOUNT_ID_KEYS)
    graph_version = clean_text(env.get("INSTAGRAM_GRAPH_API_VERSION")) or DEFAULT_GRAPH_VERSION
    has_credentials = bool(access_token and business_account_id)
    dry_run = (not has_credentials) if dry_run is None else dry_run

    posts: list[dict[str, Any]] = []
    skipped = 0
    failed = 0
    skip_reasons: dict[str, str] = {}

    if dry_run:
        for handle, payload in DRY_RUN_PAYLOADS.items():
            parsed_posts, skip_reason = parse_business_discovery_payload(
                handle,
                payload,
                known_fencers=DRY_RUN_KNOWN_FENCERS,
                provider=PROVIDER_FIXTURE,
            )
            posts.extend(parsed_posts)
            if skip_reason:
                skipped += 1
                skip_reasons[handle] = skip_reason
        rows = [build_article_row(post) for post in posts]
        return {
            "provider": PROVIDER_FIXTURE,
            "dry_run": True,
            "handles": len(DRY_RUN_PAYLOADS),
            "fetched": len(posts),
            "written": 0,
            "failed": failed,
            "skipped": skipped,
            "skip_reasons": skip_reasons,
            "rows": rows,
        }

    client = client or get_supabase_client()
    session = session or requests.Session()
    known_fencers = load_known_fencers(client)
    handles = target_handles(client, env, known_fencers)

    for index, handle in enumerate(handles):
        try:
            payload = fetch_business_discovery_payload(
                session,
                handle=handle,
                access_token=access_token,
                business_account_id=business_account_id,
                graph_version=graph_version,
                limit=max_posts_per_handle,
            )
            parsed_posts, skip_reason = parse_business_discovery_payload(
                handle,
                payload,
                known_fencers=known_fencers,
                provider=PROVIDER_GRAPH,
            )
            posts.extend(parsed_posts)
            if skip_reason:
                skipped += 1
                skip_reasons[handle] = skip_reason
                if skip_reason == "provider_error":
                    failed += 1
        except Exception as exc:
            failed += 1
            skip_reasons[handle] = str(exc)[:500]
            print(f"  Instagram provider fetch failed for @{handle}: {exc}")
        if request_delay > 0 and index < len(handles) - 1:
            time.sleep(request_delay)

    rows = [build_article_row(post) for post in posts]
    written = upsert_instagram_rows(client, rows) if write else 0
    summary = {
        "provider": PROVIDER_GRAPH,
        "dry_run": False,
        "handles": len(handles),
        "fetched": len(posts),
        "written": written,
        "failed": failed,
        "skipped": skipped,
        "skip_reasons": skip_reasons,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    set_state(SOURCE, "last_run", summary)
    return {**summary, "rows": rows}


def main() -> None:
    run_log = ScraperRunLogger("scrape_instagram_fencing").start()
    try:
        result = scrape_instagram_fencing()
        run_log.complete(
            written=result["written"],
            failed=result["failed"],
            skipped=result["skipped"],
            metadata={
                "provider": result["provider"],
                "dry_run": result["dry_run"],
                "handles": result["handles"],
                "fetched": result["fetched"],
            },
        )
        print(
            "Instagram fencing aggregation complete - "
            f"provider={result['provider']}, dry_run={result['dry_run']}, "
            f"handles={result['handles']}, fetched={result['fetched']}, "
            f"written={result['written']}, failed={result['failed']}, skipped={result['skipped']}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

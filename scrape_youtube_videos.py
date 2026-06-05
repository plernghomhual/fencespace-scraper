from __future__ import annotations

import html
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from run_logger import ScraperRunLogger
from scraper_state import set_state


SOURCE = "scrape_youtube_videos"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
REQUEST_TIMEOUT = float(os.environ.get("YOUTUBE_REQUEST_TIMEOUT", "20"))
REQUEST_DELAY = float(os.environ.get("YOUTUBE_REQUEST_DELAY", "0.1"))
YOUTUBE_MAX_RESULTS = int(os.environ.get("YOUTUBE_MAX_RESULTS", "10"))
FENCER_QUERY_LIMIT = int(os.environ.get("YOUTUBE_FENCER_QUERY_LIMIT", "100"))
TOURNAMENT_QUERY_LIMIT = int(os.environ.get("YOUTUBE_TOURNAMENT_QUERY_LIMIT", "100"))
PAGE_SIZE = 1000
UPSERT_BATCH_SIZE = 100

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

HEADERS = {
    "User-Agent": "FenceSpaceBot/1.0 (youtube-video-indexer; +https://fencespace.app)",
    "Accept": "application/json",
}

WEAPON_PATTERNS = {
    "foil": re.compile(r"\bfoil\b", re.IGNORECASE),
    "epee": re.compile(r"\b(?:epee|epée)\b", re.IGNORECASE),
    "sabre": re.compile(r"\b(?:sabre|saber)\b", re.IGNORECASE),
}
GENERAL_CONTENT_KEYWORDS = {
    "interview",
    "training",
    "tutorial",
    "lesson",
    "tips",
    "review",
    "podcast",
    "documentary",
    "preview",
    "recap",
    "highlight",
    "highlights",
}
MATCH_PATTERNS = (
    re.compile(r"\b(?:vs|v\.?|versus)\b", re.IGNORECASE),
    re.compile(r"\bfull\s+(?:bout|match)\b", re.IGNORECASE),
    re.compile(r"\b(?:gold|bronze)\s+medal\s+(?:bout|match)\b", re.IGNORECASE),
    re.compile(r"\b(?:semi[- ]?final|quarter[- ]?final)\b", re.IGNORECASE),
    re.compile(r"\btable\s+of\s+\d+\b", re.IGNORECASE),
)
TOURNAMENT_WORDS = (
    "world cup",
    "grand prix",
    "world championship",
    "olympic",
    "european championship",
    "asian championship",
    "pan american championship",
)
PRIVATE_OR_DELETED_TITLES = {"private video", "[private video]", "deleted video", "[deleted video]"}


@dataclass(frozen=True)
class SearchQuery:
    text: str
    source_type: str
    source_id: str | None = None
    source_name: str | None = None
    tournament_id: str | None = None


@dataclass(frozen=True)
class FencerMatchResult:
    related_ids: list[str]
    ambiguities: list[dict[str, Any]]


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = html.unescape(str(value or "")).replace("\u200b", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def parse_datetime(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _normalize_for_match(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).casefold()
    return clean_text(text) or ""


def _name_aliases(name: str) -> list[str]:
    normalized = _normalize_for_match(name)
    if not normalized:
        return []
    parts = normalized.split()
    if len(parts) < 2:
        return []
    aliases = [normalized]
    if len(parts) == 2:
        aliases.append(f"{parts[1]} {parts[0]}")
    return aliases


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _matches_alias(normalized_text: str, alias: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized_text))


def match_related_fencers(
    text: str,
    known_fencers: list[dict[str, Any]],
    *,
    log_ambiguity: bool = False,
) -> FencerMatchResult:
    normalized_text = _normalize_for_match(text)
    alias_candidates: dict[str, list[dict[str, str]]] = {}
    for fencer in known_fencers:
        fencer_id = clean_text(fencer.get("id"))
        name = clean_text(fencer.get("name"))
        if not fencer_id or not name:
            continue
        for alias in _name_aliases(name):
            alias_candidates.setdefault(alias, []).append({"id": fencer_id, "name": name})

    related: list[str] = []
    seen_related: set[str] = set()
    ambiguities: list[dict[str, Any]] = []
    seen_ambiguous_aliases: set[str] = set()
    checked_aliases: set[str] = set()

    for fencer in known_fencers:
        name = clean_text(fencer.get("name"))
        if not name:
            continue
        for alias in _name_aliases(name):
            if alias in checked_aliases or not _matches_alias(normalized_text, alias):
                continue
            checked_aliases.add(alias)
            candidates = alias_candidates.get(alias, [])
            candidate_ids = _unique_preserving_order([candidate["id"] for candidate in candidates])
            if len(candidate_ids) > 1:
                if alias not in seen_ambiguous_aliases:
                    ambiguity = {"name": candidates[0]["name"], "candidate_ids": candidate_ids}
                    ambiguities.append(ambiguity)
                    seen_ambiguous_aliases.add(alias)
                    if log_ambiguity:
                        print(
                            "Ambiguous fencer match: "
                            f"{ambiguity['name']} -> {', '.join(candidate_ids)}"
                        )
                break
            if candidate_ids and candidate_ids[0] not in seen_related:
                related.append(candidate_ids[0])
                seen_related.add(candidate_ids[0])
            break

    return FencerMatchResult(related_ids=related, ambiguities=ambiguities)


def classify_video(title: str, description: str | None = None) -> tuple[str, list[str]]:
    combined = f"{clean_text(title) or ''} {clean_text(description) or ''}"
    lowered = combined.casefold()
    tags: list[str] = []

    for weapon, pattern in WEAPON_PATTERNS.items():
        if pattern.search(combined):
            tags.append(weapon)

    if re.search(r"\bfinal\b", lowered):
        tags.append("final")
    if re.search(r"\bsemi[- ]?final\b", lowered):
        tags.append("semifinal")
    if re.search(r"\bquarter[- ]?final\b", lowered):
        tags.append("quarterfinal")
    if re.search(r"\bteam\b", lowered):
        tags.append("team")

    general_hits = [keyword for keyword in GENERAL_CONTENT_KEYWORDS if keyword in lowered]
    for keyword in general_hits:
        tags.append(keyword)

    has_match_indicator = any(pattern.search(combined) for pattern in MATCH_PATTERNS)
    has_tournament_final = (
        "final" in lowered
        and bool(tags and any(tag in {"foil", "epee", "sabre"} for tag in tags))
        and any(word in lowered for word in TOURNAMENT_WORDS)
    )
    is_general = bool(general_hits)
    if (has_match_indicator or has_tournament_final) and not is_general:
        return "likely_match", _unique_preserving_order(["likely_match", *tags])
    return "general", _unique_preserving_order(["general", *tags])


def _best_thumbnail(snippet: dict[str, Any]) -> str | None:
    thumbnails = snippet.get("thumbnails")
    if not isinstance(thumbnails, dict):
        return None
    for key in ("maxres", "standard", "high", "medium", "default"):
        candidate = thumbnails.get(key)
        if isinstance(candidate, dict) and candidate.get("url"):
            return str(candidate["url"])
    return None


def parse_youtube_search_response(
    data: dict[str, Any],
    *,
    query: SearchQuery,
    known_fencers: list[dict[str, Any]],
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()

    for item in data.get("items", []):
        item_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(item_id, dict) or item_id.get("kind") != "youtube#video":
            continue
        video_id = clean_text(item_id.get("videoId"))
        if not video_id:
            continue

        snippet = item.get("snippet") or {}
        if not isinstance(snippet, dict):
            continue
        title = clean_text(snippet.get("title"))
        if not title or title.casefold() in PRIVATE_OR_DELETED_TITLES:
            continue
        description = clean_text(snippet.get("description")) or ""
        channel = clean_text(snippet.get("channelTitle"))
        published_at = parse_datetime(snippet.get("publishedAt"))
        classification, tags = classify_video(title, description)
        fencer_match = match_related_fencers(
            f"{title} {description}",
            known_fencers,
            log_ambiguity=True,
        )
        metadata: dict[str, Any] = {
            "source_api": "youtube.search.list",
            "query": query.text,
            "query_source_type": query.source_type,
            "query_source_id": query.source_id,
            "query_source_name": query.source_name,
            "classification": classification,
            "description": description,
            "channel_id": clean_text(snippet.get("channelId")),
            "live_broadcast_content": clean_text(snippet.get("liveBroadcastContent")),
            "thumbnail_url": _best_thumbnail(snippet),
            "etag": item.get("etag"),
        }
        metadata = {key: value for key, value in metadata.items() if value not in (None, "")}
        if fencer_match.ambiguities:
            metadata["fencer_match_ambiguities"] = fencer_match.ambiguities

        rows.append(
            {
                "platform": "youtube",
                "video_id": video_id,
                "title": title,
                "channel": channel,
                "published_at": published_at,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "related_fencer_ids": fencer_match.related_ids,
                "tournament_id": query.tournament_id,
                "tags": tags,
                "metadata": metadata,
                "scraped_at": scraped_at,
            }
        )

    return rows


def build_search_queries(
    *,
    fencers: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    fencer_limit: int = FENCER_QUERY_LIMIT,
    tournament_limit: int = TOURNAMENT_QUERY_LIMIT,
) -> list[SearchQuery]:
    queries: list[SearchQuery] = []
    seen_texts: set[str] = set()

    for fencer in fencers:
        if len([query for query in queries if query.source_type == "fencer"]) >= fencer_limit:
            break
        name = clean_text(fencer.get("name"))
        if not name:
            continue
        text = f'fencing "{name}"'
        if text in seen_texts:
            continue
        seen_texts.add(text)
        queries.append(
            SearchQuery(
                text=text,
                source_type="fencer",
                source_id=clean_text(fencer.get("id")),
                source_name=name,
            )
        )

    for tournament in tournaments:
        if len([query for query in queries if query.source_type == "tournament"]) >= tournament_limit:
            break
        name = clean_text(tournament.get("name"))
        if not name:
            continue
        text = f'fencing "{name}"'
        if text in seen_texts:
            continue
        seen_texts.add(text)
        queries.append(
            SearchQuery(
                text=text,
                source_type="tournament",
                source_id=clean_text(tournament.get("id")),
                source_name=name,
                tournament_id=clean_text(tournament.get("id")),
            )
        )

    return queries


def load_known_fencers(client: Any, *, limit: int = FENCER_QUERY_LIMIT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while len(rows) < limit:
        result = (
            client.table("fs_fencers")
            .select("id,name,world_rank")
            .order("world_rank", desc=False)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        batch = result.data or []
        for row in batch:
            if row.get("id") and clean_text(row.get("name")):
                rows.append(row)
                if len(rows) >= limit:
                    break
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def load_tournaments(client: Any, *, limit: int = TOURNAMENT_QUERY_LIMIT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while len(rows) < limit:
        result = (
            client.table("fs_tournaments")
            .select("id,name,start_date")
            .order("start_date", desc=True)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        batch = result.data or []
        for row in batch:
            if row.get("id") and clean_text(row.get("name")):
                rows.append(row)
                if len(rows) >= limit:
                    break
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def search_youtube(
    session: requests.Session,
    query: SearchQuery,
    *,
    api_key: str,
    max_results: int = YOUTUBE_MAX_RESULTS,
) -> dict[str, Any]:
    response = session.get(
        YOUTUBE_SEARCH_URL,
        params={
            "part": "snippet",
            "q": query.text,
            "type": "video",
            "maxResults": max_results,
            "key": api_key,
        },
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    elif getattr(response, "status_code", 200) >= 400:
        raise RuntimeError(f"YouTube search failed: HTTP {response.status_code}")
    return response.json()


def _merge_list_field(first: Any, second: Any) -> list[str]:
    values: list[str] = []
    for item in (first, second):
        if isinstance(item, list):
            values.extend(str(value) for value in item if value)
        elif item:
            values.append(str(item))
    return _unique_preserving_order(values)


def _merge_video_rows(existing: dict[str, Any], new_row: dict[str, Any]) -> dict[str, Any]:
    merged = {**existing, **new_row}
    for field in ("related_fencer_ids", "tags"):
        if field in existing or field in new_row:
            merged[field] = _merge_list_field(existing.get(field), new_row.get(field))

    existing_metadata = (existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}) or {}
    new_metadata = (new_row.get("metadata") if isinstance(new_row.get("metadata"), dict) else {}) or {}
    if existing_metadata or new_metadata:
        merged["metadata"] = {**existing_metadata, **new_metadata}

    return merged


def upsert_video_rows(client: Any, rows: list[dict[str, Any]], *, batch_size: int = UPSERT_BATCH_SIZE) -> int:
    by_video_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        video_id = clean_text(row.get("video_id"))
        if video_id:
            by_video_id[video_id] = (
                _merge_video_rows(by_video_id[video_id], row)
                if video_id in by_video_id
                else row
            )
    deduped = list(by_video_id.values())
    for index in range(0, len(deduped), batch_size):
        client.table("fs_fencing_videos").upsert(
            deduped[index : index + batch_size],
            on_conflict="video_id",
        ).execute()
    return len(deduped)


def scrape_youtube_videos(
    *,
    client: Any | None = None,
    session: requests.Session | None = None,
    api_key: str | None = None,
    fencer_limit: int = FENCER_QUERY_LIMIT,
    tournament_limit: int = TOURNAMENT_QUERY_LIMIT,
    log_run: bool = True,
    update_state: bool = True,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("Skipping YouTube video indexing: YOUTUBE_API_KEY is not set.")
        summary = {
            "queries": 0,
            "parsed": 0,
            "written": 0,
            "failed": 0,
            "skipped": 1,
            "dry_run": True,
        }
        if log_run:
            ScraperRunLogger(SOURCE).start().complete(
                written=0,
                failed=0,
                skipped=1,
                metadata={"dry_run": True},
            )
        return summary

    client = client or get_supabase_client()
    if client is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set when YOUTUBE_API_KEY is set.")
    session = session or requests.Session()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    failed = 0
    all_rows: list[dict[str, Any]] = []
    query_count = 0

    try:
        known_fencers = load_known_fencers(client, limit=fencer_limit)
        tournaments = load_tournaments(client, limit=tournament_limit)
        queries = build_search_queries(
            fencers=known_fencers,
            tournaments=tournaments,
            fencer_limit=fencer_limit,
            tournament_limit=tournament_limit,
        )

        for index, query in enumerate(queries):
            if index > 0:
                sleeper(REQUEST_DELAY)
            query_count += 1
            try:
                payload = search_youtube(session, query, api_key=api_key)
                all_rows.extend(
                    parse_youtube_search_response(
                        payload,
                        query=query,
                        known_fencers=known_fencers,
                    )
                )
            except Exception as exc:
                failed += 1
                print(f"  YouTube search failed for {query.text}: {exc}")

        written = upsert_video_rows(client, all_rows)
        summary = {
            "queries": query_count,
            "parsed": len(all_rows),
            "written": written,
            "failed": failed,
            "skipped": 0,
            "dry_run": False,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "queries": query_count,
                    "parsed": len(all_rows),
                    "written": written,
                    "failed": failed,
                },
            )
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=0,
                metadata={"queries": query_count, "parsed": len(all_rows)},
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    summary = scrape_youtube_videos()
    print(
        "Done - "
        f"queries={summary['queries']}, parsed={summary['parsed']}, "
        f"written={summary['written']}, failed={summary['failed']}, "
        f"skipped={summary['skipped']}, dry_run={summary['dry_run']}"
    )


if __name__ == "__main__":
    main()

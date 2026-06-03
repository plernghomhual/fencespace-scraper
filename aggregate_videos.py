import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

SOURCE = "aggregate_videos"
PROVIDER = "youtube"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"

PAGE_SIZE = 1000
UPSERT_BATCH_SIZE = 100
DEFAULT_FENCER_LIMIT = 100
DEFAULT_TOURNAMENT_LIMIT = 100
DEFAULT_MAX_RESULTS_PER_QUERY = 10
REQUEST_TIMEOUT = 20
REQUEST_DELAY_SECONDS = 0.25

OFFICIAL_CHANNELS = (
    ("FIE Fencing", None),
    ("USA Fencing", None),
    ("European Fencing Confederation", None),
    ("British Fencing", None),
)

FENCING_SIGNAL_TOKENS = {
    "epee",
    "epée",
    "fencing",
    "fencer",
    "fencers",
    "fechten",
    "fie",
    "foil",
    "saber",
    "sabre",
    "scherma",
    "escrime",
}

FALSE_POSITIVE_PHRASES = (
    "backyard fence",
    "chain link fence",
    "garden fence",
    "home depot",
    "privacy fence",
    "vinyl fence",
    "wood fence",
)

FALSE_POSITIVE_TOKENS = {
    "backyard",
    "deck",
    "diy",
    "gate",
    "garden",
    "installer",
    "installation",
    "landscaping",
    "picket",
    "privacy",
    "staining",
}

STOP_TOKENS = {
    "and",
    "championship",
    "championships",
    "cup",
    "de",
    "du",
    "fencing",
    "games",
    "grand",
    "la",
    "le",
    "of",
    "prix",
    "the",
    "v",
    "vs",
    "world",
}

FALLBACK_STOP_TOKENS = {
    "and",
    "de",
    "du",
    "la",
    "le",
    "of",
    "the",
    "v",
    "vs",
}


@dataclass(frozen=True)
class RelatedTarget:
    kind: str
    id: str | None
    name: str
    query: str | None = None
    channel_id: str | None = None


class RateLimiter:
    def __init__(
        self,
        min_interval_seconds: float = REQUEST_DELAY_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.min_interval_seconds = min_interval_seconds
        self.clock = clock
        self.sleeper = sleeper
        self._last_call: float | None = None

    def wait(self) -> None:
        now = self.clock()
        if self._last_call is not None:
            elapsed = now - self._last_call
            wait_for = self.min_interval_seconds - elapsed
            if wait_for > 0:
                self.sleeper(wait_for)
                now = self.clock()
        self._last_call = now


class YouTubeDataAPI:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.rate_limiter = rate_limiter or RateLimiter()

    def search(
        self,
        query: str,
        *,
        max_results: int = DEFAULT_MAX_RESULTS_PER_QUERY,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        self.rate_limiter.wait()
        params = {
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": max(1, min(max_results, 50)),
            "key": self.api_key,
        }
        if channel_id:
            params["channelId"] = channel_id
        response = self.session.get(
            YOUTUBE_SEARCH_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def video_details(self, video_ids: Iterable[str]) -> dict[str, Any]:
        ids = [video_id for video_id in video_ids if video_id]
        if not ids:
            return {"items": []}
        self.rate_limiter.wait()
        response = self.session.get(
            YOUTUBE_VIDEOS_URL,
            params={
                "part": "contentDetails,statistics",
                "id": ",".join(ids[:50]),
                "key": self.api_key,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def ascii_fold(value: Any) -> str:
    text = clean_text(value) or ""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def text_tokens(value: Any, *, keep_stopwords: bool = False) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", ascii_fold(value))
    if keep_stopwords:
        return tokens
    return [token for token in tokens if token not in STOP_TOKENS and len(token) > 1]


def target_match_tokens(name: str) -> list[str]:
    tokens = text_tokens(name)
    if tokens:
        return tokens
    return [
        token
        for token in text_tokens(name, keep_stopwords=True)
        if len(token) > 1 and token not in FALLBACK_STOP_TOKENS
    ]


def dedupe_list(values: Iterable[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def item_video_id(item: dict[str, Any]) -> str | None:
    item_id = item.get("id")
    if isinstance(item_id, dict):
        return clean_text(item_id.get("videoId"))
    return clean_text(item_id)


def item_text(item: dict[str, Any]) -> str:
    snippet = item.get("snippet") or {}
    return " ".join(
        filter(
            None,
            [
                clean_text(snippet.get("title")),
                clean_text(snippet.get("description")),
                clean_text(snippet.get("channelTitle")),
            ],
        )
    )


def has_fencing_signal(text: str) -> bool:
    folded = ascii_fold(text)
    tokens = set(text_tokens(folded, keep_stopwords=True))
    return bool(tokens & FENCING_SIGNAL_TOKENS)


def has_false_positive_signal(text: str) -> bool:
    folded = ascii_fold(text)
    if any(phrase in folded for phrase in FALSE_POSITIVE_PHRASES):
        return True
    tokens = set(text_tokens(folded, keep_stopwords=True))
    return bool(tokens & FALSE_POSITIVE_TOKENS) and "fencing" not in tokens


def official_channel_ids_from_env() -> list[tuple[str, str]]:
    raw = os.environ.get("YOUTUBE_OFFICIAL_CHANNEL_IDS", "")
    channels = []
    for value in raw.split(","):
        channel_id = clean_text(value)
        if channel_id:
            channels.append((channel_id, channel_id))
    return channels


def build_search_targets(
    fencers: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    *,
    include_official_channels: bool = True,
) -> list[RelatedTarget]:
    targets: list[RelatedTarget] = []
    seen_names: set[tuple[str, str]] = set()

    for fencer in fencers:
        fencer_id = clean_text(fencer.get("id"))
        name = clean_text(fencer.get("name"))
        if not fencer_id or not name:
            continue
        key = ("fencer", ascii_fold(name))
        if key in seen_names:
            continue
        seen_names.add(key)
        targets.append(
            RelatedTarget(
                kind="fencer",
                id=fencer_id,
                name=name,
                query=f"fencing {name}",
            )
        )

    for tournament in tournaments:
        tournament_id = clean_text(tournament.get("id"))
        name = clean_text(tournament.get("name"))
        if not tournament_id or not name:
            continue
        key = ("tournament", ascii_fold(name))
        if key in seen_names:
            continue
        seen_names.add(key)
        targets.append(
            RelatedTarget(
                kind="tournament",
                id=tournament_id,
                name=name,
                query=f"fencing {name}",
            )
        )

    if include_official_channels:
        for name, channel_id in OFFICIAL_CHANNELS:
            targets.append(
                RelatedTarget(
                    kind="official_channel",
                    id=None,
                    name=name,
                    query=f"fencing {name}",
                    channel_id=channel_id,
                )
            )
        for name, channel_id in official_channel_ids_from_env():
            targets.append(
                RelatedTarget(
                    kind="official_channel",
                    id=None,
                    name=name,
                    query="fencing",
                    channel_id=channel_id,
                )
            )

    return targets


def target_matches_item(target: RelatedTarget, item: dict[str, Any]) -> bool:
    text = item_text(item)
    if not text or has_false_positive_signal(text):
        return False

    tokens = set(text_tokens(text))
    all_tokens = set(text_tokens(text, keep_stopwords=True))
    target_tokens = target_match_tokens(target.name)

    if target.kind == "official_channel":
        channel = (item.get("snippet") or {}).get("channelTitle")
        channel_tokens = set(text_tokens(channel or ""))
        named_channel_tokens = set(text_tokens(target.name))
        return has_fencing_signal(text) or bool(named_channel_tokens & channel_tokens)

    if not has_fencing_signal(text):
        return False

    if not target_tokens:
        return False

    if target.kind == "fencer":
        return set(target_tokens).issubset(tokens)

    if target.kind == "tournament":
        needed = min(3, len(target_tokens))
        return len(set(target_tokens) & all_tokens) >= needed

    return False


def extract_thumbnail(snippet: dict[str, Any]) -> str | None:
    thumbnails = snippet.get("thumbnails") or {}
    for key in ("maxres", "standard", "high", "medium", "default"):
        url = (thumbnails.get(key) or {}).get("url")
        if url:
            return clean_text(url)
    return None


def parse_iso8601_duration_seconds(duration: str | None) -> int | None:
    if not duration:
        return None
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        duration,
    )
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def detail_by_video_id(details_response: dict[str, Any]) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for item in details_response.get("items") or []:
        video_id = clean_text(item.get("id"))
        if not video_id:
            continue
        duration = clean_text((item.get("contentDetails") or {}).get("duration"))
        details[video_id] = {
            "duration": duration,
            "duration_seconds": parse_iso8601_duration_seconds(duration),
            "statistics": item.get("statistics") or {},
        }
    return details


def build_video_rows(
    items: Iterable[dict[str, Any]],
    *,
    related_targets: list[RelatedTarget],
    detail_by_id: dict[str, dict[str, Any]] | None = None,
    scraped_at: str | None = None,
) -> list[dict[str, Any]]:
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    detail_by_id = detail_by_id or {}
    rows: list[dict[str, Any]] = []

    for item in items:
        video_id = item_video_id(item)
        if not video_id:
            continue

        entity_matches = [
            target
            for target in related_targets
            if target.kind != "official_channel" and target_matches_item(target, item)
        ]
        official_matches = [
            target
            for target in related_targets
            if target.kind == "official_channel" and target_matches_item(target, item)
        ]
        matches = entity_matches or official_matches
        if not matches:
            continue

        snippet = item.get("snippet") or {}
        details = detail_by_id.get(video_id) or {}
        matched_targets = []
        tags = []
        fencer_ids = []
        tournament_ids = []

        for target in matches:
            tag_name = ascii_fold(target.name)
            tags.append(f"{target.kind}:{tag_name}")
            matched = {"kind": target.kind, "id": target.id, "name": target.name}
            if target.kind == "fencer" and target.id:
                fencer_ids.append(target.id)
            elif target.kind == "tournament" and target.id:
                tournament_ids.append(target.id)
            elif target.kind == "official_channel":
                matched.pop("id", None)
            matched_targets.append(matched)

        metadata = {
            "duration_seconds": details.get("duration_seconds"),
            "provider_payload": item,
            "matched_targets": matched_targets,
        }
        if details.get("statistics"):
            metadata["statistics"] = details["statistics"]

        rows.append(
            {
                "provider": PROVIDER,
                "video_id": video_id,
                "title": clean_text(snippet.get("title")) or "",
                "channel": clean_text(snippet.get("channelTitle")),
                "url": YOUTUBE_WATCH_URL.format(video_id=video_id),
                "thumbnail": extract_thumbnail(snippet),
                "published_at": clean_text(snippet.get("publishedAt")),
                "duration": details.get("duration"),
                "related_fencer_ids": dedupe_list(fencer_ids),
                "related_tournament_ids": dedupe_list(tournament_ids),
                "tags": dedupe_list(tags),
                "source": "youtube_data_api",
                "metadata": metadata,
                "scraped_at": scraped_at,
            }
        )

    return rows


def merge_video_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["provider"], row["video_id"])
        if key not in merged:
            merged[key] = row
            continue

        existing = merged[key]
        incoming_has_entities = bool(
            row.get("related_fencer_ids") or row.get("related_tournament_ids")
        )
        existing_has_entities = bool(
            existing.get("related_fencer_ids") or existing.get("related_tournament_ids")
        )
        if not incoming_has_entities and existing_has_entities:
            continue

        existing["related_fencer_ids"] = dedupe_list(
            [*existing.get("related_fencer_ids", []), *row.get("related_fencer_ids", [])]
        )
        existing["related_tournament_ids"] = dedupe_list(
            [
                *existing.get("related_tournament_ids", []),
                *row.get("related_tournament_ids", []),
            ]
        )
        existing["tags"] = dedupe_list([*existing.get("tags", []), *row.get("tags", [])])
        existing_matches = existing.setdefault("metadata", {}).setdefault(
            "matched_targets", []
        )
        existing_match_keys = {
            (match.get("kind"), match.get("id"), match.get("name"))
            for match in existing_matches
        }
        for match in (row.get("metadata") or {}).get("matched_targets", []):
            match_key = (match.get("kind"), match.get("id"), match.get("name"))
            if match_key not in existing_match_keys:
                existing_matches.append(match)
                existing_match_keys.add(match_key)

    return list(merged.values())


def fetch_page(client, table_name: str, columns: str, *, limit: int) -> list[dict[str, Any]]:
    result = (
        client.table(table_name)
        .select(columns)
        .range(0, max(limit - 1, 0))
        .execute()
    )
    return list(result.data or [])[:limit]


def load_known_fencers(client, *, limit: int = DEFAULT_FENCER_LIMIT) -> list[dict[str, Any]]:
    rows = fetch_page(client, "fs_fencers", "id,name,fie_id,country", limit=limit)
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = clean_text(row.get("name"))
        if name:
            deduped.setdefault(ascii_fold(name), row)
    return list(deduped.values())[:limit]


def load_known_tournaments(
    client,
    *,
    limit: int = DEFAULT_TOURNAMENT_LIMIT,
) -> list[dict[str, Any]]:
    rows = fetch_page(
        client,
        "fs_tournaments",
        "id,name,source_id,type,category",
        limit=limit,
    )
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = clean_text(row.get("name"))
        if name:
            deduped.setdefault(ascii_fold(name), row)
    return list(deduped.values())[:limit]


def upsert_video_rows(
    client,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = UPSERT_BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_videos").upsert(batch, on_conflict="provider,video_id").execute()
        written += len(batch)
    return written


def dry_run_summary() -> dict[str, Any]:
    return {
        "provider": PROVIDER,
        "dry_run": True,
        "queries_run": 0,
        "videos_found": 0,
        "rows_written": 0,
        "failed": 0,
        "skipped": 1,
        "reason": "missing YOUTUBE_API_KEY",
    }


def aggregate_videos(
    client=None,
    *,
    api_key: str | None = None,
    youtube_client: Any | None = None,
    fencer_limit: int = DEFAULT_FENCER_LIMIT,
    tournament_limit: int = DEFAULT_TOURNAMENT_LIMIT,
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY,
    include_official_channels: bool = True,
    log_run: bool = True,
    update_state: bool = True,
    scraped_at: str | None = None,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    effective_api_key = api_key if api_key is not None else YOUTUBE_API_KEY

    try:
        if not effective_api_key and youtube_client is None:
            summary = dry_run_summary()
            if update_state:
                set_state(SOURCE, "last_run", {"updated_at": scraped_at, **summary})
            if run_log:
                run_log.complete(
                    written=0,
                    failed=0,
                    skipped=1,
                    metadata=summary,
                )
            return summary

        client = client or get_supabase_client()
        youtube_client = youtube_client or YouTubeDataAPI(effective_api_key or "")
        fencers = load_known_fencers(client, limit=fencer_limit)
        tournaments = load_known_tournaments(client, limit=tournament_limit)
        targets = build_search_targets(
            fencers,
            tournaments,
            include_official_channels=include_official_channels,
        )

        item_by_id: dict[str, dict[str, Any]] = {}
        queries_run = 0
        failed = 0
        for target in targets:
            try:
                response = youtube_client.search(
                    target.query or target.name,
                    max_results=max_results_per_query,
                    channel_id=target.channel_id,
                )
                queries_run += 1
            except Exception as exc:
                failed += 1
                print(f"  YouTube search failed for {target.name!r}: {exc}")
                continue

            for item in response.get("items") or []:
                video_id = item_video_id(item)
                if video_id:
                    item_by_id.setdefault(video_id, item)

        detail_map: dict[str, dict[str, Any]] = {}
        video_ids = list(item_by_id)
        for index in range(0, len(video_ids), 50):
            batch_ids = video_ids[index : index + 50]
            try:
                details = youtube_client.video_details(batch_ids)
                detail_map.update(detail_by_video_id(details))
            except Exception as exc:
                failed += 1
                print(f"  YouTube video detail lookup failed: {exc}")

        rows = merge_video_rows(
            build_video_rows(
                item_by_id.values(),
                related_targets=targets,
                detail_by_id=detail_map,
                scraped_at=scraped_at,
            )
        )
        written = upsert_video_rows(client, rows) if rows else 0
        skipped = max(0, len(item_by_id) - len(rows))
        summary = {
            "provider": PROVIDER,
            "dry_run": False,
            "queries_run": queries_run,
            "videos_found": len(rows),
            "rows_written": written,
            "failed": failed,
            "skipped": skipped,
        }
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": scraped_at, **summary})
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=skipped,
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Video aggregation starting - {datetime.now(timezone.utc).isoformat()}")
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous video aggregation state: {previous_state}")
    summary = aggregate_videos(log_run=True)
    if summary.get("dry_run"):
        print(
            "Video aggregation dry run - "
            f"{summary['reason']}; no provider calls or video rows written"
        )
        return
    print(
        "Video aggregation complete - "
        f"queries={summary['queries_run']}, videos={summary['videos_found']}, "
        f"written={summary['rows_written']}, failed={summary['failed']}, "
        f"skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()

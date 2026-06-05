"""Collect public TikTok fencing video metadata through approved API providers.

Default execution is a no-key dry run using local fixtures. Live collection
requires a configured API/provider endpoint and key; this module does not scrape
login-gated TikTok pages or bypass access controls.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

import requests

from run_logger import ScraperRunLogger
from scraper_state import set_state
from scripts.rate_limiter import RateLimiter


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


SOURCE = "scrape_tiktok_fencing"
TABLE = "fs_tiktok_fencing_videos"
BATCH_SIZE = int(os.environ.get("TIKTOK_FENCING_BATCH_SIZE", "100"))
DEFAULT_LIMIT = int(os.environ.get("TIKTOK_FENCING_TARGET_LIMIT", "25"))
REQUEST_TIMEOUT = int(os.environ.get("TIKTOK_PROVIDER_TIMEOUT", "30"))
CAPTION_SNIPPET_LENGTH = int(os.environ.get("TIKTOK_CAPTION_SNIPPET_LENGTH", "280"))

DEFAULT_TARGETS = [
    "hashtag:fencing",
    "hashtag:fencetok",
    "hashtag:olympicfencing",
    "hashtag:teamusa",
    "handle:fencing_fie",
    "handle:usafencing",
    "handle:britishfencing",
    "handle:leekiefer",
]

DEFAULT_KNOWN_FENCERS: list[dict[str, Any]] = [
    {
        "id": None,
        "name": "Lee Kiefer",
        "country": "USA",
        "metadata": {"social_handles": {"tiktok": "leekiefer"}, "tags": ["teamusa"]},
    },
    {
        "id": None,
        "name": "Italo Santelli",
        "country": "ITA",
        "metadata": {"tags": ["italosantelli"]},
    },
]

FIXTURE_PAYLOAD = {
    "aweme_list": [
        {
            "aweme_id": "7351234567890123456",
            "desc": "Lee Kiefer breaks down a foil touch from Paris. #Fencing #TeamUSA",
            "create_time": 1717000000,
            "author": {"unique_id": "leekiefer", "nickname": "Lee Kiefer"},
            "statistics": {
                "play_count": 12750,
                "digg_count": 830,
                "comment_count": 24,
                "share_count": 51,
            },
            "share_url": "https://www.tiktok.com/@leekiefer/video/7351234567890123456",
        }
    ]
}


class ProviderError(RuntimeError):
    """Raised when a configured TikTok API provider cannot return public data."""


@dataclass(frozen=True)
class Target:
    kind: str
    value: str

    def __post_init__(self) -> None:
        normalized_kind = self.kind.lower().strip()
        if normalized_kind not in {"hashtag", "handle"}:
            raise ValueError("target kind must be 'hashtag' or 'handle'")
        object.__setattr__(self, "kind", normalized_kind)
        object.__setattr__(self, "value", clean_text(self.value).lstrip("#@"))

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.value}"


def clean_text(value: Any) -> str:
    text = str(value or "").replace("\u200b", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_targets(values: Iterable[str | Target] | None = None) -> list[Target]:
    targets: list[Target] = []
    for value in values or DEFAULT_TARGETS:
        if isinstance(value, Target):
            targets.append(value)
            continue
        kind, _, raw = clean_text(value).partition(":")
        if not raw:
            raise ValueError(f"Invalid TikTok target {value!r}; expected kind:value")
        targets.append(Target(kind=kind, value=raw))
    return targets


def _dig(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_value(raw: dict[str, Any], paths: Iterable[tuple[str, ...]]) -> Any:
    for path in paths:
        value = _dig(raw, *path)
        if value not in (None, ""):
            return value
    return None


def _looks_like_video(value: dict[str, Any]) -> bool:
    return any(key in value for key in ("aweme_id", "video_id", "id", "item_id", "share_url", "webVideoUrl"))


def _video_candidates(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        candidates: list[dict[str, Any]] = []
        for item in value:
            candidates.extend(_video_candidates(item))
        return candidates
    if not isinstance(value, dict):
        return []

    candidates = [value] if _looks_like_video(value) else []
    for key in ("aweme_list", "itemList", "items", "videos", "videoList", "data", "results"):
        child = value.get(key)
        if child is not None:
            candidates.extend(_video_candidates(child))
    return candidates


def parse_provider_payload(payload: Any) -> list[dict[str, Any]]:
    """Return video-like objects from common public TikTok provider payload shapes."""

    seen: set[str] = set()
    videos: list[dict[str, Any]] = []
    for item in _video_candidates(payload):
        video_id = extract_video_id(item)
        dedupe_key = video_id or str(id(item))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        videos.append(item)
    return videos


def _explicit_video_id(raw: dict[str, Any]) -> str | None:
    value = _first_value(raw, [("aweme_id",), ("video_id",), ("item_id",), ("id",), ("video", "id")])
    text = clean_text(value)
    return text or None


def _explicit_video_url(raw: dict[str, Any]) -> str | None:
    value = _first_value(
        raw,
        [
            ("share_url",),
            ("webVideoUrl",),
            ("url",),
            ("link",),
            ("video", "webVideoUrl"),
            ("video", "shareUrl"),
        ],
    )
    text = clean_text(value)
    return text if text.startswith("http") else None


def extract_video_id(raw: dict[str, Any]) -> str | None:
    text = _explicit_video_id(raw)
    if text:
        return text
    url = _explicit_video_url(raw)
    match = re.search(r"/video/(\d+)", url or "")
    return match.group(1) if match else None


def extract_video_url(raw: dict[str, Any]) -> str | None:
    text = _explicit_video_url(raw)
    if text:
        return text

    video_id = _explicit_video_id(raw)
    handle = extract_creator_handle(raw)
    if video_id and handle:
        return f"https://www.tiktok.com/@{handle}/video/{video_id}"
    return None


def extract_creator_handle(raw: dict[str, Any]) -> str | None:
    value = _first_value(
        raw,
        [
            ("author", "unique_id"),
            ("author", "uniqueId"),
            ("author", "username"),
            ("authorMeta", "name"),
            ("author_name",),
            ("username",),
            ("creator_handle",),
            ("handle",),
        ],
    )
    text = clean_text(value).lstrip("@")
    return text or None


def extract_creator_name(raw: dict[str, Any]) -> str | None:
    value = _first_value(
        raw,
        [
            ("author", "nickname"),
            ("author", "display_name"),
            ("authorMeta", "nickName"),
            ("authorMeta", "nickname"),
            ("creator",),
            ("author_name",),
        ],
    )
    text = clean_text(value)
    return text or extract_creator_handle(raw)


def extract_caption(raw: dict[str, Any]) -> str:
    value = _first_value(raw, [("desc",), ("description",), ("caption",), ("text",), ("title",)])
    return clean_text(value)


def caption_snippet(caption: str, limit: int = CAPTION_SNIPPET_LENGTH) -> str | None:
    text = clean_text(caption)
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def parse_posted_at(raw: dict[str, Any]) -> str | None:
    value = _first_value(
        raw,
        [
            ("create_time",),
            ("createTime",),
            ("created_at",),
            ("createTimestamp",),
            ("timestamp",),
            ("taken_at",),
        ],
    )
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) or clean_text(value).isdigit():
        seconds = int(value)
        if seconds > 9_999_999_999:
            seconds = seconds // 1000
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()

    text = clean_text(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_metrics(raw: dict[str, Any]) -> dict[str, int]:
    stats = (raw.get("statistics") if isinstance(raw.get("statistics"), dict) else {}) or {}
    stats_alt = (raw.get("stats") if isinstance(raw.get("stats"), dict) else {}) or {}
    metrics = {
        "views": _int_or_none(_first_value(raw, [("play_count",), ("playCount",), ("views",)]))
        or _int_or_none(stats.get("play_count"))
        or _int_or_none(stats_alt.get("playCount")),
        "likes": _int_or_none(_first_value(raw, [("digg_count",), ("diggCount",), ("likes",)]))
        or _int_or_none(stats.get("digg_count"))
        or _int_or_none(stats_alt.get("diggCount")),
        "comments": _int_or_none(_first_value(raw, [("comment_count",), ("commentCount",), ("comments",)]))
        or _int_or_none(stats.get("comment_count"))
        or _int_or_none(stats_alt.get("commentCount")),
        "shares": _int_or_none(_first_value(raw, [("share_count",), ("shareCount",), ("shares",)]))
        or _int_or_none(stats.get("share_count"))
        or _int_or_none(stats_alt.get("shareCount")),
    }
    return {key: value for key, value in metrics.items() if value is not None}


def extract_hashtags(raw: dict[str, Any], caption: str | None = None) -> list[str]:
    tags = [match.group(1) for match in re.finditer(r"#([A-Za-z0-9_]+)", caption or "")]
    for field in ("hashtags", "challenges", "textExtra"):
        values = raw.get(field)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, str):
                tags.append(item.lstrip("#"))
            elif isinstance(item, dict):
                for key in ("name", "title", "hashtagName", "hashtag_name"):
                    text = clean_text(item.get(key)).lstrip("#")
                    if text:
                        tags.append(text)
                        break

    deduped: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = _token(tag)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(tag)
    return deduped


def _token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_text(value).lower())


def _metadata_tokens(metadata: Any) -> set[str]:
    tokens: set[str] = set()
    if not isinstance(metadata, dict):
        return tokens
    for key in ("tiktok", "tiktok_handle", "handle"):
        token = _token(metadata.get(key))
        if token:
            tokens.add(token)
    social_handles = metadata.get("social_handles")
    if isinstance(social_handles, dict):
        token = _token(social_handles.get("tiktok"))
        if token:
            tokens.add(token)
    tags = metadata.get("tags")
    if isinstance(tags, list):
        tokens.update(_token(tag) for tag in tags if _token(tag))
    return tokens


def match_related_fencers(
    caption: str,
    *,
    hashtags: list[str] | None,
    known_fencers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    text = clean_text(caption)
    lower_text = text.lower()
    handle_tokens = {_token(match.group(1)) for match in re.finditer(r"@([A-Za-z0-9_.]+)", text)}
    hashtag_tokens = {_token(tag) for tag in hashtags or []}
    compact_text = _token(text)

    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fencer in known_fencers:
        name = clean_text(fencer.get("name"))
        country = clean_text(fencer.get("country")) or None
        fencer_id = clean_text(fencer.get("id")) or None
        match_key = fencer_id or name.lower()
        if not name or match_key in seen:
            continue

        name_pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(name).replace('\\ ', r'\\s+')}(?![A-Za-z0-9])", re.I)
        name_tokens = {_token(name)}
        metadata_tokens = _metadata_tokens(fencer.get("metadata"))
        token_match = bool((name_tokens | metadata_tokens) & (handle_tokens | hashtag_tokens))
        compact_match = any(token and token in compact_text for token in metadata_tokens)
        if name_pattern.search(lower_text) or token_match or compact_match:
            matches.append({"id": fencer_id, "name": name, "country": country})
            seen.add(match_key)
    return matches


def build_video_row(
    raw: dict[str, Any],
    *,
    target: Target,
    known_fencers: list[dict[str, Any]],
    provider_name: str,
) -> dict[str, Any] | None:
    video_id = extract_video_id(raw)
    url = extract_video_url(raw)
    if not video_id or not url:
        return None

    caption = extract_caption(raw)
    hashtags = extract_hashtags(raw, caption)
    related_fencers = match_related_fencers(caption, hashtags=hashtags, known_fencers=known_fencers)
    return {
        "platform": "tiktok",
        "video_id": video_id,
        "url": url,
        "creator": extract_creator_name(raw),
        "creator_handle": extract_creator_handle(raw),
        "caption_snippet": caption_snippet(caption),
        "posted_at": parse_posted_at(raw),
        "metrics": extract_metrics(raw),
        "related_fencers": related_fencers,
        "targets": [target.key],
        "source": "tiktok_provider",
        "provider": provider_name,
        "metadata": {
            "target": {"kind": target.kind, "value": target.value},
            "hashtags": hashtags,
            "caption_length": len(caption),
        },
    }


def _merge_json_list(existing: list[Any], incoming: list[Any], key: str | None = None) -> list[Any]:
    merged: list[Any] = []
    seen: set[str] = set()
    for item in existing + incoming:
        if key and isinstance(item, dict):
            marker = clean_text(item.get(key)) or repr(item)
        else:
            marker = clean_text(item) or repr(item)
        if marker in seen:
            continue
        seen.add(marker)
        merged.append(item)
    return merged


def dedupe_video_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        video_id = clean_text(row.get("video_id"))
        platform = clean_text(row.get("platform")) or "tiktok"
        if not video_id:
            continue
        key = (platform, video_id)
        existing = chosen.get(key)
        if not existing:
            chosen[key] = row
            continue
        existing["targets"] = _merge_json_list(existing.get("targets", []), row.get("targets", []))
        existing["related_fencers"] = _merge_json_list(
            existing.get("related_fencers", []),
            row.get("related_fencers", []),
            key="id",
        )
        existing["metrics"] = {**existing.get("metrics", {}), **row.get("metrics", {})}
    return list(chosen.values())


def upsert_video_rows(client: Any, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    clean_rows = dedupe_video_rows(rows)
    written = 0
    for index in range(0, len(clean_rows), batch_size):
        batch = clean_rows[index : index + batch_size]
        client.table(TABLE).upsert(batch, on_conflict="platform,video_id").execute()
        written += len(batch)
    return written


def load_known_fencers(client: Any | None, *, limit: int = 1000) -> list[dict[str, Any]]:
    if client is None:
        return DEFAULT_KNOWN_FENCERS
    try:
        rows = client.table("fs_fencers").select("id,name,country,metadata").limit(limit).execute().data or []
        return rows or DEFAULT_KNOWN_FENCERS
    except Exception as exc:
        print(f"  Could not load fencer match context: {exc}")
        return DEFAULT_KNOWN_FENCERS


class FixtureProvider:
    name = "fixture"

    def fetch_target(self, target: Target, limit: int = DEFAULT_LIMIT) -> Any:
        return FIXTURE_PAYLOAD


class TikTokAPIProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        name: str = "configured_provider",
        session: requests.Session | None = None,
        rate_limiter: RateLimiter | None = None,
        timeout: int = REQUEST_TIMEOUT,
    ):
        if not base_url or not api_key:
            raise ValueError("base_url and api_key are required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.name = name
        self.session = session or requests.Session()
        self.rate_limiter = rate_limiter or RateLimiter(default_rps=0.5, jitter=0.2, backoff=5.0)
        self.timeout = timeout
        self.domain = urlparse(self.base_url).netloc

    def fetch_target(self, target: Target, limit: int = DEFAULT_LIMIT) -> Any:
        self.rate_limiter.wait(self.domain)
        params = {"type": target.kind, "q": target.value, "limit": limit}
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,
        }
        try:
            response = self.session.get(self.base_url, params=params, headers=headers, timeout=self.timeout)
        except Exception as exc:
            self.rate_limiter.record_failure(self.domain)
            raise ProviderError(str(exc)) from exc

        if response.status_code != 200:
            self.rate_limiter.record_failure(self.domain)
            detail = clean_text(getattr(response, "text", ""))[:200]
            raise ProviderError(f"HTTP {response.status_code}: {detail}")

        self.rate_limiter.record_success(self.domain)
        try:
            return response.json()
        except Exception as exc:
            raise ProviderError(f"Invalid provider JSON: {exc}") from exc


def provider_from_env(env: dict[str, str] | os._Environ[str] | None = None) -> TikTokAPIProvider | None:
    env = env or os.environ
    base_url = clean_text(env.get("TIKTOK_PROVIDER_API_URL"))
    api_key = clean_text(env.get("TIKTOK_PROVIDER_API_KEY"))
    if not base_url or not api_key:
        return None
    return TikTokAPIProvider(
        base_url=base_url,
        api_key=api_key,
        name=clean_text(env.get("TIKTOK_PROVIDER_NAME")) or "configured_provider",
    )


def collect_tiktok_fencing(
    *,
    client: Any | None = None,
    provider: Any | None = None,
    targets: Iterable[str | Target] | None = None,
    env: dict[str, str] | os._Environ[str] | None = None,
    dry_run: bool | None = None,
    logger_factory: Any = ScraperRunLogger,
    update_state: bool = True,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    configured_provider = provider or provider_from_env(env)
    if configured_provider is None:
        configured_provider = FixtureProvider()
        if dry_run is None:
            dry_run = True
    if dry_run is None:
        dry_run = client is None

    run_log = logger_factory(SOURCE).start() if logger_factory else None
    selected_targets = parse_targets(targets)
    known_fencers = load_known_fencers(client)
    rows: list[dict[str, Any]] = []
    failed = skipped = 0
    provider_errors: list[str] = []

    try:
        for target in selected_targets:
            try:
                payload = configured_provider.fetch_target(target, limit=limit)
                videos = parse_provider_payload(payload)
                if not videos:
                    skipped += 1
                    continue
                for video in videos:
                    row = build_video_row(
                        video,
                        target=target,
                        known_fencers=known_fencers,
                        provider_name=configured_provider.name,
                    )
                    if row:
                        rows.append(row)
                    else:
                        skipped += 1
            except ProviderError as exc:
                failed += 1
                provider_errors.append(f"{target.key}: {exc}")
                print(f"  TikTok provider error for {target.key}: {exc}")
            except Exception as exc:
                failed += 1
                provider_errors.append(f"{target.key}: {exc}")
                print(f"  TikTok target failed for {target.key}: {exc}")

        deduped_rows = dedupe_video_rows(rows)
        written = 0 if dry_run or client is None else upsert_video_rows(client, deduped_rows)
        summary = {
            "provider": configured_provider.name,
            "dry_run": bool(dry_run),
            "targets": len(selected_targets),
            "videos": len(deduped_rows),
            "would_write": len(deduped_rows) if dry_run or client is None else 0,
            "written": written,
            "skipped": skipped,
            "failed": failed,
            "provider_errors": provider_errors,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {"updated_at": datetime.now(timezone.utc).isoformat(), **summary},
            )
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    summary = collect_tiktok_fencing(client=supabase)
    print(
        "TikTok fencing scraper complete - "
        f"provider={summary['provider']}, dry_run={summary['dry_run']}, "
        f"videos={summary['videos']}, written={summary['written']}, "
        f"failed={summary['failed']}, skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()

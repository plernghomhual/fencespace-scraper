from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse

from run_logger import ScraperRunLogger
from scraper_state import set_state

try:
    from supabase import create_client
except Exception:  # pragma: no cover - import errors surface when a client is required.
    create_client = None


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "compute_social_leaderboard"
PAGE_SIZE = 1000
BATCH_SIZE = 200
STALE_AFTER_DAYS = 30
SOCIAL_SELECT = "id,fencer_id,platform,handle,url,source,verified,metadata,created_at"
LEADERBOARD_CONFLICT = "platform,normalized_handle"
KNOWN_PLATFORMS = {"instagram", "twitter", "youtube", "tiktok", "facebook", "threads", "other"}
PLATFORM_ALIASES = {
    "ig": "instagram",
    "insta": "instagram",
    "instagram": "instagram",
    "x": "twitter",
    "twitter": "twitter",
    "twitterx": "twitter",
    "youtube": "youtube",
    "yt": "youtube",
    "tiktok": "tiktok",
    "facebook": "facebook",
    "fb": "facebook",
    "threads": "threads",
    "other": "other",
}
IDENTITY_SELECTS = (
    "canonical_id,fs_fencer_row_ids",
    "id,canonical_id,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
    "canonical_id,fencer_ids",
)
COUNT_KEYS = ("follower_count", "followers", "followers_count", "followerCount", "subscriber_count", "subscribers")
MENTION_KEYS = ("mention_count", "mentions", "mentions_count", "mentionCount", "social_mentions")
COLLECTED_AT_KEYS = ("collected_at", "collection_date", "metrics_collected_at", "follower_collected_at", "snapshot_at")
NESTED_METADATA_KEYS = ("metrics", "public_metrics", "social_metrics", "snapshot", "account")
PRIVATE_STATUS_VALUES = {"private", "protected", "missing", "not_found", "deleted", "suspended", "unavailable"}

Provider = Callable[[dict[str, Any]], dict[str, Any] | None]


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    if create_client is None:
        raise RuntimeError("supabase package is required.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def ensure_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = clean_text(value)
    return bool(text and text.casefold() in {"1", "true", "yes", "y", "public", "verified"})


def platform_from_url(url: Any) -> str | None:
    parsed = urlparse(clean_text(url) or "")
    host = parsed.netloc.casefold().removeprefix("www.")
    if "instagram.com" in host:
        return "instagram"
    if host in {"x.com", "twitter.com", "mobile.twitter.com"}:
        return "twitter"
    if "youtube.com" in host or host == "youtu.be":
        return "youtube"
    if "tiktok.com" in host:
        return "tiktok"
    if "facebook.com" in host or host == "fb.com":
        return "facebook"
    if "threads.net" in host:
        return "threads"
    return None


def normalize_platform(value: Any, url: Any = None) -> str | None:
    text = clean_text(value)
    if text:
        key = re.sub(r"[^a-z0-9]+", "", text.casefold())
        platform = PLATFORM_ALIASES.get(key)
        if platform:
            return platform
    return platform_from_url(url)


def handle_from_url(platform: str, url: Any) -> str | None:
    parsed = urlparse(clean_text(url) or "")
    segments = [unquote(part) for part in parsed.path.split("/") if part]
    if not segments:
        return None
    if platform == "youtube" and segments[0].casefold() in {"channel", "user", "c"} and len(segments) > 1:
        return clean_text(segments[1].lstrip("@"))
    return clean_text(segments[0].lstrip("@"))


def normalize_handle(platform: str, handle: Any, url: Any = None) -> tuple[str | None, str | None]:
    display = clean_text(handle)
    if display and display.startswith(("http://", "https://")):
        display = handle_from_url(platform, display)
    if not display:
        display = handle_from_url(platform, url)
    if not display:
        return None, None

    display = display.strip().strip("/").lstrip("@")
    if "?" in display:
        display = display.split("?", 1)[0]
    display = display.strip()
    if not display:
        return None, None
    return display, display.casefold()


def parse_identity_members(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if clean_text(item)})


def build_identity_map(identity_rows: list[dict[str, Any]]) -> dict[str, str]:
    identity_map: dict[str, str] = {}
    for row in identity_rows:
        members = parse_identity_members(row.get("fs_fencer_row_ids") or row.get("fencer_ids"))
        canonical = clean_text(row.get("canonical_id"))
        row_id = clean_text(row.get("id"))
        if not canonical and row_id and row_id in members:
            canonical = row_id
        if not canonical and members:
            canonical = members[0]
        if not canonical:
            continue
        identity_map[canonical] = canonical
        for member in members:
            identity_map[member] = canonical
    return identity_map


def canonical_fencer_id(fencer_id: Any, identity_map: dict[str, str] | None = None) -> str | None:
    text = clean_text(fencer_id)
    if not text:
        return None
    return identity_map.get(text, text) if identity_map else text


def iter_metadata_candidates(row: dict[str, Any], metadata: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [row, metadata]
    for key in NESTED_METADATA_KEYS:
        nested = metadata.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    return candidates


def first_value(row: dict[str, Any], metadata: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for candidate in iter_metadata_candidates(row, metadata):
        for key in keys:
            if key in candidate and candidate.get(key) not in (None, ""):
                return candidate.get(key)
    return None


def coerce_count(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None

    text = clean_text(value)
    if not text:
        return None
    normalized = text.casefold().replace(",", "")
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*([kmb])?", normalized)
    if not match:
        return None
    number = float(match.group(1))
    if number < 0:
        return None
    multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(match.group(2), 1)
    return int(number * multiplier)


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    else:
        text = clean_text(value)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def is_publicly_verified(row: dict[str, Any], metadata: dict[str, Any]) -> bool:
    status = clean_text(metadata.get("account_status"))
    return bool(
        normalize_bool(metadata.get("publicly_verified"))
        or normalize_bool(metadata.get("public_verified"))
        or (status and status.casefold() == "public")
    )


def account_is_excluded(row: dict[str, Any], metadata: dict[str, Any]) -> bool:
    if is_publicly_verified(row, metadata):
        return False
    for key in ("private", "is_private", "account_private", "protected"):
        if normalize_bool(metadata.get(key)):
            return True
    for key in ("missing", "is_missing", "account_missing", "not_found"):
        if normalize_bool(metadata.get(key)):
            return True
    for key in ("status", "account_status", "privacy_status"):
        text = clean_text(metadata.get(key))
        if text and text.casefold() in PRIVATE_STATUS_VALUES:
            return True
    return False


def source_key(row: dict[str, Any], metadata: dict[str, Any]) -> str:
    for key in ("metric_source", "mention_source", "source_url", "profile_url", "provider"):
        value = clean_text(metadata.get(key))
        if value:
            return value
    return clean_text(row.get("source")) or "unknown"


def observation_preference(observation: dict[str, Any]) -> tuple[int, datetime, int, int, str]:
    collected_at = observation.get("collected_at_dt")
    return (
        1 if collected_at else 0,
        collected_at or datetime.min.replace(tzinfo=UTC),
        1 if observation.get("verified") else 0,
        observation.get("follower_count") or -1,
        observation.get("handle") or "",
    )


def merge_provider_metrics(
    row: dict[str, Any],
    platform: str,
    providers: dict[str, Provider] | None,
) -> tuple[dict[str, Any], bool]:
    metadata = ensure_metadata(row.get("metadata"))
    follower_count = coerce_count(first_value(row, metadata, COUNT_KEYS))
    mention_count = coerce_count(first_value(row, metadata, MENTION_KEYS))
    if follower_count is not None or mention_count is not None:
        return row, False

    provider = (providers or {}).get(platform)
    if not provider:
        return row, True

    provider_data = provider(row) or {}
    merged = dict(row)
    merged_metadata = ensure_metadata(merged.get("metadata"))
    merged_metadata.update(provider_data)
    merged["metadata"] = merged_metadata
    return merged, False


def social_observations(
    social_rows: list[dict[str, Any]],
    *,
    identity_map: dict[str, str] | None = None,
    providers: dict[str, Provider] | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    observations: list[dict[str, Any]] = []
    skipped = 0
    missing_provider = 0

    for raw_row in social_rows:
        platform = normalize_platform(raw_row.get("platform"), raw_row.get("url"))
        if not platform or platform not in KNOWN_PLATFORMS:
            skipped += 1
            continue

        row, needed_provider = merge_provider_metrics(raw_row, platform, providers)
        if needed_provider:
            missing_provider += 1
            skipped += 1
            continue

        metadata = ensure_metadata(row.get("metadata"))
        if account_is_excluded(row, metadata):
            skipped += 1
            continue

        display_handle, normalized_handle = normalize_handle(platform, row.get("handle"), row.get("url"))
        fencer_id = canonical_fencer_id(row.get("fencer_id"), identity_map)
        if not fencer_id or not display_handle or not normalized_handle:
            skipped += 1
            continue

        follower_count = coerce_count(first_value(row, metadata, COUNT_KEYS))
        mention_count = coerce_count(first_value(row, metadata, MENTION_KEYS))
        if follower_count is None and mention_count is None:
            skipped += 1
            continue

        collected_at = parse_datetime(first_value(row, metadata, COLLECTED_AT_KEYS) or row.get("created_at"))
        observations.append(
            {
                "fencer_id": fencer_id,
                "platform": platform,
                "source_platform": platform,
                "handle": display_handle,
                "normalized_handle": normalized_handle,
                "url": clean_text(row.get("url")),
                "source": clean_text(row.get("source")) or "unknown",
                "source_key": source_key(row, metadata),
                "verified": bool(row.get("verified") or is_publicly_verified(row, metadata)),
                "follower_count": follower_count,
                "mention_count": mention_count or 0,
                "collected_at_dt": collected_at,
                "collected_at": collected_at.isoformat() if collected_at else None,
            }
        )

    return observations, skipped, missing_provider


def stale_fields(
    collected_at: datetime | None,
    computed_at: datetime,
    *,
    stale_after_days: int,
    has_follower_count: bool,
) -> tuple[bool, str | None, int | None]:
    if not has_follower_count:
        return False, None, None
    if collected_at is None:
        return True, "missing_collection_date", None

    days_since = max(0, (computed_at.date() - collected_at.date()).days)
    if days_since > stale_after_days:
        return True, f"follower_count_older_than_{stale_after_days}_days", days_since
    return False, None, days_since


def aggregate_observations(
    observations: list[dict[str, Any]],
    *,
    computed_at: str | None = None,
    stale_after_days: int = STALE_AFTER_DAYS,
) -> list[dict[str, Any]]:
    computed_at_dt = parse_datetime(computed_at) or datetime.now(UTC)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for observation in observations:
        grouped.setdefault((observation["platform"], observation["normalized_handle"]), []).append(observation)

    rows: list[dict[str, Any]] = []
    for (_platform, _handle), group in sorted(grouped.items()):
        by_source: dict[str, dict[str, Any]] = {}
        for observation in group:
            key = observation["source_key"]
            existing = by_source.get(key)
            if existing is None or observation_preference(observation) > observation_preference(existing):
                by_source[key] = observation

        unique_observations = list(by_source.values())
        follower_candidates = [item for item in unique_observations if item.get("follower_count") is not None]
        follower_observation = max(follower_candidates, key=observation_preference) if follower_candidates else None
        primary = follower_observation or max(unique_observations, key=observation_preference)
        mention_count = sum(item.get("mention_count") or 0 for item in unique_observations)
        follower_count = follower_observation.get("follower_count") if follower_observation else None
        collected_at = follower_observation.get("collected_at_dt") if follower_observation else primary.get("collected_at_dt")
        is_stale, stale_reason, days_since = stale_fields(
            collected_at,
            computed_at_dt,
            stale_after_days=stale_after_days,
            has_follower_count=follower_count is not None,
        )
        sources = sorted({item["source"] for item in unique_observations if item.get("source")})

        rows.append(
            {
                "platform": primary["platform"],
                "source_platform": primary["source_platform"],
                "normalized_handle": primary["normalized_handle"],
                "handle": primary["handle"],
                "fencer_id": primary["fencer_id"],
                "url": primary.get("url"),
                "source": ",".join(sources) if sources else None,
                "sources": sources,
                "follower_count": follower_count,
                "mention_count": mention_count,
                "follower_rank": None,
                "mention_rank": None,
                "collected_at": collected_at.isoformat() if collected_at else None,
                "days_since_collected": days_since,
                "is_stale": is_stale,
                "stale_reason": stale_reason,
                "computed_at": computed_at_dt.isoformat(),
                "metadata": {
                    "source_observation_count": len(unique_observations),
                    "verified": any(item.get("verified") for item in unique_observations),
                },
            }
        )

    apply_ranks(rows)
    return rows


def apply_ranks(rows: list[dict[str, Any]]) -> None:
    follower_ranked = [row for row in rows if row.get("follower_count") is not None]
    follower_ranked.sort(
        key=lambda row: (
            -(row["follower_count"] or 0),
            -(row.get("mention_count") or 0),
            1 if row.get("is_stale") else 0,
            row.get("normalized_handle") or "",
        )
    )
    for rank, row in enumerate(follower_ranked, start=1):
        row["follower_rank"] = rank

    mention_ranked = [row for row in rows if (row.get("mention_count") or 0) > 0]
    mention_ranked.sort(
        key=lambda row: (
            -(row.get("mention_count") or 0),
            -(row.get("follower_count") or 0),
            row.get("normalized_handle") or "",
        )
    )
    for rank, row in enumerate(mention_ranked, start=1):
        row["mention_rank"] = rank


def build_leaderboard_rows(
    social_rows: list[dict[str, Any]],
    *,
    identity_map: dict[str, str] | None = None,
    providers: dict[str, Provider] | None = None,
    computed_at: str | None = None,
    stale_after_days: int = STALE_AFTER_DAYS,
) -> tuple[list[dict[str, Any]], int]:
    observations, skipped, _missing_provider = social_observations(
        social_rows,
        identity_map=identity_map,
        providers=providers,
    )
    return aggregate_observations(
        observations,
        computed_at=computed_at,
        stale_after_days=stale_after_days,
    ), skipped


def fetch_all(client, table: str, columns: str, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def load_identity_map(client, page_size: int = PAGE_SIZE) -> tuple[dict[str, str], int]:
    last_error: Exception | None = None
    for columns in IDENTITY_SELECTS:
        try:
            rows = fetch_all(client, "fs_fencer_identities", columns, page_size=page_size)
            return build_identity_map(rows), len(rows)
        except Exception as exc:
            last_error = exc
    print(f"Identity table unavailable; using raw fs_fencer_social_media.fencer_id grouping: {last_error}")
    return {}, 0


def _probe_leaderboard_table(client) -> None:
    client.table("fs_fencer_social_leaderboard").select("platform").limit(0).execute()


def upsert_leaderboard_rows(client, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table("fs_fencer_social_leaderboard").upsert(
                batch,
                on_conflict=LEADERBOARD_CONFLICT,
            ).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_fencer_social_leaderboard upsert batch {index // batch_size} failed: {exc}")
    return written, failed


def compute_social_leaderboard(
    *,
    client=None,
    providers: dict[str, Provider] | None = None,
    computed_at: str | None = None,
    stale_after_days: int = STALE_AFTER_DAYS,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    try:
        _probe_leaderboard_table(client)
        social_rows = fetch_all(client, "fs_fencer_social_media", SOCIAL_SELECT, page_size=page_size)
        identity_map, identity_rows = load_identity_map(client, page_size=page_size)
        observations, skipped, missing_provider = social_observations(
            social_rows,
            identity_map=identity_map,
            providers=providers,
        )
        rows = aggregate_observations(
            observations,
            computed_at=computed_at,
            stale_after_days=stale_after_days,
        )
        written, failed = upsert_leaderboard_rows(client, rows) if rows else (0, 0)

        if update_state:
            set_state(SOURCE, "last_run", datetime.now(UTC).isoformat())
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=skipped,
                metadata={
                    "read": len(social_rows),
                    "identity_rows": identity_rows,
                    "missing_provider": missing_provider,
                },
            )
        return {
            "read": len(social_rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "identity_rows": identity_rows,
            "missing_provider": missing_provider,
        }
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Social leaderboard computation starting - {datetime.now(UTC).isoformat()}")
    result = compute_social_leaderboard()
    print(
        "Social leaderboard computation complete - "
        f"read={result['read']}, written={result['written']}, "
        f"failed={result['failed']}, skipped={result['skipped']}, "
        f"missing_provider={result['missing_provider']}"
    )


if __name__ == "__main__":
    main()

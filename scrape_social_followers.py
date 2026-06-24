import os
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


SOURCE = "scrape_social_followers"
WIKIDATA_SOURCE = "wikidata"
SPARQL_URL = "https://query.wikidata.org/sparql"
REQUEST_DELAY = float(os.environ.get("SOCIAL_FOLLOWERS_REQUEST_DELAY", "1.0"))
PAGE_SIZE = int(os.environ.get("SOCIAL_FOLLOWERS_PAGE_SIZE", "1000"))

HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; plerngh@gmail.com)",
}

MASTODON_HEADERS = {
    "Accept": "application/json",
    "User-Agent": HEADERS["User-Agent"],
}

SOCIAL_PROPERTIES = {
    "twitter": "P2002",
    "instagram": "P2003",
    "facebook": "P2013",
    "youtube": "P2397",
    "tiktok": "P7085",
    "mastodon": "P4033",
}

BLOCKED_PLATFORM_DETAILS = {
    "instagram": "Follower counts require login, scraping, or restricted platform APIs.",
    "twitter": "Follower counts require login or paid/restricted platform APIs.",
    "facebook": "Follower counts require login or restricted platform APIs.",
    "youtube": "Follower counts require an API key; no key is configured for this scraper.",
    "tiktok": "Follower counts require login, scraping, or restricted platform APIs.",
    "threads": "Follower counts require login or restricted platform APIs.",
}

LOGIN_OR_PRIVATE_MARKERS = (
    "/accounts/login",
    "/i/flow/login",
    "/login",
    "/signin",
    "/sign-in",
    "/private",
)

SPARQL_QUERY = """
SELECT ?athlete ?athleteLabel ?fie_id ?twitter ?instagram ?facebook ?youtube ?tiktok ?mastodon WHERE {{
  ?athlete wdt:P641 wd:Q12100 .
  OPTIONAL {{ ?athlete wdt:P2423 ?fie_id . }}
  OPTIONAL {{ ?athlete wdt:{twitter} ?twitter . }}
  OPTIONAL {{ ?athlete wdt:{instagram} ?instagram . }}
  OPTIONAL {{ ?athlete wdt:{facebook} ?facebook . }}
  OPTIONAL {{ ?athlete wdt:{youtube} ?youtube . }}
  OPTIONAL {{ ?athlete wdt:{tiktok} ?tiktok . }}
  OPTIONAL {{ ?athlete wdt:{mastodon} ?mastodon . }}
  FILTER(
    BOUND(?twitter) || BOUND(?instagram) || BOUND(?facebook) ||
    BOUND(?youtube) || BOUND(?tiktok) || BOUND(?mastodon)
  )
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
    ?athlete rdfs:label ?athleteLabel .
  }}
}}
LIMIT {limit}
OFFSET {offset}
"""


@dataclass
class SocialProfileCandidate:
    platform: str
    handle: str
    url: str
    source: str = WIKIDATA_SOURCE
    wikidata_id: str | None = None
    fencer_name: str | None = None
    fie_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourcePolicy:
    allowed: bool
    reason: str


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _binding_value(binding: dict[str, Any], key: str) -> str | None:
    return _clean_text((binding.get(key) or {}).get("value"))


def _wikidata_id(value: str | None) -> str | None:
    if not value:
        return None
    return value.rstrip("/").split("/")[-1] or None


def _is_login_or_private_url(raw: str) -> bool:
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return False
    path = parsed.path.lower()
    query = parsed.query.lower()
    return any(marker in path for marker in LOGIN_OR_PRIVATE_MARKERS) or "login" in query


def _strip_common_handle_noise(handle: str) -> str:
    handle = handle.strip()
    handle = handle.split("?", 1)[0].split("#", 1)[0].strip("/")
    if handle.startswith("@"):
        handle = handle[1:]
    return handle.strip().lower()


def _handle_from_url(raw: str) -> str | None:
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return None
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return None
    first = path_parts[0]
    if first in {"i", "intent", "search", "share", "explore", "accounts"}:
        return None
    return _strip_common_handle_noise(first)


def _normalize_standard_handle(raw: str) -> str | None:
    if raw.startswith(("http://", "https://")):
        return _handle_from_url(raw)
    return _strip_common_handle_noise(raw)


def _normalize_mastodon(raw: str) -> tuple[str, str] | None:
    raw = raw.strip()
    if raw.startswith(("http://", "https://")):
        parsed = urlparse(raw)
        if not parsed.netloc:
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return None
        username = parts[0][1:] if parts[0].startswith("@") else parts[0]
        username = _strip_common_handle_noise(username)
        instance = parsed.netloc.lower()
        if not username or not instance:
            return None
        return f"{username}@{instance}", f"https://{instance}/@{username}"

    address = raw[1:] if raw.startswith("@") else raw
    if "@" not in address:
        return None
    username, instance = address.split("@", 1)
    username = _strip_common_handle_noise(username)
    instance = instance.strip().lower().strip("/")
    if not username or not instance or "." not in instance:
        return None
    return f"{username}@{instance}", f"https://{instance}/@{username}"


def normalize_social_profile(platform: str, raw: str | None) -> SocialProfileCandidate | None:
    platform = (platform or "").strip().lower()
    raw = _clean_text(raw)
    if not platform or not raw:
        return None
    if raw.startswith(("http://", "https://")) and _is_login_or_private_url(raw):
        return None

    if platform == "mastodon":
        normalized = _normalize_mastodon(raw)
        if not normalized:
            return None
        handle, url = normalized
        return SocialProfileCandidate(platform=platform, handle=handle, url=url)

    handle_std = _normalize_standard_handle(raw)
    if not handle_std:
        return None
    handle = handle_std

    if platform == "instagram":
        url = f"https://www.instagram.com/{handle}/"
    elif platform == "twitter":
        url = f"https://x.com/{handle}"
    elif platform == "facebook":
        url = f"https://www.facebook.com/{handle}"
    elif platform == "youtube":
        url = (
            f"https://www.youtube.com/channel/{handle}"
            if re.fullmatch(r"UC[\w-]{20,}", handle, flags=re.IGNORECASE)
            else f"https://www.youtube.com/@{handle}"
        )
    elif platform == "tiktok":
        url = f"https://www.tiktok.com/@{handle}"
    else:
        return None

    return SocialProfileCandidate(platform=platform, handle=handle, url=url)


def parse_wikidata_social_binding(binding: dict[str, Any]) -> list[SocialProfileCandidate]:
    wikidata_id = _wikidata_id(_binding_value(binding, "athlete"))
    fencer_name = _binding_value(binding, "athleteLabel")
    fie_id = _binding_value(binding, "fie_id")
    profiles: list[SocialProfileCandidate] = []

    for platform in SOCIAL_PROPERTIES:
        raw = _binding_value(binding, platform)
        profile = normalize_social_profile(platform, raw)
        if not profile:
            continue
        profile.wikidata_id = wikidata_id
        profile.fencer_name = fencer_name
        profile.fie_id = fie_id
        profile.source = WIKIDATA_SOURCE
        profile.metadata = {"wikidata_id": wikidata_id, "fie_id": fie_id}
        profiles.append(profile)

    return profiles


def source_policy_for_profile(profile: SocialProfileCandidate | None) -> SourcePolicy:
    if profile is None:
        return SourcePolicy(False, "invalid_or_login_only_profile")
    if profile.platform == "mastodon":
        parsed = urlparse(profile.url)
        if parsed.scheme == "https" and parsed.netloc and "/@" in parsed.path:
            return SourcePolicy(True, "public_federated_api")
        return SourcePolicy(False, "invalid_mastodon_profile")
    if profile.platform in BLOCKED_PLATFORM_DETAILS:
        return SourcePolicy(False, "blocked_login_or_restricted_api")
    return SourcePolicy(False, "unsupported_platform")


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _metadata_without_none(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if value is not None}


def parse_mastodon_account_snapshot(
    profile: SocialProfileCandidate,
    account: dict[str, Any],
    *,
    collected_at: datetime,
    fencer_identity_id: str | None = None,
    fencer_id: str | None = None,
) -> dict[str, Any]:
    identity_key = fencer_identity_id or fencer_id
    if not identity_key:
        raise ValueError("fencer_identity_id or fencer_id is required")

    collected_at = _utc_datetime(collected_at)
    date_bucket = collected_at.date().isoformat()
    follower_count = _optional_nonnegative_int(account.get("followers_count"))
    following_count = _optional_nonnegative_int(account.get("following_count"))
    counts_available = follower_count is not None or following_count is not None
    account_url = _clean_text(account.get("url")) or profile.url

    return {
        "snapshot_key": f"{identity_key}:{profile.platform}:{profile.handle}:{date_bucket}",
        "fencer_identity_id": fencer_identity_id,
        "fencer_id": fencer_id,
        "platform": profile.platform,
        "handle": profile.handle,
        "url": account_url,
        "follower_count": follower_count,
        "following_count": following_count,
        "source": "mastodon_api",
        "collected_at": collected_at.isoformat(),
        "date_bucket": date_bucket,
        "metadata": _metadata_without_none(
            {
                "wikidata_id": profile.wikidata_id,
                "fie_id": profile.fie_id,
                "fencer_name": profile.fencer_name,
                "source": profile.source,
                "source_profile_url": profile.url,
                "account_id": account.get("id"),
                "acct": account.get("acct"),
                "display_name": account.get("display_name"),
                "locked": account.get("locked"),
                "counts_available": counts_available,
            }
        ),
    }


def _mastodon_lookup(profile: SocialProfileCandidate) -> tuple[str, str] | None:
    parsed = urlparse(profile.url)
    if not parsed.netloc:
        return None
    username = profile.handle.split("@", 1)[0]
    if not username:
        return None
    return f"https://{parsed.netloc}/api/v1/accounts/lookup", username


def collect_profile_snapshot(
    profile: SocialProfileCandidate,
    *,
    session: requests.Session,
    collected_at: datetime,
    fencer_identity_id: str | None = None,
    fencer_id: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    policy = source_policy_for_profile(profile)
    if not policy.allowed:
        return None, {
            "platform": profile.platform if profile else None,
            "url": profile.url if profile else None,
            "reason": policy.reason,
            "evidence": BLOCKED_PLATFORM_DETAILS.get(profile.platform if profile else "", policy.reason),
        }

    lookup = _mastodon_lookup(profile)
    if not lookup:
        return None, {"platform": profile.platform, "url": profile.url, "reason": "invalid_mastodon_profile"}

    lookup_url, username = lookup
    try:
        response = session.get(
            lookup_url,
            params={"acct": username},
            headers=MASTODON_HEADERS,
            timeout=20,
        )
    except Exception as exc:
        return None, {
            "platform": profile.platform,
            "url": profile.url,
            "reason": "public_api_unavailable",
            "evidence": str(exc)[:500],
        }

    if response.status_code in {401, 403}:
        return None, {
            "platform": profile.platform,
            "url": profile.url,
            "reason": "public_api_restricted",
            "evidence": f"HTTP {response.status_code}",
        }
    if response.status_code == 404:
        return None, {
            "platform": profile.platform,
            "url": profile.url,
            "reason": "public_profile_not_found",
            "evidence": "HTTP 404",
        }
    if response.status_code != 200:
        return None, {
            "platform": profile.platform,
            "url": profile.url,
            "reason": "public_api_error",
            "evidence": f"HTTP {response.status_code}",
        }

    return (
        parse_mastodon_account_snapshot(
            profile,
            response.json(),
            collected_at=collected_at,
            fencer_identity_id=fencer_identity_id,
            fencer_id=fencer_id,
        ),
        None,
    )


def fetch_wikidata_social_profiles() -> list[SocialProfileCandidate]:
    profiles: list[SocialProfileCandidate] = []
    offset = 0
    while True:
        query = SPARQL_QUERY.format(**SOCIAL_PROPERTIES, limit=PAGE_SIZE, offset=offset)
        try:
            response = requests.get(
                SPARQL_URL,
                params={"query": query, "format": "json"},
                headers=HEADERS,
                timeout=60,
            )
        except Exception as exc:
            print(f"  Wikidata social probe unavailable: {exc}")
            break

        if response.status_code != 200:
            print(f"  Wikidata social probe HTTP {response.status_code}: {response.text[:300]}")
            break

        bindings = response.json().get("results", {}).get("bindings", [])
        if not bindings:
            break

        for binding in bindings:
            profiles.extend(parse_wikidata_social_binding(binding))

        print(f"  Fetched {len(profiles)} social profile candidates so far...")
        if len(bindings) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(REQUEST_DELAY)

    return profiles


def dedupe_profiles(profiles: list[SocialProfileCandidate]) -> list[SocialProfileCandidate]:
    deduped: dict[tuple[str | None, str | None, str, str], SocialProfileCandidate] = {}
    for profile in profiles:
        key = (profile.wikidata_id, profile.fie_id, profile.platform, profile.handle)
        deduped[key] = profile
    return list(deduped.values())


def dedupe_snapshot_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["snapshot_key"]
        current = deduped.get(key)
        if current is None or row["collected_at"] >= current["collected_at"]:
            deduped[key] = row
    return list(deduped.values())


def write_snapshot_rows(client: Any, rows: list[dict[str, Any]]) -> int:
    written = 0
    for row in rows:
        client.table("fs_social_followers").upsert(row, on_conflict="snapshot_key").execute()
        written += 1
    return written


def resolve_fencer_identity(
    client: Any,
    profile: SocialProfileCandidate,
) -> tuple[str | None, str | None]:
    if not profile.fie_id:
        return None, None

    try:
        identity_rows = (
            client.table("fs_fencer_identities")
            .select("id")
            .contains("fie_ids", [profile.fie_id])
            .limit(1)
            .execute()
            .data
        )
        if identity_rows:
            return identity_rows[0]["id"], None
    except Exception as exc:
        print(f"  Identity lookup failed for FIE {profile.fie_id}: {exc}")

    try:
        fencer_rows = (
            client.table("fs_fencers")
            .select("id")
            .eq("fie_id", profile.fie_id)
            .limit(1)
            .execute()
            .data
        )
        if fencer_rows:
            return None, fencer_rows[0]["id"]
    except Exception as exc:
        print(f"  Fencer lookup failed for FIE {profile.fie_id}: {exc}")

    return None, None


def print_blocked_source_stubs() -> None:
    print("Blocked source stubs:")
    for platform, evidence in sorted(BLOCKED_PLATFORM_DETAILS.items()):
        print(f"  {platform}: skipped - {evidence}")


def main() -> None:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        print(f"Social follower snapshots starting - {datetime.now(UTC).isoformat()}")
        print("Policy: public/API-backed sources only; no login bypass or private profile scraping.")
        print_blocked_source_stubs()

        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous social follower run state found: {previous_state}")

        profiles = dedupe_profiles(fetch_wikidata_social_profiles())
        print(f"Total social profile candidates: {len(profiles)}")

        if not supabase:
            print("SUPABASE_URL and SUPABASE_SERVICE_KEY are not set; no rows written.")
            run_log.complete(
                written=0,
                failed=0,
                skipped=len(profiles),
                metadata={"reason": "missing_supabase_credentials"},
            )
            return

        session = requests.Session()
        collected_at = datetime.now(UTC)
        rows: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        unmatched = 0

        for profile in profiles:
            fencer_identity_id, fencer_id = resolve_fencer_identity(supabase, profile)
            if not fencer_identity_id and not fencer_id:
                unmatched += 1
                continue

            row, blocked_source = collect_profile_snapshot(
                profile,
                session=session,
                collected_at=collected_at,
                fencer_identity_id=fencer_identity_id,
                fencer_id=fencer_id,
            )
            if row:
                rows.append(row)
                time.sleep(REQUEST_DELAY)
            elif blocked_source:
                blocked.append(blocked_source)

        rows = dedupe_snapshot_rows(rows)
        written = write_snapshot_rows(supabase, rows)
        set_state(SOURCE, "last_run", datetime.now(UTC).isoformat())
        set_state(
            SOURCE,
            "last_summary",
            {
                "candidates": len(profiles),
                "written": written,
                "blocked": len(blocked),
                "unmatched": unmatched,
            },
        )
        run_log.complete(
            written=written,
            failed=0,
            skipped=len(blocked) + unmatched,
            metadata={
                "candidates": len(profiles),
                "blocked_sources": blocked[:25],
                "unmatched": unmatched,
            },
        )
        print(
            f"Done - written={written}, blocked={len(blocked)}, "
            f"unmatched={unmatched}, candidates={len(profiles)}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

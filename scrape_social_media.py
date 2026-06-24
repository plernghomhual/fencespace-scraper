import html
import json
import os
import re
import time
from datetime import UTC, datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


SOURCE = "social_media"
SPARQL_URL = "https://query.wikidata.org/sparql"
FIE_ID_PROPERTY = "P2423"
FIE_BASE_URL = "https://fie.org/athletes"
REQUEST_DELAY = float(os.environ.get("SOCIAL_MEDIA_DELAY", "1.0"))
PAGE_SIZE = int(os.environ.get("SOCIAL_MEDIA_WIKIDATA_PAGE_SIZE", "5000"))
PROFILE_LIMIT = int(os.environ.get("SOCIAL_MEDIA_PROFILE_LIMIT", "250"))
PROFILE_TIMEOUT = int(os.environ.get("SOCIAL_MEDIA_PROFILE_TIMEOUT", "20"))
BATCH_SIZE = int(os.environ.get("SOCIAL_MEDIA_BATCH_SIZE", "100"))

HEADERS = {
    "User-Agent": "FenceSpaceBot/1.0 (social-media scraper; +https://fencespace.app)",
    "Accept": "application/sparql-results+json, application/json;q=0.9, */*;q=0.8",
}

PROFILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://fie.org/athletes",
}

WIKIDATA_SOCIAL_PROPERTIES = {
    "instagram": {"binding": "instagram", "property": "P2003"},
    "twitter": {"binding": "twitter", "property": "P2002"},
    "youtube": {"binding": "youtube", "property": "P2397"},
    "tiktok": {"binding": "tiktok", "property": "P7085"},
    "facebook": {"binding": "facebook", "property": "P2013"},
}

SPARQL_QUERY = """
SELECT ?athlete ?athleteLabel ?fie_id ?instagram ?twitter ?youtube ?tiktok ?facebook WHERE {{
  ?athlete wdt:P641 wd:Q12100 .
  OPTIONAL {{ ?athlete wdt:{fie_prop} ?fie_id . }}
  OPTIONAL {{ ?athlete wdt:P2003 ?instagram . }}
  OPTIONAL {{ ?athlete wdt:P2002 ?twitter . }}
  OPTIONAL {{ ?athlete wdt:P2397 ?youtube . }}
  OPTIONAL {{ ?athlete wdt:P7085 ?tiktok . }}
  OPTIONAL {{ ?athlete wdt:P2013 ?facebook . }}
  FILTER(BOUND(?instagram) || BOUND(?twitter) || BOUND(?youtube) || BOUND(?tiktok) || BOUND(?facebook))
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
    ?athlete rdfs:label ?athleteLabel .
  }}
}}
LIMIT {limit}
OFFSET {offset}
"""

KNOWN_PLATFORMS = {"instagram", "twitter", "youtube", "tiktok", "facebook", "threads", "other"}
GLOBAL_CONTEXT_MARKERS = {"footer", "header", "nav", "menu", "primary-menu", "xs-menu", "share", "sharing"}
SOCIAL_CONTEXT_MARKERS = {"social", "socials", "profile", "athlete"}
RESERVED_HANDLES = {
    "instagram": {"p", "reel", "reels", "stories", "explore", "accounts"},
    "twitter": {"intent", "share", "home", "search", "i"},
    "youtube": {"watch", "playlist", "shorts", "embed", "results"},
    "tiktok": {"tag", "music", "discover", "embed"},
    "facebook": {"sharer", "share.php", "plugins", "dialog", "events", "groups", "pages"},
    "threads": {"t", "privacy", "login"},
}
SOCIAL_URL_RE = re.compile(
    r"https?://(?:[a-z0-9.-]*\.)?(?:instagram\.com|twitter\.com|x\.com|youtube\.com|youtu\.be|"
    r"tiktok\.com|facebook\.com|fb\.com|threads\.net)[^\s\"'<>\\]*",
    flags=re.IGNORECASE,
)


def clean_text(value: Any) -> str | None:
    text = html.unescape(str(value or "")).strip().strip("\"'")
    text = re.sub(r"\s+", " ", text)
    return text or None


def ensure_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def strip_tracking(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/", "", "", ""))


def first_path_segment(url: str) -> str | None:
    segments = [part for part in urlparse(url).path.split("/") if part]
    return segments[0] if segments else None


def platform_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()

    if "instagram.com" in host:
        first = (first_path_segment(url) or "").lower()
        return None if first in RESERVED_HANDLES["instagram"] else "instagram"
    if host in {"twitter.com", "mobile.twitter.com", "x.com"}:
        first = (first_path_segment(url) or "").lower()
        return None if first in RESERVED_HANDLES["twitter"] else "twitter"
    if "youtube.com" in host or host == "youtu.be":
        first = (first_path_segment(url) or "").lower()
        return None if first in RESERVED_HANDLES["youtube"] else "youtube"
    if "tiktok.com" in host:
        first = (first_path_segment(url) or "").lower()
        return None if first in RESERVED_HANDLES["tiktok"] else "tiktok"
    if "facebook.com" in host or host == "fb.com":
        first = (first_path_segment(url) or "").lower()
        if first in RESERVED_HANDLES["facebook"] or path.startswith("/sharer"):
            return None
        return "facebook"
    if "threads.net" in host:
        first = (first_path_segment(url) or "").lower()
        return None if first in RESERVED_HANDLES["threads"] else "threads"
    return None


def handle_from_url(platform: str, url: str) -> str | None:
    parsed = urlparse(url)
    segments = [part for part in parsed.path.split("/") if part]
    if not segments:
        if platform == "facebook":
            query_id = parse_qs(parsed.query).get("id")
            return query_id[0] if query_id else None
        return None

    if platform == "youtube":
        if segments[0] in {"channel", "user", "c"} and len(segments) > 1:
            return clean_text(segments[1].lstrip("@"))
        return clean_text(segments[0].lstrip("@"))

    if platform in {"instagram", "twitter", "tiktok", "facebook", "threads"}:
        return clean_text(segments[0].lstrip("@"))

    return clean_text(segments[-1].lstrip("@"))


def normalize_handle(platform: str, value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if text.startswith("http://") or text.startswith("https://") or text.startswith("//"):
        url = f"https:{text}" if text.startswith("//") else text
        return handle_from_url(platform, url)
    text = text.rstrip("/")
    if platform in {"instagram", "twitter", "tiktok", "threads"}:
        text = text.lstrip("@")
    return text or None


def wikidata_url_for(platform: str, handle: str) -> str:
    if platform == "instagram":
        return f"https://www.instagram.com/{handle}/"
    if platform == "twitter":
        return f"https://twitter.com/{handle}"
    if platform == "youtube":
        if handle.startswith("@"):
            return f"https://www.youtube.com/{handle}"
        return f"https://www.youtube.com/channel/{handle}"
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{handle.lstrip('@')}"
    if platform == "facebook":
        return f"https://www.facebook.com/{handle}"
    if platform == "threads":
        return f"https://www.threads.net/@{handle.lstrip('@')}"
    return handle


def parse_wikidata_social_binding(binding: dict[str, Any]) -> dict[str, Any]:
    athlete_url = (binding.get("athlete") or {}).get("value", "")
    wikidata_id = athlete_url.split("/")[-1] if athlete_url else None
    parsed: dict[str, Any] = {
        "wikidata_id": wikidata_id,
        "name": (binding.get("athleteLabel") or {}).get("value"),
        "fie_id": (binding.get("fie_id") or {}).get("value"),
        "accounts": [],
    }

    for platform, spec in WIKIDATA_SOCIAL_PROPERTIES.items():
        value = (binding.get(spec["binding"]) or {}).get("value")
        handle = normalize_handle(platform, value)
        if not handle:
            continue
        parsed["accounts"].append(
            {
                "platform": platform,
                "handle": handle,
                "url": wikidata_url_for(platform, handle),
                "property": spec["property"],
            }
        )
    return parsed


def build_social_rows_for_fencers(
    parsed: dict[str, Any],
    fencer_ids: list[str],
    *,
    source: str,
    verified: bool = False,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    base_metadata = {
        "wikidata_id": parsed.get("wikidata_id"),
        "wikidata_label": parsed.get("name"),
        "fie_id": parsed.get("fie_id"),
    }
    if metadata:
        base_metadata.update(metadata)

    for fencer_id in dict.fromkeys(fencer_ids):
        for account in parsed.get("accounts", []):
            row_metadata = {k: v for k, v in base_metadata.items() if v is not None}
            if account.get("property"):
                row_metadata["wikidata_property"] = account["property"]
            rows.append(
                {
                    "fencer_id": fencer_id,
                    "platform": account["platform"],
                    "handle": account.get("handle"),
                    "url": account["url"],
                    "source": source,
                    "verified": verified,
                    "metadata": row_metadata,
                }
            )
    return rows


def fetch_wikidata_social_bindings(page_size: int = PAGE_SIZE, delay: float = REQUEST_DELAY) -> list[dict[str, Any]]:
    results = []
    offset = 0
    while True:
        query = SPARQL_QUERY.format(fie_prop=FIE_ID_PROPERTY, limit=page_size, offset=offset)
        response = requests.get(
            SPARQL_URL,
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=60,
        )
        if response.status_code != 200:
            print(f"  SPARQL social query failed with HTTP {response.status_code}")
            break
        bindings = response.json()["results"]["bindings"]
        if not bindings:
            break
        results.extend(bindings)
        if len(bindings) < page_size:
            break
        offset += page_size
        if delay > 0:
            time.sleep(delay)
    return results


def find_matching_fencer_ids(client: Any, *, wikidata_id: str | None = None, fie_id: str | None = None) -> list[str]:
    if wikidata_id:
        try:
            rows = (
                client.table("fs_fencers")
                .select("id")
                .eq("metadata->>wikidata_id", wikidata_id)
                .execute()
                .data
                or []
            )
            ids = [row["id"] for row in rows if row.get("id")]
            if ids:
                return list(dict.fromkeys(ids))
        except Exception as exc:
            print(f"  Wikidata ID match failed for {wikidata_id}: {exc}")

    if fie_id:
        try:
            rows = client.table("fs_fencers").select("id").eq("fie_id", fie_id).execute().data or []
            return list(dict.fromkeys(row["id"] for row in rows if row.get("id")))
        except Exception as exc:
            print(f"  FIE ID match failed for {fie_id}: {exc}")

    return []


def dedupe_social_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not row.get("fencer_id") or row.get("platform") not in KNOWN_PLATFORMS or not row.get("url"):
            continue
        key = (row["fencer_id"], row["platform"])
        existing = chosen.get(key)
        if not existing or (row.get("verified") and not existing.get("verified")):
            chosen[key] = row
    return list(chosen.values())


def upsert_social_rows(client: Any, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    clean_rows = dedupe_social_rows(rows)
    written = 0
    for i in range(0, len(clean_rows), batch_size):
        batch = clean_rows[i : i + batch_size]
        client.table("fs_fencer_social_media").upsert(batch, on_conflict="fencer_id,platform").execute()
        written += len(batch)
    return written


def scrape_wikidata_social_media(client: Any) -> dict[str, int]:
    bindings = fetch_wikidata_social_bindings()
    rows = []
    matched = skipped = failed = 0

    for binding in bindings:
        try:
            parsed = parse_wikidata_social_binding(binding)
            if not parsed["accounts"]:
                skipped += 1
                continue
            fencer_ids = find_matching_fencer_ids(
                client,
                wikidata_id=parsed.get("wikidata_id"),
                fie_id=parsed.get("fie_id"),
            )
            if not fencer_ids:
                skipped += 1
                continue
            matched += len(fencer_ids)
            rows.extend(build_social_rows_for_fencers(parsed, fencer_ids, source="wikidata"))
        except Exception as exc:
            failed += 1
            print(f"  Wikidata social parse failed: {exc}")

    written = upsert_social_rows(client, rows)
    set_state(SOURCE, "wikidata_last_run", datetime.now(UTC).isoformat())
    return {
        "bindings": len(bindings),
        "matched": matched,
        "written": written,
        "skipped": skipped,
        "failed": failed,
    }


def context_tokens(tag: Any) -> set[str]:
    tokens = set()
    current = tag
    for _ in range(6):
        if current is None:
            break
        if getattr(current, "name", None):
            tokens.add(str(current.name).lower())
        attrs = getattr(current, "attrs", {}) or {}
        for key in ("class", "id", "role"):
            value = attrs.get(key)
            if isinstance(value, list):
                parts = value
            elif value:
                parts = [value]
            else:
                parts = []
            for part in parts:
                tokens.update(re.split(r"[^a-z0-9_-]+", str(part).lower()))
        current = getattr(current, "parent", None)
    return {token for token in tokens if token}


def is_global_social_link(tag: Any) -> bool:
    tokens = context_tokens(tag)
    return bool(tokens & GLOBAL_CONTEXT_MARKERS)


def is_other_social_candidate(tag: Any) -> bool:
    attrs = getattr(tag, "attrs", {}) or {}
    rel = attrs.get("rel") or []
    if isinstance(rel, str):
        rel = [rel]
    if any(str(item).lower() == "me" for item in rel):
        return True
    data_platform = clean_text(attrs.get("data-platform") or attrs.get("aria-label"))
    if data_platform and "social" in data_platform.lower():
        return True
    return bool(context_tokens(tag) & SOCIAL_CONTEXT_MARKERS)


def social_link_from_anchor(anchor: Any, base_url: str | None = None) -> dict[str, Any] | None:
    href = clean_text(anchor.get("href"))
    if not href or href.startswith(("mailto:", "tel:", "javascript:")):
        return None

    url = urljoin(base_url or "", href)
    if is_global_social_link(anchor):
        return None

    platform = platform_from_url(url)
    if not platform and is_other_social_candidate(anchor):
        platform = "other"
    if not platform:
        return None

    normalized_url = strip_tracking(url)
    return {
        "platform": platform,
        "handle": handle_from_url(platform, normalized_url),
        "url": normalized_url,
    }


def social_link_from_url(url: str, base_url: str | None = None) -> dict[str, Any] | None:
    normalized_url = strip_tracking(urljoin(base_url or "", url.strip().rstrip(").,;")))
    platform = platform_from_url(normalized_url)
    if not platform:
        return None
    return {
        "platform": platform,
        "handle": handle_from_url(platform, normalized_url),
        "url": normalized_url,
    }


def extract_social_links_from_script_text(text: str, base_url: str | None = None) -> list[dict[str, Any]]:
    links = []
    for match in SOCIAL_URL_RE.finditer(text or ""):
        link = social_link_from_url(match.group(0), base_url=base_url)
        if link:
            links.append(link)
    return links


def extract_social_links_from_html(page_html: str, base_url: str | None = None) -> list[dict[str, Any]]:
    soup = BeautifulSoup(page_html or "", "html.parser")
    links = []
    for anchor in soup.find_all("a", href=True):
        link = social_link_from_anchor(anchor, base_url=base_url)
        if link:
            links.append(link)
    for script in soup.find_all("script"):
        links.extend(extract_social_links_from_script_text(script.get_text(" "), base_url=base_url))

    by_platform: dict[str, Any] = {}
    for link in links:
        by_platform.setdefault(link["platform"], link)
    return list(by_platform.values())


def profile_url_for_fencer(fencer: dict[str, Any]) -> str | None:
    metadata = ensure_metadata(fencer.get("metadata"))
    candidates = [
        metadata.get("federation_profile_url"),
        metadata.get("profile_url"),
        metadata.get("fie_profile_url"),
    ]
    profile_scrape = metadata.get("fie_profile_scrape")
    if isinstance(profile_scrape, dict):
        candidates.append(profile_scrape.get("profile_url"))

    for candidate in candidates:
        text = clean_text(candidate)
        if text:
            return urljoin(FIE_BASE_URL + "/", text)

    fie_id = clean_text(fencer.get("fie_id"))
    if fie_id:
        return f"{FIE_BASE_URL}/{fie_id}"
    return None


def fetch_fencers_for_profile_scrape(client: Any, *, offset: int, limit: int) -> list[dict[str, Any]]:
    rows = (
        client.table("fs_fencers")
        .select("id,fie_id,name,metadata")
        .order("fie_id")
        .range(offset, offset + limit - 1)
        .execute()
        .data
        or []
    )
    return [row for row in rows if row.get("id") and profile_url_for_fencer(row)]


def profile_rows_for_fencer(fencer: dict[str, Any], links: list[dict[str, Any]], profile_url: str) -> list[dict[str, Any]]:
    metadata = {
        "profile_url": profile_url,
        "fie_id": clean_text(fencer.get("fie_id")),
    }
    return [
        {
            "fencer_id": fencer["id"],
            "platform": link["platform"],
            "handle": link.get("handle"),
            "url": link["url"],
            "source": "federation_profile",
            "verified": True,
            "metadata": {k: v for k, v in metadata.items() if v is not None},
        }
        for link in links
    ]


def profile_cursor_offset() -> int:
    state = get_state(SOURCE, "federation_cursor")
    if isinstance(state, dict):
        try:
            return max(0, int(state.get("offset", 0)))
        except (TypeError, ValueError):
            return 0
    try:
        return max(0, int(state or 0))
    except (TypeError, ValueError):
        return 0


def make_profile_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(PROFILE_HEADERS)
    return session


def scrape_federation_profiles(
    client: Any,
    *,
    session: requests.Session | None = None,
    limit: int = PROFILE_LIMIT,
    delay: float = REQUEST_DELAY,
) -> dict[str, int]:
    offset = profile_cursor_offset()
    fencers = fetch_fencers_for_profile_scrape(client, offset=offset, limit=limit)
    session = session or make_profile_session()

    rows = []
    processed = skipped = failed = 0
    for fencer in fencers:
        profile_url = profile_url_for_fencer(fencer)
        if not profile_url:
            skipped += 1
            continue
        try:
            response = session.get(profile_url, timeout=PROFILE_TIMEOUT)
            if response.status_code != 200:
                failed += 1
                print(f"  Profile social scrape HTTP {response.status_code}: {profile_url}")
                continue
            links = extract_social_links_from_html(response.text, base_url=profile_url)
            if not links:
                skipped += 1
                continue
            rows.extend(profile_rows_for_fencer(fencer, links, profile_url))
            processed += 1
        except Exception as exc:
            failed += 1
            print(f"  Profile social scrape failed for {profile_url}: {exc}")
        if delay > 0:
            time.sleep(delay)

    written = upsert_social_rows(client, rows)
    next_offset = 0 if len(fencers) < limit else offset + len(fencers)
    set_state(
        SOURCE,
        "federation_cursor",
        {
            "offset": next_offset,
            "updated_at": datetime.now(UTC).isoformat(),
            "last_batch_size": len(fencers),
        },
    )
    return {"profiles": processed, "written": written, "skipped": skipped, "failed": failed}


def main() -> None:
    if supabase is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_social_media").start()
    try:
        print(f"Social media scraper starting - {datetime.now(UTC).isoformat()}")
        wikidata_stats = scrape_wikidata_social_media(supabase)
        profile_stats = scrape_federation_profiles(supabase)
        set_state(SOURCE, "last_run", datetime.now(UTC).isoformat())

        written = wikidata_stats["written"] + profile_stats["written"]
        failed = wikidata_stats["failed"] + profile_stats["failed"]
        skipped = wikidata_stats["skipped"] + profile_stats["skipped"]
        run_log.complete(
            written=written,
            failed=failed,
            skipped=skipped,
            metadata={"wikidata": wikidata_stats, "federation_profiles": profile_stats},
        )
        print(
            "Social media scraper complete - "
            f"written={written}, failed={failed}, skipped={skipped}, "
            f"wikidata={wikidata_stats}, federation_profiles={profile_stats}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

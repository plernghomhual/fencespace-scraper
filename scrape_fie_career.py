"""
Extracts FIE career ranking history for each fencer from their athlete page.

Reads window._tabRanking from the athlete page HTML (same URL as
scrape_athlete_profiles.py) and writes entries to fs_rankings_history.

Progress is tracked via metadata.fie_career_scraped_at on fs_fencers rows so
fencers already processed are skipped on subsequent runs.
"""
import json
import os
import re
import time
from datetime import UTC, datetime, timezone
from typing import Any

import requests

from run_logger import ScraperRunLogger

try:
    from scripts.rate_limiter import RateLimiter as _RateLimiter
    _fie_limiter = _RateLimiter(default_rps=0.67, jitter=0.2, backoff=5.0)
except ImportError:
    _fie_limiter = None

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FIE_BASE_URL = "https://fie.org/athletes"
MAX_FENCERS = int(os.environ.get("FIE_CAREER_LIMIT", "500"))
REQUEST_DELAY = float(os.environ.get("FIE_CAREER_DELAY", "1.5"))
BATCH_SIZE = 100
FORCE = os.environ.get("FIE_CAREER_FORCE", "").lower() in {"1", "true", "yes"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://fie.org/athletes",
}

# Lowercase keys — apply via .lower() on raw values from _tabRanking
WEAPON_MAP: dict[str, str] = {
    "e": "Epee", "epee": "Epee",
    "f": "Foil", "foil": "Foil", "fleuret": "Foil",
    "s": "Sabre", "sabre": "Sabre",
    "m": "Sabre",  # alternate FIE single-letter code for sabre
}
CATEGORY_MAP: dict[str, str] = {
    "s": "Senior", "senior": "Senior",
    "j": "Junior", "junior": "Junior",
    "c": "Cadet", "cadet": "Cadet",
    "v": "Veteran", "veteran": "Veteran",
}


def extract_window_var(html: str, var_name: str) -> Any:
    """Extract window.{var_name} = [...] or {...} from page HTML.

    Uses JSONDecoder.raw_decode for correct handling of nested structures.
    Returns None if the variable is absent or unparseable.
    """
    m = re.search(rf"window\.{re.escape(var_name)}\s*=\s*", html)
    if not m:
        return None
    offset = m.end()
    while offset < len(html) and html[offset].isspace():
        offset += 1
    if offset >= len(html) or html[offset] not in "[{":
        return None
    try:
        result, _ = json.JSONDecoder().raw_decode(html[offset:])
        return result
    except json.JSONDecodeError:
        return None


def parse_tab_ranking(html: str) -> list[dict]:
    """Parse window._tabRanking entries from an athlete page.

    Each entry in the FIE array has: weapon, category, season, rank, point.
    Returns a list of normalised dicts with keys: weapon, category, season,
    rank, points. Entries with unrecognised weapon or category codes are
    silently skipped.
    """
    data = extract_window_var(html, "_tabRanking")
    if not data or not isinstance(data, list):
        return []
    rows: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        weapon = WEAPON_MAP.get(str(entry.get("weapon", "")).lower())
        category = CATEGORY_MAP.get(str(entry.get("category", "")).lower())
        if not weapon or not category:
            continue
        season = entry.get("season")
        rank_raw = entry.get("rank")
        point_raw = entry.get("point") or entry.get("points")
        if not season or not rank_raw:
            continue
        try:
            rows.append({
                "weapon": weapon,
                "category": category,
                "season": int(season),
                "rank": int(rank_raw),
                "points": float(point_raw) if point_raw is not None else None,
            })
        except (ValueError, TypeError):
            continue
    return rows


def gender_from_category(category: str | None) -> str | None:
    """Derive gender label from fs_fencers.category (e.g. "Women's Senior" → "Women's")."""
    if not category:
        return None
    c = category.strip()
    if c.startswith("Women"):
        return "Women's"
    if c.startswith("Men"):
        return "Men's"
    return None


def load_fencers(limit: int) -> list[dict]:
    """Return up to *limit* distinct fencers (by fie_id) not yet career-scraped.

    Queries fs_fencers ordered by world_rank (best-ranked first) and
    deduplicates by fie_id client-side, since the same fencer can appear in
    multiple weapon/category rows.
    """
    columns = "fie_id,name,country,category,metadata"

    def run_query(with_filter: bool):
        q = (
            supabase.table("fs_fencers")  # type: ignore[union-attr]
            .select(columns)
            .not_.is_("fie_id", "null")
            .order("world_rank", desc=False)
            .limit(limit * 6)
        )
        if with_filter and not FORCE:
            q = q.filter("metadata->>fie_career_scraped_at", "is", "null")
        return q.execute().data or []

    try:
        rows = run_query(with_filter=True)
    except Exception as exc:
        print(f"  metadata filter failed ({exc}), fetching without filter")
        rows = run_query(with_filter=False)

    seen: dict[str, dict] = {}
    for row in rows:
        fie_id = str(row.get("fie_id") or "").strip()
        if fie_id and fie_id not in seen:
            seen[fie_id] = row
        if len(seen) >= limit:
            break
    return list(seen.values())


def upsert_career_rankings(
    fie_id: str,
    gender: str,
    name: str | None,
    country: str | None,
    ranking_rows: list[dict],
) -> int:
    """Upsert career ranking entries to fs_rankings_history. Returns count written."""
    if not ranking_rows:
        return 0
    now = datetime.now(UTC).isoformat()
    db_rows = [
        {
            "fie_fencer_id": fie_id,
            "season": r["season"],
            "weapon": r["weapon"],
            "gender": gender,
            "category": f"{gender} {r['category']}",
            "rank": r["rank"],
            "points": r["points"],
            "name": name,
            "country": country,
            "scraped_at": now,
        }
        for r in ranking_rows
    ]
    written = 0
    for i in range(0, len(db_rows), BATCH_SIZE):
        batch = db_rows[i : i + BATCH_SIZE]
        try:
            supabase.table("fs_rankings_history").upsert(  # type: ignore[union-attr]
                batch, on_conflict="season,weapon,gender,category,fie_fencer_id"
            ).execute()
            written += len(batch)
        except Exception as exc:
            print(f"    Batch upsert failed: {exc}")
    return written


def mark_scraped(fie_id: str, existing_metadata: Any) -> None:
    """Set metadata.fie_career_scraped_at on all fs_fencers rows for this fie_id."""
    meta: dict = dict(existing_metadata) if isinstance(existing_metadata, dict) else {}
    meta["fie_career_scraped_at"] = datetime.now(UTC).isoformat()
    try:
        supabase.table("fs_fencers").update({"metadata": meta}).eq("fie_id", fie_id).execute()  # type: ignore[union-attr]
    except Exception as exc:
        print(f"    Could not mark career scraped for fie_id={fie_id}: {exc}")


def main() -> None:
    if not supabase:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    run_log = ScraperRunLogger("scrape_fie_career").start()
    print(f"FIE career scraper starting — {datetime.now(UTC).isoformat()}")
    print(f"  Limit: {MAX_FENCERS}, delay: {REQUEST_DELAY}s, force: {FORCE}")

    try:
        fencers = load_fencers(MAX_FENCERS)
        print(f"  {len(fencers)} fencers to process")

        written = failed = skipped = 0

        for fencer in fencers:
            fie_id = str(fencer.get("fie_id", "")).strip()
            if not fie_id:
                skipped += 1
                continue
            gender = gender_from_category(fencer.get("category"))
            if not gender:
                skipped += 1
                continue

            url = f"{FIE_BASE_URL}/{fie_id}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=20)
                if resp.status_code != 200:
                    print(f"  {fie_id}: HTTP {resp.status_code}")
                    failed += 1
                    if _fie_limiter:
                        _fie_limiter.record_failure("fie.org")
                        _fie_limiter.wait("fie.org")
                    else:
                        time.sleep(REQUEST_DELAY)
                    continue

                ranking_rows = parse_tab_ranking(resp.text)
                mark_scraped(fie_id, fencer.get("metadata"))

                if not ranking_rows:
                    print(f"  {fie_id}: no _tabRanking data")
                    skipped += 1
                    if _fie_limiter:
                        _fie_limiter.wait("fie.org")
                    else:
                        time.sleep(REQUEST_DELAY)
                    continue

                n = upsert_career_rankings(
                    fie_id, gender,
                    fencer.get("name"), fencer.get("country"),
                    ranking_rows,
                )
                print(f"  {fie_id} ({fencer.get('name')}): {n} ranking rows")
                written += n

            except Exception as exc:
                print(f"  {fie_id}: error — {exc}")
                failed += 1
                if _fie_limiter:
                    _fie_limiter.record_failure("fie.org")

            if _fie_limiter:
                _fie_limiter.wait("fie.org")
            else:
                time.sleep(REQUEST_DELAY)

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"\nDone — written={written}, failed={failed}, skipped={skipped}")

    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

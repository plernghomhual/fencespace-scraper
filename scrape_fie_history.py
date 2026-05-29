"""
Scrape FIE historical tournament data from https://fie.org/competitions/search
and upsert into fs_tournaments.

The FIE API uses:
  POST /competitions/search
  Body: {"name":"","status":"passed","gender":[],"weapon":[],"type":[],
         "season":<int>,"level":"","competitionCategory":"","fromDate":"","toDate":"","fetchPage":<int>}
  Returns: {"items":[...], "totalFound":<int>, "page":<int>, "pageSize":<int>, ...}

Item fields: competitionId, name, country, location, startDate, endDate,
             weapon (lowercase), gender (lowercase), category (lowercase),
             type ("individual"/"team"), hasResults (0/1), season (int)
"""

import os
import time
from datetime import datetime, timezone

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FIE_BASE = "https://fie.org"
SOURCE = "fie_history"
# 2003 is the first season with substantial data (347+ competitions).
# Probe result: 2001=18, 2002=24, 2003=347 — use 2003 as the practical baseline.
EARLIEST_SEASON = int(os.environ.get("FIE_HISTORY_EARLIEST_SEASON", 2003))
REQUEST_DELAY = 1.5

COMP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/competitions",
}

# API returns lowercase text; normalize to title-case for display
WEAPON_MAP = {"epee": "Epee", "foil": "Foil", "sabre": "Sabre"}
GENDER_MAP = {"men": "Men", "women": "Women"}
CATEGORY_MAP = {"senior": "Senior", "junior": "Junior", "cadet": "Cadet", "veteran": "Veteran"}


def normalize_fie_date(date_str):
    """Convert FIE date format DD-MM-YYYY to ISO 8601 YYYY-MM-DD."""
    if not date_str:
        return None
    try:
        parts = date_str.split("-")
        if len(parts) != 3 or len(parts[2]) != 4:
            return None
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
        return None


def seasons_to_scrape(earliest, current):
    """Return list of season integers from earliest to current inclusive."""
    return list(range(earliest, current + 1))


def competition_to_tournament_row(comp, season):
    """Map a FIE API competition item dict to a fs_tournaments row dict."""
    return {
        "fie_id": comp["competitionId"],
        "name": comp.get("name"),
        "season": str(season),
        "country": comp.get("country"),
        "location": comp.get("location"),
        "start_date": normalize_fie_date(comp.get("startDate")),
        "end_date": normalize_fie_date(comp.get("endDate")),
        "weapon": WEAPON_MAP.get(comp.get("weapon", ""), comp.get("weapon")),
        "gender": GENDER_MAP.get(comp.get("gender", ""), comp.get("gender")),
        "category": CATEGORY_MAP.get(comp.get("category", ""), comp.get("category")),
        "type": comp.get("type"),
        "has_results": bool(comp.get("hasResults", 0)),
        "metadata": {"scraped_by": "scrape_fie_history"},
    }


def _make_session():
    """Create a requests session with FIE cookies loaded."""
    s = requests.Session()
    s.headers.update({"User-Agent": COMP_HEADERS["User-Agent"]})
    try:
        s.get(f"{FIE_BASE}/competitions", timeout=15)
    except Exception as exc:
        print(f"  Warning: session setup GET failed: {exc}")
    return s


def fetch_competitions(session, season):
    """
    Fetch all competition items for a given season from FIE /competitions/search.
    Paginates until fewer than pageSize items are returned or page >= 20.
    Returns a list of raw item dicts.
    """
    results = []
    page = 1
    while True:
        payload = {
            "name": "", "status": "passed",
            "gender": [], "weapon": [], "type": [],
            "season": season, "level": "", "competitionCategory": "",
            "fromDate": "", "toDate": "", "fetchPage": page,
        }
        try:
            r = session.post(
                f"{FIE_BASE}/competitions/search",
                headers=COMP_HEADERS,
                json=payload,
                timeout=15,
            )
            if r.status_code != 200 or not r.text.strip():
                print(f"    HTTP {r.status_code} for season={season} page={page}, stopping.")
                break
            data = r.json()
            items = data.get("items", [])
            if not items:
                break
            results.extend(items)
            page_size = data.get("pageSize", 300)
            if len(items) < page_size or page >= 20:
                break
            page += 1
            time.sleep(0.5)
        except Exception as exc:
            print(f"    Fetch failed (season={season} page={page}): {exc}")
            break
    return results


def upsert_tournaments(rows):
    """Upsert tournament rows into fs_tournaments, deduping on fie_id. Returns count written."""
    if not rows or supabase is None:
        return 0
    seen = {r["fie_id"]: r for r in rows}
    deduped = list(seen.values())
    for i in range(0, len(deduped), 100):
        try:
            supabase.table("fs_tournaments").upsert(
                deduped[i:i + 100], on_conflict="fie_id"
            ).execute()
        except Exception as exc:
            print(f"  Upsert batch failed: {exc}")
    return len(deduped)


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_fie_history").start()
    print(f"FIE history scraper starting — {datetime.now(timezone.utc).isoformat()}")

    current_year = datetime.now(timezone.utc).year
    done_seasons = set(get_state(SOURCE, "done_seasons") or [])
    all_seasons = seasons_to_scrape(EARLIEST_SEASON, current_year)
    seasons = [s for s in all_seasons if s not in done_seasons]
    print(f"Seasons to scrape: {len(seasons)} (skipping {len(done_seasons)} already done)")

    session = _make_session()
    total_written = total_failed = 0

    for season in seasons:
        print(f"\nSeason {season}:")
        try:
            comps = fetch_competitions(session, season)
            if not comps:
                print(f"  No competitions found.")
                done_seasons.add(season)
                set_state(SOURCE, "done_seasons", list(done_seasons))
                continue

            rows = [competition_to_tournament_row(c, season) for c in comps]
            n = upsert_tournaments(rows)
            print(f"  Season {season}: {n} tournaments upserted ({len(comps)} fetched)")
            total_written += n
            done_seasons.add(season)
            set_state(SOURCE, "done_seasons", list(done_seasons))
        except Exception as exc:
            print(f"  Season {season} failed: {exc}")
            total_failed += 1

        time.sleep(REQUEST_DELAY)

    run_log.complete(written=total_written, failed=total_failed)
    print(f"\nDone — written={total_written}, failed={total_failed}")


if __name__ == "__main__":
    main()

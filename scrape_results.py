import os
import re
import json
import time
import requests
from datetime import datetime, timedelta
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def extract_inline_json(html):
    matches = re.findall(r'window\.\w+\s*=\s*(\{.*?\}|\[.*?\]);', html, re.DOTALL)
    blocks = []
    for m in matches:
        try:
            blocks.append(json.loads(m))
        except Exception:
            pass
    return blocks


def get_competition_data(season, competition_url_id):
    url = f"https://fie.org/competitions/{season}/{competition_url_id}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        if res.status_code != 200:
            return None, None
        blocks = extract_inline_json(res.text)
        meta = None
        rows = None
        for block in blocks:
            if isinstance(block, dict) and 'competitionId' in block:
                meta = block
            if isinstance(block, dict) and 'rows' in block and block['rows']:
                rows = block['rows']
        return meta, rows
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None, None


def normalize_date(date_str):
    # Convert "28-01-2026" -> "2026-01-28"
    try:
        parts = date_str.split("-")
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
        return None


def names_match(a, b):
    # Loose name match - both lowercase, strip accents
    import unicodedata

    def clean(s):
        s = (s or "").lower().strip()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        return s

    a, b = clean(a), clean(b)
    return a == b or a in b or b in a


def discover_competition_url_ids(tournaments):
    """Try to find competitionId URL slugs for tournaments that don't have them yet"""
    print("Discovering competition URL IDs...")

    s = requests.Session()
    s.headers.update(HEADERS)
    s.get("https://fie.org/competitions", timeout=15)

    # Group by season for efficient searching
    by_season = {}
    for t in tournaments:
        season = t.get("season") or datetime.utcnow().year
        by_season.setdefault(season, []).append(t)

    current_year = datetime.utcnow().year
    current_month = datetime.utcnow().month

    for season, season_tournaments in by_season.items():
        print(f"  Searching season {season} — {len(season_tournaments)} tournaments")

        # Collect ALL items for this season across all months
        all_items = []
        for month in range(1, 13):
            if season == current_year and month > current_month:
                continue
            from_date = f"{season}-{month:02d}-01"
            to_date = f"{season}-{month:02d}-28"
            try:
                res = s.post("https://fie.org/competitions/search", headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://fie.org/competitions",
                }, json={
                    "name": "", "status": "passed", "gender": [], "weapon": [],
                    "type": [], "season": season, "level": "",
                    "competitionCategory": "", "fromDate": from_date,
                    "toDate": to_date, "fetchPage": 1,
                }, timeout=15)
                items = res.json().get("items", [])
                all_items.extend(items)
                time.sleep(0.3)
            except Exception:
                continue

        print(f"    Got {len(all_items)} total items for season {season}")

        # Match each of our tournaments against search results
        for t in season_tournaments:
            t_start = t.get("start_date", "")
            t_weapon = (t.get("weapon") or "").lower()
            t_gender = (t.get("gender") or "").lower()
            t_name = t.get("name", "")

            best_match = None
            for item in all_items:
                item_start = normalize_date(item.get("startDate", ""))
                item_weapon = (item.get("weapon") or "").lower()
                item_gender = (item.get("gender") or "").lower()
                item_name = item.get("name", "")

                if (
                    item_start == t_start
                    and item_weapon == t_weapon
                    and item_gender == t_gender
                    and names_match(item_name, t_name)
                ):
                    best_match = item
                    break

            if best_match:
                url_id = best_match.get("competitionId")
                supabase.table("fs_tournaments")\
                    .update({"competition_url_id": url_id})\
                    .eq("id", t["id"])\
                    .execute()
                print(f"    ✓ Mapped '{t_name}' → url_id={url_id}")
            else:
                print(f"    ✗ No match for '{t_name}' {t_start} {t_weapon} {t_gender}")


def scrape_results():
    print(f"Results scraper starting — {datetime.utcnow().isoformat()}")
    current_year = datetime.utcnow().year
    today = datetime.utcnow().strftime("%Y-%m-%d")
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Get all completed tournaments that don't have results yet
    # and have a competition_url_id
    tournaments = supabase.table("fs_tournaments")\
        .select("id,fie_id,name,season,weapon,gender,competition_url_id")\
        .lte("end_date", today)\
        .eq("is_sub_competition", False)\
        .not_.is_("competition_url_id", "null")\
        .execute().data

    print(f"Found {len(tournaments)} completed tournaments with URL IDs")

    # Also get tournaments without competition_url_id — need to discover them
    tournaments_no_url = supabase.table("fs_tournaments")\
        .select("id,fie_id,name,season,weapon,gender,start_date")\
        .lte("end_date", today)\
        .eq("is_sub_competition", False)\
        .is_("competition_url_id", "null")\
        .execute().data

    print(f"Found {len(tournaments_no_url)} completed tournaments needing URL ID discovery")

    # Discover competition_url_ids via FIE search API
    if tournaments_no_url:
        discover_competition_url_ids(tournaments_no_url)
        # Re-fetch with url ids now populated
        tournaments = supabase.table("fs_tournaments")\
            .select("id,fie_id,name,season,weapon,gender,competition_url_id")\
            .lte("end_date", today)\
            .eq("is_sub_competition", False)\
            .not_.is_("competition_url_id", "null")\
            .execute().data

    # Also include currently live tournaments (started but not ended yet)
    live_tournaments = supabase.table("fs_tournaments")\
        .select("id,fie_id,name,season,weapon,gender,competition_url_id")\
        .lte("start_date", today)\
        .gte("end_date", today)\
        .eq("is_sub_competition", False)\
        .not_.is_("competition_url_id", "null")\
        .execute().data

    print(f"Found {len(live_tournaments)} live tournaments")
    tournaments = tournaments + live_tournaments

    # Check which already have results
    existing = supabase.table("fs_results")\
        .select("tournament_id")\
        .execute().data
    existing_ids = set(r["tournament_id"] for r in existing)

    # Always re-scrape recent tournaments (ended within the last 7 days)
    recent_tournaments = supabase.table("fs_tournaments")\
        .select("id")\
        .gte("end_date", week_ago)\
        .lte("end_date", today)\
        .execute().data
    recent_ids = set(r["id"] for r in recent_tournaments)

    # Scrape if: no results yet OR recently ended
    to_scrape = [t for t in tournaments if t["id"] not in existing_ids or t["id"] in recent_ids]
    print(f"{len(to_scrape)} tournaments need results scraped")

    scraped = 0
    failed = 0
    scraped_this_run = set()

    for t in to_scrape:
        season = t.get("season") or current_year
        url_id = t.get("competition_url_id")
        tournament_id = t["id"]

        # Skip if already scraped this run
        if tournament_id in scraped_this_run:
            print(f"  Skipping {t['name']} — already scraped this run")
            continue
        scraped_this_run.add(tournament_id)
        print(f"  Scraping {t['name']} ({season}/{url_id})...")

        meta, rows = get_competition_data(season, url_id)

        if not rows:
            print(f"    No results found")
            failed += 1
            time.sleep(1)
            continue

        # Get tournament's Supabase ID
        # Build result rows
        result_rows = []
        for r in rows:
            if not r.get("name") or not r.get("rank"):
                continue
            result_rows.append({
                "tournament_id": tournament_id,
                "fie_fencer_id": r.get("fencerId"),
                "name": r.get("name", "").title(),
                "nationality": r.get("nationality"),
                "rank": r.get("rank"),
                "placement": r.get("rank"),
                "victory": r.get("victory"),
                "matches": r.get("matches"),
                "td": r.get("td"),
                "tr": r.get("tr"),
                "diff": r.get("diff"),
            })

        if not result_rows:
            print(f"    No valid rows")
            failed += 1
            time.sleep(1)
            continue

        # If re-scraping, clear existing rows to avoid duplicates
        if tournament_id in existing_ids:
            supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()

        # Upsert in batches
        for i in range(0, len(result_rows), 100):
            supabase.table("fs_results").upsert(
                result_rows[i:i+100],
                on_conflict="tournament_id,fie_fencer_id,rank"
            ).execute()

        print(f"    Inserted {len(result_rows)} results")
        scraped += 1
        time.sleep(0.5)  # be polite to FIE

    print(f"\nDone — {scraped} tournaments scraped, {failed} failed")


if __name__ == "__main__":
    scrape_results()

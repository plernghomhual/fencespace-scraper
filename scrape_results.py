import os
import re
import json
import time
import requests
from datetime import datetime
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

    for season, season_tournaments in by_season.items():
        print(f"  Searching season {season} — {len(season_tournaments)} tournaments")

        # Search each month of the season
        for month in range(1, 13):
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
                if not items:
                    continue

                # Match search results to our tournaments by fie_id
                for item in items:
                    fie_id = item.get("id")
                    competition_url_id = item.get("competitionId")
                    if not fie_id or not competition_url_id:
                        continue

                    # Find matching tournament in our DB
                    matching = [t for t in season_tournaments if t.get("fie_id") == fie_id]
                    for t in matching:
                        supabase.table("fs_tournaments")\
                            .update({"competition_url_id": competition_url_id})\
                            .eq("id", t["id"])\
                            .execute()
                        print(f"    Mapped {t['name']} fie_id={fie_id} → url_id={competition_url_id}")

                time.sleep(0.5)
            except Exception as e:
                print(f"    Search error for {from_date}: {e}")
                continue


def scrape_results():
    print(f"Results scraper starting — {datetime.utcnow().isoformat()}")
    current_year = datetime.utcnow().year
    today = datetime.utcnow().strftime("%Y-%m-%d")

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
        .select("id,fie_id,name,season,weapon,gender")\
        .lte("end_date", today)\
        .eq("is_sub_competition", False)\
        .is_("competition_url_id", "null")\
        .limit(50)\
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

    # Check which already have results
    existing = supabase.table("fs_results")\
        .select("tournament_id")\
        .execute().data
    existing_ids = set(r["tournament_id"] for r in existing)

    to_scrape = [t for t in tournaments if t["id"] not in existing_ids]
    print(f"{len(to_scrape)} tournaments need results scraped")

    scraped = 0
    failed = 0

    for t in to_scrape:
        season = t.get("season") or current_year
        url_id = t.get("competition_url_id")
        print(f"  Scraping {t['name']} ({season}/{url_id})...")

        meta, rows = get_competition_data(season, url_id)

        if not rows:
            print(f"    No results found")
            failed += 1
            time.sleep(1)
            continue

        # Get tournament's Supabase ID
        tournament_id = t["id"]

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

        # Insert in batches
        for i in range(0, len(result_rows), 100):
            supabase.table("fs_results").insert(result_rows[i:i+100]).execute()

        print(f"    Inserted {len(result_rows)} results")
        scraped += 1
        time.sleep(1.5)  # be polite to FIE

    print(f"\nDone — {scraped} tournaments scraped, {failed} failed")


if __name__ == "__main__":
    scrape_results()

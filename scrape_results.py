import os
import re
import json
import time
import calendar
import unicodedata
import requests
from datetime import datetime, timedelta, timezone
from supabase import create_client

from run_logger import ScraperRunLogger

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
RESULTS_UNAVAILABLE_THRESHOLD = int(os.environ.get("RESULTS_UNAVAILABLE_THRESHOLD", "3"))


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


def clean_text(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def title_case(value):
    text = clean_text(value)
    return text.title() if text else None


def normalize_country(value):
    text = clean_text(value)
    if not text:
        return None
    key = text.upper().replace(".", "")
    key = re.sub(r"\s+", " ", key)
    country_map = {
        "_AIN": "Russia",
        "AIN_": "Russia",
        "AIN": "Russia",
        "INDIVIDUAL NEUTRAL ATHLETES": "Russia",
        "FIE": "FIE",
        "USA": "United States",
        "US": "United States",
        "UNITED STATES": "United States",
        "UNITED STATES OF AMERICA": "United States",
        "GBR": "Great Britain",
        "GREAT BRITAIN": "Great Britain",
        "KOREA": "South Korea",
        "KOR": "South Korea",
        "HONG KONG, CHINA": "Hong Kong",
        "HONG KONG CHINA": "Hong Kong",
        "MACAO, CHINA": "Macau",
        "MACAO CHINA": "Macau",
        "TURKIYE": "Turkey",
        "TÜRKIYE": "Turkey",
        "TÜRKİYE": "Turkey",
        "COTE D'IVOIRE": "Côte d'Ivoire",
        "COTE DIVOIRE": "Côte d'Ivoire",
    }
    return country_map.get(key, title_case(text))


def normalize_person_name(value):
    text = clean_text(value)
    if not text:
        return None
    parts = text.split()
    leading = 0
    while leading < len(parts) and any(ch.isalpha() for ch in parts[leading]) and parts[leading].upper() == parts[leading]:
        leading += 1
    if 0 < leading < len(parts):
        last = title_case(" ".join(parts[:leading]))
        first = title_case(" ".join(parts[leading:]))
        return first if first.lower() == last.lower() else f"{first} {last}"
    trailing = 0
    while trailing < len(parts) and any(ch.isalpha() for ch in parts[-1 - trailing]) and parts[-1 - trailing].upper() == parts[-1 - trailing]:
        trailing += 1
    if 0 < trailing < len(parts):
        first = title_case(" ".join(parts[:-trailing]))
        last = title_case(" ".join(parts[-trailing:]))
        return first if first.lower() == last.lower() else f"{first} {last}"
    return title_case(text)


def names_match(a, b):
    def clean(s):
        s = (s or "").lower().strip()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        return s

    a, b = clean(a), clean(b)
    if a == b or a in b or b in a:
        return True
    # Token overlap: if most tokens from the shorter string appear in the longer string
    tokens_a = set(re.split(r"\W+", a)) - {""}
    tokens_b = set(re.split(r"\W+", b)) - {""}
    if not tokens_a or not tokens_b:
        return False
    shorter = tokens_a if len(tokens_a) <= len(tokens_b) else tokens_b
    longer = tokens_a if len(tokens_a) > len(tokens_b) else tokens_b
    overlap = len(shorter & longer) / len(shorter)
    return overlap >= 0.7


def to_int(value):
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except Exception:
        return None


def dedupe_result_rows(rows):
    seen = {}
    for row in rows:
        fencer_key = row.get("fie_fencer_id") or row.get("name")
        key = (row.get("tournament_id"), fencer_key, row.get("rank"))
        if key not in seen:
            seen[key] = row
    return list(seen.values())


def discover_competition_url_ids(tournaments):
    """Try to find competitionId URL slugs for tournaments that don't have them yet"""
    print("Discovering competition URL IDs...")

    s = requests.Session()
    s.headers.update(HEADERS)
    s.get("https://fie.org/competitions", timeout=15)

    # Group by season for efficient searching
    by_season = {}
    for t in tournaments:
        season = int(t.get("season") or datetime.now(timezone.utc).year)
        by_season.setdefault(season, []).append(t)

    current_year = datetime.now(timezone.utc).year
    current_month = datetime.now(timezone.utc).month

    for season, season_tournaments in by_season.items():
        print(f"  Searching season {season} — {len(season_tournaments)} tournaments")

        # Collect ALL items for this season across all months
        all_items = []
        for month in range(1, 13):
            if season == current_year and month > current_month:
                continue
            from_date = f"{season}-{month:02d}-01"
            to_date = f"{season}-{month:02d}-{calendar.monthrange(season, month)[1]}"
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


def filter_tournaments(tournaments, season=None, weapon=None):
    filtered = tournaments or []
    if season is not None:
        filtered = [t for t in filtered if to_int(t.get("season")) == season]
    if weapon:
        weapon = weapon.lower()
        filtered = [t for t in filtered if (t.get("weapon") or "").lower() == weapon]
    return filtered


def discover_urls_main(season=None):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tournaments_no_url = supabase.table("fs_tournaments")\
        .select("id,fie_id,name,season,weapon,gender,start_date")\
        .lte("end_date", today)\
        .eq("is_sub_competition", False)\
        .is_("competition_url_id", "null")\
        .execute().data

    tournaments_no_url = filter_tournaments(tournaments_no_url, season=season)
    print(f"Found {len(tournaments_no_url)} completed tournaments needing URL ID discovery")
    discover_competition_url_ids(tournaments_no_url)


def mark_results_failure(tournament_id, current_failures: int):
    failures = current_failures + 1
    update = {"results_check_failures": failures}
    if failures >= RESULTS_UNAVAILABLE_THRESHOLD:
        update["results_unavailable"] = True
        print(f"    Marking tournament {tournament_id} results_unavailable after {failures} failures")
    supabase.table("fs_tournaments").update(update).eq("id", tournament_id).execute()


def main(season=None, weapon=None, limit=0):
    print(f"Results scraper starting — {datetime.now(timezone.utc).isoformat()}")
    run_log = ScraperRunLogger("scrape_results").start()

    current_year = datetime.now(timezone.utc).year
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    # Get all completed tournaments that don't have results yet
    # and have a competition_url_id; exclude permanently unavailable ones
    tournaments = supabase.table("fs_tournaments")\
        .select("id,fie_id,name,season,weapon,gender,competition_url_id,results_check_failures,results_unavailable")\
        .lte("end_date", today)\
        .eq("is_sub_competition", False)\
        .not_.is_("competition_url_id", "null")\
        .neq("results_unavailable", True)\
        .execute().data

    tournaments = filter_tournaments(tournaments, season=season, weapon=weapon)
    print(f"Found {len(tournaments)} completed tournaments with URL IDs (excluding unavailable)")

    # Also get tournaments without competition_url_id — need to discover them
    tournaments_no_url = supabase.table("fs_tournaments")\
        .select("id,fie_id,name,season,weapon,gender,start_date")\
        .lte("end_date", today)\
        .eq("is_sub_competition", False)\
        .is_("competition_url_id", "null")\
        .neq("results_unavailable", True)\
        .execute().data

    tournaments_no_url = filter_tournaments(tournaments_no_url, season=season, weapon=weapon)
    print(f"Found {len(tournaments_no_url)} completed tournaments needing URL ID discovery")

    # Discover competition_url_ids via FIE search API
    if tournaments_no_url:
        if len(tournaments_no_url) < 10:
            print(f"Only {len(tournaments_no_url)} unmapped — running targeted discovery")
        discover_competition_url_ids(tournaments_no_url)
        # Re-fetch with url ids now populated
        tournaments = supabase.table("fs_tournaments")\
            .select("id,fie_id,name,season,weapon,gender,competition_url_id,results_check_failures,results_unavailable")\
            .lte("end_date", today)\
            .eq("is_sub_competition", False)\
            .not_.is_("competition_url_id", "null")\
            .neq("results_unavailable", True)\
            .execute().data
        tournaments = filter_tournaments(tournaments, season=season, weapon=weapon)

    # Also include currently live tournaments (started but not ended yet)
    live_tournaments = supabase.table("fs_tournaments")\
        .select("id,fie_id,name,season,weapon,gender,competition_url_id,results_check_failures,results_unavailable")\
        .lte("start_date", today)\
        .gte("end_date", today)\
        .eq("is_sub_competition", False)\
        .not_.is_("competition_url_id", "null")\
        .execute().data

    live_tournaments = filter_tournaments(live_tournaments, season=season, weapon=weapon)
    print(f"Found {len(live_tournaments)} live tournaments")
    tournaments = tournaments + live_tournaments

    # Check which already have results (paginated — fs_results can exceed 1000 rows)
    existing_ids: set = set()
    _ex_offset = 0
    while True:
        _page = supabase.table("fs_results").select("tournament_id")\
            .range(_ex_offset, _ex_offset + 999).execute().data or []
        for r in _page:
            if r.get("tournament_id"):
                existing_ids.add(r["tournament_id"])
        if len(_page) < 1000:
            break
        _ex_offset += 1000

    # Always re-scrape recent tournaments (ended within the last 7 days)
    recent_tournaments = supabase.table("fs_tournaments")\
        .select("id")\
        .gte("end_date", week_ago)\
        .lte("end_date", today)\
        .execute().data
    recent_ids = set(r["id"] for r in recent_tournaments)

    # Scrape if: no results yet OR recently ended
    to_scrape = [t for t in tournaments if t["id"] not in existing_ids or t["id"] in recent_ids]
    if limit and limit > 0:
        to_scrape = to_scrape[:limit]
    print(f"{len(to_scrape)} tournaments need results scraped")

    scraped = 0
    failed = 0
    scraped_this_run = set()

    for t in to_scrape:
        tournament_season = int(t.get("season") or current_year)
        url_id = t.get("competition_url_id")
        tournament_id = t["id"]
        current_failures = t.get("results_check_failures") or 0

        # Skip if already scraped this run
        if tournament_id in scraped_this_run:
            print(f"  Skipping {t['name']} — already scraped this run")
            continue
        scraped_this_run.add(tournament_id)
        print(f"  Scraping {t['name']} ({tournament_season}/{url_id})...")

        meta, rows = get_competition_data(tournament_season, url_id)

        if not rows:
            print(f"    No results found")
            mark_results_failure(tournament_id, current_failures)
            failed += 1
            time.sleep(1)
            continue

        # Build result rows
        result_rows = []
        for r in rows:
            if not r.get("name") or not r.get("rank"):
                continue
            result_rows.append({
                "tournament_id": tournament_id,
                "fie_fencer_id": str(r.get("fencerId")) if r.get("fencerId") is not None else None,
                "name": normalize_person_name(r.get("name")),
                "nationality": normalize_country(r.get("nationality")),
                "country": normalize_country(r.get("country") or r.get("nationality")),
                "rank": to_int(r.get("rank")),
                "placement": to_int(r.get("rank")),
                "victory": to_int(r.get("victory")),
                "matches": to_int(r.get("matches")),
                "td": to_int(r.get("td")),
                "tr": to_int(r.get("tr")),
                "diff": to_int(r.get("diff")),
            })

        result_rows = dedupe_result_rows(result_rows)

        if not result_rows:
            print(f"    No valid rows")
            mark_results_failure(tournament_id, current_failures)
            failed += 1
            time.sleep(1)
            continue

        # Fetch existing rows so we can restore them if inserts fail (paginated)
        old_rows: list = []
        _old_offset = 0
        while True:
            _old_page = supabase.table("fs_results").select("*").eq("tournament_id", tournament_id)\
                .range(_old_offset, _old_offset + 999).execute().data or []
            old_rows.extend(_old_page)
            if len(_old_page) < 1000:
                break
            _old_offset += 1000
        supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
        try:
            for i in range(0, len(result_rows), 100):
                supabase.table("fs_results").insert(result_rows[i:i+100]).execute()
        except Exception as insert_exc:
            print(f"    Insert failed: {insert_exc}; restoring {len(old_rows)} existing rows")
            supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
            if old_rows:
                try:
                    for i in range(0, len(old_rows), 100):
                        supabase.table("fs_results").insert(old_rows[i:i+100]).execute()
                except Exception as restore_exc:
                    print(f"    CRITICAL: restore also failed for tournament {tournament_id}: {restore_exc}")
            mark_results_failure(tournament_id, current_failures)
            failed += 1
            time.sleep(1)
            continue

        supabase.table("fs_tournaments").update({
            "has_results": True,
            "results_check_failures": 0,
            "results_unavailable": False,
        }).eq("id", tournament_id).execute()
        print(f"    Inserted {len(result_rows)} results")
        scraped += 1
        time.sleep(0.3)  # be polite to FIE

    run_log.complete(written=scraped, failed=failed)
    print(f"\nDone — {scraped} tournaments scraped, {failed} failed")


def scrape_results(season=None, weapon=None, limit=0):
    return main(season=season, weapon=weapon, limit=limit)


if __name__ == "__main__":
    main()

import os
import requests
from supabase import create_client, Client
from datetime import datetime, date as date_obj
import time
import calendar

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Shared headers ──────────────────────────────────────────────────────────

ATHLETE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/athletes",
}

COMP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/competitions",
}

# ── Fencer scraper ───────────────────────────────────────────────────────────

WEAPONS = [
    {"weapon": "S", "gender": "M", "label": "Men's Sabre"},
    {"weapon": "S", "gender": "F", "label": "Women's Sabre"},
    {"weapon": "E", "gender": "M", "label": "Men's Epee"},
    {"weapon": "E", "gender": "F", "label": "Women's Epee"},
    {"weapon": "F", "gender": "M", "label": "Men's Foil"},
    {"weapon": "F", "gender": "F", "label": "Women's Foil"},
]
WEAPON_MAP = {"S": "Sabre", "E": "Epee", "F": "Foil"}


def scrape_rankings(weapon: str, gender: str, label: str):
    print(f"Scraping {label}...")
    page = 1
    total = 0
    while True:
        payload = {
            "weapon": weapon, "gender": gender, "category": "S",
            "country": "", "name": "", "page": page, "season": "2026",
        }
        try:
            res = requests.post("https://fie.org/athletes", headers=ATHLETE_HEADERS, json=payload, timeout=15)
            res.raise_for_status()
            athletes = res.json().get("allAthletes", [])
            if not athletes:
                break
            rows = []
            for f in athletes:
                fie_id = str(f.get("id", ""))
                name = f.get("name", "").strip()
                if not name or not fie_id:
                    continue
                gender_label = "Women's" if gender == "F" else "Men's"
                points_raw = f.get("points", "0") or "0"
                rows.append({
                    "fie_id": fie_id,
                    "name": name,
                    "country": f.get("country", "").strip(),
                    "weapon": WEAPON_MAP.get(weapon, weapon),
                    "category": f"{gender_label} Senior",
                    "world_rank": f.get("rank"),
                    "fie_points": int(float(points_raw)),
                    "updated_at": datetime.utcnow().isoformat(),
                })
            if rows:
                supabase.table("fs_fencers").upsert(rows, on_conflict="fie_id,weapon").execute()
            total += len(athletes)
            print(f"  Page {page} — {len(athletes)} fencers (total: {total})")
            if len(athletes) < 100:
                break
            page += 1
            time.sleep(1)
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break
    print(f"Done — {label}: {total} fencers")

# ── Competition scraper ──────────────────────────────────────────────────────


def parse_date(d):
    if not d:
        return None
    for fmt in ["%d-%m-%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def make_comp_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; FenceSquare/1.0)"})
    s.get("https://fie.org/competitions", timeout=15)
    return s


def fetch_comp_range(s, from_date, to_date, status="passed", season=0):
    all_items = []
    page = 1
    while True:
        payload = {
            "name": "", "status": status, "gender": [], "weapon": [], "type": [],
            "season": season, "level": "", "competitionCategory": "",
            "fromDate": from_date, "toDate": to_date, "fetchPage": page,
        }
        try:
            res = s.post("https://fie.org/competitions/search", headers=COMP_HEADERS, json=payload, timeout=15)
            if res.status_code != 200 or not res.text.strip():
                return None
            items = res.json().get("items", [])
            if not items:
                break
            all_items.extend(items)
            if len(items) < 300 or page >= 20:
                break
            page += 1
        except Exception as e:
            print(f"  Comp fetch error: {e}")
            return None
    return all_items


def scrape_competitions():
    print("Scraping competitions...")
    s = make_comp_session()
    seen = set()
    all_rows = []

    today = date_obj.today()

    # Past competitions
    for year in range(2010, 2027):
        for month in range(1, 13):
            if year == 2026 and month > 12:
                break
            last_day = calendar.monthrange(year, month)[1]
            from_d = f"{year}-{str(month).zfill(2)}-01"
            to_d   = f"{year}-{str(month).zfill(2)}-{str(last_day).zfill(2)}"
            month_date = date_obj(year, month, last_day)
            status = "passed" if month_date < today else ""
            result = fetch_comp_range(s, from_d, to_d, status=status)
            if result is None:
                s = make_comp_session()
                time.sleep(1)
                result = fetch_comp_range(s, from_d, to_d) or []
            for c in result:
                key = (c["competitionId"], c.get("weapon", ""), c.get("gender", ""))
                if key not in seen:
                    seen.add(key)
                    all_rows.append(c)

    # Upcoming
    result = fetch_comp_range(s, "", "", status="", season=0) or []
    for c in result:
        key = (c["competitionId"], c.get("weapon", ""), c.get("gender", ""))
        if key not in seen:
            seen.add(key)
            all_rows.append(c)

    print(f"  {len(all_rows)} competitions fetched, upserting...")

    rows = []
    for c in all_rows:
        rows.append({
            "fie_id": c["competitionId"],
            "season": c.get("season"),
            "name": c.get("name"),
            "location": c.get("location"),
            "country": c.get("country"),
            "federation": c.get("federation"),
            "flag": c.get("flag"),
            "start_date": parse_date(c.get("startDate")),
            "end_date": parse_date(c.get("endDate")),
            "weapon": c.get("weapon"),
            "weapons": c.get("weapons", []),
            "gender": c.get("gender"),
            "category": c.get("category"),
            "categories": c.get("categories", []),
            "type": c.get("type"),
            "has_results": bool(c.get("hasResults")),
            "is_sub_competition": bool(c.get("isSubCompetition")),
            "is_link": bool(c.get("isLink")),
        })

    # Upsert in batches of 100
    for i in range(0, len(rows), 100):
        supabase.table("fs_tournaments").upsert(
            rows[i:i+100], on_conflict="fie_id,weapon,gender"
        ).execute()

    print(f"Done — competitions: {len(rows)} upserted")

# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    print(f"FenceSquare scraper starting — {datetime.utcnow().isoformat()}")
    for w in WEAPONS:
        scrape_rankings(w["weapon"], w["gender"], w["label"])
        time.sleep(2)
    scrape_competitions()
    print("Scraper complete")


if __name__ == "__main__":
    main()

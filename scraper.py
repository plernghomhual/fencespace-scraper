import os
import requests
from supabase import create_client, Client
from datetime import datetime, date as date_obj, timezone
import time
import calendar
import re

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Shared headers ──────────────────────────────────────────────────────────

ATHLETE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Referer": "https://fie.org/athletes",
}

COMP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/competitions",
}

# ── Fencer scraper ───────────────────────────────────────────────────────────

WEAPON_MAP = {"S": "Sabre", "E": "Epee", "F": "Foil"}
CATEGORY_MAP = {"S": "Senior", "J": "Junior", "C": "Cadet", "V": "Veteran"}

WEAPONS = [
    {
        "weapon": weapon,
        "gender": gender,
        "category": category,
        "label": f"{'Women' if gender == 'F' else 'Men'}'s {category_label} {weapon_label}",
    }
    for weapon, weapon_label in WEAPON_MAP.items()
    for gender in ["M", "F"]
    for category, category_label in CATEGORY_MAP.items()
]


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


def batch_upsert(table: str, rows: list[dict], on_conflict: str, batch_size: int = 100):
    for i in range(0, len(rows), batch_size):
        supabase.table(table).upsert(
            rows[i:i+batch_size], on_conflict=on_conflict
        ).execute()


def scrape_rankings(weapon: str, gender: str, category: str, label: str):
    category_label = CATEGORY_MAP.get(category, category)
    gender_label = "Women's" if gender == "F" else "Men's"
    db_category = f"{gender_label} {category_label}"

    print(f"Scraping {label} ({weapon}/{gender}/{category})...")
    page = 1
    total = 0
    seen_fie_ids: set = set()
    while True:
        payload = {
            "weapon": weapon, "gender": gender, "category": category,
            "country": "", "name": "", "page": page,
            "season": str(datetime.now(timezone.utc).year),
        }
        try:
            res = requests.post("https://fie.org/athletes", headers=ATHLETE_HEADERS, json=payload, timeout=15)
            res.raise_for_status()
            data = res.json()
            athletes = data.get("allAthletes", data.get("topFencers", []))
            if not athletes:
                break
            rows = []
            for f in athletes:
                fie_id = str(f.get("id", ""))
                name = normalize_person_name(f.get("name"))
                if not name or not fie_id:
                    continue
                if fie_id in seen_fie_ids:
                    continue
                seen_fie_ids.add(fie_id)
                points_raw = f.get("points", "0") or "0"
                rows.append({
                    "fie_id": fie_id,
                    "name": name,
                    "country": normalize_country(f.get("country")),
                    "weapon": WEAPON_MAP.get(weapon, weapon),
                    "category": db_category,
                    "world_rank": f.get("rank"),
                    "fie_points": int(float(points_raw)),
                    "image_url": f.get("image"),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
            if rows:
                try:
                    batch_upsert("fs_fencers", rows, on_conflict="fie_id,weapon,category")
                except Exception as upsert_exc:
                    msg = str(upsert_exc)
                    if "23505" in msg or "21000" in msg or "unique" in msg.lower():
                        print(f"  Batch upsert conflict on page {page}, falling back to row-by-row")
                        for row in rows:
                            try:
                                supabase.table("fs_fencers").upsert(
                                    [row], on_conflict="fie_id,weapon,category"
                                ).execute()
                            except Exception as row_exc:
                                print(f"    Row upsert failed for fie_id={row.get('fie_id')}: {row_exc}")
                    else:
                        raise
            total += len(athletes)
            print(f"  Page {page} — {len(athletes)} fencers (total: {total})")
            if len(athletes) < 100:
                break
            page += 1
            time.sleep(1)
        except requests.exceptions.RequestException as e:
            print(f"  Connection error on page {page}: {e}")
            break
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break
    print(f"Done — {label}: {total} fencers")

# ── Competition scraper ──────────────────────────────────────────────────────


def parse_date(d):
    if not d:
        return None
    for fmt in ["%d-%m-%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    print(f"  ⚠️ parse_date FAILED: '{d}'")
    return None


def normalize_date_range(start_date, end_date, label):
    if start_date and end_date and end_date < start_date:
        print(f"  ⚠️ invalid date range for {label}: {start_date} > {end_date}; using start date as end date")
        return start_date, start_date
    return start_date, end_date


def make_comp_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)"})
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
    all_rows = []
    for year in range(2010, datetime.now(timezone.utc).year + 1):
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            from_d = f"{year}-{str(month).zfill(2)}-01"
            to_d   = f"{year}-{str(month).zfill(2)}-{str(last_day).zfill(2)}"
            month_date = date_obj(year, month, last_day)
            status = "passed" if month_date < date_obj.today() else ""
            result = fetch_comp_range(s, from_d, to_d, status=status)
            if result is None:
                s = make_comp_session()
                time.sleep(1)
                result = fetch_comp_range(s, from_d, to_d, status=status) or []
            all_rows.extend(result)

    print(f"  {len(all_rows)} total rows (pre-dedup by Supabase), upserting...")

    rows = []
    for c in all_rows:
        start_date, end_date = normalize_date_range(
            parse_date(c.get("startDate")),
            parse_date(c.get("endDate")),
            c.get("competitionId") or c.get("name") or "competition",
        )
        rows.append({
            "fie_id": c["competitionId"],
            "season": c.get("season"),
            "name": c.get("name"),
            "location": c.get("location"),
            "country": normalize_country(c.get("country")),
            "federation": c.get("federation"),
            "flag": c.get("flag"),
            "start_date": start_date,
            "end_date": end_date,
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

    # Deduplicate by the Supabase upsert conflict key before writing.
    seen = {}
    for r in rows:
        key = r["fie_id"]
        seen[key] = r
    rows = list(seen.values())
    print(f"  {len(rows)} unique rows after dedup")

    # Upsert in batches of 100
    for i in range(0, len(rows), 100):
        supabase.table("fs_tournaments").upsert(
            rows[i:i+100], on_conflict="fie_id"
        ).execute()

    print("Done — competitions upserted")

# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    print(f"FenceSpace scraper starting — {datetime.now(timezone.utc).isoformat()}")
    for index, w in enumerate(WEAPONS, start=1):
        print(f"\nRanking combination {index}/{len(WEAPONS)}")
        scrape_rankings(w["weapon"], w["gender"], w["category"], w["label"])
        if index < len(WEAPONS):
            time.sleep(2)
    scrape_competitions()
    print("Scraper complete")


if __name__ == "__main__":
    main()

import os
import re
import time
from datetime import UTC, datetime, timezone

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

BASE_URL = "https://ncaa.escrimeresults.com"
SOURCE = "ncaa"
REQUEST_DELAY = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
}

# No 2020 (COVID cancellation)
CHAMPIONSHIP_YEARS = [y for y in range(2000, 2027) if y != 2020]

# anchor id → (weapon, gender)
SECTION_MAP = {
    "WS": ("Sabre", "Women"),
    "WF": ("Foil", "Women"),
    "WE": ("Epee", "Women"),
    "MS": ("Sabre", "Men"),
    "MF": ("Foil", "Men"),
    "ME": ("Epee", "Men"),
}


def fetch_year(year):
    url = f"{BASE_URL}/ncaa{year}.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        return r.text if r.status_code == 200 else None
    except Exception as exc:
        print(f"  Fetch failed for {year}: {exc}")
        return None


def parse_section(soup, section_code):
    """Find anchor by name/id, return placement rows from next table.

    Returns list of dicts: rank, name, school, vb, pct, ts, tr_val, ind
    """
    anchor = (
        soup.find("a", attrs={"name": section_code})
        or soup.find("a", attrs={"id": section_code})
    )
    if not anchor:
        return []
    table = anchor.find_next("table")
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        place_raw = cells[0].rstrip(".")
        m = re.match(r"^T?(\d+)$", place_raw)
        if not m:
            continue  # header or non-placement row
        rank = int(m.group(1))
        name = cells[1]
        if not name or name.lower() in ("name", "competitor", "fencer"):
            continue
        school = cells[2] if len(cells) > 2 else None
        vb = cells[3] if len(cells) > 3 else None
        pct = cells[4] if len(cells) > 4 else None
        ts = cells[5] if len(cells) > 5 else None
        tr_val = cells[6] if len(cells) > 6 else None
        ind = cells[7] if len(cells) > 7 else None
        rows.append({
            "rank": rank,
            "name": name,
            "school": school,
            "vb": vb,
            "pct": pct,
            "ts": ts,
            "tr_val": tr_val,
            "ind": ind,
        })
    return rows


def upsert_tournament(year, weapon, gender):
    source_id = f"ncaa:{year}:{weapon.lower()}:{gender.lower()}"
    row = {
        "source_id": source_id,
        "name": f"NCAA Championship {year} — {gender}'s {weapon}",
        "season": str(year),
        "type": "ncaa_championship",
        "weapon": weapon,
        "gender": gender,
        "category": "College",
        "country": "USA",
        "has_results": True,
        "metadata": {
            "year": year,
            "source_url": f"{BASE_URL}/ncaa{year}.html",
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()  # type: ignore[union-attr]
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def upsert_results(tournament_id, result_rows):
    """Delete+reinsert individual placements. Returns total written or 0 on partial failure."""
    db_rows = []
    for r in result_rows:
        db_rows.append({
            "tournament_id": tournament_id,
            "name": r["name"],
            "nationality": "USA",
            "rank": r["rank"],
            "medal": None,
            "fencer_id": None,
            "metadata": {
                "school": r["school"],
                "vb": r["vb"],
                "pct": r["pct"],
                "ts": r["ts"],
                "tr": r["tr_val"],
                "ind": r["ind"],
            },
        })
    if not db_rows:
        return 0
    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()  # type: ignore[union-attr]
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i:i + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()  # type: ignore[union-attr]
            written += len(batch)
        except Exception as exc:
            print(f"  Insert batch failed: {exc}")
    if written < len(db_rows):
        return 0
    return written


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_ncaa").start()
    try:
        print(f"NCAA scraper starting — {datetime.now(UTC).isoformat()}")
        done_years = set(get_state(SOURCE, "done_years") or [])
        written = failed = skipped = 0

        for year in CHAMPIONSHIP_YEARS:
            if year in done_years:
                skipped += 1
                continue
            print(f"\nYear {year}:")
            html = fetch_year(year)
            if not html:
                failed += 1
                continue

            soup = BeautifulSoup(html, "html.parser")
            year_written = 0
            year_failed = 0

            for section_code, (weapon, gender) in SECTION_MAP.items():
                rows = parse_section(soup, section_code)
                if not rows:
                    print(f"  {section_code}: no results found")
                    continue
                t_id = upsert_tournament(year, weapon, gender)
                if not t_id:
                    year_failed += 1
                    continue
                n = upsert_results(t_id, rows)
                if n == 0:
                    year_failed += 1
                    continue
                print(f"  {section_code}: {n} results")
                year_written += n

            failed += year_failed
            written += year_written
            # Only mark done when no section failed and at least one wrote
            if year_failed == 0 and year_written > 0:
                done_years.add(year)
                set_state(SOURCE, "done_years", list(done_years))
            time.sleep(REQUEST_DELAY)

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"\nDone — written={written}, failed={failed}, skipped={skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

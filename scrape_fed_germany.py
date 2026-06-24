"""
scrape_fed_germany.py — German Fencing Federation (DFB) national rankings scraper.

Rankings are hosted on the Ophardt Online platform:
  Index page:  https://fencing.ophardt.online/de/search/rankings/1
  Ranking page: https://fencing.ophardt.online/de/search/rankings/show/<id>

Ranking IDs (verified 2026-05-29):
  Senior Damen  Degen=21203, Florett=21205, Säbel=21207
  Senior Herren Degen=21204, Florett=21206, Säbel=21208
  Junior Damen  Degen=21017, Florett=21023, Säbel=20977   (U20 category)
  Junior Herren Degen=21020, Florett=21026, Säbel=20979   (U20 category)

Table structure (T1, direct <tr> children only):
  Col 0: Platz (rank)
  Col 1: Punkte (points, German decimal comma)
  Col 2: Ü-P (carry-over points, ignored)
  Col 3: Name  (appended with "Detail Biographie..." — strip at "Detail")
  Col 4: Nation
  Col 5: Vereine (club, class="rankingclub")
  Col 6: Jahrgang (birth year, ignored)
  Col 7+: Per-tournament result columns (ignored)
"""

import re
import time
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger
from season_utils import season_to_string

SOURCE = "dfb_germany"
COUNTRY = "GER"
REQUEST_DELAY = 1.5
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)"}

BASE_URL = "https://fencing.ophardt.online/de/search/rankings/show"

# (weapon, gender, category, ophardt_id)
RANKING_COMBOS = [
    ("Foil",  "Men",   "Senior", 21206),
    ("Foil",  "Women", "Senior", 21205),
    ("Epee",  "Men",   "Senior", 21204),
    ("Epee",  "Women", "Senior", 21203),
    ("Sabre", "Men",   "Senior", 21208),
    ("Sabre", "Women", "Senior", 21207),
    ("Foil",  "Men",   "Junior", 21026),
    ("Foil",  "Women", "Junior", 21023),
    ("Epee",  "Men",   "Junior", 21020),
    ("Epee",  "Women", "Junior", 21017),
    ("Sabre", "Men",   "Junior", 20979),
    ("Sabre", "Women", "Junior", 20977),
]


def parse_rankings_table(html: str) -> list[dict]:
    """
    Parse an Ophardt Online ranking page.

    Uses recursive=False on the main ranking table (T1) so nested per-tournament
    detail sub-tables are not traversed; only the top-level fencer rows are visited.

    Returns a list of dicts with keys: rank (int), name (str), club (str|None),
    points (float|None).
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2:
        return []

    # T1 is the main ranking table (T0 is the metadata/info table)
    ranking_table = tables[1]

    # Use recursive=False on <tbody> to get only direct fencer <tr> rows.
    # The nested per-tournament detail sub-tables live inside <td> elements;
    # their <tr> children are NOT direct children of <tbody>, so they are
    # skipped automatically.
    tbody = ranking_table.find("tbody") or ranking_table

    results = []
    for row in tbody.find_all("tr", recursive=False):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 6:
            continue

        rank_text = cells[0].get_text(strip=True)
        if not rank_text.isdigit():
            continue  # Skip header rows

        try:
            rank = int(rank_text)
        except ValueError:
            continue

        # Cell 3 contains: "LASTNAME Firstname Detail Biographie ..."
        # Split at "Detail" to isolate the name.
        name_raw = cells[3].get_text(separator=" ", strip=True)
        name = re.split(r"\s+Detail\b", name_raw)[0].strip()
        if not name:
            continue

        # Cell 5 is the club (class="rankingclub")
        club_raw = cells[5].get_text(strip=True)
        # Club may have multiple clubs separated by ", (" — take the primary one
        club = club_raw or None

        # Cell 1 is points with German decimal comma
        points_text = cells[1].get_text(strip=True).replace(",", ".")
        try:
            points = float(points_text)
        except ValueError:
            points = None

        results.append({
            "rank": rank,
            "name": name,
            "club": club,
            "points": points,
        })

    return results


def fetch_rankings_page(ophardt_id: int) -> str | None:
    """Fetch the Ophardt Online ranking page for the given ID."""
    url = f"{BASE_URL}/{ophardt_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code == 200:
            return r.text
        print(f"    HTTP {r.status_code} for ID {ophardt_id}")
        return None
    except requests.RequestException as exc:
        print(f"    Request failed for ID {ophardt_id}: {exc}")
        return None


def current_season() -> str:
    now = datetime.now(UTC)
    season_end_year = now.year if now.month < 7 else now.year + 1
    return season_to_string(season_end_year)


def main():
    run_log = ScraperRunLogger("scrape_fed_germany").start()
    season = current_season()
    print(f"DFB Germany rankings — season {season}")
    total_written = total_failed = 0

    for weapon, gender, category, ophardt_id in RANKING_COMBOS:
        print(f"  {weapon} {gender} {category} (ID {ophardt_id})...")
        html = fetch_rankings_page(ophardt_id)
        if not html:
            total_failed += 1
            continue

        parsed = parse_rankings_table(html)
        if not parsed:
            print(f"    No rows parsed")
            total_failed += 1
            time.sleep(REQUEST_DELAY)
            continue

        rows = [
            build_ranking_row(
                source=SOURCE,
                season=season,
                weapon=weapon,
                gender=gender,
                category=category,
                rank=r["rank"],
                name=r["name"],
                country=COUNTRY,
                club=r.get("club"),
                points=r.get("points"),
            )
            for r in parsed
        ]
        n = write_rankings(rows, source=SOURCE, season=season)
        print(f"    Written {n} rows")
        total_written += n
        time.sleep(REQUEST_DELAY)

    run_log.complete(written=total_written, failed=total_failed)
    print(f"Done — written={total_written}, failed={total_failed}")


if __name__ == "__main__":
    main()

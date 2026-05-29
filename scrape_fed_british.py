"""
scrape_fed_british.py — British Fencing national rankings scraper.

URL pattern (discovered by probe):
  https://www.britishfencing.com/rankings-v2/<category>-<gender>-<weapon>/

Slug conventions (verified against live site):
  Senior Men:   senior-mixed-mens-<weapon>
  Senior Women: senior-womens-<weapon>
  Junior Men:   junior-mens-<weapon>          (NOT junior-mixed-mens)
  Junior Women: junior-womens-<weapon>

Table columns:
  Rank | Name | Club | Licence | Total Points | Domestic | Domestic # | International | International #
"""

import os
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from fed_rankings_common import build_ranking_row, write_rankings

SOURCE = "british_fencing"
COUNTRY = "GBR"
REQUEST_DELAY = 1.5
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)"}

BASE_URL = "https://www.britishfencing.com/rankings-v2"

RANKING_COMBOS = [
    ("Foil",  "Men",   "Senior"),
    ("Foil",  "Women", "Senior"),
    ("Epee",  "Men",   "Senior"),
    ("Epee",  "Women", "Senior"),
    ("Sabre", "Men",   "Senior"),
    ("Sabre", "Women", "Senior"),
    ("Foil",  "Men",   "Junior"),
    ("Foil",  "Women", "Junior"),
    ("Epee",  "Men",   "Junior"),
    ("Epee",  "Women", "Junior"),
    ("Sabre", "Men",   "Junior"),
    ("Sabre", "Women", "Junior"),
]


def build_slug(weapon: str, gender: str, category: str) -> str:
    """
    Build the URL slug for a given weapon/gender/category combo.

    Examples:
      ("Foil",  "Men",   "Senior") -> "senior-mixed-mens-foil"
      ("Foil",  "Women", "Senior") -> "senior-womens-foil"
      ("Epee",  "Men",   "Junior") -> "junior-mens-epee"
      ("Sabre", "Women", "Junior") -> "junior-womens-sabre"
    """
    cat = category.lower()
    wpn = weapon.lower()
    if gender.lower() == "men":
        # Senior men pages use "mixed-mens"; Junior men pages use just "mens"
        gender_slug = "mixed-mens" if cat == "senior" else "mens"
    else:
        gender_slug = "womens"
    return f"{cat}-{gender_slug}-{wpn}"


def parse_rankings_table(html: str) -> list[dict]:
    """
    Parse a British Fencing rankings-v2 page.

    Returns a list of dicts with keys: rank, name, club, points.
    The table header row (Rank/Name/Club/...) is skipped automatically
    by detecting whether the first cell is a digit.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    results = []
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 5:
            continue
        rank_text = cells[0].get_text(strip=True)
        # Skip header rows (non-numeric rank)
        if not rank_text.isdigit():
            continue
        try:
            rank = int(rank_text)
        except ValueError:
            continue

        name = cells[1].get_text(strip=True)
        club = cells[2].get_text(strip=True) or None

        points_text = cells[4].get_text(strip=True).replace(",", "")
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


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch the rankings HTML for a weapon/gender/category combo."""
    slug = build_slug(weapon, gender, category)
    url = f"{BASE_URL}/{slug}/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code == 200:
            return r.text
        print(f"    HTTP {r.status_code} for {url}")
        return None
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None


def current_season() -> str:
    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year-1}-{year}" if now.month < 7 else f"{year}-{year+1}"


def main():
    run_log = ScraperRunLogger("scrape_fed_british").start()
    season = current_season()
    print(f"British Fencing rankings — season {season}")
    total_written = total_failed = 0

    for weapon, gender, category in RANKING_COMBOS:
        print(f"  {weapon} {gender} {category}...")
        html = fetch_rankings_page(weapon, gender, category)
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

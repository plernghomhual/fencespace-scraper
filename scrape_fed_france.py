"""
scrape_fed_france.py — French Fencing Federation (FFE) national rankings scraper.

Site: https://www.ffescrime.fr/classements/
Discovery pattern:
  1. GET /classements/?arme[{ARME}]={ARME}&sexe[{SEXE}]={SEXE}&categorie={CAT}&niveau=N&saison={YEAR}
     → Returns one /fiche-classements/{id} link (national-level ranking)
  2. GET /fiche-classements/{id}
     → Contains ranking rows in div.section__table-row > div.row__title > ul > li
     Fields (li index): 0=Rang, 1=Nom (last), 2=Prénom (first), 3=Club, 4=Points, 5=arrow (skip)

Category mapping (FFE value for Junior): M20
Season query param: year of end-of-season (e.g. 2026 for 2025/2026)
"""

import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger
from season_utils import season_from_string, season_to_string

SOURCE = "fff_france"
COUNTRY = "FRA"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Referer": "https://www.ffescrime.fr/classements/",
}

BASE_URL = "https://www.ffescrime.fr"
CLASSEMENTS_URL = f"{BASE_URL}/classements/"

# Maps (weapon, gender, category) → (arme_code, sexe_code, categorie_code)
_WEAPON_MAP = {"Foil": "FLE", "Epee": "EPE", "Sabre": "SAB"}
_GENDER_MAP = {"Men": "M", "Women": "F"}
_CATEGORY_MAP = {"Senior": "SENIOR", "Junior": "M20"}

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


def current_season() -> str:
    now = datetime.now(timezone.utc)
    season_end_year = now.year if now.month < 7 else now.year + 1
    return season_to_string(season_end_year)


def _season_year(season: str) -> str:
    """Return the end-year of the season string ('2025-2026' → '2026')."""
    return str(season_from_string(season))


def discover_fiche_id(weapon: str, gender: str, category: str, season_year: str) -> str | None:
    """
    Query the classements filter page to discover the national-level fiche ID
    for a given weapon/gender/category combo in the current season.

    Returns the fiche path string like '/fiche-classements/820', or None if not found.
    """
    arme = _WEAPON_MAP[weapon]
    sexe = _GENDER_MAP[gender]
    cat = _CATEGORY_MAP[category]
    params = {
        f"arme[{arme}]": arme,
        f"sexe[{sexe}]": sexe,
        "categorie": cat,
        "niveau": "N",
        "saison": season_year,
    }
    try:
        r = requests.get(CLASSEMENTS_URL, headers=HEADERS, params=params, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            print(f"    Discovery HTTP {r.status_code}")
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        links = [
            a["href"] for a in soup.find_all("a", href=True)
            if "fiche-classements" in a.get("href", "")
        ]
        if not links:
            print(f"    No fiche-classements link found for {weapon} {gender} {category}")
            return None
        # Take the first link (should be exactly one at niveau=N)
        return links[0]
    except requests.RequestException as exc:
        print(f"    Request error during discovery: {exc}")
        return None


def parse_rankings_table(html: str) -> list[dict]:
    """
    Parse a FFE fiche-classements page.

    The ranking data is server-side rendered in:
      div.section__table-row > div.row__title > ul > li

    li indices (after removing the mobile label span):
      0 = Rang (rank, int)
      1 = Nom (last name)
      2 = Prénom (first name)
      3 = Club
      4 = Points (float)
      5 = arrow (skip)

    Returns a list of dicts with keys: rank, name, club, points.
    Name format: "{LAST_NAME} {First_Name}" (e.g. "JEAN JOSEPH Kendrick").
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("div", class_="section__table-row")
    if not rows:
        return []

    results = []
    for row in rows:
        ul = row.find("ul")
        if not ul:
            continue
        lis = ul.find_all("li")
        if len(lis) < 5:
            continue

        # Extract text from each li, stripping the mobile label span
        vals = []
        for li in lis:
            span = li.find("span", class_="mobile-libelle-detail-classement")
            if span:
                span.decompose()
            vals.append(li.get_text(strip=True))

        rank_text = vals[0]
        if not rank_text.isdigit():
            continue
        try:
            rank = int(rank_text)
        except ValueError:
            continue

        last_name = vals[1].strip()
        first_name = vals[2].strip()
        name = f"{last_name} {first_name}".strip() if first_name else last_name
        club = vals[3].strip() or None

        points_text = vals[4].replace(",", ".").strip()
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


def fetch_rankings_page(weapon: str, gender: str, category: str, season_year: str) -> str | None:
    """
    Discover the fiche-classements ID for the given combo, then fetch its HTML.
    Returns the page HTML string, or None on failure.
    """
    fiche_path = discover_fiche_id(weapon, gender, category, season_year)
    if not fiche_path:
        return None
    url = BASE_URL + fiche_path
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        if r.status_code == 200:
            return r.text
        print(f"    HTTP {r.status_code} for {url}")
        return None
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None


def main():
    run_log = ScraperRunLogger("scrape_fed_france").start()
    season = current_season()
    season_year = _season_year(season)
    print(f"FFE France rankings — season {season} (year param: {season_year})")
    total_written = total_failed = 0

    for weapon, gender, category in RANKING_COMBOS:
        print(f"  {weapon} {gender} {category}...")
        html = fetch_rankings_page(weapon, gender, category, season_year)
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
        print(f"    Written {n} rows ({len(parsed)} parsed)")
        total_written += n
        time.sleep(REQUEST_DELAY)

    run_log.complete(written=total_written, failed=total_failed)
    print(f"Done — written={total_written}, failed={total_failed}")


if __name__ == "__main__":
    main()

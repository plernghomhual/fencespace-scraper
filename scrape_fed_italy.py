"""
scrape_fed_italy.py — Italian Fencing Federation (Federscherma) national rankings scraper.

Site: https://federscherma.it/
Probe findings (2026-05-29):
  - The site is a WordPress CMS. All "classifiche/" paths redirect to an old 2010 news post.
  - Olympic weapon rankings (Foil/Epee/Sabre) are NOT exposed as structured HTML tables.
  - Rankings exist as legacy .xls (BIFF format) files served via the WordPress document manager
    plugin at: /wp-content/plugins/if_document_manager/forceDownload.php?ID_file=<ID>
  - The only accessible "Ranking" section is Paralympic rankings (wheelchair fencing), which
    also uses the same forceDownload XLS distribution.
  - No xlrd/openpyxl library is installed in this venv; BIFF XLS parsing is not possible
    without adding a dependency.

Current behaviour:
  fetch_rankings_page() returns None for all 12 combos — the scraper logs all as failed.
  parse_rankings_table() contains a fully working generic HTML table parser for Italian column
  headers (Pos/Posizione=rank, Atleta/Nome=name, Società/Societa/Club=club, Punti=points).
  This parser will work immediately if Federscherma ever publishes ranked HTML tables.

To enable live scraping, install xlrd or openpyxl and implement XLS parsing in
fetch_rankings_page() / parse_xls_rankings_file().
"""

import os
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from fed_rankings_common import build_ranking_row, write_rankings

SOURCE = "fis_italy"
COUNTRY = "ITA"
REQUEST_DELAY = 1.5
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)"}

BASE_URL = "https://federscherma.it"

# Italian column header aliases → normalised key
_RANK_HEADERS = {"pos", "posizione", "rank", "#"}
_NAME_HEADERS = {"atleta", "nome", "athlete", "name"}
_CLUB_HEADERS = {"società", "societa", "club", "società sportiva", "affiliazione"}
_POINTS_HEADERS = {"punti", "points", "punteggio", "pt", "pts"}

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


def _parse_points(raw: str) -> float | None:
    """
    Parse a points string into a float.

    Handles:
    - Comma as thousands separator: "1,250" → 1250.0
    - Comma as decimal separator: "1,5" → 1.5
    - Dot as thousands separator: "1.250" → 1250.0  (3-digit group)
    - Standard floats: "1250", "1250.5"
    """
    s = raw.strip().replace(" ", "")
    if not s:
        return None
    # Detect thousands-separator comma: digit,exactly-3-digits (possibly more groups)
    # e.g. "1,250" or "1,250,000"
    if re.match(r"^\d{1,3}(,\d{3})+$", s):
        s = s.replace(",", "")
    # Detect thousands-separator dot: same pattern with dot
    elif re.match(r"^\d{1,3}(\.\d{3})+$", s):
        s = s.replace(".", "")
    # Comma as decimal separator (e.g. "1,5")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _normalise_header(text: str) -> str:
    """Lowercase, strip accents lightly, remove punctuation for header matching."""
    return re.sub(r"[^\w\s]", "", text.lower().strip())


def _detect_columns(header_cells: list[str]) -> dict[str, int]:
    """
    Given a list of header cell texts, return a mapping:
      rank_col, name_col, club_col, points_col → column index.
    Returns only the keys that were matched.
    """
    mapping = {}
    for idx, raw in enumerate(header_cells):
        key = _normalise_header(raw)
        if key in _RANK_HEADERS and "rank_col" not in mapping:
            mapping["rank_col"] = idx
        elif key in _NAME_HEADERS and "name_col" not in mapping:
            mapping["name_col"] = idx
        elif key in _CLUB_HEADERS and "club_col" not in mapping:
            mapping["club_col"] = idx
        elif key in _POINTS_HEADERS and "points_col" not in mapping:
            mapping["points_col"] = idx
    return mapping


def parse_rankings_table(html: str) -> list[dict]:
    """
    Parse an Italian-style fencing rankings HTML page.

    Supports two column-detection strategies:
    1. Header-based: detects Italian/English headers (Pos/Posizione, Atleta/Nome,
       Società, Punti) and maps them to rank/name/club/points.
    2. Positional fallback: assumes first numeric column = rank, second text = name,
       third text = club, last numeric = points — same convention as British scraper.

    Returns a list of dicts: {rank: int, name: str, club: str|None, points: float|None}
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    results = []
    col_map: dict[str, int] = {}
    header_detected = False

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        texts = [c.get_text(strip=True) for c in cells]

        # Try to detect header row
        if not header_detected:
            candidate = _detect_columns(texts)
            if "rank_col" in candidate and "name_col" in candidate:
                col_map = candidate
                header_detected = True
                continue  # skip the header row itself
            # Positional fallback: check if first cell is a digit
            if texts and texts[0].isdigit():
                # No header found yet, use positional convention
                header_detected = True
                col_map = {}  # empty = positional mode

        if not header_detected:
            continue

        # Positional mode (no headers found)
        if not col_map:
            if len(texts) < 2:
                continue
            rank_text = texts[0]
            if not rank_text.isdigit():
                continue
            try:
                rank = int(rank_text)
            except ValueError:
                continue
            name = texts[1]
            club = texts[2] if len(texts) > 2 else None
            points = _parse_points(texts[-1]) if len(texts) >= 4 else None
            results.append({
                "rank": rank,
                "name": name,
                "club": club or None,
                "points": points,
            })
            continue

        # Header-based mode
        if len(texts) <= max(col_map.values()):
            continue

        rank_text = texts[col_map["rank_col"]]
        if not rank_text.isdigit():
            continue
        try:
            rank = int(rank_text)
        except ValueError:
            continue

        name = texts[col_map["name_col"]]
        club = texts[col_map["club_col"]].strip() if "club_col" in col_map else None
        if "points_col" in col_map:
            points = _parse_points(texts[col_map["points_col"]])
        else:
            points = None

        results.append({
            "rank": rank,
            "name": name,
            "club": club or None,
            "points": points,
        })

    return results


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """
    Attempt to fetch an Italian national ranking HTML page for the given combo.

    Current status: federscherma.it does not expose Olympic weapon rankings as HTML
    tables. All /classifiche/ and /ranking/ paths redirect to an unrelated 2010 news
    post. Rankings are distributed as legacy XLS files via a WordPress document manager
    plugin which requires xlrd/openpyxl (not installed in this venv).

    Returns None for all combos until the site structure improves or XLS parsing
    is added.
    """
    # Placeholder: no publicly accessible structured ranking page found.
    # Returning None causes the main loop to count this as a failed/skipped combo.
    return None


def current_season() -> str:
    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year-1}-{year}" if now.month < 7 else f"{year}-{year+1}"


def main():
    run_log = ScraperRunLogger("scrape_fed_italy").start()
    season = current_season()
    print(f"FIS Italy rankings — season {season}")
    print(
        "NOTE: federscherma.it does not expose structured HTML rankings.\n"
        "      Rankings are stored as legacy XLS files (requires xlrd/openpyxl).\n"
        "      All combos will be recorded as failed/unavailable."
    )
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

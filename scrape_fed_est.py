"""
scrape_fed_est.py - Eesti Vehklemisliit national rankings scraper.

Probe summary, 2026-06-02:
  - https://efl.ee/ is Eesti Fusioterapeutide Liit, not fencing.
  - Public fencing rankings are HTML TablePress pages under:
      https://vehklemisliit.ee/edetabelid/
  - GET returns text/html. Public 2025-2026 pages:
      /2025-2026-edetabel-mehed/
      /2025-2026-edetabel-naised/
      /2025-2026-edetabel-u20-mehed/
      /2025-2026-edetabel-u20-naised/
  - Weapon-specific foil/epee/sabre slugs returned 404 during probe.
    Estonia's public pages are mapped to Epee only; Foil/Sabre combos are
    attempted and reported as missing public ranking URLs.
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

try:
    from season_utils import normalize_season
except ImportError:  # pragma: no cover - compatibility fallback for isolated use
    normalize_season = None


SOURCE = "est_fencing"
COUNTRY = "Estonia"
BASE_URL = "https://vehklemisliit.ee"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "et-EE,et;q=0.9,en;q=0.7",
    "Referer": "https://vehklemisliit.ee/edetabelid/",
}

RANKING_COMBOS = [
    ("Foil", "Men", "Senior"),
    ("Foil", "Women", "Senior"),
    ("Epee", "Men", "Senior"),
    ("Epee", "Women", "Senior"),
    ("Sabre", "Men", "Senior"),
    ("Sabre", "Women", "Senior"),
    ("Foil", "Men", "Junior"),
    ("Foil", "Women", "Junior"),
    ("Epee", "Men", "Junior"),
    ("Epee", "Women", "Junior"),
    ("Sabre", "Men", "Junior"),
    ("Sabre", "Women", "Junior"),
]

CATEGORY_SLUGS = {
    ("Senior", "Men"): "edetabel-mehed",
    ("Senior", "Women"): "edetabel-naised",
    ("Junior", "Men"): "edetabel-u20-mehed",
    ("Junior", "Women"): "edetabel-u20-naised",
}

RANK_HEADERS = {"koht", "rank", "ranking", "pos", "nr"}
NAME_HEADERS = {"nimi", "name", "vehkleja", "sportlane"}
CLUB_HEADERS = {"klubi", "club"}
POINT_HEADERS = {"punktid", "points", "total", "total points", "kokku"}
SKIP_TOKENS = {"dns", "dq", "dsq", "dnf"}
SUMMARY_NAMES = {"kokku", "punktid", "stardipunktid", "summary", "total"}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def _ascii_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(value).casefold())
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9 ]+", " ", without_marks).strip()


def _parse_rank(value: str) -> int | None:
    value = _clean_text(value)
    if not re.fullmatch(r"\d+", value):
        return None
    return int(value)


def _parse_points(value: str) -> float | None:
    cleaned = _clean_text(value).replace(",", ".")
    cleaned = cleaned.replace("*", "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _detect_columns(cells: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(cells):
        key = _ascii_key(cell)
        if key in RANK_HEADERS and "rank" not in mapping:
            mapping["rank"] = idx
        elif key in NAME_HEADERS and "name" not in mapping:
            mapping["name"] = idx
        elif key in CLUB_HEADERS and "club" not in mapping:
            mapping["club"] = idx
        elif key in POINT_HEADERS and "points" not in mapping:
            mapping["points"] = idx
    if {"rank", "name", "points"}.issubset(mapping):
        return mapping
    return None


def _row_should_skip(cells: list[str], name: str) -> bool:
    row_key = _ascii_key(" ".join(cells))
    tokens = set(row_key.split())
    name_key = _ascii_key(name)
    return bool(tokens & SKIP_TOKENS) or name_key in SUMMARY_NAMES


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Eesti Vehklemisliit ranking tables into rank/name/club/points rows."""
    if not html_or_text or not _clean_text(html_or_text):
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []

    results: list[dict] = []
    for table in tables:
        columns: dict[str, int] | None = None
        for row in table.find_all("tr"):
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
            if not cells:
                continue

            detected = _detect_columns(cells)
            if detected:
                columns = detected
                continue
            if columns is None:
                continue
            if max(columns.values()) >= len(cells):
                continue

            rank = _parse_rank(cells[columns["rank"]])
            if rank is None:
                continue

            name = cells[columns["name"]]
            club = cells[columns["club"]] if "club" in columns and columns["club"] < len(cells) else None
            points = _parse_points(cells[columns["points"]])
            if not name or points is None or _row_should_skip(cells, name):
                continue

            results.append({"rank": rank, "name": name, "club": club or None, "points": points})

    return results


def current_season() -> str:
    now = datetime.now(timezone.utc)
    season_end_year = now.year if now.month < 7 else now.year + 1
    if normalize_season is not None:
        return normalize_season(season_end_year)
    return f"{season_end_year - 1:04d}-{season_end_year:04d}"


def ranking_url_for(weapon: str, gender: str, category: str) -> str | None:
    if weapon != "Epee":
        return None
    slug = CATEGORY_SLUGS.get((category, gender))
    if not slug:
        return None
    return urljoin(BASE_URL, f"/{current_season()}-{slug}/")


def _has_ranking_table(html: str) -> bool:
    return bool(parse_rankings_table(html))


def _looks_blocked_or_unusable(html: str) -> bool:
    soup = BeautifulSoup(html or "", "html.parser")
    if soup.find("table"):
        return False
    text = _ascii_key(soup.get_text(" ", strip=True))
    blocked_markers = (
        "logi sisse",
        "login required",
        "palun logi sisse",
        "enable javascript",
        "please enable javascript",
        "lehte ei leitud",
        "sellist lehekulge ei eksisteeri",
    )
    return any(marker in text for marker in blocked_markers)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    url = ranking_url_for(weapon, gender, category)
    if not url:
        print(f"No public Estonia ranking URL for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=30)
    except requests.RequestException as exc:
        print(f"Network error for {weapon} {gender} {category}: {exc}")
        return None

    if response.status_code == 404:
        print(f"No scrapeable rankings at {url}")
        return None
    if response.status_code in {401, 403}:
        print(f"Blocked rankings page at {url}: HTTP {response.status_code}")
        return None
    if response.status_code >= 400:
        print(f"Failed rankings page at {url}: HTTP {response.status_code}")
        return None

    html = response.text
    if _looks_blocked_or_unusable(html) or not _has_ranking_table(html):
        print(f"No scrapeable rankings at {url}")
        return None
    return html


def main():
    run_log = ScraperRunLogger("scrape_fed_est").start()
    season = current_season()
    print(f"Estonia federation rankings - season {season}")

    total_written = 0
    failed_combos: list[str] = []
    skipped_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            label = f"{weapon} {gender} {category}"
            print(f"  {label}...")
            url = ranking_url_for(weapon, gender, category)
            html = fetch_rankings_page(weapon, gender, category)
            if not html:
                if url:
                    failed_combos.append(label)
                else:
                    skipped_combos.append(label)
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(html)
            if not parsed:
                print("    No rows parsed")
                failed_combos.append(label)
                time.sleep(REQUEST_DELAY)
                continue

            rows = [
                build_ranking_row(
                    source=SOURCE,
                    season=season,
                    weapon=weapon,
                    gender=gender,
                    category=category,
                    rank=row["rank"],
                    name=row["name"],
                    country=COUNTRY,
                    club=row.get("club"),
                    points=row.get("points"),
                    metadata={"url": url},
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            total_written += written
            print(f"    Parsed {len(parsed)} rows; written {written}")
            time.sleep(REQUEST_DELAY)

        metadata = {
            "failed_combos": failed_combos,
            "skipped_combos": skipped_combos,
            "working_combos": len(RANKING_COMBOS) - len(failed_combos) - len(skipped_combos),
            "probe_url": "https://vehklemisliit.ee/edetabelid/",
            "format": "html",
        }
        run_log.complete(
            written=total_written,
            failed=len(failed_combos),
            skipped=len(skipped_combos),
            metadata=metadata,
        )
        print(
            "Done - "
            f"written={total_written}, failed={len(failed_combos)}, skipped={len(skipped_combos)}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

"""
scrape_fed_fin.py — Finland national federation rankings scraper.

Probe findings, 2026-06-01:
  - https://fencing.fi/ranking, /rankingit, /kilpailu/ranking, /tulokset timed out.
  - Current public federation page:
      https://www.fencing-pentathlon.fi/miekkailu/kilpailutoiminta/miekkailun_ranking/
  - It links to Ophardt public ranking search:
      https://fencing.ophardt.online/en/search/rankings/11
  - Current public rankings are GET text/html pages:
      https://fencing.ophardt.online/en/search/rankings/show/<id>
  - Public Kansallinen ranking pages exist for 10/12 Senior/U20 combos.
    Missing from the current public listing: Junior Foil Men, Junior Foil Women.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "fin_fencing"
COUNTRY = "FIN"
BASE_URL = "https://fencing.ophardt.online/en/search/rankings/show"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fi,en;q=0.9",
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

# Public Kansallinen ranking pages from the current Ophardt search listing.
RANKING_URLS = {
    ("Foil", "Men", "Senior"): f"{BASE_URL}/21304",
    ("Foil", "Women", "Senior"): f"{BASE_URL}/21288",
    ("Epee", "Men", "Senior"): f"{BASE_URL}/21286",
    ("Epee", "Women", "Senior"): f"{BASE_URL}/21271",
    ("Sabre", "Men", "Senior"): f"{BASE_URL}/21446",
    ("Sabre", "Women", "Senior"): f"{BASE_URL}/21442",
    ("Epee", "Men", "Junior"): f"{BASE_URL}/21285",
    ("Epee", "Women", "Junior"): f"{BASE_URL}/21146",
    ("Sabre", "Men", "Junior"): f"{BASE_URL}/21445",
    ("Sabre", "Women", "Junior"): f"{BASE_URL}/21441",
}

MISSING_PUBLIC_COMBOS = [
    ("Foil", "Men", "Junior"),
    ("Foil", "Women", "Junior"),
]

RANK_HEADER_ALIASES = {"rank", "sija", "sijoitus"}
NAME_HEADER_ALIASES = {"name", "nimi", "miekkailija", "fencer"}
CLUB_HEADER_ALIASES = {"club", "clubs", "seura", "seurat"}
POINTS_HEADER_ALIASES = {"points", "point", "pisteet", "piste", "totalpoints"}
SKIP_RANK_VALUES = {"dns", "dnf", "dq", "dsq", "wd", "wdr", "yhteensä", "total", "summary"}
DETAIL_LINK_TEXTS = {"details", "biography"}


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _header_key(value: str) -> str:
    return re.sub(r"[^a-zåäö]", "", _clean_text(value).lower())


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value).lower().strip(".")
    if not text or text in SKIP_RANK_VALUES:
        return None
    if any(token in text for token in SKIP_RANK_VALUES):
        return None
    match = re.match(r"^(\d+)", text)
    return int(match.group(1)) if match else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        head, tail = text.rsplit(",", 1)
        if len(tail) in (1, 2):
            text = f"{head.replace(',', '')}.{tail}"
        else:
            text = text.replace(",", "")

    try:
        return float(text)
    except ValueError:
        return None


def _top_level_rows(table: Tag) -> list[Tag]:
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _row_cells(row: Tag) -> list[Tag]:
    return row.find_all(["td", "th"], recursive=False)


def _find_header_mapping(labels: Iterable[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, label in enumerate(labels):
        key = _header_key(label)
        if key in RANK_HEADER_ALIASES:
            mapping["rank"] = index
        elif key in NAME_HEADER_ALIASES:
            mapping["name"] = index
        elif key in CLUB_HEADER_ALIASES:
            mapping["club"] = index
        elif key in POINTS_HEADER_ALIASES:
            mapping["points"] = index

    required = {"rank", "name", "points"}
    return mapping if required.issubset(mapping) else None


def _name_from_cell(cell: Tag) -> str:
    dropdown = cell.find("a", class_="dropdown-toggle")
    if dropdown:
        return _clean_text(dropdown.get_text(" ", strip=True))

    cell = BeautifulSoup(str(cell), "html.parser")
    for unwanted in cell.select(".modal, .dropdown-menu, script, style"):
        unwanted.decompose()

    candidate_links = [
        _clean_text(link.get_text(" ", strip=True))
        for link in cell.find_all("a")
        if _clean_text(link.get_text(" ", strip=True)).lower() not in DETAIL_LINK_TEXTS
    ]
    if candidate_links:
        return candidate_links[0]
    return _clean_text(cell.get_text(" ", strip=True))


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Finnish federation/Ophardt ranking HTML into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        rows = _top_level_rows(table)
        for header_index, header_row in enumerate(rows):
            header_cells = _row_cells(header_row)
            if not header_cells:
                continue
            header_labels = [cell.get_text(" ", strip=True) for cell in header_cells]
            mapping = _find_header_mapping(header_labels)
            if not mapping:
                continue

            for row in rows[header_index + 1:]:
                cells = _row_cells(row)
                if len(cells) <= max(mapping.values()):
                    continue

                rank = _parse_rank(cells[mapping["rank"]].get_text(" ", strip=True))
                if rank is None:
                    continue

                name = _name_from_cell(cells[mapping["name"]])
                if not name:
                    continue

                club = None
                if "club" in mapping:
                    club = _clean_text(cells[mapping["club"]].get_text(" ", strip=True)) or None

                results.append(
                    {
                        "rank": rank,
                        "name": name,
                        "club": club,
                        "points": _parse_points(cells[mapping["points"]].get_text(" ", strip=True)),
                    }
                )

    return results


def ranking_url_for(weapon: str, gender: str, category: str) -> str | None:
    return RANKING_URLS.get((weapon, gender, category))


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public Finland ranking page, returning None for missing/failed combos."""
    url = ranking_url_for(weapon, gender, category)
    if not url:
        print(f"    No public ranking URL for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code == 200:
        return response.text

    print(f"    HTTP {response.status_code} for {url}")
    return None


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY, using season_utils if present."""
    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "current_fie_season"):
            season = season_utils.current_fie_season()
            if hasattr(season_utils, "normalize_season"):
                return season_utils.normalize_season(season)
            if hasattr(season_utils, "season_to_string"):
                return season_utils.season_to_string(season)

        if hasattr(season_utils, "current_season"):
            season = season_utils.current_season()
            if hasattr(season_utils, "normalize_season"):
                return season_utils.normalize_season(season)
            return str(season)
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    return f"{now.year - 1}-{now.year}" if now.month < 7 else f"{now.year}-{now.year + 1}"


def _combo_label(combo: tuple[str, str, str]) -> str:
    weapon, gender, category = combo
    return f"{weapon} {gender} {category}"


def main():
    run_log = ScraperRunLogger("scrape_fed_fin").start()
    season = current_season()
    print(f"Finland federation rankings — season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos: list[str] = []
    failed_combos: list[str] = []
    missing_combos: list[str] = []
    inferred_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            combo = (weapon, gender, category)
            label = _combo_label(combo)
            url = ranking_url_for(weapon, gender, category)
            print(f"  {label}...")

            if not url:
                print("    Missing public listing")
                missing_combos.append(label)
                total_skipped += 1
                continue

            html = fetch_rankings_page(weapon, gender, category)
            if html is None:
                failed_combos.append(label)
                total_failed += 1
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(html)
            if not parsed:
                print("    No rows parsed")
                failed_combos.append(label)
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
                    rank=row["rank"],
                    name=row["name"],
                    country=COUNTRY,
                    club=row.get("club"),
                    points=row.get("points"),
                    metadata={
                        "source_url": url,
                        "ranking_name": "Kansallinen ranking",
                        "country_page": "https://www.fencing-pentathlon.fi/miekkailu/kilpailutoiminta/miekkailun_ranking/",
                        "inferred_combo": False,
                    },
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Parsed {len(parsed)} rows; written {written}")
            total_written += written
            working_combos.append(label)
            time.sleep(REQUEST_DELAY)

        metadata = {
            "combos_working": len(working_combos),
            "combos_total": len(RANKING_COMBOS),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
            "missing_public_combos": missing_combos,
            "inferred_combos": inferred_combos,
        }
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=metadata,
        )
        print(
            f"Done — written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"combos_working={len(working_combos)}/{len(RANKING_COMBOS)}, "
            f"inferred_combos={inferred_combos}"
        )
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
        if missing_combos:
            print(f"Missing public combos: {', '.join(missing_combos)}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

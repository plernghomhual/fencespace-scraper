"""
scrape_fed_hun.py — Hungarian Fencing Federation (MVSZ) rankings scraper.

Probe findings (2026-06-01):
  - Main federation site: https://hunfencing.hu/
  - /ranglistak and /rankings return 404 on hunfencing.hu.
  - The public rankings link points to:
      https://versenyinfo.hunfencing.hu/index.php?p=pRanglista
  - Rankings are server-rendered HTML via GET parameters:
      p=pRanglista, szezon=<season_id>, kor=<category_id>,
      nem=<gender_id>, fegyver=<weapon_id>, submit=Mutat
  - 2025/2026 season_id is 15. Season IDs are start_year - 2010.
  - All 12 Senior/Junior Foil/Epee/Sabre Men/Women combos are public HTML tables.
  - Table columns: Rang | Név | Egyesület | Szül. dátum | Korosztály | Σ
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "hun_fencing"
COUNTRY = "HUN"
BASE_URL = "https://versenyinfo.hunfencing.hu/index.php"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "hu-HU,hu;q=0.9,en-US;q=0.7,en;q=0.6",
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

_WEAPON_PARAMS = {"Sabre": "1", "Foil": "2", "Epee": "3"}
_GENDER_PARAMS = {"Men": "1", "Women": "2"}
_CATEGORY_PARAMS = {"Senior": "10", "Junior": "9"}

_RANK_HEADERS = {"rang", "helyezes", "rank", "#"}
_NAME_HEADERS = {"nev", "name", "versenyzo", "vivo", "sportolo"}
_CLUB_HEADERS = {"egyesulet", "klub", "club", "egyesulet neve"}
_POINTS_HEADERS = {"σ", "Σ", "pont", "pontszam", "pontok", "points", "osszesen", "sum"}
_SKIP_ROW_MARKERS = (
    "dns",
    "dnf",
    "dq",
    "kizart",
    "visszalepett",
    "nem indult",
    "osszesen",
    "summary",
    "total",
)


def _strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)
    )


def _normalise_header(value: str) -> str:
    text = _strip_accents(value).lower().replace(".", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _detect_columns(header_cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
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


def _parse_rank(raw: str) -> int | None:
    match = re.match(r"^\s*(\d+)\.?\s*$", raw)
    if not match:
        return None
    return int(match.group(1))


def _parse_points(raw: str) -> float | None:
    text = raw.replace("\xa0", " ").strip()
    if not text:
        return None

    cleaned = re.sub(r"\s+", "", text)
    cleaned = re.sub(r"[^\d,.\-]", "", cleaned)
    if not cleaned or cleaned in {"-", ",", "."}:
        return None

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        if re.match(r"^-?\d{1,3}(,\d{3})+$", cleaned):
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(",", ".")
    elif "." in cleaned and re.match(r"^-?\d{1,3}(\.\d{3})+$", cleaned):
        cleaned = cleaned.replace(".", "")

    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_skip_row(cells: list[str]) -> bool:
    text = _strip_accents(" ".join(cells)).lower()
    return any(marker in text for marker in _SKIP_ROW_MARKERS)


def _cell_texts(row) -> list[str]:
    return [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]


def _parse_table(table) -> list[dict]:
    results: list[dict] = []
    col_map: dict[str, int] = {}
    header_detected = False

    for row in table.find_all("tr"):
        texts = _cell_texts(row)
        if not texts:
            continue

        if not header_detected:
            candidate = _detect_columns(texts)
            if "rank_col" in candidate and "name_col" in candidate:
                col_map = candidate
                header_detected = True
                continue

            if len(texts) >= 2 and _parse_rank(texts[0]) is not None:
                header_detected = True
                col_map = {"rank_col": 0, "name_col": 1}
                if len(texts) > 2:
                    col_map["club_col"] = 2
                if len(texts) > 3:
                    col_map["points_col"] = len(texts) - 1

        if not header_detected or _is_skip_row(texts):
            continue

        if len(texts) <= max(col_map.values()):
            continue

        rank = _parse_rank(texts[col_map["rank_col"]])
        if rank is None:
            continue

        name = texts[col_map["name_col"]].strip()
        if not name:
            continue

        club = texts[col_map["club_col"]].strip() if "club_col" in col_map else None
        points = _parse_points(texts[col_map["points_col"]]) if "points_col" in col_map else None

        results.append(
            {
                "rank": rank,
                "name": name,
                "club": club or None,
                "points": points,
            }
        )

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse an MVSZ rankings HTML table.

    Returns rows with keys: rank, name, club, points. Supports Hungarian
    headers (Rang/Helyezés, Név, Egyesület, Pont/Σ), UTF-8 names, decimal
    commas, and skips DNS/DQ/summary rows.
    """
    if not html_or_text:
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    results: list[dict] = []
    for table in soup.find_all("table"):
        results.extend(_parse_table(table))
    return results


def _season_to_site_id(season: str) -> str:
    start_year = int(season.replace("/", "-").split("-", 1)[0])
    return str(start_year - 2010)


def current_season() -> str:
    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "current_season"):
            raw = season_utils.current_season()
        elif hasattr(season_utils, "current_fie_season"):
            raw = season_utils.current_fie_season()
        else:
            raw = None

        if raw is not None:
            if hasattr(season_utils, "normalize_season"):
                return season_utils.normalize_season(raw)
            if isinstance(raw, int) and hasattr(season_utils, "season_to_string"):
                return season_utils.season_to_string(raw)
            return str(raw).replace("/", "-")
    except (ImportError, AttributeError, ValueError, TypeError):
        pass

    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def _build_params(weapon: str, gender: str, category: str) -> dict[str, str]:
    season_id = _season_to_site_id(current_season())
    return {
        "p": "pRanglista",
        "szezon": season_id,
        "kor": _CATEGORY_PARAMS[category],
        "nem": _GENDER_PARAMS[gender],
        "fegyver": _WEAPON_PARAMS[weapon],
        "submit": "Mutat",
    }


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """
    Fetch one Hungary rankings page.

    Returns page HTML on success, or None for 404/network errors. Transient
    network/server failures get one short retry before the combo is skipped.
    """
    try:
        params = _build_params(weapon, gender, category)
    except (KeyError, ValueError) as exc:
        print(f"    Invalid combo {weapon} {gender} {category}: {exc}")
        return None

    for attempt in range(2):
        try:
            response = requests.get(
                BASE_URL,
                params=params,
                headers=HEADERS,
                timeout=20,
                allow_redirects=True,
            )
            if response.status_code == 200:
                return response.text
            print(f"    HTTP {response.status_code} for {response.url}")
            if response.status_code == 404:
                return None
        except requests.RequestException as exc:
            print(f"    Request error for {weapon} {gender} {category}: {exc}")

        if attempt == 0:
            time.sleep(REQUEST_DELAY)

    return None


def main():
    run_log = ScraperRunLogger("scrape_fed_hun").start()
    try:
        season = current_season()
        print(f"Hungary MVSZ rankings — season {season}")
        total_written = total_failed = total_skipped = 0
        parsed_total = 0
        failed_combos: list[str] = []
        skipped_combos: list[str] = []

        for idx, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_name = f"{weapon} {gender} {category}"
            print(f"  {combo_name}...")
            html = fetch_rankings_page(weapon, gender, category)
            if not html:
                total_failed += 1
                failed_combos.append(combo_name)
            else:
                parsed = parse_rankings_table(html)
                if not parsed:
                    print("    No rows parsed")
                    total_skipped += 1
                    skipped_combos.append(combo_name)
                else:
                    parsed_total += len(parsed)
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
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    print(f"    Written {written} rows ({len(parsed)} parsed)")
                    total_written += written

            if idx < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "parsed": parsed_total,
                "failed_combos": failed_combos,
                "skipped_combos": skipped_combos,
            },
        )
        print(
            "Done — "
            f"written={total_written}, parsed={parsed_total}, "
            f"failed={total_failed}, skipped={total_skipped}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

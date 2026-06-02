"""
scrape_fed_nor.py — Norges Fekteforbund national rankings scraper.

Probe findings (2026-06-01):
  - https://www.fencing.no and https://fencing.no do not resolve.
  - The live federation site is https://www.fekting.no/.
  - The ranking page is https://www.fekting.no/next/p/24263/ranking.
  - That page has no rankings table or embedded Google Sheet; it links to
    https://fencing.ophardt.online/en/search/rankings/7.
  - Ophardt serves public, server-rendered HTML ranking pages via GET.
  - Public 2025/2026 "Norges Rankinglister" coverage found for the required
    Senior/Junior set is Epee only: Senior Men/Women and U20 Men/Women.
"""

import csv
import io
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "nor_fencing"
COUNTRY = "NOR"
BASE_URL = "https://www.fekting.no"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nb-NO,nb;q=0.9,en;q=0.8",
}

RANKING_INDEX_URL = "https://fencing.ophardt.online/en/search/rankings/7"
OPHARDT_RANKING_BASE_URL = "https://fencing.ophardt.online/en/search/rankings/show"

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

# Public "Norges Rankinglister" pages discovered from Ophardt index season 2025/2026.
# Ophardt labels Junior as U20.
RANKING_URLS = {
    ("Epee", "Men", "Senior"): f"{OPHARDT_RANKING_BASE_URL}/21181",
    ("Epee", "Women", "Senior"): f"{OPHARDT_RANKING_BASE_URL}/21180",
    ("Epee", "Men", "Junior"): f"{OPHARDT_RANKING_BASE_URL}/21177",
    ("Epee", "Women", "Junior"): f"{OPHARDT_RANKING_BASE_URL}/21176",
}

_RANK_HEADERS = {"rank", "ranking", "place", "plass", "rangering", "#"}
_NAME_HEADERS = {"name", "navn", "fencer", "athlete", "utoever", "utover", "utøver"}
_CLUB_HEADERS = {"club", "clubs", "klubb", "forening", "lag", "team"}
_POINTS_HEADERS = {"points", "point", "pts", "poeng", "punkt", "p"}


def _normalise_header(text: str) -> str:
    value = text.strip().lower()
    for src, dst in (("æ", "ae"), ("ø", "o"), ("å", "a")):
        value = value.replace(src, dst)
    value = re.sub(r"[^\w\s#-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _detect_columns(header_cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(header_cells):
        key = _normalise_header(raw)
        if key in _RANK_HEADERS and "rank" not in mapping:
            mapping["rank"] = idx
        elif key in _NAME_HEADERS and "name" not in mapping:
            mapping["name"] = idx
        elif key in _CLUB_HEADERS and "club" not in mapping:
            mapping["club"] = idx
        elif key in _POINTS_HEADERS and "points" not in mapping:
            mapping["points"] = idx
    return mapping


def _parse_rank(raw: str) -> int | None:
    match = re.match(r"^\s*(\d{1,5})(?:[.)])?\s*$", raw.strip())
    return int(match.group(1)) if match else None


def _parse_points(raw: str) -> float | None:
    value = raw.strip().replace("\xa0", " ").replace(" ", "")
    value = re.sub(r"(?i)(points?|pts?|poeng)", "", value)
    value = re.sub(r"[^0-9,.-]", "", value)
    if not value:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        if re.match(r"^\d{1,3}(,\d{3})+$", value):
            value = value.replace(",", "")
        else:
            value = value.replace(",", ".")
    elif "." in value and re.match(r"^\d{1,3}(\.\d{3})+$", value):
        value = value.replace(".", "")

    try:
        return float(value)
    except ValueError:
        return None


def _clean_name(raw: str) -> str:
    value = re.sub(r"\s+", " ", raw).strip()
    value = re.split(r"\s+(?:Details|Detail)\s+(?:Biography|Biographie)\b", value, maxsplit=1)[0]
    value = re.split(r"\s+×\s+Rank\s+Points\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
    return value.strip()


def _iter_table_rows(table):
    thead = table.find("thead", recursive=False)
    if thead:
        yield from thead.find_all("tr", recursive=False)

    tbody = table.find("tbody", recursive=False)
    if tbody:
        yield from tbody.find_all("tr", recursive=False)
        return

    yield from table.find_all("tr", recursive=False)


def _row_texts(row) -> list[str]:
    return [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"], recursive=False)]


def _parse_row(texts: list[str], col_map: dict[str, int] | None) -> dict | None:
    if col_map:
        if "rank" not in col_map or "name" not in col_map:
            return None
        if len(texts) <= max(col_map.values()):
            return None
        rank = _parse_rank(texts[col_map["rank"]])
        if rank is None:
            return None
        name = _clean_name(texts[col_map["name"]])
        club = texts[col_map["club"]].strip() if "club" in col_map else None
        points = _parse_points(texts[col_map["points"]]) if "points" in col_map else None
    else:
        if len(texts) < 4:
            return None
        rank = _parse_rank(texts[0])
        if rank is None:
            return None
        name = _clean_name(texts[1])
        club = texts[2].strip() if len(texts) > 2 else None
        points = _parse_points(texts[-1]) if len(texts) > 3 else None

    if not name:
        return None
    return {
        "rank": rank,
        "name": name,
        "club": club or None,
        "points": points,
    }


def _parse_html_tables(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        col_map: dict[str, int] | None = None
        table_rows: list[dict] = []
        saw_header_like = False

        for row in _iter_table_rows(table):
            texts = _row_texts(row)
            if not texts:
                continue

            candidate = _detect_columns(texts)
            if candidate:
                saw_header_like = True
            if "rank" in candidate and "name" in candidate:
                col_map = candidate
                continue

            if col_map is None and not saw_header_like and _parse_rank(texts[0]) is not None:
                col_map = {}

            parsed = _parse_row(texts, col_map)
            if parsed:
                table_rows.append(parsed)

        if table_rows:
            return table_rows

    return []


def _parse_delimited_text(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    sample = "\n".join(lines[:5])
    delimiter = "\t"
    if "\t" not in sample:
        delimiter = max((";", "|", ","), key=sample.count)
    if sample.count(delimiter) == 0:
        return []

    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    rows = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return []

    col_map = _detect_columns(rows[0])
    if "rank" not in col_map or "name" not in col_map:
        return []

    parsed: list[dict] = []
    for row in rows[1:]:
        item = _parse_row(row, col_map)
        if item:
            parsed.append(item)
    return parsed


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse a Norway rankings page or sheet export.

    Returns rows with keys: rank, name, club, points.
    Supports Ophardt HTML tables, Norwegian/English headers, decimal commas,
    UTF-8 names/clubs, and simple CSV/TSV/semicolon/pipe sheet exports.
    """
    if not html_or_text or not html_or_text.strip():
        return []

    if re.search(r"<\s*(html|body|table|tr|td|th)\b", html_or_text, flags=re.IGNORECASE):
        rows = _parse_html_tables(html_or_text)
        if rows:
            return rows

    return _parse_delimited_text(html_or_text)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch a public Norway ranking page for one combo, or None if unavailable."""
    url = RANKING_URLS.get((weapon, gender, category))
    if not url:
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
        if response.status_code == 200:
            return response.text
        print(f"    HTTP {response.status_code} for {url}")
        return None
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None


def current_season() -> str:
    try:
        import season_utils

        if hasattr(season_utils, "current_fie_season"):
            season_value = season_utils.current_fie_season()
            if hasattr(season_utils, "normalize_season"):
                return season_utils.normalize_season(season_value)
            if hasattr(season_utils, "season_to_string"):
                return season_utils.season_to_string(season_value)
    except (ImportError, AttributeError):
        pass

    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year-1}-{year}" if now.month < 7 else f"{year}-{year+1}"


def _coverage_metadata(failed_combos: list[str], skipped_combos: list[str]) -> dict:
    public_combos = [f"{w} {g} {c}" for w, g, c in RANKING_URLS]
    return {
        "base_url": BASE_URL,
        "ranking_page": f"{BASE_URL}/next/p/24263/ranking",
        "ranking_index_url": RANKING_INDEX_URL,
        "request_method": "GET",
        "response_format": "html",
        "public_combos": public_combos,
        "failed_combos": failed_combos,
        "skipped_combos": skipped_combos,
        "notes": (
            "fencing.no did not resolve during probe; fekting.no links to Ophardt. "
            "Only Epee Senior and U20/Senior-Junior equivalents are public for required combos."
        ),
    }


def main():
    run_log = ScraperRunLogger("scrape_fed_nor").start()
    season = current_season()
    print(f"Norges Fekteforbund rankings — season {season}")
    print(f"Ranking index: {RANKING_INDEX_URL}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []
    skipped_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")

            if (weapon, gender, category) not in RANKING_URLS:
                print("    No public Norway ranking URL found during probe")
                total_skipped += 1
                skipped_combos.append(combo_label)
                continue

            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                total_failed += 1
                failed_combos.append(combo_label)
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(content)
            if not parsed:
                print("    No rows parsed")
                total_failed += 1
                failed_combos.append(combo_label)
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
                    metadata={"source_url": RANKING_URLS[(weapon, gender, category)]},
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Parsed {len(parsed)} rows; written {written}")
            total_written += written
            time.sleep(REQUEST_DELAY)

        metadata = _coverage_metadata(failed_combos, skipped_combos)
        set_state(SOURCE, "last_run", metadata)
        run_log.complete(written=total_written, failed=total_failed, skipped=total_skipped, metadata=metadata)
        print(f"Done — written={total_written}, failed={total_failed}, skipped={total_skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

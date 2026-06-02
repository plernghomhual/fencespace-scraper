"""
scrape_fed_egy.py - Egypt federation national rankings scraper.

Probe notes, 2026-06-01:
  Requested host:
    GET https://www.egfencing.com/ -> 200 HTML, but public rankings were found
    on the federation's ranking system at fencingegypt.org.
  Working list URL:
    GET https://www.fencingegypt.org/EFF/Ranking/OverallRanking.aspx
  Working detail URL format:
    GET https://www.fencingegypt.org/EFF/Ranking/
        OverallRankingDetails.aspx?OverAllRankingID=<id>
  Response format:
    HTML, UTF-8 Arabic, table headers:
      التصنيف | الاسم | النادى | إجمالى النقاط
  Public combos:
    Senior and Junior/U20 Men/Women for Foil, Epee, and Sabre are public.
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "egy_fencing"
COUNTRY = "EGY"
BASE_URL = "https://www.fencingegypt.org/EFF/Ranking"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
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

RANKING_URL_IDS = {
    ("Foil", "Men", "Senior"): 12,
    ("Foil", "Women", "Senior"): 6,
    ("Sabre", "Men", "Senior"): 24,
    ("Sabre", "Women", "Senior"): 18,
    ("Epee", "Men", "Senior"): 36,
    ("Epee", "Women", "Senior"): 30,
    ("Foil", "Men", "Junior"): 11,
    ("Foil", "Women", "Junior"): 5,
    ("Sabre", "Men", "Junior"): 23,
    ("Sabre", "Women", "Junior"): 17,
    ("Epee", "Men", "Junior"): 35,
    ("Epee", "Women", "Junior"): 29,
}

_DIGIT_TRANSLATION = str.maketrans(
    {
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
        "٫": ".",
        "٬": ",",
    }
)

_HEADER_ALIASES = {
    "rank": {"rank", "ranking", "position", "pos", "المركز", "الترتيب", "التصنيف"},
    "name": {"name", "fencer", "player", "athlete", "الاسم", "اسم اللاعب", "اللاعب"},
    "club": {"club", "team", "academy", "النادي", "النادى", "الهيئة"},
    "points": {
        "points",
        "point",
        "total points",
        "score",
        "النقاط",
        "اجمالى النقاط",
        "اجمالي النقاط",
        "إجمالى النقاط",
        "إجمالي النقاط",
    },
}

_SKIP_MARKERS = {
    "dns",
    "dq",
    "dsq",
    "dnf",
    "wd",
    "withdrawn",
    "total",
    "summary",
    "المجموع",
    "اجمالي",
    "إجمالي",
    "اجمالى",
    "إجمالى",
    "انسحاب",
    "مستبعد",
    "استبعاد",
}


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _strip_marks(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _normalize_header(value: str) -> str:
    text = _clean_text(value).translate(_DIGIT_TRANSLATION)
    text = _strip_marks(text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي")
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text, flags=re.UNICODE)
    return _clean_text(text).lower()


def _header_kind(value: str) -> str | None:
    normalized = _normalize_header(value)
    for kind, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            alias_normalized = _normalize_header(alias)
            if normalized == alias_normalized:
                return kind
            if kind == "points" and alias_normalized in normalized:
                return kind
    return None


def _header_indexes(cells: list[str]) -> dict[str, int] | None:
    indexes: dict[str, int] = {}
    for idx, cell in enumerate(cells):
        kind = _header_kind(cell)
        if kind and kind not in indexes:
            indexes[kind] = idx
    required = {"rank", "name", "points"}
    if required.issubset(indexes):
        return indexes
    return None


def _is_skip_marker(value: str) -> bool:
    normalized = _normalize_header(value)
    if not normalized:
        return False
    if normalized in {_normalize_header(marker) for marker in _SKIP_MARKERS}:
        return True
    return normalized.startswith("total ") or normalized.startswith("summary ")


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value).translate(_DIGIT_TRANSLATION)
    if not re.fullmatch(r"\d+\s*[\.)]?", text):
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    return int(match.group(0))


def _parse_points(value: str) -> float | None:
    text = _clean_text(value).translate(_DIGIT_TRANSLATION)
    text = text.replace(" ", "")
    match = re.search(r"-?[\d.,]+", text)
    if not match:
        return None

    number = match.group(0)
    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    elif "," in number:
        parts = number.split(",")
        if len(parts[-1]) in (1, 2):
            number = "".join(parts[:-1]) + "." + parts[-1]
        else:
            number = "".join(parts)

    try:
        return float(number)
    except ValueError:
        return None


def _parse_table(table) -> list[dict]:
    header: dict[str, int] | None = None
    parsed: list[dict] = []

    for row in table.find_all("tr"):
        cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if len(cells) < 3:
            continue

        maybe_header = _header_indexes(cells)
        if maybe_header:
            header = maybe_header
            continue
        if not header:
            continue

        max_index = max(header.values())
        if len(cells) <= max_index:
            continue

        rank_text = cells[header["rank"]]
        name = cells[header["name"]]
        points_text = cells[header["points"]]
        club = cells[header["club"]] if "club" in header and len(cells) > header["club"] else None

        if any(_is_skip_marker(value) for value in (rank_text, name, points_text)):
            continue

        rank = _parse_rank(rank_text)
        if rank is None or not name:
            continue

        parsed.append(
            {
                "rank": rank,
                "name": name,
                "club": club or None,
                "points": _parse_points(points_text),
            }
        )

    return parsed


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Egypt federation rankings HTML into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []

    best_rows: list[dict] = []
    for table in tables:
        rows = _parse_table(table)
        if len(rows) > len(best_rows):
            best_rows = rows
    return best_rows


def _ranking_url(weapon: str, gender: str, category: str) -> str | None:
    ranking_id = RANKING_URL_IDS.get((weapon, gender, category))
    if ranking_id is None:
        return None
    return f"{BASE_URL}/OverallRankingDetails.aspx?OverAllRankingID={ranking_id}"


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Egypt ranking detail page, returning None on HTTP/network errors."""
    url = _ranking_url(weapon, gender, category)
    if not url:
        print(f"    No configured Egypt ranking URL for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None
    return response.text


def current_season() -> str:
    """Return the active season in YYYY-YYYY form, using season_utils when present."""
    try:
        import season_utils

        season = None
        if hasattr(season_utils, "current_season"):
            season = season_utils.current_season()
        elif hasattr(season_utils, "current_fie_season"):
            season = season_utils.current_fie_season()

        if season is not None:
            if hasattr(season_utils, "normalize_season"):
                return season_utils.normalize_season(season)
            if isinstance(season, str):
                return season
            if hasattr(season_utils, "season_to_string"):
                return season_utils.season_to_string(season)
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def main():
    run_log = ScraperRunLogger("scrape_fed_egy").start()
    season = current_season()
    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []

    print(f"Egypt federation rankings - season {season}")
    try:
        for idx, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")
            html = fetch_rankings_page(weapon, gender, category)
            if not html:
                total_failed += 1
                failed_combos.append(combo_label)
            else:
                parsed = parse_rankings_table(html)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append(combo_label)
                else:
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
                    total_written += written
                    print(f"    Parsed {len(rows)} rows; written {written} rows")

            if idx < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "failed_combos": failed_combos,
                "ranking_url_ids": {"/".join(key): value for key, value in RANKING_URL_IDS.items()},
            },
        )
        print(
            f"Done - written={total_written}, failed={total_failed}, "
            f"skipped={total_skipped}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

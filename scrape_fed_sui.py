"""
scrape_fed_sui.py - Swiss Fencing national rankings scraper.

Probe findings (2026-06-01):
  - https://swiss-fencing.ch/ is the official federation site.
  - /classements, /rankings, /ranglisten, and /ranking return 404.
  - The official site links "Nationales Ranking" to Ophardt Online:
    https://fencing.ophardt.online/fr/search/rankings/12
  - Method: GET. Format: server-rendered HTML.
  - Public coverage: all 12 Circuit National Senior/U20 Foil/Epee/Sabre
    Men/Women pages are accessible without login.

Ophardt index table order:
  Dames:  Epée, Fleuret, Sabre
  Hommes: Epée, Fleuret, Sabre
  Junior maps to Ophardt U20.
"""

import re
import time
import unicodedata
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

try:
    from season_utils import current_fie_season, normalize_season, season_to_string
except ImportError:  # Agent 5 may not be merged yet.
    current_fie_season = None  # type: ignore[assignment]
    normalize_season = None  # type: ignore[assignment]
    season_to_string = None  # type: ignore[assignment]


SOURCE = "sui_fencing"
COUNTRY = "SUI"
BASE_URL = "https://fencing.ophardt.online/fr/search/rankings/show"
OFFICIAL_INDEX_URL = "https://fencing.ophardt.online/fr/search/rankings/12"
OFFICIAL_FEDERATION_URL = "https://swiss-fencing.ch/"
REQUEST_DELAY = 1.5
SOURCE_LANGUAGE = "fr"
DATA_FORMAT = "html"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-CH,fr;q=0.9,de;q=0.8,it;q=0.7,en;q=0.6",
    "Referer": OFFICIAL_FEDERATION_URL,
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

RANKING_IDS = {
    ("Epee", "Women", "Senior"): 21064,
    ("Foil", "Women", "Senior"): 21069,
    ("Sabre", "Women", "Senior"): 21071,
    ("Epee", "Men", "Senior"): 21068,
    ("Foil", "Men", "Senior"): 21070,
    ("Sabre", "Men", "Senior"): 21072,
    ("Epee", "Women", "Junior"): 21063,
    ("Foil", "Women", "Junior"): 21073,
    ("Sabre", "Women", "Junior"): 21075,
    ("Epee", "Men", "Junior"): 21067,
    ("Foil", "Men", "Junior"): 21074,
    ("Sabre", "Men", "Junior"): 21076,
}

_RANK_HEADERS = {"rank", "rang", "platz", "classement", "classe", "pos", "position", "place", "#"}
_NAME_HEADERS = {"name", "nom", "nome", "atleta", "athlete", "fencer", "fechter"}
_CLUB_HEADERS = {"club", "clubs", "verein", "vereine", "societe", "societa", "society"}
_POINTS_HEADERS = {"points", "point", "punkte", "punti", "punteggio", "score", "pts"}
_SKIP_TOKENS = {"dns", "dnf", "dq", "dsq", "disqualified", "total", "summary", "resume", "zusammenfassung"}


def ranking_url(weapon: str, gender: str, category: str) -> str | None:
    ranking_id = RANKING_IDS.get((weapon, gender, category))
    if ranking_id is None:
        return None
    return f"{BASE_URL}/{ranking_id}"


def _normalise_header(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("ß", "ss")
    return re.sub(r"[^a-z0-9#]+", "", text)


def _cell_text(cell) -> str:
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()


def _detect_columns(header_cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, raw in enumerate(header_cells):
        key = _normalise_header(raw)
        if key in _RANK_HEADERS and "rank_col" not in mapping:
            mapping["rank_col"] = index
        elif key in _NAME_HEADERS and "name_col" not in mapping:
            mapping["name_col"] = index
        elif key in _CLUB_HEADERS and "club_col" not in mapping:
            mapping["club_col"] = index
        elif key in _POINTS_HEADERS and "points_col" not in mapping:
            mapping["points_col"] = index
    return mapping


def _parse_rank(raw: str) -> int | None:
    match = re.match(r"^\s*(\d+)\.?\s*$", raw or "")
    if not match:
        return None
    return int(match.group(1))


def _parse_points(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    if _normalise_header(text) in _SKIP_TOKENS:
        return None

    value = text.replace("\u00a0", " ").replace(" ", "").replace("'", "")
    value = re.sub(r"[^0-9,.\-]", "", value)
    if not value or value in {"-", ".", ","}:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        if re.match(r"^-?\d{1,3}(,\d{3})+$", value):
            value = value.replace(",", "")
        else:
            value = value.replace(",", ".")
    elif "." in value and re.match(r"^-?\d{1,3}(\.\d{3})+$", value):
        value = value.replace(".", "")

    try:
        return float(value)
    except ValueError:
        return None


def _clean_name(raw: str) -> str:
    name = re.sub(r"\s+", " ", raw or "").strip()
    name = re.split(r"\s+(?:Details?|Details|Dettagli|Détails|Biographie|Biography|Biografia)\b", name)[0]
    return name.strip(" \t\r\n-")


def _should_skip_text(text: str) -> bool:
    key = _normalise_header(text)
    return not key or key in _SKIP_TOKENS


def _parse_row(cells, columns: dict[str, int]) -> dict | None:
    required = ["rank_col", "name_col"]
    if any(key not in columns for key in required):
        return None
    if len(cells) <= max(columns.values()):
        return None

    rank_text = _cell_text(cells[columns["rank_col"]])
    rank = _parse_rank(rank_text)
    if rank is None:
        return None

    name = _clean_name(_cell_text(cells[columns["name_col"]]))
    if _should_skip_text(name):
        return None

    club = None
    if "club_col" in columns:
        club = _cell_text(cells[columns["club_col"]]) or None

    points = None
    if "points_col" in columns:
        points = _parse_points(_cell_text(cells[columns["points_col"]]))

    return {"rank": rank, "name": name, "club": club, "points": points}


def _parse_table(table) -> list[dict]:
    results: list[dict] = []
    columns: dict[str, int] | None = None

    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        texts = [_cell_text(cell) for cell in cells]

        candidate = _detect_columns(texts)
        if "rank_col" in candidate and "name_col" in candidate:
            columns = candidate
            continue

        if columns is None:
            rank = _parse_rank(texts[0]) if texts else None
            if rank is not None and len(texts) >= 2:
                columns = {
                    "rank_col": 0,
                    "name_col": 1,
                    "club_col": 2 if len(texts) > 2 else 1,
                    "points_col": len(texts) - 1,
                }
            else:
                continue

        parsed = _parse_row(cells, columns)
        if parsed:
            results.append(parsed)

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse a Swiss/Ophardt ranking page into rank/name/club/points rows."""
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


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch the Swiss Ophardt ranking HTML for one weapon/gender/category combo."""
    url = ranking_url(weapon, gender, category)
    if not url:
        print(f"    No ranking ID for {weapon} {gender} {category}")
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
    """Return a YYYY-YYYY season string, using season_utils when available."""
    if current_fie_season is not None:
        season_value = current_fie_season()
        if normalize_season is not None:
            return normalize_season(season_value)
        if season_to_string is not None:
            return season_to_string(season_value)
        if isinstance(season_value, int):
            return f"{season_value - 1}-{season_value}"
        return str(season_value).replace("/", "-")

    now = datetime.now(UTC)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def _row_metadata(weapon: str, gender: str, category: str) -> dict:
    return {
        "source_language": SOURCE_LANGUAGE,
        "file_url": ranking_url(weapon, gender, category),
        "official_index_url": OFFICIAL_INDEX_URL,
        "official_federation_url": OFFICIAL_FEDERATION_URL,
        "data_format": DATA_FORMAT,
        "ranking_id": RANKING_IDS.get((weapon, gender, category)),
    }


def main():
    run_log = ScraperRunLogger("scrape_fed_sui").start()
    try:
        season = current_season()
        print(f"Swiss Fencing rankings - season {season}")
        total_written = 0
        total_failed = 0
        total_skipped = 0
        working_combos = 0
        failed_combos: list[dict] = []

        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            print(f"  {weapon} {gender} {category}...")
            html = fetch_rankings_page(weapon, gender, category)
            if not html:
                total_failed += 1
                failed_combos.append({"weapon": weapon, "gender": gender, "category": category, "reason": "fetch_failed"})
                if index < len(RANKING_COMBOS) - 1:
                    time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(html)
            if not parsed:
                print("    No rows parsed")
                total_failed += 1
                failed_combos.append({"weapon": weapon, "gender": gender, "category": category, "reason": "no_rows"})
                if index < len(RANKING_COMBOS) - 1:
                    time.sleep(REQUEST_DELAY)
                continue

            metadata = _row_metadata(weapon, gender, category)
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
                    metadata=metadata,
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Written {written} rows ({len(parsed)} parsed)")
            total_written += written
            working_combos += 1

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "working_combos": working_combos,
                "total_combos": len(RANKING_COMBOS),
                "failed_combos": failed_combos,
                "data_format": DATA_FORMAT,
                "official_index_url": OFFICIAL_INDEX_URL,
            },
        )
        print(
            f"Done - written={total_written}, failed={total_failed}, "
            f"skipped={total_skipped}, combos={working_combos}/{len(RANKING_COMBOS)}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

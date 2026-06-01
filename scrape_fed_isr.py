"""
scrape_fed_isr.py — Israel Fencing Association national rankings scraper.

Probe findings (2026-06-01):
  - Official site: https://www.fencing.org.il/
  - Tried /ranking, /rankings, /he/ranking, /תחרויות: HTTP 404.
  - /דירוג is public but veteran-only.
  - Current "ניקוד מתעדכן" links to https://podiumcomp.com/site/isrisf, which returns
    Cloudflare 403 (`cf-mitigated: challenge`) to non-browser probes.
  - Public archive page /דירוגים-עונה-2023-2024/ exposes all 12 Senior/Junior
    Foil/Epee/Sabre Men/Women rankings as XLSX files.
  - Request method: GET with browser-like headers.
  - Response format: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.

Current behavior:
  Scrapes the 2023-2024 public XLSX archive for all 12 required combos. Rows are
  stored with season "2023-2024" and source URL metadata so archived data is not
  mislabeled as the current PodiumComp rankings.

Relevant worksheet columns:
  דירוג | שם | אגודה | ניקוד משוקלל | ...

Hebrew right-to-left text is preserved exactly as provided by the source.
"""

from __future__ import annotations

import io
import re
import time
import urllib.parse
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "isr_fencing"
COUNTRY = "ISR"
BASE_URL = "https://www.fencing.org.il"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "he,en-US;q=0.8,en;q=0.6",
}

ARCHIVE_SEASON = "2023-2024"
ARCHIVE_PAGE = f"{BASE_URL}/%d7%93%d7%99%d7%a8%d7%95%d7%92%d7%99%d7%9d-%d7%a2%d7%95%d7%a0%d7%94-2023-2024/"
CURRENT_PUBLIC_URL = "https://podiumcomp.com/site/isrisf"

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

RANKING_URLS = {
    ("Foil", "Men", "Senior"): f"{BASE_URL}/wp-content/uploads/2024/08/רומח-בנים-בוגרים.xlsx",
    ("Foil", "Women", "Senior"): f"{BASE_URL}/wp-content/uploads/2024/08/רומח-בנות-בוגרים.xlsx",
    ("Epee", "Men", "Senior"): f"{BASE_URL}/wp-content/uploads/2024/08/דקר-בנים-בוגרים.xlsx",
    ("Epee", "Women", "Senior"): f"{BASE_URL}/wp-content/uploads/2024/08/דקר-בנות-בוגרים.xlsx",
    ("Sabre", "Men", "Senior"): f"{BASE_URL}/wp-content/uploads/2024/08/חרב-בנים-בוגרים.xlsx",
    ("Sabre", "Women", "Senior"): f"{BASE_URL}/wp-content/uploads/2024/08/חרב-בנות-בוגרים.xlsx",
    ("Foil", "Men", "Junior"): f"{BASE_URL}/wp-content/uploads/2024/08/רומח-בנים-נוער.xlsx",
    ("Foil", "Women", "Junior"): f"{BASE_URL}/wp-content/uploads/2024/08/רומח-בנות-נוער.xlsx",
    ("Epee", "Men", "Junior"): f"{BASE_URL}/wp-content/uploads/2024/10/דקר-בנים-נוער.xlsx",
    ("Epee", "Women", "Junior"): f"{BASE_URL}/wp-content/uploads/2024/08/דקר-בנות-נוער.xlsx",
    ("Sabre", "Men", "Junior"): f"{BASE_URL}/wp-content/uploads/2024/08/חרב-בנים-נוער.xlsx",
    ("Sabre", "Women", "Junior"): f"{BASE_URL}/wp-content/uploads/2024/08/חרב-בנות-נוער.xlsx",
}

_XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _normalise_header(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("״", '"').replace("”", '"').replace("“", '"')
    text = re.sub(r"[\s:_\-./]+", " ", text.lower().strip())
    return text.strip()


_RANK_HEADERS = {_normalise_header(v) for v in {"דירוג", "מיקום", "rank", "place", "position", "#"}}
_HEBREW_NAME_HEADERS = {_normalise_header(v) for v in {"שם", "שם מלא", "שם הספורטאי", "ספורטאי"}}
_LATIN_NAME_HEADERS = {_normalise_header(v) for v in {"name", "english name", "latin name", "athlete", "fencer"}}
_CLUB_HEADERS = {_normalise_header(v) for v in {"אגודה", "מועדון", "קבוצה", "club", "team"}}
_POINTS_HEADERS = {
    _normalise_header(v)
    for v in {
        "ניקוד משוקלל",
        "נקודות",
        "ניקוד",
        "סהכ נקודות",
        "סה\"כ נקודות",
        "points",
        "total points",
        "pts",
        "score",
    }
}
_SKIP_ROW_MARKERS = {
    _normalise_header(v)
    for v in {
        "dns",
        "dq",
        "dsq",
        "dnf",
        "דירוג",
        "שם",
        "סהכ",
        "סה\"כ",
        "סה״כ",
        "סיכום",
        "total",
        "summary",
    }
}
_NO_DATA_MARKERS = {
    "no rankings available",
    "no data",
    "אין דירוגים",
    "אין נתונים",
    "לא נמצאו",
}


def ranking_url(weapon: str, gender: str, category: str) -> str | None:
    return RANKING_URLS.get((weapon, gender, category))


def _quote_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            urllib.parse.quote(parts.path),
            parts.query,
            parts.fragment,
        )
    )


def _parse_rank(raw: str) -> int | None:
    text = raw.strip().replace(".", "")
    if not text or _normalise_header(text) in _SKIP_ROW_MARKERS:
        return None
    if not re.fullmatch(r"\d+", text):
        return None
    return int(text)


def _parse_points(raw: str) -> float | None:
    text = raw.strip().replace("\u00a0", "").replace(" ", "").replace("%", "")
    if not text or _normalise_header(text) in _SKIP_ROW_MARKERS or text in {"-", "—", "–"}:
        return None
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", text):
        text = text.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", text):
        text = text.replace(".", "").replace(",", ".")
    elif "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _clean_cell(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def _detect_columns(cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(cells):
        key = _normalise_header(raw)
        if key in _RANK_HEADERS and "rank_col" not in mapping:
            mapping["rank_col"] = idx
        elif key in _LATIN_NAME_HEADERS and "latin_name_col" not in mapping:
            mapping["latin_name_col"] = idx
        elif key in _HEBREW_NAME_HEADERS and "hebrew_name_col" not in mapping:
            mapping["hebrew_name_col"] = idx
        elif key in _CLUB_HEADERS and "club_col" not in mapping:
            mapping["club_col"] = idx
        elif key in _POINTS_HEADERS and "points_col" not in mapping:
            mapping["points_col"] = idx

    if "latin_name_col" in mapping:
        mapping["name_col"] = mapping["latin_name_col"]
    elif "hebrew_name_col" in mapping:
        mapping["name_col"] = mapping["hebrew_name_col"]

    return mapping


def _append_parsed_row(rows: list[dict], col_map: dict[str, int], cells: list[str]) -> None:
    required = ("rank_col", "name_col")
    if any(key not in col_map for key in required):
        return
    if len(cells) <= max(col_map.values()):
        return

    rank = _parse_rank(cells[col_map["rank_col"]])
    if rank is None:
        return

    name = _clean_cell(cells[col_map["name_col"]])
    if not name:
        return

    club = _clean_cell(cells[col_map["club_col"]]) if "club_col" in col_map else None
    points = _parse_points(cells[col_map["points_col"]]) if "points_col" in col_map else None

    metadata = {}
    hebrew_col = col_map.get("hebrew_name_col")
    latin_col = col_map.get("latin_name_col")
    if hebrew_col is not None and hebrew_col != col_map["name_col"] and hebrew_col < len(cells):
        hebrew_name = _clean_cell(cells[hebrew_col])
        if hebrew_name:
            metadata["hebrew_name"] = hebrew_name
    if latin_col is not None and latin_col != col_map["name_col"] and latin_col < len(cells):
        latin_name = _clean_cell(cells[latin_col])
        if latin_name:
            metadata["latin_name"] = latin_name

    row = {"rank": rank, "name": name, "club": club or None, "points": points}
    if metadata:
        row["metadata"] = metadata
    rows.append(row)


def _parse_matrix(matrix: list[list[str]]) -> list[dict]:
    rows: list[dict] = []
    col_map: dict[str, int] | None = None
    seen: set[tuple[int, str]] = set()

    for raw_cells in matrix:
        cells = [_clean_cell(cell) for cell in raw_cells]
        while cells and not cells[-1]:
            cells.pop()
        if not cells:
            continue

        if col_map is None:
            candidate = _detect_columns(cells)
            if "rank_col" in candidate and "name_col" in candidate:
                col_map = candidate
                continue
            if len(cells) >= 2 and _parse_rank(cells[0]) is not None:
                col_map = {"rank_col": 0, "name_col": 1}
                if len(cells) >= 3:
                    col_map["club_col"] = 2
                if len(cells) >= 4:
                    col_map["points_col"] = 3
            else:
                continue

        before = len(rows)
        _append_parsed_row(rows, col_map, cells)
        if len(rows) == before:
            continue

        key = (rows[-1]["rank"], rows[-1]["name"])
        if key in seen:
            rows.pop()
        else:
            seen.add(key)

    return rows


def _html_tables_to_matrices(html: str) -> list[list[list[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    matrices = []
    for table in soup.find_all("table"):
        matrix = []
        for tr in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
            if cells:
                matrix.append(cells)
        if matrix:
            matrices.append(matrix)
    return matrices


def _text_to_matrix(text: str) -> list[list[str]]:
    matrix = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            cells = line.split("\t")
        elif "|" in line:
            cells = line.split("|")
        else:
            cells = re.split(r"\s{2,}", line)
        if len(cells) > 1:
            matrix.append(cells)
    return matrix


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse Israel federation ranking content.

    Accepts HTML tables and tab/pipe-delimited text extracted from the current
    public XLSX files. Returns dictionaries with rank, name, club, points, and
    optional metadata for alternate Hebrew/Latin name columns.
    """
    if not html_or_text or not html_or_text.strip():
        return []

    lowered = html_or_text.lower()
    if any(marker in lowered for marker in _NO_DATA_MARKERS):
        return []

    parsed_rows: list[dict] = []
    for matrix in _html_tables_to_matrices(html_or_text):
        parsed_rows.extend(_parse_matrix(matrix))
    if parsed_rows:
        return parsed_rows

    text = BeautifulSoup(html_or_text, "html.parser").get_text("\n", strip=True)
    return _parse_matrix(_text_to_matrix(text))


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter.upper()) - 64
    return max(index - 1, 0)


def _read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    shared = []
    for item in root.findall("a:si", _XLSX_NS):
        shared.append("".join(node.text or "" for node in item.findall(".//a:t", _XLSX_NS)))
    return shared


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//a:t", _XLSX_NS))

    value = cell.find("a:v", _XLSX_NS)
    raw = value.text if value is not None else ""
    if cell_type == "s" and raw.isdigit():
        idx = int(raw)
        return shared[idx] if idx < len(shared) else ""
    return raw


def _extract_xlsx_text(content: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            shared = _read_shared_strings(zf)
            sheet_names = sorted(name for name in zf.namelist() if name.startswith("xl/worksheets/sheet"))
            if not sheet_names:
                return None

            root = ET.fromstring(zf.read(sheet_names[0]))
            lines = []
            for row in root.findall(".//a:sheetData/a:row", _XLSX_NS):
                cells: list[str] = []
                for cell in row.findall("a:c", _XLSX_NS):
                    idx = _column_index(cell.attrib.get("r", "A1"))
                    while len(cells) <= idx:
                        cells.append("")
                    cells[idx] = _cell_text(cell, shared)
                while cells and not cells[-1]:
                    cells.pop()
                if cells:
                    lines.append("\t".join(cells))
            return "\n".join(lines)
    except (OSError, KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        print(f"    XLSX parse error: {exc}")
        return None


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch ranking content for one Israel weapon/gender/category combo."""
    url = ranking_url(weapon, gender, category)
    if not url:
        print(f"    No URL configured for {weapon} {gender} {category}")
        return None

    try:
        response = requests.get(_quote_url(url), headers=HEADERS, timeout=30, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code == 404:
        print(f"    HTTP 404 for {url}")
        return None
    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    content_type = response.headers.get("content-type", "").lower()
    if "spreadsheetml.sheet" in content_type or response.content.startswith(b"PK\x03\x04"):
        return _extract_xlsx_text(response.content)

    return response.text


def current_season() -> str:
    try:
        import season_utils

        if hasattr(season_utils, "current_season"):
            value = season_utils.current_season()
        elif hasattr(season_utils, "current_fie_season"):
            value = season_utils.current_fie_season()
        else:
            value = None

        if value is not None:
            if hasattr(season_utils, "normalize_season"):
                return season_utils.normalize_season(value)
            if hasattr(season_utils, "season_to_string"):
                return season_utils.season_to_string(value)
            if isinstance(value, int):
                return f"{value - 1}-{value}"
            return str(value)
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_isr").start()
    runtime_season = current_season()
    source_season = ARCHIVE_SEASON
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous Israel federation run state found: {previous_state}")

    print(f"Israel Fencing Association rankings — source season {source_season}")
    print(f"Current PodiumComp rankings are Cloudflare-challenged: {CURRENT_PUBLIC_URL}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_label = f"{weapon} {gender} {category}"
            source_url = ranking_url(weapon, gender, category)
            print(f"  {combo_label}...")

            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                total_failed += 1
                failed_combos.append(combo_label)
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append(combo_label)
                else:
                    rows = []
                    for row in parsed:
                        metadata = {
                            "source_url": source_url,
                            "source_page": ARCHIVE_PAGE,
                            "source_season": source_season,
                            "format": "xlsx",
                            "current_public_url": CURRENT_PUBLIC_URL,
                        }
                        metadata.update(row.get("metadata") or {})
                        rows.append(
                            build_ranking_row(
                                source=SOURCE,
                                season=source_season,
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
                        )
                    written = write_rankings(rows, source=SOURCE, season=source_season)
                    print(f"    Parsed {len(rows)} rows; written {written} rows")
                    total_written += written

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        state = {
            "source_season": source_season,
            "runtime_current_season": runtime_season,
            "written": total_written,
            "failed": total_failed,
            "skipped": total_skipped,
            "failed_combos": failed_combos,
            "source_page": ARCHIVE_PAGE,
            "current_public_url": CURRENT_PUBLIC_URL,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        set_state(SOURCE, "last_run", state)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=state,
        )
        print(f"Done — written={total_written}, failed={total_failed}, skipped={total_skipped}")
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
    except Exception as exc:
        set_state(
            SOURCE,
            "last_error",
            {"error": str(exc), "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        run_log.error(str(exc))
        print(f"FAILED — {exc}")


if __name__ == "__main__":
    main()

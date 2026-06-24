"""
scrape_fed_ltu.py - Lithuania national federation rankings scraper.

Probe evidence, 2026-06-02:
  - Requested probe URL https://ltf.lt/ is public HTML for the Lithuanian
    volleyball federation, not fencing.
  - Current fencing federation page: https://fechtavimas.lt/reitingas
  - Public ranking links are Google Sheets exports from "Visa reitingo lentelė".
  - Request method: GET.
  - Response format: public text/csv sheet exports.
  - Public ranking coverage found in the current workbook:
      Epee Men Senior:    suaugeV
      Epee Women Senior:  suaugeM
      Epee Men Junior:    JaunimasV_U20
      Epee Women Junior:  JaunimasM_U20
    No durable public Foil/Sabre ranking sheets were found in the workbook.
"""

from __future__ import annotations

import csv
import io
import re
import time
import unicodedata
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings

SOURCE = "ltu_fencing"
COUNTRY = "Lithuania"
BASE_URL = "https://fechtavimas.lt/reitingas"
SPREADSHEET_ID = "1pGGeY7ZUkEm2bjkeawdfYzP3IiOB8QSs"
SPREADSHEET_EXPORT_BASE = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain;q=0.9,text/html;q=0.8,*/*;q=0.7",
    "Accept-Language": "lt-LT,lt;q=0.9,en;q=0.7",
    "Referer": BASE_URL,
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

PUBLIC_RANKING_SHEETS = {
    ("Epee", "Men", "Senior"): {
        "sheet": "suaugeV",
        "gid": "1854966084",
        "public_category": "suaugę vyrai",
    },
    ("Epee", "Women", "Senior"): {
        "sheet": "suaugeM",
        "gid": "860759954",
        "public_category": "suaugę moterys",
    },
    ("Epee", "Men", "Junior"): {
        "sheet": "JaunimasV_U20",
        "gid": "1118411918",
        "public_category": "jaunimas vyrai U20",
    },
    ("Epee", "Women", "Junior"): {
        "sheet": "JaunimasM_U20",
        "gid": "2111530628",
        "public_category": "jaunimas moterys U20",
    },
}

RANK_HEADER_ALIASES = {"rank", "vieta", "eilnr", "nr", "pozicija"}
NAME_HEADER_ALIASES = {
    "name",
    "fencer",
    "athlete",
    "sportininkas",
    "sportininke",
    "vardaspavarde",
}
FIRST_NAME_HEADER_ALIASES = {"vardas", "firstname"}
LAST_NAME_HEADER_ALIASES = {"pavarde", "lastname", "surname"}
CLUB_HEADER_ALIASES = {"club", "clubs", "klubas", "klubai", "komanda", "organizacija"}
POINT_HEADER_ALIASES = {"points", "point", "taskai", "pts"}
SUM_HEADER_ALIASES = {"suma", "total", "totalpoints", "bendrataskusuma", "bendrataskaisuma"}
SKIP_VALUES = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "ret",
    "isviso",
    "viso",
    "total",
    "totals",
    "summary",
    "santrauka",
    "bendra",
    "neatvyko",
    "diskvalifikuotas",
    "diskvalifikuota",
}


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY using season_utils when present."""
    now = datetime.now(UTC)
    season_end_year = now.year if now.month < 7 else now.year + 1

    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "normalize_season"):
            return season_utils.normalize_season(season_end_year)
        if hasattr(season_utils, "season_to_string"):
            return season_utils.season_to_string(season_end_year)
    except Exception:
        pass

    return f"{season_end_year - 1:04d}-{season_end_year:04d}"


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(value))
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def _is_skip_text(value: str) -> bool:
    key = _normalize_key(value)
    return key in SKIP_VALUES


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value)
    if not text or _is_skip_text(text):
        return None

    match = re.match(r"^\s*(\d+)", text)
    if not match:
        return None

    rank = int(match.group(1))
    return rank if rank > 0 else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if not text or _is_skip_text(text):
        return None

    text = re.sub(r"[^\d,.\-\s]", "", text).replace(" ", "")
    if text in {"", "-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            normalized = text.replace(".", "").replace(",", ".")
        else:
            normalized = text.replace(",", "")
    elif "," in text:
        head, tail = text.rsplit(",", 1)
        if len(tail) == 3 and head.lstrip("-").isdigit() and len(head.lstrip("-")) <= 3:
            normalized = head + tail
        else:
            normalized = f"{head.replace(',', '')}.{tail}"
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 2 and all(len(part) == 3 for part in parts[1:]):
            normalized = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0].lstrip("-")) <= 3:
            normalized = "".join(parts)
        else:
            normalized = text
    else:
        normalized = text

    try:
        return float(normalized)
    except ValueError:
        return None


def _cell(cells: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(cells):
        return ""
    return _clean_text(cells[index])


def _find_header_mapping(rows: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    for row_index, row in enumerate(rows):
        mapping: dict[str, int] = {}
        point_candidates: list[int] = []
        sum_candidates: list[int] = []

        for index, label in enumerate(row):
            key = _normalize_key(label)
            if not key:
                continue
            if key in RANK_HEADER_ALIASES and "rank" not in mapping:
                mapping["rank"] = index
            elif key in NAME_HEADER_ALIASES:
                mapping["name"] = index
            elif key in FIRST_NAME_HEADER_ALIASES:
                mapping["first_name"] = index
            elif key in LAST_NAME_HEADER_ALIASES:
                mapping["last_name"] = index
            elif key in CLUB_HEADER_ALIASES:
                mapping["club"] = index
            elif key in SUM_HEADER_ALIASES:
                sum_candidates.append(index)
            elif key in POINT_HEADER_ALIASES:
                point_candidates.append(index)

        if sum_candidates:
            mapping["points"] = sum_candidates[-1]
        elif point_candidates:
            mapping["points"] = point_candidates[-1]

        has_name = "name" in mapping or {"first_name", "last_name"}.issubset(mapping)
        if {"rank", "points"}.issubset(mapping) and has_name:
            return row_index, mapping

    return None


def _name_from_row(cells: list[str], mapping: dict[str, int]) -> str:
    if "name" in mapping:
        return _cell(cells, mapping["name"])
    parts = [_cell(cells, mapping.get("first_name")), _cell(cells, mapping.get("last_name"))]
    return _clean_text(" ".join(part for part in parts if part))


def _parse_matrix(rows: list[list[str]]) -> list[dict]:
    if not rows:
        return []

    header = _find_header_mapping(rows)
    if not header:
        return []

    header_index, mapping = header
    results: list[dict] = []
    for cells in rows[header_index + 1:]:
        if not any(_clean_text(cell) for cell in cells):
            continue

        rank = _parse_rank(_cell(cells, mapping["rank"]))
        if rank is None:
            continue

        name = _name_from_row(cells, mapping)
        if not name or _is_skip_text(name):
            continue

        points = _parse_points(_cell(cells, mapping["points"]))
        if points is None:
            continue

        club = _cell(cells, mapping.get("club")) or None
        results.append({"rank": rank, "name": name, "club": club, "points": points})

    return results


def _csv_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in csv.reader(io.StringIO(text)):
        cleaned = [_clean_text(cell) for cell in row]
        if any(cleaned):
            rows.append(cleaned)
    return rows


def _html_tables(html: str) -> list[list[list[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    tables: list[list[list[str]]] = []
    for table in soup.find_all("table"):
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"], recursive=False)
            if not cells:
                continue
            values = [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            if any(values):
                rows.append(values)
        if rows:
            tables.append(rows)
    return tables


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Lithuania ranking CSV or HTML into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    text = html_or_text.strip()
    if "<table" in text.lower() or "<html" in text.lower():
        results: list[dict] = []
        for table_rows in _html_tables(text):
            results.extend(_parse_matrix(table_rows))
        return results

    return _parse_matrix(_csv_rows(text))


def _sheet_url(weapon: str, gender: str, category: str) -> str | None:
    sheet = PUBLIC_RANKING_SHEETS.get((weapon, gender, category))
    if not sheet:
        return None
    return f"{SPREADSHEET_EXPORT_BASE}?format=csv&gid={sheet['gid']}"


def _decoded_response_text(response) -> str:
    content = getattr(response, "content", None)
    if content:
        for encoding in ("utf-8-sig", "utf-8"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                pass

    text = response.text or ""
    if any(marker in text for marker in ("Å", "Ä", "Â")):
        try:
            return text.encode("latin-1").decode("utf-8")
        except UnicodeError:
            pass
    return text


def _looks_like_blocked_html(response, text: str) -> bool:
    content_type = (response.headers.get("content-type") or "").lower()
    lowered = text.strip().lower()

    if "text/html" not in content_type and not lowered.startswith("<!doctype") and not lowered.startswith("<html"):
        return False
    if "<table" in lowered:
        return False

    markers = [
        "sign in",
        "login",
        "accounts.google.com",
        "enable javascript",
        "please enable javascript",
        "javascript to view",
    ]
    return any(marker in lowered for marker in markers)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public Lithuania ranking CSV. Return None for missing or failed combos."""
    url = _sheet_url(weapon, gender, category)
    if not url:
        print(f"    No public ranking sheet for {weapon} {gender} {category} at {BASE_URL}")
        return None

    try:
        response = federation_request(
            "get",
            url,
            headers=HEADERS,
            timeout=25,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {getattr(response, 'url', url)}")
        return None

    text = _decoded_response_text(response)
    if _looks_like_blocked_html(response, text):
        print(f"    No scrapeable rankings at {getattr(response, 'url', url)}")
        return None

    return text


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main():
    from run_logger import ScraperRunLogger
    from scraper_state import set_state

    run_log = ScraperRunLogger("scrape_fed_ltu").start()
    season = current_season()
    print(f"Lithuania federation rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos: list[str] = []
    failed_combos: list[str] = []
    missing_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            combo = (weapon, gender, category)
            label = _combo_label(weapon, gender, category)
            print(f"  {label}...")

            sheet = PUBLIC_RANKING_SHEETS.get(combo)
            html_or_text = fetch_rankings_page(weapon, gender, category)
            if html_or_text is None:
                if sheet is None:
                    missing_combos.append(label)
                    total_skipped += 1
                else:
                    failed_combos.append(label)
                    total_failed += 1
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(html_or_text)
            if not parsed:
                print("    No rows parsed")
                failed_combos.append(label)
                total_failed += 1
                time.sleep(REQUEST_DELAY)
                continue

            source_url = _sheet_url(weapon, gender, category)
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
                        "source_url": source_url,
                        "country_page": BASE_URL,
                        "spreadsheet_id": SPREADSHEET_ID,
                        "sheet": sheet["sheet"] if sheet else None,
                        "public_category": sheet["public_category"] if sheet else None,
                        "public_weapon_scope": "Epee only in probed workbook",
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
            "season": season,
            "combos_total": len(RANKING_COMBOS),
            "combos_working": len(working_combos),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
            "missing_public_combos": missing_combos,
            "data_format": "csv",
            "probe": {
                "requested_url": "https://ltf.lt/",
                "requested_url_result": "public volleyball federation HTML, not fencing",
                "ranking_page": BASE_URL,
                "method": "GET",
                "source_format": "public Google Sheets text/csv exports",
            },
        }
        set_state(SOURCE, "last_run", metadata)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=metadata,
        )
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"combos_working={len(working_combos)}/{len(RANKING_COMBOS)}"
        )
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
        if missing_combos:
            print(f"Missing public combos: {', '.join(missing_combos)}")
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

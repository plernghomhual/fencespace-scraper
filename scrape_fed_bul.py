"""
scrape_fed_bul.py - Bulgaria national federation rankings scraper.

Probe findings (2026-06-02):
  - Official page: https://bulfencing.com/sastezania/ranglista.html
  - The page embeds three public Google Sheets, one for Sabre/Epee/Foil.
  - Durable fetch format is GET text/csv using the published sheet export:
      https://docs.google.com/spreadsheets/d/e/<sheet_id>/pub?gid=<gid>&single=true&output=csv
  - All 12 requested Senior/Junior Foil/Epee/Sabre Men/Women combos are public.
  - Source headers are Bulgarian Cyrillic, commonly:
      ФАМИЛИЯ | ИМЕ | КЛУБ | Год. | Точки
"""

from __future__ import annotations

import csv
import re
import time
from datetime import datetime, timezone
from io import StringIO

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

try:
    from season_utils import normalize_season, season_to_string
except Exception:  # pragma: no cover - compatibility fallback for stripped envs.
    normalize_season = None  # type: ignore[assignment]
    season_to_string = None  # type: ignore[assignment]


SOURCE = "bul_fencing"
COUNTRY = "Bulgaria"
BASE_URL = "https://bulfencing.com/sastezania/ranglista.html"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
}

SHEET_IDS = {
    "Sabre": "2PACX-1vTbER4pYMPMg0gLy-Qxn7mPbaKo0ez3X7sdcNvxNQQf61Uiq758u8LeOeb8k0w19kGFd-j5H0fB3YyC",
    "Epee": "2PACX-1vRXMs9c3ynzKozc0CeIow9W2lDvlc26SIMnI_TvS_V2CLFK07yDtwBkYeo7j8ukpv7EcrSkgN-eCRtB",
    "Foil": "2PACX-1vRYQlpDIdpnZdqgC_PO_LgRjPQfzrJAuvJGN0HQ5L0Uyg-_r4BT16ofloAglI4niX2WxtiBTHoP8Vmh",
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

RANKING_GIDS = {
    ("Foil", "Men", "Senior"): "1659868868",
    ("Foil", "Women", "Senior"): "1803904722",
    ("Foil", "Men", "Junior"): "1406404595",
    ("Foil", "Women", "Junior"): "1130514698",
    ("Epee", "Men", "Senior"): "303437023",
    ("Epee", "Women", "Senior"): "1272098068",
    ("Epee", "Men", "Junior"): "1008955208",
    ("Epee", "Women", "Junior"): "1438810122",
    ("Sabre", "Men", "Senior"): "241008218",
    ("Sabre", "Women", "Senior"): "1857587468",
    ("Sabre", "Men", "Junior"): "524327685",
    ("Sabre", "Women", "Junior"): "366868271",
}


def _build_sheet_url(weapon: str, gid: str) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/e/{SHEET_IDS[weapon]}"
        f"/pub?gid={gid}&single=true&output=csv"
    )


RANKING_URLS = {
    combo: _build_sheet_url(combo[0], gid)
    for combo, gid in RANKING_GIDS.items()
}

_SKIP_ROW_TOKENS = {
    "",
    "-",
    "dns",
    "dq",
    "dsq",
    "dnf",
    "wd",
    "withdrawn",
    "summary",
    "subtotal",
    "total",
    "totals",
    "общо",
    "сума",
    "дисквалифициран",
}
_BLOCKED_MARKERS = (
    "sign in",
    "please sign in",
    "google accounts",
    "login required",
    "not authorized",
    "enable javascript",
    "please enable javascript",
    "javascript to view",
)


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip() if value is not None else ""


def _header_key(value: str) -> str:
    text = _clean_text(value).lower()
    text = text.replace("№", "#")
    text = re.sub(r"[^\w#]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value).rstrip(".")
    key = _header_key(text)
    if key in _SKIP_ROW_TOKENS:
        return None
    match = re.fullmatch(r"\d+", text)
    return int(text) if match else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if not text or _header_key(text) in _SKIP_ROW_TOKENS or text in {"-", "—", "–"}:
        return None

    text = re.sub(r"[^0-9,.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")

    try:
        return float(text)
    except ValueError:
        return None


def _detect_columns(cells: list[str]) -> dict[str, int] | None:
    keys = [_header_key(cell) for cell in cells]
    mapping: dict[str, int] = {}

    for idx, key in enumerate(keys):
        compact = key.replace(" ", "")
        if key in {"#", "rank", "place", "position", "място", "класиране"}:
            mapping["rank_col"] = idx
        elif compact in {"фамилия", "surname", "lastname", "familyname"}:
            mapping["surname_col"] = idx
        elif compact in {"име", "name", "firstname", "fencer", "състезател"}:
            mapping["name_col"] = idx
        elif compact in {"клуб", "club", "team", "сала"}:
            mapping["club_col"] = idx
        elif compact in {"точки", "точка", "points", "pts", "totalpoints"}:
            mapping["points_col"] = idx

    if "rank_col" not in mapping and (
        "surname_col" in mapping or "name_col" in mapping
    ) and "points_col" in mapping:
        mapping["rank_col"] = 0

    if "rank_col" in mapping and (
        "name_col" in mapping or "surname_col" in mapping
    ):
        return mapping
    return None


def _parse_matrix(matrix: list[list[str]]) -> list[dict]:
    parsed: list[dict] = []
    col_map: dict[str, int] | None = None
    seen: set[tuple[int, str]] = set()

    for raw_cells in matrix:
        cells = [_clean_text(cell) for cell in raw_cells]
        if not any(cells):
            continue

        detected = _detect_columns(cells)
        if detected:
            col_map = detected
            continue

        if col_map is None:
            if len(cells) >= 4 and _parse_rank(cells[0]) is not None:
                col_map = {
                    "rank_col": 0,
                    "name_col": 1,
                    "club_col": 2,
                    "points_col": 3,
                }
            else:
                continue

        rank_col = col_map["rank_col"]
        if rank_col >= len(cells):
            continue
        rank = _parse_rank(cells[rank_col])
        if rank is None:
            continue

        name_parts: list[str] = []
        surname_col = col_map.get("surname_col")
        if surname_col is not None and surname_col < len(cells):
            name_parts.append(cells[surname_col])
        name_col = col_map.get("name_col")
        if name_col is not None and name_col < len(cells):
            name_parts.append(cells[name_col])
        name = _clean_text(" ".join(part for part in name_parts if part))
        if not name or _header_key(name) in _SKIP_ROW_TOKENS:
            continue

        club = None
        club_col = col_map.get("club_col")
        if club_col is not None and club_col < len(cells):
            club = _clean_text(cells[club_col]) or None

        points = None
        points_col = col_map.get("points_col")
        if points_col is not None and points_col < len(cells):
            points = _parse_points(cells[points_col])

        key = (rank, name)
        if key in seen:
            continue
        seen.add(key)
        parsed.append({"rank": rank, "name": name, "club": club, "points": points})

    return parsed


def _csv_to_matrix(text: str) -> list[list[str]]:
    return [row for row in csv.reader(StringIO(text)) if any(_clean_text(cell) for cell in row)]


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


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Return ranking rows with rank, name, club, and points."""
    if not html_or_text or not html_or_text.strip():
        return []

    text = html_or_text.strip()
    matrices: list[list[list[str]]]
    if "<table" in text.lower():
        matrices = _html_tables_to_matrices(text)
    else:
        matrices = [_csv_to_matrix(text)]

    rows: list[dict] = []
    for matrix in matrices:
        rows.extend(_parse_matrix(matrix))
    return rows


def _is_blocked_or_login_page(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _BLOCKED_MARKERS)


def _decode_response_text(response) -> str:
    content = getattr(response, "content", None)
    if content:
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError:
            pass
    return response.text


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public Bulgaria ranking CSV export."""
    url = RANKING_URLS.get((weapon, gender, category))
    if not url:
        print(f"    No scrapeable rankings at {BASE_URL} for {weapon} {gender} {category}")
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code == 404:
        print(f"    No scrapeable rankings at {url}")
        return None
    if response.status_code >= 400:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    text = _decode_response_text(response)
    if _is_blocked_or_login_page(text):
        print(f"    Blocked/login-only response at {url}")
        return None

    return text


def current_season() -> str:
    now = datetime.now(timezone.utc)
    season_end_year = now.year if now.month < 7 else now.year + 1
    season = f"{season_end_year - 1}-{season_end_year}"
    if season_to_string is not None:
        season = season_to_string(season_end_year)
    if normalize_season is not None:
        season = normalize_season(season)
    return season


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_bul").start()
    season = current_season()
    previous_state = get_state(SOURCE, "last_run")
    print(f"Bulgaria federation rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    parsed_combos = 0
    failed_combos: list[dict] = []

    try:
        for idx, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_label = f"{weapon} {gender} {category}"
            url = RANKING_URLS.get((weapon, gender, category), BASE_URL)
            print(f"  {combo_label}...")

            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                total_failed += 1
                failed_combos.append({"combo": combo_label, "url": url, "reason": "fetch_failed"})
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    total_failed += 1
                    failed_combos.append({"combo": combo_label, "url": url, "reason": "no_rows"})
                    print("    No rows parsed")
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
                            metadata={"source_url": url, "official_page": BASE_URL},
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    total_written += written
                    parsed_combos += 1
                    print(f"    Parsed {len(rows)} rows; written {written}")

            if idx < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        summary = {
            "season": season,
            "attempted_combos": len(RANKING_COMBOS),
            "parsed_combos": parsed_combos,
            "written": total_written,
            "failed": total_failed,
            "skipped": total_skipped,
            "failed_combos": failed_combos,
            "source_page": BASE_URL,
            "response_format": "text/csv",
            "previous_state": previous_state,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        set_state(SOURCE, "last_run", summary)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=summary,
        )
        if failed_combos:
            print(f"Failed combos: {failed_combos}")
        print(
            f"Done - combos={parsed_combos}/{len(RANKING_COMBOS)}, "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}"
        )
    except Exception as exc:
        set_state(
            SOURCE,
            "last_error",
            {"season": season, "error": str(exc), "at": datetime.now(timezone.utc).isoformat()},
        )
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

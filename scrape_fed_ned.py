"""
scrape_fed_ned.py - Netherlands KNAS national rankings scraper.

Probe results (2026-06-01):
  - Requested knfb.nl paths (/ranglijsten, /wedstrijdsport/ranglijsten,
    /rankings, /ranking) returned HTTP 200 text/html but no ranking content.
  - The public Dutch federation rankings are linked from knas.nl and hosted at:
      https://knas.onzeranglijsten.net/
  - Method: GET.
  - Response format: server-rendered UTF-8 HTML tables.
  - Public coverage: all 12 Senior/Junior x Foil/Epee/Sabre x Men/Women
    individual ranking combos.

KNAS table structure:
  Header: Plaats | Schermer | Vereniging | Punten
  Data rows: rank, fencer_id, name, club_id, club, points
"""

import re
import time
from datetime import UTC, datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "ned_fencing"
COUNTRY = "NED"
BASE_URL = "https://knas.onzeranglijsten.net"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": f"{BASE_URL}/",
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

RANKING_URLS = {
    ("Foil", "Men", "Senior"): f"{BASE_URL}/pag/8094/rls/3171",
    ("Foil", "Women", "Senior"): f"{BASE_URL}/pag/8094/rls/6844",
    ("Epee", "Men", "Senior"): f"{BASE_URL}/pag/8094/rls/8d4b",
    ("Epee", "Women", "Senior"): f"{BASE_URL}/pag/8094/rls/5f5e",
    ("Sabre", "Men", "Senior"): f"{BASE_URL}/pag/8094/rls/2167",
    ("Sabre", "Women", "Senior"): f"{BASE_URL}/pag/8094/rls/8c6a",
    ("Foil", "Men", "Junior"): f"{BASE_URL}/pag/8094/rls/f37a",
    ("Foil", "Women", "Junior"): f"{BASE_URL}/pag/8094/rls/fc41",
    ("Epee", "Men", "Junior"): f"{BASE_URL}/pag/8094/rls/4f54",
    ("Epee", "Women", "Junior"): f"{BASE_URL}/pag/8094/rls/f35b",
    ("Sabre", "Men", "Junior"): f"{BASE_URL}/pag/8094/rls/fc60",
    ("Sabre", "Women", "Junior"): f"{BASE_URL}/pag/8094/rls/777",
}

_HEADER_ALIASES = {
    "rank": {"plaats", "rank", "rang", "positie"},
    "name": {"schermer", "naam", "name", "fencer"},
    "club": {"vereniging", "club"},
    "points": {"punten", "points", "score", "totaal"},
}
_SKIP_ROW_TOKENS = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "disq",
    "disqualified",
    "samenvatting",
    "summary",
    "total",
    "totaal",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_header(value: str) -> str:
    value = _clean_text(value).casefold()
    return re.sub(r"[^a-z0-9]+", "", value)


def _parse_rank(value: str) -> int | None:
    match = re.fullmatch(r"\s*(\d+)\.?\s*", value)
    return int(match.group(1)) if match else None


def _parse_points(value: str) -> float | None:
    value = _clean_text(value)
    if not value:
        return None

    value = value.replace("\u00a0", "").replace(" ", "")
    value = re.sub(r"[^0-9,.\-]", "", value)
    if not value or value in {"-", ".", ","}:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        parts = value.split(",")
        if len(parts) > 1 and len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            value = "".join(parts)
        else:
            value = value.replace(",", ".")
    elif "." in value:
        parts = value.split(".")
        if len(parts) > 1 and len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            value = "".join(parts)

    try:
        return float(value)
    except ValueError:
        return None


def _table_header_map(table: Any) -> dict[str, int]:
    header_map: dict[str, int] = {}
    header_row = table.find("tr")
    if not header_row:
        return header_map

    headers = header_row.find_all("th", recursive=False)
    for idx, header in enumerate(headers):
        normalized = _normalize_header(header.get_text(" ", strip=True))
        for key, aliases in _HEADER_ALIASES.items():
            if normalized in aliases and key not in header_map:
                header_map[key] = idx
    return header_map


def _is_knas_six_cell_row(cells: list[str], header_map: dict[str, int]) -> bool:
    return (
        len(cells) >= 6
        and "name" in header_map
        and "club" in header_map
        and "points" in header_map
        and _parse_rank(cells[0]) is not None
        and re.fullmatch(r"\d+", cells[1] or "") is not None
        and re.fullmatch(r"\d+", cells[3] or "") is not None
    )


def _skip_non_ranking_row(cells: list[str]) -> bool:
    lowered = {_clean_text(cell).casefold() for cell in cells if _clean_text(cell)}
    return bool(lowered & _SKIP_ROW_TOKENS)


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse a KNAS/Onzeranglijsten ranking page.

    Returns rows with rank, name, club, and points. Dutch headers are supported
    directly, and English/French-style aliases are accepted for fixture and
    future compatibility. Names are preserved exactly apart from whitespace
    normalization; no title-casing is applied.
    """
    if not html_or_text:
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []

    parsed_rows = []
    for table in tables:
        header_map = _table_header_map(table)
        if not {"rank", "name", "points"}.issubset(header_map):
            continue

        for row in table.find_all("tr"):
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"], recursive=False)]
            if len(cells) < 4 or _skip_non_ranking_row(cells):
                continue

            rank = _parse_rank(cells[0])
            if rank is None:
                continue

            if _is_knas_six_cell_row(cells, header_map):
                name_idx, club_idx, points_idx = 2, 4, 5
            else:
                name_idx = header_map.get("name", 1)
                club_idx = header_map.get("club", 2)
                points_idx = header_map.get("points", 3)

            if max(name_idx, club_idx, points_idx) >= len(cells):
                continue

            name = cells[name_idx]
            if not name:
                continue

            club = cells[club_idx] or None
            points = _parse_points(cells[points_idx])
            parsed_rows.append(
                {
                    "rank": rank,
                    "name": name,
                    "club": club,
                    "points": points,
                }
            )

    return parsed_rows


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public KNAS ranking page, returning None on HTTP/network errors."""
    url = RANKING_URLS.get((weapon, gender, category))
    if not url:
        print(f"    No KNAS URL configured for {weapon} {gender} {category}")
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
    """Return the active fencing season string as YYYY-YYYY."""
    now = datetime.now(UTC)
    end_year = now.year if now.month < 7 else now.year + 1

    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "normalize_season"):
            return season_utils.normalize_season(end_year)
        if hasattr(season_utils, "season_to_string"):
            return season_utils.season_to_string(end_year)
    except ImportError:
        pass

    return _normalize_season_value(end_year)


def _normalize_season_value(value: Any) -> str:
    if isinstance(value, int):
        return f"{value - 1}-{value}"
    value = str(value)
    if re.fullmatch(r"\d{4}", value):
        year = int(value)
        return f"{year - 1}-{year}"
    return value


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_ned").start()
    season = current_season()
    print(f"KNAS Netherlands rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []
    skipped_combos: list[str] = []

    try:
        for idx, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_name = f"{weapon} {gender} {category}"
            print(f"  {combo_name}...")

            html = fetch_rankings_page(weapon, gender, category)
            if html is None:
                total_failed += 1
                failed_combos.append(combo_name)
            else:
                parsed = parse_rankings_table(html)
                if not parsed:
                    print("    No rows parsed")
                    total_skipped += 1
                    skipped_combos.append(combo_name)
                else:
                    url = RANKING_URLS[(weapon, gender, category)]
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
                            metadata={"source_url": url},
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    total_written += written
                    print(f"    Written {written} rows ({len(parsed)} parsed)")

            if idx < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "failed_combos": failed_combos,
                "skipped_combos": skipped_combos,
                "ranking_urls": {f"{w} {g} {c}": u for (w, g, c), u in RANKING_URLS.items()},
            },
        )
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}"
        )
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
        if skipped_combos:
            print(f"Skipped combos: {', '.join(skipped_combos)}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

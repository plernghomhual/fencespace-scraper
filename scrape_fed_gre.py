"""
scrape_fed_gre.py - Greece national federation rankings scraper.

Probe evidence:
  - Federation domain: https://fencing.org.gr
  - Public ranking reference: https://fencing.ophardt.online/en/search/rankings/151
  - Request method: GET
  - Response format: server-rendered Ophardt HTML when public.
  - Public combos expected by source matrix: Senior and U20 (Junior)
    Foil/Epee/Sabre for Men/Women. Missing links are reported per combo.

Local shell DNS was blocked for external probes in this sandbox and escalation was
rejected, so the scraper discovers live detail links from the Ophardt matrix at
runtime instead of relying on season-specific ranking IDs.
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
from scraper_state import set_state

try:
    from season_utils import normalize_season, season_to_string
except ImportError:  # pragma: no cover - compatibility fallback for older checkouts
    def season_to_string(season_int: int) -> str:
        return f"{season_int - 1:04d}-{season_int:04d}"

    def normalize_season(raw) -> str:
        if isinstance(raw, int):
            return season_to_string(raw)
        return str(raw)


SOURCE = "gre_fencing"
COUNTRY = "Greece"
BASE_URL = "https://fencing.ophardt.online/en/search/rankings/151"
FEDERATION_URL = "https://fencing.org.gr"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
    "Referer": FEDERATION_URL,
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

_RANK_HEADERS = {
    "rank",
    "ranking",
    "pos",
    "position",
    "place",
    "θεση",
    "καταταξη",
}
_NAME_HEADERS = {
    "name",
    "fencer",
    "athlete",
    "fullname",
    "ονομα",
    "ονοματεπωνυμο",
    "αθλητης",
    "αθλητρια",
}
_CLUB_HEADERS = {
    "club",
    "clubs",
    "clubname",
    "συλλογος",
    "σωματειο",
}
_POINT_HEADERS = {
    "points",
    "point",
    "pts",
    "totalpoints",
    "total",
    "βαθμοι",
    "βαθμολογια",
}
_SKIP_VALUES = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "ret",
    "total",
    "summary",
    "sum",
    "συνολο",
    "περιληψη",
    "ακυρο",
    "ακυρωση",
    "αποκλεισμος",
    "αποκλειστηκε",
}
_DETAIL_LINK_TEXTS = {"details", "detail", "biography", "bio"}
_RANKING_LINK_CACHE: dict[str, dict[tuple[str, str, str], str]] = {}


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY."""
    now = datetime.now(timezone.utc)
    season_end_year = now.year if now.month < 7 else now.year + 1
    return normalize_season(season_to_string(season_end_year))


def _season_year(season: str) -> str:
    match = re.search(r"(\d{4})\s*$", season)
    return match.group(1) if match else str(datetime.now(timezone.utc).year)


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _normalize_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _compact_text(value))
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^0-9a-z\u0370-\u03ff]+", "", without_marks.lower())


def _is_skip_text(value: str) -> bool:
    token = _normalize_token(value)
    return token in _SKIP_VALUES


def _cell_text(cell, *, prefer_name: bool = False) -> str:
    if prefer_name:
        name_link = cell.find("a", class_=lambda value: value and "dropdown-toggle" in value)
        if name_link:
            return _compact_text(name_link.get_text(" ", strip=True))

    clone = BeautifulSoup(str(cell), "html.parser").find(cell.name)
    if clone is None:
        return _compact_text(cell.get_text(" ", strip=True))

    for tag in clone.find_all(["script", "style", "table", "ul"]):
        tag.decompose()
    for tag in clone.find_all("div", class_=lambda value: value and "modal" in value):
        tag.decompose()

    link_texts = []
    for link in clone.find_all("a"):
        text = _compact_text(link.get_text(" ", strip=True))
        if text and _normalize_token(text) not in _DETAIL_LINK_TEXTS:
            link_texts.append(text)
    if prefer_name and link_texts:
        return link_texts[0]

    return _compact_text(clone.get_text(" ", strip=True))


def _parse_rank(raw: str) -> int | None:
    value = _compact_text(raw)
    if not value or _is_skip_text(value):
        return None

    match = re.match(r"^\s*(\d+)", value)
    if not match:
        return None

    rank = int(match.group(1))
    return rank if rank > 0 else None


def _parse_points(raw: str) -> float | None:
    value = _compact_text(raw)
    if not value or _is_skip_text(value):
        return None

    value = re.sub(r"[^0-9,.\-]", "", value)
    if value in {"", "-", ".", ","}:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            normalized = value.replace(".", "").replace(",", ".")
        else:
            normalized = value.replace(",", "")
    elif "," in value:
        left, right = value.rsplit(",", 1)
        normalized = f"{left.replace(',', '')}.{right}"
    elif "." in value:
        parts = value.split(".")
        if len(parts) > 2 and all(len(part) == 3 for part in parts[1:]):
            normalized = "".join(parts)
        else:
            normalized = value
    else:
        normalized = value

    try:
        return float(normalized)
    except ValueError:
        return None


def _top_level_rows(table) -> list:
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _row_cells(row) -> list:
    return row.find_all(["td", "th"], recursive=False)


def _header_indexes(headers: list[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for idx, header in enumerate(headers):
        token = _normalize_token(header)
        if "rank" not in indexes and token in _RANK_HEADERS:
            indexes["rank"] = idx
        elif "points" not in indexes and token in _POINT_HEADERS:
            indexes["points"] = idx
        elif "name" not in indexes and token in _NAME_HEADERS:
            indexes["name"] = idx
        elif "club" not in indexes and token in _CLUB_HEADERS:
            indexes["club"] = idx
    return indexes


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Greece ranking HTML into rank/name/club/points rows."""
    if not html_or_text:
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        rows = _top_level_rows(table)
        for header_index, header_row in enumerate(rows):
            header_cells = _row_cells(header_row)
            if not header_cells:
                continue

            headers = [_cell_text(cell) for cell in header_cells]
            indexes = _header_indexes(headers)
            if not {"rank", "name", "points"}.issubset(indexes):
                continue

            min_cells = max(indexes.values()) + 1
            for row in rows[header_index + 1:]:
                cells = _row_cells(row)
                if len(cells) < min_cells:
                    continue

                rank = _parse_rank(_cell_text(cells[indexes["rank"]]))
                if rank is None:
                    continue

                name = _cell_text(cells[indexes["name"]], prefer_name=True)
                if not name or _is_skip_text(name):
                    continue

                club = None
                if "club" in indexes and indexes["club"] < len(cells):
                    club = _cell_text(cells[indexes["club"]]) or None

                points = _parse_points(_cell_text(cells[indexes["points"]]))
                results.append({"rank": rank, "name": name, "club": club, "points": points})
            break

    return results


def _category_from_label(value: str) -> str | None:
    token = _normalize_token(value)
    if token in {"senior", "seniors", "ανδρωνγυναικων", "ανδρων", "γυναικων"}:
        return "Senior"
    if token in {"u20", "junior", "juniors", "juniores", "νεων", "νεοι", "νεανιδων"}:
        return "Junior"
    return None


def _extract_ranking_links(html: str, *, base_url: str = BASE_URL) -> dict[tuple[str, str, str], str]:
    soup = BeautifulSoup(html, "html.parser")
    links: dict[tuple[str, str, str], str] = {}
    column_order = [
        ("Epee", "Women"),
        ("Foil", "Women"),
        ("Sabre", "Women"),
        ("Epee", "Men"),
        ("Foil", "Men"),
        ("Sabre", "Men"),
    ]

    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 7:
            continue

        category = _category_from_label(_cell_text(cells[0]))
        if not category:
            continue

        for (weapon, gender), cell in zip(column_order, cells[1:7], strict=False):
            anchor = cell.find("a", href=True)
            if anchor:
                links[(weapon, gender, category)] = urljoin(base_url, anchor["href"])

    return links


def _discover_ranking_links(season_year: str) -> dict[tuple[str, str, str], str]:
    if season_year in _RANKING_LINK_CACHE:
        return _RANKING_LINK_CACHE[season_year]

    try:
        response = federation_request(
            "get",
            BASE_URL,
            headers=HEADERS,
            params={"season": season_year},
            timeout=20,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        print(f"    Ranking index request error for {BASE_URL}: {exc}")
        _RANKING_LINK_CACHE[season_year] = {}
        return {}

    if response.status_code != 200:
        print(f"    No scrapeable rankings at {BASE_URL} (HTTP {response.status_code})")
        _RANKING_LINK_CACHE[season_year] = {}
        return {}

    links = _extract_ranking_links(response.text, base_url=response.url)
    if not links:
        print(f"    No scrapeable rankings at {BASE_URL}")

    _RANKING_LINK_CACHE[season_year] = links
    return links


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Greece ranking detail page. Returns None on 404/network failures."""
    season_year = _season_year(current_season())
    links = _discover_ranking_links(season_year)
    url = links.get((weapon, gender, category))
    if not url:
        print(f"    No public ranking link for {weapon} {gender} {category} season={season_year}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=25, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Ranking request error for {url}: {exc}")
        return None

    if response.status_code == 200:
        return response.text

    print(f"    HTTP {response.status_code} for {url}")
    return None


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main():
    run_log = ScraperRunLogger("scrape_fed_gre").start()
    season = current_season()
    print(f"Greece federation rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []
    working_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            label = _combo_label(weapon, gender, category)
            print(f"  {label}...")

            html = fetch_rankings_page(weapon, gender, category)
            if not html:
                total_failed += 1
                failed_combos.append(label)
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(html)
            if not parsed:
                print("    No rows parsed")
                total_failed += 1
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
                    metadata={"source_url": BASE_URL},
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Written {written} rows ({len(parsed)} parsed)")
            total_written += written
            working_combos.append(label)
            time.sleep(REQUEST_DELAY)

        summary = {
            "season": season,
            "base_url": BASE_URL,
            "method": "GET",
            "format": "html",
            "combos": len(RANKING_COMBOS),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
        }
        set_state(SOURCE, "last_run", summary)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=summary,
        )
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}"
        )
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

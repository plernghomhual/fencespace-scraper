"""
scrape_fed_bra.py - Confederação Brasileira de Esgrima rankings scraper.

Probe evidence:
  - CBE page: https://cbesgrima.org.br/ranking/
  - Public rankings target: https://fencing.ophardt.online/pt/search/rankings/163
  - Request method: GET
  - Response format: server-rendered HTML
  - Public combos: Senior and U20 (Junior) for Foil/Epee/Sabre, Men/Women.

Ophardt matrix order for each category row:
  feminino: Espada, Florete, Sabre; masculino: Espada, Florete, Sabre
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import set_state

try:
    from season_utils import season_from_string, season_to_string
except ImportError:  # pragma: no cover - compatibility fallback for pre-Agent-5 checkouts
    def season_to_string(season_int: int) -> str:
        return f"{season_int - 1:04d}-{season_int:04d}"

    def season_from_string(season_str: str) -> int:
        value = str(season_str).strip()
        if "-" in value:
            return int(value.split("-")[-1])
        return int(value)


SOURCE = "bra_fencing"
COUNTRY = "BRA"
BASE_URL = "https://fencing.ophardt.online/pt/search/rankings/163"
CBE_RANKING_URL = "https://cbesgrima.org.br/ranking/"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": CBE_RANKING_URL,
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

_RANK_HEADERS = {"rank", "pos", "posicao", "posicao", "colocacao", "classificacao", "lugar"}
_NAME_HEADERS = {"nome", "atleta", "name", "fencer", "tirador"}
_CLUB_HEADERS = {"clube", "clubes", "club"}
_POINT_HEADERS = {"pontos", "pts", "points", "totalpoints", "total"}
_SKIP_VALUES = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "ret",
    "total",
    "totais",
    "resumo",
    "sumario",
    "summary",
    "desclassificado",
    "desclassificada",
    "ausente",
}
_RANKING_LINK_CACHE: dict[str, dict[tuple[str, str, str], str]] = {}


def current_season() -> str:
    """Return the current FIE-style season range as YYYY-YYYY."""
    now = datetime.now(timezone.utc)
    season_end_year = now.year if now.month < 7 else now.year + 1
    return season_to_string(season_end_year)


def _season_year(season: str) -> str:
    return str(season_from_string(season))


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _normalize_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


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

    for tag in clone.find_all(["table", "ul"]):
        tag.decompose()
    for tag in clone.find_all("div", class_=lambda value: value and "modal" in value):
        tag.decompose()

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
        parts = value.split(",")
        if len(parts) > 2:
            normalized = "".join(parts[:-1]) + "." + parts[-1]
        else:
            left, right = parts
            if len(right) == 3 and len(left) <= 3 and left.lstrip("-").isdigit() and right.isdigit():
                normalized = left + right
            else:
                normalized = left + "." + right
    elif "." in value:
        parts = value.split(".")
        if len(parts) > 2 and all(len(part) == 3 for part in parts[1:]):
            normalized = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0].lstrip("-")) <= 3:
            normalized = "".join(parts)
        else:
            normalized = value
    else:
        normalized = value

    try:
        return float(normalized)
    except ValueError:
        return None


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


def _header_row(table):
    thead = table.find("thead")
    if thead:
        row = thead.find("tr")
        if row:
            return row
    return table.find("tr")


def _data_rows(table, header_row) -> list:
    classes = table.get("class") or []
    if "rankingbody" in classes:
        return table.find_all("tr", recursive=False)

    rows = []
    for tbody in table.find_all("tbody", recursive=False):
        rows.extend(tbody.find_all("tr", recursive=False))
    if rows:
        return rows

    direct_rows = [row for row in table.find_all("tr", recursive=False) if row is not header_row]
    if direct_rows:
        return direct_rows

    return [row for row in table.find_all("tr") if row is not header_row]


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Brazil ranking HTML into rank/name/club/points rows."""
    if not html_or_text:
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        header_row = _header_row(table)
        if not header_row:
            continue

        header_cells = header_row.find_all(["th", "td"], recursive=False)
        headers = [_cell_text(cell) for cell in header_cells]
        indexes = _header_indexes(headers)
        required = {"rank", "name", "points"}
        if not required.issubset(indexes):
            continue

        min_cells = max(indexes.values()) + 1
        for row in _data_rows(table, header_row):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) < min_cells:
                continue

            rank_text = _cell_text(cells[indexes["rank"]])
            rank = _parse_rank(rank_text)
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

    return results


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

        row_label = _normalize_token(_cell_text(cells[0]))
        if row_label == "senior":
            category = "Senior"
        elif row_label in {"u20", "junior", "juniores"}:
            category = "Junior"
        else:
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
        response = requests.get(
            BASE_URL,
            headers=HEADERS,
            params={"season": season_year},
            timeout=20,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        print(f"    Ranking index request error: {exc}")
        _RANKING_LINK_CACHE[season_year] = {}
        return {}

    if response.status_code != 200:
        print(f"    Ranking index HTTP {response.status_code} for {response.url}")
        _RANKING_LINK_CACHE[season_year] = {}
        return {}

    links = _extract_ranking_links(response.text, base_url=response.url)
    _RANKING_LINK_CACHE[season_year] = links
    return links


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Brazil ranking detail page. Returns None on 404/network failures."""
    season_year = _season_year(current_season())
    links = _discover_ranking_links(season_year)
    url = links.get((weapon, gender, category))
    if not url:
        print(f"    No public ranking link for {weapon} {gender} {category} season={season_year}")
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
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
    run_log = ScraperRunLogger("scrape_fed_bra").start()
    season = current_season()
    print(f"Brazil CBE rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []

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
            time.sleep(REQUEST_DELAY)

        summary = {
            "season": season,
            "combos": len(RANKING_COMBOS),
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

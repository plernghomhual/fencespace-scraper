"""
scrape_fed_dom.py - Dominican Republic federation rankings scraper.

Probe evidence, 2026-06-02:
  - Requested domain https://fedesgrimard.org/ did not resolve.
  - Current public federation site found via FIE/search: https://www.fedomes.org/
  - GET https://www.fedomes.org/, /ranking, /rankings, /resultados-y-ranking,
    /documentos, sitemap pages, and common PDF/XLS/XLSX asset guesses returned
    generic Aruba Supersite HTML or 404 assets.
  - No visible ranking tables, public file links, forms, or usable ranking API/XHR
    payloads were exposed.
  - Public combos found: 0/12 Senior/Junior Foil/Epee/Sabre Men/Women.

This module keeps a robust Spanish HTML parser ready for future public data, but
the live fetch path is intentionally a documented no-public-data stub today.
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
from scraper_state import set_state

try:
    from season_utils import normalize_season
except ImportError:  # pragma: no cover - compatibility with older checkouts
    def normalize_season(raw) -> str:
        if isinstance(raw, int):
            return f"{raw - 1:04d}-{raw:04d}"
        return str(raw)


SOURCE = "dom_fencing"
COUNTRY = "Dominican Republic"
BASE_URL = "https://www.fedomes.org"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-DO,es;q=0.9,en;q=0.8",
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

PROBED_URLS = (
    "https://fedesgrimard.org/",
    "http://fedesgrimard.org/",
    f"{BASE_URL}/",
    f"{BASE_URL}/ranking",
    f"{BASE_URL}/rankings",
    f"{BASE_URL}/resultados-y-ranking",
    f"{BASE_URL}/documentos",
    f"{BASE_URL}/sitemap.xml",
    f"{BASE_URL}/public/ranking.pdf",
    f"{BASE_URL}/public/ranking.xlsx",
    f"{BASE_URL}/public/ranking.xls",
)

# No durable public Dominican ranking URL was found during the probe. Tests can
# monkeypatch this mapping to exercise future public fetch behavior.
PUBLIC_RANKING_URLS: dict[tuple[str, str, str], str] = {}

_RANK_HEADERS = {"pos", "posicion", "puesto", "ranking", "rank", "lugar"}
_NAME_HEADERS = {"nombre", "atleta", "tirador", "tiradora", "deportista", "name"}
_CLUB_HEADERS = {
    "club",
    "clubes",
    "asociacion",
    "asociacionclub",
    "asociacionyclub",
    "sala",
    "escuela",
    "entidad",
}
_POINT_HEADERS = {"puntos", "puntostotales", "pts", "totalpuntos", "total", "points"}
_SKIP_VALUES = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "ret",
    "total",
    "totales",
    "resumen",
    "summary",
    "sumario",
    "sinranking",
    "noranking",
    "descalificado",
    "descalificada",
}


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _strip_accents(_clean_text(value).lower()))


def _parse_rank(value: str) -> int | None:
    text = _header_key(value.strip("."))
    if not text or text in _SKIP_VALUES:
        return None
    if any(skip in text for skip in _SKIP_VALUES):
        return None
    match = re.match(r"^(\d+)", text)
    return int(match.group(1)) if match else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        text = "".join(parts[:-1]) + "." + parts[-1] if len(parts) > 2 else text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def _row_cells(row) -> list:
    return row.find_all(["td", "th"], recursive=False)


def _find_header_mapping(cells: list) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(cells):
        key = _header_key(cell.get_text(" ", strip=True))
        if key in _RANK_HEADERS:
            mapping["rank"] = index
        elif key in _NAME_HEADERS:
            mapping["name"] = index
        elif key in _CLUB_HEADERS:
            mapping["club"] = index
        elif key in _POINT_HEADERS:
            mapping["points"] = index

    return mapping if {"rank", "name", "points"}.issubset(mapping) else None


def _row_has_skip_marker(cells: list) -> bool:
    values = [_header_key(cell.get_text(" ", strip=True)) for cell in cells]
    return any(value in _SKIP_VALUES for value in values)


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse a Spanish federation ranking table into rank/name/club/points rows."""
    if not html_or_text:
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        mapping = None
        start_index = 0

        for index, row in enumerate(rows):
            cells = _row_cells(row)
            mapping = _find_header_mapping(cells)
            if mapping:
                start_index = index + 1
                break

        if not mapping:
            continue

        max_index = max(mapping.values())
        for row in rows[start_index:]:
            cells = _row_cells(row)
            if len(cells) <= max_index or _row_has_skip_marker(cells):
                continue

            rank = _parse_rank(cells[mapping["rank"]].get_text(" ", strip=True))
            name = _clean_text(cells[mapping["name"]].get_text(" ", strip=True))
            points = _parse_points(cells[mapping["points"]].get_text(" ", strip=True))
            club = None
            if "club" in mapping:
                club = _clean_text(cells[mapping["club"]].get_text(" ", strip=True)) or None

            if rank is None or not name or points is None:
                continue

            results.append({"rank": rank, "name": name, "club": club, "points": points})

    return results


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def ranking_url_for(weapon: str, gender: str, category: str) -> str | None:
    return PUBLIC_RANKING_URLS.get((weapon, gender, category))


def _looks_login_only(text: str) -> bool:
    lowered = _strip_accents(text.lower())
    return (
        "type='password'" in lowered
        or 'type="password"' in lowered
        or "iniciar sesion" in lowered
        or "login" in lowered
        or "acceso restringido" in lowered
    )


def _looks_js_only_shell(text: str) -> bool:
    lowered = text.lower()
    has_script = "<script" in lowered
    has_table = "<table" in lowered
    has_app_shell = 'id="app"' in lowered or "id='app'" in lowered or "enable javascript" in lowered
    return has_script and has_app_shell and not has_table


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one rankings page, returning None for missing, blocked, or non-public data."""
    label = _combo_label(weapon, gender, category)
    url = ranking_url_for(weapon, gender, category)
    if not url:
        print(f"    No scrapeable rankings at {BASE_URL}/ranking for {label}; probed {', '.join(PROBED_URLS)}")
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code == 404:
        print(f"    HTTP 404 for {url}")
        return None
    if response.status_code in {401, 403}:
        print(f"    Access blocked/login required: HTTP {response.status_code} for {url}")
        return None
    if response.status_code >= 400:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    text = response.text or ""
    if _looks_login_only(text):
        print(f"    Login-only rankings page at {url}")
        return None
    if _looks_js_only_shell(text):
        print(f"    JS-only rankings shell without public API at {url}")
        return None

    return text


def current_season() -> str:
    """Return the current federation season as YYYY-YYYY using season_utils when available."""
    now = datetime.now(timezone.utc)
    season_end_year = now.year if now.month < 7 else now.year + 1
    return normalize_season(season_end_year)


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_dom").start()
    season = current_season()
    print(f"Dominican Republic federation rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos: list[str] = []
    failed_combos: list[str] = []
    skipped_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            label = _combo_label(weapon, gender, category)
            print(f"  {label}...")
            has_public_url = ranking_url_for(weapon, gender, category) is not None
            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                if has_public_url:
                    total_failed += 1
                    failed_combos.append(label)
                else:
                    total_skipped += 1
                    skipped_combos.append(label)
                continue

            parsed = parse_rankings_table(content)
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
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Written {written} rows")
            total_written += written
            working_combos.append(label)
            time.sleep(REQUEST_DELAY)

        metadata = {
            "probed_urls": list(PROBED_URLS),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
            "skipped_combos": skipped_combos,
            "public_combo_count": len(PUBLIC_RANKING_URLS),
            "data_format": "stub",
        }
        set_state(
            SOURCE,
            "last_run",
            {
                "season": season,
                "written": total_written,
                "failed": total_failed,
                "skipped": total_skipped,
                "metadata": metadata,
            },
        )
        run_log.complete(written=total_written, failed=total_failed, skipped=total_skipped, metadata=metadata)
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"working_combos={len(working_combos)}/{len(RANKING_COMBOS)}"
        )
        if total_written == 0 and (total_skipped + total_failed) > 0:
            print(f"[WARNING] {SOURCE}: zero rows written after processing all targets — check URL config or source availability")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

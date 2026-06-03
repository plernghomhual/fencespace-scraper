"""
scrape_fed_ven.py - Venezuela national federation rankings scraper.

Probe findings, 2026-06-02:
  - Probe target: fevenesgrima.com.ve.
  - Method: GET with browser-like headers.
  - Paths checked from the sandbox: /, /ranking, /rankings, /ranking-nacional,
    /rankings-nacionales, /clasificacion, /clasificaciones, /resultados,
    /competencias, and WordPress wp-json search/page/post ranking endpoints on
    apex and www hosts, over both HTTPS and HTTP.
  - Response format: no response body; every probed URL failed DNS resolution.
  - Escalated outside-sandbox confirmation was blocked by the approval system,
    so no durable public ranking source could be verified.
  - Public combos found: 0/12. The scraper records all standard Venezuela
    combos as attempted and exits successfully without speculative live fetches.

If a public ranking URL appears later, add it to PUBLIC_RANKING_URLS. The fetch
and parser paths are already implemented for Spanish Posicion/Puesto,
Esgrimista/Nombre, Estado/Club, and Puntos HTML or delimited text tables.
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "ven_fencing"
COUNTRY = "Venezuela"
BASE_URL = "https://fevenesgrima.com.ve"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-VE,es;q=0.9,en;q=0.8",
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

PROBED_HOSTS = [
    "https://fevenesgrima.com.ve",
    "https://www.fevenesgrima.com.ve",
    "http://fevenesgrima.com.ve",
    "http://www.fevenesgrima.com.ve",
]
PROBED_PATHS = [
    "/",
    "/ranking",
    "/rankings",
    "/ranking-nacional",
    "/rankings-nacionales",
    "/clasificacion",
    "/clasificaciones",
    "/resultados",
    "/competencias",
    "/wp-json/wp/v2/search?search=ranking",
    "/wp-json/wp/v2/pages?search=ranking",
    "/wp-json/wp/v2/posts?search=ranking",
]
PROBED_URLS = [f"{host}{path}" for host in PROBED_HOSTS for path in PROBED_PATHS]

PUBLIC_RANKING_URLS: dict[tuple[str, str, str], str] = {}

RANK_HEADER_ALIASES = {"rank", "ranking", "position", "pos", "puesto", "posicion", "#", "lugar"}
NAME_HEADER_ALIASES = {"name", "nombre", "esgrimista", "tirador", "tiradora", "atleta"}
CLUB_HEADER_ALIASES = {
    "club",
    "estado",
    "asociacion",
    "entidad",
    "delegacion",
    "equipo",
    "sala",
}
POINTS_HEADER_ALIASES = {"points", "point", "puntos", "puntaje", "totalpoints", "pts"}

SKIP_ROW_TOKENS = {
    "",
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "baja",
    "ret",
    "retirado",
    "descalificado",
    "descalificada",
    "total",
    "totales",
    "summary",
    "resumen",
    "subtotal",
    "notranked",
    "sinranking",
}

NO_DATA_MARKERS = {
    "no rankings available",
    "no ranking available",
    "no hay ranking",
    "no hay datos",
    "no hay resultados",
    "sin ranking",
    "sin resultados",
    "no disponible para esta categoria",
    "no se encontraron resultados",
}

BLOCKED_MARKERS = {
    "access denied",
    "forbidden",
    "please log in",
    "please login",
    "sign in",
    "login required",
    "password",
    "iniciar sesion",
    "inicio de sesion",
    "contraseña",
}

JS_ONLY_MARKERS = {
    "please enable javascript",
    "enable javascript to continue",
    "requires javascript",
    "debe activar javascript",
    "requiere javascript",
}


def _clean_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _header_key(value: str) -> str:
    text = _strip_accents(_clean_text(value)).lower().replace("&", " and ").replace("/", " ")
    if text == "#":
        return "#"
    return re.sub(r"[^a-z0-9]+", "", text)


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value).lower()
    key = _header_key(text)
    if key in SKIP_ROW_TOKENS or any(token in key for token in SKIP_ROW_TOKENS if token):
        return None
    if re.search(r"[a-z]", _strip_accents(text)):
        return None

    match = re.match(r"^\s*(\d+)", text)
    if not match:
        return None

    rank = int(match.group(1))
    return rank if rank > 0 else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value).replace(" ", "")
    if not text or _header_key(text) in SKIP_ROW_TOKENS or text in {"-", ".", ",", "—", "–"}:
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
        head, tail = text.rsplit(",", 1)
        if len(tail) in (1, 2, 3, 4):
            text = f"{head.replace(',', '')}.{tail}"
        else:
            text = text.replace(",", "")

    try:
        return float(text)
    except ValueError:
        return None


def _row_cells(row: Tag) -> list[Tag]:
    return row.find_all(["td", "th"], recursive=False)


def _top_level_rows(table: Tag) -> list[Tag]:
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _find_header_mapping(labels: Iterable[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, label in enumerate(labels):
        key = _header_key(label)
        if key in RANK_HEADER_ALIASES:
            mapping["rank"] = index
        elif key in NAME_HEADER_ALIASES:
            mapping["name"] = index
        elif key in CLUB_HEADER_ALIASES:
            mapping["club"] = index
        elif key in POINTS_HEADER_ALIASES or key.startswith("puntos") or key.startswith("puntaje"):
            mapping["points"] = index

    required = {"rank", "name", "points"}
    return mapping if required.issubset(mapping) else None


def _append_row(results: list[dict], cells: list[str], mapping: dict[str, int]) -> None:
    required_index = max(mapping["rank"], mapping["name"], mapping["points"])
    if len(cells) <= required_index:
        return

    rank = _parse_rank(cells[mapping["rank"]])
    if rank is None:
        return

    name = _clean_text(cells[mapping["name"]])
    if not name or _header_key(name) in SKIP_ROW_TOKENS:
        return

    club = None
    if "club" in mapping and mapping["club"] < len(cells):
        club = _clean_text(cells[mapping["club"]]) or None

    results.append(
        {
            "rank": rank,
            "name": name,
            "club": club,
            "points": _parse_points(cells[mapping["points"]]),
        }
    )


def _parse_delimited_text(text: str) -> list[dict]:
    lines = [_clean_text(line) for line in text.splitlines() if _clean_text(line)]
    if not lines:
        return []

    delimiter = "\t" if any("\t" in line for line in lines) else "|"
    if not any(delimiter in line for line in lines):
        return []

    rows = [[_clean_text(cell) for cell in line.split(delimiter)] for line in lines if delimiter in line]
    mapping = None
    results: list[dict] = []
    for cells in rows:
        if mapping is None:
            mapping = _find_header_mapping(cells)
            if mapping is not None:
                continue
            if len(cells) >= 4 and _parse_rank(cells[0]) is not None:
                mapping = {"rank": 0, "name": 1, "club": 2, "points": 3}
        if mapping:
            _append_row(results, cells, mapping)
    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Venezuela rankings into rows with rank, name, club, and points."""
    if not html_or_text or not _clean_text(html_or_text):
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        lower = _strip_accents(html_or_text).lower()
        if any(marker in lower for marker in NO_DATA_MARKERS):
            return []
        return _parse_delimited_text(html_or_text)

    results: list[dict] = []
    for table in tables:
        mapping = None
        for row in _top_level_rows(table):
            cells = _row_cells(row)
            if not cells:
                continue

            labels = [cell.get_text(" ", strip=True) for cell in cells]
            if mapping is None:
                mapping = _find_header_mapping(labels)
                if mapping is not None:
                    continue
                if len(labels) >= 4 and _parse_rank(labels[0]) is not None:
                    mapping = {"rank": 0, "name": 1, "club": 2, "points": 3}

            if mapping:
                _append_row(results, labels, mapping)

    return results


def ranking_url_for(weapon: str, gender: str, category: str) -> str | None:
    return PUBLIC_RANKING_URLS.get((weapon, gender, category))


def _is_unusable_public_page(html: str) -> bool:
    lower = _strip_accents(html).lower()
    has_table = BeautifulSoup(html, "html.parser").find("table") is not None
    if not has_table and any(marker in lower for marker in NO_DATA_MARKERS):
        return True
    if any(marker in lower for marker in BLOCKED_MARKERS):
        return True
    return any(marker in lower for marker in JS_ONLY_MARKERS)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Venezuela rankings page, returning None for missing or blocked data."""
    url = ranking_url_for(weapon, gender, category)
    if not url:
        print(f"    No scrapeable rankings at {BASE_URL} for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    if _is_unusable_public_page(response.text):
        print(f"    Login, blocked, no-data, or JavaScript-only ranking page at {url}")
        return None

    return response.text


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY, using season_utils if present."""
    now = datetime.now(timezone.utc)
    end_year = now.year if now.month < 7 else now.year + 1
    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "normalize_season"):
            return season_utils.normalize_season(end_year)
        if hasattr(season_utils, "season_to_string"):
            return season_utils.season_to_string(end_year)
    except Exception:
        pass

    return f"{end_year - 1:04d}-{end_year:04d}"


def _combo_label(combo: tuple[str, str, str]) -> str:
    weapon, gender, category = combo
    return f"{weapon} {gender} {category}"


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_ven").start()
    season = current_season()
    print(f"Venezuela federation rankings - season {season}")
    print(f"No scrapeable rankings at {BASE_URL}")
    print("Probed URLs:")
    for url in PROBED_URLS:
        print(f"  {url}")

    total_written = 0
    total_failed = 0
    failed_combos: list[dict[str, str]] = []
    _ = get_state(SOURCE, "last_run")

    try:
        for combo in RANKING_COMBOS:
            weapon, gender, category = combo
            print(f"  {_combo_label(combo)}...")
            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                total_failed += 1
                failed_combos.append({"combo": _combo_label(combo), "reason": "no_public_ranking"})
                if ranking_url_for(weapon, gender, category):
                    time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(content)
            if not parsed:
                print("    No rows parsed")
                total_failed += 1
                failed_combos.append({"combo": _combo_label(combo), "reason": "no_rows_parsed"})
                time.sleep(REQUEST_DELAY)
                continue

            source_url = ranking_url_for(weapon, gender, category) or BASE_URL
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
                    metadata={"source_url": source_url, "cc": "ven"},
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Written {written} rows")
            total_written += written
            time.sleep(REQUEST_DELAY)

        metadata = {
            "season": season,
            "probed_urls": PROBED_URLS,
            "request_method": "GET",
            "response_format": "unavailable_dns_failure_stub",
            "combos_attempted": len(RANKING_COMBOS),
            "combos_working": len(RANKING_COMBOS) - total_failed,
            "failed_combos": failed_combos,
        }
        set_state(
            SOURCE,
            "last_run",
            {
                "season": season,
                "written": total_written,
                "failed": total_failed,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata,
            },
        )
        run_log.complete(written=total_written, failed=total_failed, skipped=0, metadata=metadata)
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, "
            f"combos_working={len(RANKING_COMBOS) - total_failed}/12"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

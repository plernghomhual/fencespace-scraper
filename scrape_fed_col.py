"""
scrape_fed_col.py - Colombia federation national rankings scraper.

Probe evidence:
  Original domain `esgrimacolombia.co` did not resolve from the sandboxed local
  probe. Public rankings are available from:
    GET https://sistemainfo.fedesgrimacolombia.com/rankings
    GET https://sistemainfo.fedesgrimacolombia.com/rankings/<id>

The public ranking pages are HTML and expose Spanish labels:
  Puesto | Puntos | Nombre | Liga | Club | Fecha de nacimiento
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

SOURCE = "col_fencing"
COUNTRY = "Colombia"
BASE_URL = "https://sistemainfo.fedesgrimacolombia.com"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.7",
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
    ("Foil", "Men", "Senior"): f"{BASE_URL}/rankings/61",
    ("Foil", "Women", "Senior"): f"{BASE_URL}/rankings/60",
    ("Epee", "Men", "Senior"): f"{BASE_URL}/rankings/5",
    ("Epee", "Women", "Senior"): f"{BASE_URL}/rankings/53",
    ("Sabre", "Men", "Senior"): f"{BASE_URL}/rankings/57",
    ("Sabre", "Women", "Senior"): f"{BASE_URL}/rankings/56",
    ("Foil", "Men", "Junior"): f"{BASE_URL}/rankings/43",
    ("Foil", "Women", "Junior"): f"{BASE_URL}/rankings/42",
    ("Epee", "Men", "Junior"): f"{BASE_URL}/rankings/4",
    ("Epee", "Women", "Junior"): f"{BASE_URL}/rankings/3",
    ("Sabre", "Men", "Junior"): f"{BASE_URL}/rankings/41",
    ("Sabre", "Women", "Junior"): f"{BASE_URL}/rankings/40",
}

WEAPON_LABELS = {"Foil": "FLORETE", "Epee": "ESPADA", "Sabre": "SABLE"}
GENDER_LABELS = {"Men": "MASCULINO", "Women": "FEMENINO"}
CATEGORY_LABELS = {"Senior": "MAYORES", "Junior": "JUVENIL"}

SKIP_TOKENS = {"dns", "dnf", "dq", "dsq", "wd", "ret", "np", "n/p"}
SUMMARY_MARKERS = {
    "total",
    "totales",
    "summary",
    "resumen",
    "temporada anterior",
    "fecha",
    "cantidad de competencias",
}
NO_DATA_MARKERS = (
    "no hay registros",
    "sin registros",
    "no existen registros",
    "no data",
)
LEAGUE_MARKERS = [
    "CUNDINAMARCA",
    "INTERNACIONAL",
    "ANTIOQUIA",
    "RISARALDA",
    "SANTANDER",
    "GUATEMALA",
    "EL SALVADOR",
    "ECUADOR",
    "BOGOTA",
    "BOGOTÁ",
    "CALDAS",
    "TOLIMA",
    "VALLE",
    "META",
    "CESAR",
    "FFAA",
    "FCE",
    "CHILE",
    "PANAMA",
    "HONDURAS",
]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalise_header(value: str) -> str:
    value = _strip_accents(_clean_text(value)).lower()
    return re.sub(r"[^a-z0-9 ]+", "", value)


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value).strip(".º°")
    if _normalise_header(text) in SUMMARY_MARKERS:
        return None
    match = re.match(r"^(\d+)$", text)
    if not match:
        return None
    return int(match.group(1))


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if not text or text in {"-", "--"}:
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
    try:
        return float(text)
    except ValueError:
        return None


def _looks_like_header(cells: list[str]) -> bool:
    headers = {_normalise_header(cell) for cell in cells}
    return bool(
        headers
        & {
            "puesto",
            "posicion",
            "ranking",
            "rank",
            "puntos",
            "puntaje",
            "nombre",
            "deportista",
        }
    ) and _parse_rank(cells[0]) is None


def _header_mapping(cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(cells):
        header = _normalise_header(cell)
        if header in {"puesto", "posicion", "ranking", "rank"}:
            mapping.setdefault("rank", idx)
        elif header in {"puntos", "puntaje", "pts", "total puntos"}:
            mapping.setdefault("points", idx)
        elif header in {"nombre", "deportista", "atleta", "tirador", "tiradora"}:
            mapping.setdefault("name", idx)
        elif header == "club":
            mapping.setdefault("club", idx)
    return mapping


def _default_mapping(cells: list[str]) -> dict[str, int]:
    mapping = {"rank": 0, "points": 1, "name": 2}
    if len(cells) > 4:
        mapping["club"] = 4
    elif len(cells) > 3:
        mapping["club"] = 3
    return mapping


def _is_skip_row(cells: list[str]) -> bool:
    normalized_cells = [_normalise_header(cell) for cell in cells]
    if any(cell in SKIP_TOKENS for cell in normalized_cells):
        return True
    joined = " ".join(normalized_cells)
    return any(marker in joined for marker in SUMMARY_MARKERS)


def _cell(cells: list[str], mapping: dict[str, int], key: str) -> str:
    idx = mapping.get(key)
    if idx is None or idx >= len(cells):
        return ""
    return _clean_text(cells[idx])


def _parse_cells(cells: list[str], mapping: dict[str, int]) -> dict | None:
    if len(cells) < 3 or _is_skip_row(cells):
        return None

    rank = _parse_rank(_cell(cells, mapping, "rank"))
    points = _parse_points(_cell(cells, mapping, "points"))
    name = _cell(cells, mapping, "name")
    club = _cell(cells, mapping, "club") or None

    if rank is None or points is None or not name:
        return None
    if _normalise_header(name) in SKIP_TOKENS:
        return None

    return {"rank": rank, "name": name, "club": club, "points": points}


def _parse_html_tables(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        mapping: dict[str, int] | None = None
        for tr in table.find_all("tr"):
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
            cells = [cell for cell in cells if cell]
            if not cells:
                continue
            if _looks_like_header(cells):
                mapping = _header_mapping(cells)
                continue
            row = _parse_cells(cells, mapping or _default_mapping(cells))
            if row:
                results.append(row)

    return results


def _parse_pipe_text(text: str) -> list[dict]:
    results: list[dict] = []
    mapping: dict[str, int] | None = None

    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line or set(line.replace("|", "").strip()) <= {"-"}:
            continue
        if "|" in line:
            cells = [_clean_text(part) for part in line.strip("|").split("|")]
            cells = [cell for cell in cells if cell]
            if _looks_like_header(cells):
                mapping = _header_mapping(cells)
                continue
            row = _parse_cells(cells, mapping or _default_mapping(cells))
            if row:
                results.append(row)

    return results


def _parse_plain_text_lines(text: str) -> list[dict]:
    results: list[dict] = []
    row_re = re.compile(r"^(\d+)\s+([0-9][0-9.,]*)\s+(.+?)\s+(\d{4}-\d{2}-\d{2})$")

    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line or _normalise_header(line) in SUMMARY_MARKERS:
            continue
        match = row_re.match(line)
        if not match:
            continue
        rank_text, points_text, body, _birthdate = match.groups()
        rank = _parse_rank(rank_text)
        points = _parse_points(points_text)
        if rank is None or points is None:
            continue

        name = body
        club = None
        upper_body = _strip_accents(body).upper()
        for marker in LEAGUE_MARKERS:
            marker_pos = upper_body.find(f" {marker} ")
            if marker_pos > 0:
                name = body[:marker_pos].strip()
                club = body[marker_pos + len(marker) + 2 :].strip() or None
                break
        if name:
            results.append({"rank": rank, "name": name, "club": club, "points": points})

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Colombian federation ranking rows into rank/name/club/points dicts."""
    if not html_or_text or not html_or_text.strip():
        return []

    lower_text = _strip_accents(html_or_text).lower()
    if any(marker in lower_text for marker in NO_DATA_MARKERS):
        return []

    html_rows = _parse_html_tables(html_or_text)
    if html_rows:
        return html_rows

    pipe_rows = _parse_pipe_text(html_or_text)
    if pipe_rows:
        return pipe_rows

    return _parse_plain_text_lines(html_or_text)


def build_rankings_url(weapon: str, gender: str, category: str) -> str | None:
    return RANKING_URLS.get((weapon, gender, category))


def _page_matches_combo(text: str, weapon: str, gender: str, category: str) -> bool:
    soup = BeautifulSoup(text, "html.parser")
    page_text = _strip_accents(soup.get_text(" ", strip=True)).upper()
    expected = [
        f"ARMA: {WEAPON_LABELS[weapon]}",
        f"GENERO: {GENDER_LABELS[gender]}",
        "TIPO: INDIVIDUAL",
        f"CATEGORIA: {CATEGORY_LABELS[category]}",
    ]
    return all(label in page_text for label in expected)


def _looks_blocked_or_unusable(text: str) -> bool:
    plain = _strip_accents(BeautifulSoup(text, "html.parser").get_text(" ", strip=True)).lower()
    has_ranking_table = "puesto" in plain and ("puntos" in plain or "puntaje" in plain)
    if has_ranking_table:
        return False
    login_only = "password" in text.lower() or "iniciar sesion" in plain
    js_only = "enable javascript" in plain or "habilite javascript" in plain
    return login_only or js_only


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public Colombia ranking page; return None for missing/blocked failures."""
    url = build_rankings_url(weapon, gender, category)
    if not url:
        print(f"    No scrapeable rankings at {BASE_URL}/rankings for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request(
            "get",
            url,
            headers=HEADERS,
            timeout=20,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    text = response.text or ""
    if not text.strip() or _looks_blocked_or_unusable(text):
        print(f"    No scrapeable rankings at {url}")
        return None
    if not _page_matches_combo(text, weapon, gender, category):
        print(f"    Ranking page did not match requested combo at {url}")
        return None
    return text


def current_season() -> str:
    """Return current fencing season as YYYY-YYYY, using season_utils when available."""
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
    run_log = ScraperRunLogger("scrape_fed_col").start()
    season = current_season()
    print(f"Colombia federation rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos: list[str] = []
    failed_combos: list[str] = []

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            label = _combo_label((weapon, gender, category))
            print(f"  {label}...")
            html = fetch_rankings_page(weapon, gender, category)
            if not html:
                total_failed += 1
                failed_combos.append(label)
                if index < len(RANKING_COMBOS) - 1:
                    time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(html)
            if not parsed:
                print("    No rows parsed")
                total_failed += 1
                failed_combos.append(label)
                if index < len(RANKING_COMBOS) - 1:
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
            print(f"    Parsed {len(parsed)} rows; written {written}")
            total_written += written
            working_combos.append(label)
            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        if failed_combos:
            print("Failed combos:")
            for combo in failed_combos:
                print(f"  - {combo}")

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "working_combos": working_combos,
                "failed_combos": failed_combos,
                "source_url": f"{BASE_URL}/rankings",
                "data_format": "html",
            },
        )
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"working={len(working_combos)}/{len(RANKING_COMBOS)}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

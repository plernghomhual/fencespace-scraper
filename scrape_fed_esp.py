"""
scrape_fed_esp.py - Spanish Fencing Federation (RFEE) national rankings scraper.

Probe findings (2026-06-01):
  - The legacy rfeespada.es host did not resolve from the local probe.
  - The current RFEE site, https://esgrima.es/, links Ranking to Skermo:
    https://app.skermo.org/ranking-rfee/public/RFEE
  - Rankings are public server-rendered HTML tables fetched by GET.
  - Current URL pattern:
    /ranking-rfee/public/RFEE?setLang=es&season=16&weapon=F&category=7&gender=M

Skermo form values:
  weapon:   E=Espada, F=Florete, S=Sable
  category: 7=ABS/Senior, 6=M20/Junior
  gender:   M=Masculino, W=Femenino
  season:   16=2025-2026

Table columns:
  Posicion/Posición | Nombre | Apellidos | Fecha nacimiento | Club | Puntuación
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

try:
    from season_utils import normalize_season as _shared_normalize_season
except ImportError:  # Agent 5 may not be merged yet.
    _shared_normalize_season = None


SOURCE = "esp_fencing"
COUNTRY = "ESP"
BASE_URL = "https://app.skermo.org/ranking-rfee/public/RFEE"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://esgrima.es/",
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

_WEAPON_PARAMS = {"Foil": "F", "Epee": "E", "Sabre": "S"}
_GENDER_PARAMS = {"Men": "M", "Women": "W"}
_CATEGORY_PARAMS = {"Senior": "7", "Junior": "6"}

_KNOWN_SEASON_IDS = {
    "2017-2018": "2",
    "2018-2019": "3",
    "2019-2020": "10",
    "2020-2021": "11",
    "2021-2022": "12",
    "2022-2023": "13",
    "2023-2024": "14",
    "2024-2025": "15",
    "2025-2026": "16",
}

_RANK_HEADERS = {"posicion", "puesto", "rank", "#"}
_NAME_HEADERS = {"nombre", "tirador", "tiradora", "deportista", "name"}
_SURNAME_HEADERS = {"apellidos", "apellido"}
_CLUB_HEADERS = {"club", "sala", "entidad"}
_POINTS_HEADERS = {"puntuacion", "puntos", "puntaje", "points", "total"}
_SKIP_ROW_TERMS = {
    "DNS",
    "DQ",
    "DESCALIFICADO",
    "DESCALIFICADA",
    "NO PRESENTADO",
    "NO PRESENTADA",
    "SIN DATOS",
    "NO HAY DATOS",
    "TOTAL",
    "RESUMEN",
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalise_header(text: str) -> str:
    text = _strip_accents(text).lower().strip()
    return re.sub(r"[^\w#]+", " ", text).strip()


def _detect_columns(header_cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(header_cells):
        key = _normalise_header(raw)
        if key in _RANK_HEADERS and "rank_col" not in mapping:
            mapping["rank_col"] = idx
        elif key in _NAME_HEADERS and "name_col" not in mapping:
            mapping["name_col"] = idx
        elif key in _SURNAME_HEADERS and "surname_col" not in mapping:
            mapping["surname_col"] = idx
        elif key in _CLUB_HEADERS and "club_col" not in mapping:
            mapping["club_col"] = idx
        elif key in _POINTS_HEADERS and "points_col" not in mapping:
            mapping["points_col"] = idx
    return mapping


def _parse_rank(raw: str) -> int | None:
    match = re.match(r"^\s*(\d+)\s*\.?\s*$", raw)
    if not match:
        return None
    return int(match.group(1))


def _parse_points(raw: str) -> float | None:
    value = raw.strip().replace("\xa0", "").replace(" ", "")
    if not value:
        return None
    value = re.sub(r"[^0-9,.\-]", "", value)
    if not value or value in {"-", ".", ","}:
        return None

    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    elif re.match(r"^\d{1,3}(\.\d{3})+$", value):
        value = value.replace(".", "")

    try:
        return float(value)
    except ValueError:
        return None


def _clean_name_part(raw: str) -> str:
    return re.sub(r"^\s*\d+\s*\.\s*", "", raw).strip()


def _row_should_be_skipped(texts: list[str]) -> bool:
    row_text = " ".join(texts).upper()
    return any(term in row_text for term in _SKIP_ROW_TERMS)


def _text_cells(row) -> list[str]:
    return [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse RFEE/Skermo ranking HTML into rows with rank, name, club, and points.

    Supports Skermo's Spanish columns and a simpler federation table shape:
    Puesto | Nombre | Club | Puntos.
    """
    if not html_or_text:
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []

    for table in tables:
        results: list[dict] = []
        col_map: dict[str, int] = {}
        header_detected = False

        for row in table.find_all("tr"):
            texts = _text_cells(row)
            if not texts:
                continue

            if not header_detected:
                candidate = _detect_columns(texts)
                if "rank_col" in candidate and "name_col" in candidate:
                    col_map = candidate
                    header_detected = True
                    continue
                if _parse_rank(texts[0]) is not None:
                    header_detected = True

            if not header_detected or _row_should_be_skipped(texts):
                continue

            if col_map:
                required_max = max(col_map.values())
                if len(texts) <= required_max:
                    continue
                rank = _parse_rank(texts[col_map["rank_col"]])
                if rank is None:
                    continue

                name_parts = [_clean_name_part(texts[col_map["name_col"]])]
                if "surname_col" in col_map:
                    name_parts.append(texts[col_map["surname_col"]].strip())
                name = " ".join(part for part in name_parts if part).strip()
                club = texts[col_map["club_col"]].strip() if "club_col" in col_map else None
                points = _parse_points(texts[col_map["points_col"]]) if "points_col" in col_map else None
            else:
                if len(texts) < 2:
                    continue
                rank = _parse_rank(texts[0])
                if rank is None:
                    continue
                name = _clean_name_part(texts[1])
                club = texts[2].strip() if len(texts) > 2 else None
                points = _parse_points(texts[-1]) if len(texts) >= 4 else None

            if not name:
                continue
            results.append({
                "rank": rank,
                "name": name,
                "club": club or None,
                "points": points,
            })

        if results:
            return results

    return []


def current_season() -> str:
    now = datetime.now(timezone.utc)
    end_year = now.year if now.month < 7 else now.year + 1

    if _shared_normalize_season:
        return str(_shared_normalize_season(end_year))

    return f"{end_year - 1}-{end_year}"


def _season_to_skermo_id(season: str) -> str:
    if season in _KNOWN_SEASON_IDS:
        return _KNOWN_SEASON_IDS[season]

    match = re.match(r"^\d{4}-(\d{4})$", season)
    if match:
        end_year = int(match.group(1))
        if end_year >= 2020:
            return str(end_year - 2010)

    return _KNOWN_SEASON_IDS["2025-2026"]


def _build_params(weapon: str, gender: str, category: str) -> dict[str, str]:
    season = current_season()
    return {
        "setLang": "es",
        "season": _season_to_skermo_id(season),
        "weapon": _WEAPON_PARAMS[weapon],
        "category": _CATEGORY_PARAMS[category],
        "gender": _GENDER_PARAMS[gender],
    }


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one RFEE/Skermo ranking page, returning None on HTTP/network failure."""
    try:
        params = _build_params(weapon, gender, category)
    except KeyError as exc:
        print(f"    Unsupported combo value: {exc}")
        return None

    try:
        response = federation_request("get",
            BASE_URL,
            headers=HEADERS,
            params=params,
            timeout=20,
            allow_redirects=True,
        )
        if response.status_code == 200:
            return response.text
        print(f"    HTTP {response.status_code} for {response.url}")
        return None
    except requests.RequestException as exc:
        print(f"    Request error for {weapon} {gender} {category}: {exc}")
        return None


def main():
    run_log = ScraperRunLogger("scrape_fed_esp").start()
    try:
        season = current_season()
        print(f"RFEE Spain rankings - season {season}")
        total_written = total_failed = total_skipped = 0
        failed_combos: list[str] = []

        for weapon, gender, category in RANKING_COMBOS:
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")
            html = fetch_rankings_page(weapon, gender, category)
            if not html:
                total_failed += 1
                failed_combos.append(combo_label)
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(html)
            if not parsed:
                print("    No rows parsed")
                total_failed += 1
                failed_combos.append(combo_label)
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
            print(f"    Written {written} rows ({len(parsed)} parsed)")
            total_written += written
            time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={"failed_combos": failed_combos},
        )
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
        print(f"Done - written={total_written}, failed={total_failed}, skipped={total_skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

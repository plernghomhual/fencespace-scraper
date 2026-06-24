"""
scrape_fed_rus.py — Russian Fencing Federation national rankings scraper.

Probe findings (2026-06-01):
  - Requested paths `/rating`, `/rankings`, and `/sport/ranking` return 404.
  - Working URL: https://www.rusfencing.ru/rating.php
  - Request method: GET.
  - Response format: server-rendered HTML; two tables are returned when filtered.
    The `table.results_table` table contains ranking rows.
  - Public combos: all 12 Senior/Junior Foil/Epee/Sabre Men/Women combinations
    returned HTTP 200 with `table.results_table` rows when probed.
  - Filter params:
      WEAPON: рапира=474, шпага=475, сабля=476
      SEX: Мужчины=450, Женщины=451
      AGE: Взрослые=498, Юниоры=496

Live ranking columns:
  Место | фамилия и имя | Дата рождения | Субъект РФ | Организация | ... | очки
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "rus_fencing"
COUNTRY = "RUS"
BASE_URL = "https://www.rusfencing.ru/rating.php"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.7,en;q=0.6",
}

RANKING_COMBOS = [
    ("Foil",  "Men",   "Senior"),
    ("Foil",  "Women", "Senior"),
    ("Epee",  "Men",   "Senior"),
    ("Epee",  "Women", "Senior"),
    ("Sabre", "Men",   "Senior"),
    ("Sabre", "Women", "Senior"),
    ("Foil",  "Men",   "Junior"),
    ("Foil",  "Women", "Junior"),
    ("Epee",  "Men",   "Junior"),
    ("Epee",  "Women", "Junior"),
    ("Sabre", "Men",   "Junior"),
    ("Sabre", "Women", "Junior"),
]

_WEAPON_PARAMS = {"Foil": "474", "Epee": "475", "Sabre": "476"}
_GENDER_PARAMS = {"Men": "450", "Women": "451"}
_CATEGORY_PARAMS = {"Senior": "498", "Junior": "496"}

_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_RANK_HEADERS = {"место", "rank", "rang"}
_NAME_HEADERS = {
    "фио",
    "фамилия и имя",
    "фамилия имя",
    "спортсмен",
    "спортсменка",
    "athlete",
    "name",
}
_CLUB_HEADERS = {
    "клуб",
    "организация",
    "организациясубъектрф",
    "общество",
    "club",
}
_POINTS_HEADERS = {"очки", "баллы", "points", "pts", "пункты"}


def _normalise_header(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.replace("ё", "е").lower()).strip()


def _parse_rank(raw: str) -> int | None:
    text = raw.strip()
    match = re.fullmatch(r"(\d+)[.)]?", text)
    if not match:
        return None
    return int(match.group(1))


def _parse_points(raw: str) -> float | None:
    text = raw.replace("\xa0", " ").strip()
    if not text:
        return None

    match = re.search(r"-?\d[\d\s.,]*", text)
    if not match:
        return None

    value = match.group(0).replace(" ", "")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+", value):
        value = value.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", value):
        value = value.replace(".", "")
    elif "," in value:
        value = value.replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return None


def _split_name(raw: str) -> tuple[str, str | None]:
    text = " ".join(raw.split())
    if not text:
        return "", None

    paren_match = re.search(r"\(([^()]*)\)\s*$", text)
    if paren_match:
        alt = paren_match.group(1).strip()
        if _LATIN_RE.search(alt) and not _CYRILLIC_RE.search(alt):
            name = text[:paren_match.start()].strip()
            return name, alt

    parts = [part.strip() for part in re.split(r"\s*/\s*|\s+\|\s+", text) if part.strip()]
    if len(parts) > 1:
        native = next((part for part in parts if _CYRILLIC_RE.search(part)), parts[0])
        latin = next(
            (
                part for part in parts
                if _LATIN_RE.search(part) and not _CYRILLIC_RE.search(part)
            ),
            None,
        )
        return native, latin

    return text, None


def _detect_columns(header_cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(header_cells):
        key = _normalise_header(raw)
        compact = key.replace(" ", "")
        if key in _RANK_HEADERS and "rank_col" not in mapping:
            mapping["rank_col"] = idx
        elif (key in _NAME_HEADERS or compact in _NAME_HEADERS) and "name_col" not in mapping:
            mapping["name_col"] = idx
        elif (key in _CLUB_HEADERS or compact in _CLUB_HEADERS) and "club_col" not in mapping:
            mapping["club_col"] = idx
        elif key in _POINTS_HEADERS and "points_col" not in mapping:
            mapping["points_col"] = idx
    return mapping


def _parse_table(table) -> list[dict]:
    rows = table.find_all("tr")
    col_map: dict[str, int] | None = None
    parsed: list[dict] = []

    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        texts = [" ".join(cell.get_text(" ", strip=True).split()) for cell in cells]

        if col_map is None:
            candidate = _detect_columns(texts)
            if {"rank_col", "name_col"}.issubset(candidate):
                if "points_col" not in candidate:
                    candidate["points_col"] = len(texts) - 1
                col_map = candidate
                continue
            if _parse_rank(texts[0]) is not None and len(texts) >= 2:
                col_map = {"rank_col": 0, "name_col": 1, "points_col": len(texts) - 1}
                if len(texts) >= 5:
                    col_map["club_col"] = 4
                elif len(texts) >= 3:
                    col_map["club_col"] = 2

        if col_map is None:
            continue

        max_col = max(col_map.values())
        if len(texts) <= max_col:
            continue

        rank = _parse_rank(texts[col_map["rank_col"]])
        if rank is None:
            continue

        name, latin_name = _split_name(texts[col_map["name_col"]])
        if not name:
            continue

        club = texts[col_map["club_col"]].strip() if "club_col" in col_map else None
        points = _parse_points(texts[col_map["points_col"]]) if "points_col" in col_map else None

        row_data = {
            "rank": rank,
            "name": name,
            "club": club or None,
            "points": points,
        }
        if latin_name:
            row_data["latin_name"] = latin_name
        parsed.append(row_data)

    return parsed


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Russian federation ranking HTML into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    tables = soup.select("table.results_table")
    if not tables:
        tables = soup.find_all("table")
    if not tables:
        return []

    for table in tables:
        rows = _parse_table(table)
        if rows:
            return rows
    return []


def current_season() -> str:
    """Return the current FIE-style season as YYYY-YYYY."""
    now = datetime.now(UTC)
    start_year = now.year - 1 if now.month < 7 else now.year
    fallback = f"{start_year}-{start_year + 1}"

    try:
        import season_utils  # type: ignore
    except ImportError:
        return fallback

    normalise = getattr(season_utils, "normalize_season", None)
    if callable(normalise):
        return normalise(fallback)

    current_fie_season = getattr(season_utils, "current_fie_season", None)
    season_to_string = getattr(season_utils, "season_to_string", None)
    if callable(current_fie_season) and callable(season_to_string):
        return season_to_string(current_fie_season())

    return fallback


def _ranking_params(weapon: str, gender: str, category: str) -> dict[str, str]:
    return {
        "WEAPON": _WEAPON_PARAMS[weapon],
        "SEX": _GENDER_PARAMS[gender],
        "AGE": _CATEGORY_PARAMS[category],
        "SEASON_CUSTOM": current_season(),
    }


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one rusfencing.ru ranking page; return None on HTTP or network failure."""
    try:
        response = federation_request("get",
            BASE_URL,
            params=_ranking_params(weapon, gender, category),
            headers=HEADERS,
            timeout=25,
            allow_redirects=True,
        )
    except (KeyError, requests.RequestException) as exc:
        print(f"    Request error for {weapon} {gender} {category}: {exc}")
        return None

    if response.status_code != 200:
        response_url = getattr(response, "url", BASE_URL)
        print(f"    HTTP {response.status_code} for {response_url}")
        return None

    return response.text


def main():
    run_log = ScraperRunLogger("scrape_fed_rus").start()
    season = current_season()
    total_written = total_failed = total_skipped = 0
    failed_combos: list[str] = []

    print(f"Russian Fencing Federation rankings — season {season}")
    print(f"Source URL: {BASE_URL} (GET HTML)")

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")

            html = fetch_rankings_page(weapon, gender, category)
            if not html:
                total_failed += 1
                failed_combos.append(combo_label)
            else:
                parsed = parse_rankings_table(html)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append(combo_label)
                else:
                    rows = []
                    for row in parsed:
                        metadata = {"source_url": BASE_URL}
                        if row.get("latin_name"):
                            metadata["latin_name"] = row["latin_name"]
                        rows.append(
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
                                metadata=metadata,
                            )
                        )

                    written = write_rankings(rows, source=SOURCE, season=season)
                    total_written += written
                    print(f"    Parsed {len(parsed)} rows; written {written}")

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "failed_combos": failed_combos,
                "source_url": BASE_URL,
                "public_combos": len(RANKING_COMBOS) - total_failed,
                "response_format": "html",
            },
        )
        print(
            "Done — "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}"
        )
        if failed_combos:
            print("Failed combos: " + "; ".join(failed_combos))
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

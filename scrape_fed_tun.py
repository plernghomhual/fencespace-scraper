"""
scrape_fed_tun.py - Tunisia federation-published rankings scraper.

Probe evidence, 2026-06-02:
  - fte-tunisie.com, http://fte-tunisie.com, and www.fte-tunisie.com did not resolve.
  - Current public federation site is https://escrimetunisie.org/.
  - Public rankings data is exposed as FIE-ranked Tunisian athletes:
      GET https://escrimetunisie.org/api/fie-athletes?weapon=<weapon>&gender=<M|F>&category=<category>
  - Response format is JSON. Login-only endpoints such as /api/athletes return 401.
  - Public Senior/Junior coverage has rows for 10/12 standard combos.
    Senior Women Foil and Junior Women Epee currently return 200 [].
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import UTC, datetime, timezone
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup, Tag

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "tun_fencing"
COUNTRY = "Tunisia"
BASE_URL = "https://escrimetunisie.org/api/fie-athletes"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,ar;q=0.8,en;q=0.7",
    "Referer": "https://escrimetunisie.org/",
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

WEAPON_PARAMS = {"Foil": "foil", "Epee": "epee", "Sabre": "sabre"}
GENDER_PARAMS = {"Men": "M", "Women": "F"}
CATEGORY_PARAMS = {"Senior": "senior", "Junior": "junior"}

RANK_HEADERS = {"rank", "rang", "classement", "position", "pos", "n", "no", "المركز", "الترتيب", "تصنيف"}
NAME_HEADERS = {"name", "nom", "nomprenom", "tireur", "tireuse", "athlete", "fencer", "الاسم", "اللاعب", "اللاعبة"}
CLUB_HEADERS = {"club", "clubs", "association", "salle", "النادي", "الجمعية"}
POINTS_HEADERS = {"points", "point", "pts", "total", "النقاط"}
SKIP_VALUES = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "ret",
    "total",
    "totaux",
    "resume",
    "résumé",
    "summary",
    "مجموع",
    "المجموع",
}


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY, using season_utils when present."""
    now = datetime.now(UTC)
    season_end_year = now.year if now.month < 7 else now.year + 1

    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "season_to_string"):
            return season_utils.season_to_string(season_end_year)
        if hasattr(season_utils, "normalize_season"):
            return season_utils.normalize_season(season_end_year)
    except ImportError:
        pass

    return f"{season_end_year - 1:04d}-{season_end_year:04d}"


def build_rankings_url(weapon: str, gender: str, category: str) -> str:
    params = [
        ("weapon", WEAPON_PARAMS[weapon]),
        ("gender", GENDER_PARAMS[gender]),
        ("category", CATEGORY_PARAMS[category]),
    ]
    return f"{BASE_URL}?{urlencode(params)}"


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _header_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(value).lower())
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[\W_]+", "", without_marks, flags=re.UNICODE)


def _is_skip_value(value: str) -> bool:
    key = _header_key(value)
    return key in {_header_key(item) for item in SKIP_VALUES}


def _parse_rank(value) -> int | None:
    text = _clean_text(str(value or ""))
    if not text or _is_skip_value(text):
        return None
    match = re.match(r"^\s*#?\s*(\d+)", text)
    if not match:
        return None
    rank = int(match.group(1))
    return rank if rank > 0 else None


def _parse_points(value) -> float | None:
    text = _clean_text(str(value or ""))
    if not text or _is_skip_value(text):
        return None
    text = re.sub(r"[^0-9,.\-]", "", text)
    if text in {"", "-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        if text.count(",") > 1:
            head, tail = text.rsplit(",", 1)
            text = f"{head.replace(',', '')}.{tail}"
        else:
            text = text.replace(",", ".")
    elif text.count(".") > 1:
        head, tail = text.rsplit(".", 1)
        text = f"{head.replace('.', '')}.{tail}"

    try:
        return float(text)
    except ValueError:
        return None


def _parse_json_rows(text: str) -> list[dict] | None:
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return None

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None

    if isinstance(payload, dict):
        for key in ("data", "athletes", "rows", "rankings"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            payload = [payload]

    if not isinstance(payload, list):
        return []

    rows: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        rank = _parse_rank(item.get("rank") or item.get("ranking") or item.get("classement"))
        name = _clean_text(str(item.get("name") or ""))
        if not name:
            first_name = _clean_text(str(item.get("firstName") or ""))
            last_name = _clean_text(str(item.get("lastName") or ""))
            name = _clean_text(f"{last_name} {first_name}")
        if rank is None or not name:
            continue

        club = item.get("club") or item.get("clubName") or item.get("team")
        club_text = _clean_text(str(club)) if club else None
        rows.append(
            {
                "rank": rank,
                "name": name,
                "club": club_text or None,
                "points": _parse_points(item.get("points") or item.get("totalPoints")),
            }
        )
    return rows


def _row_cells(row: Tag) -> list[Tag]:
    return row.find_all(["td", "th"], recursive=False)


def _find_header_mapping(labels: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, label in enumerate(labels):
        key = _header_key(label)
        if key in RANK_HEADERS:
            mapping["rank"] = index
        elif key in NAME_HEADERS:
            mapping["name"] = index
        elif key in CLUB_HEADERS:
            mapping["club"] = index
        elif key in POINTS_HEADERS:
            mapping["points"] = index

    return mapping if {"rank", "name", "points"}.issubset(mapping) else None


def _parse_html_tables(text: str) -> list[dict]:
    soup = BeautifulSoup(text, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        rows = [row for row in table.find_all("tr") if row.find_parent("table") is table]
        for header_index, header_row in enumerate(rows):
            labels = [_clean_text(cell.get_text(" ", strip=True)) for cell in _row_cells(header_row)]
            mapping = _find_header_mapping(labels)
            if not mapping:
                continue

            min_cells = max(mapping.values()) + 1
            for row in rows[header_index + 1:]:
                cells = _row_cells(row)
                if len(cells) < min_cells:
                    continue

                rank = _parse_rank(cells[mapping["rank"]].get_text(" ", strip=True))
                if rank is None:
                    continue

                name = _clean_text(cells[mapping["name"]].get_text(" ", strip=True))
                if not name or _is_skip_value(name):
                    continue

                club = None
                if "club" in mapping:
                    club = _clean_text(cells[mapping["club"]].get_text(" ", strip=True)) or None

                results.append(
                    {
                        "rank": rank,
                        "name": name,
                        "club": club,
                        "points": _parse_points(cells[mapping["points"]].get_text(" ", strip=True)),
                    }
                )
            break

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Return rank/name/club/points rows from Tunisia JSON or ranking-table HTML."""
    if not html_or_text or not html_or_text.strip():
        return []

    json_rows = _parse_json_rows(html_or_text)
    if json_rows is not None:
        return json_rows

    return _parse_html_tables(html_or_text)


def _looks_like_spa_shell(text: str) -> bool:
    lower = text.lower()
    return (
        "<!doctype html" in lower
        and 'id="root"' in lower
        and "/assets/" in lower
        and "<table" not in lower
    )


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public Tunisia combo; return None for blocked, login-only, or failed pages."""
    url = build_rankings_url(weapon, gender, category)
    try:
        response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code in {401, 403, 404} or response.status_code == 429:
        print(f"    HTTP {response.status_code} for {url}")
        return None
    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None
    if _looks_like_spa_shell(response.text):
        print(f"    No scrapeable API response at {url}")
        return None
    return response.text


def main():
    run_log = ScraperRunLogger("scrape_fed_tun").start()
    season = current_season()
    print(f"Tunisia federation rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[dict] = []
    skipped_combos: list[dict] = []
    get_state(SOURCE, "last_run")

    try:
        for weapon, gender, category in RANKING_COMBOS:
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")
            content = fetch_rankings_page(weapon, gender, category)
            if content is None:
                total_failed += 1
                failed_combos.append({"weapon": weapon, "gender": gender, "category": category})
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(content)
            if not parsed:
                print(f"    No public rows parsed for {combo_label}")
                total_skipped += 1
                skipped_combos.append({"weapon": weapon, "gender": gender, "category": category})
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
                    metadata={"source_url": build_rankings_url(weapon, gender, category)},
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Parsed {len(rows)} rows; written {written}")
            total_written += written
            time.sleep(REQUEST_DELAY)

        set_state(
            SOURCE,
            "last_run",
            {
                "season": season,
                "base_url": BASE_URL,
                "attempted_combos": len(RANKING_COMBOS),
                "failed_combos": failed_combos,
                "skipped_combos": skipped_combos,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        run_log.complete(written=total_written, failed=total_failed, skipped=total_skipped)
        print(f"Done - written={total_written}, failed={total_failed}, skipped={total_skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

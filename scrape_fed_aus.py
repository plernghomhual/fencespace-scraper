"""
scrape_fed_aus.py — Australian Fencing Federation national rankings scraper.

Probe findings (2026-06-01):
  - https://www.ausfencing.org/rankings/ is a category landing page.
  - https://www.ausfencing.org/results/ contains historical results, not current rankings.
  - https://www.ausfencing.org/national-rankings/ returns 404.
  - https://www.ausfencing.org/events/results/ redirects to /results/.
  - Current public ranking tables are server-rendered HTML:
      Senior: https://www.ausfencing.org/open-rankings/
      Junior: https://www.ausfencing.org/junior-rankings/
  - All 12 Senior/Junior Foil/Epee/Sabre Men/Women combos are public.

AFF table columns:
  Rank | Fencer | Pts | AFC1 2025/26 | ...

AFF embeds state in the fencer label, e.g. "CROOK, Jacob (QLD)".
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "aus_fencing"
COUNTRY = "AUS"
BASE_URL = "https://www.ausfencing.org"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
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

_CATEGORY_PATHS = {
    "Senior": "/open-rankings/",
    "Junior": "/junior-rankings/",
}

_RANK_HEADERS = {"rank", "ranking", "place", "#"}
_NAME_HEADERS = {"fencer", "name", "athlete", "competitor"}
_STATE_HEADERS = {"state", "state/territory", "state territory"}
_CLUB_HEADERS = {"club", "state", "club / country", "club/country"}
_POINTS_HEADERS = {"pts", "points", "total points", "score"}
_NON_RANK_VALUES = {"", "*", "dns", "dq", "dnf", "total", "summary", "rank"}
_STATE_SUFFIX_RE = re.compile(r"\s*\(([A-Z][A-Z0-9]{1,8})\)\s*$")


def _normalise_header(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s/#]", " ", text.lower())).strip()


def _parse_points(raw: str) -> float | None:
    value = raw.strip().replace("\xa0", " ").replace(" ", "")
    if not value or value == "-":
        return None
    if re.match(r"^\d{1,3}(,\d{3})+(\.\d+)?$", value):
        value = value.replace(",", "")
    elif "," in value and "." not in value:
        value = value.replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def _split_name_state(raw_name: str) -> tuple[str, str | None]:
    name = re.sub(r"\s+", " ", raw_name).strip()
    match = _STATE_SUFFIX_RE.search(name)
    if not match:
        return name, None
    return _STATE_SUFFIX_RE.sub("", name).strip(), match.group(1)


def _detect_columns(texts: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(texts):
        key = _normalise_header(raw)
        if key in _RANK_HEADERS and "rank" not in mapping:
            mapping["rank"] = idx
        elif key in _NAME_HEADERS and "name" not in mapping:
            mapping["name"] = idx
        elif key in _STATE_HEADERS and "state" not in mapping:
            mapping["state"] = idx
        elif key in _CLUB_HEADERS and "club" not in mapping and key != "state":
            mapping["club"] = idx
        elif key in _POINTS_HEADERS and "points" not in mapping:
            mapping["points"] = idx
    return mapping


def _is_ranking_table(table) -> bool:
    first_row = table.find("tr")
    if not first_row:
        return False
    texts = [cell.get_text(" ", strip=True) for cell in first_row.find_all(["th", "td"])]
    mapping = _detect_columns(texts)
    return "rank" in mapping and "name" in mapping and "points" in mapping


def _row_texts(row) -> list[str]:
    return [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse AFF ranking table HTML into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    tables = [table for table in soup.find_all("table") if _is_ranking_table(table)]
    if not tables:
        return []

    results: list[dict] = []
    for table in tables:
        col_map: dict[str, int] = {}
        for row in table.find_all("tr"):
            texts = _row_texts(row)
            if not texts:
                continue

            if not col_map:
                candidate = _detect_columns(texts)
                if "rank" in candidate and "name" in candidate:
                    col_map = candidate
                    continue
                col_map = {"rank": 0, "name": 1, "points": 2}

            if len(texts) <= max(col_map.values()):
                continue

            rank_text = texts[col_map["rank"]].strip()
            if rank_text.lower() in _NON_RANK_VALUES or not rank_text.isdigit():
                continue

            name_text = texts[col_map["name"]].strip()
            if not name_text:
                continue

            try:
                rank = int(rank_text)
            except ValueError:
                continue

            name, state_from_name = _split_name_state(name_text)
            club = texts[col_map["club"]].strip() if "club" in col_map else None
            state = texts[col_map["state"]].strip() if "state" in col_map else state_from_name
            points = _parse_points(texts[col_map["points"]]) if "points" in col_map else None

            metadata = {}
            if state:
                metadata["state"] = state

            results.append(
                {
                    "rank": rank,
                    "name": name,
                    "club": club or None,
                    "points": points,
                    "metadata": metadata,
                }
            )

    return results


def _combo_label(weapon: str, gender: str) -> str:
    return f"{gender}'s {weapon}"


def _label_matches(text: str, weapon: str, gender: str) -> bool:
    wanted = _combo_label(weapon, gender).lower()
    cleaned = re.sub(r"\s+", " ", text).strip().lower()
    return cleaned == wanted or cleaned == f"{wanted} expand"


def extract_combo_table_html(page_html: str, weapon: str, gender: str) -> str | None:
    """Return the ranking table HTML for one AFF accordion section."""
    soup = BeautifulSoup(page_html, "html.parser")
    ranking_tables = [table for table in soup.find_all("table") if _is_ranking_table(table)]
    for table in ranking_tables:
        parent = table.parent
        previous_texts: list[str] = []
        if parent:
            for text_node in parent.find_all_previous(string=True, limit=40):
                text = re.sub(r"\s+", " ", str(text_node)).strip()
                if text:
                    previous_texts.append(text)

        if any(_label_matches(text, weapon, gender) for text in previous_texts[:12]):
            return str(table)

    # AFF pages order their six ranking tables consistently; keep this as a
    # fallback if accordion labels change but table order remains stable.
    order = {
        ("Epee", "Men"): 0,
        ("Epee", "Women"): 1,
        ("Foil", "Men"): 2,
        ("Foil", "Women"): 3,
        ("Sabre", "Men"): 4,
        ("Sabre", "Women"): 5,
    }
    idx = order.get((weapon, gender))
    if idx is not None and idx < len(ranking_tables):
        return str(ranking_tables[idx])
    return None


def _category_url(category: str) -> str | None:
    path = _CATEGORY_PATHS.get(category)
    if not path:
        return None
    return f"{BASE_URL}{path}"


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one AFF ranking table for a weapon/gender/category combo."""
    url = _category_url(category)
    if not url:
        print(f"    Unsupported category {category!r}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    table_html = extract_combo_table_html(response.text, weapon, gender)
    if not table_html:
        print(f"    No public table found for {category} {gender} {weapon} at {url}")
        return None
    return table_html


def current_season() -> str:
    now = datetime.now(UTC)
    raw_season = f"{now.year - 1}-{now.year}" if now.month < 7 else f"{now.year}-{now.year + 1}"
    try:
        from season_utils import normalize_season

        return normalize_season(raw_season)
    except Exception:
        return raw_season


def main():
    run_log = ScraperRunLogger("scrape_fed_aus").start()
    season = current_season()
    print(f"Australian Fencing rankings — season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []
    combo_results: dict[str, dict] = {}

    try:
        set_state(
            SOURCE,
            "probe",
            {
                "working_urls": {
                    "Senior": f"{BASE_URL}/open-rankings/",
                    "Junior": f"{BASE_URL}/junior-rankings/",
                },
                "method": "GET",
                "format": "html",
                "public_combos": len(RANKING_COMBOS),
            },
        )

        for weapon, gender, category in RANKING_COMBOS:
            combo_key = f"{category} {gender} {weapon}"
            print(f"  {combo_key}...")
            html = fetch_rankings_page(weapon, gender, category)
            if not html:
                total_failed += 1
                failed_combos.append(combo_key)
                combo_results[combo_key] = {"status": "fetch_failed"}
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(html)
            if not parsed:
                print("    No rows parsed")
                total_failed += 1
                failed_combos.append(combo_key)
                combo_results[combo_key] = {"status": "empty"}
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
                    metadata=row.get("metadata") or {},
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Parsed {len(parsed)} rows; written {written}")
            total_written += written
            combo_results[combo_key] = {"status": "ok", "parsed": len(parsed), "written": written}
            time.sleep(REQUEST_DELAY)

        set_state(
            SOURCE,
            "last_run",
            {
                "season": season,
                "written": total_written,
                "failed": total_failed,
                "skipped": total_skipped,
                "failed_combos": failed_combos,
                "combo_results": combo_results,
            },
        )
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={"season": season, "failed_combos": failed_combos},
        )
        print(
            f"Done — written={total_written}, failed={total_failed}, "
            f"skipped={total_skipped}, failed_combos={failed_combos}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

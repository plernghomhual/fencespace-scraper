"""
scrape_fed_nzl.py - New Zealand national federation rankings scraper.

Probe evidence, 2026-06-01:
  - https://www.fencing.org.nz/rankings -> 404
  - https://www.fencing.org.nz/results -> 404
  - https://www.fencing.org.nz/competitions/rankings -> 404
  - https://results.fencing.org.nz/ -> JS portal, no server-rendered tables
  - GET https://api.fencing.org.nz/public/ranking?weapon=<weapon>&cat=<cat>
    returns JSON as text/html with keys: cat, weapon, ranking_at, last_update,
    Mens, Womens.

Public combo coverage:
  - Senior: cat=open for foil/epee/sabre, Mens and Womens
  - Junior: cat=u20 for foil/epee/sabre, Mens and Womens
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime, timezone
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "nzl_fencing"
COUNTRY = "NZL"
BASE_URL = "https://api.fencing.org.nz/public"
RANKING_ENDPOINT = f"{BASE_URL}/ranking"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-NZ,en;q=0.9",
    "Referer": "https://results.fencing.org.nz/",
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
CATEGORY_PARAMS = {"Senior": "open", "Junior": "u20"}
GENDER_KEYS = {"Men": "Mens", "Women": "Womens"}

_RANK_HEADERS = {"rank", "ranking", "place", "#", "position"}
_NAME_HEADERS = {"name", "fencer", "athlete", "competitor"}
_CLUB_HEADERS = {"club", "team", "school"}
_REGION_HEADERS = {"region", "province", "association"}
_POINTS_HEADERS = {"points", "point", "pts", "totalpoints", "total"}
_SKIP_MARKERS = {"dns", "dq", "dnf", "wd", "withdrawn", "scratch", "total", "totals", "summary"}


def ranking_params(weapon: str, category: str) -> dict[str, str] | None:
    weapon_param = WEAPON_PARAMS.get(weapon)
    category_param = CATEGORY_PARAMS.get(category)
    if not weapon_param or not category_param:
        return None
    return {"weapon": weapon_param, "cat": category_param}


def ranking_url(weapon: str, category: str) -> str | None:
    params = ranking_params(weapon, category)
    if not params:
        return None
    return f"{RANKING_ENDPOINT}?{urlencode(params)}"


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _compact_header(value: str) -> str:
    return re.sub(r"[^a-z0-9#]+", "", value.lower())


def _parse_rank(value) -> int | None:
    text = _clean(value)
    if not text or text.lower() in _SKIP_MARKERS:
        return None
    match = re.match(r"^\s*(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def _parse_points(value) -> float | None:
    text = _clean(value)
    if not text or text.lower() in _SKIP_MARKERS:
        return None
    text = text.replace("\xa0", "").replace(" ", "")
    if "," in text and "." not in text:
        comma_parts = text.split(",")
        if len(comma_parts[-1]) in (1, 2):
            text = "".join(comma_parts[:-1]) + "." + comma_parts[-1]
        else:
            text = "".join(comma_parts)
    else:
        text = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _is_skip_row(rank_text: str, name: str) -> bool:
    rank_key = _clean(rank_text).lower()
    name_key = _clean(name).lower()
    if rank_key in _SKIP_MARKERS or name_key in _SKIP_MARKERS:
        return True
    return any(marker in name_key for marker in ("no rankings", "no data", "last updated"))


def _header_map(cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, header in enumerate(cells):
        key = _compact_header(header)
        if key in _RANK_HEADERS:
            mapping["rank"] = index
        elif key in _NAME_HEADERS:
            mapping["name"] = index
        elif key in _CLUB_HEADERS:
            mapping["club"] = index
        elif key in _REGION_HEADERS:
            mapping["region"] = index
        elif key in _POINTS_HEADERS:
            mapping["points"] = index
    return mapping


def _value(cells: list[str], index: int | None) -> str:
    if index is None or index >= len(cells):
        return ""
    return cells[index]


def _row_from_values(
    *,
    rank_text,
    name,
    club=None,
    region=None,
    points=None,
    uid=None,
    category_code=None,
    ranking_at=None,
    last_update=None,
) -> dict | None:
    if _is_skip_row(str(rank_text), str(name)):
        return None

    rank = _parse_rank(rank_text)
    clean_name = _clean(name)
    if rank is None or not clean_name:
        return None

    row = {
        "rank": rank,
        "name": clean_name,
        "club": _clean(club) or None,
        "points": _parse_points(points),
    }
    clean_region = _clean(region)
    if clean_region:
        row["region"] = clean_region
    clean_uid = _clean(uid)
    if clean_uid:
        row["uid"] = clean_uid
    clean_category = _clean(category_code)
    if clean_category:
        row["category_code"] = clean_category
    clean_ranking_at = _clean(ranking_at)
    if clean_ranking_at:
        row["ranking_at"] = clean_ranking_at
    clean_last_update = _clean(last_update)
    if clean_last_update:
        row["last_update"] = clean_last_update
    return row


def _parse_json_rankings(text: str) -> list[dict]:
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return []

    rows: list[dict] = []
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        source_rows = payload.get("rows") or []
        for raw in source_rows:
            if not isinstance(raw, dict):
                continue
            parsed = _row_from_values(
                rank_text=raw.get("rank"),
                name=raw.get("name"),
                club=raw.get("club"),
                region=raw.get("region"),
                points=raw.get("points"),
                uid=raw.get("uid"),
                category_code=raw.get("cat"),
                ranking_at=raw.get("ranking_at") or payload.get("ranking_at"),
                last_update=raw.get("last_update") or payload.get("last_update"),
            )
            if parsed:
                rows.append(parsed)
        return rows

    if isinstance(payload, dict):
        for gender_key in ("Mens", "Womens"):
            for raw in payload.get(gender_key) or []:
                if not isinstance(raw, dict):
                    continue
                parsed = _row_from_values(
                    rank_text=raw.get("rank"),
                    name=raw.get("name"),
                    club=raw.get("club"),
                    region=raw.get("region"),
                    points=raw.get("points"),
                    uid=raw.get("uid"),
                    category_code=raw.get("cat"),
                    ranking_at=raw.get("ranking_at") or payload.get("ranking_at"),
                    last_update=raw.get("last_update") or payload.get("last_update"),
                )
                if parsed:
                    rows.append(parsed)
    elif isinstance(payload, list):
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            parsed = _row_from_values(
                rank_text=raw.get("rank"),
                name=raw.get("name"),
                club=raw.get("club"),
                region=raw.get("region"),
                points=raw.get("points"),
                uid=raw.get("uid"),
                category_code=raw.get("cat"),
                ranking_at=raw.get("ranking_at"),
                last_update=raw.get("last_update"),
            )
            if parsed:
                rows.append(parsed)
    return rows


def _parse_html_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        mapping: dict[str, int] = {}
        for tr in rows:
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
            if not cells:
                continue
            has_header_cells = bool(tr.find_all("th"))
            if has_header_cells:
                mapping = _header_map(cells)
                continue

            if not mapping:
                inferred_points = 4 if len(cells) > 4 else len(cells) - 1
                mapping = {"rank": 0, "name": 1, "club": 2, "points": inferred_points}

            rank_index = mapping.get("rank")
            name_index = mapping.get("name")
            points_index = mapping.get("points")
            if rank_index is None or name_index is None or points_index is None:
                continue

            parsed = _row_from_values(
                rank_text=_value(cells, rank_index),
                name=_value(cells, name_index),
                club=_value(cells, mapping.get("club")),
                region=_value(cells, mapping.get("region")),
                points=_value(cells, points_index),
            )
            if parsed:
                results.append(parsed)

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse FeNZ ranking content.

    Accepts the current public API JSON returned by fetch_rankings_page and
    HTML table fallback content with English Rank/Name/Club/Region/Points
    headers. DNS/DQ/summary rows are skipped.
    """
    if not html_or_text or not html_or_text.strip():
        return []

    json_rows = _parse_json_rankings(html_or_text)
    if json_rows:
        return json_rows

    return _parse_html_table(html_or_text)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch ranking content for one weapon/gender/category combo."""
    params = ranking_params(weapon, category)
    gender_key = GENDER_KEYS.get(gender)
    if not params or not gender_key:
        print(f"    Unsupported combo: {weapon} {gender} {category}")
        return None

    try:
        response = federation_request("get",
            RANKING_ENDPOINT,
            headers=HEADERS,
            params=params,
            timeout=20,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        print(f"    Request error for {ranking_url(weapon, category)}: {exc}")
        return None

    if response.status_code == 404:
        print(f"    HTTP 404 for {ranking_url(weapon, category)}")
        return None
    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {ranking_url(weapon, category)}")
        return None

    try:
        payload = response.json()
    except ValueError:
        try:
            payload = json.loads(response.text)
        except ValueError:
            return response.text

    if not isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False)

    selected = {
        "cat": params["cat"],
        "weapon": params["weapon"],
        "ranking_at": payload.get("ranking_at"),
        "last_update": payload.get("last_update"),
        "gender": gender,
        "gender_key": gender_key,
        "source_url": ranking_url(weapon, category),
        "rows": payload.get(gender_key) or [],
    }
    return json.dumps(selected, ensure_ascii=False)


def current_season() -> str:
    try:
        import season_utils

        if hasattr(season_utils, "current_season"):
            value = season_utils.current_season()
            if hasattr(season_utils, "normalize_season"):
                return season_utils.normalize_season(value)
            return str(value)
        elif hasattr(season_utils, "current_fie_season"):
            value = season_utils.current_fie_season()
            if isinstance(value, int):
                start_year = value
                season_range = f"{start_year}-{start_year + 1}"
                if hasattr(season_utils, "normalize_season"):
                    return season_utils.normalize_season(season_range)
                return season_range
        else:
            value = None

        if value is not None:
            if hasattr(season_utils, "normalize_season"):
                return season_utils.normalize_season(value)
            if hasattr(season_utils, "season_to_string"):
                return season_utils.season_to_string(value)
            if isinstance(value, int):
                return f"{value - 1}-{value}"
            return str(value)
    except Exception:
        pass

    now = datetime.now(UTC)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def _metadata_for_row(row: dict, source_url: str | None) -> dict:
    metadata = {}
    for key in ("region", "uid", "category_code", "ranking_at", "last_update"):
        if row.get(key):
            metadata[key] = row[key]
    if source_url:
        metadata["source_url"] = source_url
    return metadata


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_nzl").start()
    season = current_season()
    print(f"FeNZ New Zealand rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []
    skipped_combos: list[str] = []
    available_combos: list[str] = []
    previous_state = get_state(SOURCE, "last_rankings") or {}

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_label = f"{weapon} {gender} {category}"
            source_url = ranking_url(weapon, category)
            print(f"  {combo_label}...")

            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                total_failed += 1
                failed_combos.append(combo_label)
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    print("    No rows parsed")
                    total_skipped += 1
                    skipped_combos.append(combo_label)
                else:
                    available_combos.append(combo_label)
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
                            metadata=_metadata_for_row(row, source_url),
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    print(f"    Parsed {len(rows)} rows; written {written} rows")
                    total_written += written

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        state_value = {
            "season": season,
            "checked_at": datetime.now(UTC).isoformat(),
            "available_combos": available_combos,
            "failed_combos": failed_combos,
            "skipped_combos": skipped_combos,
            "previous_available_combos": previous_state.get("available_combos", []),
        }
        set_state(SOURCE, "last_rankings", state_value)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=state_value,
        )
        print(
            f"Done - written={total_written}, failed={total_failed}, "
            f"skipped={total_skipped}"
        )
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
        if skipped_combos:
            print(f"Skipped combos: {', '.join(skipped_combos)}")
    except Exception as exc:
        run_log.error(str(exc))
        print(f"FAILED - {exc}")


if __name__ == "__main__":
    main()

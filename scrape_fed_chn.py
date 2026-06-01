"""
scrape_fed_chn.py — China Fencing Association national rankings scraper.

Probe summary:
  - Legacy domains `fencing.org.cn` and `cnfencing.org.cn` did not resolve.
  - `fencing.sport.org.cn` reset HTTP/HTTPS connections.
  - `https://www.sport.gov.cn/zjzx/` is public HTML but did not expose ranking data.
  - Current public source is the China fencing information platform:
      https://fencing.yy-sport.com.cn/

Ranking API:
  GET https://fencing.yy-sport.com.cn/fencingapi/rankinfo/total/week
  Response: JSON with data.records[] rows containing:
    totalRank, athleteName, organName, totalPoints

Public combos confirmed by probe:
  Senior `PS` and Junior `PJ` for Foil/Epee/Sabre × Men/Women.
"""

from __future__ import annotations

import json
import re
import time
import warnings
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "chn_fencing"
COUNTRY = "CHN"
BASE_URL = "https://fencing.yy-sport.com.cn"
REQUEST_DELAY = 1.5
REQUEST_TIMEOUT = 20
API_PAGE_SIZE = 20
PAGE_REQUEST_DELAY = 0.1
VERIFY_SSL = False
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
}

SEASON_ENDPOINT = f"{BASE_URL}/fencingapi/competition/season/condition"
WEEK_ENDPOINT = f"{BASE_URL}/fencingapi/rankinfo/total/getWeek"
RANKINGS_ENDPOINT = f"{BASE_URL}/fencingapi/rankinfo/total/week"

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

_WEAPON_CODES = {"Foil": "F", "Epee": "E", "Sabre": "S"}
_GENDER_CODES = {"Men": "M", "Women": "F"}
_CATEGORY_CODES = {"Senior": "PS", "Junior": "PJ"}
_SUMMARY_MARKERS = {
    "dns",
    "dq",
    "dsq",
    "wd",
    "ret",
    "弃权",
    "退赛",
    "取消",
    "合计",
    "总计",
    "小计",
}

warnings.filterwarnings("ignore", message="Unverified HTTPS request")


def _current_utc() -> datetime:
    return datetime.now(timezone.utc)


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY."""
    try:
        import season_utils  # type: ignore

        normalize = getattr(season_utils, "normalize_season", None)
        if normalize:
            current_fie = getattr(season_utils, "current_fie_season", None)
            if current_fie:
                return str(normalize(current_fie()))
            return str(normalize(_current_utc().year))
    except Exception:
        pass

    now = _current_utc()
    year = now.year
    return f"{year-1}-{year}" if now.month < 7 else f"{year}-{year+1}"


def _json_or_none(text: str) -> Any | None:
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None


def _is_summary_or_non_result(cells: list[str]) -> bool:
    joined = " ".join(cell.strip().lower() for cell in cells if cell)
    return any(marker in joined for marker in _SUMMARY_MARKERS)


def _parse_rank(raw: Any) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or _is_summary_or_non_result([text]):
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _parse_points(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or _is_summary_or_non_result([text]):
        return None
    text = re.sub(r"\s+", "", text)
    if "," in text and "." not in text:
        parts = text.split(",")
        text = ".".join(parts) if len(parts) == 2 and len(parts[1]) <= 2 else "".join(parts)
    elif "," in text and "." in text:
        text = text.replace(",", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", ".", "-", "-."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _coerce_text(raw: Any) -> str:
    return str(raw or "").strip()


def _first_present(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return value
    return None


def _row_from_json(record: dict[str, Any]) -> dict | None:
    cells = [_coerce_text(record.get(key)) for key in ("totalRank", "rank", "athleteName", "name", "totalPoints")]
    if _is_summary_or_non_result(cells):
        return None

    rank = _parse_rank(_first_present(record, "totalRank", "rank", "排名"))
    name = _coerce_text(_first_present(record, "athleteName", "name", "姓名"))
    if not name and isinstance(record.get("memberInfo"), dict):
        name = _coerce_text(record["memberInfo"].get("memberName"))
    if not rank or not name:
        return None

    club = _coerce_text(_first_present(record, "organName", "club", "单位")) or None
    if not club and isinstance(record.get("organInfo"), dict):
        club = _coerce_text(record["organInfo"].get("organName")) or None
    points = _parse_points(_first_present(record, "totalPoints", "points", "积分"))
    return {"rank": rank, "name": name, "club": club, "points": points}


def _extract_json_records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        payload = data.get("data", data)
        if isinstance(payload, dict):
            records = payload.get("records") or payload.get("rows") or payload.get("data")
            if isinstance(records, list):
                return [row for row in records if isinstance(row, dict)]
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _header_index(headers: list[str], names: tuple[str, ...]) -> int | None:
    for idx, header in enumerate(headers):
        normalized = re.sub(r"\s+", "", header).lower()
        if any(name in normalized for name in names):
            return idx
    return None


def _parse_html_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    header_cells = rows[0].find_all(["td", "th"]) if rows else []
    headers = [cell.get_text(" ", strip=True) for cell in header_cells]
    rank_idx = _header_index(headers, ("排名", "名次", "序号", "rank", "position"))
    name_idx = _header_index(headers, ("姓名", "运动员", "name", "athlete"))
    club_idx = _header_index(headers, ("单位", "俱乐部", "代表单位", "club", "organ"))
    points_idx = _header_index(headers, ("总积分", "积分", "points", "totalpoints"))

    if rank_idx is None:
        rank_idx = 0
    if name_idx is None:
        name_idx = 1
    if club_idx is None:
        club_idx = 2
    if points_idx is None:
        points_idx = 3

    parsed = []
    for row in rows:
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        if not cells or len(cells) <= max(rank_idx, name_idx, points_idx):
            continue
        if _is_summary_or_non_result(cells):
            continue
        rank = _parse_rank(cells[rank_idx])
        name = _coerce_text(cells[name_idx])
        if not rank or not name or name in headers:
            continue
        club = _coerce_text(cells[club_idx]) if len(cells) > club_idx else ""
        points = _parse_points(cells[points_idx])
        parsed.append({"rank": rank, "name": name, "club": club or None, "points": points})
    return parsed


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse China ranking API JSON or a Chinese ranking table into normalized rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    data = _json_or_none(html_or_text)
    if data is not None:
        return [row for record in _extract_json_records(data) if (row := _row_from_json(record))]

    return _parse_html_table(html_or_text)


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict | None:
    try:
        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            verify=VERIFY_SSL,
        )
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code == 404:
        print(f"    HTTP 404 for {response.url}")
        return None
    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {response.url}")
        return None

    try:
        data = response.json()
    except ValueError:
        print(f"    Non-JSON response for {response.url}")
        return None
    if isinstance(data, dict):
        return data
    return None


@lru_cache(maxsize=1)
def _latest_api_season() -> str:
    data = _get_json(SEASON_ENDPOINT)
    seasons = data.get("data") if data else None
    if isinstance(seasons, list):
        for season in seasons:
            if not isinstance(season, dict):
                continue
            value = season.get("seasonDes") or season.get("seasonName") or season.get("value")
            if value:
                return str(value)
    return str(_current_utc().year)


@lru_cache(maxsize=8)
def _latest_week(api_season: str) -> str:
    data = _get_json(WEEK_ENDPOINT, {"season": api_season, "itemType": "I"})
    payload = data.get("data") if data else None
    if isinstance(payload, dict):
        weeks = payload.get("week")
        if isinstance(weeks, list) and weeks:
            first = weeks[0]
            if isinstance(first, dict) and first.get("value"):
                return str(first["value"])
    return ""


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one weapon/gender/category ranking JSON payload from the public China API."""
    weapon_code = _WEAPON_CODES.get(weapon)
    gender_code = _GENDER_CODES.get(gender)
    category_code = _CATEGORY_CODES.get(category)
    if not weapon_code or not gender_code or not category_code:
        return None

    api_season = _latest_api_season()
    params = {
        "searchName": "",
        "gender": gender_code,
        "weapon": weapon_code,
        "groupCode": category_code,
        "season": api_season,
        "week": _latest_week(api_season),
        "current": 1,
        "size": API_PAGE_SIZE,
        "itemType": "I",
    }
    data = _get_json(RANKINGS_ENDPOINT, params)
    if data is None:
        return None

    payload = data.get("data")
    if not isinstance(payload, dict):
        return json.dumps(data, ensure_ascii=False)

    records = list(payload.get("records") or [])
    try:
        pages = int(payload.get("pages") or 1)
    except (TypeError, ValueError):
        pages = 1

    for page in range(2, pages + 1):
        page_params = dict(params)
        page_params["current"] = page
        page_data = _get_json(RANKINGS_ENDPOINT, page_params)
        if page_data is None:
            print(f"    Missing page {page}/{pages} for {weapon} {gender} {category}")
            break
        page_payload = page_data.get("data")
        if not isinstance(page_payload, dict):
            break
        page_records = page_payload.get("records") or []
        records.extend(page_records)
        time.sleep(PAGE_REQUEST_DELAY)

    payload = dict(payload)
    payload["records"] = records
    data = dict(data)
    data["data"] = payload
    return json.dumps(data, ensure_ascii=False)


def main():
    run_log = ScraperRunLogger("scrape_fed_chn").start()
    season = current_season()
    api_season = _latest_api_season()
    latest_week = _latest_week(api_season)
    print(f"China fencing rankings — season {season}; API season {api_season}; week {latest_week or 'latest'}")
    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")
            content = fetch_rankings_page(weapon, gender, category)
            if content is None:
                total_failed += 1
                failed_combos.append(combo_label)
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(content)
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
                    metadata={
                        "api_season": api_season,
                        "week": latest_week,
                        "source_url": RANKINGS_ENDPOINT,
                    },
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Parsed {len(rows)} rows; written {written} rows")
            total_written += written
            time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "api_season": api_season,
                "week": latest_week,
                "failed_combos": failed_combos,
            },
        )
        print(f"Done — written={total_written}, failed={total_failed}, skipped={total_skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

"""
scrape_fed_kor.py — Korean Fencing Federation rankings scraper.

Probe summary (2026-06-01):
  - https://koreafencing.org and https://www.koreafencing.org:
      GET, DNS resolution failed.
  - https://fencing.sports.or.kr/:
      GET, text/html;charset=UTF-8, public Korean federation site.
  - /ranking, /rank, /ranking/list, /ranking/rankList, /player/ranking,
    /api/rankings and similar candidate ranking paths:
      GET, text/html 404 page.
  - /player/profList:
      GET, text/html, public registered-player table with No/이름/소속,
      but no ranking points.
  - /player/nationalProfList:
      GET, text/html, public national-team roster, but no ranking points.
  - /game/finishRank:
      POST, application/json, public competition final standings for completed
      events. Verified senior individual Foil/Epee/Sabre Men/Women on
      eventCd=COMPM00680. This is competition result data, not a public
      national season ranking, so the live scraper does not write it as
      fs_national_fed_rankings.

Public national ranking combos verified: 0/12.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "kor_fencing"
COUNTRY = "KOR"
BASE_URL = "https://fencing.sports.or.kr"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://fencing.sports.or.kr/",
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

PROBE_SUMMARY = {
    "official_base_url": BASE_URL,
    "legacy_domain": "koreafencing.org",
    "legacy_domain_status": "DNS resolution failed",
    "ranking_endpoint_status": "No public national season ranking endpoint found",
    "competition_result_endpoint": {
        "url": f"{BASE_URL}/game/finishRank",
        "method": "POST",
        "format": "application/json",
        "public_combos_observed": [
            "Senior Men Foil",
            "Senior Men Epee",
            "Senior Men Sabre",
            "Senior Women Foil",
            "Senior Women Epee",
            "Senior Women Sabre",
        ],
        "used_for_rankings": False,
        "reason": "competition final standings, not national ranking points",
    },
}

# Keep empty until a public national ranking URL is verified. This prevents
# writing tournament result standings into the national rankings table.
RANKING_URL_TEMPLATES: tuple[str, ...] = ()

_HANGUL_RE = re.compile(r"[\uAC00-\uD7AF]+(?:[\s·ㆍ]*[\uAC00-\uD7AF]+)*")
_ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
_SKIP_MARKERS = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "withdraw",
    "summary",
    "total",
    "기권",
    "실격",
    "합계",
    "총계",
    "총점",
}

_HEADER_ALIASES = {
    "rank": {"순위", "등위", "rank", "ranking", "place"},
    "name": {"이름", "성명", "선수", "선수명", "name", "athlete", "player", "plynm"},
    "club": {"소속", "소속팀", "팀", "팀명", "club", "team", "teamnm"},
    "points": {"점수", "포인트", "points", "point", "score", "scoreval"},
}


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split())


def _contains_skip_marker(value: str) -> bool:
    text = _clean_text(value).lower()
    return any(marker in text for marker in _SKIP_MARKERS)


def _parse_rank(value: object) -> int | None:
    text = _clean_text(value)
    if not text or _contains_skip_marker(text):
        return None
    match = re.search(r"\d+", text.replace(",", ""))
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _parse_points(value: object) -> float | None:
    text = _clean_text(value)
    if not text or _contains_skip_marker(text):
        return None

    number = re.sub(r"[^\d,.\-]", "", text)
    if not number or number in {"-", ".", ",", "-.", "-,"}:
        return None

    if "," in number and "." in number:
        number = number.replace(",", "")
    elif "," in number:
        parts = number.split(",")
        if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
            number = ".".join(parts)
        else:
            number = "".join(parts)

    try:
        return float(number)
    except ValueError:
        return None


def _split_korean_name(value: object) -> tuple[str, str | None]:
    text = _clean_text(value)
    if not text:
        return "", None

    hangul_matches = [match.group(0).strip() for match in _HANGUL_RE.finditer(text)]
    if not hangul_matches:
        return text, None

    primary = " ".join(hangul_matches).strip()
    if not _ASCII_LETTER_RE.search(text):
        return primary, None

    alternate = text
    for match in hangul_matches:
        alternate = alternate.replace(match, " ")
    alternate = re.sub(r"[\(\)\[\]{}]", " ", alternate)
    alternate = re.sub(r"\s*[/|,;]\s*", " ", alternate)
    alternate = _clean_text(alternate.strip(" -"))

    return primary, alternate if alternate else None


def _first_present(row: dict, keys: tuple[str, ...]) -> object:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _row_from_values(rank_raw: object, name_raw: object, club_raw: object, points_raw: object) -> dict | None:
    joined = " ".join(_clean_text(v) for v in (rank_raw, name_raw, club_raw, points_raw))
    if _contains_skip_marker(joined):
        return None

    rank = _parse_rank(rank_raw)
    name, alternate_name = _split_korean_name(name_raw)
    if rank is None or not name:
        return None

    row = {
        "rank": rank,
        "name": name,
        "club": _clean_text(club_raw) or None,
        "points": _parse_points(points_raw),
    }
    if alternate_name:
        row["alternate_name"] = alternate_name
    return row


def _normalise_header(value: str) -> str:
    return re.sub(r"[\s:_\-()]+", "", _clean_text(value).lower())


def _header_indices(headers: list[str]) -> dict[str, int]:
    indices: dict[str, int] = {}
    for index, header in enumerate(headers):
        normalised = _normalise_header(header)
        for field, aliases in _HEADER_ALIASES.items():
            if normalised in aliases and field not in indices:
                indices[field] = index
    return indices


def _parse_json_rankings(text: str) -> list[dict]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    if isinstance(payload, list):
        raw_rows = payload
    elif isinstance(payload, dict):
        raw_rows = []
        for key in ("resultList", "rankList", "ranks", "rows", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                raw_rows = value
                break
    else:
        return []

    rows = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        row = _row_from_values(
            _first_present(raw, ("rank", "rankNo", "ranking", "position", "순위")),
            _first_present(raw, ("name", "plyNm", "playerName", "athleteName", "이름", "성명")),
            _first_present(raw, ("club", "teamNm", "teamName", "team", "소속", "팀명")),
            _first_present(raw, ("points", "scoreVal", "score", "point", "점수", "포인트")),
        )
        if row:
            rows.append(row)
    return rows


def _parse_html_rankings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for table in soup.find_all("table"):
        table_rows = table.find_all("tr")
        if not table_rows:
            continue

        header_row_index = None
        indices: dict[str, int] = {}
        for index, row in enumerate(table_rows):
            cells = row.find_all(["th", "td"])
            headers = [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            candidate = _header_indices(headers)
            if {"rank", "name", "points"}.issubset(candidate):
                header_row_index = index
                indices = candidate
                break

        if header_row_index is None:
            continue

        max_index = max(indices.values())
        for row in table_rows[header_row_index + 1:]:
            if row.find("th"):
                continue
            cells = row.find_all("td")
            if len(cells) <= max_index:
                continue
            values = [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            parsed = _row_from_values(
                values[indices["rank"]],
                values[indices["name"]],
                values[indices.get("club", -1)] if "club" in indices else None,
                values[indices["points"]],
            )
            if parsed:
                results.append(parsed)

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Korean ranking HTML or public KFA-style JSON into ranking rows."""
    text = (html_or_text or "").strip()
    if not text:
        return []

    json_rows = _parse_json_rankings(text)
    if json_rows:
        return json_rows

    return _parse_html_rankings(text)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """
    Fetch one public national ranking page if a verified URL template exists.

    The 2026-06-01 probe found no public national season ranking URL on the
    KFA site. Until one is verified, return None and let main log the combo as
    skipped rather than misclassifying competition final standings as rankings.
    """
    if not RANKING_URL_TEMPLATES:
        return None

    for template in RANKING_URL_TEMPLATES:
        url = template.format(weapon=weapon.lower(), gender=gender.lower(), category=category.lower())
        try:
            response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
        except requests.RequestException as exc:
            print(f"    Request error for {url}: {exc}")
            continue

        if response.status_code == 200:
            return response.text
        if response.status_code != 404:
            print(f"    HTTP {response.status_code} for {url}")

    return None


def current_season() -> str:
    try:
        from season_utils import current_fie_season, season_to_string

        return season_to_string(current_fie_season())
    except Exception:
        pass

    try:
        from season_utils import current_season as shared_current_season
        from season_utils import normalize_season

        return normalize_season(shared_current_season())
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def _metadata_for_row(row: dict) -> dict:
    metadata = {"country_source": "Korean Fencing Federation"}
    if row.get("alternate_name"):
        metadata["alternate_name"] = row["alternate_name"]
    return metadata


def main():
    run_log = ScraperRunLogger("scrape_fed_kor").start()
    season = current_season()
    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos = []
    missing_combos = []

    print(f"Korean Fencing Federation rankings — season {season}")
    print("No public KFA national ranking endpoint verified; logging combos as skipped.")

    try:
        for weapon, gender, category in RANKING_COMBOS:
            print(f"  {weapon} {gender} {category}...")
            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                total_skipped += 1
                missing_combos.append({"weapon": weapon, "gender": gender, "category": category})
                print("    Skipped: no public national ranking URL found")
                if RANKING_URL_TEMPLATES:
                    time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(content)
            if not parsed:
                total_failed += 1
                failed_combos.append({"weapon": weapon, "gender": gender, "category": category})
                print("    No rows parsed")
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
                    metadata=_metadata_for_row(row),
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            total_written += written
            print(f"    Written {written} rows ({len(parsed)} parsed)")
            time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "probe_summary": PROBE_SUMMARY,
                "failed_combos": failed_combos,
                "missing_combos": missing_combos,
                "combos_working": len(RANKING_COMBOS) - total_skipped - total_failed,
                "combos_total": len(RANKING_COMBOS),
            },
        )
        print(
            "Done — "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"combos_working={len(RANKING_COMBOS) - total_skipped - total_failed}/{len(RANKING_COMBOS)}"
        )
        if total_written == 0 and (total_skipped + total_failed) > 0:
            print(f"[WARNING] {SOURCE}: zero rows written after processing all targets — check URL config or source availability")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

"""
scrape_fed_iri.py - Iran Fencing Federation rankings scraper.

Probe notes:
  Initial probe domain: https://iranfencing.ir/
  Current services host: https://www.iranfencing.org/
  Public indexed ranking examples:
    GET https://irfnc-services.ir/Athletes/Ranking/rankshow/Foil-Female-C-I
    GET https://irfnc-services.ir/Athletes/Ranking/rankshow/Sabre-Female-C-I
  Response format: HTML tables with Farsi/RTL headers and Persian numerals.
  URL convention: /Athletes/Ranking/rankshow/{Weapon}-{Gender}-{Category}-I

The public examples verified the table shape for cadet pages. This scraper
attempts all requested Senior/Junior weapon and gender combinations using the
same rankshow convention and logs each missing or blocked combo without
crashing.
"""

import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger

try:
    from season_utils import season_to_string
except ImportError:  # pragma: no cover - compatibility fallback for isolated runs.
    season_to_string = None


SOURCE = "iri_fencing"
COUNTRY = "Iran"
BASE_URL = "https://www.iranfencing.org/Athletes/Ranking/rankshow"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.iranfencing.org/Athletes/Ranking",
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

WEAPON_CODES = {
    "Foil": "Foil",
    "Epee": "Epee",
    "Sabre": "Sabre",
}
GENDER_CODES = {
    "Men": "Male",
    "Women": "Female",
}
CATEGORY_CODES = {
    "Senior": "S",
    "Junior": "J",
}

_DIGIT_TRANS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_BIDI_CHARS = "\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
_SKIP_RANKS = {"dns", "dq", "dsq", "dnf", "حذف", "انصراف"}
_SUMMARY_MARKERS = ("جمع", "مجموع", "خلاصه", "summary", "total")
_BLOCKED_MARKERS = (
    "access denied",
    "forbidden",
    "cloudflare",
    "service unavailable",
    "please enable javascript",
    "enable javascript",
    "دسترسی غیرمجاز",
    "دسترسی امکان پذیر نیست",
)


def build_rankings_url(weapon: str, gender: str, category: str) -> str:
    """Build the public Iran federation rankshow URL for one combo."""
    weapon_code = WEAPON_CODES[weapon]
    gender_code = GENDER_CODES[gender]
    category_code = CATEGORY_CODES[category]
    return f"{BASE_URL}/{weapon_code}-{gender_code}-{category_code}-I"


def _clean_text(value: str) -> str:
    for char in _BIDI_CHARS:
        value = value.replace(char, "")
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def _normalize_digits(value: str) -> str:
    return _clean_text(value).translate(_DIGIT_TRANS)


def _parse_rank(value: str) -> int | None:
    text = _normalize_digits(value).strip(" .#")
    if text.lower() in _SKIP_RANKS:
        return None
    if not re.fullmatch(r"\d+", text):
        return None
    rank = int(text)
    return rank if rank > 0 else None


def _parse_points(value: str) -> float | None:
    text = _normalize_digits(value)
    if not text or "/" in text:
        return None
    text = (
        text.replace("٫", ".")
        .replace("٬", ",")
        .replace(" ", "")
        .strip()
    )
    if "," in text and "." not in text:
        if re.fullmatch(r"\d+,\d{1,2}", text):
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text and "." in text:
        text = text.replace(",", "")

    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None
    return float(text)


def _is_summary_or_status_row(cells: list[str]) -> bool:
    if not cells:
        return True
    first = _normalize_digits(cells[0]).lower()
    if first in _SKIP_RANKS:
        return True
    return any(marker in first for marker in _SUMMARY_MARKERS)


def _find_indexes(cells: list[str], header_rows: list[list[str]]) -> tuple[int, int, int | None, int | None]:
    rank_idx = 0
    name_idx = 1
    club_idx = 2 if len(cells) > 2 else None
    points_idx = len(cells) - 1 if cells else None

    for headers in header_rows:
        if len(headers) != len(cells):
            continue
        for idx, header in enumerate(headers):
            header_text = _clean_text(header).lower()
            if any(token in header_text for token in ("رتبه", "رده", "rank")):
                rank_idx = idx
            if "نام" in header_text or "name" in header_text:
                name_idx = idx
            if any(token in header_text for token in ("باشگاه", "استان", "club", "province")):
                club_idx = idx
            if any(token in header_text for token in ("جمع امتیاز", "امتیاز", "points", "total")):
                points_idx = idx

    return rank_idx, name_idx, club_idx, points_idx


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Iran federation HTML ranking tables into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        header_rows: list[list[str]] = []
        for row in table.find_all("tr"):
            cells = [
                _clean_text(cell.get_text(" ", strip=True))
                for cell in row.find_all(["td", "th"])
            ]
            if len(cells) < 2 or _is_summary_or_status_row(cells):
                continue

            rank_idx, name_idx, club_idx, points_idx = _find_indexes(cells, header_rows)
            rank_text = cells[rank_idx] if rank_idx < len(cells) else ""
            rank = _parse_rank(rank_text)
            if rank is None:
                if row.find("th") or not header_rows:
                    header_rows.append(cells)
                continue

            if name_idx >= len(cells):
                continue
            name = _clean_text(cells[name_idx])
            if not name:
                continue

            club = None
            if club_idx is not None and club_idx < len(cells):
                club = _clean_text(cells[club_idx]) or None

            points = None
            if points_idx is not None and points_idx < len(cells):
                points = _parse_points(cells[points_idx])
            if points is None:
                for cell in reversed(cells[2:]):
                    points = _parse_points(cell)
                    if points is not None:
                        break

            results.append({
                "rank": rank,
                "name": name,
                "club": club,
                "points": points,
            })

    return results


def _looks_unusable_response(text: str) -> bool:
    lowered = text.lower()
    if any(marker in lowered for marker in _BLOCKED_MARKERS):
        return True
    if "ورود" in text and ("password" in lowered or "رمز عبور" in text):
        return True
    return False


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public Iran federation ranking page, returning None on failures."""
    url = build_rankings_url(weapon, gender, category)
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code == 404:
        print(f"    No scrapeable rankings at {url} (HTTP 404)")
        return None
    if response.status_code in {401, 403}:
        print(f"    No scrapeable rankings at {url} (HTTP {response.status_code})")
        return None
    if response.status_code >= 500:
        time.sleep(REQUEST_DELAY)
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=15,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            print(f"    Request error for {url}: {exc}")
            return None
        if response.status_code >= 400:
            print(f"    No scrapeable rankings at {url} (HTTP {response.status_code})")
            return None
    elif response.status_code >= 400:
        print(f"    No scrapeable rankings at {url} (HTTP {response.status_code})")
        return None

    content = response.text or ""
    if _looks_unusable_response(content):
        print(f"    No scrapeable rankings at {url} (blocked/login/js-only)")
        return None
    return content


def current_season() -> str:
    now = datetime.now(timezone.utc)
    season_end_year = now.year if now.month < 7 else now.year + 1
    if season_to_string is not None:
        return season_to_string(season_end_year)
    return f"{season_end_year - 1:04d}-{season_end_year:04d}"


def main():
    run_log = ScraperRunLogger("scrape_fed_iri").start()
    season = current_season()
    print(f"Iran federation rankings - season {season}")
    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[dict] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            combo_label = f"{weapon} {gender} {category}"
            url = build_rankings_url(weapon, gender, category)
            print(f"  {combo_label}...")

            content = fetch_rankings_page(weapon, gender, category)
            if content is None:
                total_failed += 1
                failed_combos.append({
                    "weapon": weapon,
                    "gender": gender,
                    "category": category,
                    "url": url,
                    "reason": "fetch_failed_or_blocked",
                })
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(content)
            if not parsed:
                print(f"    No scrapeable rankings at {url}")
                total_failed += 1
                failed_combos.append({
                    "weapon": weapon,
                    "gender": gender,
                    "category": category,
                    "url": url,
                    "reason": "no_rankings_rows",
                })
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
                    metadata={"source_url": url},
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Written {written} rows")
            total_written += written
            time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "attempted_combos": len(RANKING_COMBOS),
                "failed_combos": failed_combos,
                "base_url": BASE_URL,
            },
        )
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

"""
scrape_fed_bel.py — Belgium national federation rankings scraper.

Probe results (2026-06-01):
  - National page:
      GET https://www.fencing-belgium.be/nationa-a-l
      HTML page linking national rankings to Ophardt.
  - Working rankings index:
      GET https://fencing.ophardt.online/en/search/rankings/159
      HTML table with public ranking links.
  - Working ranking pages:
      GET https://fencing.ophardt.online/en/search/rankings/show/<id>
      HTML, server-rendered ranking table.
  - Public Senior and U20 individual rankings exist for Foil/Epee/Sabre,
    Men/Women. U20 is stored as Junior.
  - FFCEB/VSB pages were checked; no separate public regional ranking tables
    were found. Both point users back to the national KBFS/FRBCE/Ophardt flow.

Ophardt ranking columns:
  Rank | Points | T-P | Name | Nation | Clubs | YOB | per-event columns...
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "bel_fencing"
COUNTRY = "BEL"
BASE_URL = "https://fencing.ophardt.online"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8,nl;q=0.7,de;q=0.6",
    "Referer": "https://www.fencing-belgium.be/nationa-a-l",
}

RANKINGS_INDEX_URL = f"{BASE_URL}/en/search/rankings/159"
LANGUAGE = "en"
SUB_FEDERATION = "KBFS-FRBCE"

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

# IDs from the public Ophardt index. Cell order is Men's Epee/Foil/Sabre,
# then Women's Epee/Foil/Sabre; U20 maps to this scraper's Junior category.
RANKING_PAGE_IDS = {
    ("Epee", "Men", "Senior"): 21418,
    ("Foil", "Men", "Senior"): 21464,
    ("Sabre", "Men", "Senior"): 21469,
    ("Epee", "Women", "Senior"): 21349,
    ("Foil", "Women", "Senior"): 21463,
    ("Sabre", "Women", "Senior"): 21424,
    ("Epee", "Men", "Junior"): 21415,
    ("Foil", "Men", "Junior"): 21416,
    ("Sabre", "Men", "Junior"): 21468,
    ("Epee", "Women", "Junior"): 21348,
    ("Foil", "Women", "Junior"): 21466,
    ("Sabre", "Women", "Junior"): 21423,
}

REGIONAL_SOURCES = [
    {
        "sub_federation": SUB_FEDERATION,
        "language": LANGUAGE,
        "url": RANKINGS_INDEX_URL,
        "request_method": "GET",
        "response_format": "html",
        "coverage": "Senior and Junior individual Foil/Epee/Sabre Men/Women",
    }
]

_HEADER_ALIASES = {
    "rank": {"rank", "rang", "classement", "place", "plaats", "platz"},
    "name": {"name", "naam", "nom"},
    "club": {"club", "clubs", "vereniging", "verenigingen", "vereine"},
    "points": {"points", "punt", "punten", "punkte", "pts"},
}
_SKIP_TOKENS = {
    "DNS",
    "DNF",
    "DQ",
    "DSQ",
    "FORFAIT",
    "ABANDON",
    "TOTAL",
    "SUMMARY",
    "TOTAAL",
    "TOTAUX",
    "SOMME",
    "SUMME",
}
_DETAIL_SPLIT_RE = re.compile(
    r"\s+(?:Details?|D[ée]tails?|Detail|Biographie|Biography)\b",
    flags=re.IGNORECASE,
)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _normalize_header(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", without_accents)


def _header_indices(table) -> dict[str, int] | None:
    rows = []
    thead = table.find("thead")
    if thead:
        rows.extend(thead.find_all("tr"))
    rows.extend(row for row in table.find_all("tr") if row.find("th"))

    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        labels = [_normalize_header(cell.get_text(" ", strip=True)) for cell in cells]
        indices: dict[str, int] = {}
        for index, label in enumerate(labels):
            for field, aliases in _HEADER_ALIASES.items():
                if label in aliases and field not in indices:
                    indices[field] = index
        if {"rank", "name", "points"}.issubset(indices):
            return indices
    return None


def _iter_body_rows(table):
    bodies = table.find_all("tbody", recursive=False)
    if bodies:
        for body in bodies:
            yield from body.find_all("tr", recursive=False)
        return
    yield from table.find_all("tr", recursive=False)


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value)
    if text.upper() in _SKIP_TOKENS:
        return None
    match = re.match(r"^(\d+)(?:[.)]|e|er|eme|ème)?$", text, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if not text or text.upper() in _SKIP_TOKENS:
        return None
    match = re.search(r"[-+]?\d[\d\s\xa0\u202f'.,]*", text)
    if not match:
        return None
    number = match.group(0)
    number = number.replace("\xa0", "").replace("\u202f", "").replace(" ", "").replace("'", "")
    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    elif "," in number:
        number = number.replace(",", ".")
    try:
        return float(number)
    except ValueError:
        return None


def _clean_name(value: str) -> str:
    text = _clean_text(value)
    text = _DETAIL_SPLIT_RE.split(text, maxsplit=1)[0]
    return _clean_text(text)


def _should_skip_name(name: str) -> bool:
    normalized = _clean_text(name).upper()
    if not normalized:
        return True
    return normalized in _SKIP_TOKENS or normalized.startswith(("TOTAL ", "SUMMARY "))


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse a Belgium Ophardt ranking page into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    results = []
    for table in soup.find_all("table"):
        indices = _header_indices(table)
        if not indices:
            continue

        required_max = max(indices["rank"], indices["name"], indices["points"], indices.get("club", 0))
        for row in _iter_body_rows(table):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) <= required_max:
                continue

            rank = _parse_rank(cells[indices["rank"]].get_text(" ", strip=True))
            if rank is None:
                continue

            name = _clean_name(cells[indices["name"]].get_text(" ", strip=True))
            if _should_skip_name(name):
                continue

            club = None
            if "club" in indices and len(cells) > indices["club"]:
                club = _clean_text(cells[indices["club"]].get_text(" ", strip=True)) or None

            points = _parse_points(cells[indices["points"]].get_text(" ", strip=True))
            results.append({"rank": rank, "name": name, "club": club, "points": points})

    return results


def _ranking_url(ranking_id: int, language: str = LANGUAGE) -> str:
    return f"{BASE_URL}/{language}/search/rankings/show/{ranking_id}"


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public Belgium Ophardt ranking page, returning None on failure."""
    ranking_id = RANKING_PAGE_IDS.get((weapon, gender, category))
    if ranking_id is None:
        print(f"    No public ranking ID for {weapon} {gender} {category}")
        return None

    url = _ranking_url(ranking_id)
    last_error = None
    for attempt in range(1, 4):
        try:
            response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
        except requests.RequestException as exc:
            last_error = exc
            print(f"    Request error for {url} (attempt {attempt}/3): {exc}")
            if attempt < 3:
                time.sleep(min(REQUEST_DELAY * attempt, 5))
            continue

        if response.status_code == 200:
            return response.text
        if response.status_code == 404:
            print(f"    HTTP 404 for {url}")
            return None

        print(f"    HTTP {response.status_code} for {url} (attempt {attempt}/3)")
        if response.status_code in {403, 408, 425, 429} or response.status_code >= 500:
            if attempt < 3:
                time.sleep(min(REQUEST_DELAY * attempt, 5))
            continue
        return None

    if last_error:
        print(f"    Giving up after request errors for {url}: {last_error}")
    return None


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY."""
    now = datetime.now(UTC)
    end_year = now.year if now.month < 7 else now.year + 1
    try:
        from season_utils import normalize_season

        return normalize_season(end_year)
    except Exception:
        return f"{end_year - 1}-{end_year}"


def _normalize_identity_part(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value.lower())
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", without_accents)


def _dedupe_rows(rows: list[dict]) -> tuple[list[dict], int]:
    seen = set()
    deduped = []
    skipped = 0
    for row in rows:
        key = (
            _normalize_identity_part(row.get("name")),
            _normalize_identity_part(row.get("club")),
            row.get("weapon"),
            row.get("gender"),
            row.get("category"),
        )
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        deduped.append(row)
    return deduped, skipped


def main():
    run_log = ScraperRunLogger("scrape_fed_bel").start()
    season = current_season()
    print(f"Belgium federation rankings — season {season}")
    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            combo_label = f"{weapon} {gender} {category}"
            ranking_id = RANKING_PAGE_IDS.get((weapon, gender, category))
            print(f"  {combo_label} (ID {ranking_id})...")
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

            source_url = _ranking_url(ranking_id) if ranking_id else None
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
                        "language": LANGUAGE,
                        "sub_federation": SUB_FEDERATION,
                        "ranking_id": ranking_id,
                        "source_url": source_url,
                        "rankings_index_url": RANKINGS_INDEX_URL,
                        "request_method": "GET",
                        "response_format": "html",
                    },
                )
                for row in parsed
            ]
            rows, skipped = _dedupe_rows(rows)
            total_skipped += skipped

            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Written {written} rows ({len(parsed)} parsed, {skipped} duplicates skipped)")
            total_written += written
            time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "failed_combos": failed_combos,
                "combos_total": len(RANKING_COMBOS),
                "combos_failed": total_failed,
                "rankings_index_url": RANKINGS_INDEX_URL,
                "regional_sources": REGIONAL_SOURCES,
            },
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise

    print(f"Done — written={total_written}, failed={total_failed}, skipped={total_skipped}")


if __name__ == "__main__":
    main()

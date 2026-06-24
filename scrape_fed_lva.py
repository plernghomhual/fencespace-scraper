"""
scrape_fed_lva.py - Latvia national federation rankings scraper.

Probe evidence, 2026-06-02:
  - Prompt host `pauksmes.lv` has no search presence; official federation site is
    https://paukosana.lv/.
  - Working public source: GET https://paukosana.lv/sacensibu-rezultati/
    returns WordPress HTML listing official competition-result Google Drive folders.
  - WordPress API searches for "ranking" and "reitings" returned empty arrays.
  - Google Drive folders are public but list competition result folders, not durable
    federation ranking tables.
  - https://paukosana.tv/results/LCH2021/index.htm returns FencingTime competition
    live results, not season federation rankings.
  - Public Senior/Junior weapon/gender ranking coverage found: 0/12 combos.

The parser remains ready for a future public Latvian ranking table with localized
headers. Until such a table exists, main() attempts all standard combos and exits
cleanly with skipped combo metadata.
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Iterable
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "lva_fencing"
COUNTRY = "Latvia"
BASE_URL = "https://paukosana.lv/sacensibu-rezultati/"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "lv,en;q=0.9",
    "Referer": "https://paukosana.lv/",
}

PROBED_URLS = [
    "https://pauksmes.lv/",
    "https://paukosana.lv/",
    "https://paukosana.lv/sacensibu-rezultati/",
    "https://paukosana.lv/wp-json/wp/v2/pages?per_page=100",
    "https://paukosana.lv/wp-json/wp/v2/posts?per_page=100&search=reitings",
    "https://paukosana.lv/wp-json/wp/v2/posts?per_page=100&search=ranking",
    "https://drive.google.com/drive/folders/1K458Aph-bakcajRkaIDMN7UVigllATwI?usp=drive_link",
    "https://paukosana.tv/results/LCH2021/index.htm",
]

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

_RANK_HEADERS = {
    "vieta",
    "rank",
    "ranking",
    "place",
    "seed",
    "pozicija",
    "nr",
}
_NAME_HEADERS = {
    "vards",
    "uzvards",
    "vardsuzvards",
    "sportists",
    "sportiste",
    "sportistsportiste",
    "athlete",
    "fencer",
    "name",
}
_CLUB_HEADERS = {
    "klubs",
    "club",
    "clubs",
    "clubss",
    "seura",
}
_POINT_HEADERS = {
    "punkti",
    "punkt",
    "points",
    "point",
    "pts",
    "totalpoints",
    "total",
}
_SKIP_VALUES = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "ret",
    "kop",
    "kopa",
    "kopaa",
    "kopsavilkums",
    "summary",
    "total",
    "totals",
    "nav",
}


def current_season() -> str:
    """Return the current fencing season range as YYYY-YYYY."""
    now = datetime.now(UTC)
    season_end_year = now.year if now.month < 7 else now.year + 1
    try:
        from season_utils import normalize_season

        return normalize_season(season_end_year)
    except Exception:
        return f"{season_end_year - 1:04d}-{season_end_year:04d}"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _normalize_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(value))
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def _is_skip_text(value: str) -> bool:
    token = _normalize_token(value)
    return not token or token in _SKIP_VALUES


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value)
    if _is_skip_text(text):
        return None
    match = re.match(r"^\s*(\d+)", text)
    if not match:
        return None
    rank = int(match.group(1))
    return rank if rank > 0 else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if _is_skip_text(text):
        return None

    text = text.replace(" ", "")
    text = re.sub(r"[^0-9,.\-]", "", text)
    if text in {"", "-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            normalized = text.replace(".", "").replace(",", ".")
        else:
            normalized = text.replace(",", "")
    elif "," in text:
        left, right = text.rsplit(",", 1)
        if len(right) in (1, 2):
            normalized = f"{left.replace(',', '')}.{right}"
        else:
            normalized = text.replace(",", "")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 2 and all(len(part) == 3 for part in parts[1:]):
            normalized = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0].lstrip("-")) <= 3:
            normalized = "".join(parts)
        else:
            normalized = text
    else:
        normalized = text

    try:
        return float(normalized)
    except ValueError:
        return None


def _top_level_rows(table: Tag) -> list[Tag]:
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _row_cells(row: Tag) -> list[Tag]:
    return row.find_all(["td", "th"], recursive=False)


def _find_header_mapping(labels: Iterable[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, label in enumerate(labels):
        token = _normalize_token(label)
        if "rank" not in mapping and token in _RANK_HEADERS:
            mapping["rank"] = index
        elif "name" not in mapping and token in _NAME_HEADERS:
            mapping["name"] = index
        elif "club" not in mapping and token in _CLUB_HEADERS:
            mapping["club"] = index
        elif "points" not in mapping and token in _POINT_HEADERS:
            mapping["points"] = index

    required = {"rank", "name"}
    return mapping if required.issubset(mapping) else None


def _cell_text(cell: Tag, *, prefer_name: bool = False) -> str:
    if prefer_name:
        name_link = cell.find("a", class_=lambda value: value and "dropdown-toggle" in value)
        if name_link:
            return _clean_text(name_link.get_text(" ", strip=True))

    clone = BeautifulSoup(str(cell), "html.parser").find(cell.name)
    if clone is None:
        return _clean_text(cell.get_text(" ", strip=True))

    for tag in clone.find_all(["script", "style", "table", "ul"]):
        tag.decompose()
    for tag in clone.find_all("div", class_=lambda value: value and "modal" in value):
        tag.decompose()

    return _clean_text(clone.get_text(" ", strip=True))


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Latvian/localized ranking HTML into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        rows = _top_level_rows(table)
        for header_index, header_row in enumerate(rows):
            header_cells = _row_cells(header_row)
            if not header_cells:
                continue

            labels = [cell.get_text(" ", strip=True) for cell in header_cells]
            mapping = _find_header_mapping(labels)
            if not mapping:
                continue

            min_cell_count = max(mapping.values()) + 1
            for row in rows[header_index + 1:]:
                cells = _row_cells(row)
                if len(cells) < min_cell_count:
                    continue
                if _find_header_mapping(cell.get_text(" ", strip=True) for cell in cells):
                    continue

                rank = _parse_rank(_cell_text(cells[mapping["rank"]]))
                if rank is None:
                    continue

                name = _cell_text(cells[mapping["name"]], prefer_name=True)
                if not name or _is_skip_text(name):
                    continue

                club = None
                if "club" in mapping and mapping["club"] < len(cells):
                    club = _cell_text(cells[mapping["club"]]) or None

                points = None
                if "points" in mapping and mapping["points"] < len(cells):
                    points = _parse_points(_cell_text(cells[mapping["points"]]))

                results.append({"rank": rank, "name": name, "club": club, "points": points})

    return results


def ranking_url_for(weapon: str, gender: str, category: str) -> str | None:
    if (weapon, gender, category) not in RANKING_COMBOS:
        return None
    return BASE_URL


def _looks_login_only(text: str) -> bool:
    token = text.lower()
    return any(marker in token for marker in ("type='password'", 'type="password"', "wp-login", "log in", "sign in"))


def _looks_js_only(text: str) -> bool:
    token = text.lower()
    return any(
        marker in token
        for marker in (
            "enable javascript",
            "please enable javascript",
            "drive_main_page",
            "this browser version is no longer supported",
        )
    )


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public Latvia ranking page, returning None for no public data."""
    url = ranking_url_for(weapon, gender, category)
    if not url:
        print(f"    No public ranking URL for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code == 404:
        print(f"    No scrapeable rankings at {url}")
        return None
    if response.status_code in {401, 403}:
        print(f"    Access blocked for {url}: HTTP {response.status_code}")
        return None
    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    text = response.text or ""
    if _looks_login_only(text):
        print(f"    Login-only ranking page at {url}")
        return None
    if _looks_js_only(text):
        print(f"    JS-only/no static ranking data at {url}")
        return None
    parsed_rows = parse_rankings_table(text)
    if not parsed_rows or all(row.get("points") is None for row in parsed_rows):
        print(f"    No scrapeable rankings at {url}")
        return None
    return text


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main():
    run_log = ScraperRunLogger("scrape_fed_lva").start()
    season = current_season()
    print(f"Latvia federation rankings - season {season}")
    print(f"Probe URLs checked: {', '.join(PROBED_URLS)}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos: list[str] = []
    failed_combos: list[str] = []
    skipped_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            label = _combo_label(weapon, gender, category)
            print(f"  {label}...")

            html = fetch_rankings_page(weapon, gender, category)
            if html is None:
                total_skipped += 1
                skipped_combos.append(label)
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(html)
            if not parsed:
                print("    No rows parsed")
                total_failed += 1
                failed_combos.append(label)
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
                    metadata={"source_url": BASE_URL},
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Parsed {len(parsed)} rows; written {written}")
            total_written += written
            working_combos.append(label)
            time.sleep(REQUEST_DELAY)

        metadata = {
            "season": season,
            "combos_total": len(RANKING_COMBOS),
            "combos_working": len(working_combos),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
            "skipped_combos": skipped_combos,
            "probed_urls": PROBED_URLS,
        }
        set_state(SOURCE, "last_run", metadata)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=metadata,
        )
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"combos_working={len(working_combos)}/{len(RANKING_COMBOS)}"
        )
        if total_written == 0 and (total_skipped + total_failed) > 0:
            print(f"[WARNING] {SOURCE}: zero rows written after processing all targets — check URL config or source availability")
        if skipped_combos:
            print(f"Skipped combos: {', '.join(skipped_combos)}")
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

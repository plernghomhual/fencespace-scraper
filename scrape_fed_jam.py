"""
scrape_fed_jam.py - Jamaica Fencing Federation rankings scraper.

Probe evidence, 2026-06-02:
  - Requested probe domain: https://jamaicafencing.com
  - Official site listed by Commonwealth Fencing Federation:
      https://jamaicanfencing.org/
  - Request method: GET
  - Response format: public server-rendered HTML landing/contact page
  - Public ranking combos: none found for Senior/Junior Men/Women
    Foil/Epee/Sabre.

No durable public Jamaica national ranking table was found. This scraper still
attempts all 12 standard federation ranking combos and exits cleanly, while
keeping a parser ready for future public HTML tables with:
  Rank | Name | Club | Points
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import set_state

try:
    from season_utils import season_to_string
except ImportError:  # pragma: no cover - compatibility fallback
    def season_to_string(season_int: int) -> str:
        return f"{season_int - 1:04d}-{season_int:04d}"


SOURCE = "jam_fencing"
COUNTRY = "Jamaica"
BASE_URL = "https://jamaicanfencing.org"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-JM,en-US;q=0.8,en;q=0.6",
    "Referer": "https://jamaicafencing.com",
}

REQUEST_METHOD = "GET"
DATA_FORMAT = "stub"
PROBED_URLS = [
    {
        "url": "https://jamaicafencing.com",
        "method": REQUEST_METHOD,
        "format": "unretrievable during probe",
        "public_combos": [],
    },
    {
        "url": BASE_URL,
        "method": REQUEST_METHOD,
        "format": "html landing/contact page",
        "public_combos": [],
    },
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

_RANK_HEADERS = {"#", "rank", "ranking", "place", "position", "pos"}
_NAME_HEADERS = {"name", "fencer", "athlete", "competitor"}
_CLUB_HEADERS = {"club", "team", "school", "association", "affiliation"}
_POINT_HEADERS = {"points", "point", "pts", "totalpoints", "score"}
_SKIP_TOKENS = {
    "",
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "ret",
    "withdrawn",
    "total",
    "totals",
    "summary",
    "subtotal",
    "noresult",
    "norank",
}
_NO_DATA_MARKERS = {
    "no rankings available",
    "no ranking available",
    "no ranking data",
    "no data",
    "rankings coming soon",
}
_BLOCKED_MARKERS = {
    "login required",
    "sign in",
    "log in",
    "password",
    "requires javascript",
    "enable javascript",
    "recaptcha",
}


def current_season() -> str:
    """Return the current national ranking season as YYYY-YYYY."""
    now = datetime.now(timezone.utc)
    season_end_year = now.year if now.month < 7 else now.year + 1
    return season_to_string(season_end_year)


def _clean_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _normalize_token(value: str) -> str:
    text = _clean_text(value)
    if text == "#":
        return "#"
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def _is_skip_text(value: str) -> bool:
    return _normalize_token(value) in _SKIP_TOKENS


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value)
    if not text or _is_skip_text(text):
        return None

    match = re.match(r"^\s*(\d+)", text)
    if not match:
        return None

    rank = int(match.group(1))
    return rank if rank > 0 else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value).replace(" ", "")
    if not text or _is_skip_text(text) or text in {"-", "—", "–"}:
        return None

    text = re.sub(r"[^0-9,.\-]", "", text)
    if text in {"", "-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            normalized = text.replace(".", "").replace(",", ".")
        else:
            normalized = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) > 2:
            normalized = "".join(parts[:-1]) + "." + parts[-1]
        else:
            left, right = parts
            if len(right) == 3 and len(left.lstrip("-")) <= 3:
                normalized = left + right
            else:
                normalized = left + "." + right
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


def _cell_text(cell) -> str:
    return _clean_text(cell.get_text(" ", strip=True))


def _header_indexes(headers: list[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for idx, header in enumerate(headers):
        token = _normalize_token(header)
        if token in _RANK_HEADERS and "rank" not in indexes:
            indexes["rank"] = idx
        elif token in _NAME_HEADERS and "name" not in indexes:
            indexes["name"] = idx
        elif token in _CLUB_HEADERS and "club" not in indexes:
            indexes["club"] = idx
        elif token in _POINT_HEADERS and "points" not in indexes:
            indexes["points"] = idx
    return indexes


def _header_row(table):
    thead = table.find("thead")
    if thead:
        row = thead.find("tr")
        if row:
            return row
    return table.find("tr")


def _data_rows(table, header_row) -> list:
    rows = []
    for tbody in table.find_all("tbody", recursive=False):
        rows.extend(tbody.find_all("tr", recursive=False))
    if rows:
        return rows

    direct_rows = [row for row in table.find_all("tr", recursive=False) if row is not header_row]
    if direct_rows:
        return direct_rows

    return [row for row in table.find_all("tr") if row is not header_row]


def _parse_html_tables(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        header_row = _header_row(table)
        if not header_row:
            continue

        header_cells = header_row.find_all(["th", "td"], recursive=False)
        headers = [_cell_text(cell) for cell in header_cells]
        indexes = _header_indexes(headers)
        if not {"rank", "name", "points"}.issubset(indexes):
            continue

        min_cells = max(indexes.values()) + 1
        for row in _data_rows(table, header_row):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) < min_cells:
                continue

            rank = _parse_rank(_cell_text(cells[indexes["rank"]]))
            if rank is None:
                continue

            name = _cell_text(cells[indexes["name"]])
            if not name or _is_skip_text(name):
                continue

            club = None
            if "club" in indexes and indexes["club"] < len(cells):
                club = _cell_text(cells[indexes["club"]]) or None

            points = _parse_points(_cell_text(cells[indexes["points"]]))
            results.append({"rank": rank, "name": name, "club": club, "points": points})

    return results


def _split_delimited_line(line: str) -> list[str]:
    if "\t" in line:
        return [_clean_text(part) for part in line.split("\t")]
    if "|" in line:
        return [_clean_text(part) for part in line.split("|")]
    return []


def _parse_delimited_text(text: str) -> list[dict]:
    lines = [_clean_text(line) for line in text.splitlines()]
    rows = [_split_delimited_line(line) for line in lines if _split_delimited_line(line)]
    if not rows:
        return []

    indexes = _header_indexes(rows[0])
    if not {"rank", "name", "points"}.issubset(indexes):
        return []

    results: list[dict] = []
    min_cells = max(indexes.values()) + 1
    for cells in rows[1:]:
        if len(cells) < min_cells:
            continue
        rank = _parse_rank(cells[indexes["rank"]])
        if rank is None:
            continue
        name = cells[indexes["name"]]
        if not name or _is_skip_text(name):
            continue
        club = cells[indexes["club"]] or None if "club" in indexes and indexes["club"] < len(cells) else None
        points = _parse_points(cells[indexes["points"]])
        results.append({"rank": rank, "name": name, "club": club, "points": points})
    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Jamaica ranking content into rank/name/club/points rows."""
    if not html_or_text:
        return []

    html_rows = _parse_html_tables(html_or_text)
    if html_rows:
        return html_rows

    return _parse_delimited_text(html_or_text)


def _has_rankings_table(html: str) -> bool:
    soup = BeautifulSoup(html or "", "html.parser")
    for table in soup.find_all("table"):
        header_row = _header_row(table)
        if not header_row:
            continue
        headers = [_cell_text(cell) for cell in header_row.find_all(["th", "td"], recursive=False)]
        indexes = _header_indexes(headers)
        if {"rank", "name", "points"}.issubset(indexes):
            return True
    return False


def _looks_unscrapeable(html: str) -> bool:
    text = _clean_text(BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)).lower()
    if any(marker in text for marker in _NO_DATA_MARKERS | _BLOCKED_MARKERS):
        return True
    if re.search(r"<script\b", html or "", flags=re.IGNORECASE) and re.search(
        r"id=[\"'](?:root|app)[\"']", html or "", flags=re.IGNORECASE
    ):
        return True
    return False


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_ranking_url(weapon: str, gender: str, category: str) -> str:
    """Build the conventional Jamaica ranking URL checked for a combo."""
    path = f"/rankings/{_slug(category)}-{_slug(gender)}-{_slug(weapon)}/"
    return urljoin(BASE_URL, path)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Jamaica ranking page. Returns None on missing/blocked pages."""
    url = build_ranking_url(weapon, gender, category)
    try:
        response = federation_request(
            "get",
            url,
            headers=HEADERS,
            timeout=20,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code == 404:
        print(f"    No scrapeable rankings at {url} (HTTP 404)")
        return None
    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    if not _has_rankings_table(response.text):
        reason = "blocked/no-data page" if _looks_unscrapeable(response.text) else "no ranking table"
        print(f"    No scrapeable rankings at {getattr(response, 'url', url)} ({reason})")
        return None

    return response.text


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_jam").start()
    season = current_season()
    print(f"Jamaica federation rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    public_combos: list[str] = []
    failed_combos: list[dict] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            label = _combo_label(weapon, gender, category)
            url = build_ranking_url(weapon, gender, category)
            print(f"  {label}...")

            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                print(f"    No scrapeable rankings at {url}")
                total_failed += 1
                failed_combos.append({"combo": label, "url": url, "reason": "no public rankings"})
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(content)
            if not parsed:
                print("    No rows parsed")
                total_failed += 1
                failed_combos.append({"combo": label, "url": url, "reason": "no rows parsed"})
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
                    metadata={"source_url": url, "probe_format": DATA_FORMAT},
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Written {written} rows ({len(parsed)} parsed)")
            total_written += written
            public_combos.append(label)
            time.sleep(REQUEST_DELAY)

        summary = {
            "season": season,
            "combos": len(RANKING_COMBOS),
            "public_combos": public_combos,
            "failed_combos": failed_combos,
            "probed_urls": PROBED_URLS,
            "data_format": DATA_FORMAT,
        }
        set_state(SOURCE, "last_run", summary)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=summary,
        )
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}"
        )
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

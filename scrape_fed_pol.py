"""
scrape_fed_pol.py - Polish Fencing Federation (PZS) rankings scraper.

Probe results:
  - https://pzszerm.pl/ranking: 404
  - https://pzszerm.pl/klasyfikacje: 200, redirects to /zawody/klasyfikacje/
  - https://pzszerm.pl/rankingi: 404

Working index:
  https://pzszerm.pl/zawody/klasyfikacje/

Detail URL pattern discovered from the index:
  https://pzszerm.pl/zawody/klasyfikacje/klasyfikacja/?id={id}

Current public coverage:
  All 12 Senior/Junior Foil/Epee/Sabre Men/Women combos are public.

Table columns:
  Miejsce | Imię i Nazwisko | Rocznik | Klub | Suma punktów | ...
"""

import re
import time
import unicodedata
from datetime import UTC, datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "pol_fencing"
COUNTRY = "POL"
BASE_URL = "https://pzszerm.pl"
INDEX_URL = f"{BASE_URL}/zawody/klasyfikacje/"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl,en-US;q=0.9,en;q=0.8",
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

_ranking_url_cache: dict[tuple[str, str, str], str] | None = None
_TRANSIENT_HTTP_STATUSES = {429, 500, 502, 503, 504}
_POLISH_TRANSLITERATION = str.maketrans({
    "ą": "a",
    "ć": "c",
    "ę": "e",
    "ł": "l",
    "ń": "n",
    "ó": "o",
    "ś": "s",
    "ź": "z",
    "ż": "z",
    "Ą": "A",
    "Ć": "C",
    "Ę": "E",
    "Ł": "L",
    "Ń": "N",
    "Ó": "O",
    "Ś": "S",
    "Ź": "Z",
    "Ż": "Z",
})


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def _strip_accents(text: str) -> str:
    text = text.translate(_POLISH_TRANSLITERATION)
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def _normalize_key(text: str) -> str:
    text = _strip_accents(_clean_text(text).casefold())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _parse_rank(text: str) -> int | None:
    match = re.match(r"^\s*(\d+)\s*[\.)]?\s*$", text or "")
    if not match:
        return None
    return int(match.group(1))


def _parse_points(text: str) -> float | None:
    text = _clean_text(text)
    match = re.search(r"-?\d[\d\s.,]*", text)
    if not match:
        return None

    raw = match.group(0).replace(" ", "")
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")

    try:
        return float(raw)
    except ValueError:
        return None


def _column_map(headers: list[str]) -> dict[str, int] | None:
    normalized = [_normalize_key(h) for h in headers]
    columns: dict[str, int] = {}

    for idx, header in enumerate(normalized):
        if not header:
            continue
        if "rank" not in columns and header in {"miejsce", "pozycja", "lp", "lokata"}:
            columns["rank"] = idx
        elif "name" not in columns and (
            "imie i nazwisko" in header
            or "zawodnik" in header
            or "nazwisko i imie" in header
            or header == "nazwisko"
        ):
            columns["name"] = idx
        elif "club" not in columns and header == "klub":
            columns["club"] = idx
        elif "points" not in columns and (
            "suma punktow" in header
            or header == "punkty"
            or header == "pkt"
            or header.endswith(" punktow")
        ):
            columns["points"] = idx

    if {"rank", "name", "points"}.issubset(columns):
        return columns
    return None


def _row_cells(row) -> list[str]:
    cells = row.find_all(["td", "th"], recursive=False)
    if not cells:
        cells = row.find_all(["td", "th"])
    return [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]


def _is_skip_row(cells: list[str]) -> bool:
    row_text = _normalize_key(" ".join(cells))
    if not row_text:
        return True
    skip_tokens = {
        "dns",
        "dnf",
        "dq",
        "dsq",
        "razem",
        "podsumowanie",
        "brak danych",
    }
    if row_text in skip_tokens:
        return True
    return any(token in row_text.split() for token in {"dns", "dnf", "dq", "dsq"})


def _parse_rows(rows, header_index: int, columns: dict[str, int]) -> list[dict]:
    results = []
    required_indexes = [columns["rank"], columns["name"], columns["points"]]
    club_index = columns.get("club")

    for row in rows[header_index + 1:]:
        cells = _row_cells(row)
        if len(cells) <= max(required_indexes):
            continue
        if _is_skip_row(cells):
            continue

        rank = _parse_rank(cells[columns["rank"]])
        if rank is None:
            continue

        name = cells[columns["name"]].strip()
        if not name:
            continue

        club = None
        if club_index is not None and club_index < len(cells):
            club = cells[club_index].strip() or None

        results.append({
            "rank": rank,
            "name": name,
            "club": club,
            "points": _parse_points(cells[columns["points"]]),
        })

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse a PZS ranking page into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []

    parsed_rows: list[dict] = []
    for table in tables:
        rows = table.find_all("tr")
        for idx, row in enumerate(rows):
            cells = _row_cells(row)
            columns = _column_map(cells)
            if not columns:
                continue
            parsed_rows.extend(_parse_rows(rows, idx, columns))
            break

    return parsed_rows


def _combo_from_label(label: str) -> tuple[str, str, str] | None:
    normalized = _normalize_key(label)
    if not normalized or "juniorow mlodszych" in normalized:
        return None

    if "seniorow" in normalized or "senior" in normalized:
        category = "Senior"
    elif "juniorow" in normalized or "junior" in normalized:
        category = "Junior"
    else:
        return None

    if "floret" in normalized:
        weapon = "Foil"
    elif "szpada" in normalized:
        weapon = "Epee"
    elif "szabla" in normalized:
        weapon = "Sabre"
    else:
        return None

    # The gender appears in the weapon phrase after the dash:
    # "seniorów - floret kobiet", "juniorów - szpada mężczyzn".
    tail = _normalize_key(label.split("-", 1)[-1])
    if "kobiet" in tail:
        gender = "Women"
    elif "mezczyzn" in tail:
        gender = "Men"
    else:
        return None

    return weapon, gender, category


def _get_with_retry(url: str) -> requests.Response | None:
    last_error: Exception | None = None
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = federation_request("get", url, headers=HEADERS, timeout=25, allow_redirects=True)
            if response.status_code in _TRANSIENT_HTTP_STATUSES and attempt < max_attempts - 1:
                time.sleep(REQUEST_DELAY * (attempt + 1))
                continue
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_attempts - 1:
                time.sleep(REQUEST_DELAY * (attempt + 1))
    print(f"    Request error for {url}: {last_error}")
    return None


def discover_ranking_urls() -> dict[tuple[str, str, str], str]:
    """
    Discover current PZS ranking detail URLs from the public index page.

    The index includes current and older seasons. It lists the current season
    first, so the first URL seen for a combo is retained.
    """
    global _ranking_url_cache
    if _ranking_url_cache is not None:
        return _ranking_url_cache

    discovered: dict[tuple[str, str, str], str] = {}
    response = _get_with_retry(INDEX_URL)
    if not response or response.status_code != 200:
        status = response.status_code if response else "network error"
        print(f"    Could not fetch ranking index {INDEX_URL}: {status}")
        _ranking_url_cache = discovered
        return discovered

    soup = BeautifulSoup(response.text, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if "klasyfikacja?id=" not in href:
            continue

        label = _clean_text(link.get_text(" ", strip=True))
        combo = _combo_from_label(label)
        if not combo or combo in discovered:
            continue
        if combo not in RANKING_COMBOS:
            continue

        discovered[combo] = urljoin(INDEX_URL, href)

    _ranking_url_cache = discovered
    return discovered


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one PZS ranking page. Return None on missing URL, 404, or network error."""
    combo = (weapon, gender, category)
    url = discover_ranking_urls().get(combo)
    if not url:
        print(f"    No public ranking URL discovered for {weapon} {gender} {category}")
        return None

    response = _get_with_retry(url)
    if not response:
        return None
    if response.status_code == 200:
        return response.text

    print(f"    HTTP {response.status_code} for {url}")
    return None


def _fallback_current_season() -> str:
    now = datetime.now(UTC)
    return f"{now.year - 1}-{now.year}" if now.month < 7 else f"{now.year}-{now.year + 1}"


def _normalize_season_string(value) -> str:
    if isinstance(value, int):
        return f"{value - 1}-{value}"
    season = str(value).strip().replace("/", "-")
    if re.match(r"^\d{4}-\d{4}$", season):
        return season
    return _fallback_current_season()


def current_season() -> str:
    """Return the current FIE-style season string, preferring season_utils when present."""
    try:
        import season_utils
    except ImportError:
        return _fallback_current_season()

    if hasattr(season_utils, "current_season"):
        value = season_utils.current_season()
    elif hasattr(season_utils, "current_fie_season"):
        value = season_utils.current_fie_season()
    else:
        return _fallback_current_season()

    if hasattr(season_utils, "normalize_season"):
        return season_utils.normalize_season(value)
    if hasattr(season_utils, "season_to_string") and isinstance(value, int):
        return season_utils.season_to_string(value)
    return _normalize_season_string(value)


def main():
    run_log = ScraperRunLogger("scrape_fed_pol").start()
    season = current_season()
    print(f"PZS Poland rankings - season {season}")
    print(f"Ranking index: {INDEX_URL}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []

    try:
        discovered = discover_ranking_urls()
        print(f"Discovered {len(discovered)}/{len(RANKING_COMBOS)} public ranking combos")

        for weapon, gender, category in RANKING_COMBOS:
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")

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

            source_url = discovered.get((weapon, gender, category))
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
                    metadata={"source_url": source_url} if source_url else {},
                )
                for row in parsed
            ]

            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Parsed {len(parsed)} rows; written {written}")
            total_written += written
            time.sleep(REQUEST_DELAY)

        missing = len(RANKING_COMBOS) - len(discovered)
        total_skipped += max(missing, 0)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "index_url": INDEX_URL,
                "working_combos": len(discovered),
                "expected_combos": len(RANKING_COMBOS),
                "failed_combos": failed_combos,
            },
        )
        print(
            f"Done - written={total_written}, failed={total_failed}, "
            f"skipped={total_skipped}, combos={len(discovered)}/{len(RANKING_COMBOS)}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

"""
scrape_fed_swe.py — Swedish Fencing national rankings scraper.

Probe notes, 2026-06-01:
  - swefencing.se and www.swefencing.se did not resolve.
  - https://svenskfaktning.se/tavling/nationella-och-regionala-tavlingsserier/
    is the current federation page for "Nationell ranking och Masters".
  - The page links public Ophardt ranking HTML:
    https://fencing.ophardt.online/sv/search/rankings/3?season=2025
  - Request method: GET.
  - Response format: HTML tables. The federation page also publishes .xlsx
    support documents, but the public point standings are Ophardt HTML tables.
  - Public national Senior/U20 coverage found: Foil and Epee, Men and Women.
    National Sabre Senior/U20 cells were blank on the probed Ophardt page.

Ophardt table columns:
  Plats | Poäng | Överförda poäng | Namn | Nation | Klubb/Klubbar | Född
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "swe_fencing"
COUNTRY = "SWE"
BASE_URL = "https://fencing.ophardt.online/sv"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.7",
}

FEDERATION_RANKING_PAGE = (
    "https://svenskfaktning.se/tavling/nationella-och-regionala-tavlingsserier/"
)
RANKINGS_INDEX_URL = f"{BASE_URL}/search/rankings/3"

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

_STATIC_RANKING_URLS = {
    ("Foil", "Women", "Senior"): f"{BASE_URL}/search/rankings/show/21576",
    ("Epee", "Women", "Senior"): f"{BASE_URL}/search/rankings/show/21566",
    ("Foil", "Men", "Senior"): f"{BASE_URL}/search/rankings/show/21578",
    ("Epee", "Men", "Senior"): f"{BASE_URL}/search/rankings/show/21574",
    ("Foil", "Women", "Junior"): f"{BASE_URL}/search/rankings/show/21575",
    ("Epee", "Women", "Junior"): f"{BASE_URL}/search/rankings/show/21565",
    ("Foil", "Men", "Junior"): f"{BASE_URL}/search/rankings/show/21577",
    ("Epee", "Men", "Junior"): f"{BASE_URL}/search/rankings/show/21573",
}

_RANKING_URL_CACHE: dict[str, dict[tuple[str, str, str], str]] = {}

_SKIP_RANK_TOKENS = {
    "",
    "dns",
    "dq",
    "dnf",
    "dsq",
    "wd",
    "summa",
    "totalt",
    "total",
    "sammanlagt",
}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _normalize_header(value: str) -> str:
    value = _strip_accents(_normalize_text(value).lower())
    return re.sub(r"[^a-z0-9/ ]+", "", value)


def _clean_cell_text(cell) -> str:
    clone = BeautifulSoup(str(cell), "html.parser")
    for hidden in clone.select(".dropdown-menu, .modal, script, style"):
        hidden.decompose()
    return _normalize_text(clone.get_text(" ", strip=True))


def _parse_number(value: str) -> float | None:
    text = _normalize_text(value)
    if not text or _normalize_header(text) in _SKIP_RANK_TOKENS:
        return None
    text = text.replace("\xa0", "").replace(" ", "")
    text = re.sub(r"[^0-9,.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_rank(value: str) -> int | None:
    text = _normalize_header(value)
    if text in _SKIP_RANK_TOKENS:
        return None
    match = re.match(r"^(\d+)$", text)
    if not match:
        return None
    rank = int(match.group(1))
    return rank if rank > 0 else None


def _find_index(headers: list[str], names: set[str]) -> int | None:
    for index, header in enumerate(headers):
        normalized = _normalize_header(header)
        if any(name in normalized for name in names):
            return index
    return None


def _find_points_index(headers: list[str]) -> int | None:
    for index, header in enumerate(headers):
        normalized = _normalize_header(header)
        if ("poang" in normalized or "points" in normalized) and "overforda" not in normalized:
            return index
    return None


def _extract_table_rows(table) -> list[list[str]]:
    rows = []
    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        rows.append([_clean_cell_text(cell) for cell in cells])
    return rows


def _rows_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    ranked_tables = sorted(
        tables,
        key=lambda table: 0 if "rankingbody" in (table.get("class") or []) else 1,
    )

    for table in ranked_tables:
        rows = _extract_table_rows(table)
        if len(rows) < 2:
            continue

        header = rows[0]
        header_norm = [_normalize_header(cell) for cell in header]
        rank_index = _find_index(header, {"plats", "placering", "rank"})
        name_index = _find_index(header, {"namn", "name", "faktare", "idrottare"})
        club_index = _find_index(header, {"klubb", "klubb/klubbar", "forening", "club"})
        points_index = _find_points_index(header)
        if rank_index is None or name_index is None:
            continue
        if not any("poang" in item or "point" in item for item in header_norm):
            continue

        parsed = []
        for row in rows[1:]:
            max_index = max(
                rank_index,
                name_index,
                club_index if club_index is not None else 0,
                points_index if points_index is not None else 0,
            )
            if len(row) <= max_index:
                continue

            rank = _parse_rank(row[rank_index])
            if rank is None:
                continue

            name = _normalize_text(row[name_index])
            name = re.sub(r"\s+(Detaljer|Biografi|Details|Biography)\b.*$", "", name).strip()
            if not name or _normalize_header(name) in _SKIP_RANK_TOKENS:
                continue

            club = None
            if club_index is not None and row[club_index]:
                club = _normalize_text(row[club_index]) or None

            points = _parse_number(row[points_index]) if points_index is not None else None
            parsed.append({"rank": rank, "name": name, "club": club, "points": points})

        if parsed:
            return parsed

    return []


def _rows_from_text(text: str) -> list[dict]:
    lines = [_normalize_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    header: list[str] | None = None
    parsed_rows: list[list[str]] = []

    for line in lines:
        if "|" in line:
            cells = [_normalize_text(cell) for cell in line.split("|")]
        else:
            cells = [_normalize_text(cell) for cell in re.split(r"\s{2,}", line)]
        normalized_line = _normalize_header(" ".join(cells))
        if header is None:
            if (
                any(token in normalized_line for token in ("placering", "plats", "rank"))
                and any(token in normalized_line for token in ("namn", "name"))
                and any(token in normalized_line for token in ("poang", "point"))
            ):
                header = cells
            continue
        parsed_rows.append(cells)

    if not header:
        return []

    rank_index = _find_index(header, {"plats", "placering", "rank"})
    name_index = _find_index(header, {"namn", "name", "faktare", "idrottare"})
    club_index = _find_index(header, {"klubb", "klubb/klubbar", "forening", "club"})
    points_index = _find_points_index(header)
    if rank_index is None or name_index is None:
        return []

    parsed = []
    for row in parsed_rows:
        max_index = max(
            rank_index,
            name_index,
            club_index if club_index is not None else 0,
            points_index if points_index is not None else 0,
        )
        if len(row) <= max_index:
            continue
        rank = _parse_rank(row[rank_index])
        if rank is None:
            continue
        name = _normalize_text(row[name_index])
        if not name or _normalize_header(name) in _SKIP_RANK_TOKENS:
            continue
        club = _normalize_text(row[club_index]) if club_index is not None else None
        points = _parse_number(row[points_index]) if points_index is not None else None
        parsed.append({"rank": rank, "name": name, "club": club or None, "points": points})
    return parsed


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Swedish ranking rows into rank/name/club/points dictionaries."""
    if not html_or_text or not html_or_text.strip():
        return []

    if "<table" in html_or_text.lower():
        rows = _rows_from_html(html_or_text)
        if rows:
            return rows
    return _rows_from_text(html_or_text)


def extract_ranking_date(html_or_text: str) -> str | None:
    """Return Ophardt's visible 'Beräknad den' timestamp when present."""
    if not html_or_text or "<table" not in html_or_text.lower():
        return None
    soup = BeautifulSoup(html_or_text, "html.parser")
    for table in soup.find_all("table"):
        rows = _extract_table_rows(table)
        for index, row in enumerate(rows):
            normalized = [_normalize_header(cell) for cell in row]
            if "beraknad den" not in normalized:
                continue
            date_index = normalized.index("beraknad den")
            for candidate in rows[index + 1:]:
                if len(candidate) > date_index and candidate[date_index]:
                    return candidate[date_index]
    return None


def _category_to_ophardt(category: str) -> str:
    return "U20" if category.lower() == "junior" else category


def _discover_ranking_urls(season: str) -> dict[tuple[str, str, str], str]:
    if season in _RANKING_URL_CACHE:
        return _RANKING_URL_CACHE[season]

    discovered: dict[tuple[str, str, str], str] = {}
    start_year = season.split("-", 1)[0]
    try:
        response = requests.get(
            RANKINGS_INDEX_URL,
            params={"season": start_year},
            headers=HEADERS,
            timeout=20,
            allow_redirects=True,
        )
        if response.status_code != 200:
            _RANKING_URL_CACHE[season] = discovered
            return discovered
    except requests.RequestException as exc:
        print(f"    Could not discover Sweden ranking URLs: {exc}")
        _RANKING_URL_CACHE[season] = discovered
        return discovered

    soup = BeautifulSoup(response.text, "html.parser")
    heading = soup.find(
        lambda tag: tag.name in {"h1", "h2", "h3", "h4"}
        and "nationell ranking" in _normalize_header(tag.get_text(" ", strip=True))
    )
    table = heading.find_next("table") if heading else None
    if table is None:
        _RANKING_URL_CACHE[season] = discovered
        return discovered

    slot_order = [
        ("Foil", "Women"),
        ("Sabre", "Women"),
        ("Epee", "Women"),
        ("Foil", "Men"),
        ("Sabre", "Men"),
        ("Epee", "Men"),
    ]
    category_map = {"Seniorer": "Senior", "U20": "Junior"}

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        raw_category = _clean_cell_text(cells[0])
        category = category_map.get(raw_category)
        if not category:
            continue
        for cell, (weapon, gender) in zip(cells[1:], slot_order):
            link = cell.find("a", href=True)
            if not link:
                continue
            discovered[(weapon, gender, category)] = urljoin(BASE_URL, link["href"])

    _RANKING_URL_CACHE[season] = discovered
    return discovered


def _ranking_url_for(
    weapon: str,
    gender: str,
    category: str,
    season: str | None = None,
) -> str | None:
    season = season or current_season()
    key = (weapon, gender, category)
    discovered = _discover_ranking_urls(season)
    return discovered.get(key) or _STATIC_RANKING_URLS.get(key)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Swedish ranking page, returning None for missing or failed pages."""
    url = _ranking_url_for(weapon, gender, category)
    if not url:
        print(f"    No public Sweden national ranking URL for {weapon} {gender} {category}")
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code == 200:
        return response.text
    print(f"    HTTP {response.status_code} for {url}")
    return None


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY."""
    now = datetime.now(timezone.utc)
    end_year = now.year if now.month < 7 else now.year + 1
    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "normalize_season"):
            normalized = season_utils.normalize_season(end_year)
            if isinstance(normalized, str):
                return normalized
        if hasattr(season_utils, "season_to_string"):
            return season_utils.season_to_string(end_year)
    except Exception:
        pass

    return f"{end_year - 1}-{end_year}"


def main():
    run_log = ScraperRunLogger("scrape_fed_swe").start()
    season = current_season()
    print(f"Swedish Fencing rankings — season {season}")
    print(f"Federation ranking page: {FEDERATION_RANKING_PAGE}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos = []
    skipped_combos = []
    working_combos = 0

    try:
        for weapon, gender, category in RANKING_COMBOS:
            combo_label = f"{weapon} {gender} {category}"
            url = _ranking_url_for(weapon, gender, category, season=season)
            if not url:
                print(f"  {combo_label}: skipped, no public national ranking URL")
                total_skipped += 1
                skipped_combos.append(combo_label)
                time.sleep(REQUEST_DELAY)
                continue

            print(f"  {combo_label}: {url}")
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

            ranking_date = extract_ranking_date(content)
            metadata = {"ranking_url": url}
            if ranking_date:
                metadata["ranking_date"] = ranking_date

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
                    metadata=metadata,
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Parsed {len(parsed)} rows, written {written}")
            total_written += written
            working_combos += 1
            time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "working_combos": working_combos,
                "total_combos": len(RANKING_COMBOS),
                "failed_combos": failed_combos,
                "skipped_combos": skipped_combos,
                "source_format": "html",
                "federation_page": FEDERATION_RANKING_PAGE,
            },
        )
        print(
            "Done — "
            f"working={working_combos}/{len(RANKING_COMBOS)}, "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

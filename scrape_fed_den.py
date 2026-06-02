"""
scrape_fed_den.py — Danish Fencing Federation national rankings scraper.

Probe findings (2026-06-01):
  - https://fencing.dk/ranglister, /ranking, and /resultater/rangliste redirect
    to trekanten.org and return 404.
  - The current DFF rankings page is:
      https://www.faegtning.dk/staevner/ranglister/
    and it links to the public Ophardt Online index:
      https://fencing.ophardt.online/en/search/rankings/10
  - Request method: GET. Response format: server-rendered HTML.
  - Public coverage: Senior and U20 (mapped to Junior) for Epee/Foil/Sabre,
    Men/Women. Junior Women Sabre currently has a public page with zero rows.

Ophardt ranking pages contain a metadata table followed by a ranking table:
  Rank | Points | T-P | Name | Nation | Clubs | YOB | per-event columns...
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "den_fencing"
COUNTRY = "DEN"
BASE_URL = "https://fencing.ophardt.online/en/search/rankings"
FEDERATION_RANKINGS_URL = "https://www.faegtning.dk/staevner/ranglister/"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da,en-US;q=0.9,en;q=0.8",
    "Referer": FEDERATION_RANKINGS_URL,
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

_INDEX_URL = f"{BASE_URL}/10"
_OPHARDT_LINK_ORDER = [
    ("Epee", "Men"),
    ("Foil", "Men"),
    ("Sabre", "Men"),
    ("Epee", "Women"),
    ("Foil", "Women"),
    ("Sabre", "Women"),
]
_DISCOVERED_URLS: dict[tuple[str, str, str], str] | None = None
_FETCH_REASONS: dict[tuple[str, str, str], str] = {}


def _fallback_current_season() -> str:
    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def current_season() -> str:
    """Return the active season as YYYY-YYYY, normalizing via season_utils when present."""
    season = _fallback_current_season()
    try:
        import season_utils  # type: ignore
    except Exception:
        return season

    try:
        if hasattr(season_utils, "normalize_season"):
            return season_utils.normalize_season(season)
        return str(season)
    except Exception:
        return season


def _normalized_header(text: str) -> str:
    return re.sub(r"[^a-zæøå0-9]+", " ", text.lower()).strip()


def _matches_header(text: str, aliases: set[str]) -> bool:
    normalized = _normalized_header(text)
    tokens = set(normalized.split())
    return normalized in aliases or bool(tokens & aliases)


def _header_indices(headers: list[str]) -> dict[str, int]:
    aliases = {
        "rank": {"rank", "rang", "place", "platz", "plads", "placering"},
        "name": {"name", "navn", "fencer", "athlete"},
        "club": {"club", "clubs", "klub", "klubber", "forening", "vereine"},
        "points": {"point", "points", "punkte"},
    }
    indices: dict[str, int] = {}
    for index, header in enumerate(headers):
        for key, key_aliases in aliases.items():
            if key not in indices and _matches_header(header, key_aliases):
                indices[key] = index
    return indices


def _find_ranking_table(soup: BeautifulSoup) -> tuple[Any | None, dict[str, int]]:
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            headers = [cell.get_text(" ", strip=True) for cell in cells]
            indices = _header_indices(headers)
            if "rank" in indices and "name" in indices and "points" in indices:
                if "club" not in indices and indices.get("name") == 3:
                    indices["club"] = 5
                return table, indices
    return None, {}


def _top_level_rows(table: Any) -> list[Any]:
    tbodies = table.find_all("tbody", recursive=False)
    if tbodies:
        rows: list[Any] = []
        for tbody in tbodies:
            rows.extend(tbody.find_all("tr", recursive=False))
        return rows
    return table.find_all("tr", recursive=False)


def _parse_rank(text: str) -> int | None:
    raw = text.replace("\xa0", " ").strip()
    if re.search(r"\b(dns|dnf|dq|dsq|disqualified|diskvalificeret|total|summary|i alt)\b", raw, re.I):
        return None
    match = re.match(r"^\s*(\d+)(?:[.)])?\s*$", raw)
    return int(match.group(1)) if match else None


def _parse_points(text: str) -> float | None:
    raw = text.replace("\xa0", " ").strip()
    if not raw or re.search(r"\b(dns|dnf|dq|dsq)\b", raw, re.I):
        return None
    raw = re.sub(r"[^\d,.\-]", "", raw)
    if not raw or raw in {"-", ",", "."}:
        return None
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


def _clean_name(cell: Any) -> str:
    for link in cell.find_all("a"):
        classes = link.get("class") or []
        if "dropdown-toggle" in classes:
            text = link.get_text(" ", strip=True)
            if text:
                return re.sub(r"\s+", " ", text).strip()

    text = cell.get_text(" ", strip=True)
    text = re.split(
        r"\s+(?:Details?|Detaljer|Detail|Biography|Biographie|Biografi|"
        r"Rank\s+Points|Rang\s+Point|Plads\s+Point|×)\b",
        text,
        maxsplit=1,
        flags=re.I,
    )[0]
    return re.sub(r"\s+", " ", text).strip()


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Danish/Ophardt ranking HTML into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    table, indices = _find_ranking_table(soup)
    if table is None:
        return []

    rank_idx = indices["rank"]
    name_idx = indices["name"]
    points_idx = indices["points"]
    club_idx = indices.get("club")

    results = []
    for row in _top_level_rows(table):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) <= max(rank_idx, name_idx, points_idx):
            continue

        rank = _parse_rank(cells[rank_idx].get_text(" ", strip=True))
        if rank is None:
            continue

        name = _clean_name(cells[name_idx])
        if not name:
            continue

        club = None
        if club_idx is not None and len(cells) > club_idx:
            club = cells[club_idx].get_text(" ", strip=True) or None

        points = _parse_points(cells[points_idx].get_text(" ", strip=True))

        results.append({
            "rank": rank,
            "name": name,
            "club": club,
            "points": points,
        })

    return results


def discover_ranking_urls() -> dict[tuple[str, str, str], str]:
    """Discover current public Ophardt ranking URLs from the Danish index."""
    global _DISCOVERED_URLS
    if _DISCOVERED_URLS is not None:
        return dict(_DISCOVERED_URLS)

    discovered: dict[tuple[str, str, str], str] = {}
    try:
        response = federation_request("get", _INDEX_URL, headers=HEADERS, timeout=20, allow_redirects=True)
        if response.status_code != 200:
            print(f"  Ranking index HTTP {response.status_code}: {_INDEX_URL}")
            _DISCOVERED_URLS = discovered
            return discovered
    except requests.RequestException as exc:
        print(f"  Ranking index request failed: {exc}")
        _DISCOVERED_URLS = discovered
        return discovered

    soup = BeautifulSoup(response.text, "html.parser")
    for row in soup.find_all("tr"):
        row_text = row.get_text(" ", strip=True)
        if re.search(r"\bSenior\b", row_text, re.I):
            category = "Senior"
        elif re.search(r"\b(U20|Junior)\b", row_text, re.I):
            category = "Junior"
        else:
            continue

        links = [
            urljoin(response.url, link["href"])
            for link in row.find_all("a", href=True)
            if "/search/rankings/show/" in link.get("href", "")
        ]
        if len(links) < 6:
            continue

        for (weapon, gender), url in zip(_OPHARDT_LINK_ORDER, links[:6]):
            discovered[(weapon, gender, category)] = url

    _DISCOVERED_URLS = discovered
    return dict(discovered)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public Danish ranking page. Returns None on missing/failed fetch."""
    combo = (weapon, gender, category)
    url = discover_ranking_urls().get(combo)
    if not url:
        _FETCH_REASONS[combo] = "missing public ranking URL"
        print(f"    No public ranking URL discovered for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
        if response.status_code == 200:
            return response.text
        _FETCH_REASONS[combo] = f"HTTP {response.status_code}: {url}"
        print(f"    HTTP {response.status_code} for {url}")
        return None
    except requests.RequestException as exc:
        _FETCH_REASONS[combo] = f"network error: {exc}"
        print(f"    Request error for {url}: {exc}")
        return None


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_den").start()
    season = current_season()
    print(f"DFF Denmark rankings — season {season}")
    print(f"  Federation page: {FEDERATION_RANKINGS_URL}")
    print(f"  Ophardt index: {_INDEX_URL}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[dict[str, str]] = []
    skipped_combos: list[dict[str, str]] = []

    discovered = discover_ranking_urls()
    print(f"  Discovered {len(discovered)}/{len(RANKING_COMBOS)} ranking URLs")

    for weapon, gender, category in RANKING_COMBOS:
        combo = (weapon, gender, category)
        print(f"  {weapon} {gender} {category}...")
        html = fetch_rankings_page(weapon, gender, category)
        reason = _FETCH_REASONS.pop(combo, None)

        if not html:
            if reason == "missing public ranking URL":
                total_skipped += 1
                skipped_combos.append({"combo": " ".join(combo), "reason": reason})
            else:
                total_failed += 1
                failed_combos.append({"combo": " ".join(combo), "reason": reason or "fetch failed"})
            time.sleep(REQUEST_DELAY)
            continue

        parsed = parse_rankings_table(html)
        if not parsed:
            reason = "public page has no ranking rows"
            print(f"    Skipped: {reason}")
            total_skipped += 1
            skipped_combos.append({"combo": " ".join(combo), "reason": reason})
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
            )
            for row in parsed
        ]
        written = write_rankings(rows, source=SOURCE, season=season)
        print(f"    Written {written} rows ({len(parsed)} parsed)")
        total_written += written
        time.sleep(REQUEST_DELAY)

    metadata = {
        "season": season,
        "country": COUNTRY,
        "source": SOURCE,
        "federation_url": FEDERATION_RANKINGS_URL,
        "index_url": _INDEX_URL,
        "available_combos": len(discovered),
        "expected_combos": len(RANKING_COMBOS),
        "failed_combos": failed_combos,
        "skipped_combos": skipped_combos,
    }
    set_state(SOURCE, "last_run", metadata)
    run_log.complete(written=total_written, failed=total_failed, skipped=total_skipped, metadata=metadata)
    print(f"Done — written={total_written}, failed={total_failed}, skipped={total_skipped}")


if __name__ == "__main__":
    main()

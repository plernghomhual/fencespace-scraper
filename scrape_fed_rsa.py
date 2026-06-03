"""
scrape_fed_rsa.py - South Africa federation rankings scraper.

Probe evidence, 2026-06-02:
  - User-specified probe domain `https://safencing.co.za/` did not resolve from
    the sandboxed probe.
  - Active public federation page found by search/open probe:
      https://safencer.co.za/rankings/
  - Request method: GET
  - Response format: server-rendered HTML
  - Public coverage: Senior and Junior for Foil/Epee/Sabre, Men/Women.
  - The federation page links each combo to public Ophardt ranking detail pages.

The Ophardt ranking IDs are season/site data, so this scraper discovers links
from the public federation page instead of hard-coding detail URLs.
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
from scraper_state import get_state, set_state

SOURCE = "rsa_fencing"
COUNTRY = "South Africa"
BASE_URL = "https://safencer.co.za/rankings/"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-ZA,en;q=0.9",
    "Referer": "https://safencer.co.za/",
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

_RANK_HEADERS = {"rank", "ranking", "position", "pos", "place", "placing"}
_NAME_HEADERS = {"name", "fencer", "athlete", "competitor"}
_CLUB_HEADERS = {"club", "clubs", "school", "team"}
_POINT_HEADERS = {"points", "point", "pts", "score", "totalpoints", "rankingpoints"}
_STATUS_SKIP_VALUES = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "ret",
    "bye",
}
_SUMMARY_SKIP_PREFIXES = {
    "total",
    "totals",
    "summary",
    "subtotal",
    "noresult",
    "noranking",
}
_UNUSABLE_PAGE_MARKERS = {
    "please sign in",
    "sign in to continue",
    "enable javascript",
    "requires javascript",
    "javascript is required",
    "access denied",
    "forbidden",
    "cloudflare",
}
_DETAIL_LINK_TEXTS = {"details", "detail", "biography", "bio"}
_RANKING_LINK_CACHE: dict[tuple[str, str, str], str] = {}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _normalize_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(value))
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def _header_indexes(headers: list[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for index, header in enumerate(headers):
        token = _normalize_token(header)
        if "rank" not in indexes and token in _RANK_HEADERS:
            indexes["rank"] = index
        elif "name" not in indexes and token in _NAME_HEADERS:
            indexes["name"] = index
        elif "club" not in indexes and token in _CLUB_HEADERS:
            indexes["club"] = index
        elif "points" not in indexes and token in _POINT_HEADERS:
            indexes["points"] = index
    return indexes


def _is_skip_text(value: str) -> bool:
    token = _normalize_token(value)
    if token in _STATUS_SKIP_VALUES:
        return True
    return any(token.startswith(prefix) for prefix in _SUMMARY_SKIP_PREFIXES)


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
    text = _clean_text(value)
    if not text or _is_skip_text(text):
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
        pieces = text.split(",")
        if len(pieces) > 2:
            normalized = "".join(pieces[:-1]) + "." + pieces[-1]
        else:
            left, right = pieces
            if len(right) == 3 and left.lstrip("-").isdigit() and right.isdigit():
                normalized = left + right
            else:
                normalized = left + "." + right
    elif "." in text:
        pieces = text.split(".")
        if len(pieces) > 2 and all(len(piece) == 3 for piece in pieces[1:]):
            normalized = "".join(pieces)
        elif len(pieces) == 2 and len(pieces[1]) == 3 and len(pieces[0].lstrip("-")) <= 3:
            normalized = "".join(pieces)
        else:
            normalized = text
    else:
        normalized = text

    try:
        return float(normalized)
    except ValueError:
        return None


def _cell_text(cell, *, prefer_name: bool = False) -> str:
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

    link_texts = [
        _clean_text(link.get_text(" ", strip=True))
        for link in clone.find_all("a")
        if _clean_text(link.get_text(" ", strip=True)).lower() not in _DETAIL_LINK_TEXTS
    ]
    if prefer_name and link_texts:
        return link_texts[0]

    return _clean_text(clone.get_text(" ", strip=True))


def _header_row(table):
    thead = table.find("thead")
    if thead:
        row = thead.find("tr")
        if row:
            return row
    return table.find("tr")


def _data_rows(table, header_row) -> list:
    classes = table.get("class") or []
    if "rankingbody" in classes:
        return [row for row in table.find_all("tr", recursive=False) if row is not header_row]

    rows = []
    for tbody in table.find_all("tbody", recursive=False):
        rows.extend(tbody.find_all("tr", recursive=False))
    if rows:
        return rows

    direct_rows = [row for row in table.find_all("tr", recursive=False) if row is not header_row]
    if direct_rows:
        return direct_rows

    return [row for row in table.find_all("tr") if row is not header_row]


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse RSA/Ophardt ranking HTML into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
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

            name = _cell_text(cells[indexes["name"]], prefer_name=True)
            if not name or _is_skip_text(name):
                continue

            club = None
            if "club" in indexes and indexes["club"] < len(cells):
                club = _cell_text(cells[indexes["club"]]) or None

            points = _parse_points(_cell_text(cells[indexes["points"]]))
            results.append({"rank": rank, "name": name, "club": club, "points": points})

    return results


def _combo_from_label(label: str) -> tuple[str, str, str] | None:
    text = _clean_text(label).lower().replace("women's", "womens").replace("men's", "mens")
    token = _normalize_token(text)

    if "junior" in token or "u20" in token:
        category = "Junior"
    elif "senior" in token:
        category = "Senior"
    else:
        return None

    if "women" in token or "womens" in token or "female" in token:
        gender = "Women"
    elif "mens" in token or re.search(r"\bmen\b", text) or "male" in token:
        gender = "Men"
    else:
        return None

    if "epee" in token or "épée" in text:
        weapon = "Epee"
    elif "foil" in token:
        weapon = "Foil"
    elif "sabre" in token or "saber" in token:
        weapon = "Sabre"
    else:
        return None

    return weapon, gender, category


def _extract_ranking_links(html: str, *, base_url: str = BASE_URL) -> dict[tuple[str, str, str], str]:
    """Extract combo -> Ophardt detail URL links from the public FFSA rankings page."""
    soup = BeautifulSoup(html or "", "html.parser")
    links: dict[tuple[str, str, str], str] = {}

    for anchor in soup.find_all("a", href=True):
        anchor_text = _clean_text(anchor.get_text(" ", strip=True)).lower()
        href = anchor["href"]
        if "check rankings" not in anchor_text and "rankings" not in href and "show-ranking" not in href:
            continue

        candidates: list[str] = []
        heading = anchor.find_previous(["h1", "h2", "h3", "h4", "h5"])
        if heading:
            candidates.append(heading.get_text(" ", strip=True))
        parent = anchor.find_parent()
        if parent:
            candidates.append(parent.get_text(" ", strip=True))
        candidates.append(anchor.get_text(" ", strip=True))

        for candidate in candidates:
            combo = _combo_from_label(candidate)
            if combo:
                links[combo] = urljoin(base_url, href)
                break

    return links


def _is_unusable_page(html: str) -> bool:
    if not html:
        return True
    soup = BeautifulSoup(html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True)).lower()
    if any(marker in text for marker in _UNUSABLE_PAGE_MARKERS):
        return True
    if soup.find("table"):
        return False

    login_fields = soup.find_all("input", attrs={"name": re.compile(r"(login|username|password)", re.I)})
    password_fields = soup.find_all("input", attrs={"type": re.compile(r"password", re.I)})
    return bool(login_fields or password_fields)


def _discover_ranking_links() -> dict[tuple[str, str, str], str]:
    if _RANKING_LINK_CACHE:
        return dict(_RANKING_LINK_CACHE)

    try:
        response = federation_request(
            "get",
            BASE_URL,
            headers=HEADERS,
            timeout=25,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        print(f"    Ranking index request error for {BASE_URL}: {exc}")
        return {}

    if response.status_code != 200:
        print(f"    Ranking index HTTP {response.status_code} for {BASE_URL}")
        return {}

    if _is_unusable_page(response.text):
        print(f"    No scrapeable rankings at {response.url}")
        return {}

    links = _extract_ranking_links(response.text, base_url=response.url)
    if not links:
        print(f"    No scrapeable rankings at {response.url}")
    _RANKING_LINK_CACHE.update(links)
    return dict(_RANKING_LINK_CACHE)


def ranking_url_for(weapon: str, gender: str, category: str) -> str | None:
    return _discover_ranking_links().get((weapon, gender, category))


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one public RSA ranking page. Return None on 404/network/login/JS failures."""
    url = ranking_url_for(weapon, gender, category)
    if not url:
        print(f"    No public ranking link for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request(
            "get",
            url,
            headers=HEADERS,
            timeout=25,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        print(f"    Ranking request error for {url}: {exc}")
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    if _is_unusable_page(response.text):
        print(f"    No scrapeable rankings at {response.url}")
        return None

    return response.text


def current_season() -> str:
    """Return the active fencing season as YYYY-YYYY, using season_utils when available."""
    now = datetime.now(timezone.utc)
    season_end_year = now.year if now.month < 7 else now.year + 1

    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "normalize_season"):
            return season_utils.normalize_season(season_end_year)
        if hasattr(season_utils, "season_to_string"):
            return season_utils.season_to_string(season_end_year)
    except Exception:
        pass

    return f"{season_end_year - 1:04d}-{season_end_year:04d}"


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main():
    run_log = ScraperRunLogger("scrape_fed_rsa").start()
    season = current_season()
    previous_run = get_state(SOURCE, "last_run")
    print(f"South Africa federation rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos: list[str] = []
    failed_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            label = _combo_label(weapon, gender, category)
            print(f"  {label}...")

            html = fetch_rankings_page(weapon, gender, category)
            source_url = _RANKING_LINK_CACHE.get((weapon, gender, category))
            if not html:
                total_failed += 1
                failed_combos.append(label)
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
                    metadata={
                        "source_url": source_url,
                        "country_page": BASE_URL,
                        "data_format": "html",
                    },
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Written {written} rows ({len(parsed)} parsed)")
            total_written += written
            working_combos.append(label)
            time.sleep(REQUEST_DELAY)

        summary = {
            "season": season,
            "combos_total": len(RANKING_COMBOS),
            "combos_working": len(working_combos),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
            "source_page": BASE_URL,
            "data_format": "html",
            "previous_run_seen": bool(previous_run),
        }
        set_state(SOURCE, "last_run", summary)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=summary,
        )
        print(
            f"Done - written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"combos_working={len(working_combos)}/{len(RANKING_COMBOS)}"
        )
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

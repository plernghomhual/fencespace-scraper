"""
scrape_fed_aut.py — Austrian Fencing Federation (ÖFV) rankings scraper.

Probe notes (2026-06-01):
  - https://fencing.at redirects to https://www.fechten.at, a KAC club site.
    Requested paths (/rangliste, /ranglisten, /leistungssport/ranglisten,
    /ranking) returned WordPress 404 pages there.
  - Public federation rankings are on https://www.oefv.com:
    https://www.oefv.com/de/intern:13/ranglisten-saison-2025-2026
  - Request method: POST form fields search[typ], search[waffen],
    search[altersklasse]. Response format: server-rendered HTML table.
  - Public combos found: Senior, Junior, and Cadet for Foil/Epee/Sabre,
    Men/Women.

Table columns:
  Rang | OEFV-Lizenznummer | Nachname | Vorname | Club | Punkte | ...
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "aut_fencing"
COUNTRY = "AUT"
BASE_URL = "https://www.oefv.com"
PROBED_RANKINGS_URL = f"{BASE_URL}/de/intern:13/ranglisten-saison-2025-2026"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/de",
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
    ("Foil", "Men", "Cadet"),
    ("Foil", "Women", "Cadet"),
    ("Epee", "Men", "Cadet"),
    ("Epee", "Women", "Cadet"),
    ("Sabre", "Men", "Cadet"),
    ("Sabre", "Women", "Cadet"),
]

_GENDER_FORM_VALUES = {"Men": "Herren", "Women": "Damen"}
_WEAPON_FORM_VALUES = {"Foil": "Florett", "Epee": "Degen", "Sabre": "Sabel"}
_CATEGORY_FORM_VALUES = {
    "Senior": "Allgemeine Klasse",
    "Junior": "Junioren",
    "Cadet": "Kadetten",
}

_SKIP_ROW_RE = re.compile(r"\b(DNS|DNF|DQ|DSQ|DISQ)\b|disqualifiziert", re.IGNORECASE)
_RANKINGS_URL_CACHE: str | None = None


def _fallback_current_season() -> str:
    now = datetime.now(UTC)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def _season_to_range(value: object) -> str:
    text = str(value).strip().replace("/", "-")
    if re.fullmatch(r"\d{4}-\d{4}", text):
        return text
    if re.fullmatch(r"\d{4}", text):
        end_year = int(text)
        return f"{end_year - 1}-{end_year}"
    return _fallback_current_season()


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY."""
    fallback = _fallback_current_season()
    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "current_season"):
            season = season_utils.current_season()
        else:
            season = fallback

        if hasattr(season_utils, "normalize_season"):
            return season_utils.normalize_season(season)
        if hasattr(season_utils, "season_to_string") and not isinstance(season, str):
            return season_utils.season_to_string(season)
        return _season_to_range(season)
    except Exception:
        return fallback


def _rankings_url(season: str | None = None) -> str:
    season_slug = (season or current_season()).replace("/", "-")
    return f"{BASE_URL}/de/intern:13/ranglisten-saison-{season_slug}"


def _unique_urls(*urls: str | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _header_key(value: str) -> str:
    value = _clean_text(value).lower()
    value = value.replace("ö", "oe").replace("ä", "ae").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "", value)


def _parse_rank(value: str) -> int | None:
    match = re.match(r"^\s*(\d+)\s*[\.)]?\s*$", value)
    return int(match.group(1)) if match else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    text = re.sub(r"[^0-9,.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")

    try:
        return float(text)
    except ValueError:
        return None


def _column_indexes(headers: list[str]) -> dict[str, int | None]:
    keys = [_header_key(header) for header in headers]

    def first(*names: str) -> int | None:
        for name in names:
            if name in keys:
                return keys.index(name)
        return None

    return {
        "rank": first("rang", "platz", "rank"),
        "name": first("name", "fencer", "fechter", "fechterin"),
        "last_name": first("nachname", "familienname", "lastname"),
        "first_name": first("vorname", "firstname"),
        "club": first("club", "verein", "vereine", "klub"),
        "points": first("punkte", "points", "gesamtpunkte"),
    }


def _find_rankings_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        header_cells = table.find_all("th")
        if not header_cells:
            first_row = table.find("tr")
            header_cells = first_row.find_all(["th", "td"], recursive=False) if first_row else []
        header_text = " ".join(_clean_text(cell.get_text(" ", strip=True)) for cell in header_cells)
        header_key = _header_key(header_text)
        if ("rang" in header_key or "platz" in header_key) and "punkte" in header_key:
            return table
    return None


def _has_rankings_table(html_or_text: str) -> bool:
    if not html_or_text or not html_or_text.strip():
        return False
    soup = BeautifulSoup(html_or_text, "html.parser")
    return _find_rankings_table(soup) is not None


def _discover_latest_rankings_url() -> str | None:
    """Find the latest public ÖFV season ranking URL linked from the home page."""
    try:
        response = federation_request("get", f"{BASE_URL}/de", headers=HEADERS, timeout=20, allow_redirects=True)
        if response.status_code != 200:
            return None
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    candidates: list[tuple[int, int, str]] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        match = re.search(r"ranglisten-saison-(\d{4})-(\d{4})", href)
        if not match:
            continue
        start_year, end_year = int(match.group(1)), int(match.group(2))
        if href.startswith("http"):
            url = href
        else:
            url = BASE_URL + href
        candidates.append((end_year, start_year, url))

    if not candidates:
        return None
    return sorted(candidates)[-1][2]


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse an ÖFV rankings HTML table.

    Returns rows with keys: rank, name, club, points.
    """
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    table = _find_rankings_table(soup)
    if not table:
        return []

    header_row = table.find("tr")
    if not header_row:
        return []

    headers = [_clean_text(cell.get_text(" ", strip=True)) for cell in header_row.find_all(["th", "td"])]
    columns = _column_indexes(headers)

    rank_idx = columns["rank"] if columns["rank"] is not None else 0
    points_idx = columns["points"] if columns["points"] is not None else 5
    club_idx = columns["club"] if columns["club"] is not None else 4
    name_idx = columns["name"]
    last_name_idx = columns["last_name"]
    first_name_idx = columns["first_name"]

    tbody = table.find("tbody") or table
    rows = tbody.find_all("tr", recursive=False)
    results: list[dict] = []

    for row in rows:
        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            continue

        values = [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]
        row_text = " ".join(values)
        if _SKIP_ROW_RE.search(row_text):
            continue
        if max(rank_idx, points_idx, club_idx) >= len(values):
            continue

        rank = _parse_rank(values[rank_idx])
        if rank is None:
            continue

        if last_name_idx is not None and first_name_idx is not None:
            if max(last_name_idx, first_name_idx) >= len(values):
                continue
            name = _clean_text(f"{values[last_name_idx]} {values[first_name_idx]}")
        elif name_idx is not None and name_idx < len(values):
            name = _clean_text(values[name_idx])
        else:
            continue

        if not name:
            continue

        club = values[club_idx] or None
        points = _parse_points(values[points_idx])

        results.append({
            "rank": rank,
            "name": name,
            "club": club,
            "points": points,
        })

    return results


def _ranking_payload(weapon: str, gender: str, category: str) -> dict[str, str] | None:
    try:
        return {
            "search[typ]": _GENDER_FORM_VALUES[gender],
            "search[waffen]": _WEAPON_FORM_VALUES[weapon],
            "search[altersklasse]": _CATEGORY_FORM_VALUES[category],
            "anzeigen": "anzeigen",
        }
    except KeyError:
        return None


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one ÖFV ranking combo as server-rendered HTML."""
    global _RANKINGS_URL_CACHE

    payload = _ranking_payload(weapon, gender, category)
    if not payload:
        print(f"    Unsupported combo: {weapon} {gender} {category}")
        return None

    discovered_url = None
    for url in _unique_urls(_RANKINGS_URL_CACHE, _rankings_url(), PROBED_RANKINGS_URL):
        headers = dict(HEADERS)
        headers["Referer"] = url
        try:
            response = federation_request("post",
                url,
                data=payload,
                headers=headers,
                timeout=20,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            print(f"    Request error for {url}: {exc}")
            continue

        if response.status_code == 404:
            print(f"    HTTP 404 for {url}")
            continue
        if response.status_code != 200:
            print(f"    HTTP {response.status_code} for {url}")
            continue
        if _has_rankings_table(response.text):
            _RANKINGS_URL_CACHE = url
            return response.text

        if not discovered_url:
            discovered_url = _discover_latest_rankings_url()
            for latest_url in _unique_urls(discovered_url):
                if latest_url in {url, _RANKINGS_URL_CACHE, _rankings_url(), PROBED_RANKINGS_URL}:
                    continue
                headers = dict(HEADERS)
                headers["Referer"] = latest_url
                try:
                    latest_response = federation_request("post",
                        latest_url,
                        data=payload,
                        headers=headers,
                        timeout=20,
                        allow_redirects=True,
                    )
                except requests.RequestException as exc:
                    print(f"    Request error for {latest_url}: {exc}")
                    continue
                if latest_response.status_code == 200 and _has_rankings_table(latest_response.text):
                    _RANKINGS_URL_CACHE = latest_url
                    return latest_response.text

    print(f"    No public ranking table found for {weapon} {gender} {category}")
    return None


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_aut").start()
    season = current_season()
    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []
    skipped_combos: list[str] = []

    print(f"ÖFV Austria rankings — season {season}")

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")
            html = fetch_rankings_page(weapon, gender, category)
            if not html:
                total_failed += 1
                failed_combos.append(combo_label)
            else:
                parsed = parse_rankings_table(html)
                if not parsed:
                    print("    No rows parsed")
                    total_skipped += 1
                    skipped_combos.append(combo_label)
                else:
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
                    print(f"    Parsed {len(rows)} rows; written {written}")
                    total_written += written

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "failed_combos": failed_combos,
                "skipped_combos": skipped_combos,
                "source_url": _RANKINGS_URL_CACHE or _rankings_url(season),
                "request_method": "POST",
            },
        )
        print(f"Done — written={total_written}, failed={total_failed}, skipped={total_skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

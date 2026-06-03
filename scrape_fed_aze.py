"""
scrape_fed_aze.py - Azerbaijan Fencing Federation rankings scraper.

Probe evidence, 2026-06-02:
  - Prompt host azfencing.az did not resolve from the local sandbox probe.
  - Current public federation domain is https://fencing.az.
  - Request method: GET.
  - Response format: server-rendered HTML.
  - Public ranking pages:
      Epee:  https://fencing.az/az/spaqa-reytinq/
      Sabre: https://fencing.az/az/sablya-reytinq/
  - Public combos: Epee and Sabre Senior/Junior Men/Women.
  - No public Foil ranking page was found in the ranking menu during probe.

Captured row shape:
  № Soyad,ad Təvəllüd Cəmi xallar
  1 Quliyeva Aynur 2007 28.5
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "aze_fencing"
COUNTRY = "Azerbaijan"
BASE_URL = "https://fencing.az"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "az,en;q=0.8",
}

EPEE_RANKING_URL = f"{BASE_URL}/az/spaqa-reytinq/"
SABRE_RANKING_URL = f"{BASE_URL}/az/sablya-reytinq/"

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

PUBLIC_RANKING_URLS = {
    ("Epee", "Women", "Senior"): EPEE_RANKING_URL,
    ("Epee", "Men", "Senior"): EPEE_RANKING_URL,
    ("Epee", "Women", "Junior"): EPEE_RANKING_URL,
    ("Epee", "Men", "Junior"): EPEE_RANKING_URL,
    ("Sabre", "Men", "Senior"): SABRE_RANKING_URL,
    ("Sabre", "Women", "Senior"): SABRE_RANKING_URL,
    ("Sabre", "Men", "Junior"): SABRE_RANKING_URL,
    ("Sabre", "Women", "Junior"): SABRE_RANKING_URL,
}

_SECTION_HEADINGS = {
    ("Epee", "Women", "Senior"): {"Şpaqa qadınlar", "Epee women"},
    ("Epee", "Men", "Senior"): {"Şpaqa kişilər", "Epee men"},
    ("Epee", "Women", "Junior"): {"Şpaqa gənc qızlar", "Epee junior women"},
    ("Epee", "Men", "Junior"): {"Şpaqa gənc oğlanlar", "Epee junior men"},
    ("Sabre", "Men", "Senior"): {"Sablya kişilər", "Sabre men"},
    ("Sabre", "Women", "Senior"): {"Sablya qadınlar", "Sabre women"},
    ("Sabre", "Men", "Junior"): {"Sablya gənclər", "Sabre juniors", "Sabre junior men"},
    ("Sabre", "Women", "Junior"): {"Sablya U20 qızlar", "Sabre U20 girls", "Sabre junior women"},
}

_AZ_TRANSLITERATION = str.maketrans(
    {
        "ə": "e",
        "Ə": "e",
        "ı": "i",
        "I": "i",
        "İ": "i",
        "ğ": "g",
        "Ğ": "g",
        "ö": "o",
        "Ö": "o",
        "ş": "s",
        "Ş": "s",
        "ü": "u",
        "Ü": "u",
        "ç": "c",
        "Ç": "c",
    }
)

_RANK_HEADERS = {"#", "no", "n", "rank", "yer", "sira", "sira", "№"}
_NAME_HEADERS = {"ad", "name", "fencer", "athlete", "idmanci", "soyadad", "soyadvead"}
_CLUB_HEADERS = {"club", "klub", "komanda", "team"}
_POINT_HEADERS = {"xal", "xallar", "points", "pts", "cemixallar", "totalpoints", "total"}
_SKIP_TOKENS = {
    "",
    "dns",
    "dq",
    "dsq",
    "dnf",
    "wd",
    "ret",
    "total",
    "summary",
    "subtotal",
    "cemi",
    "yekun",
    "disqualified",
    "diskvalifikasiya",
}
_NO_DATA_MARKERS = {
    "no rankings available",
    "no ranking available",
    "no data",
    "reytinq məlumatı tapılmadı",
    "reytinq melumati tapilmadi",
    "tapılmadı",
    "tapilmadi",
}


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY."""
    now = datetime.now(timezone.utc)
    start_year = now.year - 1 if now.month < 7 else now.year
    season = f"{start_year}-{start_year + 1}"
    try:
        import season_utils  # type: ignore

        normalize = getattr(season_utils, "normalize_season", None)
        if normalize:
            normalized = normalize(season)
            if isinstance(normalized, str):
                return normalized
    except Exception:
        pass
    return season


def _clean_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9#№]+", "", _clean_text(value).translate(_AZ_TRANSLITERATION).lower())


def _heading_key(value: str) -> str:
    return _key(value)


def _is_skip_text(value: str) -> bool:
    return _key(value) in _SKIP_TOKENS


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value).rstrip(".")
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

    text = text.replace(" ", "").replace("\xa0", "")
    text = re.sub(r"[^0-9,.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) > 2:
            text = "".join(parts[:-1]) + "." + parts[-1]
        else:
            text = parts[0] + "." + parts[1]
    elif text.count(".") > 1:
        parts = text.split(".")
        if all(len(part) == 3 for part in parts[1:]):
            text = "".join(parts)

    try:
        return float(text)
    except ValueError:
        return None


def _header_indexes(headers: list[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for idx, header in enumerate(headers):
        key = _key(header)
        if "rank" not in indexes and key in _RANK_HEADERS:
            indexes["rank"] = idx
        elif "name" not in indexes and key in _NAME_HEADERS:
            indexes["name"] = idx
        elif "club" not in indexes and key in _CLUB_HEADERS:
            indexes["club"] = idx
        elif "points" not in indexes and key in _POINT_HEADERS:
            indexes["points"] = idx
    return indexes


def _table_rows(table) -> Iterable:
    body_rows = []
    for tbody in table.find_all("tbody", recursive=False):
        body_rows.extend(tbody.find_all("tr", recursive=False))
    if body_rows:
        return body_rows
    return table.find_all("tr")


def _parse_tables(html_or_text: str) -> list[dict]:
    soup = BeautifulSoup(html_or_text, "html.parser")
    parsed: list[dict] = []

    for table in soup.find_all("table"):
        header_row = None
        for row in table.find_all("tr"):
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
            indexes = _header_indexes(cells)
            if {"rank", "name", "points"}.issubset(indexes):
                header_row = row
                break

        if header_row is None:
            continue

        headers = [_clean_text(cell.get_text(" ", strip=True)) for cell in header_row.find_all(["td", "th"])]
        indexes = _header_indexes(headers)
        min_cells = max(indexes.values()) + 1
        for row in _table_rows(table):
            if row is header_row:
                continue
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
            if len(cells) < min_cells:
                continue

            rank = _parse_rank(cells[indexes["rank"]])
            if rank is None:
                continue

            name = cells[indexes["name"]]
            if not name or _is_skip_text(name):
                continue

            club = None
            if "club" in indexes and indexes["club"] < len(cells):
                club = cells[indexes["club"]] or None

            points = _parse_points(cells[indexes["points"]])
            parsed.append({"rank": rank, "name": name, "club": club, "points": points})

    return parsed


def _parse_text_lines(html_or_text: str) -> list[dict]:
    soup = BeautifulSoup(html_or_text, "html.parser")
    text = soup.get_text("\n", strip=True)
    parsed: list[dict] = []
    seen: set[tuple[int, str, float | None]] = set()

    for line in text.splitlines():
        line = _clean_text(line)
        if not line or _is_skip_text(line):
            continue

        match = re.match(
            r"^\s*(?P<rank>\d+)[.)]?\s+"
            r"(?P<body>.+?)\s+"
            r"(?:(?P<birth_year>19\d{2}|20\d{2})\s+)?"
            r"(?P<points>-?\d+(?:[.,]\d+)?)\s*$",
            line,
        )
        if not match:
            continue

        rank = _parse_rank(match.group("rank"))
        if rank is None:
            continue

        name = _clean_text(match.group("body"))
        if not name or _is_skip_text(name):
            continue

        points = _parse_points(match.group("points"))
        key = (rank, name, points)
        if key in seen:
            continue
        seen.add(key)
        parsed.append({"rank": rank, "name": name, "club": None, "points": points})

    return parsed


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Azerbaijan ranking HTML/text into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    lowered = _clean_text(html_or_text).translate(_AZ_TRANSLITERATION).lower()
    if any(marker in lowered for marker in _NO_DATA_MARKERS):
        return []

    table_rows = _parse_tables(html_or_text)
    if table_rows:
        return table_rows
    return _parse_text_lines(html_or_text)


def _looks_non_public(html: str) -> bool:
    soup = BeautifulSoup(html or "", "html.parser")
    text_key = _key(soup.get_text(" ", strip=True))
    if soup.find("input", {"type": "password"}):
        return True
    blocked_markers = {
        "login",
        "signin",
        "password",
        "forbidden",
        "accessdenied",
        "cloudflare",
        "captcha",
    }
    return any(marker in text_key for marker in blocked_markers)


def _extract_section(html: str, headings: set[str]) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    wanted = {_heading_key(heading) for heading in headings}

    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
        if _heading_key(heading.get_text(" ", strip=True)) not in wanted:
            continue

        lines = [heading.get_text(" ", strip=True)]
        for sibling in heading.next_siblings:
            name = getattr(sibling, "name", None)
            if name in {"h1", "h2", "h3", "h4"}:
                break
            if hasattr(sibling, "get_text"):
                text = sibling.get_text("\n", strip=True)
            else:
                text = str(sibling).strip()
            if text:
                lines.extend(line for line in text.splitlines() if line.strip())

        section = "\n".join(lines)
        return section if parse_rankings_table(section) else None

    return None


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch and extract content for one Azerbaijan ranking combo."""
    combo = (weapon, gender, category)
    url = PUBLIC_RANKING_URLS.get(combo)
    if not url:
        print(f"    No public Azerbaijan ranking page for {weapon} {gender} {category}")
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
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    html = response.text or ""
    if _looks_non_public(html):
        print(f"    Non-public or blocked ranking page for {url}")
        return None

    section = _extract_section(html, _SECTION_HEADINGS.get(combo, set()))
    if not section:
        print(f"    No scrapeable rankings at {url} for {weapon} {gender} {category}")
        return None
    return section


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_aze").start()
    season = current_season()
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous Azerbaijan federation run state found: {previous_state}")

    print(f"Azerbaijan federation rankings - season {season}")
    print(f"Base URL: {BASE_URL}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos = 0
    failed_combos: list[str] = []

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            label = _combo_label(weapon, gender, category)
            print(f"  {label}...")

            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                total_failed += 1
                failed_combos.append(label)
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append(label)
                else:
                    source_url = PUBLIC_RANKING_URLS.get((weapon, gender, category))
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
                                "source_format": "html",
                                "probe_domain": BASE_URL,
                            },
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    print(f"    Parsed {len(rows)} rows; written {written} rows")
                    total_written += written
                    working_combos += 1

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        state = {
            "season": season,
            "written": total_written,
            "failed": total_failed,
            "skipped": total_skipped,
            "working_combos": working_combos,
            "total_combos": len(RANKING_COMBOS),
            "failed_combos": failed_combos,
            "public_urls": sorted(set(PUBLIC_RANKING_URLS.values())),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        set_state(SOURCE, "last_run", state)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=state,
        )
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
        print(
            "Done - "
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"working_combos={working_combos}/{len(RANKING_COMBOS)}"
        )
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

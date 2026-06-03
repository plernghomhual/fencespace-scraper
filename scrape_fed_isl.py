"""
scrape_fed_isl.py - Iceland federation rankings scraper.

Probe summary, 2026-06-02:
  - Probe target: https://skylmingar.is
  - Public active content found via https://www.fencing.is/
  - Method/format: GET text/html for the site and /frettir news page.
  - Public files: news PDFs under /_files/ugd/...pdf, but no durable public
    national ranking table/download was found.
  - Search/probe terms checked included Stigalisti, Sæti, Nafn, Félag, Stig.
  - Public Senior/Junior Foil/Epee/Sabre Men/Women coverage found: 0/12.

The fetch path is intentionally stub-safe: it attempts all standard combos, logs
that no scrapeable public ranking URL is known, and exits successfully without
writing fabricated data. The parser remains real and table/text based so this
module can be wired to a future public Icelandic ranking URL without changing
the storage path.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "isl_fencing"
COUNTRY = "Iceland"
CC = "isl"
BASE_URL = "https://www.fencing.is"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "is,en-US;q=0.8,en;q=0.6",
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

PROBED_PUBLIC_URLS = [
    "https://www.fencing.is/",
    "https://www.fencing.is/frettir",
]

# No durable public Iceland national ranking URL was found during probing.
RANKING_URLS: dict[tuple[str, str, str], str] = {}

RANK_HEADER_ALIASES = {
    "rank",
    "ranking",
    "place",
    "position",
    "nr",
    "sæti",
    "saeti",
    "stada",
    "staða",
}
NAME_HEADER_ALIASES = {
    "name",
    "fencer",
    "fencername",
    "nafn",
    "keppandi",
    "skylmingamadur",
    "skylmingamaður",
    "skylmingakona",
}
CLUB_HEADER_ALIASES = {
    "club",
    "clubs",
    "team",
    "felag",
    "félag",
    "deild",
    "klubbur",
    "klúbbur",
}
POINTS_HEADER_ALIASES = {
    "points",
    "point",
    "totalpoints",
    "stig",
    "stigin",
    "samtals",
}
SKIP_RANK_VALUES = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "samtals",
    "total",
    "summary",
    "yfirlit",
    "alls",
}


def _clean_text(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def _header_key(value: str) -> str:
    text = _clean_text(value).lower()
    return re.sub(r"[^0-9a-záðéíóúýþæö]", "", text)


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value).lower().strip(".")
    if not text:
        return None
    if text in SKIP_RANK_VALUES:
        return None
    if any(token in text for token in SKIP_RANK_VALUES):
        return None
    match = re.match(r"^(\d+)", text)
    return int(match.group(1)) if match else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            head, tail = text.rsplit(",", 1)
            text = f"{head.replace('.', '').replace(',', '')}.{tail}"
        else:
            text = text.replace(",", "")
    elif "," in text:
        head, tail = text.rsplit(",", 1)
        if len(tail) in (1, 2):
            text = f"{head.replace(',', '')}.{tail}"
        else:
            text = text.replace(",", "")

    try:
        return float(text)
    except ValueError:
        return None


def _top_level_rows(table: Tag) -> list[Tag]:
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _row_cells(row: Tag) -> list[Tag]:
    return row.find_all(["td", "th"], recursive=False)


def _find_header_mapping(labels: Iterable[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, label in enumerate(labels):
        key = _header_key(label)
        if key in RANK_HEADER_ALIASES:
            mapping["rank"] = index
        elif key in NAME_HEADER_ALIASES:
            mapping["name"] = index
        elif key in CLUB_HEADER_ALIASES:
            mapping["club"] = index
        elif key in POINTS_HEADER_ALIASES:
            mapping["points"] = index

    if {"rank", "name", "points"}.issubset(mapping):
        return mapping
    return None


def _name_from_cell(cell: Tag) -> str:
    link_texts = [_clean_text(link.get_text(" ", strip=True)) for link in cell.find_all("a")]
    link_texts = [text for text in link_texts if text]
    if link_texts:
        return link_texts[0]
    return _clean_text(cell.get_text(" ", strip=True))


def _row_from_cells(cells: list, mapping: dict[str, int]) -> dict | None:
    required_index = max(mapping["rank"], mapping["name"], mapping["points"])
    if len(cells) <= required_index:
        return None

    def cell_text(index: int) -> str:
        cell = cells[index]
        if isinstance(cell, Tag):
            return _clean_text(cell.get_text(" ", strip=True))
        return _clean_text(str(cell))

    rank = _parse_rank(cell_text(mapping["rank"]))
    if rank is None:
        return None

    name_cell = cells[mapping["name"]]
    if isinstance(name_cell, Tag):
        name = _name_from_cell(name_cell)
    else:
        name = _clean_text(str(name_cell))
    if not name:
        return None

    points_text = cell_text(mapping["points"])
    points = _parse_points(points_text)
    if points_text and points is None:
        return None

    club = None
    club_index = mapping.get("club")
    if club_index is not None and len(cells) > club_index:
        club = cell_text(club_index) or None

    return {
        "rank": rank,
        "name": name,
        "club": club,
        "points": points,
    }


def _parse_html_tables(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows_out: list[dict] = []

    for table in soup.find_all("table"):
        rows = _top_level_rows(table)
        for header_index, row in enumerate(rows):
            cells = _row_cells(row)
            labels = [cell.get_text(" ", strip=True) for cell in cells]
            mapping = _find_header_mapping(labels)
            if not mapping:
                continue

            for data_row in rows[header_index + 1 :]:
                parsed = _row_from_cells(_row_cells(data_row), mapping)
                if parsed:
                    rows_out.append(parsed)
            break

    return rows_out


def _split_text_row(line: str) -> list[str]:
    if "|" in line:
        return [_clean_text(part) for part in line.split("|")]
    if "\t" in line:
        return [_clean_text(part) for part in line.split("\t")]
    return [_clean_text(part) for part in re.split(r"\s{2,}", line.strip())]


def _parse_plain_text_table(text: str) -> list[dict]:
    lines = [_clean_text(line) for line in text.splitlines() if _clean_text(line)]
    for header_index, line in enumerate(lines):
        labels = _split_text_row(line)
        mapping = _find_header_mapping(labels)
        if not mapping:
            continue

        rows_out: list[dict] = []
        for data_line in lines[header_index + 1 :]:
            parsed = _row_from_cells(_split_text_row(data_line), mapping)
            if parsed:
                rows_out.append(parsed)
        return rows_out

    return []


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Icelandic ranking HTML/text into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    html_rows = _parse_html_tables(html_or_text)
    if html_rows:
        return html_rows
    return _parse_plain_text_table(html_or_text)


def ranking_url_for(weapon: str, gender: str, category: str) -> str | None:
    return RANKING_URLS.get((weapon, gender, category))


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def _looks_blocked_or_login_only(text: str) -> bool:
    lowered = text.lower()
    blocked_markers = (
        "access denied",
        "captcha",
        "cloudflare",
        "checking your browser",
        "forbidden",
        "blocked",
    )
    login_markers = (
        "login required",
        "log in",
        "sign in",
        "innskrá",
        "skrá inn",
        "requires authentication",
    )
    js_markers = (
        "enable javascript",
        "javascript required",
        "requires javascript",
    )
    return any(marker in lowered for marker in blocked_markers + login_markers + js_markers)


def _looks_no_public_data(text: str) -> bool:
    lowered = text.lower()
    no_data_markers = (
        "no rankings available",
        "no ranking available",
        "no data",
        "engin gögn",
        "enginn opinber stigalisti",
        "no public rankings",
    )
    return any(marker in lowered for marker in no_data_markers)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Iceland ranking page, returning None for missing/failed combos."""
    label = _combo_label(weapon, gender, category)
    url = ranking_url_for(weapon, gender, category)
    if not url:
        print(
            f"    No scrapeable rankings at {BASE_URL} for {label}; "
            f"probed: {', '.join(PROBED_PUBLIC_URLS)}"
        )
        return None

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

    text = response.text or ""
    if _looks_blocked_or_login_only(text):
        print(f"    Blocked/login/JS-only response at {url}")
        return None
    if _looks_no_public_data(text):
        print(f"    No public ranking data at {url}")
        return None
    return text


def current_season() -> str:
    """Return the current storage season as YYYY-YYYY."""
    now = datetime.now(timezone.utc)
    end_year = now.year if now.month < 7 else now.year + 1
    fallback = f"{end_year - 1:04d}-{end_year:04d}"

    try:
        import season_utils

        if hasattr(season_utils, "season_to_string"):
            fallback = season_utils.season_to_string(end_year)
        if hasattr(season_utils, "normalize_season"):
            return season_utils.normalize_season(fallback)
    except Exception:
        pass

    return fallback


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_isl").start()
    season = current_season()
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous Iceland federation run state found: {previous_state}")

    print(f"Iceland federation rankings - season {season}")
    print(f"No durable public ranking source found in probe; attempting {len(RANKING_COMBOS)} standard combos.")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos: list[str] = []
    failed_combos: list[str] = []
    missing_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            label = _combo_label(weapon, gender, category)
            url = ranking_url_for(weapon, gender, category)
            print(f"  {label}...")

            content = fetch_rankings_page(weapon, gender, category)
            if content is None:
                if url:
                    total_failed += 1
                    failed_combos.append(label)
                    time.sleep(REQUEST_DELAY)
                else:
                    total_skipped += 1
                    missing_combos.append(label)
                continue

            parsed = parse_rankings_table(content)
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
                        "country_code": CC,
                        "source_url": url,
                        "format": "html",
                    },
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            total_written += written
            working_combos.append(label)
            print(f"    Parsed {len(parsed)} rows; written {written}")
            time.sleep(REQUEST_DELAY)

        state = {
            "season": season,
            "written": total_written,
            "failed": total_failed,
            "skipped": total_skipped,
            "combos_total": len(RANKING_COMBOS),
            "combos_working": len(working_combos),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
            "missing_public_combos": missing_combos,
            "probed_urls": PROBED_PUBLIC_URLS,
            "data_format": "stub",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        set_state(SOURCE, "last_run", state)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=state,
        )
        print(
            f"Done - written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"combos_working={len(working_combos)}/{len(RANKING_COMBOS)}"
        )
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
        if missing_combos:
            print(f"Missing public combos: {', '.join(missing_combos)}")
    except Exception as exc:
        set_state(
            SOURCE,
            "last_error",
            {"error": str(exc), "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

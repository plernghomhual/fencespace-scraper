"""
scrape_fed_kaz.py - Kazakhstan national federation rankings scraper.

Probe findings, 2026-06-02:
  - Requested probe target `https://fencing.kz/` returns public HTML for an
    unrelated Karaganda meat shop (`Мясной Павильон Караганда`). Candidate
    ranking/result/API paths on that host return 404.
  - Official references list `www.kazfencing.com` and `kazfencing.kz`;
    `https://kazfencing.com/` redirects to `https://kazfencing.kz/`.
  - `https://kazfencing.kz/` is public HTML for the National Fencing Federation
    of Kazakhstan. `/?page_id=488` (`Наши результаты`) and search pages are
    public HTML, but sampled result posts expose prose/images only, with no
    durable ranking table and no public PDF/XLS/CSV ranking files.
  - Direct ranking slugs (`/ranking`, `/rankings`, `/rating`, `/rejting`,
    `/рейтинги`, `/results`) return 404. `/wp-json` and `wp-json/wp/v2/*`
    return 404. Upload directory listings return 403.
  - Request method: GET with browser-like headers.
  - Response format found: public HTML; no scrapeable ranking format found.
  - Public combos found: 0/12 for Senior/Junior Foil/Epee/Sabre Men/Women.

This scraper attempts all 12 standard combos and exits successfully with a
documented stub state until Kazakhstan publishes a durable ranking table/file.
If a public ranking URL appears later, add it to PUBLIC_RANKING_URLS; the parser
already supports Kazakh/Russian rank/name/club/points tables and delimited text.
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
from scraper_state import get_state, set_state

try:
    from season_utils import normalize_season
except ImportError:  # pragma: no cover - compatibility fallback
    def normalize_season(raw) -> str:
        if isinstance(raw, int):
            return f"{raw - 1:04d}-{raw:04d}"
        value = str(raw).strip()
        if "-" in value:
            return value
        year = int(value)
        return f"{year - 1:04d}-{year:04d}"


SOURCE = "kaz_fencing"
COUNTRY = "Kazakhstan"
BASE_URL = "https://kazfencing.kz"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-KZ,ru;q=0.9,kk;q=0.8,en;q=0.6",
    "Referer": "https://fencing.kz/",
}

REQUEST_METHOD = "GET"
DATA_FORMAT = "stub"
PROBED_URLS = [
    {
        "url": "https://fencing.kz/",
        "method": REQUEST_METHOD,
        "format": "html unrelated meat shop",
        "public_combos": [],
    },
    {
        "url": "https://fencing.kz/ranking",
        "method": REQUEST_METHOD,
        "format": "404 html",
        "public_combos": [],
    },
    {
        "url": "https://kazfencing.kz/",
        "method": REQUEST_METHOD,
        "format": "html federation site",
        "public_combos": [],
    },
    {
        "url": "https://kazfencing.kz/?page_id=488",
        "method": REQUEST_METHOD,
        "format": "html results page without ranking tables/files",
        "public_combos": [],
    },
    {
        "url": "https://kazfencing.kz/?s=рейтинг",
        "method": REQUEST_METHOD,
        "format": "html search results without ranking tables/files",
        "public_combos": [],
    },
    {
        "url": "https://kazfencing.kz/wp-json",
        "method": REQUEST_METHOD,
        "format": "404 html",
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

PUBLIC_RANKING_URLS: dict[tuple[str, str, str], str] = {}

RANK_HEADER_ALIASES = {
    "#",
    "rank",
    "ranking",
    "place",
    "position",
    "pos",
    "орын",
    "орны",
    "место",
    "позиция",
    "рейтинг",
    "n",
    "no",
    "номер",
}
NAME_HEADER_ALIASES = {
    "name",
    "fencer",
    "athlete",
    "competitor",
    "атыжөні",
    "атыжони",
    "атыжөніспортшы",
    "фио",
    "фамилияимя",
    "спортсмен",
    "спортсменка",
    "участник",
    "атлет",
}
CLUB_HEADER_ALIASES = {
    "club",
    "clubs",
    "team",
    "school",
    "city",
    "клуб",
    "команда",
    "қала",
    "город",
    "область",
    "өңір",
    "регион",
}
POINT_HEADER_ALIASES = {
    "points",
    "point",
    "pts",
    "totalpoints",
    "score",
    "ұпай",
    "ұпайлар",
    "упай",
    "очки",
    "балл",
    "баллы",
    "итого",
    "барлығы",
}
SKIP_ROW_TOKENS = {
    "",
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "ret",
    "withdrawn",
    "total",
    "totals",
    "summary",
    "subtotal",
    "итог",
    "итоги",
    "итого",
    "всего",
    "сумма",
    "сводная",
    "қорытынды",
    "корытынды",
    "барлығы",
    "жинағы",
    "неявка",
    "дисквалификация",
}
NO_DATA_MARKERS = {
    "no rankings available",
    "no ranking available",
    "no ranking data",
    "no data",
    "рейтинг спортсменов не опубликован",
    "рейтинг не опубликован",
    "нет данных",
    "данные отсутствуют",
    "ешқандай дерек жоқ",
}
BLOCKED_MARKERS = {
    "access denied",
    "forbidden",
    "security service",
    "captcha",
    "recaptcha",
    "login required",
    "please log in",
    "please login",
    "sign in",
    "password",
    "войдите",
    "авторизация",
    "пароль",
}
JS_ONLY_MARKERS = {
    "please enable javascript",
    "enable javascript to continue",
    "requires javascript",
    "javascript is required",
}


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY."""
    now = datetime.now(UTC)
    season_end_year = now.year if now.month < 7 else now.year + 1
    try:
        return normalize_season(season_end_year)
    except Exception:
        return f"{season_end_year - 1:04d}-{season_end_year:04d}"


def _clean_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _header_key(value: str) -> str:
    text = _clean_text(value)
    if text == "#":
        return "#"
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = normalized.replace("ё", "е").replace("№", "no")
    return re.sub(r"[^\w#]+", "", normalized, flags=re.UNICODE)


def _is_skip_text(value: str) -> bool:
    key = _header_key(value)
    return key in SKIP_ROW_TOKENS


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
    text = _clean_text(value).replace(" ", "").replace("\xa0", "")
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


def _find_header_mapping(labels: Iterable[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, label in enumerate(labels):
        key = _header_key(label)
        if key in RANK_HEADER_ALIASES and "rank" not in mapping:
            mapping["rank"] = index
        elif key in NAME_HEADER_ALIASES and "name" not in mapping:
            mapping["name"] = index
        elif key in CLUB_HEADER_ALIASES and "club" not in mapping:
            mapping["club"] = index
        elif key in POINT_HEADER_ALIASES and "points" not in mapping:
            mapping["points"] = index

    return mapping if {"rank", "name", "points"}.issubset(mapping) else None


def _row_cells(row: Tag) -> list[Tag]:
    return row.find_all(["td", "th"], recursive=False)


def _table_rows(table: Tag) -> list[Tag]:
    rows = []
    for section in table.find_all(["thead", "tbody", "tfoot"], recursive=False):
        rows.extend(section.find_all("tr", recursive=False))
    if rows:
        return rows
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _append_row(results: list[dict], cells: list[str], mapping: dict[str, int]) -> None:
    required_index = max(mapping["rank"], mapping["name"], mapping["points"])
    if len(cells) <= required_index:
        return

    rank = _parse_rank(cells[mapping["rank"]])
    if rank is None:
        return

    name = _clean_text(cells[mapping["name"]])
    if not name or _is_skip_text(name):
        return

    club = None
    if "club" in mapping and mapping["club"] < len(cells):
        club = _clean_text(cells[mapping["club"]]) or None

    results.append(
        {
            "rank": rank,
            "name": name,
            "club": club,
            "points": _parse_points(cells[mapping["points"]]),
        }
    )


def _parse_html_tables(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        mapping = None
        for row in _table_rows(table):
            cells = _row_cells(row)
            if not cells:
                continue

            labels = [cell.get_text(" ", strip=True) for cell in cells]
            if mapping is None:
                mapping = _find_header_mapping(labels)
                if mapping is not None:
                    continue
                if len(labels) >= 4 and _parse_rank(labels[0]) is not None:
                    mapping = {"rank": 0, "name": 1, "club": 2, "points": 3}

            if mapping:
                _append_row(results, labels, mapping)

    return results


def _split_delimited_line(line: str) -> list[str]:
    if "\t" in line:
        return [_clean_text(part) for part in line.split("\t")]
    if "|" in line:
        return [_clean_text(part) for part in line.split("|")]
    return []


def _parse_delimited_text(text: str) -> list[dict]:
    rows = [_split_delimited_line(line) for line in text.splitlines()]
    rows = [row for row in rows if row]
    if not rows:
        return []

    mapping = None
    results: list[dict] = []
    for cells in rows:
        if mapping is None:
            mapping = _find_header_mapping(cells)
            if mapping is not None:
                continue
            if len(cells) >= 4 and _parse_rank(cells[0]) is not None:
                mapping = {"rank": 0, "name": 1, "club": 2, "points": 3}

        if mapping:
            _append_row(results, cells, mapping)

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Kazakhstan ranking content into rank/name/club/points rows."""
    if not html_or_text or not _clean_text(html_or_text):
        return []

    page_text = _clean_text(BeautifulSoup(html_or_text, "html.parser").get_text(" ", strip=True)).lower()
    if any(marker in page_text for marker in NO_DATA_MARKERS):
        return []

    html_rows = _parse_html_tables(html_or_text)
    if html_rows:
        return html_rows

    return _parse_delimited_text(html_or_text)


def ranking_url_for(weapon: str, gender: str, category: str) -> str | None:
    return PUBLIC_RANKING_URLS.get((weapon, gender, category))


def _looks_unusable_public_page(html: str) -> bool:
    lower_html = (html or "").lower()
    text = _clean_text(BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)).lower()
    if any(marker in text or marker in lower_html for marker in BLOCKED_MARKERS):
        return True
    if any(marker in text or marker in lower_html for marker in JS_ONLY_MARKERS):
        return True
    if re.search(r"<script\b", html or "", flags=re.IGNORECASE) and re.search(
        r"id=[\"'](?:root|app)[\"']", html or "", flags=re.IGNORECASE
    ):
        return True
    return False


def _has_rankings_table(html: str) -> bool:
    return bool(parse_rankings_table(html))


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Kazakhstan ranking page, returning None for missing/blocked data."""
    url = ranking_url_for(weapon, gender, category)
    if not url:
        print(f"    No scrapeable rankings at {BASE_URL} for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    response_url = getattr(response, "url", url)
    if response.status_code == 404:
        print(f"    No scrapeable rankings at {response_url} (HTTP 404)")
        return None
    if response.status_code in {401, 403, 429}:
        print(f"    Blocked or unavailable ranking page at {response_url} (HTTP {response.status_code})")
        return None
    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {response_url}")
        return None

    if _looks_unusable_public_page(response.text) or not _has_rankings_table(response.text):
        print(f"    No scrapeable rankings at {response_url}")
        return None

    return response.text


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_kaz").start()
    season = current_season()
    _ = get_state(SOURCE, "last_run")

    print(f"Kazakhstan federation rankings - season {season}")
    print(f"No scrapeable rankings at {BASE_URL}")
    print("Probed URLs:")
    for probe in PROBED_URLS:
        print(f"  {probe['url']} [{probe['method']}, {probe['format']}]")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    public_combos: list[str] = []
    failed_combos: list[dict[str, str]] = []

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            label = _combo_label(weapon, gender, category)
            url = ranking_url_for(weapon, gender, category) or BASE_URL
            print(f"  {label}...")

            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                print(f"    No scrapeable rankings at {url}")
                total_failed += 1
                failed_combos.append({"combo": label, "url": url, "reason": "no public rankings"})
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append({"combo": label, "url": url, "reason": "no rows parsed"})
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
                            metadata={"source_url": url, "probe_format": DATA_FORMAT},
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    print(f"    Written {written} rows ({len(parsed)} parsed)")
                    total_written += written
                    public_combos.append(label)

            if index < len(RANKING_COMBOS) - 1 and ranking_url_for(weapon, gender, category):
                time.sleep(REQUEST_DELAY)

        summary = {
            "season": season,
            "combos": len(RANKING_COMBOS),
            "public_combos": public_combos,
            "failed_combos": failed_combos,
            "probed_urls": PROBED_URLS,
            "data_format": DATA_FORMAT,
            "combos_working": len(public_combos),
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
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}, "
            f"combos_working={len(public_combos)}/{len(RANKING_COMBOS)}"
        )
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

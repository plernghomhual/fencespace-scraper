"""
scrape_fed_mar.py - Morocco federation rankings scraper.

Probe evidence, 2026-06-02:
  - Target domain: https://frmescrime.ma
  - Request method attempted: GET with browser-like headers
  - Sandbox result: frmescrime.ma and www.frmescrime.ma did not resolve.
  - Escalated live probe was blocked by the Codex approval usage gate.
  - Search results did not expose a durable public ranking URL, API, PDF, or XLS feed.
  - Public combos confirmed: 0/12. The scraper attempts all standard combos and exits 0.

If a durable Morocco ranking URL becomes public, add it to RANKING_URLS; the parser
already handles French/Arabic HTML tables with rank/name/club/points columns.
"""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "mar_fencing"
COUNTRY = "Morocco"
BASE_URL = "https://frmescrime.ma"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-MA,fr;q=0.9,ar-MA;q=0.8,en;q=0.7",
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

PROBED_URLS = [
    BASE_URL,
    f"{BASE_URL}/classement",
    f"{BASE_URL}/classements",
    f"{BASE_URL}/ranking",
    f"{BASE_URL}/rankings",
    f"{BASE_URL}/resultats",
    f"{BASE_URL}/competitions",
    f"{BASE_URL}/wp-json/wp/v2/search?search=classement",
    f"{BASE_URL}/wp-json/wp/v2/pages?search=classement",
    f"{BASE_URL}/wp-json/wp/v2/posts?search=classement",
]

# No durable public Morocco ranking URL was available during the probe.
RANKING_URLS: dict[tuple[str, str, str], str] = {}

_RANK_HEADERS = {"rank", "rang", "classement", "position", "pos", "place"}
_NAME_HEADERS = {"nom", "nomprenom", "name", "athlete", "tireur", "fencer"}
_CLUB_HEADERS = {"club", "clubs", "association", "salle", "structure"}
_POINT_HEADERS = {"points", "point", "pts", "totalpoints", "total"}
_ARABIC_HEADERS = {
    "rank": ("المركز", "الترتيب", "تصنيف", "الرتبة"),
    "name": ("الاسم", "الإسم", "اسم", "اللاعب"),
    "club": ("النادي", "الجمعية"),
    "points": ("النقاط", "نقاط"),
}
_SKIP_VALUES = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "forfait",
    "abandon",
    "disqualifie",
    "disqualifiee",
    "total",
    "totaux",
    "resume",
    "summary",
    "مجموع",
    "ملخص",
    "منسحب",
    "غائب",
    "مستبعد",
}


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY, using season_utils if present."""
    now = datetime.now(UTC)
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


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _latin_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(value).lower())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_text)


def _header_kind(value: str) -> str | None:
    text = _clean_text(value).lower()
    token = _latin_key(text)
    if token in _RANK_HEADERS:
        return "rank"
    if token in _NAME_HEADERS:
        return "name"
    if token in _CLUB_HEADERS:
        return "club"
    if token in _POINT_HEADERS:
        return "points"

    for kind, aliases in _ARABIC_HEADERS.items():
        if any(alias in text for alias in aliases):
            return kind
    return None


def _header_mapping(labels: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for index, label in enumerate(labels):
        kind = _header_kind(label)
        if kind and kind not in mapping:
            mapping[kind] = index

    required = {"rank", "name", "points"}
    return mapping if required.issubset(mapping) else None


def _row_cells(row: Tag) -> list[Tag]:
    return row.find_all(["td", "th"], recursive=False)


def _table_rows(table: Tag) -> list[Tag]:
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _cell_text(cell: Tag, *, prefer_name: bool = False) -> str:
    if prefer_name:
        dropdown = cell.find("a", class_=lambda value: value and "dropdown-toggle" in value)
        if dropdown:
            return _clean_text(dropdown.get_text(" ", strip=True))

    clone = BeautifulSoup(str(cell), "html.parser").find(cell.name)
    if clone is None:
        return _clean_text(cell.get_text(" ", strip=True))

    for unwanted in clone.select("script, style, form, .modal, .dropdown-menu"):
        unwanted.decompose()
    return _clean_text(clone.get_text(" ", strip=True))


def _is_skip_text(value: str) -> bool:
    text = _clean_text(value).lower()
    token = _latin_key(text)
    if token in _SKIP_VALUES or text in _SKIP_VALUES:
        return True
    return any(skip in text for skip in _SKIP_VALUES if any("\u0600" <= ch <= "\u06ff" for ch in skip))


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value)
    if not text or _is_skip_text(text):
        return None

    digits = []
    for char in text:
        try:
            digits.append(str(unicodedata.digit(char)))
        except (TypeError, ValueError):
            digits.append(char)
    match = re.match(r"^\s*(\d+)", "".join(digits))
    if not match:
        return None

    rank = int(match.group(1))
    return rank if rank > 0 else None


def _ascii_digits(value: str) -> str:
    converted = []
    for char in value:
        try:
            converted.append(str(unicodedata.digit(char)))
        except (TypeError, ValueError):
            converted.append(char)
    return "".join(converted)


def _parse_points(value: str) -> float | None:
    text = _ascii_digits(_clean_text(value))
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
        head, tail = text.rsplit(",", 1)
        normalized = f"{head.replace(',', '')}.{tail}" if len(tail) in (1, 2) else text.replace(",", "")
    elif "." in text:
        parts = text.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0].lstrip("-")) <= 3:
            normalized = "".join(parts)
        elif len(parts) > 2 and all(len(part) == 3 for part in parts[1:]):
            normalized = "".join(parts)
        else:
            normalized = text
    else:
        normalized = text

    try:
        return float(normalized)
    except ValueError:
        return None


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse French/Arabic ranking tables into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    soup = BeautifulSoup(html_or_text, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        rows = _table_rows(table)
        for header_index, header_row in enumerate(rows):
            header_cells = _row_cells(header_row)
            if not header_cells:
                continue

            labels = [_cell_text(cell) for cell in header_cells]
            mapping = _header_mapping(labels)
            if not mapping:
                continue

            min_cells = max(mapping.values()) + 1
            for row in rows[header_index + 1:]:
                cells = _row_cells(row)
                if len(cells) < min_cells:
                    continue

                rank_text = _cell_text(cells[mapping["rank"]])
                name = _cell_text(cells[mapping["name"]], prefer_name=True)
                if _is_skip_text(rank_text) or _is_skip_text(name):
                    continue

                rank = _parse_rank(rank_text)
                if rank is None or not name:
                    continue

                club = None
                if "club" in mapping and mapping["club"] < len(cells):
                    club = _cell_text(cells[mapping["club"]]) or None

                points = _parse_points(_cell_text(cells[mapping["points"]]))
                results.append({"rank": rank, "name": name, "club": club, "points": points})

            break

    return results


def _discover_ranking_links() -> dict[tuple[str, str, str], str]:
    return dict(RANKING_URLS)


def _looks_login_or_blocked(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("input", {"type": re.compile(r"password", re.I)}):
        return True

    text = _clean_text(soup.get_text(" ", strip=True)).lower()
    return any(
        marker in text
        for marker in (
            "connexion requise",
            "se connecter",
            "login",
            "password",
            "mot de passe",
            "access denied",
            "forbidden",
            "تسجيل الدخول",
        )
    )


def _looks_js_only(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("table"):
        return False

    text = _clean_text(soup.get_text(" ", strip=True)).lower()
    has_app_shell = bool(soup.select("#app, #root, [data-reactroot]"))
    has_script = bool(soup.find("script"))
    return has_script and (has_app_shell or "enable javascript" in text or "javascript requis" in text)


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Morocco ranking page, returning None for missing, blocked, or failed combos."""
    links = _discover_ranking_links()
    url = links.get((weapon, gender, category))
    if not url:
        print(
            f"    No scrapeable rankings at {BASE_URL} for {_combo_label(weapon, gender, category)}; "
            f"probed {len(PROBED_URLS)} candidate URLs"
        )
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    if _looks_login_or_blocked(response.text):
        print(f"    Login-only or blocked page at {response.url}")
        return None

    if _looks_js_only(response.text):
        print(f"    JS-only page with no public table at {response.url}")
        return None

    return response.text


def main():
    run_log = ScraperRunLogger("scrape_fed_mar").start()
    season = current_season()
    print(f"Morocco federation rankings - season {season}")

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
            if html is None:
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
                        "source_url": RANKING_URLS.get((weapon, gender, category), BASE_URL),
                        "probed_urls": PROBED_URLS,
                    },
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
            "combos_working": len(working_combos),
            "combos_total": len(RANKING_COMBOS),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
            "probed_urls": PROBED_URLS,
            "probe_result": "No durable public Morocco federation ranking URL found",
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
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

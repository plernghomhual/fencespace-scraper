"""
scrape_fed_ukr.py — Ukrainian Fencing Federation (NFFU) rankings scraper.

Probe findings (2026-06-01):
  Candidate paths:
    https://fencing.ua/reyting, /rankings, /zmahannya/reyting all redirect to
    https://www.nffu.org.ua/ and do not expose ranking data directly.
    https://nffu.gov.ua does not resolve.
  Working index:
    GET https://www.nffu.org.ua/рейтинги/ -> text/html; charset=UTF-8
  Ranking files:
    Public PDF links under /wp-content/uploads/2026/05/.
    All 12 Senior/Junior Foil/Epee/Sabre Men/Women combinations are public.
  PDF text columns:
    П. І. П. | Рік народження | Місто | Організація | Очки разом | event columns
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from io import BytesIO

import pdfplumber
import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "ukr_fencing"
COUNTRY = "UKR"
BASE_URL = "https://www.nffu.org.ua/рейтинги/"
REFERER_URL = "https://www.nffu.org.ua/%D1%80%D0%B5%D0%B9%D1%82%D0%B8%D0%BD%D0%B3%D0%B8/"
REQUEST_DELAY = 1.5
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (1.5, 3.0)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": REFERER_URL,
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

RANKING_URLS = {
    ("Foil", "Men", "Senior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/рапіра-чол-дорослі-2.pdf",
    ("Foil", "Women", "Senior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/рапіра-жін-дорослі-2.pdf",
    ("Epee", "Men", "Senior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/шпага-чол-дорослі-2.pdf",
    ("Epee", "Women", "Senior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/шпага-жін-дорослі-2.pdf",
    ("Sabre", "Men", "Senior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/шабля-чол-дорослі-1.pdf",
    ("Sabre", "Women", "Senior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/шабля-жін-дорослі-2.pdf",
    ("Foil", "Men", "Junior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/рапіра-юн-юніори.pdf",
    ("Foil", "Women", "Junior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/рапіра-дів-юніорки.pdf",
    ("Epee", "Men", "Junior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/шпага-юн-юніори.pdf",
    ("Epee", "Women", "Junior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/шпага-дів-юніорки.pdf",
    ("Sabre", "Men", "Junior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/шабля-юн-юніори.pdf",
    ("Sabre", "Women", "Junior"): "https://www.nffu.org.ua/wp-content/uploads/2026/05/шабля-дів-юніорки.pdf",
}

_HTML_RE = re.compile(r"<\s*(?:!doctype|html|body|table|tr|td|th)\b", re.IGNORECASE)
_STATUS_RE = re.compile(
    r"\b(?:DNS|DQ|DSQ|DNF|WD|WDR)\b|ДНС|ДСК|ДИСКВ|ДИСКВАЛ|ЗНЯТ|ВІДМОВ",
    re.IGNORECASE,
)
_PDF_ROW_RE = re.compile(r"^\s*(\d+)\s*(.+?)\s+((?:19|20)\d{2})\s+(.+)$")
_POINTS_RE = re.compile(r"(?<!\d)(\d{1,4}(?:[,.]\d{1,2})?)(?!\d)")
_TOTAL_POINTS_RE = re.compile(r"(?<!\d)(\d{1,4}[,.]\d{2})(?!\d)")


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _header_key(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.lower(), flags=re.UNICODE)


def _parse_rank(value: str) -> int | None:
    match = re.match(r"^\s*(\d+)", value)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _parse_points(value: str) -> float | None:
    text = _compact_text(value)
    if not text or _STATUS_RE.search(text):
        return None
    match = _TOTAL_POINTS_RE.search(text) or _POINTS_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _skip_non_fencer_text(value: str) -> bool:
    text = _compact_text(value)
    if not text:
        return True
    upper = text.upper()
    if _STATUS_RE.search(text):
        return True
    if upper.startswith(("РАЗОМ", "ПІДСУМОК", "П. І. П.", "МІСЦЕ", "ОЧКИ")):
        return True
    if any(marker in upper for marker in ("ТУРНІР", "РЕЙТИНГ", "ГНИТЙЕР", "ЯННЕЖДОРАН")):
        return True
    return False


def _find_header_indexes(headers: list[str]) -> dict[str, int]:
    aliases = {
        "rank": {"місце", "мiсце", "rank", "рейтинг", "пп", "номер"},
        "name": {"імя", "iмя", "піп", "спортсмен", "спортсменка", "name", "прізвище"},
        "club": {"клуб", "організація", "органiзацiя", "команда", "club", "vereine"},
        "points": {"очки", "бали", "points", "totalpoints", "разом"},
    }
    indexes: dict[str, int] = {}
    for idx, raw_header in enumerate(headers):
        key = _header_key(raw_header)
        for column, choices in aliases.items():
            if column not in indexes and key in choices:
                indexes[column] = idx
    return indexes


def _parse_html_tables(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []

    for table in soup.find_all("table"):
        header_indexes: dict[str, int] = {}

        for row in table.find_all("tr"):
            cells = [_compact_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
            cells = [cell for cell in cells if cell]
            if not cells:
                continue

            maybe_headers = _find_header_indexes(cells)
            if "rank" in maybe_headers and "name" in maybe_headers:
                header_indexes = maybe_headers
                continue

            if _skip_non_fencer_text(" ".join(cells)):
                continue

            rank_idx = header_indexes.get("rank", 0)
            name_idx = header_indexes.get("name", 1)
            club_idx = header_indexes.get("club", 2)
            points_idx = header_indexes.get("points", len(cells) - 1)

            if max(rank_idx, name_idx, club_idx, points_idx) >= len(cells):
                continue

            rank = _parse_rank(cells[rank_idx])
            name = cells[name_idx]
            points = _parse_points(cells[points_idx])
            if rank is None or not name or points is None or _skip_non_fencer_text(name):
                continue

            club = cells[club_idx] or None
            results.append({"rank": rank, "name": name, "club": club, "points": points})

    return results


def _parse_pdf_text(text: str) -> list[dict]:
    results: list[dict] = []

    for raw_line in text.splitlines():
        line = _compact_text(raw_line)
        if _skip_non_fencer_text(line):
            continue

        match = _PDF_ROW_RE.match(line)
        if not match:
            continue

        rank = _parse_rank(match.group(1))
        name = _compact_text(match.group(2))
        after_birth_year = match.group(4)
        points_match = _TOTAL_POINTS_RE.search(after_birth_year)
        if rank is None or not name or not points_match or _skip_non_fencer_text(name):
            continue

        points = _parse_points(points_match.group(1))
        if points is None:
            continue

        before_points = _compact_text(after_birth_year[: points_match.start()])
        location_and_club = before_points.split()
        club = " ".join(location_and_club[1:]) if len(location_and_club) > 1 else None
        club = club or None

        results.append({"rank": rank, "name": name, "club": club, "points": points})

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse NFFU ranking content.

    Accepts either HTML table content or text extracted from the public NFFU
    PDFs. Returns rows with rank, name, club, and points. Ukrainian Cyrillic is
    preserved, decimal commas are normalized to floats, and non-fencer/status
    rows are skipped.
    """
    if not html_or_text or not html_or_text.strip():
        return []

    if _HTML_RE.search(html_or_text):
        html_rows = _parse_html_tables(html_or_text)
        if html_rows:
            return html_rows

    return _parse_pdf_text(html_or_text)


def _extract_pdf_text(content: bytes) -> str:
    pages: list[str] = []
    with pdfplumber.open(BytesIO(content)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text(x_tolerance=1, y_tolerance=3) or "")
    return "\n".join(pages)


def build_ranking_url(weapon: str, gender: str, category: str) -> str | None:
    return RANKING_URLS.get((weapon, gender, category))


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch and decode one NFFU rankings page/PDF; return None on failure."""
    url = build_ranking_url(weapon, gender, category)
    if not url:
        print(f"    No URL configured for {weapon} {gender} {category}")
        return None

    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < MAX_ATTEMPTS:
                delay = RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
                print(f"    Request error for {url} (attempt {attempt}/{MAX_ATTEMPTS}): {exc}; retrying in {delay}s")
                time.sleep(delay)
                continue
            print(f"    Request failed for {url}: {exc}")
            return None

        if response.status_code == 404:
            print(f"    HTTP 404 for {url}")
            return None

        if response.status_code != 200:
            last_error = f"HTTP {response.status_code}"
            if attempt < MAX_ATTEMPTS:
                delay = RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
                print(f"    HTTP {response.status_code} for {url} (attempt {attempt}/{MAX_ATTEMPTS}); retrying in {delay}s")
                time.sleep(delay)
                continue
            print(f"    HTTP {response.status_code} for {url}")
            return None

        content_type = response.headers.get("content-type", "").lower()
        if "pdf" in content_type or response.content.startswith(b"%PDF"):
            try:
                return _extract_pdf_text(response.content)
            except Exception as exc:
                print(f"    PDF extraction failed for {url}: {exc}")
                return None

        return response.text

    print(f"    Request failed for {url}: {last_error}")
    return None


def current_season() -> str:
    """Return the current FIE-style season as YYYY-YYYY."""
    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "current_season"):
            season = season_utils.current_season()
            return str(season)

        if hasattr(season_utils, "current_fie_season"):
            season_value = season_utils.current_fie_season()
            if hasattr(season_utils, "season_to_string"):
                return str(season_utils.season_to_string(season_value))
            if hasattr(season_utils, "normalize_season"):
                return str(season_utils.normalize_season(season_value))
            if isinstance(season_value, int):
                return f"{season_value - 1}-{season_value}"
            return str(season_value)
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def main():
    run_log = ScraperRunLogger("scrape_fed_ukr").start()
    season = current_season()
    print(f"NFFU Ukraine rankings — season {season}")
    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")

            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                total_failed += 1
                failed_combos.append(f"{combo_label}: fetch failed")
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    total_failed += 1
                    failed_combos.append(f"{combo_label}: no rows parsed")
                    print("    No rows parsed")
                else:
                    source_url = build_ranking_url(weapon, gender, category)
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
                            metadata={"source_url": source_url} if source_url else None,
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    total_written += written
                    print(f"    Parsed {len(parsed)} rows; written {written} rows")

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "working_combos": len(RANKING_COMBOS) - total_failed,
                "total_combos": len(RANKING_COMBOS),
                "failed_combos": failed_combos,
                "base_url": BASE_URL,
            },
        )
        print(
            f"Done — written={total_written}, failed={total_failed}, "
            f"skipped={total_skipped}, working_combos={len(RANKING_COMBOS) - total_failed}/{len(RANKING_COMBOS)}"
        )
        if failed_combos:
            print("Failed combos:")
            for failed_combo in failed_combos:
                print(f"  - {failed_combo}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

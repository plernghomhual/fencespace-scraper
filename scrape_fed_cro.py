"""
scrape_fed_cro.py - Croatia HMS national rankings scraper.

Probe evidence, 2026-06-02:
  - Public index: https://hms.hr/rang-liste
  - Request method: GET
  - Index response format: server-rendered HTML.
  - Ranking data format: public PDF linked from the index. The latest probed
    2025/2026 media URL returns application/pdf and %PDF-1.7 content despite
    a .png path:
      https://v3-hms-master-uxhuxdpqnq-ew.a.run.app/media/221/463779/MediumSize/20260513-rang-hms-pdf.png/YAv9vjk7pjfsVeD.Eevz-BOCaQFupHlkDrgMlE119Y358~~221
  - Sampled PDF sections use Croatian headings and columns such as:
    RANG LISTA, FLORET JUNIORI, Rg. Prezime, Ime, Klub, Bod. Zbroj.
  - Public coverage is attempted for all 12 Senior/Junior Foil/Epee/Sabre
    Men/Women combos; missing sections are logged per combo.
"""

from __future__ import annotations

import io
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

try:
    from season_utils import season_to_string
except ImportError:  # pragma: no cover - compatibility fallback
    def season_to_string(season_int: int) -> str:
        return f"{season_int - 1:04d}-{season_int:04d}"


SOURCE = "cro_fencing"
COUNTRY = "Croatia"
BASE_URL = "https://hms.hr/rang-liste"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "hr-HR,hr;q=0.9,en;q=0.8",
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

_RANK_HEADERS = {"rank", "rang", "rg", "mjesto", "poredak", "pozicija"}
_NAME_HEADERS = {"imeiprezime", "prezimeime", "ime", "prezime", "natjecatelj", "sportas", "sportasica"}
_SURNAME_HEADERS = {"prezime"}
_GIVEN_HEADERS = {"ime"}
_CLUB_HEADERS = {"klub", "club"}
_POINT_HEADERS = {"bodovi", "bod", "bodzbroj", "zbroj", "points", "pts", "ukupnobodova"}
_SKIP_TOKENS = {
    "",
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "ret",
    "total",
    "totals",
    "ukupno",
    "sazetak",
    "summary",
    "prijava",
    "login",
    "nema",
    "nemapodataka",
}
_NO_DATA_MARKERS = {
    "nema podataka",
    "no data",
    "no rankings",
    "rang lista nije dostupna",
    "prijava",
    "login",
}
_PDF_TEXT_CACHE: dict[str, str | None] = {}


def current_season() -> str:
    """Return the current federation season range as YYYY-YYYY."""
    now = datetime.now(timezone.utc)
    season_end_year = now.year if now.month < 7 else now.year + 1
    return season_to_string(season_end_year)


def _clean_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _normalize_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(value).lower())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_text)


def _is_skip_text(value: str) -> bool:
    token = _normalize_token(value)
    return token in _SKIP_TOKENS


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value)
    if not text or _is_skip_text(text):
        return None
    match = re.match(r"^\D*(\d+)", text)
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
    if text in {"", "-", ".", ","}:
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
        elif len(parts) == 2:
            left, right = parts
            text = left + right if len(right) == 3 and left.lstrip("-").isdigit() else left + "." + right
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 2 and all(len(part) == 3 for part in parts[1:]):
            text = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0].lstrip("-")) <= 3:
            text = "".join(parts)

    try:
        return float(text)
    except ValueError:
        return None


def _header_indexes(headers: list[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for idx, header in enumerate(headers):
        token = _normalize_token(header)
        if "rank" not in indexes and token in _RANK_HEADERS:
            indexes["rank"] = idx
        elif "points" not in indexes and token in _POINT_HEADERS:
            indexes["points"] = idx
        elif "full_name" not in indexes and token in {"imeiprezime", "prezimeime", "natjecatelj"}:
            indexes["full_name"] = idx
        elif "surname" not in indexes and token in _SURNAME_HEADERS:
            indexes["surname"] = idx
        elif "given" not in indexes and token in _GIVEN_HEADERS:
            indexes["given"] = idx
        elif "club" not in indexes and token in _CLUB_HEADERS:
            indexes["club"] = idx
    return indexes


def _parse_html_tables(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for table in soup.find_all("table"):
        header_row = None
        for candidate in table.find_all("tr"):
            headers = [_clean_text(cell.get_text(" ", strip=True)) for cell in candidate.find_all(["th", "td"])]
            indexes = _header_indexes(headers)
            if "rank" in indexes and "points" in indexes and (
                "full_name" in indexes or ("surname" in indexes and "given" in indexes)
            ):
                header_row = candidate
                break
        if header_row is None:
            continue

        headers = [_clean_text(cell.get_text(" ", strip=True)) for cell in header_row.find_all(["th", "td"])]
        indexes = _header_indexes(headers)
        min_cells = max(indexes.values()) + 1

        for row in table.find_all("tr"):
            if row is header_row:
                continue
            cells = row.find_all(["td", "th"])
            if len(cells) < min_cells:
                continue

            cell_values = [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            rank = _parse_rank(cell_values[indexes["rank"]])
            if rank is None:
                continue

            if "full_name" in indexes:
                name = cell_values[indexes["full_name"]]
            else:
                surname = cell_values[indexes["surname"]]
                given = cell_values[indexes["given"]]
                name = _clean_text(f"{surname} {given}")
            if not name or _is_skip_text(name):
                continue

            club = cell_values[indexes["club"]] if "club" in indexes and indexes["club"] < len(cell_values) else ""
            points = _parse_points(cell_values[indexes["points"]])
            rows.append({"rank": rank, "name": name, "club": club or None, "points": points})

    return rows


def _collect_until_markers(lines: list[str], start: int, markers: set[str]) -> tuple[list[str], int]:
    collected: list[str] = []
    idx = start
    while idx < len(lines):
        token = _normalize_token(lines[idx])
        if token in markers:
            break
        collected.append(lines[idx])
        idx += 1
    return collected, idx


def _parse_rank_surname_lines(lines: list[str]) -> tuple[list[int], list[str]]:
    ranks: list[int] = []
    surnames: list[str] = []
    for line in lines:
        match = re.match(r"^\D*(\d+)\.?\s+(.+)$", line)
        if not match:
            continue
        rank = _parse_rank(match.group(1))
        surname = _clean_text(match.group(2))
        if rank is None or not surname or _is_skip_text(surname):
            continue
        ranks.append(rank)
        surnames.append(surname)
    return ranks, surnames


def _parse_points_lines(lines: list[str]) -> list[float | None]:
    points: list[float | None] = []
    for line in lines:
        numbers = re.findall(r"-?\d+(?:[.,]\d+)*", line)
        if not numbers:
            continue
        points.append(_parse_points(numbers[-1]))
    return points


def _parse_text_columns(text: str) -> list[dict]:
    lines = [_clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    rows: list[dict] = []

    for idx, line in enumerate(lines):
        token = _normalize_token(line)
        if token not in {"rgprezime", "poredakprezime", "mjestoprezime"}:
            continue

        surname_lines, next_idx = _collect_until_markers(lines, idx + 1, {"ime", "klub", "godbodzbroj", "bodzbroj"})
        ranks, surnames = _parse_rank_surname_lines(surname_lines)
        if not ranks:
            continue

        given_names: list[str] = []
        clubs: list[str] = []
        points: list[float | None] = []

        if next_idx < len(lines) and _normalize_token(lines[next_idx]) == "ime":
            given_names, next_idx = _collect_until_markers(lines, next_idx + 1, {"klub", "godbodzbroj", "bodzbroj"})
        if next_idx < len(lines) and _normalize_token(lines[next_idx]) == "klub":
            clubs, next_idx = _collect_until_markers(lines, next_idx + 1, {"god", "godbodzbroj", "bodzbroj", "bodovi"})
        if next_idx < len(lines) and _normalize_token(lines[next_idx]) in {"god", "godbodzbroj", "bodzbroj", "bodovi"}:
            points = _parse_points_lines(lines[next_idx + 1 : next_idx + 1 + len(ranks)])

        for row_idx, rank in enumerate(ranks):
            surname = surnames[row_idx] if row_idx < len(surnames) else ""
            given = given_names[row_idx] if row_idx < len(given_names) else ""
            name = _clean_text(f"{surname} {given}")
            if not name or _is_skip_text(name):
                continue
            club = clubs[row_idx] if row_idx < len(clubs) and clubs[row_idx] else None
            point_value = points[row_idx] if row_idx < len(points) else None
            rows.append({"rank": rank, "name": name, "club": club, "points": point_value})

    return rows


def _parse_text_rows(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        cleaned = _clean_text(line)
        if not cleaned:
            continue
        match = re.match(r"^\D*(\d+)\.?\s+(.+?)\s{2,}(.+?)\s{2,}([0-9][0-9.,]*)$", cleaned)
        if not match:
            continue
        rank = _parse_rank(match.group(1))
        if rank is None:
            continue
        name = _clean_text(match.group(2))
        if not name or _is_skip_text(name):
            continue
        rows.append(
            {
                "rank": rank,
                "name": name,
                "club": _clean_text(match.group(3)) or None,
                "points": _parse_points(match.group(4)),
            }
        )
    return rows


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Croatian HMS ranking HTML or extracted PDF text."""
    if not html_or_text:
        return []

    lowered = html_or_text.lower()
    if any(marker in lowered for marker in _NO_DATA_MARKERS) and "<table" not in lowered:
        return []

    rows = _parse_html_tables(html_or_text)
    if rows:
        return rows

    rows = _parse_text_columns(html_or_text)
    if rows:
        return rows

    return _parse_text_rows(html_or_text)


def _extract_latest_pdf_url(html: str) -> str | None:
    soup = BeautifulSoup(html or "", "html.parser")
    candidates: list[tuple[tuple[int, int, int], str]] = []

    for anchor in soup.find_all("a", href=True):
        text = _clean_text(anchor.get_text(" ", strip=True))
        href = anchor["href"]
        combined = f"{text} {href}".lower()
        if "rang" not in combined or "hms" not in combined:
            continue
        if "pdf" not in combined and "rang-hms" not in combined:
            continue

        match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
        if not match:
            match = re.search(r"(\d{4})(\d{2})(\d{2})", href)
            if match:
                year, month, day = match.groups()
            else:
                year = month = day = "0"
        else:
            day, month, year = match.groups()

        candidates.append(((int(year), int(month), int(day)), urljoin(BASE_URL, href)))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _extract_pdf_text(pdf_bytes: bytes) -> str | None:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
        print(f"    pdfplumber unavailable for HMS PDF extraction: {exc}")
        return None

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page_text = []
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                if text:
                    page_text.append(text)
        return "\n".join(page_text)
    except Exception as exc:
        print(f"    PDF text extraction failed: {exc}")
        return None


def _request_with_retries(method: str, url: str, *, attempts: int = 3, **kwargs):
    last_exc = None
    last_response = None
    for attempt in range(1, attempts + 1):
        try:
            response = federation_request(method, url, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < attempts:
                time.sleep(0.25 * attempt)
                continue
            raise

        last_response = response
        if response.status_code in {403, 429} or response.status_code >= 500:
            if attempt < attempts:
                print(f"    HTTP {response.status_code} for {url}; retrying")
                time.sleep(0.25 * attempt)
                continue
        return response

    if last_exc:
        raise last_exc
    return last_response


def _get_latest_pdf_text() -> str | None:
    if "latest" in _PDF_TEXT_CACHE:
        return _PDF_TEXT_CACHE["latest"]

    try:
        response = _request_with_retries("get", BASE_URL, headers=HEADERS, timeout=25, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    HMS ranking index request error: {exc}")
        _PDF_TEXT_CACHE["latest"] = None
        return None

    if response.status_code != 200:
        print(f"    HMS ranking index HTTP {response.status_code} for {BASE_URL}")
        _PDF_TEXT_CACHE["latest"] = None
        return None

    _PDF_TEXT_CACHE["index_html"] = response.text
    pdf_url = _extract_latest_pdf_url(response.text)
    if not pdf_url:
        print(f"    No scrapeable rankings at {BASE_URL}")
        _PDF_TEXT_CACHE["latest"] = None
        return None

    try:
        pdf_response = _request_with_retries("get", pdf_url, headers=HEADERS, timeout=45, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    HMS ranking PDF request error for {pdf_url}: {exc}")
        _PDF_TEXT_CACHE["latest"] = None
        return None

    if pdf_response.status_code != 200:
        print(f"    HMS ranking PDF HTTP {pdf_response.status_code} for {pdf_url}")
        _PDF_TEXT_CACHE["latest"] = None
        return None

    content = pdf_response.content or pdf_response.text.encode("utf-8", errors="ignore")
    content_type = (pdf_response.headers or {}).get("content-type", "").lower()
    if content.startswith(b"%PDF") or "pdf" in content_type:
        text = _extract_pdf_text(content)
    else:
        text = pdf_response.text

    _PDF_TEXT_CACHE["latest"] = text
    _PDF_TEXT_CACHE["latest_url"] = pdf_url
    if text:
        set_state(SOURCE, "last_pdf_url", pdf_url)
    return text


def _combo_title(weapon: str, gender: str, category: str) -> str:
    weapon_map = {"Foil": "FLORET", "Epee": "MAČ", "Sabre": "SABLJA"}
    category_map = {
        ("Senior", "Men"): "SENIORI",
        ("Senior", "Women"): "SENIORKE",
        ("Junior", "Men"): "JUNIORI",
        ("Junior", "Women"): "JUNIORKE",
    }
    return f"{weapon_map[weapon]} {category_map[(category, gender)]}"


def _line_matches_combo(line: str, weapon: str, gender: str, category: str) -> bool:
    target = _normalize_token(_combo_title(weapon, gender, category))
    return target in _normalize_token(line)


def _is_combo_heading(line: str) -> bool:
    token = _normalize_token(line)
    weapon_tokens = {"floret", "mac", "sablja"}
    category_tokens = {"seniori", "seniorke", "juniori", "juniorke"}
    return any(weapon in token for weapon in weapon_tokens) and any(cat in token for cat in category_tokens)


def _extract_combo_section(text: str, weapon: str, gender: str, category: str) -> str | None:
    lines = text.splitlines()
    start_idx = None
    for idx, line in enumerate(lines):
        if _line_matches_combo(line.strip(), weapon, gender, category):
            start_idx = idx
            break
    if start_idx is None:
        return None

    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        if _is_combo_heading(lines[idx].strip()):
            end_idx = idx
            break
    section = "\n".join(lines[start_idx:end_idx]).strip()
    return section or None


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Return extracted text for one HMS ranking combo, or None on failure."""
    full_text = _get_latest_pdf_text()
    if not full_text:
        return None

    section = _extract_combo_section(full_text, weapon, gender, category)
    if not section:
        print(f"    No public ranking section for {weapon} {gender} {category}")
        return None
    return section


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main():
    run_log = ScraperRunLogger("scrape_fed_cro").start()
    season = current_season()
    print(f"Croatia HMS rankings - season {season}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []
    skipped_combos: list[str] = []

    try:
        last_pdf_url = get_state(SOURCE, "last_pdf_url")
        for weapon, gender, category in RANKING_COMBOS:
            label = _combo_label(weapon, gender, category)
            print(f"  {label}...")

            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                total_failed += 1
                failed_combos.append(label)
                time.sleep(REQUEST_DELAY)
                continue

            parsed = parse_rankings_table(content)
            if not parsed:
                print("    No rows parsed")
                total_skipped += 1
                skipped_combos.append(label)
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
                    metadata={"source_url": BASE_URL},
                )
                for row in parsed
            ]
            written = write_rankings(rows, source=SOURCE, season=season)
            print(f"    Written {written} rows ({len(parsed)} parsed)")
            total_written += written
            time.sleep(REQUEST_DELAY)

        summary = {
            "season": season,
            "combos": len(RANKING_COMBOS),
            "failed_combos": failed_combos,
            "skipped_combos": skipped_combos,
            "last_pdf_url": _PDF_TEXT_CACHE.get("latest_url") or last_pdf_url,
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
            f"written={total_written}, failed={total_failed}, skipped={total_skipped}"
        )
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
        if skipped_combos:
            print(f"Skipped combos: {', '.join(skipped_combos)}")
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

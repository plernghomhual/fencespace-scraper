"""
scrape_fed_tha.py - Thailand Fencing Federation national rankings scraper.

Probe evidence, 2026-06-02:
  - Source page: https://thaifencing.org/
  - Request method: GET
  - Homepage response format: text/html
  - Public ranking files: Google Drive PDF links under "Ranking 2024 - 2025 Season"
  - Public combos: Senior and U20/Junior for Foil/Epee/Sabre, Men/Women.

The homepage currently exposes Thai link labels:
  เอเป้บุคคลชาย, ฟอยล์บุคคลชาย, เซเบอร์บุคคลชาย,
  เอเป้บุคคลหญิง, ฟอยล์บุคคลหญิง, เซเบอร์บุคคลหญิง.
"""

from __future__ import annotations

import io
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import pdfplumber
import requests
from bs4 import BeautifulSoup, Tag

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "tha_fencing"
COUNTRY = "Thailand"
BASE_URL = "https://thaifencing.org/"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "th,en-US;q=0.8,en;q=0.6",
    "Referer": BASE_URL,
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

DEFAULT_RANKING_URLS = {
    ("Epee", "Men", "Senior"): "https://drive.google.com/file/d/1BiYZ6yFtIoGZ0JqWn9yD3E__CODDTbGJ/view?usp=sharing",
    ("Foil", "Men", "Senior"): "https://drive.google.com/file/d/1SFV0w0iFaAmtyxlXL6kJVzf3ExobJFW_/view?usp=sharing",
    ("Sabre", "Men", "Senior"): "https://drive.google.com/file/d/1QcLpJDW2U5JpUfvGlwY7uFS706CO2i9Z/view?usp=sharing",
    ("Epee", "Women", "Senior"): "https://drive.google.com/file/d/11iUk09vVUEZFsxfV-XzFzqjAaDX0YZbe/view?usp=sharing",
    ("Foil", "Women", "Senior"): "https://drive.google.com/file/d/1aM-L6snsNZYObbR_RGv9JnkNjJUX0mDf/view?usp=sharing",
    ("Sabre", "Women", "Senior"): "https://drive.google.com/file/d/13txB0W6y_W0bdEFihqvdVOggOV5HauTL/view?usp=sharing",
    ("Epee", "Men", "Junior"): "https://drive.google.com/file/d/1AosLBPkEd_2qf6M4jk-25qO1f2sSCSXl/view?usp=sharing",
    ("Foil", "Men", "Junior"): "https://drive.google.com/file/d/1Q6oAZ6F_kD8cURwZ6pYBi6vkONUBA7KH/view?usp=sharing",
    ("Sabre", "Men", "Junior"): "https://drive.google.com/file/d/1pzaI6TWRSrtSXVj9tiRf_Zy4JHNIlT9H/view?usp=sharing",
    ("Epee", "Women", "Junior"): "https://drive.google.com/file/d/16hUkqDuCkQ3rKcxe4r1xqJ-6wxLTxiUf/view?usp=sharing",
    ("Foil", "Women", "Junior"): "https://drive.google.com/file/d/1AtC_Dl2vkc9AaSOqvw5spw_iWd1VOsrl/view?usp=sharing",
    ("Sabre", "Women", "Junior"): "https://drive.google.com/file/d/1EKz9zeQ6gMPpnBgxWRSt01flS4GMVSn3/view?usp=sharing",
}

_RANKING_URL_CACHE: dict[tuple[str, str, str], str] | None = None
_RANKING_CONTENT_CACHE: dict[str, str] = {}
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

RANK_HEADER_ALIASES = {"rank", "ranking", "no", "place", "position", "อันดับ", "ลำดับ"}
NAME_HEADER_ALIASES = {
    "name",
    "fencer",
    "athlete",
    "ชื่อ",
    "นักกีฬา",
    "ชื่อนักกีฬา",
    "ชื่อสกุล",
    "ชื่อนามสกุล",
}
CLUB_HEADER_ALIASES = {"club", "clubs", "team", "สโมสร", "ชมรม", "หน่วยงาน", "สังกัด"}
POINT_HEADER_ALIASES = {
    "points",
    "point",
    "pts",
    "score",
    "totalpoints",
    "คะแนน",
    "คะแนนรวม",
    "คะแนนสะสม",
}
SKIP_TOKENS = {
    "",
    "dns",
    "dnf",
    "dq",
    "dsq",
    "wd",
    "wdr",
    "ret",
    "total",
    "totals",
    "summary",
    "subtotal",
    "รวม",
    "สรุป",
    "สรุปคะแนน",
    "คะแนนรวม",
    "ถอนตัว",
    "ถูกตัดสิทธิ์",
}
NO_DATA_MARKERS = (
    "ไม่มีข้อมูล",
    "ไม่พบข้อมูล",
    "no data",
    "no rankings",
    "no ranking",
)


def _clean_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _header_key(value: str) -> str:
    text = _clean_text(value).translate(_THAI_DIGITS).lower()
    text = text.replace("&", " and ")
    return re.sub(r"[^a-z0-9\u0e00-\u0e7f]+", "", text)


def _is_skip_text(value: str) -> bool:
    key = _header_key(value)
    if key in SKIP_TOKENS:
        return True
    return any(token and token in key for token in {"summary", "total", "รวม", "สรุป"})


def _parse_rank(value: str) -> int | None:
    text = _clean_text(value).translate(_THAI_DIGITS).strip().rstrip(".")
    if not text or _is_skip_text(text):
        return None
    match = re.match(r"^(\d+)", text)
    if not match:
        return None
    rank = int(match.group(1))
    return rank if rank > 0 else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value).translate(_THAI_DIGITS)
    if not text or _is_skip_text(text) or text in {"-", "—", "–"}:
        return None

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
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            text = f"{parts[0]}.{parts[1]}"
        else:
            text = text.replace(",", "")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 2 and all(len(part) == 3 for part in parts[1:]):
            text = "".join(parts)

    try:
        return float(text)
    except ValueError:
        return None


def _row_cells(row: Tag) -> list[Tag]:
    return row.find_all(["td", "th"], recursive=False)


def _html_tables_to_matrices(html: str) -> list[list[list[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    matrices = []
    for table in soup.find_all("table"):
        matrix = []
        for row in table.find_all("tr"):
            if row.find_parent("table") is not table:
                continue
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in _row_cells(row)]
            if cells:
                matrix.append(cells)
        if matrix:
            matrices.append(matrix)
    return matrices


def _text_to_matrix(text: str) -> list[list[str]]:
    matrix = []
    for raw_line in text.splitlines():
        line = str(raw_line).replace("\xa0", " ").strip()
        if not line:
            continue
        if "\t" in line:
            cells = [_clean_text(part) for part in line.split("\t")]
        elif "|" in line:
            cells = [_clean_text(part) for part in line.split("|")]
        else:
            cells = [_clean_text(part) for part in re.split(r"\s{2,}", line)]
            if len(cells) < 3:
                fallback = re.match(r"^(\d+)\s+(.+?)\s+([0-9][0-9,.\s]*)$", line.translate(_THAI_DIGITS))
                if fallback:
                    cells = [fallback.group(1), fallback.group(2), "", fallback.group(3)]
        cells = [cell for cell in cells if cell]
        if cells:
            matrix.append(cells)
    return matrix


def _detect_columns(cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(cells):
        key = _header_key(cell)
        if key in RANK_HEADER_ALIASES and "rank" not in mapping:
            mapping["rank"] = index
        elif key in NAME_HEADER_ALIASES and "name" not in mapping:
            mapping["name"] = index
        elif key in CLUB_HEADER_ALIASES and "club" not in mapping:
            mapping["club"] = index
        elif key in POINT_HEADER_ALIASES and "points" not in mapping:
            mapping["points"] = index
    return mapping


def _append_row(results: list[dict], mapping: dict[str, int], cells: list[str]) -> None:
    if not {"rank", "name"}.issubset(mapping):
        return
    if len(cells) <= max(mapping.values()):
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

    points = None
    if "points" in mapping and mapping["points"] < len(cells):
        points = _parse_points(cells[mapping["points"]])
    elif len(cells) > max(mapping.values()) + 1:
        points = _parse_points(cells[-1])

    results.append({"rank": rank, "name": name, "club": club, "points": points})


def _parse_matrix(matrix: list[list[str]]) -> list[dict]:
    results: list[dict] = []
    mapping: dict[str, int] | None = None
    seen: set[tuple[int, str]] = set()

    for cells in matrix:
        if not cells or any(_is_skip_text(cell) for cell in cells[:1]):
            continue

        candidate = _detect_columns(cells)
        if {"rank", "name"}.issubset(candidate):
            mapping = candidate
            continue

        if mapping is None:
            if len(cells) >= 3 and _parse_rank(cells[0]) is not None:
                mapping = {"rank": 0, "name": 1}
                if len(cells) >= 3:
                    mapping["club"] = 2
                if len(cells) >= 4:
                    mapping["points"] = len(cells) - 1
            else:
                continue

        before = len(results)
        _append_row(results, mapping, cells)
        if len(results) == before:
            continue

        key = (results[-1]["rank"], results[-1]["name"])
        if key in seen:
            results.pop()
        else:
            seen.add(key)

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Thailand ranking HTML/PDF-extracted text into rank/name/club/points rows."""
    if not html_or_text or not html_or_text.strip():
        return []

    lowered = html_or_text.lower()
    if any(marker in lowered for marker in NO_DATA_MARKERS):
        return []

    parsed: list[dict] = []
    for matrix in _html_tables_to_matrices(html_or_text):
        parsed.extend(_parse_matrix(matrix))
    if parsed:
        return parsed

    text = BeautifulSoup(html_or_text, "html.parser").get_text("\n", strip=True)
    return _parse_matrix(_text_to_matrix(text))


def _weapon_from_label(label: str) -> str | None:
    if "เอเป้" in label or "epee" in label.lower():
        return "Epee"
    if "ฟอยล์" in label or "foil" in label.lower():
        return "Foil"
    if "เซเบอร์" in label or "sabre" in label.lower() or "saber" in label.lower():
        return "Sabre"
    return None


def _gender_from_label(label: str) -> str | None:
    lowered = label.lower()
    if "หญิง" in label or "women" in lowered or re.search(r"\bwf\b|\bwe\b|\bws\b", lowered):
        return "Women"
    if "ชาย" in label or "men" in lowered or re.search(r"\bmf\b|\bme\b|\bms\b", lowered):
        return "Men"
    return None


def _category_from_heading(text: str) -> str | None:
    lowered = text.lower()
    if "cadet" in lowered or "veteran" in lowered or "team" in lowered:
        return None
    if "รุ่นอายุไม่เกิน 17" in text or "อาวุโส" in text or "ประเภททีม" in text:
        return None
    if "junior" in lowered or "u20" in lowered or "อายุไม่เกิน 20" in text:
        return "Junior"
    if "senior" in lowered or "รุ่นทั่วไป" in text:
        return "Senior"
    return None


def _extract_ranking_urls(html: str) -> dict[tuple[str, str, str], str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: dict[tuple[str, str, str], str] = {}
    current_category: str | None = None

    for element in soup.find_all(["h1", "h2", "h3", "h4", "strong", "p", "a"]):
        text = _clean_text(element.get_text(" ", strip=True))
        if not text:
            continue

        heading_category = _category_from_heading(text)
        if heading_category is not None:
            current_category = heading_category
        elif any(marker in text.lower() for marker in ("cadet", "veteran", "team")):
            current_category = None
        elif any(marker in text for marker in ("รุ่นอายุไม่เกิน 17", "อาวุโส", "ประเภททีม")):
            current_category = None

        if element.name != "a" or current_category not in {"Senior", "Junior"}:
            continue

        href = element.get("href", "")
        if "drive.google.com" not in href:
            continue

        weapon = _weapon_from_label(text)
        gender = _gender_from_label(text)
        if weapon and gender:
            urls[(weapon, gender, current_category)] = urljoin(BASE_URL, href)

    return urls


def _discover_ranking_urls() -> dict[tuple[str, str, str], str]:
    global _RANKING_URL_CACHE
    if _RANKING_URL_CACHE is not None:
        return _RANKING_URL_CACHE

    discovered: dict[tuple[str, str, str], str] = {}
    try:
        response = federation_request("get", BASE_URL, headers=HEADERS, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Ranking index request error for {BASE_URL}: {exc}")
    else:
        if response.status_code == 200:
            discovered = _extract_ranking_urls(response.text)
        else:
            print(f"    Ranking index HTTP {response.status_code} for {BASE_URL}")

    merged = dict(DEFAULT_RANKING_URLS)
    merged.update(discovered)
    _RANKING_URL_CACHE = merged
    return merged


def _ranking_url_for(weapon: str, gender: str, category: str) -> str | None:
    return _discover_ranking_urls().get((weapon, gender, category))


def _google_drive_file_id(url: str) -> str | None:
    match = re.search(r"/file/d/([^/]+)", url)
    if match:
        return match.group(1)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    ids = query.get("id")
    return ids[0] if ids else None


def _download_url(url: str) -> str:
    file_id = _google_drive_file_id(url)
    if file_id:
        return f"https://drive.google.com/uc?{urlencode({'export': 'download', 'id': file_id})}"
    return url


def _is_pdf_response(response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    return response.content.startswith(b"%PDF") or "application/pdf" in content_type


def _looks_login_or_js_only(text: str) -> bool:
    lowered = text.lower()
    login_markers = ("sign in", "accounts.google.com", "login", "เข้าสู่ระบบ")
    js_markers = ("enable javascript", "loading...", "javascript is disabled")
    return any(marker in lowered for marker in login_markers + js_markers)


def _extract_drive_confirm_url(response) -> str | None:
    soup = BeautifulSoup(response.text, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "uc?export=download" in href or "download" in href.lower():
            return urljoin(response.url, href)
    form = soup.find("form", action=True)
    if form and "download" in form["action"].lower():
        action = urljoin(response.url, form["action"])
        inputs = {
            input_tag.get("name"): input_tag.get("value", "")
            for input_tag in form.find_all("input")
            if input_tag.get("name")
        }
        if inputs:
            separator = "&" if urlparse(action).query else "?"
            return f"{action}{separator}{urlencode(inputs)}"
        return action
    return None


def _fetch_url_with_retries(url: str, *, attempts: int = 3):
    last_response = None
    for attempt in range(1, attempts + 1):
        try:
            response = federation_request("get", url, headers=HEADERS, timeout=35, allow_redirects=True)
        except requests.RequestException as exc:
            print(f"    Request error for {url}: {exc}")
            response = None
        if response is None:
            if attempt < attempts:
                time.sleep(REQUEST_DELAY * attempt)
            continue

        last_response = response
        if response.status_code not in {403, 429} and response.status_code < 500:
            return response
        if attempt < attempts:
            print(f"    HTTP {response.status_code} for {url}; retrying")
            time.sleep(REQUEST_DELAY * attempt)

    return last_response


def _extract_pdf_text(content: bytes) -> str:
    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    cells = [_clean_text(cell) for cell in row or []]
                    while cells and not cells[-1]:
                        cells.pop()
                    if any(cells):
                        lines.append("\t".join(cells))
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            if text:
                lines.extend(text.splitlines())
    return "\n".join(lines)


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch one Thailand ranking PDF/HTML page. Returns None on 404/network/login/JS failures."""
    source_url = _ranking_url_for(weapon, gender, category)
    if not source_url:
        print(f"    No scrapeable rankings at {BASE_URL} for {weapon} {gender} {category}")
        return None

    if source_url in _RANKING_CONTENT_CACHE:
        return _RANKING_CONTENT_CACHE[source_url]

    url = _download_url(source_url)
    response = _fetch_url_with_retries(url)
    if response is None:
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    if _is_pdf_response(response):
        try:
            content = _extract_pdf_text(response.content)
        except Exception as exc:
            print(f"    PDF parse error for {source_url}: {exc}")
            return None
        _RANKING_CONTENT_CACHE[source_url] = content
        return content

    confirm_url = _extract_drive_confirm_url(response)
    if confirm_url and confirm_url != url:
        confirmed = _fetch_url_with_retries(confirm_url, attempts=2)
        if confirmed and confirmed.status_code == 200 and _is_pdf_response(confirmed):
            try:
                content = _extract_pdf_text(confirmed.content)
            except Exception as exc:
                print(f"    PDF parse error for {source_url}: {exc}")
                return None
            _RANKING_CONTENT_CACHE[source_url] = content
            return content

    if _looks_login_or_js_only(response.text):
        print(f"    No scrapeable rankings at {source_url}: login-only or JS-only response")
        return None

    _RANKING_CONTENT_CACHE[source_url] = response.text
    return response.text


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY, normalized through season_utils when present."""
    now = datetime.now(timezone.utc)
    start_year = now.year - 1 if now.month < 7 else now.year
    season = f"{start_year}-{start_year + 1}"
    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "normalize_season"):
            normalized = season_utils.normalize_season(season)
            if isinstance(normalized, str):
                return normalized
    except Exception:
        pass
    return season


def _combo_label(weapon: str, gender: str, category: str) -> str:
    return f"{weapon} {gender} {category}"


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_tha").start()
    season = current_season()
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous Thailand federation run state found: {previous_state}")

    print(f"Thailand federation rankings - season {season}")
    print(f"Ranking source page: {BASE_URL}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos: list[str] = []
    failed_combos: list[str] = []

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            label = _combo_label(weapon, gender, category)
            print(f"  {label}...")

            content = fetch_rankings_page(weapon, gender, category)
            source_url = _ranking_url_for(weapon, gender, category)
            if not content:
                failed_combos.append(label)
                total_failed += 1
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    print("    No rows parsed")
                    failed_combos.append(label)
                    total_failed += 1
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
                            metadata={
                                "source_url": source_url,
                                "source_page": BASE_URL,
                                "source_format": "pdf",
                            },
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    print(f"    Parsed {len(parsed)} rows; written {written} rows")
                    total_written += written
                    working_combos.append(label)

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        state = {
            "season": season,
            "source_page": BASE_URL,
            "combos_working": len(working_combos),
            "combos_total": len(RANKING_COMBOS),
            "working_combos": working_combos,
            "failed_combos": failed_combos,
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
            f"combos_working={len(working_combos)}/{len(RANKING_COMBOS)}"
        )
    except Exception as exc:
        set_state(SOURCE, "last_error", {"season": season, "error": str(exc)})
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

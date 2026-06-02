"""
scrape_fed_jpn.py — Japan Fencing Association national rankings scraper.

Probe findings (2026-06-01):
  - Working host: https://fencing-jpn.jp/
  - jfa-fencing.jp DNS lookup failed.
  - /cms/wp-json/ search/media endpoints returned 404.
  - Rankings are public PDF files under /cms/wp-content/uploads/2025/04/.
  - Request method: GET with browser-like headers.
  - Response format: application/pdf.
  - Public coverage: all 12 Senior/Junior Foil/Epee/Sabre Men/Women combos.

PDF table columns:
  順位 | 氏名 | 所属 | 2025年協会登録 | カテゴリ | 獲得総得点 | ...

Names are stored as-is in Japanese source order.
"""

from __future__ import annotations

import io
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "jpn_fencing"
COUNTRY = "JPN"
BASE_URL = "https://fencing-jpn.jp"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
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

PDF_PATHS = {
    ("Foil", "Men", "Senior"): "/cms/wp-content/uploads/2025/04/859382aab860ab59bb88adc59523218c.pdf",
    ("Foil", "Women", "Senior"): "/cms/wp-content/uploads/2025/04/6b3ec9acce0375c575fc1be4eee53039.pdf",
    ("Epee", "Men", "Senior"): "/cms/wp-content/uploads/2025/04/47ecf725ac5115134bfd302f900bfcab.pdf",
    ("Epee", "Women", "Senior"): "/cms/wp-content/uploads/2025/04/a720e4363c74c0ee37af6ffdc36104dd.pdf",
    ("Sabre", "Men", "Senior"): "/cms/wp-content/uploads/2025/04/99c0df89814e5ed4c16e8019c7b405af.pdf",
    ("Sabre", "Women", "Senior"): "/cms/wp-content/uploads/2025/04/c1c4ba060b7e97131d174f188d1e74a2.pdf",
    ("Foil", "Men", "Junior"): "/cms/wp-content/uploads/2025/04/ce7e5978f4e3d55823d442bae223b3aa.pdf",
    ("Foil", "Women", "Junior"): "/cms/wp-content/uploads/2025/04/153de5ea9276a3f92dff1dc93e6ce03c.pdf",
    ("Epee", "Men", "Junior"): "/cms/wp-content/uploads/2025/04/77f441670a428cbaf54665c236472d15.pdf",
    ("Epee", "Women", "Junior"): "/cms/wp-content/uploads/2025/04/d53e716de6f2746ab07b98601a3d61bb.pdf",
    ("Sabre", "Men", "Junior"): "/cms/wp-content/uploads/2025/04/bcc6828348c3e63f0fb553dd3741264d.pdf",
    ("Sabre", "Women", "Junior"): "/cms/wp-content/uploads/2025/04/aa41f72cee1e7eef0cf691d6da194a63.pdf",
}

_RANK_HEADERS = {"順位", "rank", "#"}
_NAME_HEADERS = {"氏名", "選手名", "名前", "name", "athlete"}
_CLUB_HEADERS = {"所属", "所属先", "団体名", "チーム", "club", "team"}
_POINTS_HEADERS = {"得点", "獲得総得点", "総得点", "合計点", "points", "point", "pts"}
_SKIP_ROW_MARKERS = {
    "dns",
    "dq",
    "棄権",
    "失格",
    "合計",
    "総合",
    "順位",
    "氏名",
    "選手名",
}
_CATEGORY_TOKENS = {"S", "U23", "J", "C", "#######"}


def ranking_url(weapon: str, gender: str, category: str) -> str | None:
    path = PDF_PATHS.get((weapon, gender, category))
    return f"{BASE_URL}{path}" if path else None


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text).lower().strip()


def _parse_rank(raw: str) -> int | None:
    text = raw.strip()
    if not text or _compact(text) in _SKIP_ROW_MARKERS:
        return None
    if not re.fullmatch(r"\d+", text):
        return None
    return int(text)


def _parse_points(raw: str) -> float | None:
    text = raw.strip().replace("\u00a0", "").replace(" ", "")
    if not text or text in {"-", "—", "DNS", "DQ"}:
        return None
    if re.fullmatch(r"\d{1,3}(,\d{3})+", text):
        text = text.replace(",", "")
    elif "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _is_skip_line(line: str) -> bool:
    compact = _compact(line)
    if not compact:
        return True
    if compact.startswith(("※", "注", "2025年度", "2025/")):
        return True
    if "ランキング表" in compact or "公開されているランキングはありません" in compact:
        return True
    if compact in _SKIP_ROW_MARKERS:
        return True
    return False


def _detect_columns(cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(cells):
        key = _compact(raw)
        if key in _RANK_HEADERS and "rank_col" not in mapping:
            mapping["rank_col"] = idx
        elif key in _NAME_HEADERS and "name_col" not in mapping:
            mapping["name_col"] = idx
        elif key in _CLUB_HEADERS and "club_col" not in mapping:
            mapping["club_col"] = idx
        elif key in _POINTS_HEADERS and "points_col" not in mapping:
            mapping["points_col"] = idx
    return mapping


def _append_row(
    rows: list[dict],
    *,
    rank: int | None,
    name: str,
    club: str | None,
    points: float | None,
) -> None:
    name = re.sub(r"\s+", " ", name).strip()
    club = re.sub(r"\s+", " ", club).strip() if club else None
    if rank is None or not name:
        return
    rows.append({"rank": rank, "name": name, "club": club or None, "points": points})


def _parse_html_table(text: str) -> list[dict]:
    soup = BeautifulSoup(text, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows: list[dict] = []
    col_map: dict[str, int] = {}
    for tr in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
        if not cells:
            continue

        detected = _detect_columns(cells)
        if "rank_col" in detected and "name_col" in detected:
            col_map = detected
            continue

        if col_map:
            needed = max(col_map.values())
            if len(cells) <= needed:
                continue
            rank = _parse_rank(cells[col_map["rank_col"]])
            name = cells[col_map["name_col"]]
            club = cells[col_map["club_col"]] if "club_col" in col_map else None
            points = _parse_points(cells[col_map["points_col"]]) if "points_col" in col_map else None
            _append_row(rows, rank=rank, name=name, club=club, points=points)
            continue

        if len(cells) >= 4:
            rank = _parse_rank(cells[0])
            points = _parse_points(cells[-1])
            _append_row(rows, rank=rank, name=cells[1], club=cells[2], points=points)

    return rows


def _parse_pipe_line(line: str) -> dict | None:
    cells = [part.strip() for part in re.split(r"\s*\|\s*", line.strip())]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    if len(cells) < 4:
        return None

    rank = _parse_rank(cells[0])
    if rank is None:
        return None

    name = cells[1].strip()
    club = cells[2].strip() if len(cells) > 2 else None
    points_idx = 5 if len(cells) > 5 else 3
    points = _parse_points(cells[points_idx])
    return {"rank": rank, "name": name, "club": club or None, "points": points}


def _parse_whitespace_line(line: str) -> dict | None:
    if _is_skip_line(line):
        return None

    match = re.match(
        r"^\s*(?P<rank>\d+)\s+"
        r"(?P<name>\S+)\s+"
        r"(?P<club>.+?)\s+"
        r"(?:(?:F\d{4,}|#N/A)\s+)?"
        r"(?P<category>S|U23|J|C|#######)\s+"
        r"(?P<points>\d+(?:[,.]\d+)?)\b",
        line,
    )
    if not match:
        return None

    rank = _parse_rank(match.group("rank"))
    points = _parse_points(match.group("points"))
    return {
        "rank": rank,
        "name": match.group("name").strip(),
        "club": match.group("club").strip() or None,
        "points": points,
    }


def _parse_text_table(text: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[int, str]] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if _is_skip_line(line):
            continue

        parsed = _parse_pipe_line(line) if "|" in line else _parse_whitespace_line(line)
        if not parsed:
            continue

        key = (parsed["rank"], parsed["name"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(parsed)

    return rows


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse Japan federation ranking content.

    Accepts server-rendered HTML tables if the source changes, and PDF-extracted
    text from current public ranking PDFs. Returns dictionaries with rank, name,
    club, and points. DNS/DQ/header/summary rows are skipped.
    """
    if not html_or_text or not html_or_text.strip():
        return []

    html_rows = _parse_html_table(html_or_text)
    if html_rows:
        return html_rows

    text = BeautifulSoup(html_or_text, "html.parser").get_text("\n", strip=True)
    return _parse_text_table(text)


def _extract_pdf_text(content: bytes) -> str | None:
    try:
        import pdfplumber
    except ImportError:
        print("    pdfplumber is required to parse Japan ranking PDFs")
        return None

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        print(f"    PDF parse error: {exc}")
        return None


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch and extract ranking content for one Japan weapon/gender/category combo."""
    url = ranking_url(weapon, gender, category)
    if not url:
        print(f"    No URL configured for {weapon} {gender} {category}")
        return None

    try:
        response = federation_request("get", url, headers=HEADERS, timeout=30, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code == 404:
        print(f"    HTTP 404 for {url}")
        return None
    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    content_type = response.headers.get("content-type", "").lower()
    if "application/pdf" in content_type or response.content.startswith(b"%PDF"):
        return _extract_pdf_text(response.content)

    return response.text


def current_season() -> str:
    try:
        import season_utils

        if hasattr(season_utils, "current_season"):
            value = season_utils.current_season()
        elif hasattr(season_utils, "current_fie_season"):
            value = season_utils.current_fie_season()
        else:
            value = None

        if value is not None:
            if hasattr(season_utils, "normalize_season"):
                return season_utils.normalize_season(value)
            if hasattr(season_utils, "season_to_string"):
                return season_utils.season_to_string(value)
            if isinstance(value, int):
                return f"{value - 1}-{value}"
            return str(value)
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_jpn").start()
    season = current_season()
    print(f"JFA Japan rankings — season {season}")
    total_written = 0
    total_failed = 0
    failed_combos: list[str] = []

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")
            content = fetch_rankings_page(weapon, gender, category)
            if not content:
                total_failed += 1
                failed_combos.append(combo_label)
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append(combo_label)
                else:
                    source_url = ranking_url(weapon, gender, category)
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
                            metadata={"source_url": source_url, "format": "pdf"},
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    print(f"    Parsed {len(rows)} rows; written {written} rows")
                    total_written += written

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=0,
            metadata={"failed_combos": failed_combos, "format": "pdf"},
        )
        print(f"Done — written={total_written}, failed={total_failed}")
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
    except Exception as exc:
        run_log.error(str(exc))
        print(f"FAILED — {exc}")


if __name__ == "__main__":
    main()

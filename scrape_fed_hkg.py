"""
scrape_fed_hkg.py — Hong Kong, China Fencing Association rankings scraper.

Probe findings (2026-06-01):
  - Requested fencing.org.hk paths:
      /ranking, /rankings, /competition/ranking, /en/ranking, /tc/ranking
    failed publicly: HTTPS handshake failures, HTTP 409 challenge pages.
  - Working host: http://www.hkfa.org.hk/
  - Working index URLs:
      http://www.hkfa.org.hk/EN/ranking.html?mID=8
      http://www.hkfa.org.hk/TC/ranking.html?mID=8
  - Request method: GET with browser-like headers.
  - Response format: index pages are HTML; rankings are public PDF files.
  - Public coverage: all 12 Senior/Open and Junior/U20 Foil/Epee/Sabre
    Men/Women combos.

HKFA PDF rows are bilingual, for example:
  1 Choi Chun Yin Ryan 蔡俊彥 ... 83

The scraper stores the published English display name in ``name`` and stores
the Traditional Chinese name in ``metadata.alt_name`` when both are present.
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

SOURCE = "hkg_fencing"
COUNTRY = "HKG"
BASE_URL = "http://www.hkfa.org.hk"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-HK,zh-HK;q=0.9,en;q=0.8,zh;q=0.7",
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
    ("Foil", "Men", "Senior"): "/ranking/mf.pdf",
    ("Foil", "Women", "Senior"): "/ranking/lf.pdf",
    ("Epee", "Men", "Senior"): "/ranking/me.pdf",
    ("Epee", "Women", "Senior"): "/ranking/le.pdf",
    ("Sabre", "Men", "Senior"): "/ranking/ms.pdf",
    ("Sabre", "Women", "Senior"): "/ranking/ls.pdf",
    ("Foil", "Men", "Junior"): "/ranking/u20mf.pdf",
    ("Foil", "Women", "Junior"): "/ranking/u20lf.pdf",
    ("Epee", "Men", "Junior"): "/ranking/u20me.pdf",
    ("Epee", "Women", "Junior"): "/ranking/u20le.pdf",
    ("Sabre", "Men", "Junior"): "/ranking/u20ms.pdf",
    ("Sabre", "Women", "Junior"): "/ranking/u20ls.pdf",
}

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
_RANK_HEADERS = {"rank", "ranking", "#", "排名"}
_NAME_HEADERS = {"name", "athlete", "fencer", "姓名"}
_CLUB_HEADERS = {"club", "會", "會籍"}
_POINTS_HEADERS = {"points", "point", "pts", "score", "total", "overall", "積分"}
_SKIP_MARKERS = {"dns", "dq", "dnf", "dsq", "棄權", "棄賽", "失格"}


def ranking_url(weapon: str, gender: str, category: str) -> str | None:
    path = PDF_PATHS.get((weapon, gender, category))
    return f"{BASE_URL}{path}" if path else None


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text).strip().lower()


def _parse_rank(raw: str) -> int | None:
    text = raw.strip()
    if not re.fullmatch(r"\d+", text):
        return None
    return int(text)


def _parse_points(raw: str) -> float | None:
    text = raw.strip().replace("\u00a0", "").replace(" ", "")
    if not text or _compact(text) in _SKIP_MARKERS or text in {"-", "—"}:
        return None
    if re.fullmatch(r"\d{1,3}(,\d{3})+(?:\.\d+)?", text):
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
    if compact in _SKIP_MARKERS:
        return True
    if compact.startswith(("rankingname", "best", "least", "overall", "summary")):
        return True
    if compact.startswith(("男子", "女子", "青年組", "排名", "name姓名")):
        return True
    if "fencers" in compact or "norankingsavailable" in compact or "未有排名" in compact:
        return True
    return False


def _has_skip_marker(text: str) -> bool:
    compact = _compact(text)
    return any(marker in compact for marker in _SKIP_MARKERS)


def _split_bilingual_name(raw: str) -> tuple[str, str | None]:
    text = re.sub(r"\s+", " ", raw).strip()
    if not text:
        return "", None

    chinese_parts = _CJK_RE.findall(text)
    alt_name = " ".join(chinese_parts) if chinese_parts else None
    latin_name = _CJK_RE.sub(" ", text)
    latin_name = re.sub(r"\s+", " ", latin_name).strip()

    if latin_name and re.search(r"[A-Za-z]", latin_name):
        return latin_name, alt_name
    return text, None


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
    name_raw: str,
    club: str | None,
    points: float | None,
) -> None:
    if rank is None or _has_skip_marker(name_raw):
        return

    name, alt_name = _split_bilingual_name(name_raw)
    if not name:
        return

    clean_club = re.sub(r"\s+", " ", club).strip() if club else None
    row = {
        "rank": rank,
        "name": name,
        "club": clean_club or None,
        "points": points,
        "metadata": {},
    }
    if alt_name:
        row["metadata"]["alt_name"] = alt_name
    rows.append(row)


def _parse_html_table(content: str) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
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
            name_raw = cells[col_map["name_col"]]
            club = cells[col_map["club_col"]] if "club_col" in col_map else None
            points = _parse_points(cells[col_map["points_col"]]) if "points_col" in col_map else None
            _append_row(rows, rank=rank, name_raw=name_raw, club=club, points=points)
            continue

        if len(cells) >= 3:
            rank = _parse_rank(cells[0])
            points = _parse_points(cells[-1])
            club = cells[2] if len(cells) >= 4 else None
            _append_row(rows, rank=rank, name_raw=cells[1], club=club, points=points)

    return rows


def _parse_pipe_line(line: str) -> dict | None:
    cells = [part.strip() for part in re.split(r"\s*\|\s*", line.strip())]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    if len(cells) < 3:
        return None

    rank = _parse_rank(cells[0])
    if rank is None:
        return None
    points = _parse_points(cells[-1])
    return {"rank": rank, "name_raw": cells[1], "club": None, "points": points}


def _parse_pdf_text_line(line: str) -> dict | None:
    if _is_skip_line(line) or _has_skip_marker(line):
        return None

    match = re.match(r"^\s*(?P<rank>\d+)\s+(?P<body>.+?)\s*$", line)
    if not match:
        return None

    rank = _parse_rank(match.group("rank"))
    body = match.group("body")
    tokens = body.split()
    if len(tokens) < 2:
        return None

    points = _parse_points(tokens[-1])
    if points is None:
        return None

    chinese_idx = next((idx for idx, token in enumerate(tokens) if _CJK_RE.search(token)), None)
    if chinese_idx is not None:
        name_tokens = tokens[: chinese_idx + 1]
    else:
        first_number_idx = next((idx for idx, token in enumerate(tokens) if _parse_points(token) is not None), None)
        if first_number_idx is None or first_number_idx == 0:
            return None
        name_tokens = tokens[:first_number_idx]

    name_raw = " ".join(name_tokens)
    return {"rank": rank, "name_raw": name_raw, "club": None, "points": points}


def _parse_text_table(text: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[int, str, float | None]] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parsed = _parse_pipe_line(line) if "|" in line else _parse_pdf_text_line(line)
        if not parsed:
            continue

        key = (parsed["rank"], parsed["name_raw"], parsed["points"])
        if key in seen:
            continue
        seen.add(key)
        _append_row(
            rows,
            rank=parsed["rank"],
            name_raw=parsed["name_raw"],
            club=parsed.get("club"),
            points=parsed.get("points"),
        )

    return rows


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse HKFA ranking content.

    Accepts language-specific HTML tables and text extracted from the current
    public ranking PDFs. Returns rows with rank, name, club, points, and
    optional metadata.alt_name for Traditional Chinese names.
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
        print("    pdfplumber is required to parse HKFA ranking PDFs")
        return None

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        print(f"    PDF parse error: {exc}")
        return None


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch and extract ranking content for one HKFA weapon/gender/category combo."""
    url = ranking_url(weapon, gender, category)
    if not url:
        print(f"    No URL configured for {weapon} {gender} {category}")
        return None

    for attempt in range(2):
        try:
            response = federation_request("get", url, headers=HEADERS, timeout=30, allow_redirects=True)
        except requests.RequestException as exc:
            if attempt == 0:
                time.sleep(REQUEST_DELAY)
                continue
            print(f"    Request error for {url}: {exc}")
            return None

        if response.status_code == 404:
            print(f"    HTTP 404 for {url}")
            return None
        if response.status_code in {409, 429} or response.status_code >= 500:
            if attempt == 0:
                time.sleep(REQUEST_DELAY)
                continue
        if response.status_code != 200:
            print(f"    HTTP {response.status_code} for {url}")
            return None

        content_type = response.headers.get("content-type", "").lower()
        if "application/pdf" in content_type or response.content.startswith(b"%PDF"):
            return _extract_pdf_text(response.content)
        return response.text

    return None


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


def _storage_rank(rank: int, used_ranks: set[int], ordinal: int) -> tuple[int, dict]:
    if rank not in used_ranks:
        used_ranks.add(rank)
        return rank, {}

    storage_rank = ordinal
    while storage_rank in used_ranks:
        storage_rank += 1
    used_ranks.add(storage_rank)
    return storage_rank, {"published_rank": rank}


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_hkg").start()
    season = current_season()
    print(f"HKFA Hong Kong rankings — season {season}")
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
                failed_combos.append(combo_label)
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append(combo_label)
                else:
                    source_url = ranking_url(weapon, gender, category)
                    used_ranks: set[int] = set()
                    rows = []
                    for ordinal, row in enumerate(parsed, start=1):
                        rank, tie_metadata = _storage_rank(row["rank"], used_ranks, ordinal)
                        metadata = dict(row.get("metadata") or {})
                        metadata.update(tie_metadata)
                        metadata.update({"source_url": source_url, "format": "pdf"})
                        rows.append(
                            build_ranking_row(
                                source=SOURCE,
                                season=season,
                                weapon=weapon,
                                gender=gender,
                                category=category,
                                rank=rank,
                                name=row["name"],
                                country=COUNTRY,
                                club=row.get("club"),
                                points=row.get("points"),
                                metadata=metadata,
                            )
                        )

                    written = write_rankings(rows, source=SOURCE, season=season)
                    print(f"    Parsed {len(rows)} rows; written {written} rows")
                    total_written += written

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "failed_combos": failed_combos,
                "format": "pdf",
                "ranking_index": f"{BASE_URL}/EN/ranking.html?mID=8",
            },
        )
        print(f"Done — written={total_written}, failed={total_failed}, skipped={total_skipped}")
        if failed_combos:
            print(f"Failed combos: {', '.join(failed_combos)}")
    except Exception as exc:
        run_log.error(str(exc))
        print(f"FAILED — {exc}")


if __name__ == "__main__":
    main()

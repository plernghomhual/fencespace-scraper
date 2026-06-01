"""
scrape_fed_rou.py — Romanian Fencing Federation national rankings scraper.

Probe findings:
  - federatia-de-scrima.ro did not resolve during local and escalated probes.
  - The current federation site is https://frscrima.ro/.
  - /clasamente and /rankinguri return 404.
  - /rezultate/clasament resolves to an old JPEG, not structured ranking data.
  - /ranking-national/ is public and links Junior/Cadet static PDF rankings.

Target coverage:
  - Junior Foil/Epee/Sabre Men/Women: public PDFs.
  - Senior Foil/Epee/Sabre Men/Women: no public ranking link found.
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

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "rou_fencing"
COUNTRY = "ROU"
BASE_URL = "https://frscrima.ro"
RANKING_INDEX_URL = f"{BASE_URL}/ranking-national/"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.7,en;q=0.6",
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

# Static fallbacks are the public links discovered on /ranking-national/.
_STATIC_RANKING_URLS = {
    ("Foil", "Women", "Junior"): f"{BASE_URL}/wp-content/uploads/2021/12/FLF-JUNIORI-3.pdf",
    ("Foil", "Men", "Junior"): f"{BASE_URL}/wp-content/uploads/2021/12/FLM-JUNIORI-3.pdf",
    ("Sabre", "Women", "Junior"): f"{BASE_URL}/wp-content/uploads/2021/12/SBF-JUNIORI-3.pdf",
    ("Sabre", "Men", "Junior"): f"{BASE_URL}/wp-content/uploads/2021/12/SBM-JUNIORI-3.pdf",
    ("Epee", "Women", "Junior"): f"{BASE_URL}/wp-content/uploads/2021/12/SPF-JUNIORI-3.pdf",
    ("Epee", "Men", "Junior"): f"{BASE_URL}/wp-content/uploads/2021/12/SPM-JUNIORI-3.pdf",
}

_ranking_url_cache: dict[tuple[str, str, str], str] | None = None

_RANK_HEADERS = {"loc", "rang", "rank", "pozitie", "nr", "numar"}
_NAME_HEADERS = {"nume", "nume si prenume", "nume prenume", "sportiv", "sportivi"}
_CLUB_HEADERS = {"club", "club sportiv", "asociatie", "asociatia"}
_POINTS_HEADERS = {"puncte", "punctaj", "pct", "pts", "points", "total"}
_SKIP_MARKERS = {"dns", "dq", "dsq", "dnf", "wd", "abs", "total", "summary", "sumar"}


def _strip_accents(text: str) -> str:
    """Normalize Romanian header text without changing parsed names."""
    replacements = str.maketrans({
        "ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
        "Ă": "a", "Â": "a", "Î": "i", "Ș": "s", "Ş": "s", "Ț": "t", "Ţ": "t",
    })
    text = text.translate(replacements)
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _normalise_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _normalise_header(text: str) -> str:
    text = _strip_accents(text).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return _normalise_spaces(text)


def _parse_points(raw: str) -> float | None:
    text = _normalise_spaces(raw).replace("*", "").replace(" ", "")
    if not text:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+", text):
        text = text.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def _parse_rank(raw: str) -> int | None:
    text = _normalise_spaces(raw)
    if _is_skip_text(text):
        return None
    match = re.match(r"^(\d{1,4})(?:[.)])?$", text)
    if not match:
        return None
    return int(match.group(1))


def _is_skip_text(text: str) -> bool:
    key = _normalise_header(text)
    first = key.split(" ", 1)[0] if key else ""
    return first in _SKIP_MARKERS or key in _SKIP_MARKERS


def _detect_columns(header_cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(header_cells):
        key = _normalise_header(raw)
        if key in _RANK_HEADERS and "rank_col" not in mapping:
            mapping["rank_col"] = idx
        elif key in _NAME_HEADERS and "name_col" not in mapping:
            mapping["name_col"] = idx
        elif key in _CLUB_HEADERS and "club_col" not in mapping:
            mapping["club_col"] = idx
        elif key in _POINTS_HEADERS and "points_col" not in mapping:
            mapping["points_col"] = idx
    return mapping


def _parse_html_tables(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []

    results = []
    for table in tables:
        col_map: dict[str, int] = {}
        positional_mode = False

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            texts = [_normalise_spaces(cell.get_text(" ", strip=True)) for cell in cells]
            if any(_is_skip_text(text) for text in texts[:2]):
                continue

            if not col_map and not positional_mode:
                candidate = _detect_columns(texts)
                if "rank_col" in candidate and "name_col" in candidate:
                    col_map = candidate
                    continue
                if _parse_rank(texts[0]) is not None:
                    positional_mode = True
                else:
                    continue

            if positional_mode:
                rank_idx, name_idx, club_idx, points_idx = 0, 1, 2, len(texts) - 1
            else:
                rank_idx = col_map["rank_col"]
                name_idx = col_map["name_col"]
                club_idx = col_map.get("club_col")
                points_idx = col_map.get("points_col")

            max_required = max(i for i in [rank_idx, name_idx, club_idx, points_idx] if i is not None)
            if len(texts) <= max_required:
                continue

            rank = _parse_rank(texts[rank_idx])
            if rank is None:
                continue

            name = texts[name_idx]
            if not name or _is_skip_text(name):
                continue

            club = texts[club_idx] if club_idx is not None else None
            points = _parse_points(texts[points_idx]) if points_idx is not None else None

            results.append({
                "rank": rank,
                "name": name,
                "club": club or None,
                "points": points,
            })

    return results


def _is_numeric_token(token: str) -> bool:
    return re.fullmatch(r"\*?\d+(?:[.,]\d+)?", token.strip()) is not None


def _parse_pdf_text(text: str) -> list[dict]:
    results = []
    for raw_line in text.splitlines():
        line = _normalise_spaces(raw_line)
        if not line or _is_skip_text(line):
            continue

        # Real PDF extraction lines look like:
        # 1 39 Teodorescu Maria 2005 CS Rapid Bucuresti 2 7.5 12 16 1.5
        match = re.match(r"^(\d{1,4})\s+(\*?\d+(?:[.,]\d+)?)\s+(.+?)\s+((?:19|20)\d{2})\s+(.+)$", line)
        if not match:
            continue

        rank = int(match.group(1))
        points = _parse_points(match.group(2))
        name = _normalise_spaces(match.group(3))
        club_tokens = _normalise_spaces(match.group(5)).split()

        while len(club_tokens) > 1 and _is_numeric_token(club_tokens[-1]):
            club_tokens.pop()

        club = " ".join(club_tokens).strip() or None
        if not name or _is_skip_text(name):
            continue

        results.append({
            "rank": rank,
            "name": name,
            "club": club,
            "points": points,
        })

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """
    Parse Romanian federation ranking data.

    Supports:
      - Romanian HTML tables with headers such as Loc/Nume/Club/Puncte.
      - pdfplumber text extracted from frscrima.ro ranking PDFs, where rows are
        rank, total points, name, birth year, club, then event point columns.
    """
    if not html_or_text or not html_or_text.strip():
        return []

    if "<table" in html_or_text.lower():
        return _parse_html_tables(html_or_text)

    if "<" in html_or_text and ">" in html_or_text:
        soup = BeautifulSoup(html_or_text, "html.parser")
        text = soup.get_text("\n", strip=True)
    else:
        text = html_or_text

    return _parse_pdf_text(text)


def _combo_from_label(label: str) -> tuple[str, str, str] | None:
    key = _normalise_header(label)

    if "juniori" in key or "junior" in key:
        category = "Junior"
    elif "seniori" in key or "senior" in key:
        category = "Senior"
    else:
        return None

    if "masculin" in key:
        gender = "Men"
    elif "feminin" in key:
        gender = "Women"
    else:
        return None

    if "floreta" in key:
        weapon = "Foil"
    elif "spada" in key:
        weapon = "Epee"
    elif "sabie" in key:
        weapon = "Sabre"
    else:
        return None

    combo = (weapon, gender, category)
    return combo if combo in RANKING_COMBOS else None


def discover_ranking_urls() -> dict[tuple[str, str, str], str]:
    """Discover public ranking PDF URLs from the current Romanian ranking index."""
    global _ranking_url_cache
    if _ranking_url_cache is not None:
        return dict(_ranking_url_cache)

    discovered = dict(_STATIC_RANKING_URLS)
    try:
        response = requests.get(RANKING_INDEX_URL, headers=HEADERS, timeout=20, allow_redirects=True)
        if response.status_code != 200:
            print(f"    Ranking index HTTP {response.status_code}: {RANKING_INDEX_URL}")
            _ranking_url_cache = discovered
            return dict(discovered)

        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.select_one(".entry-content") or soup
        for link in content.find_all("a", href=True):
            combo = _combo_from_label(link.get_text(" ", strip=True))
            href = urljoin(response.url, link["href"])
            if combo and href.lower().endswith(".pdf"):
                discovered[combo] = href
    except requests.RequestException as exc:
        print(f"    Ranking index request failed: {exc}")

    _ranking_url_cache = discovered
    return dict(discovered)


def get_ranking_url(weapon: str, gender: str, category: str) -> str | None:
    return discover_ranking_urls().get((weapon, gender, category))


def _extract_pdf_text(content: bytes) -> str | None:
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception as exc:
        print(f"    PDF extraction failed: {exc}")
        return None


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch ranking content for a weapon/gender/category combo."""
    url = get_ranking_url(weapon, gender, category)
    if not url:
        print(f"    No public ranking URL for {weapon} {gender} {category}")
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        if response.status_code != 200:
            print(f"    HTTP {response.status_code} for {url}")
            return None

        content_type = (response.headers.get("content-type") or "").lower()
        if "application/pdf" in content_type or response.content[:4] == b"%PDF":
            return _extract_pdf_text(response.content)
        return response.text
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None


def current_season() -> str:
    """
    Return the current fencing season as YYYY-YYYY.

    Uses season_utils when present. The local fallback mirrors existing
    federation scrapers: seasons roll over in July.
    """
    try:
        import season_utils

        if hasattr(season_utils, "current_season"):
            raw = season_utils.current_season()
        elif hasattr(season_utils, "current_fie_season"):
            raw = season_utils.current_fie_season()
        else:
            raw = None

        if raw is not None:
            if hasattr(season_utils, "normalize_season"):
                return season_utils.normalize_season(raw)
            if isinstance(raw, int):
                if hasattr(season_utils, "season_to_string"):
                    return season_utils.season_to_string(raw)
                return f"{raw - 1}-{raw}"
            if isinstance(raw, str) and re.fullmatch(r"\d{4}-\d{4}", raw):
                return raw
    except ImportError:
        pass

    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year - 1}-{year}" if now.month < 7 else f"{year}-{year + 1}"


def main():
    run_log = ScraperRunLogger("scrape_fed_rou").start()
    season = current_season()
    print(f"Romanian Fencing Federation rankings — season {season}")
    total_written = total_failed = total_skipped = 0
    failed_combos: list[str] = []
    skipped_combos: list[str] = []
    working_combos: list[str] = []

    try:
        for weapon, gender, category in RANKING_COMBOS:
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")

            url = get_ranking_url(weapon, gender, category)
            if not url:
                print("    Skipped: no public URL found")
                total_skipped += 1
                skipped_combos.append(combo_label)
                continue

            content = fetch_rankings_page(weapon, gender, category)
            try:
                if not content:
                    total_failed += 1
                    failed_combos.append(combo_label)
                    continue

                parsed = parse_rankings_table(content)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append(combo_label)
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
                        metadata={"source_url": url},
                    )
                    for row in parsed
                ]
                written = write_rankings(rows, source=SOURCE, season=season)
                total_written += written
                working_combos.append(combo_label)
                print(f"    Written {written} rows ({len(parsed)} parsed)")
            finally:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "working_combos": working_combos,
                "failed_combos": failed_combos,
                "skipped_combos": skipped_combos,
                "ranking_index_url": RANKING_INDEX_URL,
            },
        )
        print(
            f"Done — written={total_written}, failed={total_failed}, "
            f"skipped={total_skipped}, working_combos={len(working_combos)}/{len(RANKING_COMBOS)}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

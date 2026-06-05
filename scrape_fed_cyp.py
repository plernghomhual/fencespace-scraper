"""
scrape_fed_cyp.py - Cyprus federation national rankings scraper.

Probe notes, 2026-06-02:
  - Requested probe host `cyprusfencing.com` did not resolve from the local
    sandbox. Public web discovery found the current federation site at:
      https://fencing.org.cy/
  - Rankings page:
      GET https://fencing.org.cy/rankings/
  - Public ranking asset linked from that page:
      GET https://fencing.org.cy/wp-content/uploads/Rankings-290126.pdf
  - Response format: PDF. Text is expected to be extractable with pdfplumber.
  - Coverage appears partial and PDF-based; the scraper attempts all 12
    Senior/Junior Foil/Epee/Sabre Men/Women combos and logs missing sections.

Supported table headers:
  Θέση / Position, Ονοματεπώνυμο / Name, Σύλλογος / Club, Βαθμοί / Points.
"""

from __future__ import annotations

import io
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "cyp_fencing"
COUNTRY = "Cyprus"
BASE_URL = "https://fencing.org.cy"
RANKINGS_URL = f"{BASE_URL}/rankings/"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "el-CY,el;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": f"{BASE_URL}/",
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

_ranking_text_cache: str | None = None
_ranking_source_url_cache: str | None = None

_HEADER_ALIASES = {
    "rank": {"#", "rank", "ranking", "position", "pos", "place", "θεση", "σειρα", "καταταξη"},
    "name": {
        "name",
        "fencer",
        "athlete",
        "player",
        "ονομα",
        "ονοματεπωνυμο",
        "αθλητης",
        "αθλητρια",
        "αθλητη",
    },
    "club": {"club", "team", "academy", "association", "συλλογος", "σωματειο", "ομιλος"},
    "points": {"points", "point", "total points", "score", "pts", "βαθμοι", "μορια", "συνολο"},
}

_SKIP_MARKERS = {
    "dns",
    "dnf",
    "dq",
    "dsq",
    "disq",
    "disqualified",
    "wd",
    "withdrawn",
    "summary",
    "total",
    "totals",
    "no data",
    "no rankings",
    "συνολο",
    "συγκεντρωτικα",
    "περιληψη",
    "ακυρωση",
    "ακυρος",
    "ακυρη",
    "αποκλεισμος",
    "δεν υπαρχουν",
}

_CLUB_START_WORDS = {
    "club",
    "fencing",
    "academy",
    "team",
    "cyprus",
    "nicosia",
    "limassol",
    "larnaca",
    "paphos",
    "lefkosia",
    "lemesos",
    "larnaKa",
    "σξ",
    "συλλογος",
    "σωματειο",
    "ομιλος",
    "ακαδημια",
    "λευκωσια",
    "λεμεσος",
    "λαρνακα",
    "παφος",
}

_WEAPON_ALIASES = {
    "Foil": {"foil", "fleuret", "florete", "ξιφος ασκησεως", "ασκησεως"},
    "Epee": {"epee", "épée", "degen", "espada", "ξιφος μονομαχιας", "μονομαχιας"},
    "Sabre": {"sabre", "saber", "sable", "σπαθη"},
}
_GENDER_ALIASES = {
    "Men": {"men", "mens", "male", "ανδρων", "ανδρες", "ανδρας", "εφηβων", "εφηβοι", "νεων"},
    "Women": {"women", "womens", "female", "γυναικων", "γυναικες", "νεανιδων", "νεανιδες"},
}
_JUNIOR_ALIASES = {"junior", "juniors", "u20", "under 20", "νεων", "νεανιδων", "εφηβων", "νεανιδες", "εφηβοι"}
_NON_SENIOR_CATEGORY_ALIASES = _JUNIOR_ALIASES | {"cadet", "cadets", "u17", "u18", "παιδων", "κορασιδων", "veteran"}


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _normalize_text(value: str) -> str:
    value = _strip_accents(_clean_text(value)).casefold()
    value = value.replace("ς", "σ")
    value = re.sub(r"[^\w\s#]+", " ", value, flags=re.UNICODE)
    return _clean_text(value)


def _header_kind(value: str) -> str | None:
    normalized = _normalize_text(value)
    for kind, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            alias_normalized = _normalize_text(alias)
            if normalized == alias_normalized or alias_normalized in normalized:
                return kind
    return None


def _header_indexes(cells: list[str]) -> dict[str, int] | None:
    indexes: dict[str, int] = {}
    for idx, cell in enumerate(cells):
        kind = _header_kind(cell)
        if kind and kind not in indexes:
            indexes[kind] = idx
    if {"rank", "name", "points"}.issubset(indexes):
        return indexes
    return None


def _is_skip_text(value: str) -> bool:
    normalized = _normalize_text(value)
    if not normalized:
        return False
    first = normalized.split(" ", 1)[0]
    for marker in _SKIP_MARKERS:
        marker_normalized = _normalize_text(marker)
        if normalized == marker_normalized or first == marker_normalized:
            return True
    return False


def _parse_rank(value: str) -> int | None:
    if _is_skip_text(value):
        return None
    match = re.fullmatch(r"\s*(\d{1,4})(?:[.)])?\s*", value)
    return int(match.group(1)) if match else None


def _parse_points(value: str) -> float | None:
    text = _clean_text(value).replace(" ", "")
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
        if len(parts) > 1 and len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            text = "".join(parts)
        else:
            text = text.replace(",", ".")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 1 and len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            text = "".join(parts)

    try:
        return float(text)
    except ValueError:
        return None


def _parse_html_tables(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []

    results: list[dict] = []
    for table in tables:
        header: dict[str, int] | None = None
        positional_mode = False

        for row in table.find_all("tr"):
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            if any(_is_skip_text(cell) for cell in cells[:2]):
                continue

            maybe_header = _header_indexes(cells)
            if maybe_header:
                header = maybe_header
                positional_mode = False
                continue
            if not header and not positional_mode:
                if _parse_rank(cells[0]) is not None:
                    positional_mode = True
                else:
                    continue

            if positional_mode:
                rank_idx = 0
                name_idx = 1
                club_idx = 2 if len(cells) > 3 else None
                points_idx = len(cells) - 1
            else:
                assert header is not None
                rank_idx = header["rank"]
                name_idx = header["name"]
                club_idx = header.get("club")
                points_idx = header["points"]

            required = [rank_idx, name_idx, points_idx]
            if club_idx is not None:
                required.append(club_idx)
            if max(required) >= len(cells):
                continue

            rank = _parse_rank(cells[rank_idx])
            name = cells[name_idx]
            if rank is None or not name or _is_skip_text(name):
                continue

            points = _parse_points(cells[points_idx])
            club = cells[club_idx] if club_idx is not None else None
            results.append({"rank": rank, "name": name, "club": club or None, "points": points})

    return results


def _is_numeric_token(token: str) -> bool:
    return re.fullmatch(r"-?\d+(?:[.,]\d+)?", token.strip()) is not None


def _split_name_club(identity_tokens: list[str]) -> tuple[str, str | None]:
    tokens = [token for token in identity_tokens if token]
    if not tokens:
        return "", None

    for idx, token in enumerate(tokens):
        key = _normalize_text(token).replace(" ", "")
        if key in {_normalize_text(word).replace(" ", "") for word in _CLUB_START_WORDS} and idx > 0:
            return " ".join(tokens[:idx]).strip(), " ".join(tokens[idx:]).strip() or None

    if len(tokens) <= 2:
        return " ".join(tokens), None

    return " ".join(tokens[:2]).strip(), " ".join(tokens[2:]).strip() or None


def _parse_pdf_text(text: str) -> list[dict]:
    results: list[dict] = []
    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line or _is_skip_text(line):
            continue
        if _header_indexes(line.split()):
            continue

        match = re.match(r"^(\d{1,4})(?:[.)])?\s+(.+)$", line)
        if not match:
            continue

        rank = int(match.group(1))
        rest = match.group(2)
        tokens = rest.split()
        if len(tokens) < 2:
            continue

        point_idx = None
        for idx in range(len(tokens) - 1, -1, -1):
            if _is_numeric_token(tokens[idx]):
                point_idx = idx
                break
        if point_idx is None:
            continue

        points = _parse_points(tokens[point_idx])
        identity_tokens = tokens[:point_idx]
        while identity_tokens and _is_numeric_token(identity_tokens[-1]):
            identity_tokens.pop()

        birth_year_idx = next(
            (idx for idx, token in enumerate(identity_tokens) if re.fullmatch(r"(?:19|20)\d{2}", token)),
            None,
        )
        if birth_year_idx is not None:
            name = " ".join(identity_tokens[:birth_year_idx]).strip()
            club = " ".join(identity_tokens[birth_year_idx + 1:]).strip() or None
        else:
            name, club = _split_name_club(identity_tokens)

        if not name or _is_skip_text(name):
            continue
        results.append({"rank": rank, "name": name, "club": club, "points": points})

    return results


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Cyprus federation rankings into rank/name/club/points rows."""
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


def _contains_any(text: str, aliases: set[str]) -> bool:
    normalized = _normalize_text(text)
    padded = f" {normalized} "
    for alias in aliases:
        alias_normalized = _normalize_text(alias)
        if " " in alias_normalized:
            if alias_normalized in normalized:
                return True
        elif f" {alias_normalized} " in padded:
            return True
    return False


def _line_combo(line: str) -> tuple[str, str, str] | None:
    if not any(_contains_any(line, aliases) for aliases in _WEAPON_ALIASES.values()):
        return None

    weapon = next((weapon for weapon, aliases in _WEAPON_ALIASES.items() if _contains_any(line, aliases)), None)
    gender = next((gender for gender, aliases in _GENDER_ALIASES.items() if _contains_any(line, aliases)), None)
    if not weapon or not gender:
        return None

    if _contains_any(line, _JUNIOR_ALIASES):
        category = "Junior"
    elif _contains_any(line, _NON_SENIOR_CATEGORY_ALIASES):
        return None
    else:
        category = "Senior"

    combo = (weapon, gender, category)
    return combo if combo in RANKING_COMBOS else None


def extract_combo_section(text: str, weapon: str, gender: str, category: str) -> str | None:
    """Return the text section for a requested combo from a combined ranking PDF."""
    if not text or not text.strip():
        return None

    wanted = (weapon, gender, category)
    sections: list[tuple[tuple[str, str, str], list[str]]] = []
    current_combo: tuple[str, str, str] | None = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        combo = _line_combo(line)
        if combo:
            if current_combo and current_lines:
                sections.append((current_combo, current_lines))
            current_combo = combo
            current_lines = [line]
            continue
        if current_combo:
            current_lines.append(raw_line)

    if current_combo and current_lines:
        sections.append((current_combo, current_lines))

    if not sections:
        return text if parse_rankings_table(text) else None

    for combo, lines in sections:
        if combo == wanted:
            section = "\n".join(lines)
            return section if parse_rankings_table(section) else None
    return None


def _page_requires_login(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    text = _normalize_text(soup.get_text(" ", strip=True))
    has_password = soup.find("input", {"type": "password"}) is not None
    return has_password or "login" in text or "log in" in text or "συνδεση" in text


def _page_looks_js_only(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    visible_text = _clean_text(soup.get_text(" ", strip=True))
    has_app_root = soup.find(id=re.compile(r"^(?:app|root)$", re.I)) is not None
    return bool(soup.find("script")) and (has_app_root or len(visible_text) < 80)


def _find_ranking_pdf_url(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[int, str]] = []
    for link in soup.find_all("a", href=True):
        href = urljoin(base_url, link["href"])
        label = f"{link.get_text(' ', strip=True)} {href}"
        if not href.lower().split("?", 1)[0].endswith(".pdf"):
            continue
        score = 0
        normalized = _normalize_text(label)
        for token in ("ranking", "rankings", "καταταξη", "καταταξεισ", "βαθμολογια", "πινακεσ"):
            if _normalize_text(token) in normalized:
                score += 1
        candidates.append((score, href))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_pdf_text(content: bytes) -> str | None:
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages)
    except Exception as exc:
        print(f"    PDF extraction failed: {exc}")
        return None


def _response_text_from_pdf_or_html(response: Any) -> str | None:
    global _ranking_source_url_cache
    content_type = (response.headers.get("content-type") or "").lower()
    content = getattr(response, "content", b"")
    if "application/pdf" in content_type or content.startswith(b"%PDF"):
        _ranking_source_url_cache = response.url
        return _extract_pdf_text(content)
    _ranking_source_url_cache = response.url
    return response.text


def _load_rankings_text() -> str | None:
    global _ranking_text_cache, _ranking_source_url_cache
    if _ranking_text_cache is not None:
        return _ranking_text_cache

    try:
        index = federation_request("get", RANKINGS_URL, headers=HEADERS, timeout=25, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {RANKINGS_URL}: {exc}")
        return None

    if index.status_code != 200:
        print(f"    No scrapeable rankings at {RANKINGS_URL} (HTTP {index.status_code})")
        return None

    direct_text = _response_text_from_pdf_or_html(index)
    if direct_text and parse_rankings_table(direct_text):
        _ranking_text_cache = direct_text
        return _ranking_text_cache

    pdf_url = _find_ranking_pdf_url(index.text, index.url)
    if not pdf_url:
        if _page_requires_login(index.text):
            print(f"    Login-only rankings page, no public PDF/API found: {index.url}")
        elif _page_looks_js_only(index.text):
            print(f"    JS-only rankings page, no public PDF/API found: {index.url}")
        else:
            print(f"    No scrapeable rankings at {index.url}")
        return None

    try:
        ranking = federation_request("get", pdf_url, headers=HEADERS, timeout=35, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {pdf_url}: {exc}")
        return None

    if ranking.status_code != 200:
        print(f"    No scrapeable rankings at {pdf_url} (HTTP {ranking.status_code})")
        return None

    _ranking_text_cache = _response_text_from_pdf_or_html(ranking)
    return _ranking_text_cache


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch ranking content for one combo, returning None on missing/error."""
    text = _load_rankings_text()
    if not text:
        return None

    section = extract_combo_section(text, weapon, gender, category)
    if section is None:
        print(f"    No public ranking section for {weapon} {gender} {category}")
    return section


def current_season() -> str:
    """Return the active fencing season as YYYY-YYYY."""
    now = datetime.now(timezone.utc)
    end_year = now.year if now.month < 7 else now.year + 1
    try:
        import season_utils

        if hasattr(season_utils, "normalize_season"):
            return season_utils.normalize_season(end_year)
        if hasattr(season_utils, "season_to_string"):
            return season_utils.season_to_string(end_year)
    except Exception:
        pass
    return f"{end_year - 1:04d}-{end_year:04d}"


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_cyp").start()
    season = current_season()
    total_written = 0
    total_failed = 0
    total_skipped = 0
    failed_combos: list[str] = []
    skipped_combos: list[str] = []
    working_combos: list[str] = []

    print(f"Cyprus federation rankings - season {season}")
    print(f"Ranking index: {RANKINGS_URL}")

    try:
        for idx, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")
            content = fetch_rankings_page(weapon, gender, category)
            if content is None:
                total_failed += 1
                failed_combos.append(f"{combo_label}: no public scrapeable section")
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    total_skipped += 1
                    skipped_combos.append(f"{combo_label}: no rows parsed")
                    print("    No rows parsed")
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
                                "source_url": _ranking_source_url_cache or RANKINGS_URL,
                                "format": "pdf",
                            },
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    total_written += written
                    working_combos.append(combo_label)
                    print(f"    Written {written} rows ({len(parsed)} parsed)")

            if idx < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={
                "ranking_index": RANKINGS_URL,
                "ranking_source_url": _ranking_source_url_cache,
                "working_combos": working_combos,
                "failed_combos": failed_combos,
                "skipped_combos": skipped_combos,
            },
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
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

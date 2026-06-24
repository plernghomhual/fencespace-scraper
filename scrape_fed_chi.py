"""
scrape_fed_chi.py - Chilean Fencing Federation national rankings scraper.

Probe findings (2026-06-02):
  - Requested probe host: feche.cl.
  - Current public FECHE site found during probe: https://esgrima.cl.
  - Weapon pages are public HTML reached by GET:
      https://esgrima.cl/espada/
      https://esgrima.cl/florete/
      https://esgrima.cl/sable/
  - The weapon pages link to public ranking PDFs under:
      https://esgrima.cl/wp-content/uploads/2025/04/
      {ESPADA,FLORETE,SABLE}-{FEMENINA,MASCULINA}-{JUVENIL,TODO-COMPETIDOR}.pdf
  - Response format: application/pdf with text extractable by pdfplumber.
  - Public coverage: all 12 required Senior/Junior Foil/Epee/Sabre Men/Women
    combos are public in the probed 2025/2026 pages.
  - Category labels:
      TODO COMPETIDOR -> Senior
      JUVENIL -> Junior

PDF text columns:
  Puntaje TOTAL | Ranking | DEPORTISTA | RUT | DV | FECHA DE NACIMIENTO |
  CLUB | event position/points columns.
"""

from __future__ import annotations

import io
import re
import time
import unicodedata
from datetime import UTC, datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "chi_fencing"
COUNTRY = "Chile"
BASE_URL = "https://esgrima.cl"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.7",
}

WEAPON_PAGES = {
    "Epee": f"{BASE_URL}/espada/",
    "Foil": f"{BASE_URL}/florete/",
    "Sabre": f"{BASE_URL}/sable/",
}
CATEGORY_LABELS = {
    "Senior": "TODO COMPETIDOR",
    "Junior": "JUVENIL",
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

_RANKING_URLS_CACHE: dict[tuple[str, str, str], str] | None = None

_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")
_POINT_TOKEN_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")
_ROW_START_RE = re.compile(r"^\s*\d+(?:[.,]\d+)?\s+\d+\s+")
_SKIP_ROW_RE = re.compile(
    r"^\s*(?:DNS|DQ|DSQ|DNF|RET|WD|TOTAL|RESUMEN|SUMMARY|RANKING|PUNTAJE|"
    r"PUESTO|POSICI[ÓO]N|CLUB\s+PARTIC|PARTICIPANTES)\b",
    re.IGNORECASE,
)
_HEADER_LINE_RE = re.compile(
    r"\b(?:RANKING NACIONAL|CAMPEONATO|PUNTAJE|DEPORTISTA|NACIMIENTO|"
    r"POSICI[ÓO]N\s+CLUB|RANKING DE|PARTICIPANTES POR CLUB)\b",
    re.IGNORECASE,
)
_NO_DATA_MARKERS = {
    "no hay datos",
    "sin datos",
    "no data",
    "no rankings available",
    "no se encontraron",
}
_LOGIN_MARKERS = {
    "iniciar sesión",
    "iniciar sesion",
    "login required",
    "wp-login.php",
    "wp-login",
    "type=\"password\"",
    "password",
    "contraseña",
}
_JS_ONLY_MARKERS = {
    "enable javascript",
    "habilitar javascript",
    "active javascript",
    "requires javascript",
}
_EVENT_MARKERS = {
    "-",
    "PAN",
    "PANAM",
    "MED",
    "MUNDIAL",
    "SUD",
    "SURAM",
}
_RANK_HEADERS = {"#", "n", "no", "nro", "numero", "ranking", "rank", "puesto", "posicion"}
_NAME_HEADERS = {"nombre", "deportista", "tirador", "tiradora", "atleta"}
_CLUB_HEADERS = {"club", "institucion", "asociacion", "entidad"}
_POINT_HEADERS = {"puntos", "puntaje", "total", "pts", "points"}


def _clean_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _header_key(value: str) -> str:
    text = _strip_accents(_clean_text(value)).lower()
    text = text.replace("º", "o").replace("°", "o")
    if text == "#":
        return "#"
    return re.sub(r"[^a-z0-9#]+", "", text)


def _parse_points(raw: str) -> float | None:
    value = _clean_text(raw)
    if not value:
        return None
    value = re.sub(r"[^0-9,.\-]", "", value)
    if not value or value in {"-", ".", ","}:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", value):
        value = value.replace(".", "")

    try:
        return float(value)
    except ValueError:
        return None


def _parse_rank(raw: str) -> int | None:
    text = _clean_text(raw)
    if _SKIP_ROW_RE.match(text):
        return None
    match = re.match(r"^(\d+)(?:[º°.]*)?$", text)
    if not match:
        return None
    rank = int(match.group(1))
    return rank if rank > 0 else None


def _detect_columns(cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(cells):
        key = _header_key(cell)
        if key in _RANK_HEADERS and "rank" not in mapping:
            mapping["rank"] = idx
        elif key in _NAME_HEADERS and "name" not in mapping:
            mapping["name"] = idx
        elif key in _CLUB_HEADERS and "club" not in mapping:
            mapping["club"] = idx
        elif key in _POINT_HEADERS and "points" not in mapping:
            mapping["points"] = idx
    return mapping


def _parse_html_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    parsed: list[dict] = []
    seen: set[tuple[int, str]] = set()

    for table in soup.find_all("table"):
        col_map: dict[str, int] | None = None
        for row in table.find_all("tr"):
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
            if not cells:
                continue

            candidate = _detect_columns(cells)
            if "rank" in candidate and "name" in candidate:
                col_map = candidate
                continue

            if col_map:
                if len(cells) <= max(col_map.values()):
                    continue
                rank = _parse_rank(cells[col_map["rank"]])
                name = cells[col_map["name"]]
                club = cells[col_map["club"]] if "club" in col_map and col_map["club"] < len(cells) else None
                points = (
                    _parse_points(cells[col_map["points"]])
                    if "points" in col_map and col_map["points"] < len(cells)
                    else _parse_points(cells[-1])
                )
            else:
                if len(cells) < 2:
                    continue
                rank = _parse_rank(cells[0])
                name = cells[1]
                club = cells[2] if len(cells) > 2 else None
                points = _parse_points(cells[-1]) if len(cells) > 3 else None

            if rank is None or not name or _SKIP_ROW_RE.match(name):
                continue
            key = (rank, name)
            if key in seen:
                continue
            seen.add(key)
            parsed.append({"rank": rank, "name": name, "club": club or None, "points": points})

    return parsed


def _is_header_or_summary_line(line: str) -> bool:
    if not line:
        return True
    if _SKIP_ROW_RE.match(line):
        return True
    return bool(_HEADER_LINE_RE.search(line))


def _normalise_pdf_rows(text: str) -> list[str]:
    rows: list[str] = []
    current: str | None = None

    def flush() -> None:
        nonlocal current
        if current:
            rows.append(current)
            current = None

    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        line = re.sub(r"\s*\|\s*", " ", line)
        line = _clean_text(line)
        if not line:
            continue

        if _is_header_or_summary_line(line):
            flush()
            continue

        if _ROW_START_RE.match(line):
            flush()
            current = line
        elif current:
            current = f"{current} {line}"

    flush()
    return rows


def _looks_like_rut(token: str) -> bool:
    value = token.strip().replace(".", "").replace("-", "")
    return bool(re.fullmatch(r"\d{6,9}|[A-Z]{2,}\d{3,}", value, flags=re.IGNORECASE))


def _looks_like_dv(token: str) -> bool:
    return bool(re.fullmatch(r"[0-9Kk]", token.strip()))


def _remove_identity_tokens(tokens: list[str]) -> list[str]:
    if len(tokens) >= 2 and _looks_like_dv(tokens[-1]) and _looks_like_rut(tokens[-2]):
        return tokens[:-2]
    if tokens and _looks_like_rut(tokens[-1]):
        return tokens[:-1]
    return tokens


def _is_event_token(token: str) -> bool:
    value = token.strip().strip("()").upper()
    if value in _EVENT_MARKERS:
        return True
    return bool(_POINT_TOKEN_RE.fullmatch(value))


def _parse_pdf_row(line: str) -> dict | None:
    match = re.match(r"^\s*(?P<points>\d+(?:[.,]\d+)?)\s+(?P<rank>\d+)\s+(?P<rest>.+)$", line)
    if not match:
        return None

    points = _parse_points(match.group("points"))
    rank = _parse_rank(match.group("rank"))
    if points is None or rank is None:
        return None

    rest = match.group("rest")
    date_match = _DATE_RE.search(rest)
    if not date_match:
        return None

    before_date = rest[: date_match.start()].strip()
    after_date = rest[date_match.end() :].strip()
    identity_tokens = _remove_identity_tokens(before_date.split())
    if not identity_tokens:
        return None

    name = " ".join(identity_tokens).strip()
    if not name or _SKIP_ROW_RE.match(name):
        return None

    club_tokens: list[str] = []
    for token in after_date.split():
        if _is_event_token(token):
            break
        club_tokens.append(token)
    club = " ".join(club_tokens).strip() or None

    return {"rank": rank, "name": name, "club": club, "points": points}


def _parse_pdf_text(text: str) -> list[dict]:
    parsed: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for line in _normalise_pdf_rows(text):
        row = _parse_pdf_row(line)
        if not row:
            continue
        key = (row["rank"], row["name"])
        if key in seen:
            continue
        seen.add(key)
        parsed.append(row)
    return parsed


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Chile rankings from HTML tables or extracted FECHE PDF text."""
    if not html_or_text or not html_or_text.strip():
        return []

    lowered = html_or_text.lower()
    if any(marker in lowered for marker in _NO_DATA_MARKERS):
        return []

    html_rows = _parse_html_table(html_or_text)
    if html_rows:
        return html_rows
    return _parse_pdf_text(BeautifulSoup(html_or_text, "html.parser").get_text("\n", strip=True))


def _is_unusable_html(text: str) -> bool:
    lowered = text.lower()
    if any(marker in lowered for marker in _LOGIN_MARKERS):
        return True
    return any(marker in lowered for marker in _JS_ONLY_MARKERS)


def _request_get(url: str, *, timeout: int):
    last_exc: requests.RequestException | None = None
    for attempt in range(3):
        try:
            response = federation_request(
                "get",
                url,
                headers=HEADERS,
                timeout=timeout,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(REQUEST_DELAY * (attempt + 1))
            continue

        if response.status_code in {429} or response.status_code >= 500:
            if attempt < 2:
                time.sleep(REQUEST_DELAY * (attempt + 1))
                continue
        return response

    if last_exc:
        print(f"    Request error for {url}: {last_exc}")
    return None


def _extract_links_from_weapon_page(weapon: str, page_url: str, html: str) -> dict[tuple[str, str, str], str]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[tuple[str, str, str], str] = {}
    section_gender: str | None = None

    for node in soup.find_all(["h1", "h2", "h3", "a"]):
        text = _clean_text(node.get_text(" ", strip=True)).upper()
        if node.name in {"h1", "h2", "h3"}:
            if "RANKING INTERNACIONAL" in text:
                section_gender = None
            elif "RANKING NACIONAL FEMENINO" in text:
                section_gender = "Women"
            elif "RANKING NACIONAL MASCULINO" in text:
                section_gender = "Men"
            continue

        if node.name != "a" or not section_gender:
            continue

        href = node.get("href")
        if not href:
            continue
        for category, label in CATEGORY_LABELS.items():
            key = (weapon, section_gender, category)
            if text == label and key not in found:
                found[key] = urljoin(page_url, href)

    return found


def _discover_ranking_urls() -> dict[tuple[str, str, str], str]:
    global _RANKING_URLS_CACHE
    if _RANKING_URLS_CACHE is not None:
        return _RANKING_URLS_CACHE

    discovered: dict[tuple[str, str, str], str] = {}
    for weapon, page_url in WEAPON_PAGES.items():
        response = _request_get(page_url, timeout=30)
        if response is None:
            continue
        if response.status_code != 200:
            print(f"    HTTP {response.status_code} for {page_url}")
            continue
        if _is_unusable_html(response.text):
            print(f"    No scrapeable rankings at {page_url}")
            continue
        discovered.update(_extract_links_from_weapon_page(weapon, page_url, response.text))

    _RANKING_URLS_CACHE = discovered
    return discovered


def _extract_pdf_text(content: bytes) -> str | None:
    try:
        import pdfplumber
    except ImportError:
        print("    pdfplumber is required to parse Chile ranking PDFs")
        return None

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(
                page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages
            )
    except Exception as exc:
        print(f"    PDF parse error: {exc}")
        return None


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """Fetch and extract ranking content for one Chile weapon/gender/category combo."""
    url = _discover_ranking_urls().get((weapon, gender, category))
    if not url:
        print(f"    No scrapeable rankings at {WEAPON_PAGES.get(weapon, BASE_URL)} for {weapon} {gender} {category}")
        return None

    response = _request_get(url, timeout=45)
    if response is None:
        return None
    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    content_type = response.headers.get("content-type", "").lower()
    if "application/pdf" in content_type or response.content.startswith(b"%PDF"):
        return _extract_pdf_text(response.content)

    if "text/html" in content_type:
        if _is_unusable_html(response.text):
            print(f"    No scrapeable rankings at {url}")
            return None
        return response.text

    print(f"    Unexpected Chile ranking format from {url}: {content_type}")
    return None


def current_season() -> str:
    """Return the current fencing season as YYYY-YYYY."""
    now = datetime.now(UTC)
    end_year = now.year if now.month < 7 else now.year + 1
    try:
        import season_utils  # type: ignore

        if hasattr(season_utils, "normalize_season"):
            normalized = season_utils.normalize_season(end_year)
            if isinstance(normalized, str):
                return normalized
        if hasattr(season_utils, "season_to_string"):
            return season_utils.season_to_string(end_year)
    except Exception:
        pass
    return f"{end_year - 1:04d}-{end_year:04d}"


def main() -> None:
    run_log = ScraperRunLogger("scrape_fed_chi").start()
    season = current_season()
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous Chile federation run state found: {previous_state}")

    print(f"Chile FECHE rankings - season {season}")
    print(f"Base URL: {BASE_URL}")

    total_written = 0
    total_failed = 0
    total_skipped = 0
    working_combos = 0
    failed_combos: list[str] = []

    try:
        for index, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            combo_label = f"{weapon} {gender} {category}"
            print(f"  {combo_label}...")
            content = fetch_rankings_page(weapon, gender, category)
            source_url = _discover_ranking_urls().get((weapon, gender, category))

            if not content:
                total_failed += 1
                failed_combos.append(f"{combo_label}: fetch failed")
            else:
                parsed = parse_rankings_table(content)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append(f"{combo_label}: no rows parsed")
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
                                "source_format": "pdf" if source_url and source_url.lower().endswith(".pdf") else "html",
                            },
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    print(f"    Parsed {len(rows)} rows; written {written} rows")
                    total_written += written
                    working_combos += 1

            if index < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        state = {
            "season": season,
            "written": total_written,
            "failed": total_failed,
            "skipped": total_skipped,
            "working_combos": working_combos,
            "total_combos": len(RANKING_COMBOS),
            "failed_combos": failed_combos,
            "weapon_pages": WEAPON_PAGES,
            "discovered_urls": {f"{w} {g} {c}": u for (w, g, c), u in _discover_ranking_urls().items()},
            "response_format": "application/pdf",
            "updated_at": datetime.now(UTC).isoformat(),
        }
        set_state(SOURCE, "last_run", state)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata=state,
        )
        print(
            f"Done - written={total_written}, failed={total_failed}, "
            f"skipped={total_skipped}, working_combos={working_combos}/{len(RANKING_COMBOS)}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

"""
scrape_fed_arg.py - Federacion Argentina de Esgrima national rankings scraper.

Probe findings (2026-06-01):
  - Requested host `esgrima.org.ar` did not resolve.
  - Current FAE host is https://www.esgrima-fae.com.ar.
  - HTML routes `/ranking`, `/rankings`, `/clasificaciones`, and `/resultados`
    return a reCAPTCHA security page, not ranking tables.
  - Direct ranking PDF assets are public:
      GET /assets/pdf/ranking/{mayores,juveniles,cadetes}/
          {category}-{florete,espada,sable}{masc,fem}.pdf
    Response format is `application/pdf` and the PDF text is extractable with
    pdfplumber.
  - All 12 requested Senior/Junior Foil/Epee/Sabre Men/Women combos are public.

Spanish category mapping:
  Mayores -> Senior, Juvenil/Juveniles -> Junior, Cadetes -> Cadet.
"""

import io
import re
import time
import unicodedata
from datetime import UTC, datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, federation_request, write_rankings
from run_logger import ScraperRunLogger

SOURCE = "arg_fencing"
COUNTRY = "ARG"
BASE_URL = "https://www.esgrima-fae.com.ar"
REQUEST_DELAY = 1.5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

CATEGORY_SLUGS = {
    "Senior": "mayores",
    "Junior": "juveniles",
    "Cadet": "cadetes",
}
SPANISH_CATEGORY_MAP = {
    "mayores": "Senior",
    "mayor": "Senior",
    "juvenil": "Junior",
    "juveniles": "Junior",
    "cadete": "Cadet",
    "cadetes": "Cadet",
}
WEAPON_SLUGS = {
    "Foil": "florete",
    "Epee": "espada",
    "Sabre": "sable",
}
GENDER_SLUGS = {
    "Men": "masc",
    "Women": "fem",
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

_DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
_POINT_RE = re.compile(r"\d+(?:[.,]\d+)?")
_POINT_TOKEN_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
_SKIP_ROW_RE = re.compile(
    r"^\s*(?:DNS|DQ|DSQ|RET|BAJA|TOTAL|RESUMEN|RANKING|N[º°]|PUESTO|POSICI[ÓO]N)\b",
    re.IGNORECASE,
)
_RANK_HEADERS = {"#", "n", "no", "nro", "numero", "puesto", "posicion", "rank"}
_NAME_HEADERS = {"nombre", "tirador", "tiradora", "atleta", "deportista"}
_CLUB_HEADERS = {"club", "sala", "institucion", "entidad"}
_POINT_HEADERS = {"puntos", "puntaje", "total", "pts", "points"}


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _normalise_header(value: str) -> str:
    value = _strip_accents(value).lower().strip()
    value = value.replace("º", "o").replace("°", "o")
    value = re.sub(r"[^\w#]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _parse_points(raw: str) -> float | None:
    value = raw.replace("\xa0", " ").strip()
    if not value:
        return None
    value = re.sub(r"[^\d,.\-]", "", value)
    if not value:
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
    if _SKIP_ROW_RE.match(raw):
        return None
    match = re.match(r"^\s*(\d+)", raw)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _detect_columns(cells: list[str]) -> dict[str, int]:
    mapping = {}
    for idx, raw in enumerate(cells):
        header = _normalise_header(raw)
        if header in _RANK_HEADERS and "rank" not in mapping:
            mapping["rank"] = idx
        elif header in _NAME_HEADERS and "name" not in mapping:
            mapping["name"] = idx
        elif header in _CLUB_HEADERS and "club" not in mapping:
            mapping["club"] = idx
        elif header in _POINT_HEADERS and "points" not in mapping:
            mapping["points"] = idx
    return mapping


def _parse_html_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = []
    col_map: dict[str, int] = {}
    in_data = False

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        texts = [cell.get_text(" ", strip=True) for cell in cells]
        candidate = _detect_columns(texts)
        if "rank" in candidate and "name" in candidate:
            col_map = candidate
            in_data = True
            continue

        if not in_data:
            if texts and _parse_rank(texts[0]) is not None:
                in_data = True
            else:
                continue

        if col_map:
            max_col = max(col_map.values())
            if len(texts) <= max_col:
                continue
            rank = _parse_rank(texts[col_map["rank"]])
            if rank is None:
                continue
            name = texts[col_map["name"]].strip()
            club = texts[col_map["club"]].strip() if "club" in col_map else None
            points = _parse_points(texts[col_map["points"]]) if "points" in col_map else None
        else:
            if len(texts) < 2:
                continue
            rank = _parse_rank(texts[0])
            if rank is None:
                continue
            name = texts[1].strip()
            club = texts[2].strip() if len(texts) > 2 else None
            points = _parse_points(texts[-1]) if len(texts) > 3 else None

        if not name or _SKIP_ROW_RE.match(name):
            continue
        rows.append({"rank": rank, "name": name, "club": club or None, "points": points})

    return rows


def _parse_pdf_text(text: str) -> list[dict]:
    rows = []
    for raw_line in text.splitlines():
        line = raw_line.replace("\xa0", " ").strip()
        line = re.sub(r"\s*\|\s*", " ", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line or _SKIP_ROW_RE.match(line):
            continue

        rank_match = re.match(r"^(\d+)\s+(.+)$", line)
        if not rank_match:
            continue

        rank = int(rank_match.group(1))
        rest = rank_match.group(2).strip()
        tokens = rest.split()
        point_start = len(tokens)
        while point_start > 0 and _POINT_TOKEN_RE.match(tokens[point_start - 1]):
            point_start -= 1

        if point_start < len(tokens):
            points = _parse_points(tokens[-1])
            identity_parts = tokens[:point_start]
            if identity_parts and "/" in identity_parts[-1] and re.search(r"\d{4}$", identity_parts[-1]):
                identity_parts = identity_parts[:-1]
        else:
            date_match = _DATE_RE.search(rest)
            if not date_match:
                continue
            before_date = rest[:date_match.start()].strip()
            after_date = rest[date_match.end():].strip()
            identity_parts = before_date.split()
            point_values = _POINT_RE.findall(after_date)
            points = _parse_points(point_values[-1]) if point_values else None

        parts = identity_parts
        if len(parts) < 2:
            continue

        club = parts[-1]
        name = " ".join(parts[:-1]).strip()
        if not name or _SKIP_ROW_RE.match(name):
            continue

        if points is None:
            continue

        rows.append({"rank": rank, "name": name, "club": club or None, "points": points})

    return rows


def parse_rankings_table(html_or_text: str) -> list[dict]:
    """Parse Argentina rankings from extracted PDF text or a Spanish HTML table."""
    if not html_or_text or not html_or_text.strip():
        return []

    html_rows = _parse_html_table(html_or_text)
    if html_rows:
        return html_rows
    return _parse_pdf_text(html_or_text)


def build_rankings_url(weapon: str, gender: str, category: str) -> str:
    category_slug = CATEGORY_SLUGS[category]
    weapon_slug = WEAPON_SLUGS[weapon]
    gender_slug = GENDER_SLUGS[gender]
    return (
        f"{BASE_URL}/assets/pdf/ranking/{category_slug}/"
        f"{category_slug}-{weapon_slug}{gender_slug}.pdf"
    )


def _extract_pdf_text(content: bytes) -> str | None:
    try:
        import pdfplumber
    except ImportError:
        print("    pdfplumber is required to parse Argentina ranking PDFs")
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
    """Fetch and extract text for one Argentina ranking combo."""
    url = build_rankings_url(weapon, gender, category)
    try:
        response = federation_request("get", url, headers=HEADERS, timeout=30, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"    Request error for {url}: {exc}")
        return None

    if response.status_code != 200:
        print(f"    HTTP {response.status_code} for {url}")
        return None

    content_type = response.headers.get("content-type", "").lower()
    if "application/pdf" in content_type or response.content.startswith(b"%PDF"):
        return _extract_pdf_text(response.content)

    return response.text


def current_season() -> str:
    now = datetime.now(UTC)
    end_year = now.year if now.month < 7 else now.year + 1
    try:
        from season_utils import normalize_season

        return normalize_season(end_year)
    except Exception:
        return f"{end_year - 1}-{end_year}"


def main():
    run_log = ScraperRunLogger("scrape_fed_arg").start()
    season = current_season()
    total_written = 0
    total_failed = 0
    failed_combos = []
    url_pattern = f"{BASE_URL}/assets/pdf/ranking/{{category}}/{{category}}-{{weapon}}{{gender}}.pdf"

    print(f"Argentina FAE rankings - season {season}")
    print(f"URL pattern: {url_pattern}")

    try:
        for idx, (weapon, gender, category) in enumerate(RANKING_COMBOS):
            print(f"  {weapon} {gender} {category}...")
            text = fetch_rankings_page(weapon, gender, category)
            if not text:
                total_failed += 1
                failed_combos.append(f"{weapon} {gender} {category}: fetch failed")
            else:
                parsed = parse_rankings_table(text)
                if not parsed:
                    print("    No rows parsed")
                    total_failed += 1
                    failed_combos.append(f"{weapon} {gender} {category}: no rows parsed")
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
                            metadata={"source_url": build_rankings_url(weapon, gender, category)},
                        )
                        for row in parsed
                    ]
                    written = write_rankings(rows, source=SOURCE, season=season)
                    print(f"    Written {written} rows ({len(parsed)} parsed)")
                    total_written += written

            if idx < len(RANKING_COMBOS) - 1:
                time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=0,
            metadata={
                "failed_combos": failed_combos,
                "working_url_pattern": url_pattern,
                "response_format": "application/pdf",
                "public_combos": len(RANKING_COMBOS) - total_failed,
            },
        )
        print(f"Done - written={total_written}, failed={total_failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

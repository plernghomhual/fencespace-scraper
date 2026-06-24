"""
Pan American Fencing Confederation (PAFC/CPE) circuit and championship results.

Probe notes (2026-06-02):
  - Historical PAFC domains (`panam-fencing.org`, `panam-fencing.com`,
    `panamericanfencing.org`) were recorded in project memory as DNS-offline.
  - Public 2024/2025 Senior Pan American Championship references point to FIE
    competition result pages.
  - The Puerto Rico host federation publishes the 2025 Spanish invitation PDF;
    it links to the Ophardt widget event `31914`.
  - Local script probing of `fie.org` was blocked by sandbox DNS, and the
    escalated retry was blocked by the Codex usage-limit approval gate.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import time
import unicodedata
from datetime import UTC, datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import normalize_category, normalize_gender, normalize_weapon
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SOURCE = "panam_conf"
REQUEST_DELAY = float(os.environ.get("PANAM_CONF_DELAY", "1.5"))
BATCH_SIZE = 100

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,application/json,*/*;q=0.8",
}

FIE_SEARCH_URL = "https://fie.org/competitions/search"
FIE_COMPETITIONS_URL = "https://fie.org/competitions"
FIE_DISCOVERY_SEASONS = [2024, 2025, 2026]
FIE_SEARCH_NAMES = ["Pan American", "Panamericano", "Panam"]

HOST_SOURCE_URLS = [
    "https://fedesgrimapuertorico.org/campeonato-panamericano-adulto-2025/",
    "https://fedesgrimapuertorico.org/wp-content/uploads/2025/03/Convocatoria-Campeonato-Panamericano-adulto-2025_esp.pdf",
]

PAFC_COUNTRY_ALIASES = {
    "ARGENTINA": "ARG",
    "ARUBA": "ARU",
    "ANTIGUA AND BARBUDA": "ANT",
    "ANTIGUA Y BARBUDA": "ANT",
    "BAHAMAS": "BAH",
    "BARBADOS": "BAR",
    "BELICE": "BIZ",
    "BELIZE": "BIZ",
    "BERMUDA": "BER",
    "BOLIVIA": "BOL",
    "BRITISH VIRGIN ISLANDS": "IVB",
    "BVI": "IVB",
    "BRASIL": "BRA",
    "BRAZIL": "BRA",
    "CANADA": "CAN",
    "CAN": "CAN",
    "CAYMAN ISLANDS": "CAY",
    "ISLAS CAIMAN": "CAY",
    "CHILE": "CHI",
    "COLOMBIA": "COL",
    "COSTA RICA": "CRC",
    "CUBA": "CUB",
    "CURACAO": "CUR",
    "CURAZAO": "CUR",
    "CURACAO NETHERLANDS ANTILLES": "CUR",
    "DOMINICAN REPUBLIC": "DOM",
    "REPUBLICA DOMINICANA": "DOM",
    "REP DOMINICANA": "DOM",
    "ECUADOR": "ECU",
    "EL SALVADOR": "ESA",
    "ESTADOS UNIDOS": "USA",
    "ESTADOS UNIDOS DE AMERICA": "USA",
    "EE UU": "USA",
    "EEUU": "USA",
    "USA": "USA",
    "US": "USA",
    "UNITED STATES": "USA",
    "UNITED STATES OF AMERICA": "USA",
    "U S A": "USA",
    "GUATEMALA": "GUA",
    "GUYANA": "GUY",
    "GRENADA": "GRN",
    "HAITI": "HAI",
    "HONDURAS": "HON",
    "ISLAS VIRGENES": "ISV",
    "ISLAS VIRGENES DE EEUU": "ISV",
    "ISLAS VIRGENES DE EE UU": "ISV",
    "ISLAS VIRGENES ESTADOUNIDENSES": "ISV",
    "U S VIRGIN ISLANDS": "ISV",
    "US VIRGIN ISLANDS": "ISV",
    "U S VIRGIN IS": "ISV",
    "VIRGIN ISLANDS": "ISV",
    "JAMAICA": "JAM",
    "MEXICO": "MEX",
    "MEX": "MEX",
    "NICARAGUA": "NCA",
    "PANAMA": "PAN",
    "PARAGUAY": "PAR",
    "PERU": "PER",
    "PUERTO RICO": "PUR",
    "PUR": "PUR",
    "SAINT KITTS AND NEVIS": "SKN",
    "SAN CRISTOBAL Y NIEVES": "SKN",
    "SAINT LUCIA": "LCA",
    "SANTA LUCIA": "LCA",
    "SAINT VINCENT AND THE GRENADINES": "VIN",
    "SAN VICENTE Y LAS GRANADINAS": "VIN",
    "SURINAME": "SUR",
    "TRINIDAD AND TOBAGO": "TTO",
    "TRINIDAD Y TOBAGO": "TTO",
    "URUGUAY": "URU",
    "VENEZUELA": "VEN",
}

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def clean_text(value) -> str:
    text = html.unescape(str(value or "").replace("\xa0", " "))
    return re.sub(r"\s+", " ", text).strip()


def _strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", value or "")
        if unicodedata.category(ch) != "Mn"
    )


def _norm(value) -> str:
    text = _strip_accents(clean_text(value)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _upper_key(value) -> str:
    text = _strip_accents(clean_text(value)).upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _title_word(value: str) -> str:
    return "-".join(piece[:1].upper() + piece[1:].lower() for piece in value.split("-"))


def _title_name(value: str) -> str:
    return " ".join(_title_word(part) for part in clean_text(value).split())


def _is_upper_name_part(value: str) -> bool:
    letters = "".join(ch for ch in value if ch.isalpha())
    return bool(letters) and letters.upper() == letters


def normalize_person_name(value) -> str | None:
    text = clean_text(value).strip(",")
    if not text:
        return None
    if "," in text:
        last, first = [part.strip() for part in text.split(",", 1)]
        first = _title_name(first)
        last = _title_name(last)
        return first if first.lower() == last.lower() else f"{first} {last}".strip()

    parts = text.split()
    leading = 0
    while leading < len(parts) and _is_upper_name_part(parts[leading]):
        leading += 1
    if 0 < leading < len(parts):
        first = _title_name(" ".join(parts[leading:]))
        last = _title_name(" ".join(parts[:leading]))
        return first if first.lower() == last.lower() else f"{first} {last}".strip()

    trailing = 0
    while trailing < len(parts) and _is_upper_name_part(parts[-1 - trailing]):
        trailing += 1
    if 0 < trailing < len(parts):
        first = _title_name(" ".join(parts[:-trailing]))
        last = _title_name(" ".join(parts[-trailing:]))
        return first if first.lower() == last.lower() else f"{first} {last}".strip()
    return _title_name(text)


def normalize_country_code(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = _upper_key(text)
    if key in PAFC_COUNTRY_ALIASES:
        return PAFC_COUNTRY_ALIASES[key]
    compact = key.replace(" ", "")
    if compact in PAFC_COUNTRY_ALIASES:
        return PAFC_COUNTRY_ALIASES[compact]
    if re.fullmatch(r"[A-Z]{3}", compact):
        return compact
    return None


def _parse_rank(value) -> int | None:
    text = clean_text(value)
    medal_rank = {
        "gold": 1,
        "oro": 1,
        "silver": 2,
        "plata": 2,
        "bronze": 3,
        "bronce": 3,
    }.get(_norm(text))
    if medal_rank:
        return medal_rank
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def _medal_for_rank(rank: int | None) -> str | None:
    if rank is None:
        return None
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _parse_points(value) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(r"[^0-9,.\-]+", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%B %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    match = re.search(r"\b(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s+de\s+(\d{4})\b", text, re.I)
    if match:
        month = SPANISH_MONTHS.get(_norm(match.group(2)))
        if month:
            return f"{int(match.group(3)):04d}-{month:02d}-{int(match.group(1)):02d}"
    return None


def _extract_date_from_text(value: str) -> str | None:
    text = clean_text(value)
    patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{1,2}[/-]\d{1,2}[/-]\d{4}",
        r"\d{1,2}\s+de\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+\s+de\s+\d{4}",
        r"[A-Za-z]+\s+\d{1,2},\s+\d{4}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            parsed = parse_date(match.group(0))
            if parsed:
                return parsed
    return None


def classify_event(event_name: str, metadata: dict | None = None) -> dict:
    metadata = metadata or {}
    text = _norm(event_name)

    weapon = normalize_weapon(str(metadata.get("weapon") or "")) if metadata.get("weapon") else None
    if not weapon:
        if re.search(r"\b(foil|florete|fleuret)\b", text):
            weapon = "Foil"
        elif re.search(r"\b(epee|ep\u00e9e|espada)\b", text):
            weapon = "Epee"
        elif re.search(r"\b(sabre|saber|sable)\b", text):
            weapon = "Sabre"

    gender = normalize_gender(str(metadata.get("gender") or "")) if metadata.get("gender") else None
    if not gender:
        if re.search(r"\b(women|woman|female|femenino|femenina|mujeres|damas|ladies)\b", text):
            gender = "Women"
        elif re.search(r"\b(men|man|male|masculino|masculina|hombres|varonil)\b", text):
            gender = "Men"

    category = normalize_category(str(metadata.get("category") or "")) if metadata.get("category") else None
    if not category:
        if re.search(r"\b(junior|juvenil|u20|sub 20)\b", text):
            category = "Junior"
        elif re.search(r"\b(cadet|cadete|u17|sub 17)\b", text):
            category = "Cadet"
        elif re.search(r"\b(veteran|veterano|veterana|master|veteranos)\b", text):
            category = "Veteran"
        else:
            category = "Senior"

    team = bool(re.search(r"\b(team|teams|equipo|equipos)\b", text))
    event_code = None
    if weapon and gender:
        event_code = f"{gender.lower()}-{weapon.lower()}-{'team' if team else 'individual'}"
    return {"weapon": weapon, "gender": gender, "category": category, "team": team, "event_code": event_code}


def _header_key(value) -> str:
    return _norm(value)


def _header_indexes(headers: list[str]) -> dict[str, int]:
    indexes = {}
    for idx, header in enumerate(headers):
        key = _header_key(header)
        if "rank" not in indexes and re.search(r"\b(rank|place|pos|puesto|posicion|clasificacion)\b", key):
            indexes["rank"] = idx
        if "name" not in indexes and re.search(r"\b(name|fencer|athlete|competitor|esgrimista|tirador|nombre|equipo|team)\b", key):
            indexes["name"] = idx
        if "country" not in indexes and re.search(r"\b(country|nation|nationality|noc|pais|nacion|federation)\b", key):
            indexes["country"] = idx
        if "points" not in indexes and re.search(r"\b(points|point|pts|puntos)\b", key):
            indexes["points"] = idx
        if "fie_id" not in indexes and re.search(r"\b(fie|license|licencia|id)\b", key) and "rank" not in key:
            indexes["fie_id"] = idx
    return indexes


def discover_source_links(html_text: str, base_url: str | None = None) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    links = []
    seen = set()
    for link in soup.find_all("a", href=True):
        url = urljoin(base_url or "", link["href"])
        parsed = urlparse(url)
        lower = url.lower()
        kind = None
        if "fencing.ophardt.online" in parsed.netloc:
            kind = "ophardt"
        elif "fencingtimelive.com" in parsed.netloc:
            kind = "fencing_time_live"
        elif "engarde-service.com" in parsed.netloc:
            kind = "engarde"
        elif "fie.org" in parsed.netloc and "/competitions/" in parsed.path:
            kind = "fie"
        elif lower.endswith(".pdf"):
            kind = "pdf"
        if not kind or url in seen:
            continue
        seen.add(url)
        links.append({"url": url, "kind": kind, "label": clean_text(link.get_text(" ", strip=True))})
    return links


def _row_from_cells(cells: list[str], indexes: dict[str, int], classification: dict) -> dict | None:
    try:
        rank = _parse_rank(cells[indexes["rank"]])
        raw_name = cells[indexes["name"]]
    except (KeyError, IndexError):
        return None
    if rank is None or not clean_text(raw_name):
        return None

    country = None
    if "country" in indexes and indexes["country"] < len(cells):
        country = normalize_country_code(cells[indexes["country"]])
    points = None
    if "points" in indexes and indexes["points"] < len(cells):
        points = _parse_points(cells[indexes["points"]])
    fie_id = None
    if "fie_id" in indexes and indexes["fie_id"] < len(cells):
        fie_id = clean_text(cells[indexes["fie_id"]]) or None

    team = classification["team"]
    name = clean_text(raw_name) if team else normalize_person_name(raw_name)
    if not name or not country:
        return None
    return {
        "rank": rank,
        "name": name,
        "country": country,
        "points": points,
        "medal": _medal_for_rank(rank),
        "fie_id": str(fie_id) if fie_id else None,
        "team": team,
    }


def parse_html_result_page(html_text: str, source_url: str | None = None, event_name: str | None = None) -> dict | None:
    soup = BeautifulSoup(html_text, "html.parser")
    heading = event_name
    if not heading:
        heading_tag = soup.find(["h1", "h2", "h3"])
        heading = clean_text(heading_tag.get_text(" ", strip=True)) if heading_tag else ""
    if not heading and soup.title:
        heading = clean_text(soup.title.get_text(" ", strip=True))

    classification = classify_event(heading)
    if not classification["weapon"] or not classification["gender"]:
        return None

    rows = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if not trs:
            continue
        header_cells = [clean_text(cell.get_text(" ", strip=True)) for cell in trs[0].find_all(["th", "td"])]
        indexes = _header_indexes(header_cells)
        if "rank" not in indexes or "name" not in indexes:
            continue
        for tr in trs[1:]:
            cells = [clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
            if not cells:
                continue
            row = _row_from_cells(cells, indexes, classification)
            if row:
                rows.append(row)
        if rows:
            break

    if not rows:
        return None
    return {
        "event_name": heading,
        "event_code": classification["event_code"],
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": classification["category"],
        "team": classification["team"],
        "date": _extract_date_from_text(soup.get_text(" ", strip=True)),
        "source_url": source_url,
        "source_kind": "html_table",
        "source_links": discover_source_links(html_text, source_url),
        "results": rows,
    }


def _json_span(text: str, start: int) -> str | None:
    opening = text[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def _extract_json_blocks(html_text: str) -> list:
    blocks = []
    for match in re.finditer(r"window\.[A-Za-z0-9_$]+\s*=\s*", html_text):
        idx = match.end()
        while idx < len(html_text) and html_text[idx].isspace():
            idx += 1
        if idx >= len(html_text) or html_text[idx] not in "[{":
            continue
        span = _json_span(html_text, idx)
        if not span:
            continue
        try:
            blocks.append(json.loads(span))
        except json.JSONDecodeError:
            continue
    return blocks


def _iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _first_result_payload(blocks: list) -> dict | None:
    for block in blocks:
        for item in _iter_dicts(block):
            rows = item.get("rows")
            if isinstance(rows, list) and rows:
                return item
    return None


def _row_from_mapping(row: dict, classification: dict) -> dict | None:
    rank = _parse_rank(row.get("rank") or row.get("place") or row.get("position"))
    if rank is None:
        return None
    team = classification["team"] or bool(row.get("team"))
    name = row.get("name") or row.get("fencerName") or row.get("athlete") or row.get("teamName")
    country = normalize_country_code(
        row.get("nationality")
        or row.get("country")
        or row.get("nation")
        or row.get("noc")
        or row.get("countryCode")
    )
    if not name or not country:
        return None
    fencer_id = row.get("fencerId") or row.get("fie_id") or row.get("fieFencerId")
    return {
        "rank": rank,
        "name": clean_text(name) if team else normalize_person_name(name),
        "country": country,
        "points": _parse_points(row.get("points") or row.get("point") or row.get("score")),
        "medal": _medal_for_rank(rank),
        "fie_id": str(fencer_id) if fencer_id is not None and clean_text(fencer_id) else None,
        "team": team,
    }


def parse_fie_results_page(html_text: str, source_url: str | None = None) -> dict | None:
    payload = _first_result_payload(_extract_json_blocks(html_text))
    if not payload:
        return None
    soup = BeautifulSoup(html_text, "html.parser")
    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    event_name = clean_text(payload.get("name") or payload.get("title") or title)
    classification = classify_event(event_name, payload)
    if not classification["weapon"] or not classification["gender"]:
        return None

    rows = []
    for raw in payload.get("rows") or []:
        if isinstance(raw, dict):
            row = _row_from_mapping(raw, classification)
            if row:
                rows.append(row)
    if not rows:
        return None
    return {
        "event_name": event_name,
        "event_code": classification["event_code"],
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": classification["category"],
        "team": classification["team"],
        "date": parse_date(payload.get("startDate") or payload.get("date")),
        "location": clean_text(payload.get("location")),
        "host_country": normalize_country_code(payload.get("country")),
        "source_url": source_url,
        "source_kind": "fie_inline_json",
        "source_links": [],
        "results": rows,
    }


def _split_country_tail(value: str) -> tuple[str | None, str | None, float | None]:
    text = clean_text(value)
    points = None
    points_match = re.search(r"\s+(-?\d+(?:[.,]\d+)?)\s*$", text)
    if points_match:
        possible = _parse_points(points_match.group(1))
        if possible is not None:
            points = possible
            text = text[: points_match.start()].strip()

    paren = re.search(r"\(([^)]+)\)\s*$", text)
    if paren:
        country = normalize_country_code(paren.group(1))
        if country:
            return text[: paren.start()].strip(), country, points

    tokens = text.split()
    for size in range(min(5, len(tokens)), 0, -1):
        phrase = " ".join(tokens[-size:])
        country = normalize_country_code(phrase)
        if country:
            return " ".join(tokens[:-size]).strip(), country, points
    return None, None, points


def _parse_result_line(line: str, classification: dict) -> dict | None:
    match = re.match(r"^\s*(?P<rank>\d+|Gold|Silver|Bronze|Oro|Plata|Bronce)(?:=|T)?\s+(?P<body>.+)$", line, re.I)
    if not match:
        return None
    rank = _parse_rank(match.group("rank"))
    body = re.sub(r"\s+(Gold|Silver|Bronze|Oro|Plata|Bronce)\s*$", "", match.group("body"), flags=re.I)
    name, country, points = _split_country_tail(body)
    if not name or not country or rank is None:
        return None
    team = classification["team"]
    return {
        "rank": rank,
        "name": clean_text(name) if team else normalize_person_name(name),
        "country": country,
        "points": points,
        "medal": _medal_for_rank(rank),
        "fie_id": None,
        "team": team,
    }


def parse_pdf_text_events(text: str, source_url: str | None = None) -> list[dict]:
    events = []
    current = None
    for raw_line in text.splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        if re.search(r"\b(rank|puesto|nombre|pais|pa[ií]s|points|puntos)\b", line, re.I):
            continue
        classification = classify_event(line)
        looks_like_event = (
            classification["weapon"]
            and classification["gender"]
            and re.search(r"\b(individual|team|equipo|equipos)\b", _norm(line))
            and not re.match(r"^\d", line)
        )
        if looks_like_event:
            if current and current["results"]:
                events.append(current)
            current = {
                "event_name": line,
                "event_code": classification["event_code"],
                "weapon": classification["weapon"],
                "gender": classification["gender"],
                "category": classification["category"],
                "team": classification["team"],
                "date": _extract_date_from_text(text),
                "source_url": source_url,
                "source_kind": "pdf_text",
                "source_links": [],
                "results": [],
            }
            continue
        if not current:
            continue
        row = _parse_result_line(line, classify_event(current["event_name"]))
        if row:
            current["results"].append(row)
    if current and current["results"]:
        events.append(current)
    return events


def _get(url: str, retries: int = 2):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                return response
            print(f"  HTTP {response.status_code} for {url}")
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
            else:
                return None
        except requests.RequestException as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def _parse_pdf_response(response, source_url: str) -> list[dict]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        text = "\n".join(page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages)
    return parse_pdf_text_events(text, source_url=source_url)


def parse_source_response(response, source_url: str) -> list[dict]:
    content_type = (response.headers.get("content-type") or "").lower()
    if "pdf" in content_type or source_url.lower().endswith(".pdf"):
        return _parse_pdf_response(response, source_url)
    if "fie.org" in urlparse(source_url).netloc and "/competitions/" in urlparse(source_url).path:
        event = parse_fie_results_page(response.text, source_url=source_url)
        return [event] if event else []
    event = parse_html_result_page(response.text, source_url=source_url)
    return [event] if event else []


def _fie_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(FIE_COMPETITIONS_URL, timeout=15)
    except requests.RequestException as exc:
        print(f"  FIE warmup failed: {exc}")
    return session


def discover_fie_result_urls(seasons: list[int] | None = None) -> list[str]:
    seasons = seasons or FIE_DISCOVERY_SEASONS
    session = _fie_session()
    urls = []
    seen = set()
    for season in seasons:
        for name in FIE_SEARCH_NAMES:
            payload = {
                "name": name,
                "status": "passed",
                "gender": [],
                "weapon": [],
                "type": [],
                "season": season,
                "level": "",
                "competitionCategory": "",
                "fromDate": f"{season}-01-01",
                "toDate": f"{season}-12-31",
                "fetchPage": 1,
            }
            try:
                response = session.post(
                    FIE_SEARCH_URL,
                    headers={
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": "application/json, text/plain, */*",
                        "Referer": FIE_COMPETITIONS_URL,
                    },
                    json=payload,
                    timeout=20,
                )
                items = response.json().get("items", []) if response.status_code == 200 else []
            except Exception as exc:
                print(f"  FIE search failed season={season} name={name!r}: {exc}")
                continue
            for item in items:
                title = clean_text(item.get("name"))
                if "pan" not in _norm(title):
                    continue
                competition_id = item.get("competitionId")
                item_season = item.get("season") or season
                if not competition_id:
                    continue
                url = f"https://fie.org/competitions/{item_season}/{competition_id}?tab=results"
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
            time.sleep(0.2)
    return urls


def discover_host_result_urls() -> list[str]:
    discovered = []
    seen = set()
    for url in HOST_SOURCE_URLS:
        response = _get(url, retries=1)
        if not response:
            continue
        if "pdf" in (response.headers.get("content-type") or "").lower() or url.lower().endswith(".pdf"):
            # Host PDFs can be result books or invitations. Try parsing them later; if
            # they contain no result rows, they are counted as skipped.
            links = [{"url": url, "kind": "pdf", "label": "host pdf"}]
        else:
            links = discover_source_links(response.text, url)
            html_event = parse_html_result_page(response.text, source_url=url)
            if html_event:
                links.append({"url": url, "kind": "html", "label": "host html table"})
        for link in links:
            link_url = link["url"]
            if link_url not in seen:
                seen.add(link_url)
                discovered.append(link_url)
        time.sleep(REQUEST_DELAY)
    return discovered


def blocked_source_stubs() -> list[dict]:
    return [
        {
            "url": "https://www.panam-fencing.org",
            "status": "missing",
            "reason": "prior project probe recorded DNS/offline PAFC domain",
        },
        {
            "url": "https://panam-fencing.org",
            "status": "missing",
            "reason": "prior project probe recorded DNS/offline PAFC domain",
        },
        {
            "url": "https://panam-fencing.com",
            "status": "missing",
            "reason": "prior project probe recorded DNS/offline PAFC domain",
        },
        {
            "url": "https://panamericanfencing.org",
            "status": "missing",
            "reason": "prior project probe recorded DNS/offline PAFC domain",
        },
        {
            "url": FIE_COMPETITIONS_URL,
            "status": "blocked",
            "reason": "local probe script hit sandbox DNS failure on 2026-06-02; escalated retry blocked by usage-limit gate",
        },
    ]


def discover_events() -> tuple[list[dict], list[dict]]:
    events = []
    skipped_sources = blocked_source_stubs()
    source_urls = []
    try:
        source_urls.extend(discover_fie_result_urls())
    except Exception as exc:
        skipped_sources.append({"url": FIE_SEARCH_URL, "status": "blocked", "reason": str(exc)[:300]})
    try:
        source_urls.extend(discover_host_result_urls())
    except Exception as exc:
        skipped_sources.append({"url": "host_sources", "status": "blocked", "reason": str(exc)[:300]})

    seen_events = set()
    for url in dict.fromkeys(source_urls):
        response = _get(url, retries=1)
        if not response:
            skipped_sources.append({"url": url, "status": "missing", "reason": "fetch failed or no public static response"})
            continue
        parsed = parse_source_response(response, url)
        if not parsed:
            skipped_sources.append({"url": url, "status": "missing", "reason": "no parseable result rows in public source"})
            continue
        for event in parsed:
            source_id = event_source_id(event)
            if source_id in seen_events:
                continue
            event["source_id"] = source_id
            seen_events.add(source_id)
            events.append(event)
        time.sleep(REQUEST_DELAY)
    return events, skipped_sources


def _source_url_id(source_url: str | None) -> str:
    if not source_url:
        return "unknown"
    match = re.search(r"/competitions/(\d+)/(\d+)", source_url)
    if match:
        return f"fie-{match.group(1)}-{match.group(2)}"
    slug = _norm(source_url)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug[-64:] or "unknown"


def event_source_id(event: dict) -> str:
    year = None
    if event.get("date"):
        year = event["date"][:4]
    if not year:
        match = re.search(r"\b(20\d{2}|19\d{2})\b", event.get("event_name") or "")
        year = match.group(1) if match else "unknown"
    return f"panam:{year}:{event.get('event_code') or 'event'}:{_source_url_id(event.get('source_url'))}"


def upsert_tournament(event: dict) -> str | None:
    source_id = event.get("source_id") or event_source_id(event)
    year = (event.get("date") or "")[:4] or None
    row = {
        "source_id": source_id,
        "name": f"Pan American Fencing Confederation - {event['event_name']}",
        "season": year,
        "type": "panam_conf_championship",
        "weapon": event.get("weapon"),
        "gender": event.get("gender"),
        "category": event.get("category") or "Senior",
        "country": event.get("host_country"),
        "location": event.get("location"),
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "source_url": event.get("source_url"),
            "source_kind": event.get("source_kind"),
            "source_links": event.get("source_links") or [],
            "event_code": event.get("event_code"),
            "event_name": event.get("event_name"),
            "team": event.get("team"),
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()  # type: ignore[union-attr]
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def _match_fencer(fie_id=None, name=None, country=None) -> tuple[str | None, str | None]:
    if supabase is None:
        return None, None
    try:
        if fie_id:
            rows = (
                supabase.table("fs_fencers")
                .select("id")
                .eq("fie_id", str(fie_id))
                .limit(2)
                .execute()
                .data
                or []
            )
            if len(rows) == 1:
                return rows[0]["id"], "fie_id"
        if name and country:
            rows = (
                supabase.table("fs_fencers")
                .select("id")
                .ilike("name", name)
                .eq("country", country)
                .limit(2)
                .execute()
                .data
                or []
            )
            if len(rows) == 1:
                return rows[0]["id"], "name_country"
            identity_rows = (
                supabase.table("fs_fencer_identities")
                .select("canonical_id,fs_fencer_row_ids,fencer_ids")
                .ilike("canonical_name", name)
                .eq("country", country)
                .limit(2)
                .execute()
                .data
                or []
            )
            if len(identity_rows) == 1:
                member_id = _identity_member_id(identity_rows[0])
                if member_id:
                    return member_id, "identity_name_country"
    except Exception as exc:
        print(f"  Fencer match failed for {name} {country}: {exc}")
    return None, None


def _identity_member_id(row: dict) -> str | None:
    for key in ("fs_fencer_row_ids", "fencer_ids", "source_fencer_ids"):
        value = row.get(key)
        if isinstance(value, list) and value:
            return clean_text(value[0]) or None
        if isinstance(value, str) and value.strip():
            parts = [part.strip() for part in re.split(r"[,|]", value) if part.strip()]
            if parts:
                return parts[0]
    return None


def build_result_rows(tournament_id: str, source_id: str, result_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    db_rows = []
    unmatched = []
    for row in result_rows:
        if row.get("rank") is None:
            continue
        team = bool(row.get("team"))
        fencer_id = None
        match_type = None
        if not team:
            fencer_id, match_type = _match_fencer(row.get("fie_id"), row.get("name"), row.get("country"))
            if not fencer_id:
                unmatched.append(
                    {
                        "source_id": source_id,
                        "rank": row.get("rank"),
                        "name": row.get("name"),
                        "country": row.get("country"),
                        "fie_id": row.get("fie_id"),
                        "reason": "no_fencer_match",
                    }
                )
                continue
        metadata = {
            "source": SOURCE,
            "source_id": source_id,
            "country": row.get("country"),
            "points": row.get("points"),
            "fie_id": row.get("fie_id"),
            "team": team,
        }
        if match_type:
            metadata["fencer_match"] = match_type
        db_row = {
            "tournament_id": tournament_id,
            "name": row.get("name"),
            "nationality": row.get("country"),
            "country": row.get("country"),
            "rank": row.get("rank"),
            "placement": row.get("rank"),
            "medal": row.get("medal"),
            "fencer_id": fencer_id,
            "metadata": metadata,
        }
        if row.get("fie_id"):
            db_row["fie_fencer_id"] = str(row["fie_id"])
        db_rows.append(db_row)
    return db_rows, unmatched


def upsert_results(tournament_id: str, source_id: str, result_rows: list[dict]) -> tuple[int, int]:
    db_rows, unmatched = build_result_rows(tournament_id, source_id, result_rows)
    for row in unmatched:
        print(
            "  Unmatched PAFC fencer: "
            f"{row['name']} {row['country']} rank={row['rank']} source={row['source_id']}"
        )
    if not db_rows:
        return 0, len(unmatched)

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()  # type: ignore[union-attr]
    written = 0
    for idx in range(0, len(db_rows), BATCH_SIZE):
        batch = db_rows[idx : idx + BATCH_SIZE]
        try:
            supabase.table("fs_results").insert(batch).execute()  # type: ignore[union-attr]
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed for {source_id}: {exc}")
    return written if written == len(db_rows) else 0, len(unmatched)


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_panam_conf").start()
    try:
        print(f"PAFC scraper starting - {datetime.now(UTC).isoformat()}")
        done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])
        events, skipped_sources = discover_events()
        if not events:
            for source in skipped_sources:
                print(f"  Skipped source {source['status']}: {source['url']} ({source['reason']})")
            run_log.complete(written=0, failed=0, skipped=len(skipped_sources), metadata={"skipped_sources": skipped_sources})
            return

        written = failed = skipped = unmatched_total = 0
        for event in events:
            source_id = event.get("source_id") or event_source_id(event)
            if source_id in done_source_ids:
                skipped += 1
                continue
            if not event.get("results"):
                skipped += 1
                continue
            tournament_id = upsert_tournament(event)
            if not tournament_id:
                failed += 1
                continue
            count, unmatched = upsert_results(tournament_id, source_id, event["results"])
            unmatched_total += unmatched
            if count == 0:
                failed += 1
                continue
            done_source_ids.add(source_id)
            set_state(SOURCE, "done_source_ids", sorted(done_source_ids))
            written += count
            print(f"  {source_id}: inserted {count}, unmatched {unmatched}")
            time.sleep(REQUEST_DELAY)

        metadata = {"events_found": len(events), "skipped_sources": skipped_sources, "unmatched_rows": unmatched_total}
        set_state(SOURCE, "last_run", {**metadata, "updated_at": datetime.now(UTC).isoformat()})
        run_log.complete(written=written, failed=failed, skipped=skipped + len(skipped_sources), metadata=metadata)
        print(f"Done - written={written}, failed={failed}, skipped={skipped}, unmatched={unmatched_total}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

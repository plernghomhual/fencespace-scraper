"""
FFSU / French university fencing results scraper.

Probe summary (verified 2026-06-02):
  * Public index: https://sport-u.com/sports-ind/ESCRIME/
  * The index exposes CFU fencing result links for 2022-2025. The 2024
    individual/team files are public PDFs; the 2023 and 2022 result files are
    public PDFs; the 2025 result link is published from the same FFSU index.
  * A local requests probe was attempted but sandbox DNS blocked it. Browser
    probing confirmed the public page text and representative PDF extraction.

The scraper intentionally treats missing or non-public current files as a
deterministic skipped-source path instead of inventing replacement data.
"""
from __future__ import annotations

import io
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SOURCE = "ffsu"
FFSU_ESCRIME_URL = "https://sport-u.com/sports-ind/ESCRIME/"
REQUEST_DELAY = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.8",
}

STATUS_TOKENS = {"DNF", "DNS", "DSQ", "DQ", "ABD", "AB", "NC", "FORFAIT"}

UNIVERSITY_MARKERS = {
    "AMU",
    "AS",
    "ASE",
    "ASU",
    "CENTRALE",
    "CENTRALESUPELEC",
    "COLLEGE",
    "COLLÈGE",
    "CY",
    "DAUPHINE",
    "ECAM",
    "ECOLE",
    "ÉCOLE",
    "EDHEC",
    "ENS",
    "ENSEEIMT",
    "ENTPE",
    "ESAIP",
    "ESSCA",
    "GROUPE",
    "ICP",
    "IFPEK",
    "ILEPS",
    "INSA",
    "KINÉSITHÉRAPIE",
    "LGE",
    "LIC",
    "LICENCE",
    "LIGUE",
    "NANTES",
    "POLE",
    "PÔLE",
    "POLYTECHNIQUE",
    "SCIENCE",
    "SCIENCES",
    "SORBONNE",
    "TELECOM",
    "TÉLÉCOM",
    "U.",
    "UDG",
    "UDL",
    "UNIV",
    "UNIV.",
    "UNIVERSITE",
    "UNIVERSITÉ",
    "UT1",
    "UTBM",
}

ACRONYMS = {
    "AMU",
    "AS",
    "ASE",
    "ASU",
    "BX",
    "CY",
    "DNF",
    "DNS",
    "DSQ",
    "ECAM",
    "EDHEC",
    "ENS",
    "ENSEEIMT",
    "ENTPE",
    "ESA",
    "ESAIP",
    "ESSCA",
    "FFSU",
    "ICP",
    "IFPEK",
    "ILIS",
    "INP",
    "INSA",
    "IUT",
    "LGE",
    "LHDF",
    "NC",
    "PSL",
    "SHS",
    "ST",
    "STAPS",
    "SU",
    "UDG",
    "UDL",
    "URCA",
    "UT1",
    "UTBM",
}

SMALL_WORDS = {"de", "des", "du", "d", "la", "le", "les", "et"}


def _clean_text(value) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = text.replace("\u00a0", " ").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def _fold(value) -> str:
    text = unicodedata.normalize("NFKD", _clean_text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.upper()


def _title_token(token: str) -> str:
    if not token:
        return token
    return token.title()


def normalize_person_name(value) -> str:
    text = _clean_text(value)
    text = re.sub(r"\s*-\s*-\s*", " ", text)
    return " ".join(_title_token(part) for part in text.split())


def _canonical_university_text(value) -> str:
    text = _clean_text(value)
    replacements = [
        (r"\bUNIVERSITE\b", "UNIVERSITÉ"),
        (r"\bUNIV\.", "UNIVERSITÉ"),
        (r"\bUNIV\b", "UNIVERSITÉ"),
        (r"\bECOLE\b", "ÉCOLE"),
        (r"\bCOLLEGE\b", "COLLÈGE"),
        (r"\bSANTE\b", "SANTÉ"),
        (r"\bCITE\b", "CITÉ"),
        (r"\bCOTE\b", "CÔTE"),
        (r"\bPOLE\b", "PÔLE"),
        (r"\bSCIENCE PO\b", "SCIENCES PO"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return _clean_text(text)


def _format_university_token(token: str, index: int) -> str:
    stripped = token.strip()
    punctuation = ""
    while stripped and stripped[-1] in ",;:":
        punctuation = stripped[-1] + punctuation
        stripped = stripped[:-1]
    key = _fold(stripped).replace(".", "")
    lower = stripped.lower().strip(".")
    if key in ACRONYMS:
        return key + punctuation
    if lower in SMALL_WORDS and index > 0:
        return lower + punctuation
    return stripped.title() + punctuation


def normalize_university_label(value) -> str | None:
    text = _canonical_university_text(value)
    if not text:
        return None
    words = [_format_university_token(token, index) for index, token in enumerate(text.split())]
    formatted = " ".join(words)
    formatted = formatted.replace("Sciences PO", "Sciences Po")
    formatted = formatted.replace("D'Azur", "d'Azur")
    return _clean_text(formatted)


def normalize_season(value) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    match = re.search(r"\b((?:19|20)\d{2})\s*[-/]\s*((?:19|20)?\d{2})\b", text)
    if match:
        start = int(match.group(1))
        raw_end = match.group(2)
        end = int(raw_end) if len(raw_end) == 4 else int(str(start)[:2] + raw_end)
        if start <= end <= start + 2:
            return f"{start}-{end}"
    match = re.search(r"\b(\d{2})\s*[-/]\s*(\d{2})\b", text)
    if match:
        start = 2000 + int(match.group(1))
        end = 2000 + int(match.group(2))
        if start <= end <= start + 2:
            return f"{start}-{end}"
    years = [int(year) for year in re.findall(r"\b((?:19|20)\d{2})\b", text)]
    if years:
        year = years[-1]
        return f"{year - 1}-{year}"
    return None


def _rank_to_int(value) -> int | None:
    match = re.match(r"\s*(\d{1,3})", str(value or ""))
    return int(match.group(1)) if match else None


def _medal_for_rank(rank: int | None) -> str | None:
    if rank is None:
        return None
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _parse_points(value) -> int | float | None:
    text = _clean_text(value).replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None
    number = float(text)
    return int(number) if number.is_integer() else number


def classify_event(event_name) -> dict:
    label = _fold(event_name)
    weapon = None
    if re.search(r"\bEPEE\b", label):
        weapon = "Epee"
    elif re.search(r"\bFLEURET\b", label):
        weapon = "Foil"
    elif re.search(r"\bSABRE\b|\bSABER\b", label):
        weapon = "Sabre"

    gender = None
    if re.search(r"\bDAMES?\b|\bFEMMES?\b|\bFEMININ\b|\bFEMININE\b", label):
        gender = "Women"
    elif re.search(r"\bHOMMES?\b|\bMASCULIN\b|\bMASCULINE\b|MESSIEURS", label):
        gender = "Men"

    team = bool(re.search(r"\bEQUIPES?\b|\bTEAM\b", label))
    category = "Senior"
    if re.search(r"\bM17\b|\bU17\b", label):
        category = "U17"
    elif re.search(r"\bM20\b|\bU20\b", label):
        category = "U20"
    elif re.search(r"\bM23\b|\bU23\b", label):
        category = "U23"

    event_code = None
    if weapon and gender:
        event_type = "team" if team else "individual"
        event_code = f"{weapon.lower()}-{gender.lower()}-{event_type}"
    return {
        "weapon": weapon,
        "gender": gender,
        "team": team,
        "category": category,
        "event_code": event_code,
    }


def _event_name_from_code(season: str | None, event_name: str) -> str:
    prefix = f"Championnat de France Universitaire {season}" if season else "Championnat de France Universitaire"
    return f"{prefix} - {_clean_text(event_name)}"


def _make_event(event_name, season, source_url, source_format="text") -> dict | None:
    classification = classify_event(event_name)
    if not classification["event_code"]:
        return None
    normalized_season = normalize_season(season) or normalize_season(source_url)
    source_id = f"ffsu:{normalized_season or 'unknown'}:{classification['event_code']}"
    return {
        "source_id": source_id,
        "name": _event_name_from_code(normalized_season, event_name),
        "season": normalized_season,
        "event_name": _clean_text(event_name),
        "event_code": classification["event_code"],
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": classification["category"],
        "team": classification["team"],
        "source_url": source_url,
        "source_format": source_format,
        "results": [],
    }


def _is_noise_line(line: str) -> bool:
    label = _fold(line)
    if not label:
        return True
    patterns = [
        r"^CHAMPIONNAT DE FRANCE",
        r"^FFSU$",
        r"^CLASSEMENT GENERAL",
        r"^PAGE \d+",
        r"^RG\s+",
        r"^RANG\s+",
        r"^PLACE\s+",
        r"^TOTAL\b",
        r"^DOCUMENT ENGARDE",
        r"^DATE\b",
        r"^LIEU\b",
    ]
    return any(re.search(pattern, label) for pattern in patterns)


def _find_university_index(tokens: list[str]) -> int | None:
    for index, token in enumerate(tokens):
        folded = _fold(token)
        folded_no_dot = folded.rstrip(".")
        if folded in UNIVERSITY_MARKERS or folded_no_dot in UNIVERSITY_MARKERS:
            return index
        pair = _fold(" ".join(tokens[index:index + 2]))
        if pair.startswith("SCIENCE PO") or pair.startswith("SCIENCES PO"):
            return index
    return None


def _strip_status(rest: str) -> tuple[str, str | None]:
    tokens = rest.split()
    if tokens and _fold(tokens[-1]).replace(".", "") in STATUS_TOKENS:
        return " ".join(tokens[:-1]), _fold(tokens[-1]).replace(".", "")
    return rest, None


def _parse_individual_text_rest(rest: str) -> tuple[str | None, str | None, str | None]:
    stripped, status = _strip_status(rest)
    tokens = stripped.split()
    index = _find_university_index(tokens)
    if index is None:
        return normalize_person_name(stripped), None, status
    name = normalize_person_name(" ".join(tokens[:index]))
    university = normalize_university_label(" ".join(tokens[index:]))
    return name, university, status


def _result_row(rank, name, university, event, source_url, points=None, status=None) -> dict:
    return {
        "rank": rank,
        "name": name,
        "university": university,
        "medal": _medal_for_rank(rank),
        "points": points,
        "status": status,
        "team": bool(event["team"]),
        "source_url": source_url,
    }


def _parse_text_result_line(line: str, event: dict, source_url: str | None) -> dict | None:
    match = re.match(r"^(?P<rank>\d{1,3})(?:er|e|\.|,)?\s+(?P<rest>.+)$", line)
    if not match:
        return None
    rank = _rank_to_int(match.group("rank"))
    rest, status = _strip_status(match.group("rest"))
    if rank is None or not rest:
        return None
    if event["team"]:
        university = normalize_university_label(rest)
        if not university:
            return None
        return _result_row(rank, university, university, event, source_url, status=status)
    name, university, status = _parse_individual_text_rest(match.group("rest"))
    if not name:
        return None
    return _result_row(rank, name, university, event, source_url, status=status)


def parse_ffsu_text_result(text, season=None, source_url=None, source_format="text") -> list[dict]:
    events = []
    current = None
    for raw_line in str(text or "").splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue
        if "Document engarde" in line and "Championnat" in line:
            line = line[line.find("Championnat"):]
        heading = _make_event(line, season, source_url, source_format)
        if heading:
            if current and current["source_id"] == heading["source_id"]:
                continue
            if current and current["results"]:
                events.append(current)
            current = heading
            continue
        if _is_noise_line(line):
            continue
        if not current:
            continue
        row = _parse_text_result_line(line, current, source_url)
        if row:
            current["results"].append(row)
    if current and current["results"]:
        events.append(current)
    return events


def _header_key(value) -> str:
    text = _fold(value)
    text = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
    return text


def _column_index(headers: list[str], options: set[str]) -> int | None:
    for index, header in enumerate(headers):
        if header in options:
            return index
    return None


def _cell(row: list, index: int | None):
    if index is None or index >= len(row):
        return ""
    return row[index]


def _parse_tabular_result_row(event: dict, headers: list[str], row: list, source_url: str | None) -> dict | None:
    rank_index = _column_index(headers, {"RG", "RANG", "PLACE", "CLASSEMENT"})
    last_name_index = _column_index(headers, {"NOM"})
    first_name_index = _column_index(headers, {"PRENOM", "PRÉNOM"})
    full_name_index = _column_index(headers, {"NOM_PRENOM", "NOM_PRENOM_CLUB", "TIREUR", "TIREUSE"})
    university_index = _column_index(headers, {"AS", "CLUB", "ASSOCIATION", "UNIVERSITE", "UNIVERSITÉ"})
    points_index = _column_index(headers, {"RESULTAT", "RÉSULTAT", "POINTS", "PTS"})
    status_index = _column_index(headers, {"STATUT", "STATUS"})

    rank = _rank_to_int(_cell(row, rank_index))
    if rank is None:
        return None
    if event["team"]:
        university = normalize_university_label(_cell(row, university_index) or _cell(row, full_name_index) or _cell(row, last_name_index))
        name = university
    else:
        if full_name_index is not None:
            name = normalize_person_name(_cell(row, full_name_index))
        else:
            name = normalize_person_name(f"{_cell(row, last_name_index)} {_cell(row, first_name_index)}")
        university = normalize_university_label(_cell(row, university_index))
    if not name:
        return None
    return _result_row(
        rank,
        name,
        university,
        event,
        source_url,
        points=_parse_points(_cell(row, points_index)),
        status=_clean_text(_cell(row, status_index)) or None,
    )


def _nearest_heading(table) -> str:
    caption = table.find("caption")
    if caption:
        return _clean_text(caption.get_text(" ", strip=True))
    for sibling in table.find_previous_siblings():
        if sibling.name in {"h1", "h2", "h3", "h4", "strong", "p"}:
            text = _clean_text(sibling.get_text(" ", strip=True))
            if classify_event(text)["event_code"]:
                return text
    return ""


def _parse_html_table(table, season, source_url) -> dict | None:
    event = _make_event(_nearest_heading(table), season, source_url, "html")
    if not event:
        return None
    rows = []
    for tr in table.find_all("tr"):
        rows.append([_clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])])
    if not rows:
        return None
    header_index = None
    headers = []
    for index, row in enumerate(rows):
        candidate = [_header_key(cell) for cell in row]
        if _column_index(candidate, {"RG", "RANG", "PLACE", "CLASSEMENT"}) is not None:
            header_index = index
            headers = candidate
            break
    if header_index is None:
        return None

    for row in rows[header_index + 1:]:
        parsed = _parse_tabular_result_row(event, headers, row, source_url)
        if parsed:
            event["results"].append(parsed)
    return event if event["results"] else None


def parse_ffsu_html_result(html, season=None, source_url=None) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    events = []
    for table in soup.find_all("table"):
        event = _parse_html_table(table, season, source_url)
        if event:
            events.append(event)
    if events:
        return events
    text = soup.get_text("\n", strip=True)
    return parse_ffsu_text_result(text, season=season, source_url=source_url, source_format="html")


def _result_source_format(url: str, content_type: str | None = None) -> str:
    path = urlparse(url).path.lower()
    content = (content_type or "").lower()
    if path.endswith(".pdf") or "pdf" in content:
        return "pdf"
    if path.endswith(".xlsx") or "spreadsheetml" in content:
        return "xlsx"
    if path.endswith(".xls"):
        return "xls"
    return "html"


def _is_result_link(title: str, href: str) -> bool:
    haystack = _fold(f"{title} {href}")
    if "RESULTAT" not in haystack:
        return False
    if not ("ESCRIME" in haystack or "CFU" in haystack):
        return False
    blocked = ("DOSSIER", "QUALIF", "REGLEMENT", "CANDIDATURE", "INSCRIPTION")
    return not any(word in haystack for word in blocked)


def discover_result_sources(html, base_url=FFSU_ESCRIME_URL) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    sources = []
    seen = set()
    current_season = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "td", "th", "span", "strong", "a"]):
        text = _clean_text(tag.get_text(" ", strip=True))
        if not text:
            continue
        if tag.name != "a":
            season = normalize_season(text)
            if season and ("SAISON" in _fold(text) or re.fullmatch(r"\d{4}-\d{4}", season)):
                current_season = season
            continue
        href = tag.get("href")
        if not href or not _is_result_link(text, href):
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        sources.append(
            {
                "title": text,
                "url": url,
                "season": normalize_season(text) or normalize_season(url) or current_season,
                "format": _result_source_format(url),
            }
        )
    return sources


def build_no_public_data_stub(probe_statuses: list[dict] | None = None) -> dict:
    statuses = probe_statuses or []
    return {
        "source": SOURCE,
        "events": [],
        "written": 0,
        "failed": 0,
        "skipped": len(statuses),
        "reason": "no public FFSU fencing result files were available from the probed pages",
        "probe_statuses": statuses,
    }


def fetch_index(session=requests) -> tuple[str, list[dict]]:
    response = session.get(FFSU_ESCRIME_URL, headers=HEADERS, timeout=45)
    response.raise_for_status()
    return response.text, [{"url": FFSU_ESCRIME_URL, "status": response.status_code, "evidence": "FFSU fencing index fetched"}]


def parse_ffsu_pdf_bytes(content: bytes, season=None, source_url=None) -> list[dict]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required to parse FFSU PDF results.") from exc
    text_parts = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text(x_tolerance=1, y_tolerance=3) or "")
    return parse_ffsu_text_result("\n".join(text_parts), season=season, source_url=source_url, source_format="pdf")


def parse_ffsu_workbook_bytes(content: bytes, season=None, source_url=None) -> list[dict]:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl is required to parse FFSU spreadsheet results.") from exc
    workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    events = []
    for sheet in workbook.worksheets:
        rows = [[_clean_text(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
        current = _make_event(sheet.title, season, source_url, "xlsx")
        headers: list[str] = []
        for row in rows:
            nonempty = [cell for cell in row if _clean_text(cell)]
            if not nonempty:
                continue
            row_text = _clean_text(" ".join(nonempty))
            heading = _make_event(row_text, season, source_url, "xlsx")
            if heading and _rank_to_int(nonempty[0]) is None:
                if current and current["results"]:
                    events.append(current)
                current = heading
                headers = []
                continue
            candidate_headers = [_header_key(cell) for cell in row]
            if _column_index(candidate_headers, {"RG", "RANG", "PLACE", "CLASSEMENT"}) is not None:
                headers = candidate_headers
                continue
            if current and headers:
                parsed = _parse_tabular_result_row(current, headers, row, source_url)
                if parsed:
                    current["results"].append(parsed)
        if current and current["results"]:
            events.append(current)
    return events


def parse_source_content(source: dict, content: bytes, content_type: str | None = None) -> list[dict]:
    source_format = source.get("format") or _result_source_format(source.get("url", ""), content_type)
    if source_format == "pdf":
        return parse_ffsu_pdf_bytes(content, season=source.get("season"), source_url=source.get("url"))
    if source_format in {"xlsx", "xls"}:
        return parse_ffsu_workbook_bytes(content, season=source.get("season"), source_url=source.get("url"))
    encoding = "utf-8"
    text = content.decode(encoding, errors="replace")
    return parse_ffsu_html_result(text, season=source.get("season"), source_url=source.get("url"))


def fetch_and_parse_source(source: dict, session=requests) -> tuple[list[dict], dict]:
    response = session.get(source["url"], headers=HEADERS, timeout=90)
    status = {
        "url": source["url"],
        "status": response.status_code,
        "evidence": source.get("title") or "FFSU result source",
    }
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    source = {**source, "format": source.get("format") or _result_source_format(source["url"], content_type)}
    events = parse_source_content(source, response.content, content_type=content_type)
    return events, status


def discover_events(session=requests) -> tuple[list[dict], list[dict]]:
    html, probe_statuses = fetch_index(session=session)
    sources = discover_result_sources(html, FFSU_ESCRIME_URL)
    if not sources:
        probe_statuses[0]["evidence"] = "index fetched but no public result links matched"
        return [], probe_statuses
    events = []
    for source in sources:
        try:
            source_events, status = fetch_and_parse_source(source, session=session)
            status["events"] = len(source_events)
            probe_statuses.append(status)
            events.extend(source_events)
            time.sleep(REQUEST_DELAY)
        except Exception as exc:
            probe_statuses.append({"url": source["url"], "status": "error", "evidence": str(exc)[:300]})
    return events, probe_statuses


def upsert_tournament(event: dict) -> str | int | None:
    row = {
        "source_id": event["source_id"],
        "name": event["name"],
        "season": event.get("season"),
        "type": "ffsu_university",
        "weapon": event["weapon"],
        "gender": event["gender"],
        "category": event.get("category") or "Senior",
        "country": "FRA",
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "source_url": event.get("source_url"),
            "source_format": event.get("source_format"),
            "event_name": event.get("event_name"),
            "event_code": event.get("event_code"),
            "team": event.get("team"),
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()  # type: ignore[union-attr]
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {event.get('source_id')}: {exc}")
        return None


def _match_fencer(name: str | None) -> str | int | None:
    if not supabase or not name:
        return None
    try:
        rows = (
            supabase.table("fs_fencers")
            .select("id")
            .ilike("name", name)
            .eq("country", "FRA")
            .limit(2)
            .execute()
            .data
        )
        return rows[0]["id"] if len(rows) == 1 else None
    except Exception:
        return None


def upsert_results(tournament_id, event: dict) -> dict:
    db_rows = []
    unmatched_rows = []
    for result in event.get("results", []):
        rank = result.get("rank")
        if rank is None:
            continue
        fencer_id = None if result.get("team") else _match_fencer(result.get("name"))
        if not result.get("team") and not fencer_id:
            unmatched_rows.append(
                {
                    "name": result.get("name"),
                    "university": result.get("university"),
                    "rank": rank,
                    "source_url": result.get("source_url") or event.get("source_url"),
                }
            )
        db_rows.append(
            {
                "tournament_id": tournament_id,
                "name": result["name"],
                "nationality": "FRA",
                "rank": rank,
                "medal": result.get("medal"),
                "points": result.get("points"),
                "fencer_id": fencer_id,
                "metadata": {
                    "source": SOURCE,
                    "source_id": event.get("source_id"),
                    "source_url": result.get("source_url") or event.get("source_url"),
                    "event_name": event.get("event_name"),
                    "event_code": event.get("event_code"),
                    "university": result.get("university"),
                    "status": result.get("status"),
                    "team": result.get("team"),
                    "match_status": "matched" if fencer_id else "unmatched",
                },
            }
        )
    if not db_rows:
        return {"written": 0, "unmatched": 0, "unmatched_rows": []}
    try:
        supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()  # type: ignore[union-attr]
        written = 0
        for index in range(0, len(db_rows), 100):
            batch = db_rows[index:index + 100]
            supabase.table("fs_results").insert(batch).execute()  # type: ignore[union-attr]
            written += len(batch)
        if unmatched_rows:
            print(f"  Unmatched FFSU rows for {event.get('source_id')}: {len(unmatched_rows)}")
            for row in unmatched_rows[:10]:
                print(f"    {row['rank']} {row['name']} — {row.get('university') or 'unknown university'}")
        return {"written": written, "unmatched": len(unmatched_rows), "unmatched_rows": unmatched_rows}
    except Exception as exc:
        print(f"  Results insert failed for {event.get('source_id')}: {exc}")
        return {"written": 0, "unmatched": len(unmatched_rows), "unmatched_rows": unmatched_rows}


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_ffsu").start()
    try:
        print(f"FFSU scraper starting — {datetime.now(timezone.utc).isoformat()}")
        done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])
        events, probe_statuses = discover_events()
        if not events:
            stub = build_no_public_data_stub(probe_statuses)
            run_log.complete(
                written=0,
                failed=0,
                skipped=stub["skipped"],
                metadata={"reason": stub["reason"], "probe_statuses": probe_statuses},
            )
            print(f"Done — {stub['reason']}; skipped={stub['skipped']}")
            return stub

        written = failed = skipped = unmatched = 0
        for event in events:
            if event["source_id"] in done_source_ids:
                skipped += 1
                continue
            tournament_id = upsert_tournament(event)
            if not tournament_id:
                failed += 1
                continue
            result = upsert_results(tournament_id, event)
            if result["written"] == 0:
                failed += 1
                continue
            written += result["written"]
            unmatched += result["unmatched"]
            done_source_ids.add(event["source_id"])
            set_state(SOURCE, "done_source_ids", sorted(done_source_ids))
            time.sleep(REQUEST_DELAY)

        set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
        run_log.complete(
            written=written,
            failed=failed,
            skipped=skipped,
            metadata={"unmatched_rows": unmatched, "probe_statuses": probe_statuses},
        )
        print(f"Done — written={written}, skipped={skipped}, failed={failed}, unmatched={unmatched}")
        return {"written": written, "failed": failed, "skipped": skipped, "unmatched": unmatched}
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

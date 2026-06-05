# -*- coding: utf-8 -*-
"""Asian Fencing Confederation championship and circuit result scraper.

Probe summary from this workspace (2026-06-02):
  * AFC WordPress pages and current host pages could not be reached from the
    sandbox because DNS is blocked.
  * Escalated live probing was rejected by the platform usage gate, so current
    live sources are treated as skipped with explicit evidence instead of
    fabricated rows.
  * Search-visible AFC pages link to FencingTime-style result pages and public
    AFC/FIE PDFs. This module parses those stable HTML/PDF table shapes when
    fetched by an environment with network access.
"""
from __future__ import annotations

import io
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

try:
    from fed_rankings_common import federation_request
except Exception:  # pragma: no cover - defensive fallback for standalone runs
    federation_request = None  # type: ignore[assignment]


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SOURCE = "afc"
REQUEST_DELAY = 1.5
BATCH_SIZE = 100

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}

LOCAL_PROBE_BLOCKER = (
    "Sandbox DNS probe failed for all AFC/host URLs; escalated network probe was "
    "rejected by the platform usage gate."
)


@dataclass(frozen=True)
class AFCScrapeSource:
    source_id: str
    url: str
    kind: str
    edition_name: str
    source_type: str = "asian_championship"
    blocked_reason: str | None = None
    parser: str | None = None


DEFAULT_SOURCES = [
    AFCScrapeSource(
        source_id="afc-2022-cadet-result-page",
        url="https://asian-fencing.com/?p=7948",
        kind="html",
        edition_name="Asian Cadet Circuit 2022",
        source_type="afc_circuit",
        blocked_reason=LOCAL_PROBE_BLOCKER,
        parser="html_table",
    ),
    AFCScrapeSource(
        source_id="afc-2025-cadet-circuit-ranking-pdf",
        url="https://asian-fencing.com/wp-content/uploads/2025/09/Fencing-Confederation-of-Asia-mens-epee.pdf",
        kind="pdf",
        edition_name="Fencing Confederation of Asia Cadet Circuit Ranking 2025",
        source_type="afc_circuit",
        blocked_reason=LOCAL_PROBE_BLOCKER,
        parser="pdf_text_table",
    ),
    AFCScrapeSource(
        source_id="afc-2025-u23-malaysia-pdf",
        url="https://asian-fencing.com/wp-content/uploads/2025/10/Asian-U23-MALAYSIA-2025.pdf",
        kind="pdf",
        edition_name="Asian U23 Fencing Championships Malaysia 2025",
        source_type="asian_championship",
        blocked_reason=LOCAL_PROBE_BLOCKER,
        parser="pdf_text_table",
    ),
    AFCScrapeSource(
        source_id="kuwait-2024-host",
        url="https://kuwait2024afc.com/",
        kind="html",
        edition_name="Asian Fencing Championships Kuwait 2024",
        source_type="asian_championship",
        blocked_reason=LOCAL_PROBE_BLOCKER,
        parser="html_table",
    ),
    AFCScrapeSource(
        source_id="bali-2025-host",
        url="https://asfc.inaikasi.org/",
        kind="html",
        edition_name="Asian Senior Fencing Championships Bali 2025",
        source_type="asian_championship",
        blocked_reason=LOCAL_PROBE_BLOCKER,
        parser="html_table",
    ),
]


COUNTRY_ALIASES = {
    "AFGHANISTAN": "AFG",
    "AFG": "AFG",
    "AUSTRALIA": "AUS",
    "AUS": "AUS",
    "BAHRAIN": "BRN",
    "BRN": "BRN",
    "CHINA": "CHN",
    "PEOPLE'S REPUBLIC OF CHINA": "CHN",
    "PR CHINA": "CHN",
    "CHN": "CHN",
    "CHINESE TAIPEI": "TPE",
    "TAIWAN": "TPE",
    "TPE": "TPE",
    "HONG KONG": "HKG",
    "HONG KONG, CHINA": "HKG",
    "HONG KONG CHINA": "HKG",
    "HKG": "HKG",
    "INDIA": "IND",
    "IND": "IND",
    "INDONESIA": "INA",
    "INA": "INA",
    "IRAN": "IRI",
    "IR IRAN": "IRI",
    "ISLAMIC REPUBLIC OF IRAN": "IRI",
    "IRI": "IRI",
    "IRAQ": "IRQ",
    "IRQ": "IRQ",
    "JAPAN": "JPN",
    "JPN": "JPN",
    "JORDAN": "JOR",
    "JOR": "JOR",
    "KAZAKHSTAN": "KAZ",
    "KAZ": "KAZ",
    "KOREA": "KOR",
    "SOUTH KOREA": "KOR",
    "REPUBLIC OF KOREA": "KOR",
    "KOR": "KOR",
    "KUWAIT": "KUW",
    "KUW": "KUW",
    "KYRGYZSTAN": "KGZ",
    "KGZ": "KGZ",
    "LEBANON": "LBN",
    "LBN": "LBN",
    "MACAO": "MAC",
    "MACAU": "MAC",
    "MACAO, CHINA": "MAC",
    "MACAO CHINA": "MAC",
    "MAC": "MAC",
    "MALAYSIA": "MAS",
    "MAS": "MAS",
    "MONGOLIA": "MGL",
    "MGL": "MGL",
    "NEPAL": "NEP",
    "NEP": "NEP",
    "PAKISTAN": "PAK",
    "PAK": "PAK",
    "PHILIPPINES": "PHI",
    "PHI": "PHI",
    "QATAR": "QAT",
    "QAT": "QAT",
    "SAUDI ARABIA": "KSA",
    "KSA": "KSA",
    "SINGAPORE": "SGP",
    "SIN": "SGP",
    "SGP": "SGP",
    "SYRIA": "SYR",
    "SYR": "SYR",
    "THAILAND": "THA",
    "THA": "THA",
    "UNITED ARAB EMIRATES": "UAE",
    "UAE": "UAE",
    "UZBEKISTAN": "UZB",
    "UZB": "UZB",
    "VIETNAM": "VIE",
    "VIET NAM": "VIE",
    "VIE": "VIE",
    "대한민국": "KOR",
    "한국": "KOR",
    "일본": "JPN",
    "중국": "CHN",
    "홍콩": "HKG",
    "카자흐스탄": "KAZ",
    "쿠웨이트": "KUW",
    "韓国": "KOR",
    "日本": "JPN",
    "中国": "CHN",
    "中國": "CHN",
    "香港": "HKG",
    "カザフスタン": "KAZ",
    "韩国": "KOR",
    "中华台北": "TPE",
    "中華台北": "TPE",
    "中国香港": "HKG",
    "中國香港": "HKG",
    "كازاخستان": "KAZ",
    "الكويت": "KUW",
    "اليابان": "JPN",
    "كوريا الجنوبية": "KOR",
    "الصين": "CHN",
}

COUNTRY_NAMES = {
    "AFG": "Afghanistan",
    "AUS": "Australia",
    "BRN": "Bahrain",
    "CHN": "China",
    "HKG": "Hong Kong",
    "INA": "Indonesia",
    "IND": "India",
    "IRI": "Iran",
    "IRQ": "Iraq",
    "JOR": "Jordan",
    "JPN": "Japan",
    "KAZ": "Kazakhstan",
    "KGZ": "Kyrgyzstan",
    "KOR": "South Korea",
    "KSA": "Saudi Arabia",
    "KUW": "Kuwait",
    "LBN": "Lebanon",
    "MAC": "Macau",
    "MAS": "Malaysia",
    "MGL": "Mongolia",
    "NEP": "Nepal",
    "PAK": "Pakistan",
    "PHI": "Philippines",
    "QAT": "Qatar",
    "SGP": "Singapore",
    "SYR": "Syria",
    "THA": "Thailand",
    "TPE": "Chinese Taipei",
    "UAE": "United Arab Emirates",
    "UZB": "Uzbekistan",
    "VIE": "Vietnam",
}

HEADER_ALIASES = {
    "rank": {
        "rank",
        "ranking",
        "place",
        "pos",
        "position",
        "classification",
        "순위",
        "順位",
        "排名",
        "名次",
        "الترتيب",
        "المركز",
    },
    "name": {
        "name",
        "fencer",
        "athlete",
        "competitor",
        "선수",
        "성명",
        "이름",
        "選手",
        "氏名",
        "名前",
        "姓名",
        "运动员",
        "運動員",
        "الاسم",
        "اللاعب",
        "اللاعبة",
    },
    "country": {
        "country",
        "nation",
        "nationality",
        "noc",
        "statecountry",
        "state country",
        "국가",
        "소속",
        "国",
        "國",
        "国家",
        "國家",
        "الدولة",
        "البلد",
        "الجنسية",
    },
    "fie_id": {"fieid", "fie id", "id fie", "fie", "license", "licence", "번호", "id"},
    "medal": {"medal", "메달", "メダル", "奖牌", "獎牌", "ميدالية", "الميدالية"},
    "points": {"points", "pts", "score", "점수", "포인트", "ポイント", "积分", "積分", "النقاط"},
}

MEDAL_ALIASES = {
    "gold": "Gold",
    "g": "Gold",
    "1": "Gold",
    "금": "Gold",
    "金": "Gold",
    "ذهبية": "Gold",
    "ذهب": "Gold",
    "silver": "Silver",
    "s": "Silver",
    "2": "Silver",
    "은": "Silver",
    "銀": "Silver",
    "فضية": "Silver",
    "فضه": "Silver",
    "bronze": "Bronze",
    "b": "Bronze",
    "3": "Bronze",
    "동": "Bronze",
    "銅": "Bronze",
    "برونزية": "Bronze",
    "برونز": "Bronze",
}

MONTHS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}


def clean_text(value) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _norm_key(value) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value) or "")
    text = text.replace("\u2019", "'").replace(".", "")
    return re.sub(r"\s+", " ", text).strip().upper()


def normalize_country_code(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = _norm_key(text)
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]
    compact = re.sub(r"[^A-Z0-9]", "", key)
    if compact in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[compact]
    if re.fullmatch(r"[A-Z]{3}", compact):
        return compact
    return None


def country_name_for_code(code: str | None) -> str | None:
    return COUNTRY_NAMES.get(code or "")


def _field_for_header(header) -> str | None:
    raw = unicodedata.normalize("NFKC", clean_text(header) or "").lower()
    compact = re.sub(r"[\s/_.,:;()\\-]+", "", raw)
    spaced = re.sub(r"[\s/_.,:;()\\-]+", " ", raw).strip()
    for field, aliases in HEADER_ALIASES.items():
        if compact in aliases or spaced in aliases or raw in aliases:
            return field
    for field, aliases in HEADER_ALIASES.items():
        if any(alias and (alias in compact or alias in spaced or alias in raw) for alias in aliases):
            return field
    return None


def _rank_to_int(value) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def _points_to_float(value) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def normalize_medal(value, rank: int | None = None) -> str | None:
    text = clean_text(value)
    if text:
        key = unicodedata.normalize("NFKC", text).strip().lower()
        key = key.replace(".", "")
        if key in MEDAL_ALIASES:
            return MEDAL_ALIASES[key]
        compact = re.sub(r"\s+", "", key)
        if compact in MEDAL_ALIASES:
            return MEDAL_ALIASES[compact]
    if rank in (1, 2, 3):
        return {1: "Gold", 2: "Silver", 3: "Bronze"}[rank]
    return None


def _title_latin_piece(piece: str) -> str:
    return "-".join(part.capitalize() for part in piece.split("-"))


def normalize_fencer_name(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if "," not in text:
        return text
    last, first = [clean_text(part) or "" for part in text.split(",", 1)]
    ordered = f"{first} {last}".strip()
    if ordered.isascii():
        return " ".join(_title_latin_piece(piece) for piece in ordered.split())
    return ordered


def _normalized_search_text(value) -> str:
    return unicodedata.normalize("NFKC", value or "").lower()


def classify_event(text: str) -> dict[str, object]:
    label = _normalized_search_text(text)

    weapon = None
    if re.search(r"\b(epee|epée|espada|degen)\b", label) or any(token in label for token in ("에페", "エペ", "重剑", "重劍", "سيف المبارزة")):
        weapon = "Epee"
    elif re.search(r"\b(foil|fleuret|floret|florete)\b", label) or any(token in label for token in ("플뢰레", "フルーレ", "花剑", "花劍", "الشيش")):
        weapon = "Foil"
    elif re.search(r"\b(sabre|saber|sable)\b", label) or any(token in label for token in ("사브르", "サーブル", "佩剑", "佩劍", "سابر")):
        weapon = "Sabre"

    gender = None
    if re.search(r"\b(women|womens|women's|female|ladies)\b", label) or any(token in label for token in ("여자", "女子", "女", "سيدات", "نساء")):
        gender = "Women"
    elif re.search(r"\b(men|mens|men's|male)\b", label) or any(token in label for token in ("남자", "男子", "男", "رجال")):
        gender = "Men"

    category = None
    if re.search(r"\b(cadet|cadets|u17|u18)\b", label) or any(token in label for token in ("카데트", "カデ", "少年")):
        category = "Cadet"
    elif re.search(r"\b(junior|juniors|u20|u23)\b", label) or any(token in label for token in ("주니어", "ジュニア", "青年")):
        category = "Junior"
    elif re.search(r"\b(senior|seniors)\b", label) or any(token in label for token in ("시니어", "シニア", "成年", "كبار")):
        category = "Senior"

    team = bool(re.search(r"\b(team|teams|equipe)\b", label) or any(token in label for token in ("단체", "団体", "团体", "團體", "فرق")))
    return {"weapon": weapon, "gender": gender, "category": category, "team": team}


def _event_code(event: dict) -> str:
    bits = [
        event.get("category") or "open",
        event.get("gender") or "mixed",
        event.get("weapon") or "unknown",
        "team" if event.get("team") else "individual",
    ]
    return "-".join(_slugify(str(bit)) for bit in bits)


def _slugify(value: str) -> str:
    text = value.replace("ı", "i").replace("İ", "I")
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "afc"


def _extract_date_from_text(text: str | None) -> str | None:
    value = clean_text(text)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        for match in re.finditer(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", value):
            try:
                return datetime.strptime(match.group(0), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

    match2 = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+((?:19|20)\d{2})\b", value)
    if match2:
        month = MONTHS.get(match2.group(2).lower())
        if month:
            return f"{match2.group(3)}-{month}-{int(match2.group(1)):02d}"

    match3 = re.search(r"\b((?:19|20)\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", value)
    if match3:
        return f"{match3.group(1)}-{int(match3.group(2)):02d}-{int(match3.group(3)):02d}"

    return None


def _extract_page_date(soup: BeautifulSoup) -> str | None:
    for node in soup.find_all("time"):
        for key in ("datetime", "date"):
            parsed = _extract_date_from_text(node.get(key))
            if parsed:
                return parsed
        parsed = _extract_date_from_text(node.get_text(" ", strip=True))
        if parsed:
            return parsed
    return _extract_date_from_text(soup.get_text(" ", strip=True)[:2500])


def _headers_from_table(table) -> tuple[list[str], list]:
    rows = table.find_all("tr")
    if not rows:
        return [], []
    first_cells = rows[0].find_all(["th", "td"])
    headers = [clean_text(cell.get_text(" ", strip=True)) or "" for cell in first_cells]
    body_rows = rows[1:] if first_cells else rows
    if not any(_field_for_header(header) for header in headers):
        return [], rows
    return headers, body_rows


def _row_cells(row) -> list[str]:
    return [clean_text(cell.get_text(" ", strip=True)) or "" for cell in row.find_all(["td", "th"])]


def _field_indexes(headers: list[str]) -> dict[str, int]:
    indexes = {}
    for idx, header in enumerate(headers):
        field = _field_for_header(header)
        if field and field not in indexes:
            indexes[field] = idx
    return indexes


def _value(cells: list[str], indexes: dict[str, int], field: str) -> str | None:
    idx = indexes.get(field)
    if idx is None or idx >= len(cells):
        return None
    return clean_text(cells[idx])


def _parse_table_rows(table, source_url: str) -> list[dict]:
    headers, body_rows = _headers_from_table(table)
    indexes = _field_indexes(headers)
    if not {"rank", "name", "country"}.issubset(indexes):
        return []

    rows = []
    for tr in body_rows:
        cells = _row_cells(tr)
        if len(cells) < 3:
            continue
        rank = _rank_to_int(_value(cells, indexes, "rank"))
        name = normalize_fencer_name(_value(cells, indexes, "name"))
        country = normalize_country_code(_value(cells, indexes, "country"))
        if not rank or not name or not country:
            continue
        fie_id = clean_text(_value(cells, indexes, "fie_id"))
        points = _points_to_float(_value(cells, indexes, "points"))
        infer_medal = "points" not in indexes or "medal" in indexes
        medal = normalize_medal(_value(cells, indexes, "medal"), rank if infer_medal else None)
        rows.append(
            {
                "rank": rank,
                "name": name,
                "country": country,
                "fie_id": fie_id,
                "medal": medal,
                "points": points,
                "source_url": source_url,
            }
        )
    return rows


def _table_heading(table, soup: BeautifulSoup) -> str:
    for previous in table.find_all_previous(["h1", "h2", "h3", "caption"]):
        text = clean_text(previous.get_text(" ", strip=True))
        if text:
            return text
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    return clean_text(title) or "AFC Result"


def parse_html_result_events(html: str, source_url: str, edition_name: str | None = None) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    page_date = _extract_page_date(soup)
    events = []

    for table in soup.find_all("table"):
        result_rows = _parse_table_rows(table, source_url)
        if not result_rows:
            continue
        event_name = _table_heading(table, soup)
        combined_label = " ".join(part for part in [edition_name, event_name, soup.title.get_text(" ", strip=True) if soup.title else None] if part)
        classification = classify_event(combined_label)
        event = {
            "edition_name": edition_name,
            "event_name": event_name,
            "event_code": None,
            "weapon": classification["weapon"],
            "gender": classification["gender"],
            "category": classification["category"],
            "team": classification["team"],
            "date": page_date,
            "source_url": source_url,
            "results": result_rows,
        }
        event["event_code"] = _event_code(event)
        events.append(event)
    return events


def parse_pdf_text_events(text: str, source_url: str, edition_name: str | None = None) -> list[dict]:
    """Parse simple AFC/FCA ranking PDFs after text extraction."""
    lines = [str(line).strip() for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return []

    title = next((line for line in lines if classify_event(line).get("weapon") and classify_event(line).get("gender")), lines[0])
    classification = classify_event(" ".join([edition_name or "", title]))
    date = _extract_date_from_text(" ".join(lines[:8]))
    header_idx = None
    indexes = {}
    for idx, line in enumerate(lines):
        parts = re.split(r"\s{2,}|\t+", line)
        fields = [_field_for_header(part) for part in parts]
        if {"rank", "name", "country"}.issubset(set(field for field in fields if field)):
            header_idx = idx
            indexes = {field: pos for pos, field in enumerate(fields) if field and field not in indexes}
            break

    rows = []
    if header_idx is not None:
        for line in lines[header_idx + 1 :]:
            if not re.match(r"^\s*\d+", line):
                continue
            parts = re.split(r"\s{2,}|\t+", line)
            if not indexes or max(indexes.values()) >= len(parts):
                continue
            rank = _rank_to_int(parts[indexes["rank"]])
            name = normalize_fencer_name(parts[indexes["name"]])
            country = normalize_country_code(parts[indexes["country"]])
            if not rank or not name or not country:
                continue
            infer_medal = "points" not in indexes or "medal" in indexes
            rows.append(
                {
                    "rank": rank,
                    "name": name,
                    "country": country,
                    "fie_id": clean_text(parts[indexes["fie_id"]]) if "fie_id" in indexes and indexes["fie_id"] < len(parts) else None,
                    "medal": normalize_medal(parts[indexes["medal"]], rank if infer_medal else None) if "medal" in indexes and indexes["medal"] < len(parts) else normalize_medal(None, rank if infer_medal else None),
                    "points": _points_to_float(parts[indexes["points"]]) if "points" in indexes and indexes["points"] < len(parts) else None,
                    "source_url": source_url,
                }
            )
    else:
        for line in lines:
            match = re.match(r"^(?P<rank>\d+)[=.]*\s+(?P<body>.+?)\s+(?P<country>[A-Z]{3})\s+(?P<points>\d+(?:[.,]\d+)?)?$", line)
            if not match:
                continue
            rows.append(
                {
                    "rank": int(match.group("rank")),
                    "name": normalize_fencer_name(match.group("body")),
                    "country": normalize_country_code(match.group("country")),
                    "fie_id": None,
                    "medal": normalize_medal(None, None if match.group("points") else int(match.group("rank"))),
                    "points": _points_to_float(match.group("points")),
                    "source_url": source_url,
                }
            )

    if not rows:
        return []
    event = {
        "edition_name": edition_name,
        "event_name": title,
        "event_code": None,
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": classification["category"],
        "team": classification["team"],
        "date": date,
        "source_url": source_url,
        "results": rows,
    }
    event["event_code"] = _event_code(event)
    return [event]


def _pdf_bytes_to_text(payload: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def probe_sources(sources: list[AFCScrapeSource] | None = None, session=None, timeout: int = 15) -> list[dict]:
    session = session or requests.Session()
    results = []
    for source in sources or DEFAULT_SOURCES:
        if source.blocked_reason:
            results.append(
                {
                    "source_id": source.source_id,
                    "url": source.url,
                    "status": None,
                    "content_type": None,
                    "blocked": True,
                    "evidence": source.blocked_reason,
                }
            )
            continue
        try:
            response = session.get(source.url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            content_type = response.headers.get("content-type", "").split(";")[0] or None
            blocked = response.status_code in {401, 403, 407, 451} or "cloudflare" in response.text[:500].lower()
            evidence = f"HTTP {response.status_code}"
            if blocked:
                evidence = f"{evidence}; blocked/geoblocked or login page"
            results.append(
                {
                    "source_id": source.source_id,
                    "url": response.url,
                    "status": response.status_code,
                    "content_type": content_type,
                    "blocked": blocked,
                    "evidence": evidence,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "source_id": source.source_id,
                    "url": source.url,
                    "status": None,
                    "content_type": None,
                    "blocked": True,
                    "evidence": f"{type(exc).__name__}: {exc}",
                }
            )
    return results


def _normalize_identity_text(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = unicodedata.normalize("NFKC", text).lower().strip()
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _query_rows(query):
    response = query.execute()
    return response.data or []


def _match_fencer(client, *, fie_id: str | None, name: str | None, country: str | None) -> str | None:
    if not client:
        return None
    if fie_id:
        try:
            rows = _query_rows(
                client.table("fs_fencers")
                .select("id")
                .eq("fie_id", str(fie_id))
                .limit(2)
            )
            if rows:
                return rows[0].get("id")
        except Exception:
            pass

    if name and country:
        candidates = [country]
        full_country = country_name_for_code(country)
        if full_country:
            candidates.append(full_country)
        for candidate_country in candidates:
            try:
                rows = _query_rows(
                    client.table("fs_fencers")
                    .select("id")
                    .ilike("name", name)
                    .eq("country", candidate_country)
                    .limit(2)
                )
                if len(rows) == 1:
                    return rows[0].get("id")
            except Exception:
                continue

        try:
            rows = _query_rows(
                client.table("fs_fencer_identities")
                .select("fs_fencer_row_ids")
                .ilike("canonical_name", name)
                .eq("country", country)
                .limit(2)
            )
            if len(rows) == 1:
                row_ids = rows[0].get("fs_fencer_row_ids") or []
                if row_ids:
                    return row_ids[0]
        except Exception:
            pass
    return None


def build_result_rows(
    *,
    tournament_id: str,
    event: dict,
    result_rows: list[dict],
    client=None,
    unmatched: list[dict] | None = None,
) -> list[dict]:
    client = client or supabase
    unmatched = unmatched if unmatched is not None else []
    db_rows = []
    for row in result_rows:
        rank = _rank_to_int(row.get("rank"))
        name = clean_text(row.get("name"))
        country = normalize_country_code(row.get("country"))
        if not rank or not name or not country:
            continue

        fencer_id = None
        if not event.get("team"):
            fencer_id = _match_fencer(client, fie_id=clean_text(row.get("fie_id")), name=name, country=country)
            if not fencer_id:
                unmatched.append(
                    {
                        "tournament_id": tournament_id,
                        "event_name": event.get("event_name"),
                        "rank": rank,
                        "name": name,
                        "country": country,
                        "fie_id": clean_text(row.get("fie_id")),
                        "reason": "no_fencer_match",
                        "source_url": row.get("source_url") or event.get("source_url"),
                    }
                )
                continue

        db_row = {
            "tournament_id": tournament_id,
            "name": name,
            "nationality": country,
            "country": country,
            "rank": rank,
            "placement": rank,
            "medal": normalize_medal(row.get("medal"), rank),
            "fencer_id": fencer_id,
            "weapon": event.get("weapon"),
            "category": event.get("category"),
            "date": event.get("date"),
            "metadata": {
                "source": SOURCE,
                "source_url": row.get("source_url") or event.get("source_url"),
                "event_name": event.get("event_name"),
                "edition_name": event.get("edition_name"),
                "gender": event.get("gender"),
                "team": bool(event.get("team")),
                "points": row.get("points"),
                "country_code": country,
                "fie_id": clean_text(row.get("fie_id")),
            },
        }
        if row.get("fie_id"):
            db_row["fie_fencer_id"] = str(row["fie_id"])
        db_rows.append(db_row)
    return db_rows


def upsert_tournament(event: dict, source: AFCScrapeSource):
    source_id = f"afc:{source.source_id}:{event.get('event_code') or _event_code(event)}"
    season = _extract_date_from_text(event.get("date") or event.get("edition_name") or "") or _extract_year(event.get("edition_name"))
    row = {
        "source_id": source_id,
        "name": " - ".join(part for part in [event.get("edition_name") or source.edition_name, event.get("event_name")] if part),
        "season": season,
        "type": source.source_type,
        "weapon": event.get("weapon"),
        "gender": event.get("gender"),
        "category": event.get("category"),
        "country": None,
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "source_url": event.get("source_url") or source.url,
            "source_id": source.source_id,
            "event_code": event.get("event_code"),
            "event_name": event.get("event_name"),
            "edition_name": event.get("edition_name") or source.edition_name,
            "team": bool(event.get("team")),
        },
    }
    result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()  # type: ignore[union-attr]
    return result.data[0]["id"] if result.data else None


def _extract_year(text) -> str | None:
    match = re.search(r"\b((?:19|20)\d{2})\b", str(text or ""))
    return match.group(1) if match else None


def _fetch_source(source: AFCScrapeSource) -> bytes | str | None:
    if source.blocked_reason:
        return None
    requester = federation_request if federation_request is not None else requests.request
    response = requester("get", source.url, headers=HEADERS, timeout=30)
    if response.status_code != 200:
        return None
    if source.kind == "pdf":
        return response.content
    return response.text


def parse_source_payload(source: AFCScrapeSource, payload: bytes | str | None) -> list[dict]:
    if payload is None:
        return []
    if source.kind == "pdf":
        text = _pdf_bytes_to_text(payload) if isinstance(payload, bytes) else payload
        return parse_pdf_text_events(text, source.url, source.edition_name)
    return parse_html_result_events(str(payload), source.url, source.edition_name)


def write_results_for_event(tournament_id: str, event: dict) -> tuple[int, int]:
    unmatched: list[dict] = []
    db_rows = build_result_rows(
        tournament_id=tournament_id,
        event=event,
        result_rows=event.get("results") or [],
        client=supabase,
        unmatched=unmatched,
    )
    for row in unmatched:
        print(
            "  Unmatched AFC row: "
            f"{row['event_name']} rank={row['rank']} name={row['name']} country={row['country']} source={row['source_url']}"
        )
    if not db_rows:
        return 0, len(unmatched)

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()  # type: ignore[union-attr]
    written = 0
    for index in range(0, len(db_rows), BATCH_SIZE):
        batch = db_rows[index : index + BATCH_SIZE]
        supabase.table("fs_results").insert(batch).execute()  # type: ignore[union-attr]
        written += len(batch)
    return written, len(unmatched)


def run(sources: list[AFCScrapeSource] | None = None) -> tuple[int, int, int]:
    if not supabase:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    sources = sources or DEFAULT_SOURCES
    done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])
    written = failed = skipped = 0
    completed_sources = set(done_source_ids)

    for source in sources:
        if source.source_id in done_source_ids:
            skipped += 1
            continue
        if source.blocked_reason:
            print(f"Skipping blocked AFC source {source.source_id}: {source.blocked_reason}")
            skipped += 1
            continue
        try:
            payload = _fetch_source(source)
            events = parse_source_payload(source, payload)
            if not events:
                print(f"No parseable AFC result rows found for {source.source_id}")
                skipped += 1
                continue
            for event in events:
                tournament_id = upsert_tournament(event, source)
                if not tournament_id:
                    failed += 1
                    continue
                event_written, unmatched_count = write_results_for_event(tournament_id, event)
                written += event_written
                skipped += unmatched_count
            completed_sources.add(source.source_id)
            time.sleep(REQUEST_DELAY)
        except Exception as exc:
            print(f"AFC source failed {source.source_id}: {exc}")
            failed += 1

    set_state(SOURCE, "done_source_ids", sorted(completed_sources))
    set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
    return written, failed, skipped


def main():
    run_log = ScraperRunLogger("scrape_afc").start()
    try:
        written, failed, skipped = run()
        run_log.complete(written, failed, skipped)
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

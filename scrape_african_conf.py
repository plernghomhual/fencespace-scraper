"""
African Fencing Confederation championship results scraper.

Probe summary (verified 2026-06-02 with web-accessible sources):
  CAE official: https://www.cae-fencing.org/ publishes 2025 Lagos posts and
    links to FencingWorldwide/FencingTimeLive result surfaces.
  Old mirror: https://afrique-escrime.org/ has no durable structured results.
  FencingWorldwide: public tournament/event/result pages expose sparse final
    ranking rows for African Championships.
  FencingTimeLive: current CAE live-results schedule is login-gated.
  FIE: public competition pages, news articles, and delegation PDFs preserve
    official event metadata and medallist evidence, but static full result rows
    are inconsistent outside FIE's dynamic pages.
"""
from __future__ import annotations

import io
import os
import re
import time
import unicodedata
from datetime import UTC, datetime, timezone
from typing import Any
from urllib.parse import urljoin

import pdfplumber
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

SOURCE = "african_conf"
REQUEST_DELAY = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}

PROBE_URLS = [
    "https://www.cae-fencing.org/",
    "https://afrique-escrime.org/",
    "https://www.fencingworldwide.com/en/",
    "https://www.fencingtimelive.com/tournaments/eventSchedule/1F58A08E34524BDBBFBE661B78A837E1",
    "https://fie.org/competitions/2025/586",
    "https://static.fie.org/uploads/36/180679-2025%20Information%20for%20delegations%20%28Lagos%29.pdf",
]

KNOWN_PUBLIC_SOURCES = [
    "https://www.fencingworldwide.com/en/30332-2025/tournament/",
    "https://www.fencingworldwide.com/en/30332-2025/all-medaillists/",
    "https://fie.org/articles/1453",
]

COUNTRY_ALIASES = {
    "ALG": "ALG",
    "ALGERIA": "ALG",
    "ALGERIE": "ALG",
    "ALGERIE": "ALG",
    "ALGÉRIE": "ALG",
    "الجزائر": "ALG",
    "ANG": "ANG",
    "ANGOLA": "ANG",
    "BEN": "BEN",
    "BENIN": "BEN",
    "BÉNIN": "BEN",
    "BOT": "BOT",
    "BOTSWANA": "BOT",
    "BUR": "BUR",
    "BURKINA FASO": "BUR",
    "CMR": "CMR",
    "CAMEROON": "CMR",
    "CAMEROUN": "CMR",
    "CPV": "CPV",
    "CAPE VERDE": "CPV",
    "CABO VERDE": "CPV",
    "CIV": "CIV",
    "COTE D'IVOIRE": "CIV",
    "COTE D IVOIRE": "CIV",
    "CÔTE D'IVOIRE": "CIV",
    "IVORY COAST": "CIV",
    "ساحل العاج": "CIV",
    "COD": "COD",
    "CONGO DR": "COD",
    "DEMOCRATIC REPUBLIC OF CONGO": "COD",
    "EGY": "EGY",
    "EGYPT": "EGY",
    "EGYPTE": "EGY",
    "ÉGYPTE": "EGY",
    "مصر": "EGY",
    "ETH": "ETH",
    "ETHIOPIA": "ETH",
    "GHA": "GHA",
    "GHANA": "GHA",
    "GUI": "GUI",
    "GUINEA": "GUI",
    "KEN": "KEN",
    "KENYA": "KEN",
    "LBA": "LBA",
    "LIBYA": "LBA",
    "LIBYE": "LBA",
    "MAR": "MAR",
    "MOROCCO": "MAR",
    "MAROC": "MAR",
    "المغرب": "MAR",
    "MLI": "MLI",
    "MALI": "MLI",
    "MRI": "MRI",
    "MAURITIUS": "MRI",
    "MAURICE": "MRI",
    "NGR": "NGR",
    "NIGERIA": "NGR",
    "NIGÉRIA": "NGR",
    "NIGERIA": "NGR",
    "نيجيريا": "NGR",
    "NIG": "NIG",
    "NIGER": "NIG",
    "RSA": "RSA",
    "SOUTH AFRICA": "RSA",
    "AFRIQUE DU SUD": "RSA",
    "جنوب أفريقيا": "RSA",
    "RWA": "RWA",
    "RWANDA": "RWA",
    "SEN": "SEN",
    "SENEGAL": "SEN",
    "SÉNÉGAL": "SEN",
    "SUDAN": "SUD",
    "SUD": "SUD",
    "TOG": "TOG",
    "TOGO": "TOG",
    "TUN": "TUN",
    "TUNISIA": "TUN",
    "TUNISIE": "TUN",
    "تونس": "TUN",
    "UGA": "UGA",
    "UGANDA": "UGA",
    "ZAM": "ZAM",
    "ZAMBIA": "ZAM",
    "ZIM": "ZIM",
    "ZIMBABWE": "ZIM",
}

HEADER_ALIASES = {
    "rank": {
        "rank",
        "rk",
        "place",
        "placement",
        "position",
        "rang",
        "classement",
        "classementfinal",
    },
    "name": {
        "name",
        "athlete",
        "fencer",
        "competitor",
        "nom",
        "nomprenom",
        "nomprenoms",
        "tireur",
        "tireuse",
        "joueur",
        "joueuse",
        "fullname",
        "nationalityname",
    },
    "team": {"team", "equipe", "equipes", "nationteam"},
    "country": {"country", "nation", "nationality", "pays", "federation", "fédération"},
    "medal": {"medal", "medaille", "médaille"},
    "points": {"points", "pts", "point", "score", "total"},
    "fie_id": {"fieid", "idfie", "id", "licence", "license", "fie"},
}

ARABIC_HEADER_ALIASES = {
    "الترتيب": "rank",
    "الترتيب النهائي": "rank",
    "المركز": "rank",
    "اللاعب": "name",
    "اللاعبة": "name",
    "الاسم": "name",
    "الاسم الكامل": "name",
    "الفريق": "team",
    "الدولة": "country",
    "البلد": "country",
    "الجنسية": "country",
    "الميدالية": "medal",
    "ميدالية": "medal",
    "النقاط": "points",
    "نقاط": "points",
    "معرف الاتحاد الدولي": "fie_id",
    "رقم الاتحاد الدولي": "fie_id",
}

MONTHS = {
    "january": 1,
    "janvier": 1,
    "يناير": 1,
    "february": 2,
    "fevrier": 2,
    "février": 2,
    "فبراير": 2,
    "march": 3,
    "mars": 3,
    "مارس": 3,
    "april": 4,
    "avril": 4,
    "أبريل": 4,
    "مايو": 5,
    "may": 5,
    "mai": 5,
    "june": 6,
    "juin": 6,
    "يونيو": 6,
    "july": 7,
    "juillet": 7,
    "يوليو": 7,
    "august": 8,
    "aout": 8,
    "août": 8,
    "أغسطس": 8,
    "september": 9,
    "septembre": 9,
    "سبتمبر": 9,
    "october": 10,
    "octobre": 10,
    "أكتوبر": 10,
    "november": 11,
    "novembre": 11,
    "نوفمبر": 11,
    "december": 12,
    "decembre": 12,
    "décembre": 12,
    "ديسمبر": 12,
}


def _clean_text(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def _latin_key(value):
    text = _clean_text(value) or ""
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if unicodedata.category(ch) != "Mn")
    text = text.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", text)


def _contains_arabic(value):
    return bool(re.search(r"[\u0600-\u06FF]", str(value or "")))


def normalize_country(value):
    text = _clean_text(value)
    if not text:
        return None
    key = text.upper().replace(".", "")
    key = re.sub(r"\s+", " ", key)
    key = "".join(ch for ch in unicodedata.normalize("NFKD", key) if unicodedata.category(ch) != "Mn")
    if text in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[text]
    return COUNTRY_ALIASES.get(key, key if re.fullmatch(r"[A-Z]{3}", key) else None)


def _title_word(word):
    return "-".join(piece.capitalize() for piece in word.split("-"))


def normalize_name(value):
    text = _clean_text(value)
    if not text:
        return None
    if _contains_arabic(text):
        return text
    text = text.strip(",")
    if "," in text:
        last, first = [part.strip() for part in text.split(",", 1)]
        text = f"{first} {last}"
    parts = text.split()
    leading_surname = []
    given: list[Any] = []
    for part in parts:
        letters = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ]", "", part)
        if not given and letters and letters.upper() == letters:
            leading_surname.append(part)
        else:
            given.append(part)
    if leading_surname and given:
        parts = given + leading_surname
    return " ".join(_title_word(part) for part in parts)


def normalize_date(value):
    text = _clean_text(value)
    if not text:
        return None
    iso = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if iso:
        year, month, day = [int(part) for part in iso.groups()]
        return f"{year:04d}-{month:02d}-{day:02d}"
    numeric = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b", text)
    if numeric:
        day, month, year = [int(part) for part in numeric.groups()]
        return f"{year:04d}-{month:02d}-{day:02d}"
    month_match = re.search(r"\b(\d{1,2})\s+([A-Za-zÀ-ÖØ-öø-ÿ\u0600-\u06FF]+)\s*,?\s*(20\d{2})\b", text)
    if month_match:
        day = int(month_match.group(1))
        month_key = month_match.group(2).lower()
        month_key = "".join(
            ch for ch in unicodedata.normalize("NFKD", month_key) if unicodedata.category(ch) != "Mn"
        )
        matched_month = MONTHS.get(month_key) or MONTHS.get(month_match.group(2).lower())
        if matched_month:
            return f"{int(month_match.group(3)):04d}-{matched_month:02d}-{day:02d}"
    return None


def classify_event(event_name):
    text = _clean_text(event_name) or ""
    key = _latin_key(text)
    arabic = text
    weapon = None
    if "epee" in key or "سيف المبارزة" in arabic:
        weapon = "Epee"
    elif "foil" in key or "fleuret" in key or "فلوريه" in arabic:
        weapon = "Foil"
    elif "sabre" in key or "saber" in key or "سابر" in arabic or "الحسام" in arabic:
        weapon = "Sabre"

    gender = None
    if re.search(r"\bwomen\b|\bwoman\b|\bwomens\b", text, re.I) or "dames" in key or "femmes" in key:
        gender = "Women"
    elif "السيدات" in arabic or "سيدات" in arabic or "نساء" in arabic:
        gender = "Women"
    elif re.search(r"\bmen\b|\bmens\b|\bman\b", text, re.I) or "hommes" in key or "homme" in key:
        gender = "Men"
    elif "رجال" in arabic:
        gender = "Men"

    team = bool(
        re.search(r"\bteam\b|\bteams\b", text, re.I)
        or "equipe" in key
        or "equipes" in key
        or "فرق" in arabic
        or "الفريق" in arabic
        or "جماعي" in arabic
    )

    category = "Senior"
    if "junior" in key or "juniors" in key or "u20" in key:
        category = "Junior"
    elif "cadet" in key or "u17" in key:
        category = "Cadet"
    elif "veteran" in key or "veterans" in key:
        category = "Veteran"

    event_code = None
    if weapon and gender:
        event_code = f"{gender.lower()}-{weapon.lower()}-{'team' if team else 'individual'}"
    return {"weapon": weapon, "gender": gender, "category": category, "team": team, "event_code": event_code}


def _header_role(value):
    text = _clean_text(value) or ""
    if text in ARABIC_HEADER_ALIASES:
        return ARABIC_HEADER_ALIASES[text]
    key = _latin_key(text)
    for role, aliases in HEADER_ALIASES.items():
        if key in aliases:
            return role
    return None


def _cell_text(cell):
    parts = [cell.get_text(" ", strip=True)]
    for image in cell.find_all("img"):
        parts.extend([image.get("alt"), image.get("title")])
    return _clean_text(" ".join(part for part in parts if part))


def _rank_to_int(value):
    text = _clean_text(value) or ""
    if re.search(r"\bDNS\b|did not start|abandon|scratch|withdraw", text, re.I):
        return None
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def _medal_for_rank(rank):
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _normalize_medal(value, rank=None):
    text = _clean_text(value)
    if not text:
        return _medal_for_rank(rank)
    key = _latin_key(text)
    if key in {"gold", "or"} or "ذهب" in text:
        return "Gold"
    if key in {"silver", "argent"} or "فضة" in text:
        return "Silver"
    if key in {"bronze", "bronce"} or "برونز" in text:
        return "Bronze"
    return _medal_for_rank(rank)


def _parse_points(value):
    text = _clean_text(value)
    if not text:
        return None
    match = re.search(r"-?\d+(?:[,.]\d+)?", text)
    return float(match.group(0).replace(",", ".")) if match else None


def _split_country_and_name(value):
    text = _clean_text(value)
    if not text:
        return None, None
    parts = text.split()
    if len(parts) > 1:
        first_country = normalize_country(parts[0])
        if first_country:
            return first_country, " ".join(parts[1:])
        last_country = normalize_country(parts[-1])
        if last_country:
            return last_country, " ".join(parts[:-1])
    return None, text


def _event_heading_for_table(table):
    caption = table.find("caption")
    if caption:
        return _clean_text(caption.get_text(" ", strip=True))
    heading = table.find_previous(["h1", "h2", "h3", "h4"])
    return _clean_text(heading.get_text(" ", strip=True)) if heading else None


def _table_mapping(rows):
    if not rows:
        return {}, 0
    first = rows[0]
    header_cells = first.find_all(["th", "td"])
    mapping = {}
    for index, cell in enumerate(header_cells):
        role = _header_role(_cell_text(cell))
        if role and role not in mapping:
            mapping[role] = index
    has_header = bool(first.find_all("th")) or {"rank", "name"}.issubset(mapping) or {"rank", "team"}.issubset(mapping)
    return mapping, 1 if has_header else 0


def _parse_table_result_row(cells, mapping, classification, source_url):
    if "rank" not in mapping:
        return None
    rank = _rank_to_int(cells[mapping["rank"]])
    if rank is None:
        return None
    name_role = "team" if classification["team"] and "team" in mapping else "name"
    if name_role not in mapping:
        return None
    name_raw = cells[mapping[name_role]]
    country = normalize_country(cells[mapping["country"]]) if "country" in mapping else None
    if not country:
        country, name_raw = _split_country_and_name(name_raw)
    if not country or not name_raw:
        return None
    name = _clean_text(name_raw) if classification["team"] else normalize_name(name_raw)
    if not name:
        return None
    medal = _normalize_medal(cells[mapping["medal"]], rank) if "medal" in mapping else _medal_for_rank(rank)
    return {
        "rank": rank,
        "name": name,
        "country": country,
        "medal": medal,
        "points": _parse_points(cells[mapping["points"]]) if "points" in mapping else None,
        "fie_id": _clean_text(cells[mapping["fie_id"]]) if "fie_id" in mapping else None,
        "source_url": source_url,
    }


def parse_html_result_events(html, source_url, default_event_name=None, default_date=None):
    soup = BeautifulSoup(html or "", "html.parser")
    events = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        mapping, start_index = _table_mapping(rows)
        if "rank" not in mapping or ("name" not in mapping and "team" not in mapping):
            continue
        event_name = _event_heading_for_table(table) or default_event_name or "African Championships"
        classification = classify_event(event_name)
        if not classification["weapon"] or not classification["gender"]:
            continue
        result_rows = []
        for row in rows[start_index:]:
            cells = [_cell_text(cell) for cell in row.find_all(["td", "th"])]
            if len(cells) <= max(mapping.values()):
                continue
            result = _parse_table_result_row(cells, mapping, classification, source_url)
            if result:
                result_rows.append(result)
        if not result_rows:
            continue
        event_date = normalize_date(event_name) or normalize_date(default_date)
        events.append(
            {
                "edition_id": _edition_id(event_name, event_date),
                "edition_name": _edition_name(event_name, event_date),
                "event_name": event_name,
                "event_date": event_date,
                "source_url": source_url,
                "source_kind": "html_table",
                "classification": {key: classification[key] for key in ("weapon", "gender", "category", "team")},
                "event_code": classification["event_code"],
                "results": result_rows,
            }
        )
    return events


def _edition_id(event_name, event_date):
    year = None
    if event_date:
        year = event_date[:4]
    else:
        match = re.search(r"\b(20\d{2})\b", event_name or "")
        if match:
            year = match.group(1)
    return f"african-conf:{year or 'unknown'}"


def _edition_name(event_name, event_date):
    match = re.search(r"\b(20\d{2})\b", event_name or "")
    year = (event_date or "")[:4] or (match.group(1) if match else "Unknown")
    return f"African Fencing Championships {year}"


def parse_fencingworldwide_text_result_page(text, source_url):
    lines = [_clean_text(line) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    championship = next((line for line in lines if re.search(r"african championships", line, re.I)), "African Championships")
    location_index = lines.index(championship) + 1 if championship in lines else -1
    location = lines[location_index] if 0 <= location_index < len(lines) else None
    event_line = next((line for line in lines if re.search(r"results for ", line, re.I)), None)
    event_name = re.sub(r"^results for\s+", "", event_line or "", flags=re.I).strip() or "African Championships"
    event_date = next((normalize_date(line) for line in lines if normalize_date(line)), None)
    classification = classify_event(event_name)
    result_rows = []
    for line in lines:
        if re.search(r"did not start|\bDNS\b|withdraw", line, re.I):
            continue
        match = re.match(r"^T?(?P<rank>\d+)\.?\s+(?P<country>[A-Z]{3})\s+(?P<name>.+)$", line)
        if not match:
            continue
        rank = int(match.group("rank"))
        result_rows.append(
            {
                "rank": rank,
                "name": normalize_name(match.group("name")),
                "country": normalize_country(match.group("country")),
                "medal": _medal_for_rank(rank),
                "points": None,
                "fie_id": None,
                "source_url": source_url,
            }
        )
    if not result_rows:
        return None
    edition_name = championship
    if location:
        edition_name = f"{championship} - {location}"
    return {
        "edition_id": _edition_id(championship, event_date),
        "edition_name": edition_name,
        "event_name": event_name,
        "event_date": event_date,
        "source_url": source_url,
        "source_kind": "fencingworldwide_text",
        "classification": {key: classification[key] for key in ("weapon", "gender", "category", "team")},
        "event_code": classification["event_code"],
        "results": result_rows,
    }


def parse_pdf_bytes(pdf_bytes, source_url, default_event_name=None, default_date=None):
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    text = "\n".join(text_parts)
    event = parse_fencingworldwide_text_result_page(text, source_url)
    if event:
        return [event]
    return parse_text_sparse_events(text, source_url, default_event_name=default_event_name, default_date=default_date)


def parse_text_sparse_events(text, source_url, default_event_name=None, default_date=None):
    """Parse simple copied/PDF text rows where each line starts with rank-country-name."""
    event_name = default_event_name or "African Championships"
    classification = classify_event(event_name)
    result_rows = []
    for line in (text or "").splitlines():
        cleaned = _clean_text(line)
        if not cleaned or re.search(r"did not start|\bDNS\b|withdraw", cleaned, re.I):
            continue
        match = re.match(r"^T?(?P<rank>\d+)[.=]?\s+(?P<country>[A-Z]{3})\s+(?P<name>.+?)(?:\s+(?P<points>\d+(?:[,.]\d+)?))?$", cleaned)
        if not match:
            continue
        rank = int(match.group("rank"))
        result_rows.append(
            {
                "rank": rank,
                "name": normalize_name(match.group("name")),
                "country": normalize_country(match.group("country")),
                "medal": _medal_for_rank(rank),
                "points": _parse_points(match.group("points")),
                "fie_id": None,
                "source_url": source_url,
            }
        )
    if not result_rows or not classification["weapon"] or not classification["gender"]:
        return []
    event_date = normalize_date(default_date) or normalize_date(text)
    return [
        {
            "edition_id": _edition_id(event_name, event_date),
            "edition_name": _edition_name(event_name, event_date),
            "event_name": event_name,
            "event_date": event_date,
            "source_url": source_url,
            "source_kind": "text_sparse",
            "classification": {key: classification[key] for key in ("weapon", "gender", "category", "team")},
            "event_code": classification["event_code"],
            "results": result_rows,
        }
    ]


def build_no_public_data_stub(probe_results):
    return {
        "source_kind": "no_public_data_stub",
        "source_url": None,
        "edition_id": "african-conf:no-public-data",
        "edition_name": "African Fencing Championships - no durable public data",
        "event_name": None,
        "event_date": None,
        "results": [],
        "skipped_reason": "no durable public African championship result rows found",
        "probe_results": probe_results,
    }


def _make_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _fetch(session, url):
    response = session.get(url, timeout=25, allow_redirects=True)
    return {
        "url": url,
        "final_url": response.url,
        "status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "text": response.text if "text" in response.headers.get("content-type", "") or "html" in response.headers.get("content-type", "") else None,
        "content": response.content,
    }


def probe_sources(session=None):
    session = session or _make_session()
    probe_results = []
    for url in PROBE_URLS:
        try:
            fetched = _fetch(session, url)
            reason = "ok"
            if "fencingtimelive.com" in fetched["final_url"].lower():
                reason = "login-gated or live-only schedule; not used as durable source"
            elif fetched["status"] >= 400:
                reason = f"http_{fetched['status']}"
            probe_results.append(
                {
                    "url": url,
                    "final_url": fetched["final_url"],
                    "status": fetched["status"],
                    "content_type": fetched["content_type"],
                    "reason": reason,
                }
            )
        except Exception as exc:
            probe_results.append({"url": url, "status": None, "reason": str(exc)[:300]})
    return probe_results


def _candidate_result_urls(html, base_url):
    soup = BeautifulSoup(html or "", "html.parser")
    urls = []
    for link in soup.find_all("a", href=True):
        text = _clean_text(link.get_text(" ", strip=True)) or ""
        href = urljoin(base_url, link["href"])
        combined = f"{text} {href}"
        if re.search(r"afric|result|ranking|medaill|fencingworldwide|pdf", combined, re.I):
            urls.append(href)
    return list(dict.fromkeys(urls))


def discover_events(session=None):
    session = session or _make_session()
    probe_results = probe_sources(session)
    candidate_urls = list(KNOWN_PUBLIC_SOURCES)
    for result in probe_results:
        if result.get("status") and result["status"] < 400 and result.get("url"):
            try:
                fetched = _fetch(session, result["url"])
                if fetched.get("text"):
                    candidate_urls.extend(_candidate_result_urls(fetched["text"], fetched["final_url"]))
            except Exception:
                pass
    candidate_urls = list(dict.fromkeys(candidate_urls))

    events = []
    seen_urls = set()
    cursor = 0
    while cursor < len(candidate_urls) and cursor < 80:
        url = candidate_urls[cursor]
        cursor += 1
        if url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            fetched = _fetch(session, url)
            content_type = fetched["content_type"].lower()
            if fetched["status"] >= 400:
                continue
            if "pdf" in content_type or url.lower().endswith(".pdf"):
                events.extend(parse_pdf_bytes(fetched["content"], fetched["final_url"]))
            elif fetched.get("text"):
                for discovered_url in _candidate_result_urls(fetched["text"], fetched["final_url"]):
                    if discovered_url not in seen_urls and discovered_url not in candidate_urls:
                        candidate_urls.append(discovered_url)
                html_events = parse_html_result_events(fetched["text"], fetched["final_url"])
                events.extend(html_events)
                text_event = parse_fencingworldwide_text_result_page(
                    BeautifulSoup(fetched["text"], "html.parser").get_text("\n"), fetched["final_url"]
                )
                if text_event:
                    events.append(text_event)
            time.sleep(REQUEST_DELAY)
        except Exception as exc:
            probe_results.append({"url": url, "status": None, "reason": str(exc)[:300]})
    deduped = {}
    for event in events:
        if not event or not event.get("results"):
            continue
        key = (event.get("source_url"), event.get("event_code"), event.get("event_date"))
        deduped[key] = event
    return list(deduped.values()), probe_results


def _first_identity_row_id(row):
    ids = row.get("fs_fencer_row_ids") or []
    return str(ids[0]) if ids else None


def _query_single_or_none(query):
    rows = query.limit(2).execute().data or []
    return rows[0] if len(rows) == 1 else None


def match_fencer(fie_id=None, name=None, country=None):
    if not supabase:
        return None, None, "no_supabase_client"
    fie_id = _clean_text(fie_id)
    name = _clean_text(name)
    country = normalize_country(country)
    if fie_id:
        try:
            identity = _query_single_or_none(
                supabase.table("fs_fencer_identities").select("id,fs_fencer_row_ids").contains("fie_ids", [str(fie_id)])
            )
            if identity:
                fencer_id = _first_identity_row_id(identity)
                if fencer_id:
                    return fencer_id, "fie_id_identity", None
        except Exception as exc:
            print(f"  FIE identity lookup failed for {fie_id}: {exc}")
        try:
            rows = supabase.table("fs_fencers").select("id").eq("fie_id", str(fie_id)).limit(2).execute().data or []
            if rows:
                return rows[0]["id"], "fie_id", None
        except Exception as exc:
            print(f"  FIE fencer lookup failed for {fie_id}: {exc}")
    if name and country:
        try:
            identity = _query_single_or_none(
                supabase.table("fs_fencer_identities")
                .select("id,fs_fencer_row_ids")
                .ilike("canonical_name", name)
                .eq("country", country)
            )
            if identity:
                fencer_id = _first_identity_row_id(identity)
                if fencer_id:
                    return fencer_id, "canonical_identity_name_country", None
        except Exception as exc:
            print(f"  Identity name lookup failed for {name}/{country}: {exc}")
        try:
            row = _query_single_or_none(
                supabase.table("fs_fencers").select("id").ilike("name", name).eq("country", country)
            )
            if row:
                return row["id"], "name_country", None
        except Exception as exc:
            print(f"  Fencer name lookup failed for {name}/{country}: {exc}")
    return None, None, "unmatched_fencer"


def build_tournament_row(event):
    classification = event.get("classification") or classify_event(event.get("event_name"))
    source_id = f"{SOURCE}:{event.get('event_code') or classification.get('event_code')}:{event.get('event_date') or event.get('source_url')}"
    return {
        "source_id": source_id,
        "name": event.get("event_name") or event.get("edition_name") or "African Fencing Championships",
        "season": (event.get("event_date") or "")[:4] or None,
        "country": None,
        "location": None,
        "start_date": event.get("event_date"),
        "end_date": event.get("event_date"),
        "weapon": classification.get("weapon"),
        "gender": classification.get("gender"),
        "category": classification.get("category"),
        "type": "team" if classification.get("team") else "individual",
        "has_results": bool(event.get("results")),
        "metadata": {
            "source": SOURCE,
            "source_url": event.get("source_url"),
            "source_kind": event.get("source_kind"),
            "edition_id": event.get("edition_id"),
            "edition_name": event.get("edition_name"),
            "event_code": event.get("event_code"),
            "team": classification.get("team"),
        },
    }


def upsert_tournament(event):
    if not supabase:
        return None
    row = build_tournament_row(event)
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {row['source_id']}: {exc}")
        return None


def upsert_results(tournament_id, result_rows, team=False):
    db_rows = []
    unmatched = []
    skipped = 0
    for row in result_rows:
        rank = _rank_to_int(row.get("rank"))
        if rank is None:
            skipped += 1
            continue
        fencer_id = None
        match_tier = None
        reason = None
        if not team:
            fencer_id, match_tier, reason = match_fencer(row.get("fie_id"), row.get("name"), row.get("country"))
            if not fencer_id:
                skipped += 1
                unmatched_row = {
                    "name": row.get("name"),
                    "country": row.get("country"),
                    "fie_id": row.get("fie_id"),
                    "rank": rank,
                    "source_url": row.get("source_url"),
                    "reason": reason or "unmatched_fencer",
                }
                unmatched.append(unmatched_row)
                print(
                    "  Unmatched African result skipped: "
                    f"{unmatched_row['name']} {unmatched_row['country']} rank={rank} source={unmatched_row['source_url']}"
                )
                continue
        db_row = {
            "tournament_id": tournament_id,
            "name": row.get("name"),
            "nationality": row.get("country"),
            "country": row.get("country"),
            "rank": rank,
            "placement": rank,
            "medal": row.get("medal") or _medal_for_rank(rank),
            "fencer_id": fencer_id,
            "metadata": {
                "source": SOURCE,
                "source_url": row.get("source_url"),
                "country": row.get("country"),
                "fie_id": row.get("fie_id"),
                "points": row.get("points"),
                "team": team,
                "match_tier": match_tier,
            },
        }
        if row.get("fie_id"):
            db_row["fie_fencer_id"] = str(row["fie_id"])
        db_rows.append(db_row)
    if not db_rows or not supabase:
        return {"written": 0, "skipped": skipped, "unmatched": unmatched}

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for index in range(0, len(db_rows), 100):
        batch = db_rows[index : index + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    return {"written": written, "skipped": skipped + (len(db_rows) - written), "unmatched": unmatched}


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_african_conf").start()
    try:
        done_event_ids = set(get_state(SOURCE, "done_event_ids") or [])
        events, probe_results = discover_events()
        if not events:
            stub = build_no_public_data_stub(probe_results)
            set_state(SOURCE, "last_stub", stub)
            run_log.complete(written=0, failed=0, skipped=1, metadata={"probe_results": probe_results})
            print(stub["skipped_reason"])
            return

        total_written = 0
        total_failed = 0
        total_skipped = 0
        unmatched_rows = []
        for event in events:
            event_id = f"{event.get('source_url')}|{event.get('event_code')}|{event.get('event_date')}"
            if event_id in done_event_ids:
                total_skipped += 1
                continue
            tournament_id = upsert_tournament(event)
            if not tournament_id:
                total_failed += 1
                continue
            classification = event.get("classification") or classify_event(event.get("event_name"))
            summary = upsert_results(tournament_id, event.get("results") or [], team=classification.get("team"))
            total_written += summary["written"]
            total_skipped += summary["skipped"]
            unmatched_rows.extend(summary["unmatched"])
            done_event_ids.add(event_id)
            set_state(SOURCE, "done_event_ids", sorted(done_event_ids))
        set_state(SOURCE, "last_run", datetime.now(UTC).isoformat())
        set_state(SOURCE, "last_probe_results", probe_results)
        set_state(SOURCE, "last_unmatched_rows", unmatched_rows)
        run_log.complete(
            written=total_written,
            failed=total_failed,
            skipped=total_skipped,
            metadata={"unmatched_rows": len(unmatched_rows), "events": len(events)},
        )
        print(f"Done - written={total_written}, failed={total_failed}, skipped={total_skipped}, unmatched={len(unmatched_rows)}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

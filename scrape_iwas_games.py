"""
IWAS/World Para Fencing games and satellite results scraper.

Probe summary (verified with public pages on 2026-06-02):
  - World Para Fencing historic results are listed at:
      https://parafencing.org/results-and-rankings/historic-results/
    Recent rows may have no download link; older public rows link to Ophardt
    result pages or PDF result books.
  - Ophardt result pages use:
      https://iwas.ophardt.online/en/search/results/{result_id}
    and can expose wheelchair event result tables even when an upstream
    hasResults flag would be false.
  - Paralympic wheelchair fencing archives use:
      https://www.paralympic.org/{edition_slug}/results/wheelchair-fencing
    and the Paris 2024 official result book is a public PDF.
  - World Abilitysport past competitions list current/near-current Para
    Fencing events, but not every event has public result data yet.
"""
from __future__ import annotations

import io
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

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

SOURCE = "iwas_games"
WPF_HISTORIC_RESULTS_URL = "https://parafencing.org/results-and-rankings/historic-results/"
WORLD_ABILITYSPORT_PAST_URL = "https://worldabilitysport.org/competitions/past/"
PARALYMPIC_PARIS_2024_URL = (
    "https://www.paralympic.org/paris-2024-paralympic-games/results/wheelchair-fencing"
)
REQUEST_DELAY = 1.25

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
    "Cookie": "cookie_consent=2",
}

WEAPON_PATTERNS = [
    (re.compile(r"\bepee\b", re.I), "Epee"),
    (re.compile(r"\b(?:foil|fleuret)\b", re.I), "Foil"),
    (re.compile(r"\b(?:sabre|saber)\b", re.I), "Sabre"),
]

GENDER_PATTERNS = [
    (re.compile(r"\b(?:women|women's|female)\b", re.I), "Women"),
    (re.compile(r"\b(?:men|men's|male)\b", re.I), "Men"),
]

MEDAL_BY_RANK = {1: "Gold", 2: "Silver", 3: "Bronze"}
RANK_BY_MEDAL = {"GOLD": 1, "SILVER": 2, "BRONZE": 3}

MONTHS = {
    "JAN": "01",
    "FEB": "02",
    "MAR": "03",
    "APR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AUG": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DEC": "12",
}

COUNTRY_ALIASES = {
    "ARGENTINA": "ARG",
    "BRAZIL": "BRA",
    "CANADA": "CAN",
    "CHINA": "CHN",
    "PEOPLE'S REPUBLIC OF CHINA": "CHN",
    "PEOPLES REPUBLIC OF CHINA": "CHN",
    "FRANCE": "FRA",
    "GEORGIA": "GEO",
    "GERMANY": "GER",
    "GREAT BRITAIN": "GBR",
    "BRITAIN": "GBR",
    "HONG KONG": "HKG",
    "HONG KONG CHINA": "HKG",
    "HONG KONG, CHINA": "HKG",
    "HUNGARY": "HUN",
    "IRAQ": "IRQ",
    "ITALY": "ITA",
    "JAPAN": "JPN",
    "POLAND": "POL",
    "REPUBLIC OF KOREA": "KOR",
    "SOUTH KOREA": "KOR",
    "KOREA": "KOR",
    "SPAIN": "ESP",
    "THAILAND": "THA",
    "TURKIYE": "TUR",
    "TURKEY": "TUR",
    "UKRAINE": "UKR",
    "UNITED STATES": "USA",
    "UNITED STATES OF AMERICA": "USA",
    "VENEZUELA": "VEN",
}

TYPE_BY_SOURCE_KIND = {
    "satellite": "wheelchair_satellite",
    "world_championship": "wheelchair_championship",
    "world_cup": "wheelchair_world_cup",
    "regional_championship": "wheelchair_regional_championship",
    "paralympic": "paralympics",
}


class RateLimiter:
    def __init__(self, delay_seconds=REQUEST_DELAY, monotonic=None, sleep=None):
        self.delay_seconds = float(delay_seconds or 0)
        self._monotonic = monotonic or time.monotonic
        self._sleep = sleep or time.sleep
        self._last_request_at = None

    def wait(self):
        now = self._monotonic()
        if self._last_request_at is not None and self.delay_seconds > 0:
            remaining = self.delay_seconds - (now - self._last_request_at)
            if remaining > 0:
                remaining = round(remaining, 6)
                self._sleep(remaining)
                now = self._monotonic()
        self._last_request_at = now


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _ascii_fold(value):
    text = unicodedata.normalize("NFKD", _clean_text(value))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _key(value):
    return re.sub(r"[^a-z0-9]+", " ", _ascii_fold(value).lower()).strip()


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", _ascii_fold(value).lower()).strip("-")


def normalize_country(value):
    text = _clean_text(value)
    if not text:
        return None
    text = re.sub(r"\s+-\s+.*$", "", text)
    upper = _ascii_fold(text).upper().replace(".", "")
    upper = re.sub(r"\s+", " ", upper).strip()
    if re.fullmatch(r"[A-Z]{3}", upper):
        return upper
    parsed = COUNTRY_ALIASES.get(upper, COUNTRY_ALIASES.get(upper.replace(",", "")))
    if parsed:
        return parsed
    if "," in text:
        return normalize_country(text.rsplit(",", 1)[-1])
    return upper if len(upper) == 3 else None


def _parse_float(value):
    text = _clean_text(value).replace(",", ".")
    if not text or text in {"-", "—", "–"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_rank(value):
    text = _clean_text(value)
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def _medal_from_value(value, rank):
    text = _clean_text(value).upper()
    if "GOLD" in text or text == "G":
        return "Gold"
    if "SILVER" in text or text == "S":
        return "Silver"
    if "BRONZE" in text or text == "B":
        return "Bronze"
    return MEDAL_BY_RANK.get(rank)


def _parse_pdf_date(value):
    match = re.search(
        r"\b(?:MON|TUE|WED|THU|FRI|SAT|SUN)\s+(\d{1,2})\s+([A-Z]{3})\s+(\d{4})\b",
        _clean_text(value).upper(),
    )
    if not match:
        return None
    day, month, year = match.groups()
    month_number = MONTHS.get(month)
    if not month_number:
        return None
    return f"{year}-{month_number}-{int(day):02d}"


def parse_event_label(label):
    text = _clean_text(label.replace("’", "'"))
    key_text = _ascii_fold(text)
    weapon = next((weapon for pattern, weapon in WEAPON_PATTERNS if pattern.search(key_text)), None)
    gender = next((gender for pattern, gender in GENDER_PATTERNS if pattern.search(key_text)), None)
    team = bool(re.search(r"\bteam\b", key_text, re.I))

    age = None
    age_match = re.search(r"\b(senior|u23|u17|under\s*23|under\s*17)\b", key_text, re.I)
    if age_match:
        raw_age = age_match.group(1).lower().replace(" ", "")
        age = {"under23": "U23", "under17": "U17"}.get(raw_age, raw_age.upper() if raw_age.startswith("u") else raw_age.capitalize())
    else:
        age = "Senior"

    classification = None
    class_match = re.search(r"\b(?:category|cat\.?|class)\s*([ABC])\b", key_text, re.I)
    if class_match:
        classification = class_match.group(1).upper()
    else:
        tail_match = re.search(r"\b([ABC])\b\s*$", key_text, re.I)
        if tail_match:
            classification = tail_match.group(1).upper()

    category = age
    if classification:
        category = f"{age} {classification}".strip()

    return {
        "event_name": text,
        "weapon": weapon,
        "gender": gender,
        "classification": classification,
        "category": category,
        "team": team,
    }


def _source_kind(section, competition):
    text = f"{section} {competition}".lower()
    if "satellite" in text:
        return "satellite"
    if "world cup" in text:
        return "world_cup"
    if "regional" in text or "european" in text or "asian" in text or "americas" in text:
        return "regional_championship"
    if "paralympic" in text:
        return "paralympic"
    if "world championship" in text:
        return "world_championship"
    return "wheelchair_event"


def _source_format(source_url):
    if not source_url:
        return None
    lowered = source_url.lower()
    if "iwas.ophardt.online/en/search/results/" in lowered:
        return "ophardt_html"
    if lowered.endswith(".pdf"):
        return "pdf"
    return "html"


def parse_historic_results_page(html, base_url=WPF_HISTORIC_RESULTS_URL):
    soup = BeautifulSoup(html or "", "html.parser")
    sources = []
    for table in soup.find_all("table"):
        heading = table.find_previous(["h1", "h2", "h3", "h4"])
        section = _clean_text(heading.get_text(" ", strip=True)) if heading else "Historic Results"
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"], recursive=False)
            if len(cells) < 3:
                continue
            values = [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            if values[0].lower() == "year":
                continue
            year, location, competition = values[:3]
            if not re.search(r"\b(?:19|20)\d{2}\b", year):
                continue
            link = tr.find("a", href=True)
            source_url = urljoin(base_url, link["href"]) if link else None
            result_id_match = re.search(r"/results/(\d+)", source_url or "")
            status = "public_results" if source_url else "missing_public_data"
            source_kind = _source_kind(section, competition)
            sources.append(
                {
                    "year": year.replace("*", "").strip(),
                    "location": location,
                    "competition": competition,
                    "section": section,
                    "source_kind": source_kind,
                    "source_url": source_url,
                    "source_format": _source_format(source_url),
                    "iwas_result_id": result_id_match.group(1) if result_id_match else None,
                    "status": status,
                    "evidence": {
                        "source_page": base_url,
                        "section": section,
                        "row_text": " | ".join(values),
                        "reason": "public_download_link" if source_url else "historic_results_row_without_download",
                    },
                }
            )
    return sources


def should_import_result_source(source, fie_metadata=None):
    del fie_metadata
    return bool(source.get("source_url") or source.get("rows"))


def build_no_public_data_stub(source):
    source_id = (
        f"iwas-games:{_slug(source.get('year'))}:{_slug(source.get('location'))}:"
        f"{_slug(source.get('competition'))}:stub"
    )
    return {
        "source_id": source_id,
        "name": f"{source.get('year')} {source.get('location')} - {source.get('competition')}",
        "season": source.get("year"),
        "type": TYPE_BY_SOURCE_KIND.get(source.get("source_kind"), "wheelchair_event"),
        "weapon": None,
        "gender": None,
        "category": None,
        "country": None,
        "has_results": False,
        "metadata": {
            "source": SOURCE,
            "source_kind": source.get("source_kind"),
            "source_url": source.get("source_url"),
            "status": source.get("status", "missing_public_data"),
            "location": source.get("location"),
            "competition": source.get("competition"),
            "evidence": source.get("evidence") or {},
        },
    }


def _header_map(table):
    first_row = table.find("tr")
    headers = first_row.find_all(["th", "td"], recursive=False) if first_row else []
    mapping = {}
    for index, cell in enumerate(headers):
        text = _key(cell.get_text(" ", strip=True))
        if text in {"rank", "place", "ranking"}:
            mapping.setdefault("rank", index)
        elif "name" in text or "athlete" in text or "fencer" in text:
            mapping.setdefault("name", index)
        elif "nation" in text or "country" in text or text == "npc":
            mapping.setdefault("country", index)
        elif text in {"class", "classification", "category"}:
            mapping.setdefault("classification", index)
        elif "point" in text or "score" in text:
            mapping.setdefault("points", index)
        elif "medal" in text:
            mapping.setdefault("medal", index)
        elif "date" in text:
            mapping.setdefault("date", index)
    return mapping


def _data_rows(table):
    tbody = table.find("tbody")
    rows = tbody.find_all("tr", recursive=False) if tbody else table.find_all("tr", recursive=False)
    return [row for row in rows if row.find_all("td", recursive=False)]


def _cell_text(cells, index):
    if index is None or index >= len(cells):
        return ""
    return _clean_text(cells[index].get_text(" ", strip=True))


def _country_from_cell(cell):
    if cell is None:
        return None
    abbr = cell.find("abbr")
    if abbr:
        parsed = normalize_country(abbr.get_text(" ", strip=True))
        if parsed:
            return parsed
    title = _clean_text(cell.get("title"))
    match = re.search(r"Nationality:\s*([A-Z]{2,3})", title)
    if match:
        return normalize_country(match.group(1))
    return normalize_country(cell.get_text(" ", strip=True))


def _fie_id_from_name_cell(cell):
    if cell is None:
        return None
    link = cell.find("a", href=True)
    if not link:
        return None
    numbers = re.findall(r"\d+", link["href"])
    return numbers[-1] if numbers else None


def parse_html_results_document(html, source_url, competition_name=None, event_date=None, source_kind="iwas"):
    soup = BeautifulSoup(html or "", "html.parser")
    heading = soup.find("h1")
    competition_name = competition_name or (_clean_text(heading.get_text(" ", strip=True)) if heading else None)
    events = []

    for event_heading in soup.find_all(["h2", "h3", "h4", "h5"]):
        label = _clean_text(event_heading.get_text(" ", strip=True))
        classification = parse_event_label(label)
        if not classification["weapon"] or not classification["gender"]:
            continue
        table = event_heading.find_next("table")
        if not table:
            continue
        columns = _header_map(table)
        rank_col = columns.get("rank", 0)
        name_col = columns.get("name", 3)
        country_col = columns.get("country", 7)
        class_col = columns.get("classification", 6)
        points_col = columns.get("points", 8)
        medal_col = columns.get("medal")
        date_col = columns.get("date")

        rows = []
        for tr in _data_rows(table):
            cells = tr.find_all("td", recursive=False)
            rank = _parse_rank(_cell_text(cells, rank_col))
            if rank is None:
                continue
            name_cell = cells[name_col] if name_col < len(cells) else None
            fencer = _cell_text(cells, name_col)
            if not fencer:
                continue
            row_class = _cell_text(cells, class_col).upper() if class_col < len(cells) else ""
            if row_class not in {"A", "B", "C"}:
                row_class = classification["classification"]
            country_cell = cells[country_col] if country_col < len(cells) else None
            medal = _medal_from_value(_cell_text(cells, medal_col), rank) if medal_col is not None else MEDAL_BY_RANK.get(rank)
            rows.append(
                {
                    "rank": rank,
                    "fencer": fencer,
                    "country": _country_from_cell(country_cell),
                    "medal": medal,
                    "points": _parse_float(_cell_text(cells, points_col)),
                    "classification": row_class,
                    "fie_id": _fie_id_from_name_cell(name_cell),
                    "source_url": source_url,
                    "date": _clean_text(_cell_text(cells, date_col)) or event_date,
                }
            )

        if rows:
            events.append(
                {
                    **classification,
                    "competition_name": competition_name,
                    "source_kind": source_kind,
                    "source_url": source_url,
                    "date": event_date,
                    "rows": rows,
                }
            )
    return events


def parse_pdf_results_text(text, source_url, competition_name=None):
    events = []
    current_event = None
    current_label = None
    current_date = None

    for raw_line in (text or "").splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue
        parts = line.split()
        medal_index = next((idx for idx, part in enumerate(parts) if part.upper() in RANK_BY_MEDAL), None)
        if medal_index is None:
            continue

        prefix = " ".join(parts[:medal_index])
        medal = parts[medal_index].upper()
        suffix = parts[medal_index + 1 :]
        if prefix:
            date = _parse_pdf_date(prefix)
            date_match = re.search(
                r"\b(?:MON|TUE|WED|THU|FRI|SAT|SUN)\s+\d{1,2}\s+[A-Z]{3}\s+\d{4}\b",
                prefix,
                re.I,
            )
            label = _clean_text(prefix[: date_match.start()]) if date_match else prefix
            current_label = label
            current_date = date
            classification = parse_event_label(label)
            current_event = {
                **classification,
                "competition_name": competition_name,
                "source_kind": "pdf",
                "source_url": source_url,
                "date": current_date,
                "rows": [],
            }
            events.append(current_event)

        if not current_event or len(suffix) < 2:
            continue
        country = normalize_country(suffix[-1])
        name_parts = suffix[:-1]
        row_class = None
        if len(name_parts) > 1 and name_parts[-1].upper() in {"A", "B", "C"}:
            row_class = name_parts.pop(-1).upper()
        fencer = " ".join(name_parts)
        if not fencer or not country:
            continue
        rank = RANK_BY_MEDAL[medal]
        current_event["rows"].append(
            {
                "rank": rank,
                "fencer": fencer,
                "country": country,
                "medal": medal.capitalize(),
                "points": None,
                "classification": row_class or current_event.get("classification"),
                "fie_id": None,
                "source_url": source_url,
                "date": current_date,
            }
        )

    return [event for event in events if event["rows"]]


def parse_pdf_results_bytes(pdf_bytes, source_url, competition_name=None):
    import pdfplumber

    texts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                texts.append(page_text)
    return parse_pdf_results_text("\n".join(texts), source_url, competition_name=competition_name)


def parse_results_document(content, source_url, content_type=None, competition_name=None):
    content_type = (content_type or "").lower()
    if isinstance(content, bytes):
        if "pdf" in content_type or source_url.lower().endswith(".pdf"):
            return parse_pdf_results_bytes(content, source_url, competition_name=competition_name)
        content = content.decode("utf-8", errors="replace")
    if "pdf" in content_type or source_url.lower().endswith(".pdf"):
        return parse_pdf_results_text(str(content), source_url, competition_name=competition_name)
    return parse_html_results_document(str(content), source_url, competition_name=competition_name)


def _canonical_name(value):
    return _key(value)


def build_fencer_index(fencers):
    by_fie_id = {}
    by_identity = {}
    for row in fencers or []:
        row_id = row.get("id")
        if not row_id:
            continue
        fie_id = _clean_text(row.get("fie_id"))
        if fie_id:
            by_fie_id.setdefault(fie_id, row)
        name_key = _canonical_name(row.get("name"))
        country = normalize_country(row.get("country"))
        if name_key and country:
            by_identity.setdefault((name_key, country), []).append(row)
    return {"by_fie_id": by_fie_id, "by_identity": by_identity}


def match_fencer(row, fencer_index):
    fie_id = _clean_text(row.get("fie_id"))
    if fie_id:
        match = fencer_index.get("by_fie_id", {}).get(fie_id)
        if match:
            return match.get("id"), "fie_id"
    name_key = _canonical_name(row.get("fencer") or row.get("name"))
    country = normalize_country(row.get("country"))
    if name_key and country:
        candidates = fencer_index.get("by_identity", {}).get((name_key, country), [])
        if len(candidates) == 1:
            return candidates[0].get("id"), "name_country"
    return None, None


def load_fencer_index(client):
    rows = []
    start = 0
    page_size = 1000
    while True:
        data = (
            client.table("fs_fencers")
            .select("id,fie_id,name,country")
            .range(start, start + page_size - 1)
            .execute()
            .data
        )
        rows.extend(data or [])
        if not data or len(data) < page_size:
            break
        start += page_size
    return build_fencer_index(rows)


def _unmatched_entry(row, event, reason="no_fencer_match"):
    return {
        "name": row.get("fencer") or row.get("name"),
        "country": normalize_country(row.get("country")),
        "fie_id": _clean_text(row.get("fie_id")) or None,
        "source_url": row.get("source_url") or event.get("source_url"),
        "reason": reason,
    }


def prepare_result_rows(tournament_id, event, fencer_index, unmatched_log=None):
    unmatched_log = unmatched_log if unmatched_log is not None else []
    db_rows = []
    skipped = 0
    for row in event.get("rows") or []:
        if row.get("rank") is None or not row.get("fencer"):
            continue
        fencer_id, match_method = match_fencer(row, fencer_index)
        if not fencer_id:
            unmatched_log.append(_unmatched_entry(row, event))
            skipped += 1
            continue
        nationality = normalize_country(row.get("country"))
        db_row = {
            "tournament_id": tournament_id,
            "name": row["fencer"],
            "nationality": nationality,
            "rank": row["rank"],
            "medal": row.get("medal"),
            "points": row.get("points"),
            "fencer_id": fencer_id,
            "metadata": {
                "source": SOURCE,
                "source_kind": event.get("source_kind"),
                "competition_name": event.get("competition_name"),
                "event_name": event.get("event_name"),
                "weapon": event.get("weapon"),
                "gender": event.get("gender"),
                "classification": row.get("classification") or event.get("classification"),
                "category": event.get("category"),
                "source_url": row.get("source_url") or event.get("source_url"),
                "date": row.get("date") or event.get("date"),
                "match_method": match_method,
            },
        }
        fie_id = _clean_text(row.get("fie_id"))
        if fie_id:
            db_row["fie_fencer_id"] = fie_id
            db_row["metadata"]["fie_id"] = fie_id
        db_rows.append(db_row)

    if skipped:
        for db_row in db_rows:
            db_row["metadata"]["unmatched_rows_skipped"] = skipped
    return db_rows


def upsert_event_results(client, tournament_id, event, fencer_index):
    unmatched = []
    db_rows = prepare_result_rows(tournament_id, event, fencer_index, unmatched)
    if not db_rows:
        return 0, len(unmatched), unmatched

    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i : i + 100]
        client.table("fs_results").upsert(batch, on_conflict="tournament_id,name").execute()
        written += len(batch)
    return written, len(unmatched), unmatched


def build_tournament_row(source, event=None):
    if event is None:
        return build_no_public_data_stub(source)

    event_slug = _slug(event.get("event_name"))
    source_piece = source.get("iwas_result_id") or _slug(source.get("location"))
    source_id = f"iwas-games:{source.get('year')}:{source_piece}:{event_slug}"
    return {
        "source_id": source_id,
        "name": f"{source.get('competition')} - {event.get('event_name')}",
        "season": source.get("year"),
        "type": TYPE_BY_SOURCE_KIND.get(source.get("source_kind"), "wheelchair_event"),
        "weapon": event.get("weapon"),
        "gender": event.get("gender"),
        "category": event.get("category"),
        "country": normalize_country(source.get("location")),
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "source_kind": source.get("source_kind"),
            "source_url": event.get("source_url") or source.get("source_url"),
            "source_format": source.get("source_format"),
            "iwas_result_id": source.get("iwas_result_id"),
            "location": source.get("location"),
            "competition": source.get("competition"),
            "event_name": event.get("event_name"),
            "classification": event.get("classification"),
            "date": event.get("date"),
            "evidence": source.get("evidence") or {},
        },
    }


def upsert_tournament(client, row):
    result = client.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
    return result.data[0]["id"] if result.data else None


def fetch_url(url, session=None, rate_limiter=None):
    session = session or requests.Session()
    if rate_limiter:
        rate_limiter.wait()
    response = session.get(url, headers=HEADERS, timeout=30)
    if response.status_code == 404:
        return None, None
    response.raise_for_status()
    return response.content, response.headers.get("content-type", "")


def discover_result_sources(session=None, rate_limiter=None):
    content, content_type = fetch_url(WPF_HISTORIC_RESULTS_URL, session=session, rate_limiter=rate_limiter)
    if not content:
        return []
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
    return parse_historic_results_page(text, base_url=WPF_HISTORIC_RESULTS_URL)


def fetch_source_events(source, session=None, rate_limiter=None):
    if not should_import_result_source(source):
        return []
    content, content_type = fetch_url(source["source_url"], session=session, rate_limiter=rate_limiter)
    if not content:
        return []
    return parse_results_document(
        content,
        source["source_url"],
        content_type=content_type,
        competition_name=source.get("competition"),
    )


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_iwas_games").start()
    try:
        print(f"IWAS games scraper starting - {datetime.now(timezone.utc).isoformat()}")
        session = requests.Session()
        limiter = RateLimiter(REQUEST_DELAY)
        done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])
        fencer_index = load_fencer_index(supabase)
        sources = discover_result_sources(session=session, rate_limiter=limiter)
        print(f"  Result sources discovered: {len(sources)}")

        written = failed = skipped = 0
        unmatched_all = []
        for source in sources:
            source_stub = build_no_public_data_stub(source)
            source_key = source_stub["source_id"].replace(":stub", "")
            if source_key in done_source_ids:
                skipped += 1
                continue

            if not should_import_result_source(source):
                upsert_tournament(supabase, source_stub)
                done_source_ids.add(source_key)
                skipped += 1
                continue

            try:
                events = fetch_source_events(source, session=session, rate_limiter=limiter)
            except Exception as exc:
                print(f"  Fetch/parse failed for {source.get('source_url')}: {exc}")
                failed += 1
                continue

            if not events:
                stub = build_no_public_data_stub({**source, "status": "missing_public_data"})
                stub["metadata"]["evidence"]["reason"] = "public_link_without_parseable_rows"
                upsert_tournament(supabase, stub)
                skipped += 1
                continue

            source_written = 0
            for event in events:
                if not event.get("weapon") or not event.get("gender"):
                    print(f"  Skipping unclassifiable event: {event.get('event_name')}")
                    skipped += 1
                    continue
                tournament_id = upsert_tournament(supabase, build_tournament_row(source, event))
                if not tournament_id:
                    failed += 1
                    continue
                count, unmatched_count, unmatched = upsert_event_results(
                    supabase,
                    tournament_id,
                    event,
                    fencer_index,
                )
                unmatched_all.extend(unmatched)
                skipped += unmatched_count
                source_written += count
                written += count
            if source_written:
                done_source_ids.add(source_key)
                set_state(SOURCE, "done_source_ids", sorted(done_source_ids))
            time.sleep(REQUEST_DELAY)

        set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
        if unmatched_all:
            print(f"  Unmatched fencer rows skipped: {len(unmatched_all)}")
            for item in unmatched_all[:25]:
                print(
                    "    unmatched "
                    f"{item.get('name')} {item.get('country')} "
                    f"fie_id={item.get('fie_id')} source={item.get('source_url')}"
                )
        run_log.complete(
            written=written,
            failed=failed,
            skipped=skipped,
            metadata={"unmatched_fencers": unmatched_all[:100]},
        )
        print(f"Done - written={written}, failed={failed}, skipped={skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

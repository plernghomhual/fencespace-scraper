"""
scrape_british_youth.py - British Youth Championships result scraper.

Public source notes from the 2026-06-02 probe:
- British Fencing's 2024 BYC report links to public Fencing Time Live results.
- The 2026 BYC Fencing Time Live link redirects to login; it is documented as
  a skipped non-public source, not scraped through account-only pages.
- Older BYC Engarde archives and British Fencing magazine PDFs expose public
  result rows with age group and region/club fields.
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


SOURCE = "british_youth"
COUNTRY = "GBR"
REQUEST_DELAY = float(os.environ.get("BRITISH_YOUTH_REQUEST_DELAY", "1.0"))
BATCH_SIZE = 100

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}

FTL_SCHEDULE_URLS = [
    "https://www.fencingtimelive.com/tournaments/eventSchedule/8EE15CF32DD94520BA98F08DAC10DDC7",
]

ENGARDE_INDEX_URLS = [
    "https://engarde-service.com/files/britishfencing/byc19/",
    "https://engarde-service.com/files/britishfencing/byc18/",
    "https://engarde-service.com/files/britishfencing/byc17/",
]

PDF_SOURCE_URLS = [
    "https://www.britishfencing.com/uploads/files/the_sword_magazine_-_july_2014.pdf",
]

BLOCKED_SOURCE_STUBS = [
    {
        "url": "https://fencingtimelive.com/tournaments/eventSchedule/D1A408A165A941658BDB6AADF78FD367",
        "status": "skipped",
        "reason": "login_required",
        "note": "British Fencing 2026 BYC page says Fencing Time Live requires login.",
    }
]

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

REGION_ALIASES = {
    "EAST MIDLANDS": "East Midlands",
    "EASTERN": "Eastern",
    "LONDON": "London",
    "N IRELAND": "Northern Ireland",
    "N. IRELAND": "Northern Ireland",
    "NORTH EAST": "North East",
    "NORTH WEST": "North West",
    "NORTHERN IRELAND": "Northern Ireland",
    "SCOTLAND CENTRAL": "Scotland Central",
    "SCOTLAND EAST": "Scotland East",
    "SCOTLAND WEST": "Scotland West",
    "SOUTH EAST": "South East",
    "SOUTH WEST": "South West",
    "SOUTHERN": "Southern",
    "WALES": "Wales",
    "WEST MIDLANDS": "West Midlands",
    "YORKSHIRE": "Yorkshire",
    "YORKSHIRE & NORTH EAST": "Yorkshire & North East",
}


def clean_text(value) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def ascii_key(value) -> str:
    text = clean_text(value) or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def title_if_plain(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if text.isupper() or text.islower():
        return text.title()
    return text


def normalize_weapon(value) -> str | None:
    key = ascii_key(value).lower()
    if re.search(r"\bepee\b", key):
        return "Epee"
    if re.search(r"\bfoil\b", key):
        return "Foil"
    if re.search(r"\bsabre\b|\bsaber\b", key):
        return "Sabre"
    return None


def normalize_gender(value) -> str | None:
    key = ascii_key(value).lower()
    if re.search(r"\bwomen\b|\bwoman\b|\bgirls?\b|\bfemale\b", key):
        return "Women"
    if re.search(r"\bmen\b|\bman\b|\bboys?\b|\bmixed\b|\bmale\b", key):
        return "Men"
    return None


def normalize_age_group(value) -> str | None:
    key = ascii_key(value).upper()
    match = re.search(r"\bU\s*-?\s*(1[2468])\b|\bUNDER\s*-?\s*(1[2468])\b", key)
    if not match:
        return None
    return f"U{match.group(1) or match.group(2)}"


def normalize_region(value) -> str | None:
    text = clean_text(value)
    if not text or text.lower() in {"unknown", "unattached", "none"}:
        return None
    key = ascii_key(text).upper()
    key = re.sub(r"\bREGION\b", "", key)
    key = re.sub(r"[^A-Z& ]+", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    if not key:
        return None
    return REGION_ALIASES.get(key, title_if_plain(key))


def normalize_club(value) -> str | None:
    text = clean_text(value)
    if not text or text.lower() in {"unknown", "unattached", "none", "n/a"}:
        return None
    return title_if_plain(text)


def parse_rank(value) -> int | None:
    match = re.match(r"\s*0*(\d+)", str(value or ""))
    return int(match.group(1)) if match else None


def parse_points(value) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def medal_for_rank(rank: int | None) -> str | None:
    if rank is None:
        return None
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def parse_date_from_text(value) -> str | None:
    text = clean_text(value) or ""
    match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),\s*((?:19|20)\d{2})\b",
        text,
        re.I,
    )
    if not match:
        return None
    month = MONTHS[match.group(1).lower()]
    return f"{int(match.group(3)):04d}-{month:02d}-{int(match.group(2)):02d}"


def season_from_value(*values) -> str | None:
    for value in values:
        text = clean_text(value) or ""
        if re.fullmatch(r"(?:19|20)\d{2}", text):
            return text
        match = re.search(r"\b((?:19|20)\d{2})\b", text)
        if match:
            return match.group(1)
    return None


def classify_event_name(event_name: str) -> dict:
    return {
        "event_name": clean_text(event_name),
        "weapon": normalize_weapon(event_name),
        "gender": normalize_gender(event_name),
        "age_group": normalize_age_group(event_name),
    }


def classify_source_status(html: str | None, url: str, status_code: int | None = 200, final_url: str | None = None) -> dict:
    text = ascii_key(html or "").lower()
    target = final_url or url
    if status_code in {401, 403}:
        return {"url": url, "status": "skipped", "reason": "non_public"}
    if status_code == 404:
        return {"url": url, "status": "skipped", "reason": "not_found"}
    login_required = (
        "/account/login" in target.lower()
        or "need to be logged in" in text
        or "to see tournament information" in text and "logged in" in text
    )
    if login_required:
        return {"url": url, "status": "skipped", "reason": "login_required"}
    return {"url": url, "status": "available", "reason": None}


def _event_slug(event: dict) -> str:
    parts = [event.get("age_group"), event.get("gender"), event.get("weapon")]
    slug = "-".join(str(part or "").lower() for part in parts if part)
    slug = slug.replace("é", "e")
    return re.sub(r"[^a-z0-9]+", "-", slug).strip("-")


def _table_headers(table) -> list[str]:
    first = table.find("tr")
    if not first:
        return []
    return [ascii_key(cell.get_text(" ", strip=True)).lower() for cell in first.find_all(["th", "td"])]


def _header_index(headers: list[str], *needles: str) -> int | None:
    for idx, header in enumerate(headers):
        if any(needle in header for needle in needles):
            return idx
    return None


def _name_from_cell(cell) -> str | None:
    link = cell.find("a")
    if link:
        return clean_text(link.get_text(" ", strip=True))
    copy = BeautifulSoup(str(cell), "html.parser")
    for hidden in copy.select(".sr-only, [aria-hidden='true'], script, style"):
        hidden.decompose()
    return clean_text(copy.get_text(" ", strip=True))


def _extract_event_heading(soup: BeautifulSoup) -> str | None:
    for node in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = clean_text(node.get_text(" ", strip=True))
        if text and normalize_age_group(text) and normalize_weapon(text) and normalize_gender(text):
            return text
    if soup.title:
        title = clean_text(soup.title.get_text(" ", strip=True))
        if title:
            for part in reversed(re.split(r"\s+-\s+", title)):
                if normalize_age_group(part) and normalize_weapon(part) and normalize_gender(part):
                    return part
    return None


def _event_date_for_table(table, soup) -> str | None:
    node = table
    while node:
        node = node.find_previous(["h1", "h2", "h3", "h4", "h5", "p"])
        if not node:
            break
        date = parse_date_from_text(node.get_text(" ", strip=True))
        if date:
            return date
    return parse_date_from_text(soup.get_text(" ", strip=True))


def parse_ftl_schedule(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()
    for table in soup.find_all("table"):
        table_date = _event_date_for_table(table, soup)
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            link = tr.find("a", href=True)
            if len(cells) < 2 or not link:
                continue
            event_name = clean_text(link.get_text(" ", strip=True))
            classification = classify_event_name(event_name or "")
            if not classification["weapon"] or not classification["gender"] or not classification["age_group"]:
                continue
            status = clean_text(cells[-1].get_text(" ", strip=True))
            event_url = urljoin(source_url, link["href"])
            if event_url in seen:
                continue
            seen.add(event_url)
            events.append(
                {
                    "event_name": event_name,
                    "weapon": classification["weapon"],
                    "gender": classification["gender"],
                    "age_group": classification["age_group"],
                    "date": table_date,
                    "source_url": event_url,
                    "status": status,
                }
            )
    return events


def parse_ftl_results_html(html: str, source_url: str, fallback_event: dict | None = None) -> dict | None:
    if classify_source_status(html, source_url)["status"] != "available":
        return None
    soup = BeautifulSoup(html, "html.parser")
    event_name = _extract_event_heading(soup) or (fallback_event or {}).get("event_name")
    classification = classify_event_name(event_name or "")
    if not classification["weapon"] or not classification["gender"] or not classification["age_group"]:
        return None

    result_table = None
    header_map = None
    for table in soup.find_all("table"):
        headers = _table_headers(table)
        rank_idx = _header_index(headers, "place", "rank", "position", "pos")
        name_idx = _header_index(headers, "name", "fencer")
        if rank_idx is not None and name_idx is not None:
            result_table = table
            header_map = {
                "rank": rank_idx,
                "name": name_idx,
                "club": _header_index(headers, "club"),
                "region": _header_index(headers, "region", "division"),
                "points": _header_index(headers, "points", "pts"),
            }
            break
    if result_table is None or header_map is None:
        return None

    rank_col = header_map["rank"] or 0
    name_col = header_map["name"] or 0
    results = []
    for tr in result_table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) <= max(rank_col, name_col):
            continue
        rank = parse_rank(cells[rank_col].get_text(" ", strip=True))
        name = _name_from_cell(cells[name_col])
        if rank is None or not name:
            continue
        club = None
        region = None
        points = None
        if header_map["club"] is not None and len(cells) > header_map["club"]:
            club = normalize_club(cells[header_map["club"]].get_text(" ", strip=True))
        if header_map["region"] is not None and len(cells) > header_map["region"]:
            region = normalize_region(cells[header_map["region"]].get_text(" ", strip=True))
        if header_map["points"] is not None and len(cells) > header_map["points"]:
            points = parse_points(cells[header_map["points"]].get_text(" ", strip=True))
        results.append(
            {
                "rank": rank,
                "name": name,
                "club": club,
                "region": region,
                "points": points,
                "medal": medal_for_rank(rank),
            }
        )

    if not results:
        return None
    date = parse_date_from_text(soup.get_text(" ", strip=True)) or (fallback_event or {}).get("date")
    season = season_from_value(date, soup.title.get_text(" ", strip=True) if soup.title else None, event_name)
    return {
        "event_name": event_name,
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "age_group": classification["age_group"],
        "season": season,
        "date": date,
        "source_url": source_url,
        "source_kind": "ftl_html",
        "results": results,
    }


def _is_weapon_section(line: str) -> str | None:
    normalized = ascii_key(line).upper().strip()
    if normalized in {"EPEE", "FOIL", "SABRE", "SABER"}:
        return normalize_weapon(normalized)
    return None


def _parse_pdf_event_heading(line: str, current_weapon: str | None) -> dict | None:
    pattern = re.compile(
        r"^(?P<gender>Boys|Girls|Men(?:'s)?|Women(?:'s)?|Mixed(?:/Men(?:'s)?)?)\s+"
        r"(?P<age>U\s*-?\s*1[2468])"
        r"(?:\s+(?P<weapon>Épée|Epee|Foil|Sabre|Saber))?"
        r"(?:\s*\(\d+\))?\s*$",
        re.I,
    )
    match = pattern.match(clean_text(line) or "")
    if not match:
        return None
    weapon = normalize_weapon(match.group("weapon")) or current_weapon
    gender = normalize_gender(match.group("gender"))
    age_group = normalize_age_group(match.group("age"))
    if not weapon or not gender or not age_group:
        return None
    event_name = f"{match.group('gender')} {age_group} {weapon}"
    return {
        "event_name": event_name,
        "weapon": weapon,
        "gender": gender,
        "age_group": age_group,
    }


def _parse_pdf_result_line(line: str) -> dict | None:
    match = re.match(r"^\s*(?P<rank>\d+)\s*[.=]?\s+(?P<body>.+?)\s*$", line)
    if not match:
        return None
    rank = parse_rank(match.group("rank"))
    body = clean_text(match.group("body")) or ""
    region = None
    region_match = re.search(r"\(([^()]+)\)\s*$", body)
    if region_match:
        region = normalize_region(region_match.group(1))
        body = clean_text(body[: region_match.start()]) or ""
    if not body:
        return None
    return {
        "rank": rank,
        "name": body,
        "club": None,
        "region": region,
        "points": None,
        "medal": medal_for_rank(rank),
    }


def parse_pdf_text(text: str, source_url: str, season: str | None = None, date: str | None = None) -> list[dict]:
    parsed_season = season or season_from_value(text, source_url)
    events = []
    current_weapon = None
    current_event = None

    for raw_line in str(text or "").splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        weapon_section = _is_weapon_section(line)
        if weapon_section:
            current_weapon = weapon_section
            continue

        event = _parse_pdf_event_heading(line, current_weapon)
        if event:
            if current_event and current_event["results"]:
                events.append(current_event)
            current_event = {
                **event,
                "season": parsed_season,
                "date": date,
                "source_url": source_url,
                "source_kind": "pdf_text",
                "results": [],
            }
            continue

        if not current_event:
            continue
        row = _parse_pdf_result_line(line)
        if row:
            current_event["results"].append(row)

    if current_event and current_event["results"]:
        events.append(current_event)
    return events


def parse_engarde_index(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for link in soup.find_all("a", href=True):
        event_name = clean_text(link.get_text(" ", strip=True))
        classification = classify_event_name(event_name or "")
        if classification["weapon"] and classification["gender"] and classification["age_group"]:
            events.append(
                {
                    "event_name": event_name,
                    "weapon": classification["weapon"],
                    "gender": classification["gender"],
                    "age_group": classification["age_group"],
                    "source_url": urljoin(source_url, link["href"]),
                }
            )
    return events


def parse_engarde_results_html(html: str, source_url: str, fallback_event: dict | None = None) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_event_heading(soup) or (fallback_event or {}).get("event_name")
    classification = classify_event_name(title or "")
    if not classification["weapon"] or not classification["gender"] or not classification["age_group"]:
        return None

    for table in soup.find_all("table"):
        headers = _table_headers(table)
        rank_idx = _header_index(headers, "rank", "rang", "place")
        last_idx = _header_index(headers, "surname", "nom", "name")
        first_idx = _header_index(headers, "first", "prenom", "prénom")
        club_idx = _header_index(headers, "club", "organisation", "organization")
        region_idx = _header_index(headers, "region", "country", "pays")
        if rank_idx is None or last_idx is None:
            continue
        rows = []
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(rank_idx, last_idx):
                continue
            rank = parse_rank(cells[rank_idx].get_text(" ", strip=True))
            last_name = clean_text(cells[last_idx].get_text(" ", strip=True))
            first_name = clean_text(cells[first_idx].get_text(" ", strip=True)) if first_idx is not None and len(cells) > first_idx else None
            name = clean_text(" ".join(part for part in [last_name, first_name] if part))
            if rank is None or not name:
                continue
            club = normalize_club(cells[club_idx].get_text(" ", strip=True)) if club_idx is not None and len(cells) > club_idx else None
            region = normalize_region(cells[region_idx].get_text(" ", strip=True)) if region_idx is not None and len(cells) > region_idx else None
            rows.append({"rank": rank, "name": name, "club": club, "region": region, "points": None, "medal": medal_for_rank(rank)})
        if rows:
            season = season_from_value(source_url, soup.get_text(" ", strip=True))
            return {
                "event_name": title,
                "weapon": classification["weapon"],
                "gender": classification["gender"],
                "age_group": classification["age_group"],
                "season": season,
                "date": None,
                "source_url": source_url,
                "source_kind": "engarde_html",
                "results": rows,
            }
    return None


def extract_pdf_text(content: bytes) -> str:
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "British Youth" in text or "BYC" in text:
                pages.append(text)
    return "\n".join(pages)


def fetch_url(session: requests.Session, url: str) -> requests.Response | None:
    try:
        response = session.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        status = classify_source_status(response.text, url, response.status_code, response.url)
        if status["status"] != "available":
            print(f"  Skipping {url}: {status['reason']}")
            return None
        if response.status_code == 200:
            return response
        print(f"  HTTP {response.status_code}: {url}")
        return None
    except requests.RequestException as exc:
        print(f"  Fetch failed {url}: {exc}")
        return None


def _match_fencer(name: str | None, country: str = COUNTRY) -> str | None:
    if not supabase or not name:
        return None
    try:
        rows = (
            supabase.table("fs_fencers")
            .select("id")
            .ilike("name", name)
            .eq("country", country)
            .limit(2)
            .execute()
            .data
        )
        return rows[0]["id"] if len(rows) == 1 else None
    except Exception:
        return None


def upsert_tournament(event: dict) -> str | None:
    if not supabase:
        return None
    season = event.get("season") or season_from_value(event.get("date"), event.get("source_url"), event.get("event_name"))
    source_id = f"{SOURCE}:{season or 'unknown'}:{_event_slug(event)}"
    row = {
        "source_id": source_id,
        "name": f"British Youth Championships {season or ''} - {event['event_name']}".strip(),
        "season": season,
        "type": "british_youth_championships",
        "weapon": event.get("weapon"),
        "gender": event.get("gender"),
        "category": event.get("age_group"),
        "country": COUNTRY,
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "source_url": event.get("source_url"),
            "source_kind": event.get("source_kind"),
            "event_name": event.get("event_name"),
            "age_group": event.get("age_group"),
            "date": event.get("date"),
            "minor_data_policy": "competition_results_only",
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def upsert_results(tournament_id: str, result_rows: list[dict]) -> int:
    if not supabase:
        return 0
    db_rows = []
    for row in result_rows:
        rank = row.get("rank")
        name = clean_text(row.get("name"))
        if rank is None or not name:
            continue
        fencer_id = _match_fencer(name)
        match_status = "matched" if fencer_id else "unmatched"
        if not fencer_id:
            print(f"Unmatched British youth fencer: {name}")
        db_rows.append(
            {
                "tournament_id": tournament_id,
                "name": name,
                "nationality": COUNTRY,
                "rank": rank,
                "medal": row.get("medal"),
                "fencer_id": fencer_id,
                "metadata": {
                    "source": SOURCE,
                    "club": row.get("club"),
                    "region": row.get("region"),
                    "points": row.get("points"),
                    "match_status": match_status,
                    "minor_data_policy": "competition_results_only",
                },
            }
        )
    if not db_rows:
        return 0

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for idx in range(0, len(db_rows), BATCH_SIZE):
        batch = db_rows[idx : idx + BATCH_SIZE]
        try:
            supabase.table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert failed: {exc}")
    return written if written == len(db_rows) else 0


def discover_events(session: requests.Session) -> tuple[list[dict], list[dict]]:
    events = []
    skipped = list(BLOCKED_SOURCE_STUBS)

    for schedule_url in FTL_SCHEDULE_URLS:
        response = fetch_url(session, schedule_url)
        if not response:
            skipped.append({"url": schedule_url, "status": "skipped", "reason": "fetch_failed"})
            continue
        for event_stub in parse_ftl_schedule(response.text, schedule_url):
            time.sleep(REQUEST_DELAY)
            result_response = fetch_url(session, event_stub["source_url"])
            if not result_response:
                skipped.append({"url": event_stub["source_url"], "status": "skipped", "reason": "fetch_failed"})
                continue
            event = parse_ftl_results_html(result_response.text, event_stub["source_url"], event_stub)
            if event:
                events.append(event)
            else:
                skipped.append({"url": event_stub["source_url"], "status": "skipped", "reason": "no_result_table"})

    for pdf_url in PDF_SOURCE_URLS:
        time.sleep(REQUEST_DELAY)
        response = fetch_url(session, pdf_url)
        if not response:
            skipped.append({"url": pdf_url, "status": "skipped", "reason": "fetch_failed"})
            continue
        text = extract_pdf_text(response.content)
        parsed = parse_pdf_text(text, pdf_url)
        if parsed:
            events.extend(parsed)
        else:
            skipped.append({"url": pdf_url, "status": "skipped", "reason": "no_youth_pdf_results"})

    for index_url in ENGARDE_INDEX_URLS:
        time.sleep(REQUEST_DELAY)
        response = fetch_url(session, index_url)
        if not response:
            skipped.append({"url": index_url, "status": "skipped", "reason": "fetch_failed"})
            continue
        for event_stub in parse_engarde_index(response.text, index_url):
            time.sleep(REQUEST_DELAY)
            result_response = fetch_url(session, event_stub["source_url"])
            if not result_response:
                skipped.append({"url": event_stub["source_url"], "status": "skipped", "reason": "fetch_failed"})
                continue
            event = parse_engarde_results_html(result_response.text, event_stub["source_url"], event_stub)
            if event:
                events.append(event)
            else:
                skipped.append({"url": event_stub["source_url"], "status": "skipped", "reason": "no_result_table"})

    return events, skipped


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_british_youth").start()
    try:
        session = requests.Session()
        done_event_ids = set(get_state(SOURCE, "done_event_ids") or [])
        events, skipped_sources = discover_events(session)
        written = failed = skipped = 0

        for event in events:
            event_id = f"{event.get('season') or 'unknown'}:{_event_slug(event)}:{event.get('source_kind')}"
            if event_id in done_event_ids:
                skipped += 1
                continue
            tournament_id = upsert_tournament(event)
            if not tournament_id:
                failed += 1
                continue
            count = upsert_results(tournament_id, event["results"])
            if count == 0:
                failed += 1
                continue
            done_event_ids.add(event_id)
            set_state(SOURCE, "done_event_ids", sorted(done_event_ids))
            written += count
            time.sleep(REQUEST_DELAY)

        skipped += len(skipped_sources)
        set_state(SOURCE, "last_run", {"at": datetime.now(timezone.utc).isoformat(), "events": len(events), "skipped_sources": skipped_sources})
        run_log.complete(written=written, failed=failed, skipped=skipped, metadata={"events": len(events), "skipped_sources": skipped_sources[:50]})
        print(f"Done - written={written}, failed={failed}, skipped={skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

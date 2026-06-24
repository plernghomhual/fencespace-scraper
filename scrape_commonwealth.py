"""
Commonwealth Fencing Championships results scraper.

Probe summary (verified 2026-06-01):
  Olympedia: Olympic fencing only; no Commonwealth result structure found.
  CFF official: 1998/2006 result PDFs contain full rank tables.
  CFC2018: Australian Fencing pages contain full final result tables.
  CFF 2010/CFC2022: public pages found, but no static full ranking tables.
"""
from __future__ import annotations

import io
import os
import re
import time
from datetime import UTC, datetime, timezone
from typing import Any
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

CFF_BASE = "https://www.commonwealthfencing.org"
HISTORY_URL = f"{CFF_BASE}/index.php/senior-events/past-senior-championships"
SOURCE = "commonwealth"
REQUEST_DELAY = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}

WEAPON_PATTERNS = [
    (re.compile(r"\bepee\b|\bep\u00e9e\b", re.I), "Epee"),
    (re.compile(r"\bfoil\b", re.I), "Foil"),
    (re.compile(r"\bsabre\b|\bsaber\b", re.I), "Sabre"),
]
GENDER_PATTERNS = [
    (re.compile(r"\bwomen\b|\bwoman\b|\bwomen['\u2019]s\b", re.I), "Women"),
    (re.compile(r"\bmen\b|\bman\b|\bmen['\u2019]s\b", re.I), "Men"),
]

COUNTRY_ALIASES = {
    "AUS": "AUS",
    "AUST": "AUS",
    "AUSTRALIA": "AUS",
    "BER": "BER",
    "CAN": "CAN",
    "CANADA": "CAN",
    "ENG": "ENG",
    "ENGLAND": "ENG",
    "GUE": "GUE",
    "GUERNSEY": "GUE",
    "IND": "IND",
    "INDIA": "IND",
    "IOM": "IOM",
    "ISLE OF MAN": "IOM",
    "JER": "JER",
    "JERSEY": "JER",
    "MAL": "MAS",
    "MAS": "MAS",
    "MALAYSIA": "MAS",
    "N.IRE": "NIR",
    "N IRE": "NIR",
    "NIR": "NIR",
    "NORTHERN IRELAND": "NIR",
    "NZ": "NZL",
    "NZL": "NZL",
    "NEW ZEALAND": "NZL",
    "RSA": "RSA",
    "S.AFR": "RSA",
    "S AFR": "RSA",
    "SOUTH AFRICA": "RSA",
    "SCO": "SCO",
    "SCOT": "SCO",
    "SCOTLAND": "SCO",
    "SIN": "SGP",
    "SIG": "SGP",
    "SINGAPORE": "SGP",
    "ST.VINCENT": "VIN",
    "ST VINCENT": "VIN",
    "VIN": "VIN",
    "WAL": "WAL",
    "WALES": "WAL",
}

PDF_RESULT_SOURCES = [
    {
        "edition_id": "1998",
        "url": f"{CFF_BASE}/images/results/1998_open_results.pdf",
    },
    {
        "edition_id": "2006",
        "url": f"{CFF_BASE}/images/results/2006_open_results.pdf",
    },
]

AUSFENCING_2018_URLS = [
    "https://www.ausfencing.org/competitions/mens-epee-teams-canberra-4/",
    "https://www.ausfencing.org/competitions/mens-epee-individual-canberra-10/",
    "https://www.ausfencing.org/competitions/mens-foil-teams-canberra-4/",
    "https://www.ausfencing.org/competitions/mens-foil-individual-canberra-10/",
    "https://www.ausfencing.org/competitions/womens-epee-teams-canberra-3/",
    "https://www.ausfencing.org/competitions/womens-sabre-teams-canberra-2/",
    "https://www.ausfencing.org/competitions/womens-epee-individual-canberra-9/",
    "https://www.ausfencing.org/competitions/womens-foil-teams-canberra-2/",
    "https://www.ausfencing.org/competitions/mens-sabre-teams-canberra-2/",
    "https://www.ausfencing.org/competitions/womens-sabre-individual-canberra-6/",
    "https://www.ausfencing.org/competitions/womens-foil-individual-canberra-9/",
    "https://www.ausfencing.org/competitions/mens-sabre-individual-canberra-6/",
]

NO_DATA_PROBE_URLS = [
    "https://www.olympedia.org/sports/FEN",
    f"{CFF_BASE}/events/cfc10/results.html",
    "https://www.cffc2022.com/final-results",
    "https://www.cffc2022.com/live-results",
]


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _ascii_key(value):
    return _clean_text(value).replace("\u2019", "'")


def classify_event(event_name):
    """Return weapon/gender/team/event_code for a Commonwealth fencing event name."""
    normalized = _ascii_key(event_name)
    weapon = next((weapon for pattern, weapon in WEAPON_PATTERNS if pattern.search(normalized)), None)
    gender = None
    for pattern, parsed_gender in GENDER_PATTERNS:
        if pattern.search(normalized):
            gender = parsed_gender
            break
    if gender == "Men" and re.search(r"\bwomen\b|\bwomen['\u2019]s\b", normalized, re.I):
        gender = "Women"

    team = bool(re.search(r"\bteam\b|\bteams\b", normalized, re.I))
    event_type = "team" if team else "individual"
    event_code = None
    if weapon and gender:
        event_code = f"{gender.lower()}-{weapon.lower()}-{event_type}"
    return {"weapon": weapon, "gender": gender, "team": team, "event_code": event_code}


def parse_history_page(html, base_url=CFF_BASE):
    """Parse CFF history links and distinguish Games from standalone Championships."""
    soup = BeautifulSoup(html, "html.parser")
    editions = []
    seen = set()
    for link in soup.find_all("a", href=True):
        title = _clean_text(link.get_text(" ", strip=True))
        if not re.search(r"\b(19|20)\d{2}\b", title):
            continue
        if not re.search(r"commonwealth|british empire|british commonwealth", title, re.I):
            continue
        if not re.search(r"championship|games", title, re.I):
            continue

        year = re.search(r"\b((?:19|20)\d{2})\b", title).group(1)  # type: ignore[union-attr]
        normalized_title = title.replace(" - ", " - ")
        key = (year, normalized_title)
        if key in seen:
            continue
        seen.add(key)
        is_games = bool(re.search(r"\bgames\b", title, re.I)) and not re.search(r"championship", title, re.I)
        editions.append(
            {
                "edition_id": year,
                "edition_name": normalized_title,
                "year": year,
                "kind": "commonwealth_games" if is_games else "standalone_championship",
                "source_url": urljoin(base_url, link["href"]),
            }
        )
    return editions


def _rank_to_int(raw):
    match = re.match(r"\s*0*(\d+)", str(raw or ""))
    return int(match.group(1)) if match else None


def _medal_for_rank(rank):
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _country_code(raw):
    key = _ascii_key(raw).upper().replace(".", ".")
    return COUNTRY_ALIASES.get(key, key if re.fullmatch(r"[A-Z]{3}", key) else None)


def _split_country_tail(value):
    text = _clean_text(value)
    aliases = sorted(COUNTRY_ALIASES, key=len, reverse=True)
    for alias in aliases:
        pattern = rf"^(?P<name>.+?)\s+{re.escape(alias)}$"
        match = re.match(pattern, text, re.I)
        if match:
            return match.group("name").strip(), COUNTRY_ALIASES[alias]
    parts = text.rsplit(" ", 1)
    if len(parts) == 2 and re.fullmatch(r"[A-Za-z]{3}", parts[1]):
        return parts[0].strip(), _country_code(parts[1])
    return text, None


def _format_upper_surname_name(name):
    parts = name.split()
    if len(parts) < 2:
        return name
    surname_parts = []
    given_parts: list[Any] = []
    for part in parts:
        if not given_parts and re.fullmatch(r"[A-Z][A-Z'\-\u2019]+", part):
            surname_parts.append(part)
        else:
            given_parts.append(part)
    if surname_parts and given_parts:
        return f"{' '.join(given_parts)} {' '.join(surname_parts)}"
    return name


def _title_word(word):
    return "-".join(piece.capitalize() for piece in word.split("-"))


def _format_comma_name(name):
    if "," not in name:
        return _format_upper_surname_name(name)
    last, first = [part.strip() for part in name.split(",", 1)]
    ordered = f"{first} {last}"
    return " ".join(_title_word(part) for part in ordered.split())


def _parse_result_line(line, team=False):
    match = re.match(r"^\s*(?P<rank>\d+)(?:=)?\s+(?P<body>.+?)\s*$", line)
    if not match:
        return None
    rank = _rank_to_int(match.group("rank"))
    body = re.sub(r"\s+\d+\s*-\s*\d+\s*$", "", match.group("body")).strip()
    name, country = _split_country_tail(body)
    if not name or not country:
        return None
    parsed_name = _clean_text(name).rstrip(",")
    if not team:
        parsed_name = _format_comma_name(parsed_name)
    return {
        "rank": rank,
        "name": parsed_name,
        "country": country,
        "medal": _medal_for_rank(rank),
        "fie_id": None,
    }


def _edition_from_pdf_text(text):
    match = re.search(r"\b((?:19|20)\d{2}):\s*([^\n\r]+)", text)
    if not match:
        return None, None
    year = match.group(1)
    location = _clean_text(match.group(2))
    return year, f"{year} Commonwealth Fencing Championships - {location}"


def parse_pdf_text_events(text, source_url=None):
    """Parse pdfplumber-extracted CFF PDF result text into event dicts."""
    edition_id, edition_name = _edition_from_pdf_text(text)
    if not edition_id:
        return []

    events = []
    current = None
    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue
        if re.search(r"^\u00a9|^\d+\s*/\s*\d+$|^place\s+country|^wilkinson", line, re.I):
            continue
        classification = classify_event(line)
        looks_like_event = (
            classification["weapon"]
            and classification["gender"]
            and re.search(r"\bindividual\b|\bteam\b", _ascii_key(line), re.I)
            and not re.match(r"^\d", line)
        )
        if looks_like_event:
            if current and current["results"]:
                events.append(current)
            current = {
                "edition_id": edition_id,
                "edition_name": edition_name,
                "kind": "standalone_championship",
                "event_name": line,
                "event_code": classification["event_code"],
                "source_url": source_url,
                "source_kind": "cff_pdf",
                "results": [],
            }
            continue
        if not current:
            continue
        row = _parse_result_line(line, team=classify_event(current["event_name"])["team"])
        if row:
            current["results"].append(row)
    if current and current["results"]:
        events.append(current)
    return events


def parse_ausfencing_competition_page(html, url, edition_id, edition_name):
    """Parse a 2018 Australian Fencing competition page final results table."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find(["h1", "h2"])
    event_name = _clean_text(heading.get_text(" ", strip=True)) if heading else ""
    if not event_name and soup.title:
        event_name = _clean_text(soup.title.get_text(" ", strip=True).split("|")[0])
    classification = classify_event(event_name)
    if not classification["weapon"] or not classification["gender"]:
        return None

    candidates = []
    for table in soup.find_all("table"):
        first_row = table.find("tr")
        if not first_row:
            continue
        headers = [_clean_text(cell.get_text(" ", strip=True)).lower() for cell in first_row.find_all(["th", "td"])]
        if not {"rank", "name"}.issubset(set(headers)):
            continue
        previous_heading = table.find_previous(["h1", "h2", "h3", "h4", "p"])
        previous_text = _clean_text(previous_heading.get_text(" ", strip=True)) if previous_heading else ""
        candidates.append((re.search(r"final\s+results", previous_text, re.I) is not None, table))
    if not candidates:
        return None
    table = next((candidate for is_final, candidate in candidates if is_final), candidates[-1][1])

    rows = []
    for tr in table.find_all("tr")[1:]:
        cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        rank = _rank_to_int(cells[0])
        country = _country_code(cells[2])
        name = _format_comma_name(cells[1].rstrip(","))
        if rank is None or not name or not country:
            continue
        rows.append(
            {
                "rank": rank,
                "name": name,
                "country": country,
                "medal": _medal_for_rank(rank),
                "fie_id": None,
            }
        )
    if not rows:
        return None
    return {
        "edition_id": str(edition_id),
        "edition_name": edition_name,
        "kind": "standalone_championship",
        "event_name": event_name,
        "event_code": classification["event_code"],
        "source_url": url,
        "source_kind": "ausfencing_html",
        "results": rows,
    }


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=25)
            if response.status_code == 200:
                return response
            if response.status_code == 404:
                return None
            print(f"  HTTP {response.status_code} for {url}")
            if response.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt * (10 if response.status_code == 429 else 2))
            else:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def fetch_editions():
    response = _get(HISTORY_URL)
    if not response:
        return []
    return parse_history_page(response.text, HISTORY_URL)


def fetch_pdf_text(url):
    response = _get(url)
    if not response:
        return None
    import pdfplumber

    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return "\n".join(page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages)


def discover_events():
    """Fetch known structured Commonwealth result sources and return parsed events."""
    events = []
    for source in PDF_RESULT_SOURCES:
        print(f"  Fetching CFF PDF {source['url']}")
        text = fetch_pdf_text(source["url"])
        if text:
            parsed = parse_pdf_text_events(text, source_url=source["url"])
            print(f"    {len(parsed)} events parsed")
            events.extend(parsed)
        else:
            print("    no PDF text")
        time.sleep(REQUEST_DELAY)

    edition_name = "2018 Commonwealth Senior Championships - Canberra, Australia"
    for url in AUSFENCING_2018_URLS:
        print(f"  Fetching 2018 result page {url}")
        response = _get(url)
        if response:
            event = parse_ausfencing_competition_page(response.text, url, "2018", edition_name)
            if event:
                print(f"    {event['event_code']}: {len(event['results'])} rows")
                events.append(event)
            else:
                print("    no final result table")
        else:
            print("    fetch failed")
        time.sleep(REQUEST_DELAY)
    return events


def probe_no_data_sources():
    """Log probed URLs known not to expose static full result rows."""
    statuses = []
    for url in NO_DATA_PROBE_URLS:
        response = _get(url, retries=1)
        status = response.status_code if response else None
        statuses.append({"url": url, "status": status})
        print(f"  Probe {url} -> {status}")
        time.sleep(0.3)
    return statuses


def _extract_year(edition_name):
    match = re.search(r"\b((?:19|20)\d{2})\b", edition_name or "")
    return match.group(1) if match else None


def upsert_tournament(event, classification=None):
    classification = classification or classify_event(event["event_name"])
    source_id = f"commonwealth:{event['edition_id']}:{event['event_code']}"
    row = {
        "source_id": source_id,
        "name": f"{event['edition_name']} - {event['event_name']}",
        "season": _extract_year(event["edition_name"]) or str(event["edition_id"]),
        "type": "commonwealth_games" if event.get("kind") == "commonwealth_games" else "commonwealth_championship",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": "Senior",
        "country": None,
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "source_url": event.get("source_url"),
            "source_kind": event.get("source_kind"),
            "edition_id": event["edition_id"],
            "edition_name": event["edition_name"],
            "event_name": event["event_name"],
            "event_code": event["event_code"],
            "team": classification["team"],
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()  # type: ignore[union-attr]
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def _match_fencer(fie_id=None, name=None, country=None):
    if not supabase:
        return None
    if fie_id:
        try:
            rows = (
                supabase.table("fs_fencers")
                .select("id")
                .eq("fie_id", str(fie_id))
                .limit(2)
                .execute()
                .data
            )
            if rows:
                return rows[0]["id"]
        except Exception:
            pass
    if name and country:
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
    return None


def upsert_results(tournament_id, result_rows):
    """Delete and reinsert Commonwealth placements. Returns written count or 0 on partial failure."""
    db_rows = []
    for row in result_rows:
        if row.get("rank") is None:
            continue
        fencer_id = _match_fencer(row.get("fie_id"), row.get("name"), row.get("country"))
        db_row = {
            "tournament_id": tournament_id,
            "name": row["name"],
            "nationality": row.get("country"),
            "rank": row["rank"],
            "medal": row.get("medal"),
            "fencer_id": fencer_id,
            "metadata": {
                "source": SOURCE,
                "country": row.get("country"),
                "fie_id": row.get("fie_id"),
            },
        }
        if row.get("fie_id"):
            db_row["fie_fencer_id"] = str(row["fie_id"])
        db_rows.append(db_row)
    if not db_rows:
        return 0

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()  # type: ignore[union-attr]
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i : i + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()  # type: ignore[union-attr]
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    return written if written == len(db_rows) else 0


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_commonwealth").start()
    try:
        print(f"Commonwealth scraper starting - {datetime.now(UTC).isoformat()}")
        done_events = set(get_state(SOURCE, "done_event_ids") or [])
        print(f"  {len(done_events)} event IDs already done")

        editions = fetch_editions()
        games_count = sum(1 for edition in editions if edition["kind"] == "commonwealth_games")
        standalone_count = sum(1 for edition in editions if edition["kind"] == "standalone_championship")
        print(f"  Editions discovered: {len(editions)} ({standalone_count} standalone, {games_count} Games)")

        probe_statuses = probe_no_data_sources()
        events = discover_events()
        if not events:
            print("No structured Commonwealth result rows found. Probed URLs:")
            for status in probe_statuses:
                print(f"  {status['status']} {status['url']}")
            run_log.complete(written=0, failed=0, skipped=len(probe_statuses))
            return

        written = failed = skipped = 0
        for event in events:
            event_id = f"{event['edition_id']}:{event['event_code']}"
            if event_id in done_events:
                skipped += 1
                continue
            classification = classify_event(event["event_name"])
            if not classification["weapon"] or not classification["gender"]:
                print(f"  Skipping unclassifiable event: {event['event_name']}")
                skipped += 1
                continue
            tournament_id = upsert_tournament(event, classification)
            if not tournament_id:
                failed += 1
                continue
            count = upsert_results(tournament_id, event["results"])
            if count == 0:
                print(f"  No rows written for {event_id}")
                failed += 1
                continue
            print(f"  {event_id}: {count} results inserted")
            done_events.add(event_id)
            set_state(SOURCE, "done_event_ids", sorted(done_events))
            written += count
            time.sleep(REQUEST_DELAY)

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"Done - written={written}, failed={failed}, skipped={skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

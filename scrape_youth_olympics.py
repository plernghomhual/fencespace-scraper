"""
Youth Olympic Games and 2023 multi-sport fencing results scraper.

Probe notes (2026-06-01):
  YOG: Olympedia /editions/{id}/sports/FEN, ids 65/67/69/71.
       Result pages use table.table-striped with Pos|Competitor|NOC|Medal.
  WFG: No public 2023 Bali "World Fencing Games" result source was found.
       The available 2023 multi-sport fencing source is the Riyadh 2023
       World Combat Games Swiss Timing results book PDF.
"""

import io
import os
import re
import time
import unicodedata
from datetime import datetime, timezone

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

OLYMPEDIA_BASE = "https://www.olympedia.org"
REQUEST_DELAY = 1.5
SOURCE = "youth_olympics_wfg"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}
PDF_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/pdf,*/*;q=0.8",
}

YOUTH_OLYMPIC_EDITION_IDS = [
    (65, "Singapore 2010"),
    (67, "Nanjing 2014"),
    (69, "Buenos Aires 2018"),
    (71, "Dakar 2026"),
]

WFG_RESULTS_BOOKS = {
    2023: {
        "name": "Riyadh 2023 World Combat Games",
        "location": "Riyadh",
        "country": "Saudi Arabia",
        "url": (
            "https://web.archive.org/web/20231105110628id_/"
            "https://pushserver.web.swisstiming.com/node/binaryData/"
            "WCG2023_GLO_PROD/Fencing.pdf"
            "?h=0DKloeBv%2FjEYbZk156UDekXSWwo%3D"
        ),
    }
}

WEAPON_PATTERNS = [
    (re.compile(r"\bépée\b|\bepee\b", re.I), "Epee"),
    (re.compile(r"\bfoil\b", re.I), "Foil"),
    (re.compile(r"\bsabre\b|\bsaber\b", re.I), "Sabre"),
]

GENDER_PATTERNS = [
    (re.compile(r"\bwomen'?s\b|\bwomen\b|\bgirls?\b", re.I), "Women"),
    (re.compile(r"\bmen'?s\b|\bmen\b|\bboys?\b", re.I), "Men"),
    (re.compile(r"\bmixed\b", re.I), "Mixed"),
]

MEDALS = {"Gold", "Silver", "Bronze"}


def clean_text(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def title_case(value):
    text = clean_text(value)
    return text.title() if text else None


def normalize_person_name(value):
    text = clean_text(value)
    if not text:
        return None
    parts = text.split()
    leading = 0
    while (
        leading < len(parts)
        and any(ch.isalpha() for ch in parts[leading])
        and parts[leading].upper() == parts[leading]
    ):
        leading += 1
    if 0 < leading < len(parts):
        last = title_case(" ".join(parts[:leading]))
        first = title_case(" ".join(parts[leading:]))
        return first if first.lower() == last.lower() else f"{first} {last}"
    return text


def classify_event(event_name):
    """Return weapon/gender/team classification for a fencing event label."""
    weapon = next((w for pat, w in WEAPON_PATTERNS if pat.search(event_name)), None)
    gender = None
    for pat, g in GENDER_PATTERNS:
        if pat.search(event_name):
            gender = g
            break
    team = bool(re.search(r"\bteam\b", event_name, re.I))
    return {"weapon": weapon, "gender": gender, "team": team}


def slugify_event(event_name):
    text = unicodedata.normalize("NFKD", event_name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.replace("'", "").replace("’", "")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text


def _rank_to_int(value):
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def _extract_year(value):
    match = re.search(r"\b(20\d{2}|19\d{2})\b", value or "")
    return match.group(1) if match else None


def parse_yog_edition_sport_page(html, edition_id, edition_name):
    """Parse one Olympedia Youth Olympic FEN page, dedupe links, and keep individual events."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()
    for link in soup.find_all("a", href=re.compile(r"^/results/\d+$")):
        result_id = re.search(r"/results/(\d+)", link["href"]).group(1)
        if result_id in seen:
            continue
        seen.add(result_id)
        event_name = link.get_text(" ", strip=True)
        classification = classify_event(event_name)
        if classification["team"] or "individual" not in event_name.lower():
            continue
        events.append(
            {
                "result_id": result_id,
                "event_name": event_name,
                "edition_id": str(edition_id),
                "edition_name": edition_name,
            }
        )
    return events


def _header_indexes(headers, cell_count):
    normalized = [re.sub(r"\s+", " ", h.lower()).strip() for h in headers]
    rank_idx = 0
    name_idx = None
    country_idx = None
    medal_idx = None
    for i, header in enumerate(normalized):
        if header in {"competitor", "competitors", "name"}:
            name_idx = i
        elif header == "noc":
            country_idx = i
        elif header == "medal":
            medal_idx = i
    if name_idx is None:
        name_idx = 2 if cell_count >= 5 else 1
    if country_idx is None:
        country_idx = name_idx + 1
    if medal_idx is None:
        medal_idx = country_idx + 1
    return rank_idx, name_idx, country_idx, medal_idx


def parse_olympedia_results_page(html, result_id):
    """Parse Olympedia result tables with or without an Olympic bib-number column."""
    soup = BeautifulSoup(html, "html.parser")
    table = None
    for candidate in soup.find_all("table"):
        classes = candidate.get("class", [])
        if "biodata" in classes:
            continue
        if "table-striped" in classes or "table" in classes:
            table = candidate
            break
    if not table:
        return []

    trs = table.find_all("tr")
    if not trs:
        return []
    headers = [cell.get_text(" ", strip=True) for cell in trs[0].find_all(["th", "td"])]

    rows = []
    for tr in trs[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        rank_idx, name_idx, country_idx, medal_idx = _header_indexes(headers, len(cells))
        if max(name_idx, country_idx) >= len(cells):
            continue
        rank = _rank_to_int(cells[rank_idx].get_text(" ", strip=True))
        competitor_cell = cells[name_idx]
        name = competitor_cell.get_text(" ", strip=True)
        if not name:
            continue
        athlete_link = competitor_cell.find("a", href=re.compile(r"/athletes/\d+"))
        athlete_id = None
        if athlete_link:
            athlete_id = re.search(r"/athletes/(\d+)", athlete_link["href"]).group(1)
        country = cells[country_idx].get_text(" ", strip=True) if country_idx < len(cells) else None
        medal_raw = cells[medal_idx].get_text(" ", strip=True) if medal_idx < len(cells) else ""
        medal = medal_raw if medal_raw in MEDALS else None
        rows.append(
            {
                "rank": rank,
                "name": name,
                "country": country,
                "medal": medal,
                "athlete_id": athlete_id,
            }
        )
    return rows


def parse_wfg_standing_row(line, team=False):
    medal_suffix = r"(?:\s+(?P<medal>Gold|Silver|Bronze))?$"
    if team:
        match = re.match(r"^=?(?P<rank>\d+)\s+(?P<noc>[A-Z]{3})\s+-\s+(?P<country>.+?)" + medal_suffix, line)
        if not match:
            return None
        country_name = clean_text(match.group("country"))
        return {
            "rank": int(match.group("rank")),
            "name": country_name,
            "country": match.group("noc"),
            "country_name": country_name,
            "medal": match.group("medal"),
        }

    match = re.match(
        r"^=?(?P<rank>\d+)\s+(?P<name>.+?)\s+(?P<noc>[A-Z]{3})\s+-\s+(?P<country>.+?)"
        + medal_suffix,
        line,
    )
    if not match:
        return None
    return {
        "rank": int(match.group("rank")),
        "name": normalize_person_name(match.group("name")),
        "country": match.group("noc"),
        "country_name": clean_text(match.group("country")),
        "medal": match.group("medal"),
    }


def parse_wfg_results_book_text(text, year=2023):
    """Parse Swiss Timing extracted text from the Riyadh 2023 fencing results book."""
    lines = [line.strip() for line in text.splitlines()]
    events = []
    seen = set()
    for i, line in enumerate(lines):
        if line != "Standings":
            continue
        event_name = None
        for j in range(i - 1, -1, -1):
            if lines[j] and lines[j] != "Fencing":
                event_name = lines[j]
                break
        if not event_name:
            continue

        header_idx = None
        team = False
        for j in range(i + 1, min(i + 8, len(lines))):
            if lines[j] == "Rank Name NOC":
                header_idx = j
                team = False
                break
            if lines[j] == "Rank NOC":
                header_idx = j
                team = True
                break
        if header_idx is None:
            continue

        rows = []
        for row_line in lines[header_idx + 1 :]:
            if not row_line:
                continue
            if row_line.startswith("FEN") or row_line.startswith("King Saud University"):
                break
            parsed = parse_wfg_standing_row(row_line, team=team)
            if parsed:
                rows.append(parsed)
        if not rows:
            continue

        event_code = slugify_event(event_name)
        if event_code in seen:
            continue
        seen.add(event_code)
        classification = classify_event(event_name)
        events.append(
            {
                "year": year,
                "event_name": event_name,
                "event_code": event_code,
                "classification": classification,
                "rows": rows,
            }
        )
    return events


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                return response.text
            if response.status_code == 404:
                return None
            if response.status_code in (429, 500, 502, 503):
                time.sleep((2**attempt) * (10 if response.status_code == 429 else 2))
                continue
            print(f"  HTTP {response.status_code} for {url}")
            return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2**attempt)
    return None


def _get_bytes(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=PDF_HEADERS, timeout=90)
            if response.status_code == 200 and response.content.startswith(b"%PDF"):
                return response.content
            if response.status_code == 200:
                print(f"  Non-PDF response for {url}: {response.headers.get('content-type')}")
                return None
            print(f"  HTTP {response.status_code} for {url}")
            if response.status_code in (429, 500, 502, 503):
                time.sleep((2**attempt) * (10 if response.status_code == 429 else 2))
                continue
            return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2**attempt)
    return None


def fetch_yog_events():
    events = []
    for edition_id, edition_name in YOUTH_OLYMPIC_EDITION_IDS:
        html = _get(f"{OLYMPEDIA_BASE}/editions/{edition_id}/sports/FEN")
        if not html:
            continue
        events.extend(parse_yog_edition_sport_page(html, edition_id, edition_name))
        time.sleep(0.5)
    return events


def fetch_olympedia_result_page(result_id):
    html = _get(f"{OLYMPEDIA_BASE}/results/{result_id}")
    return parse_olympedia_results_page(html, result_id) if html else []


def fetch_wfg_results_book_text(year=2023):
    source = WFG_RESULTS_BOOKS[year]
    pdf_bytes = _get_bytes(source["url"])
    if not pdf_bytes:
        return None
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required to parse WFG results books") from exc
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n\n".join(page.extract_text() or "" for page in pdf.pages)


def fetch_wfg_events(year=2023):
    text = fetch_wfg_results_book_text(year)
    return parse_wfg_results_book_text(text, year=year) if text else []


def build_yog_tournament_row(event, classification):
    year = _extract_year(event["edition_name"])
    return {
        "source_id": f"yog:{event['edition_id']}:{event['result_id']}",
        "name": f"{event['edition_name']} Youth Olympic Games — {event['event_name']}",
        "season": year,
        "type": "youth_olympics",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": "Youth",
        "country": None,
        "has_results": True,
        "metadata": {
            "source": "olympedia",
            "olympedia_result_id": event["result_id"],
            "olympedia_edition_id": event["edition_id"],
            "edition_name": event["edition_name"],
            "event_name": event["event_name"],
            "team": classification["team"],
        },
    }


def build_wfg_tournament_row(event):
    source = WFG_RESULTS_BOOKS[event["year"]]
    classification = event["classification"]
    return {
        "source_id": f"wfg:{event['year']}:{event['event_code']}",
        "name": f"{source['name']} — {event['event_name']}",
        "season": str(event["year"]),
        "type": "world_fencing_games",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": "Senior",
        "country": source["country"],
        "location": source["location"],
        "has_results": True,
        "metadata": {
            "source": "swiss_timing_results_book",
            "source_url": source["url"],
            "event_name": event["event_name"],
            "event_code": event["event_code"],
            "team": classification["team"],
            "actual_competition_name": source["name"],
        },
    }


def upsert_tournament(row):
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {row.get('source_id')}: {exc}")
        return None


def _match_fencer(name, country, fie_fencer_id=None):
    if supabase is None:
        return None
    try:
        if fie_fencer_id:
            rows = (
                supabase.table("fs_fencers")
                .select("id")
                .eq("fie_id", str(fie_fencer_id))
                .limit(2)
                .execute()
                .data
                or []
            )
            if len(rows) == 1:
                return rows[0]["id"]
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
                return rows[0]["id"]
    except Exception:
        return None
    return None


def build_result_rows(tournament_id, result_rows, source):
    rows = []
    for row in result_rows:
        if row.get("rank") is None:
            continue
        fencer_id = None
        if not row.get("team"):
            fencer_id = _match_fencer(row.get("name"), row.get("country"), row.get("fie_fencer_id"))
        metadata = {"source": source}
        if row.get("athlete_id"):
            metadata["olympedia_athlete_id"] = row["athlete_id"]
        if row.get("country_name"):
            metadata["country_name"] = row["country_name"]
        rows.append(
            {
                "tournament_id": tournament_id,
                "name": row.get("name"),
                "nationality": row.get("country"),
                "rank": row.get("rank"),
                "medal": row.get("medal"),
                "fencer_id": fencer_id,
                "metadata": metadata,
            }
        )
    return rows


def upsert_results(tournament_id, result_rows, source):
    db_rows = build_result_rows(tournament_id, result_rows, source)
    if not db_rows:
        return 0
    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i : i + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    if written < len(db_rows):
        return 0
    return written


def scrape_yog(done_ids):
    written = failed = skipped = 0
    events = fetch_yog_events()
    print(f"  YOG events found: {len(events)}")
    for event in events:
        state_id = f"yog:{event['edition_id']}:{event['result_id']}"
        if state_id in done_ids:
            skipped += 1
            continue
        classification = classify_event(event["event_name"])
        if not classification["weapon"] or not classification["gender"] or classification["team"]:
            skipped += 1
            continue
        tournament_id = upsert_tournament(build_yog_tournament_row(event, classification))
        if not tournament_id:
            failed += 1
            continue
        rows = fetch_olympedia_result_page(event["result_id"])
        if not rows:
            failed += 1
            continue
        n = upsert_results(tournament_id, rows, source="yog")
        if n == 0:
            failed += 1
            continue
        print(f"    {state_id}: {n} results")
        done_ids.add(state_id)
        set_state(SOURCE, "done_event_ids", sorted(done_ids))
        written += 1
        time.sleep(REQUEST_DELAY)
    return written, failed, skipped


def scrape_wfg(done_ids):
    written = failed = skipped = 0
    for year in WFG_RESULTS_BOOKS:
        events = fetch_wfg_events(year)
        print(f"  WFG/WCG {year} events found: {len(events)}")
        for event in events:
            state_id = f"wfg:{year}:{event['event_code']}"
            if state_id in done_ids:
                skipped += 1
                continue
            classification = event["classification"]
            if not classification["weapon"] or not classification["gender"]:
                skipped += 1
                continue
            tournament_id = upsert_tournament(build_wfg_tournament_row(event))
            if not tournament_id:
                failed += 1
                continue
            rows = []
            for row in event["rows"]:
                copied = dict(row)
                copied["team"] = classification["team"]
                rows.append(copied)
            n = upsert_results(tournament_id, rows, source="wfg")
            if n == 0:
                failed += 1
                continue
            print(f"    {state_id}: {n} results")
            done_ids.add(state_id)
            set_state(SOURCE, "done_event_ids", sorted(done_ids))
            written += 1
            time.sleep(REQUEST_DELAY)
    return written, failed, skipped


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_youth_olympics").start()
    try:
        print(f"Youth Olympics/WFG scraper starting — {datetime.now(timezone.utc).isoformat()}")
        done_ids = set(get_state(SOURCE, "done_event_ids") or [])
        written = failed = skipped = 0

        yog_written, yog_failed, yog_skipped = scrape_yog(done_ids)
        written += yog_written
        failed += yog_failed
        skipped += yog_skipped

        wfg_written, wfg_failed, wfg_skipped = scrape_wfg(done_ids)
        written += wfg_written
        failed += wfg_failed
        skipped += wfg_skipped

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"Done — written={written}, failed={failed}, skipped={skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

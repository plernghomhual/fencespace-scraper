"""
Olympedia Olympic fencing historical results scraper.

URL structure (verified 2026-05-29):
  Editions list:       GET /editions  -> table with /editions/{id} links + year + season
  Edition sport page:  GET /editions/{edition_id}/sports/FEN -> events table with /results/{id} links
  Result page:         GET /results/{result_id} -> H1=event name, table.table-striped: Pos|Number|Competitor|NOC|Medal|...
"""
import os
import re
import time
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
SOURCE = "olympedia"
REQUEST_DELAY = 2.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,*/*;q=0.8",
}

WEAPON_PATTERNS = [
    (re.compile(r"\bépée\b|\bepee\b", re.I), "Epee"),
    (re.compile(r"\bfoil\b", re.I), "Foil"),
    (re.compile(r"\bsabre\b|\bsaber\b", re.I), "Sabre"),
]
GENDER_PATTERNS = [
    (re.compile(r"\bwomen\b|\bwomen's\b|\bfemmes\b", re.I), "Women"),
    (re.compile(r"\bmen\b|\bmen's\b", re.I), "Men"),
]

# Summer Olympics edition IDs known to have fencing (1896-2024).
# Derived from /editions page; Winter/Youth Games excluded.
# Years without fencing (1900 partial, 1904 partial) are handled gracefully by empty results.
SUMMER_OLYMPIC_EDITION_IDS = [
    # id: year
    (1, "Athinai 1896"), (2, "Paris 1900"), (3, "St. Louis 1904"),
    (5, "London 1908"), (6, "Stockholm 1912"), (7, "Antwerpen 1920"),
    (8, "Paris 1924"), (9, "Amsterdam 1928"), (10, "Los Angeles 1932"),
    (11, "Berlin 1936"), (12, "London 1948"), (13, "Helsinki 1952"),
    (14, "Melbourne 1956"), (15, "Roma 1960"), (16, "Tokyo 1964"),
    (17, "Mexico 1968"), (18, "München 1972"), (19, "Montréal 1976"),
    (20, "Moskva 1980"), (21, "Los Angeles 1984"), (22, "Seoul 1988"),
    (23, "Barcelona 1992"), (24, "Atlanta 1996"), (25, "Sydney 2000"),
    (26, "Athinai 2004"), (27, "Beijing 2008"), (28, "London 2012"),
    (29, "Rio de Janeiro 2016"), (30, "Tokyo 2020"), (31, "Paris 2024"),
]


def classify_event(event_name):
    """Return {weapon, gender, team} classification for a fencing event name."""
    weapon = next((w for pat, w in WEAPON_PATTERNS if pat.search(event_name)), None)
    # For gender: Women must be checked before Men (Men matches in Women's)
    gender = None
    for pat, g in GENDER_PATTERNS:
        if pat.search(event_name):
            gender = g
            break
    # Re-check: if "men" matched but "women" is also in the string, prefer Women
    if gender == "Men" and re.search(r"\bwomen\b", event_name, re.I):
        gender = "Women"
    team = bool(re.search(r"\bteam\b", event_name, re.I))
    return {"weapon": weapon, "gender": gender, "team": team}


def parse_sport_page(html):
    """Parse HTML that contains /results/{id} links in first cell and /editions/{id} links in second cell.
    Used by tests and for any single-page format. Returns list of event dicts."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        result_link = cells[0].find("a", href=re.compile(r"/results/\d+"))
        edition_link = cells[1].find("a", href=re.compile(r"/editions/\d+"))
        if not result_link or not edition_link:
            continue
        result_id = re.search(r"/results/(\d+)", result_link["href"]).group(1)
        edition_id = re.search(r"/editions/(\d+)", edition_link["href"]).group(1)
        events.append({
            "result_id": result_id,
            "event_name": result_link.text.strip(),
            "edition_id": edition_id,
            "edition_name": edition_link.text.strip(),
        })
    return events


def fetch_sport_page():
    """Fetch all Olympic fencing events across all known Summer Games editions."""
    all_events = []
    for edition_id, edition_name in SUMMER_OLYMPIC_EDITION_IDS:
        events = fetch_edition_events(edition_id, edition_name)
        all_events.extend(events)
        time.sleep(0.5)
    return all_events


def parse_edition_sport_page(html, edition_id, edition_name):
    """Parse /editions/{id}/sports/FEN page. Returns list of event dicts."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for td in soup.find_all("td"):
        result_link = td.find("a", href=re.compile(r"^/results/\d+$"))
        if not result_link:
            continue
        result_id = re.search(r"/results/(\d+)", result_link["href"]).group(1)
        events.append({
            "result_id": result_id,
            "event_name": result_link.text.strip(),
            "edition_id": str(edition_id),
            "edition_name": edition_name,
        })
    return events


def parse_results_page(html, result_id):
    """Parse /results/{id} page. Returns list of placement dicts."""
    soup = BeautifulSoup(html, "html.parser")
    # Find the main results table (table-striped, not biodata)
    table = None
    for t in soup.find_all("table"):
        classes = t.get("class", [])
        if "table-striped" in classes or "table" in classes:
            # Skip biodata table
            if "biodata" not in classes:
                table = t
                break
    if not table:
        return []

    rows = []
    trs = table.find_all("tr")
    for tr in trs[1:]:  # skip header row
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        # Col 0: Pos, Col 1: Number (bib), Col 2: Competitor, Col 3: NOC, Col 4: Medal
        pos_text = cells[0].text.strip()
        try:
            rank = int(re.sub(r"\D", "", pos_text)) if pos_text else None
        except ValueError:
            rank = None

        competitor_td = cells[2]
        athlete_link = competitor_td.find("a", href=re.compile(r"/athletes/\d+"))
        athlete_id = re.search(r"/athletes/(\d+)", athlete_link["href"]).group(1) if athlete_link else None
        name = competitor_td.text.strip()
        if not name:
            continue

        noc = cells[3].text.strip() if len(cells) > 3 else None
        medal_raw = cells[4].text.strip() if len(cells) > 4 else ""
        medal = medal_raw if medal_raw in {"Gold", "Silver", "Bronze"} else None

        rows.append({
            "rank": rank,
            "name": name,
            "country": noc,
            "medal": medal,
            "athlete_id": athlete_id,
        })
    return rows


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
            print(f"  HTTP {r.status_code} for {url}")
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt * (10 if r.status_code == 429 else 2))
            else:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt+1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def fetch_edition_events(edition_id, edition_name):
    """Fetch all fencing events for one Olympic edition."""
    html = _get(f"{OLYMPEDIA_BASE}/editions/{edition_id}/sports/FEN")
    if not html:
        return []
    return parse_edition_sport_page(html, edition_id, edition_name)


def fetch_result_page(result_id):
    html = _get(f"{OLYMPEDIA_BASE}/results/{result_id}")
    if not html:
        return []
    return parse_results_page(html, result_id)


def _extract_year(edition_name):
    m = re.search(r"\b(\d{4})\b", edition_name)
    return m.group(1) if m else None


def upsert_tournament(event, classification):
    year = _extract_year(event["edition_name"])
    source_id = f"olympedia:{event['edition_id']}:{event['result_id']}"
    row = {
        "source_id": source_id,
        "name": f"{event['edition_name']} — {event['event_name']}",
        "season": year,
        "type": "olympics",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": "Senior",
        "country": None,
        "has_results": True,
        "metadata": {
            "olympedia_result_id": event["result_id"],
            "olympedia_edition_id": event["edition_id"],
            "edition_name": event["edition_name"],
            "event_name": event["event_name"],
            "team": classification["team"],
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def _match_fencer(name, country):
    try:
        rows = supabase.table("fs_fencers").select("id").ilike("name", name).eq("country", country).limit(2).execute().data
        return rows[0]["id"] if len(rows) == 1 else None
    except Exception:
        return None


def upsert_results(tournament_id, result_rows):
    """Write result rows to fs_results. Uses actual column names: nationality (not country)."""
    db_rows = []
    for r in result_rows:
        fencer_id = _match_fencer(r["name"], r["country"]) if r["name"] and r["country"] else None
        db_rows.append({
            "tournament_id": tournament_id,
            "name": r["name"],
            "nationality": r["country"],   # fs_results uses 'nationality', not 'country'
            "rank": r["rank"] if r["rank"] is not None else None,
            "medal": r["medal"],
            "fencer_id": fencer_id,
            "metadata": {"olympedia_athlete_id": r.get("athlete_id")},
        })
    if not db_rows:
        return 0
    # Delete existing results for this tournament before re-inserting.
    # Return 0 on partial failure so caller skips marking result done;
    # next run will delete+reinsert cleanly (idempotent retry).
    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i:i + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    if written < len(db_rows):
        return 0
    return written


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_olympics").start()
    try:
        print(f"Olympics scraper starting — {datetime.now(timezone.utc).isoformat()}")

        done_ids = set(get_state(SOURCE, "done_result_ids") or [])
        print(f"  {len(done_ids)} result IDs already done")

        written = failed = skipped = 0

        for edition_id, edition_name in SUMMER_OLYMPIC_EDITION_IDS:
            print(f"\n  Edition: {edition_name} (id={edition_id})")
            events = fetch_edition_events(edition_id, edition_name)
            if not events:
                print(f"    No fencing events found")
                time.sleep(REQUEST_DELAY)
                continue

            print(f"    {len(events)} events found")
            for event in events:
                result_id = event["result_id"]
                if result_id in done_ids:
                    skipped += 1
                    continue

                classification = classify_event(event["event_name"])
                if not classification["weapon"] or not classification["gender"]:
                    print(f"    Skipping unclassifiable: {event['event_name']}")
                    skipped += 1
                    continue

                print(f"    {event['event_name']} (result_id={result_id})")
                tournament_id = upsert_tournament(event, classification)
                if not tournament_id:
                    failed += 1
                    time.sleep(REQUEST_DELAY)
                    continue

                result_rows = fetch_result_page(result_id)
                if not result_rows:
                    print(f"      No results found")
                    failed += 1
                    time.sleep(REQUEST_DELAY)
                    continue

                n = upsert_results(tournament_id, result_rows)
                if n == 0:
                    print(f"      Insert failed or partial — skipping done mark")
                    failed += 1
                    time.sleep(REQUEST_DELAY)
                    continue
                print(f"      {n} results inserted")
                done_ids.add(result_id)
                set_state(SOURCE, "done_result_ids", list(done_ids))
                written += 1
                time.sleep(REQUEST_DELAY)

            time.sleep(REQUEST_DELAY)

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"\nDone — written={written}, skipped={skipped}, failed={failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

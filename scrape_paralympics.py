"""
Paralympic wheelchair fencing historical results scraper.

Probe summary (2026-06-01):
  - Olympedia exposes Olympic/Youth Olympic fencing under sport code FEN, but the
    probed sport pages did not expose Paralympic wheelchair fencing.
  - The official IPC archive exposes wheelchair fencing by edition:
      /{edition_slug}/results/wheelchair-fencing
    and event pages contain a Medallists table with rank, NPC, athlete/team, medal.
"""
import os
import re
import time
from datetime import datetime, timezone
from typing import Any
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


def _db() -> Any:
    if supabase is None:
        raise RuntimeError("Supabase is not configured")
    return supabase

PARALYMPIC_BASE = "https://www.paralympic.org"
SOURCE = "paralympics"
REQUEST_DELAY = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,*/*;q=0.8",
}

CLASSIFICATION_DESCRIPTIONS = {
    "A": "minimal impairment",
    "B": "moderate impairment",
    "C": "severe impairment",
}

WEAPON_PATTERNS = [
    (re.compile(r"\bépée\b|\bepee\b", re.I), "Epee"),
    (re.compile(r"\bfoil\b", re.I), "Foil"),
    (re.compile(r"\bsabre\b|\bsaber\b", re.I), "Sabre"),
]

GENDER_PATTERNS = [
    (re.compile(r"\bwomen\b|\bwomen's\b|\bfemale\b", re.I), "Women"),
    (re.compile(r"\bmen\b|\bmen's\b|\bmale\b", re.I), "Men"),
]

# Official IPC result archive slugs verified by probe for 1980-2024.
PARALYMPIC_EDITIONS = [
    {
        "year": "1980",
        "edition_id": "arnhem-1980",
        "edition_name": "Arnhem 1980",
        "url": f"{PARALYMPIC_BASE}/arnhem-1980/results/wheelchair-fencing",
    },
    {
        "year": "1984",
        "edition_id": "stoke-mandeville-new-york-1984",
        "edition_name": "Stoke Mandeville New York 1984",
        "url": f"{PARALYMPIC_BASE}/stoke-mandeville-new-york-1984/results/wheelchair-fencing",
    },
    {
        "year": "1988",
        "edition_id": "seoul-1988",
        "edition_name": "Seoul 1988",
        "url": f"{PARALYMPIC_BASE}/seoul-1988/results/wheelchair-fencing",
    },
    {
        "year": "1992",
        "edition_id": "barcelona-1992",
        "edition_name": "Barcelona 1992",
        "url": f"{PARALYMPIC_BASE}/barcelona-1992/results/wheelchair-fencing",
    },
    {
        "year": "1996",
        "edition_id": "atlanta-1996",
        "edition_name": "Atlanta 1996",
        "url": f"{PARALYMPIC_BASE}/atlanta-1996/results/wheelchair-fencing",
    },
    {
        "year": "2000",
        "edition_id": "sydney-2000",
        "edition_name": "Sydney 2000",
        "url": f"{PARALYMPIC_BASE}/sydney-2000/results/wheelchair-fencing",
    },
    {
        "year": "2004",
        "edition_id": "athens-2004",
        "edition_name": "Athens 2004",
        "url": f"{PARALYMPIC_BASE}/athens-2004/results/wheelchair-fencing",
    },
    {
        "year": "2008",
        "edition_id": "beijing-2008",
        "edition_name": "Beijing 2008",
        "url": f"{PARALYMPIC_BASE}/beijing-2008/results/wheelchair-fencing",
    },
    {
        "year": "2012",
        "edition_id": "london-2012",
        "edition_name": "London 2012",
        "url": f"{PARALYMPIC_BASE}/london-2012/results/wheelchair-fencing",
    },
    {
        "year": "2016",
        "edition_id": "rio-2016",
        "edition_name": "Rio 2016",
        "url": f"{PARALYMPIC_BASE}/rio-2016/results/wheelchair-fencing",
    },
    {
        "year": "2020",
        "edition_id": "tokyo-2020",
        "edition_name": "Tokyo 2020",
        "url": f"{PARALYMPIC_BASE}/tokyo-2020/results/wheelchair-fencing",
    },
    {
        "year": "2024",
        "edition_id": "paris-2024-paralympic-games",
        "edition_name": "Paris 2024 Paralympic Games",
        "url": f"{PARALYMPIC_BASE}/paris-2024-paralympic-games/results/wheelchair-fencing",
    },
]


def _clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _event_code_from_url(url):
    return urlparse(url).path.rstrip("/").split("/")[-1]


def classify_event(event_name):
    """Return weapon/gender/team/disability classification for a para fencing event."""
    name = _clean_text(event_name.replace("’", "'"))
    weapon = next((w for pat, w in WEAPON_PATTERNS if pat.search(name)), None)

    gender = None
    for pat, value in GENDER_PATTERNS:
        if pat.search(name):
            gender = value
            break
    if gender == "Men" and re.search(r"\bwomen\b|\bwomen's\b", name, re.I):
        gender = "Women"

    team = bool(re.search(r"\bteam\b", name, re.I))
    disability_class = None

    modern = re.search(r"\b(?:category|cat\.?)\s*([ABC])\b", name, re.I)
    if modern:
        disability_class = modern.group(1).upper()
    else:
        tail = re.search(
            r"\b(1B|1C(?:-\d+)?|\d+[A-Z]?(?:-\d+)?|open|novice)\b\s*$",
            name,
            re.I,
        )
        if tail:
            disability_class = tail.group(1).upper()
            if disability_class == "OPEN":
                disability_class = "Open"
            elif disability_class == "NOVICE":
                disability_class = "Novice"

    return {
        "weapon": weapon,
        "gender": gender,
        "team": team,
        "disability_class": disability_class,
        "classification_description": CLASSIFICATION_DESCRIPTIONS.get(disability_class or ""),
    }


def parse_sport_page(html, edition):
    """Parse an official IPC wheelchair fencing edition page into event links."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()
    event_href_re = re.compile(r"/results/wheelchair-fencing/[^/#?]+/?$")

    for link in soup.find_all("a", href=event_href_re):
        event_name = _clean_text(link.get_text(" ", strip=True))
        event_url = urljoin(edition["url"], link["href"])
        event_code = _event_code_from_url(event_url)
        if not event_name or event_code in {"participants", "medalstandings"}:
            continue
        if event_code in seen:
            continue
        seen.add(event_code)
        events.append({
            "edition_id": edition["edition_id"],
            "edition_name": edition["edition_name"],
            "year": edition["year"],
            "event_name": event_name,
            "event_code": event_code,
            "event_url": event_url,
        })
    return events


def _is_medallists_table(table):
    first_row = table.find("tr")
    if not first_row:
        return False
    first_text = _clean_text(first_row.get_text(" ", strip=True)).lower()
    first_classes = " ".join(first_row.get("class", []))
    header = first_row.find(["th", "td"])
    header_classes = " ".join(header.get("class", [])) if header else ""
    return "medallists" in first_text or "medallists" in first_classes or "medallists" in header_classes


def _medal_from_cell(cell, rank):
    medal_by_rank = {1: "Gold", 2: "Silver", 3: "Bronze"}
    if cell:
        classes = []
        for tagged in cell.find_all(class_=True):
            classes.extend(tagged.get("class", []))
        class_text = " ".join(classes)
        if "MEDG" in class_text:
            return "Gold"
        if "MEDS" in class_text:
            return "Silver"
        if "MEDB" in class_text:
            return "Bronze"
    return medal_by_rank.get(rank)


def _athlete_slug(cell):
    link = cell.find("a", href=True, class_=re.compile(r"athlete-name"))
    if not link:
        return None
    return link["href"].strip("/") or None


def parse_results_page(html, event):
    """Parse an official IPC event page. Returns medal placement rows."""
    soup = BeautifulSoup(html, "html.parser")
    table = next((candidate for candidate in soup.find_all("table") if _is_medallists_table(candidate)), None)
    if not table:
        return []

    rows = []
    event_is_team = bool(re.search(r"\bteam\b", event.get("event_name", ""), re.I))
    if not event_is_team:
        event_is_team = "-team" in event.get("event_code", "")

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        rank_text = _clean_text(cells[0].get_text(" ", strip=True))
        try:
            rank = int(re.sub(r"\D", "", rank_text))
        except ValueError:
            continue
        if rank is None:
            continue

        npc_cell = cells[1]
        country_node = npc_cell.find("abbr")
        country = _clean_text(country_node.get_text(" ", strip=True)) if country_node else _clean_text(npc_cell.get_text(" ", strip=True))
        country_link = npc_cell.find("a", class_=re.compile(r"npc-flag"))
        country_name = country_link.get("title") if country_link else None
        country_name = _clean_text(country_name) or None

        name_cell = None
        for cell in cells[2:]:
            classes = cell.get("class", [])
            if "Athlete" in classes or "Team" in classes:
                name_cell = cell
                break
        if name_cell is None:
            name_cell = cells[2]

        athlete = name_cell.find(class_=re.compile(r"athlete"))
        name = _clean_text(athlete.get_text(" ", strip=True) if athlete else name_cell.get_text(" ", strip=True))
        if not name:
            continue
        team = event_is_team or "Team" in name_cell.get("class", [])
        medal = _medal_from_cell(cells[3] if len(cells) > 3 else None, rank)

        rows.append({
            "rank": rank,
            "name": name,
            "country": country or None,
            "country_name": country_name,
            "medal": medal,
            "athlete_slug": None if team else _athlete_slug(name_cell),
            "team": team,
        })
    return rows


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=25)
            if response.status_code == 200:
                return response.text
            if response.status_code == 404:
                return None
            print(f"  HTTP {response.status_code} for {url}")
            if response.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt * (8 if response.status_code == 429 else 2))
            else:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def fetch_edition_events(edition):
    html = _get(edition["url"])
    if not html:
        return []
    return parse_sport_page(html, edition)


def fetch_result_page(event):
    html = _get(event["event_url"])
    if not html:
        return []
    return parse_results_page(html, event)


def fetch_sport_page():
    """Fetch all official IPC wheelchair fencing event links for configured editions."""
    events = []
    for edition in PARALYMPIC_EDITIONS:
        events.extend(fetch_edition_events(edition))
        time.sleep(0.5)
    return events


def _category_from_classification(classification):
    disability_class = classification.get("disability_class")
    return f"Senior {disability_class}" if disability_class else "Senior"


def upsert_tournament(event, classification):
    source_id = f"paralympics:{event['edition_id']}:{event['event_code']}"
    row = {
        "source_id": source_id,
        "name": f"{event['edition_name']} — {event['event_name']}",
        "season": event.get("year"),
        "type": "paralympics",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": _category_from_classification(classification),
        "country": None,
        "has_results": True,
        "metadata": {
            "source": "paralympic.org",
            "paralympic_edition_id": event["edition_id"],
            "paralympic_event_code": event["event_code"],
            "edition_name": event["edition_name"],
            "event_name": event["event_name"],
            "event_url": event["event_url"],
            "team": classification["team"],
            "disability_class": classification.get("disability_class"),
            "classification_description": classification.get("classification_description"),
        },
    }
    try:
        result = _db().table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def _match_fencer(name, country):
    try:
        rows = (
            _db().table("fs_fencers")
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


def _best_effort_match_fencer(row):
    if row.get("team"):
        return None
    for country in (row.get("country"), row.get("country_name")):
        if row.get("name") and country:
            fencer_id = _match_fencer(row["name"], country)
            if fencer_id:
                return fencer_id
    return None


def upsert_results(tournament_id, result_rows, event, classification):
    """Delete+reinsert event placements. Returns total written or 0 on partial failure."""
    db_rows = []
    for row in result_rows:
        if row.get("rank") is None or not row.get("name"):
            continue
        fencer_id = _best_effort_match_fencer(row)
        db_rows.append({
            "tournament_id": tournament_id,
            "name": row["name"],
            "nationality": row.get("country"),
            "rank": row["rank"],
            "medal": row.get("medal"),
            "fencer_id": fencer_id,
            "metadata": {
                "source": "paralympic.org",
                "paralympic_edition_id": event["edition_id"],
                "paralympic_event_code": event["event_code"],
                "paralympic_athlete_slug": row.get("athlete_slug"),
                "country_name": row.get("country_name"),
                "team": row.get("team", False),
                "disability_class": classification.get("disability_class"),
                "classification_description": classification.get("classification_description"),
            },
        })

    if not db_rows:
        return 0

    _db().table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i:i + 100]
        try:
            _db().table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    return written if written == len(db_rows) else 0


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_paralympics").start()
    try:
        print(f"Paralympics scraper starting — {datetime.now(timezone.utc).isoformat()}")
        done_keys = set(get_state(SOURCE, "done_event_keys") or [])
        print(f"  {len(done_keys)} events already done")

        written = failed = skipped = 0
        for edition in PARALYMPIC_EDITIONS:
            print(f"\n  Edition: {edition['edition_name']} ({edition['edition_id']})")
            events = fetch_edition_events(edition)
            if not events:
                print("    No wheelchair fencing events found")
                time.sleep(REQUEST_DELAY)
                continue
            print(f"    {len(events)} events found")

            for event in events:
                event_key = f"{event['edition_id']}:{event['event_code']}"
                if event_key in done_keys:
                    skipped += 1
                    continue

                classification = classify_event(event["event_name"])
                if not classification["weapon"] or not classification["gender"]:
                    print(f"    Skipping unclassifiable: {event['event_name']}")
                    skipped += 1
                    continue

                print(f"    {event['event_name']} ({event['event_code']})")
                tournament_id = upsert_tournament(event, classification)
                if not tournament_id:
                    failed += 1
                    time.sleep(REQUEST_DELAY)
                    continue

                result_rows = fetch_result_page(event)
                if not result_rows:
                    print("      No medal placements found")
                    failed += 1
                    time.sleep(REQUEST_DELAY)
                    continue

                inserted = upsert_results(tournament_id, result_rows, event, classification)
                if inserted == 0:
                    print("      Insert failed or partial — skipping done mark")
                    failed += 1
                    time.sleep(REQUEST_DELAY)
                    continue

                print(f"      {inserted} placements inserted")
                done_keys.add(event_key)
                set_state(SOURCE, "done_event_keys", list(done_keys))
                written += 1
                time.sleep(REQUEST_DELAY)

            time.sleep(REQUEST_DELAY)

        set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"\nDone — written={written}, skipped={skipped}, failed={failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

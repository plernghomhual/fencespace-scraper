import os
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from fed_rankings_common import build_ranking_row, write_rankings
from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

OPHARDT_BASE = "https://iwas.ophardt.online"
PARAFENCING_BASE = "https://parafencing.org"
SOURCE = "iwas"
REQUEST_DELAY = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Cookie": "cookie_consent=2",
}

WEAPON_MAP = {
    "epee": "Epee", "épée": "Epee",
    "foil": "Foil", "fleuret": "Foil",
    "sabre": "Sabre", "saber": "Sabre",
}


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
            print(f"  HTTP {r.status_code} for {url}")
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt+1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def parse_ranking_overview(html):
    """Parse IWAS rankings matrix page. Returns list of {id, weapon, gender, category}."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    # Header row: th[0]=empty, th[1..N]="Epee female", "Epee male", etc.
    header_cells = rows[0].find_all(["th", "td"])
    col_meta = []  # (weapon, gender) per column index (0-based, skipping first cell)
    for cell in header_cells[1:]:
        text = cell.get_text(strip=True).lower()
        weapon = None
        for raw, can in WEAPON_MAP.items():
            if raw in text:
                weapon = can
                break
        gender = None
        if "female" in text or "women" in text:
            gender = "Women"
        elif "male" in text or "men" in text:
            gender = "Men"
        col_meta.append((weapon, gender))

    results = []
    for tr in rows[1:]:
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        category = cells[0].get_text(strip=True)
        for i, cell in enumerate(cells[1:]):
            link = cell.find("a", href=re.compile(r"/show/\d+"))
            if not link:
                continue
            m = re.search(r"/show/(\d+)", link["href"])
            if not m:
                continue
            ranking_id = int(m.group(1))
            weapon, gender = col_meta[i] if i < len(col_meta) else (None, None)
            if not weapon or not gender:
                continue
            results.append({
                "id": ranking_id,
                "weapon": weapon,
                "gender": gender,
                "category": category,
            })
    return results


def parse_ranking_page(html):
    """Parse /show/{id} detail page. Returns list of {rank, name, country, points}."""
    soup = BeautifulSoup(html, "html.parser")
    card = soup.find("div", class_="card-body")
    if not card:
        return []
    table = card.find("table", class_="table-striped")
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        try:
            rank = int(cells[0])
        except ValueError:
            continue  # header row
        points_raw = cells[1] if len(cells) > 1 else None
        name = cells[2] if len(cells) > 2 else None
        country = cells[3] if len(cells) > 3 else None
        try:
            points = float(points_raw) if points_raw else None
        except ValueError:
            points = None
        if not name:
            continue
        rows.append({"rank": rank, "name": name, "country": country, "points": points})
    return rows


def parse_event_label(label):
    """Parse event header label into (weapon, gender, category).

    Examples:
        "Epee male Senior Individual A" → ("Epee", "Men", "Senior A")
        "Foil female U23 Individual B"  → ("Foil", "Women", "U23 B")
    """
    label_lower = label.lower()
    weapon = None
    for raw, can in WEAPON_MAP.items():
        if raw in label_lower:
            weapon = can
            break
    gender = None
    if "female" in label_lower or "women" in label_lower:
        gender = "Women"
    elif "male" in label_lower or "men" in label_lower:
        gender = "Men"
    # Age group
    age = None
    for a in ("senior", "u23", "u17"):
        if a in label_lower:
            age = a.upper() if a.startswith("u") else a.capitalize()
            break
    # Wheelchair class: last word if a/b/c
    words = label_lower.split()
    cls = words[-1].upper() if words and words[-1] in ("a", "b", "c") else None
    category = f"{age} {cls}".strip() if age and cls else (cls or age)
    return weapon, gender, category


def parse_results_page(html):
    """Parse /en/search/results/{id} page.

    Returns list of event dicts: {weapon, gender, category, rows}
    where rows = [{rank, name, country, club}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
        label = heading.get_text(strip=True)
        weapon, gender, category = parse_event_label(label)
        if not weapon or not gender or not category:
            continue
        table = heading.find_next("table")
        if not table or "table-striped" not in table.get("class", []):
            continue
        result_rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) < 4:
                continue
            try:
                rank = int(cells[0])
            except ValueError:
                continue  # header
            # Columns: Rank | Status | Round | Name | YOB | Gender | Class | Nation | Club
            name = cells[3] if len(cells) > 3 else None
            country = cells[7] if len(cells) > 7 else None
            club = cells[8] if len(cells) > 8 else None
            if not name:
                continue
            result_rows.append({
                "rank": rank,
                "name": name,
                "country": country or "",
                "club": club or None,
            })
        if result_rows:
            events.append({
                "weapon": weapon,
                "gender": gender,
                "category": category,
                "rows": result_rows,
            })
    return events


def discover_result_ids():
    """Scrape parafencing.org historic results page for IWAS result IDs."""
    html = _get(f"{PARAFENCING_BASE}/results-and-rankings/historic-results/")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    result_ids = []
    for a in soup.find_all("a", href=re.compile(r"iwas\.ophardt\.online/en/search/results/\d+")):
        m = re.search(r"/results/(\d+)", a["href"])
        if m:
            result_ids.append(int(m.group(1)))
    return sorted(set(result_ids))


def scrape_rankings(season):
    """Scrape all IWAS ranking categories → fs_national_fed_rankings."""
    html = _get(f"{OPHARDT_BASE}/en/search/rankings/1")
    if not html:
        print("  Rankings overview fetch failed")
        return 0
    entries = parse_ranking_overview(html)
    print(f"  Found {len(entries)} ranking categories")
    total = 0
    for entry in entries:
        detail_html = _get(f"{OPHARDT_BASE}/en/search/rankings/show/{entry['id']}")
        if not detail_html:
            continue
        raw_rows = parse_ranking_page(detail_html)
        if not raw_rows:
            continue
        ranking_rows = [
            build_ranking_row(
                source=SOURCE,
                season=season,
                weapon=entry["weapon"],
                gender=entry["gender"],
                category=entry["category"],
                rank=r["rank"],
                name=r["name"],
                country=r["country"],
                points=r["points"],
            )
            for r in raw_rows
        ]
        n = write_rankings(ranking_rows, SOURCE, season)
        print(f"  {entry['weapon']} {entry['gender']} {entry['category']}: {n} rows")
        total += n
        time.sleep(REQUEST_DELAY)
    return total


def upsert_tournament(result_id, competition_name, weapon, gender, category, season):
    source_id = f"iwas:{result_id}:{weapon.lower()}:{gender.lower()}:{category.lower().replace(' ', '_')}"
    row = {
        "source_id": source_id,
        "name": f"{competition_name} — {gender}'s {weapon} {category}",
        "season": season,
        "type": "wheelchair_championship",
        "weapon": weapon,
        "gender": gender,
        "category": category,
        "country": None,
        "has_results": True,
        "metadata": {
            "iwas_result_id": result_id,
            "competition_name": competition_name,
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def upsert_event_results(tournament_id, result_rows):
    """Delete+reinsert. Returns total written or 0 on partial failure."""
    db_rows = [
        {
            "tournament_id": tournament_id,
            "name": r["name"],
            "nationality": r["country"],
            "rank": r["rank"],
            "medal": None,
            "fencer_id": None,
            "metadata": {"club": r.get("club")},
        }
        for r in result_rows
    ]
    if not db_rows:
        return 0
    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i:i + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Insert batch failed: {exc}")
    return written if written == len(db_rows) else 0


def scrape_results(done_result_ids):
    """Scrape IWAS competition results → fs_tournaments + fs_results."""
    result_ids = discover_result_ids()
    print(f"  Found {len(result_ids)} result IDs from parafencing.org")
    total = 0
    new_done = set()
    for result_id in result_ids:
        if result_id in done_result_ids:
            continue
        html = _get(f"{OPHARDT_BASE}/en/search/results/{result_id}")
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        competition_name = h1.get_text(strip=True) if h1 else f"IWAS Competition {result_id}"
        m_year = re.search(r"\b(20\d{2})\b", competition_name)
        season = m_year.group(1) if m_year else str(datetime.now(timezone.utc).year)
        events = parse_results_page(html)
        result_written = 0
        for event in events:
            t_id = upsert_tournament(
                result_id, competition_name,
                event["weapon"], event["gender"], event["category"], season,
            )
            if not t_id:
                continue
            n = upsert_event_results(t_id, event["rows"])
            if n > 0:
                result_written += n
        if result_written > 0:
            new_done.add(result_id)
        total += result_written
        print(f"  Result {result_id} ({competition_name}): {result_written} fencer-placements")
        time.sleep(REQUEST_DELAY)
    return total, new_done


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_iwas").start()
    try:
        season = str(datetime.now(timezone.utc).year)
        print(f"IWAS scraper starting — {datetime.now(timezone.utc).isoformat()}")

        print("\n--- Rankings ---")
        rankings_written = scrape_rankings(season)

        print("\n--- Competition Results ---")
        done_result_ids = set(get_state(SOURCE, "done_result_ids") or [])
        results_written, new_done = scrape_results(done_result_ids)
        done_result_ids.update(new_done)
        set_state(SOURCE, "done_result_ids", list(done_result_ids))

        total_written = rankings_written + results_written
        set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
        run_log.complete(written=total_written,
                         metadata={"rankings": rankings_written, "results": results_written})
        print(f"\nDone — rankings={rankings_written}, results={results_written}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

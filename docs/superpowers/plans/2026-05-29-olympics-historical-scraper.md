# Olympics Historical Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scrape all Olympic fencing results (every Games, 1896–present) from olympedia.org into `fs_tournaments` + `fs_results`.

**Architecture:** New scraper `scrape_olympics.py` discovers Olympic fencing events from olympedia.org, writes one `fs_tournaments` row per event (e.g., "Men's Foil Individual 1996"), writes one `fs_results` row per fencer per event. Uses `scraper_state.py` for incremental progress so the first run fills history and later runs check only recent/future Games. Fencer matching against `fs_fencers` by name+country (best-effort; unmatched rows still inserted with `fencer_id=NULL`).

**Tech Stack:** Python 3.11, requests, BeautifulSoup4, supabase-py, existing `run_logger.py`, `scraper_state.py`

---

## File Map

| Action | Path |
|--------|------|
| Create | `scrape_olympics.py` |
| Create | `tests/test_scrape_olympics.py` |
| Modify | `.github/workflows/scraper.yml` — add Olympics step |

---

### Task 1: Probe olympedia.org structure

Olympedia has no public API — we scrape HTML. Run this probe script manually once to confirm URLs before building.

**Files:**
- No file created — run in a scratch script and record findings in comments at top of `scrape_olympics.py`

- [ ] **Step 1: Run probe**

```python
# probe_olympedia.py — run once manually, then delete
import requests
from bs4 import BeautifulSoup

BASE = "https://www.olympedia.org"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)"}

# 1. Fencing sport page — lists all events by edition
r = requests.get(f"{BASE}/sport_codes/FEN", headers=HEADERS, timeout=15)
soup = BeautifulSoup(r.text, "html.parser")
# Look for links to edition/event pages
links = [(a.text.strip(), a["href"]) for a in soup.find_all("a", href=True) if "/results/" in a["href"] or "/editions/" in a["href"]]
for text, href in links[:20]:
    print(text, href)
```

Run: `python probe_olympedia.py`

Expected: URLs like `/results/12345` with event names like "Men's Épée Individual".

- [ ] **Step 2: Probe one result page**

```python
# Add to probe_olympedia.py
result_id = "YOUR_RESULT_ID_FROM_ABOVE"
r2 = requests.get(f"{BASE}/results/{result_id}", headers=HEADERS, timeout=15)
soup2 = BeautifulSoup(r2.text, "html.parser")
# Find the results table
table = soup2.find("table")
if table:
    for row in table.find_all("tr")[:5]:
        print([td.text.strip() for td in row.find_all(["td","th"])])
```

Expected: Rows with rank/placement, athlete name, country, medal columns.

- [ ] **Step 3: Document findings**

Record at top of `scrape_olympics.py` as constants:
```python
# olympedia.org URL structure (verified YYYY-MM-DD):
# Sport page:   GET /sport_codes/FEN  -> table of events by edition
# Result page:  GET /results/{result_id}  -> table: rank | name | country | medal
# Athlete page: GET /athletes/{athlete_id} -> bio + DOB
OLYMPEDIA_BASE = "https://www.olympedia.org"
SPORT_CODE = "FEN"
```

---

### Task 2: Write failing tests for HTML parsers

**Files:**
- Create: `tests/test_scrape_olympics.py`

- [ ] **Step 1: Create test file with fixture HTML**

```python
# tests/test_scrape_olympics.py
import pytest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Minimal fixture HTML — matches real olympedia structure (update after probe)
SPORT_PAGE_HTML = """
<html><body>
<table>
  <tr><th>Event</th><th>Edition</th></tr>
  <tr>
    <td><a href="/results/11111">Men's Épée Individual</a></td>
    <td><a href="/editions/50">Atlanta 1996</a></td>
  </tr>
  <tr>
    <td><a href="/results/22222">Women's Foil Individual</a></td>
    <td><a href="/editions/50">Atlanta 1996</a></td>
  </tr>
</table>
</body></html>
"""

RESULTS_PAGE_HTML = """
<html><body>
<h1>Men's Épée Individual — Atlanta 1996</h1>
<table class="table">
  <tr><th>Rank</th><th>Athlete</th><th>Country</th><th>Medal</th></tr>
  <tr><td>1</td><td><a href="/athletes/99">Éric Srecki</a></td><td>FRA</td><td>Gold</td></tr>
  <tr><td>2</td><td><a href="/athletes/88">Ehren Hymmen</a></td><td>GER</td><td>Silver</td></tr>
  <tr><td>3</td><td><a href="/athletes/77">Kaido Kaaberma</a></td><td>EST</td><td>Bronze</td></tr>
  <tr><td>4</td><td><a href="/athletes/66">Ivan Trevejo</a></td><td>CUB</td><td></td></tr>
</table>
</body></html>
"""


def test_parse_sport_page_returns_event_list():
    from scrape_olympics import parse_sport_page
    events = parse_sport_page(SPORT_PAGE_HTML)
    assert len(events) == 2
    assert events[0]["result_id"] == "11111"
    assert events[0]["event_name"] == "Men's Épée Individual"
    assert events[0]["edition_name"] == "Atlanta 1996"
    assert events[0]["edition_id"] == "50"


def test_parse_results_page_returns_placements():
    from scrape_olympics import parse_results_page
    rows = parse_results_page(RESULTS_PAGE_HTML, result_id="11111")
    assert len(rows) == 4
    gold = rows[0]
    assert gold["rank"] == 1
    assert gold["name"] == "Éric Srecki"
    assert gold["country"] == "FRA"
    assert gold["medal"] == "Gold"
    assert rows[3]["medal"] is None


def test_parse_sport_page_skips_non_fencing():
    from scrape_olympics import parse_sport_page
    html = "<html><body><table><tr><td>No links here</td></tr></table></body></html>"
    events = parse_sport_page(html)
    assert events == []


def test_classify_event_weapon_gender():
    from scrape_olympics import classify_event
    assert classify_event("Men's Épée Individual") == {"weapon": "Epee", "gender": "Men", "team": False}
    assert classify_event("Women's Foil Team") == {"weapon": "Foil", "gender": "Women", "team": True}
    assert classify_event("Men's Sabre Individual") == {"weapon": "Sabre", "gender": "Men", "team": False}
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/plernghomhual/Documents/FenceSpace-Scraper/fencespace-scraper
python -m pytest tests/test_scrape_olympics.py -v 2>&1 | head -40
```

Expected: `ImportError: cannot import name 'parse_sport_page' from 'scrape_olympics'` (module doesn't exist yet).

---

### Task 3: Implement `scrape_olympics.py` core parsers

**Files:**
- Create: `scrape_olympics.py`

- [ ] **Step 1: Write the module skeleton + parsers**

```python
# scrape_olympics.py
import os
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from supabase import create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# olympedia.org URL structure (verified 2026-05-29):
# Sport page:   GET /sport_codes/FEN  -> table rows link to result pages
# Result page:  GET /results/{result_id} -> table: rank | athlete | country | medal
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
    (re.compile(r"\bwomen\b|\bwomen's\b", re.I), "Women"),
    (re.compile(r"\bmen\b|\bmen's\b", re.I), "Men"),
]


def classify_event(event_name: str) -> dict:
    weapon = next((w for pat, w in WEAPON_PATTERNS if pat.search(event_name)), None)
    gender = next((g for pat, g in GENDER_PATTERNS if pat.search(event_name)), None)
    team = bool(re.search(r"\bteam\b", event_name, re.I))
    return {"weapon": weapon, "gender": gender, "team": team}


def parse_sport_page(html: str) -> list[dict]:
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


def parse_results_page(html: str, result_id: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    rows = []
    for tr in table.find_all("tr")[1:]:  # skip header
        cells = [td.text.strip() for td in tr.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        try:
            rank = int(re.sub(r"\D", "", cells[0])) if cells[0] else None
        except ValueError:
            rank = None
        athlete_td = tr.find_all(["td", "th"])[1]
        athlete_link = athlete_td.find("a", href=re.compile(r"/athletes/\d+"))
        athlete_id = re.search(r"/athletes/(\d+)", athlete_link["href"]).group(1) if athlete_link else None
        name = athlete_td.text.strip()
        country = cells[2] if len(cells) > 2 else None
        medal_raw = cells[3].strip() if len(cells) > 3 else ""
        medal = medal_raw if medal_raw in {"Gold", "Silver", "Bronze"} else None
        rows.append({
            "rank": rank,
            "name": name,
            "country": country,
            "medal": medal,
            "athlete_id": athlete_id,
        })
    return rows
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_scrape_olympics.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scrape_olympics.py tests/test_scrape_olympics.py
git commit -m "feat: olympedia parsers + tests"
```

---

### Task 4: Implement fetch + DB write logic

**Files:**
- Modify: `scrape_olympics.py` (add `fetch_sport_page`, `fetch_result_page`, `upsert_tournament`, `upsert_results`, `main`)

- [ ] **Step 1: Add fetch helpers**

```python
# Add to scrape_olympics.py

def _get(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt+1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def fetch_sport_page() -> list[dict]:
    html = _get(f"{OLYMPEDIA_BASE}/sport_codes/FEN")
    if not html:
        raise RuntimeError("Could not fetch olympedia sport page")
    return parse_sport_page(html)


def fetch_result_page(result_id: str) -> list[dict]:
    html = _get(f"{OLYMPEDIA_BASE}/results/{result_id}")
    if not html:
        return []
    return parse_results_page(html, result_id)
```

- [ ] **Step 2: Add DB write helpers**

```python
# Add to scrape_olympics.py

def _extract_year(edition_name: str) -> str | None:
    m = re.search(r"\b(\d{4})\b", edition_name)
    return m.group(1) if m else None


def upsert_tournament(event: dict, classification: dict) -> str | None:
    year = _extract_year(event["edition_name"])
    source_id = f"olympedia:{event['edition_id']}:{event['result_id']}"
    team_suffix = " (Team)" if classification["team"] else " (Individual)"
    name = f"{event['edition_name']} — {event['event_name']}"
    row = {
        "source_id": source_id,
        "name": name,
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
        existing = supabase.table("fs_tournaments").select("id").eq("source_id", source_id).limit(1).execute().data
        if existing:
            return existing[0]["id"]
        result = supabase.table("fs_tournaments").insert(row).execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def _match_fencer(name: str, country: str) -> str | None:
    try:
        rows = supabase.table("fs_fencers").select("id").ilike("name", name).eq("country", country).limit(1).execute().data
        return rows[0]["id"] if rows else None
    except Exception:
        return None


def upsert_results(tournament_id: str, result_rows: list[dict]) -> int:
    db_rows = []
    for r in result_rows:
        fencer_id = _match_fencer(r["name"], r["country"]) if r["name"] and r["country"] else None
        db_rows.append({
            "tournament_id": tournament_id,
            "name": r["name"],
            "country": r["country"],
            "rank": r["rank"],
            "placement": r["rank"],
            "medal": r["medal"],
            "fencer_id": fencer_id,
            "metadata": {"olympedia_athlete_id": r.get("athlete_id")},
        })
    if not db_rows:
        return 0
    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    for i in range(0, len(db_rows), 100):
        supabase.table("fs_results").insert(db_rows[i:i+100]).execute()
    return len(db_rows)
```

- [ ] **Step 3: Add main loop**

```python
# Add to scrape_olympics.py

def main():
    run_log = ScraperRunLogger("scrape_olympics").start()
    print(f"Olympics scraper starting — {datetime.now(timezone.utc).isoformat()}")

    done_ids: set = set(get_state(SOURCE, "done_result_ids") or [])
    print(f"  {len(done_ids)} events already done")

    events = fetch_sport_page()
    print(f"  Found {len(events)} fencing events on olympedia")

    written = failed = skipped = 0
    for event in events:
        result_id = event["result_id"]
        if result_id in done_ids:
            skipped += 1
            continue

        classification = classify_event(event["event_name"])
        if not classification["weapon"] or not classification["gender"]:
            print(f"  Skipping unclassifiable event: {event['event_name']}")
            skipped += 1
            continue

        print(f"  Scraping {event['edition_name']} — {event['event_name']} (result_id={result_id})")
        tournament_id = upsert_tournament(event, classification)
        if not tournament_id:
            failed += 1
            time.sleep(REQUEST_DELAY)
            continue

        result_rows = fetch_result_page(result_id)
        if not result_rows:
            print(f"    No results found")
            failed += 1
            time.sleep(REQUEST_DELAY)
            continue

        n = upsert_results(tournament_id, result_rows)
        print(f"    Inserted {n} results")
        done_ids.add(result_id)
        set_state(SOURCE, "done_result_ids", list(done_ids))
        written += 1
        time.sleep(REQUEST_DELAY)

    run_log.complete(written=written, failed=failed, skipped=skipped)
    print(f"\nDone — written={written}, skipped={skipped}, failed={failed}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add scrape_olympics.py
git commit -m "feat: olympedia fetch + DB write logic"
```

---

### Task 5: Add to GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/scraper.yml`

- [ ] **Step 1: Add step after `scrape_results.py`**

```yaml
      - name: Run Olympics historical scraper
        continue-on-error: true
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python scrape_olympics.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/scraper.yml
git commit -m "ci: add Olympics scraper step"
```

---

### Task 6: Manual first run + verify

- [ ] **Step 1: Run locally against production**

```bash
SUPABASE_URL=<value> SUPABASE_SERVICE_KEY=<value> python scrape_olympics.py
```

Expected output:
```
Olympics scraper starting — ...
  0 events already done
  Found ~200 fencing events on olympedia
  Scraping Atlanta 1996 — Men's Épée Individual (result_id=...)
    Inserted 32 results
  ...
Done — written=X, skipped=0, failed=Y
```

- [ ] **Step 2: Verify in DB**

```sql
SELECT type, COUNT(*) FROM fs_tournaments WHERE type = 'olympics' GROUP BY type;
SELECT COUNT(*) FROM fs_results r JOIN fs_tournaments t ON r.tournament_id = t.id WHERE t.type = 'olympics';
SELECT name, rank, medal FROM fs_results r JOIN fs_tournaments t ON r.tournament_id = t.id WHERE t.name ILIKE '%1996%epee%' ORDER BY rank LIMIT 5;
```

Expected: `olympics` tournaments, results with Gold/Silver/Bronze medals populated.

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "feat: olympedia Olympics historical scraper complete"
```

---

## Self-Review

- Probe step confirms real URL structure before hardcoding ✓
- Tests cover all parsers with real-ish fixture HTML ✓
- Incremental via `done_result_ids` set in `fs_scraper_state` ✓
- Fencer matching is best-effort, never blocks insert ✓
- `source_id` follows project pattern (`source:edition_id:result_id`) ✓
- `REQUEST_DELAY = 2.0` — polite to olympedia ✓
- `continue-on-error: true` in CI matches existing scrapers ✓

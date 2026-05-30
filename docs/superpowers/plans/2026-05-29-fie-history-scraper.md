# FIE Historical Results Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend existing FIE scrapers to cover all historical seasons (back to ~1999) rather than only recent ones, filling `fs_tournaments` + `fs_results` with historical World Cup, World Championship, and Continental Championship data.

**Architecture:** The existing `scraper.py` (fencers) and `scrape_results.py` (results) already work for recent seasons. The gap is that `scraper.py` only scrapes the current season's fencers, and `scrape_results.py` only processes tournaments already in `fs_tournaments`. A new script `scrape_fie_history.py` loops over all seasons (1999–current), calls the FIE competitions API for each, inserts tournaments into `fs_tournaments`, then relies on the existing `scrape_results.py` to fill results on the next run. A separate run of historical fencer rankings is already handled by `scrape_rankings_history.py` (covers 2015–present); this plan extends tournament coverage.

**Tech Stack:** Python 3.11, requests, supabase-py, existing `run_logger.py`, `scraper_state.py`

---

## Background: How FIE data is structured

The existing `scraper.py` shows this FIE competition API pattern:
- `POST https://fie.org/competitions` with JSON body `{"weapon": "S", "gender": "M", "category": "S", "season": "2026", "page": 1}`
- Returns JSON with `competitions` array, each having `id` (fie_id), `name`, `country`, `location`, `startDate`, `endDate`, `weapon`, `gender`, `category`, `type`
- Season format: integer year (2026 = 2025/2026 season)
- FIE has data from season 1999 or 2000 onward

The existing `scraper.py` scrapes only the current season. `scrape_results.py` then fetches results for any tournament in `fs_tournaments` that has `competition_url_id` set but no results yet.

---

## File Map

| Action | Path |
|--------|------|
| Create | `scrape_fie_history.py` |
| Create | `tests/test_scrape_fie_history.py` |
| Modify | `.github/workflows/scraper.yml` — add history step (run once flag) |

---

### Task 1: Probe FIE API for historical seasons

- [ ] **Step 1: Test which seasons FIE has data for**

```python
# probe_fie_seasons.py — run once manually, then delete
import requests, json

BASE = "https://fie.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Content-Type": "application/json",
}

for season in [1999, 2000, 2005, 2010, 2015, 2024, 2025, 2026]:
    try:
        r = requests.post(
            f"{BASE}/competitions",
            headers=HEADERS,
            json={"weapon": "E", "gender": "M", "category": "S", "season": str(season), "page": 1},
            timeout=15
        )
        data = r.json() if r.status_code == 200 else {}
        count = len(data.get("competitions", []))
        print(f"Season {season}: HTTP {r.status_code}, {count} competitions")
    except Exception as e:
        print(f"Season {season}: ERROR {e}")
```

Run: `python probe_fie_seasons.py`

Expected: Seasons before ~2000 return 0 or 404; 2000+ return competitions. Note the earliest working season.

- [ ] **Step 2: Check competition type values**

```python
# Add to probe:
r = requests.post(f"{BASE}/competitions", headers=HEADERS,
    json={"weapon": "E", "gender": "M", "category": "S", "season": "2010", "page": 1}, timeout=15)
comps = r.json().get("competitions", [])[:5]
for c in comps:
    print(c.get("type"), c.get("name"), c.get("id"))
```

Expected: Types like `"WC"` (World Cup), `"WCH"` (World Championship), `"CC"` (Continental Championship), etc.

- [ ] **Step 3: Record findings**

Update `EARLIEST_SEASON` constant in `scrape_fie_history.py` with the earliest working season from the probe.

---

### Task 2: Write failing tests

**Files:**
- Create: `tests/test_scrape_fie_history.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_scrape_fie_history.py
import pytest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

SAMPLE_COMPETITIONS = [
    {
        "id": 12345,
        "name": "Grand Prix Budapest",
        "country": "Hungary",
        "location": "Budapest",
        "startDate": "12-03-2010",
        "endDate": "14-03-2010",
        "weapon": "E",
        "gender": "M",
        "category": "S",
        "type": "WC",
    },
    {
        "id": 12346,
        "name": "World Championships",
        "country": "France",
        "location": "Paris",
        "startDate": "01-07-2010",
        "endDate": "08-07-2010",
        "weapon": "E",
        "gender": "M",
        "category": "S",
        "type": "WCH",
    },
]


def test_competition_to_tournament_row():
    from scrape_fie_history import competition_to_tournament_row
    row = competition_to_tournament_row(SAMPLE_COMPETITIONS[0], season=2010)
    assert row["fie_id"] == 12345
    assert row["name"] == "Grand Prix Budapest"
    assert row["weapon"] == "Epee"
    assert row["gender"] == "Men"
    assert row["category"] == "Senior"
    assert row["start_date"] == "2010-03-12"
    assert row["end_date"] == "2010-03-14"
    assert row["type"] == "WC"
    assert row["season"] == "2010"
    assert row["country"] == "Hungary"
    assert row["location"] == "Budapest"


def test_competition_to_tournament_row_world_championship():
    from scrape_fie_history import competition_to_tournament_row
    row = competition_to_tournament_row(SAMPLE_COMPETITIONS[1], season=2010)
    assert row["type"] == "WCH"
    assert row["name"] == "World Championships"


def test_normalize_fie_date():
    from scrape_fie_history import normalize_fie_date
    assert normalize_fie_date("12-03-2010") == "2010-03-12"
    assert normalize_fie_date("01-07-2010") == "2010-07-01"
    assert normalize_fie_date(None) is None
    assert normalize_fie_date("") is None
    assert normalize_fie_date("bad-date") is None


def test_seasons_to_scrape():
    from scrape_fie_history import seasons_to_scrape
    seasons = seasons_to_scrape(earliest=2000, current=2026)
    assert 2000 in seasons
    assert 2026 in seasons
    assert len(seasons) == 27
    assert seasons == list(range(2000, 2027))
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_scrape_fie_history.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'competition_to_tournament_row' from 'scrape_fie_history'`

---

### Task 3: Implement `scrape_fie_history.py`

**Files:**
- Create: `scrape_fie_history.py`

- [ ] **Step 1: Write core module**

```python
# scrape_fie_history.py
import os
import re
import time
from datetime import datetime, timezone

import requests
from supabase import create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FIE_BASE = "https://fie.org"
SOURCE = "fie_history"
# Update EARLIEST_SEASON after running the probe in Task 1
EARLIEST_SEASON = int(os.environ.get("FIE_HISTORY_EARLIEST_SEASON", "2000"))
REQUEST_DELAY = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Content-Type": "application/json",
}

WEAPON_MAP = {"E": "Epee", "F": "Foil", "S": "Sabre"}
GENDER_MAP = {"M": "Men", "F": "Women"}
CATEGORY_MAP = {"S": "Senior", "J": "Junior", "C": "Cadet", "V": "Veteran"}

WEAPONS = [
    (w, g, c)
    for w in ["E", "F", "S"]
    for g in ["M", "F"]
    for c in ["S", "J", "C", "V"]
]


def normalize_fie_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        parts = date_str.split("-")
        if len(parts) != 3 or len(parts[2]) != 4:
            return None
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
        return None


def seasons_to_scrape(earliest: int, current: int) -> list[int]:
    return list(range(earliest, current + 1))


def competition_to_tournament_row(comp: dict, season: int) -> dict:
    return {
        "fie_id": comp["id"],
        "name": comp.get("name"),
        "season": str(season),
        "country": comp.get("country"),
        "location": comp.get("location"),
        "start_date": normalize_fie_date(comp.get("startDate")),
        "end_date": normalize_fie_date(comp.get("endDate")),
        "weapon": WEAPON_MAP.get(comp.get("weapon", ""), comp.get("weapon")),
        "gender": GENDER_MAP.get(comp.get("gender", ""), comp.get("gender")),
        "category": CATEGORY_MAP.get(comp.get("category", ""), comp.get("category")),
        "type": comp.get("type"),
        "has_results": False,
        "metadata": {"scraped_by": "scrape_fie_history"},
    }


def fetch_competitions(weapon: str, gender: str, category: str, season: int) -> list[dict]:
    results = []
    page = 1
    while True:
        try:
            r = requests.post(
                f"{FIE_BASE}/competitions",
                headers=HEADERS,
                json={"weapon": weapon, "gender": gender, "category": category,
                      "season": str(season), "page": page},
                timeout=15,
            )
            if r.status_code != 200:
                break
            data = r.json()
            comps = data.get("competitions", [])
            if not comps:
                break
            results.extend(comps)
            if len(comps) < 20:
                break
            page += 1
            time.sleep(0.3)
        except Exception as exc:
            print(f"    Fetch failed (season={season} {weapon}/{gender}/{category} page={page}): {exc}")
            break
    return results


def upsert_tournaments(rows: list[dict]) -> int:
    if not rows:
        return 0
    seen = {r["fie_id"]: r for r in rows}
    deduped = list(seen.values())
    for i in range(0, len(deduped), 100):
        try:
            supabase.table("fs_tournaments").upsert(
                deduped[i:i+100], on_conflict="fie_id"
            ).execute()
        except Exception as exc:
            print(f"  Upsert batch failed: {exc}")
    return len(deduped)


def main():
    run_log = ScraperRunLogger("scrape_fie_history").start()
    print(f"FIE history scraper starting — {datetime.now(timezone.utc).isoformat()}")

    current_year = datetime.now(timezone.utc).year
    done_seasons: set = set(get_state(SOURCE, "done_seasons") or [])
    seasons = [s for s in seasons_to_scrape(EARLIEST_SEASON, current_year) if s not in done_seasons]
    print(f"Seasons to scrape: {len(seasons)} (skipping {len(done_seasons)} already done)")

    total_written = total_failed = 0
    for season in seasons:
        season_written = 0
        print(f"\nSeason {season}:")
        for weapon, gender, category in WEAPONS:
            comps = fetch_competitions(weapon, gender, category, season)
            if not comps:
                continue
            rows = [competition_to_tournament_row(c, season) for c in comps]
            n = upsert_tournaments(rows)
            season_written += n
            time.sleep(REQUEST_DELAY)

        print(f"  Season {season}: {season_written} tournaments")
        total_written += season_written
        done_seasons.add(season)
        set_state(SOURCE, "done_seasons", list(done_seasons))

    run_log.complete(written=total_written, failed=total_failed)
    print(f"\nDone — written={total_written}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_scrape_fie_history.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scrape_fie_history.py tests/test_scrape_fie_history.py
git commit -m "feat: FIE historical tournament scraper + tests"
```

---

### Task 4: Add to GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/scraper.yml`

- [ ] **Step 1: Add step — runs only when triggered manually or on first Monday of month**

The history fill is a one-time backfill then minimal incremental work. Add it after `scrape_fie_events.py`:

```yaml
      - name: Scrape FIE historical tournaments
        continue-on-error: true
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python scrape_fie_history.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/scraper.yml
git commit -m "ci: add FIE history scraper step"
```

---

### Task 5: First run + verify

- [ ] **Step 1: Run locally**

```bash
SUPABASE_URL=<value> SUPABASE_SERVICE_KEY=<value> python scrape_fie_history.py
```

Expected output:
```
FIE history scraper starting — ...
Seasons to scrape: 27 (skipping 0 already done)

Season 2000:
  Season 2000: N tournaments
...
Done — written=XXXX
```

- [ ] **Step 2: Verify DB**

```sql
SELECT season, COUNT(*) as tournaments FROM fs_tournaments
WHERE (metadata->>'scraped_by') = 'scrape_fie_history'
GROUP BY season ORDER BY season;
```

Expected: Rows for each season from EARLIEST_SEASON onward.

- [ ] **Step 3: Verify results scraper can pick up new tournaments**

```sql
SELECT COUNT(*) FROM fs_tournaments
WHERE has_results = false AND competition_url_id IS NULL
AND (metadata->>'scraped_by') = 'scrape_fie_history';
```

These will be picked up by `scrape_results.py` on next run (it queries for tournaments without results that have a `competition_url_id`). The URL IDs need to be discovered first by the existing URL-discovery step in `scrape_results.py`.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: FIE history scraper — first run verified"
```

---

## Self-Review

- Probe step confirms actual earliest season before hardcoding ✓
- Uses existing `fie_id` upsert conflict — won't duplicate tournaments already in DB ✓
- Incremental via `done_seasons` set — safe to rerun ✓
- Results are deliberately left to existing `scrape_results.py` — no duplicated logic ✓
- All 24 weapon/gender/category combos covered per season ✓
- `continue-on-error: true` matches existing workflow pattern ✓

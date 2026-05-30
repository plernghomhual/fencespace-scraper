# Tier 2 Scrapers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add NCAA college fencing results, IWAS wheelchair fencing rankings and results, and fix the FIE veteran event `hasResults=0` bug so veteran competitions get their results scraped.

**Architecture:** 2 new scrapers (`scrape_ncaa.py`, `scrape_iwas.py`) plus a targeted fix to `scrape_fie_history.py`. All follow the established pattern: `ScraperRunLogger`, `scraper_state`, `supabase upsert on_conflict`, incremental state via `done_*` sets, `continue-on-error: true` in CI. Confederation championships are already covered by the existing FIE history scraper (all confederation sites are dead; FIE API returns continental championships from 2003+).

**Tech Stack:** Python 3.14, requests, beautifulsoup4, supabase-py, pytest

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `scrape_ncaa.py` | Create | Scrape ncaa.escrimeresults.com 2000–2026 championship standings |
| `tests/test_scrape_ncaa.py` | Create | Unit tests for NCAA HTML parsers |
| `scrape_iwas.py` | Create | Scrape IWAS wheelchair fencing rankings + competition results |
| `tests/test_scrape_iwas.py` | Create | Unit tests for IWAS parsers |
| `scrape_fie_history.py` | Modify | Override `has_results=True` for past veteran events (FIE API has wrong flag) |
| `tests/test_scrape_fie_history.py` | Modify | Add test for veteran override |
| `.github/workflows/scraper.yml` | Modify | Add NCAA + IWAS steps |

---

## Codebase Conventions (read before writing anything)

- Python venv: `.venv/bin/python`, run tests with `.venv/bin/python -m pytest tests/ -v`
- Supabase client: lazy-init pattern (check `SUPABASE_URL`/`SUPABASE_SERVICE_KEY`, import inside `if`)
- Run logging: `run_log = ScraperRunLogger("scrape_X").start()` → `.complete(written, failed, skipped)` or `.error(str(exc))`
- State: `get_state(SOURCE, "key")` / `set_state(SOURCE, "key", value)` — persists incremental progress
- Upsert pattern: `supabase.table("t").upsert(row, on_conflict="col").execute()`
- Existing working scrapers to reference: `scrape_olympics.py` (tournament + results), `scrape_fed_british.py` (fed rankings)
- Run logger import: `from run_logger import ScraperRunLogger`
- State import: `from scraper_state import get_state, set_state`

---

## Task 1: NCAA Championship Scraper

**Source:** `https://ncaa.escrimeresults.com/ncaa{YEAR}.html` (2000–2026, no 2020)  
**Format:** Excel-exported MSO HTML — no useful CSS classes; anchor-based navigation  
**Sections:** `<a name="WS">` Women's Sabre, `WF` Foil, `WE` Epee; `MS` Men's Sabre, `MF` Foil, `ME` Epee  
**Columns per section:** Place | Name | School | V/B | Pct. | TS | TR | Ind.  
**Output:** `fs_tournaments` (one row per year+weapon+gender) + `fs_results` (individual placements)

**Files:**
- Create: `scrape_ncaa.py`
- Create: `tests/test_scrape_ncaa.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scrape_ncaa.py
from scrape_ncaa import parse_section, SECTION_MAP
from bs4 import BeautifulSoup

NCAA_HTML = """
<html><body>
<a name="WS"></a>
<table>
  <tr><th>Place</th><th>Name</th><th>School</th><th>V/B</th><th>Pct.</th><th>TS</th><th>TR</th><th>Ind.</th></tr>
  <tr><td>1.</td><td>Maggie Shealy</td><td>Brandeis</td><td>18/23</td><td>0.783</td><td>109</td><td>74</td><td>+35</td></tr>
  <tr><td>2.</td><td>Alice Smith</td><td>Harvard</td><td>15/23</td><td>0.652</td><td>98</td><td>82</td><td>+16</td></tr>
  <tr><td>T3.</td><td>Carol Jones</td><td>Penn</td><td>14/23</td><td>0.609</td><td>95</td><td>88</td><td>+7</td></tr>
</table>
<a name="ME"></a>
<table>
  <tr><th>Place</th><th>Name</th><th>School</th><th>V/B</th><th>Pct.</th><th>TS</th><th>TR</th><th>Ind.</th></tr>
  <tr><td>1.</td><td>Bob Chen</td><td>Princeton</td><td>20/23</td><td>0.870</td><td>105</td><td>50</td><td>+55</td></tr>
</table>
</body></html>
"""


def test_parse_section_returns_rows():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "WS")
    assert len(rows) == 3


def test_parse_section_fields():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "WS")
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Maggie Shealy"
    assert rows[0]["school"] == "Brandeis"
    assert rows[0]["vb"] == "18/23"
    assert rows[0]["pct"] == "0.783"
    assert rows[0]["ts"] == "109"
    assert rows[0]["tr_val"] == "74"
    assert rows[0]["ind"] == "+35"


def test_parse_section_tied_place():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "WS")
    assert rows[2]["rank"] == 3  # T3. → 3


def test_parse_section_skips_header_row():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "WS")
    assert not any(r["name"].lower() in ("name", "place", "competitor") for r in rows)


def test_parse_section_missing_anchor_returns_empty():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "MF")  # not in HTML
    assert rows == []


def test_parse_section_me():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "ME")
    assert len(rows) == 1
    assert rows[0]["name"] == "Bob Chen"
    assert rows[0]["school"] == "Princeton"


def test_section_map_has_all_six():
    assert set(SECTION_MAP.keys()) == {"WS", "WF", "WE", "MS", "MF", "ME"}
    weapons = {v[0] for v in SECTION_MAP.values()}
    genders = {v[1] for v in SECTION_MAP.values()}
    assert weapons == {"Sabre", "Foil", "Epee"}
    assert genders == {"Women", "Men"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_scrape_ncaa.py -v
```

Expected: `ModuleNotFoundError: No module named 'scrape_ncaa'`

- [ ] **Step 3: Create `scrape_ncaa.py`**

```python
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

BASE_URL = "https://ncaa.escrimeresults.com"
SOURCE = "ncaa"
REQUEST_DELAY = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
}

# No 2020 (COVID cancellation)
CHAMPIONSHIP_YEARS = [y for y in range(2000, 2027) if y != 2020]

# anchor id → (weapon, gender)
SECTION_MAP = {
    "WS": ("Sabre", "Women"),
    "WF": ("Foil", "Women"),
    "WE": ("Epee", "Women"),
    "MS": ("Sabre", "Men"),
    "MF": ("Foil", "Men"),
    "ME": ("Epee", "Men"),
}


def fetch_year(year):
    url = f"{BASE_URL}/ncaa{year}.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        return r.text if r.status_code == 200 else None
    except Exception as exc:
        print(f"  Fetch failed for {year}: {exc}")
        return None


def parse_section(soup, section_code):
    """Find anchor by name/id, return placement rows from next table.

    Returns list of dicts: rank, name, school, vb, pct, ts, tr_val, ind
    """
    anchor = (
        soup.find("a", attrs={"name": section_code})
        or soup.find("a", attrs={"id": section_code})
    )
    if not anchor:
        return []
    table = anchor.find_next("table")
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        place_raw = cells[0].rstrip(".")
        m = re.match(r"^T?(\d+)$", place_raw)
        if not m:
            continue  # header or non-placement row
        rank = int(m.group(1))
        name = cells[1]
        if not name or name.lower() in ("name", "competitor", "fencer"):
            continue
        school = cells[2] if len(cells) > 2 else None
        vb = cells[3] if len(cells) > 3 else None
        pct = cells[4] if len(cells) > 4 else None
        ts = cells[5] if len(cells) > 5 else None
        tr_val = cells[6] if len(cells) > 6 else None
        ind = cells[7] if len(cells) > 7 else None
        rows.append({
            "rank": rank,
            "name": name,
            "school": school,
            "vb": vb,
            "pct": pct,
            "ts": ts,
            "tr_val": tr_val,
            "ind": ind,
        })
    return rows


def upsert_tournament(year, weapon, gender):
    source_id = f"ncaa:{year}:{weapon.lower()}:{gender.lower()}"
    row = {
        "source_id": source_id,
        "name": f"NCAA Championship {year} — {gender}'s {weapon}",
        "season": str(year),
        "type": "ncaa_championship",
        "weapon": weapon,
        "gender": gender,
        "category": "College",
        "country": "USA",
        "has_results": True,
        "metadata": {
            "year": year,
            "source_url": f"{BASE_URL}/ncaa{year}.html",
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {source_id}: {exc}")
        return None


def upsert_results(tournament_id, result_rows):
    """Delete+reinsert individual placements. Returns total written or 0 on partial failure."""
    db_rows = []
    for r in result_rows:
        db_rows.append({
            "tournament_id": tournament_id,
            "name": r["name"],
            "nationality": "USA",
            "rank": r["rank"],
            "medal": None,
            "fencer_id": None,
            "metadata": {
                "school": r["school"],
                "vb": r["vb"],
                "pct": r["pct"],
                "ts": r["ts"],
                "tr": r["tr_val"],
                "ind": r["ind"],
            },
        })
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
    if written < len(db_rows):
        return 0
    return written


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_ncaa").start()
    try:
        print(f"NCAA scraper starting — {datetime.now(timezone.utc).isoformat()}")
        done_years = set(get_state(SOURCE, "done_years") or [])
        written = failed = skipped = 0

        for year in CHAMPIONSHIP_YEARS:
            if year in done_years:
                skipped += 1
                continue
            print(f"\nYear {year}:")
            html = fetch_year(year)
            if not html:
                failed += 1
                continue

            soup = BeautifulSoup(html, "html.parser")
            year_written = 0
            year_failed = 0

            for section_code, (weapon, gender) in SECTION_MAP.items():
                rows = parse_section(soup, section_code)
                if not rows:
                    print(f"  {section_code}: no results found")
                    continue
                t_id = upsert_tournament(year, weapon, gender)
                if not t_id:
                    year_failed += 1
                    continue
                n = upsert_results(t_id, rows)
                if n == 0:
                    year_failed += 1
                    continue
                print(f"  {section_code}: {n} results")
                year_written += n

            failed += year_failed
            written += year_written
            # Only mark done if all 6 sections wrote successfully (or were absent)
            if year_failed == 0 and year_written > 0:
                done_years.add(year)
                set_state(SOURCE, "done_years", list(done_years))
            time.sleep(REQUEST_DELAY)

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"\nDone — written={written}, failed={failed}, skipped={skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_scrape_ncaa.py -v
```

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scrape_ncaa.py tests/test_scrape_ncaa.py
git commit -m "feat: NCAA championship scraper — ncaa.escrimeresults.com 2000-2026"
```

---

## Task 2: IWAS Wheelchair Fencing Scraper

**Source:** `https://iwas.ophardt.online` (cookie: `cookie_consent=2` bypasses consent banner)  
**Rankings:** `/en/search/rankings/1` → matrix → `/show/{ID}` detail pages  
**Results:** `https://parafencing.org/results-and-rankings/historic-results/` → discover IDs → `/en/search/results/{ID}`  
**Rankings output:** `fs_national_fed_rankings` (via `write_rankings` from `fed_rankings_common.py`)  
**Results output:** `fs_tournaments` + `fs_results`  
**Categories:** "Senior A", "Senior B", "Senior C", "U23 A", etc. (A/B/C = wheelchair disability class)

**Files:**
- Create: `scrape_iwas.py`
- Create: `tests/test_scrape_iwas.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scrape_iwas.py
from scrape_iwas import parse_ranking_overview, parse_ranking_page, parse_event_label, parse_results_page
from bs4 import BeautifulSoup

OVERVIEW_HTML = """
<html><body>
<table>
  <tr>
    <th></th>
    <th>Epee female</th>
    <th>Epee male</th>
    <th>Foil female</th>
  </tr>
  <tr>
    <td>Senior A</td>
    <td><a href="/en/search/rankings/show/910">Rankings</a></td>
    <td><a href="/en/search/rankings/show/911">Rankings</a></td>
    <td><a href="/en/search/rankings/show/912">Rankings</a></td>
  </tr>
  <tr>
    <td>Senior B</td>
    <td><a href="/en/search/rankings/show/920">Rankings</a></td>
    <td></td>
    <td></td>
  </tr>
</table>
</body></html>
"""

DETAIL_HTML = """
<html><body>
<div class="card-body">
  <table class="table table-striped">
    <thead>
      <tr><th>Rank</th><th>Points</th><th>Name</th><th>Nation</th><th>YOB</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>196.0</td><td>KIM Jiyeon</td><td>KOR</td><td>1985</td></tr>
      <tr><td>2</td><td>180.5</td><td>SMITH Jane</td><td>GBR</td><td>1990</td></tr>
      <tr><td>3</td><td>150.0</td><td>ZHANG Wei</td><td>CHN</td><td>1992</td></tr>
    </tbody>
  </table>
</div>
</body></html>
"""

# Results page: competition result, each event as a separate table section
RESULTS_HTML = """
<html><body>
<h1>2023 World Para Fencing Championships</h1>
<div>
  <h4>Epee male Senior Individual A</h4>
  <table class="table table-striped">
    <thead>
      <tr><th>Rank</th><th>Status</th><th>Round</th><th>Name</th><th>YOB</th><th>Gender</th><th>&#160;</th><th>Nation</th><th>Club</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>N</td><td></td><td>LAMBERTINI Emanuele</td><td>1999</td><td>M</td><td>A</td><td>ITA</td><td>ASD</td></tr>
      <tr><td>2</td><td>N</td><td></td><td>LEE Taewon</td><td>1990</td><td>M</td><td>A</td><td>KOR</td><td></td></tr>
    </tbody>
  </table>
  <h4>Foil female Senior Individual B</h4>
  <table class="table table-striped">
    <thead>
      <tr><th>Rank</th><th>Status</th><th>Round</th><th>Name</th><th>YOB</th><th>Gender</th><th>&#160;</th><th>Nation</th><th>Club</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>N</td><td></td><td>WANG Fang</td><td>1988</td><td>F</td><td>B</td><td>CHN</td><td></td></tr>
    </tbody>
  </table>
</div>
</body></html>
"""


def test_parse_ranking_overview_returns_entries():
    entries = parse_ranking_overview(OVERVIEW_HTML)
    assert len(entries) == 4  # 3 in Senior A row + 1 in Senior B row


def test_parse_ranking_overview_fields():
    entries = parse_ranking_overview(OVERVIEW_HTML)
    first = entries[0]
    assert first["id"] == 910
    assert first["weapon"] == "Epee"
    assert first["gender"] == "Women"
    assert first["category"] == "Senior A"


def test_parse_ranking_overview_second_weapon():
    entries = parse_ranking_overview(OVERVIEW_HTML)
    assert entries[1]["id"] == 911
    assert entries[1]["weapon"] == "Epee"
    assert entries[1]["gender"] == "Men"
    assert entries[1]["category"] == "Senior A"


def test_parse_ranking_overview_skips_empty_cells():
    entries = parse_ranking_overview(OVERVIEW_HTML)
    # Senior B only has Epee female (910+10=920), cells 2 and 3 are empty
    senior_b = [e for e in entries if e["category"] == "Senior B"]
    assert len(senior_b) == 1
    assert senior_b[0]["id"] == 920


def test_parse_ranking_page_returns_rows():
    rows = parse_ranking_page(DETAIL_HTML)
    assert len(rows) == 3


def test_parse_ranking_page_fields():
    rows = parse_ranking_page(DETAIL_HTML)
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "KIM Jiyeon"
    assert rows[0]["country"] == "KOR"
    assert rows[0]["points"] == 196.0


def test_parse_ranking_page_empty_returns_empty():
    rows = parse_ranking_page("<html><body></body></html>")
    assert rows == []


def test_parse_event_label_epee_male_senior_a():
    weapon, gender, category = parse_event_label("Epee male Senior Individual A")
    assert weapon == "Epee"
    assert gender == "Men"
    assert category == "Senior A"


def test_parse_event_label_foil_female_senior_b():
    weapon, gender, category = parse_event_label("Foil female Senior Individual B")
    assert weapon == "Foil"
    assert gender == "Women"
    assert category == "Senior B"


def test_parse_event_label_sabre_male_u23_c():
    weapon, gender, category = parse_event_label("Sabre male U23 Individual C")
    assert weapon == "Sabre"
    assert gender == "Men"
    assert category == "U23 C"


def test_parse_results_page_returns_events():
    events = parse_results_page(RESULTS_HTML, competition_name="2023 World Para Fencing Championships")
    assert len(events) == 2


def test_parse_results_page_event_fields():
    events = parse_results_page(RESULTS_HTML, competition_name="2023 World Para Fencing Championships")
    e = events[0]
    assert e["weapon"] == "Epee"
    assert e["gender"] == "Men"
    assert e["category"] == "Senior A"
    assert len(e["rows"]) == 2
    assert e["rows"][0]["rank"] == 1
    assert e["rows"][0]["name"] == "LAMBERTINI Emanuele"
    assert e["rows"][0]["country"] == "ITA"


def test_parse_results_page_second_event():
    events = parse_results_page(RESULTS_HTML, competition_name="2023 World Para Fencing Championships")
    e = events[1]
    assert e["weapon"] == "Foil"
    assert e["gender"] == "Women"
    assert e["category"] == "Senior B"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_scrape_iwas.py -v
```

Expected: `ModuleNotFoundError: No module named 'scrape_iwas'`

- [ ] **Step 3: Create `scrape_iwas.py`**

```python
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

    Examples: "Epee male Senior Individual A" → ("Epee", "Men", "Senior A")
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


def parse_results_page(html, competition_name=""):
    """Parse /en/search/results/{id} page.

    Returns list of event dicts: {weapon, gender, category, rows}
    where rows = [{rank, name, country, club}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    # Each event section: a heading (h4/h3/h2) followed by a table.table-striped
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
    """Scrape all IWAS ranking categories and write to fs_national_fed_rankings."""
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
    """Scrape IWAS competition results pages and write to fs_tournaments + fs_results."""
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
        # Extract competition name from page h1
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        competition_name = h1.get_text(strip=True) if h1 else f"IWAS Competition {result_id}"
        # Extract year from name for season
        m_year = re.search(r"\b(20\d{2})\b", competition_name)
        season = m_year.group(1) if m_year else str(datetime.now(timezone.utc).year)
        events = parse_results_page(html, competition_name)
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

        # Rankings
        print("\n--- Rankings ---")
        rankings_written = scrape_rankings(season)

        # Competition results
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_scrape_iwas.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add scrape_iwas.py tests/test_scrape_iwas.py
git commit -m "feat: IWAS wheelchair fencing scraper — rankings and competition results"
```

---

## Task 3: Fix Veteran `hasResults=0` in FIE History Scraper

**Problem:** FIE API sets `hasResults=0` for all veteran events. This causes `fs_tournaments` rows for veteran events to have `has_results=False`, which prevents any downstream result-fetching for those events.

**Fix:** In `competition_to_tournament_row`, override `has_results=True` for past veteran events (those with an `endDate`). FIE API has a known incorrect flag for veteran events.

**Files:**
- Modify: `scrape_fie_history.py` line 86
- Modify: `tests/test_scrape_fie_history.py`

- [ ] **Step 1: Write failing test**

Open `tests/test_scrape_fie_history.py` and add this test at the bottom:

```python
def test_veteran_has_results_override():
    """FIE API wrongly sets hasResults=0 for veteran events; we override for past events."""
    from scrape_fie_history import competition_to_tournament_row
    comp = {
        "competitionId": 9999,
        "name": "Championnats du Monde Vétérans",
        "country": "FRA",
        "location": "Paris",
        "startDate": "01-03-2024",
        "endDate": "03-03-2024",
        "weapon": "epee",
        "gender": "men",
        "category": "veteran",
        "type": "individual",
        "hasResults": 0,
        "season": 2024,
    }
    row = competition_to_tournament_row(comp, 2024)
    assert row["has_results"] is True, (
        "Veteran past events must have has_results=True regardless of FIE hasResults flag"
    )


def test_non_veteran_zero_results_stays_false():
    """Non-veteran events with hasResults=0 should remain has_results=False."""
    from scrape_fie_history import competition_to_tournament_row
    comp = {
        "competitionId": 8888,
        "name": "Grand Prix Paris",
        "country": "FRA",
        "location": "Paris",
        "startDate": "01-03-2024",
        "endDate": "03-03-2024",
        "weapon": "foil",
        "gender": "women",
        "category": "senior",
        "type": "individual",
        "hasResults": 0,
        "season": 2024,
    }
    row = competition_to_tournament_row(comp, 2024)
    assert row["has_results"] is False


def test_veteran_future_event_no_end_date_stays_false():
    """Veteran events without endDate (future/unknown) should not be overridden."""
    from scrape_fie_history import competition_to_tournament_row
    comp = {
        "competitionId": 7777,
        "name": "Championnats du Monde Vétérans",
        "country": "FRA",
        "location": "Paris",
        "startDate": "01-03-2025",
        "endDate": "",
        "weapon": "sabre",
        "gender": "women",
        "category": "veteran",
        "type": "individual",
        "hasResults": 0,
        "season": 2025,
    }
    row = competition_to_tournament_row(comp, 2025)
    assert row["has_results"] is False
```

- [ ] **Step 2: Run tests to verify the new ones fail**

```bash
.venv/bin/python -m pytest tests/test_scrape_fie_history.py -v
```

Expected: `test_veteran_has_results_override` FAIL, existing tests PASS

- [ ] **Step 3: Apply the fix to `scrape_fie_history.py`**

In `scrape_fie_history.py`, find line 86 (inside `competition_to_tournament_row`):

```python
        "has_results": bool(comp.get("hasResults", 0)),
```

Replace with:

```python
        # FIE API incorrectly reports hasResults=0 for all veteran events.
        # Override for past events (endDate present) so results scraper attempts them.
        "has_results": bool(comp.get("hasResults", 0)) or (
            CATEGORY_MAP.get(comp.get("category", "")) == "Veteran"
            and bool(comp.get("endDate"))
        ),
```

- [ ] **Step 4: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: all tests PASS (including the 3 new veteran tests)

- [ ] **Step 5: Commit**

```bash
git add scrape_fie_history.py tests/test_scrape_fie_history.py
git commit -m "fix: override has_results=True for past FIE veteran events (API has wrong flag)"
```

---

## Task 4: CI Integration

**Files:**
- Modify: `.github/workflows/scraper.yml`

- [ ] **Step 1: Read the current CI file to find the insertion point**

```bash
grep -n "continue-on-error\|run: python scrape_" .github/workflows/scraper.yml | tail -20
```

Expected: shows the last existing scraper steps (should end around the canada scraper step).

- [ ] **Step 2: Add NCAA and IWAS steps to `scraper.yml`**

Find the last federation scraper step in `.github/workflows/scraper.yml` (the Canada step):

```yaml
    - name: Scrape CFF Canada rankings
      continue-on-error: true
      env:
        SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
        SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
      run: python scrape_fed_canada.py
```

Immediately after it, add:

```yaml
    - name: Scrape NCAA championship results
      continue-on-error: true
      env:
        SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
        SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
      run: python scrape_ncaa.py

    - name: Scrape IWAS wheelchair fencing rankings and results
      continue-on-error: true
      env:
        SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
        SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
      run: python scrape_iwas.py
```

- [ ] **Step 3: Verify full test suite still passes**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: all tests PASS (count will be higher than before, including new NCAA and IWAS tests)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/scraper.yml
git commit -m "ci: add NCAA and IWAS scraper steps"
```

---

## Self-Review Checklist

**Spec coverage:**
- NCAA championship results (2000–2026) → Task 1 ✓
- IWAS wheelchair rankings → Task 2 (`scrape_rankings`) ✓
- IWAS wheelchair competition results → Task 2 (`scrape_results`) ✓
- Veteran `hasResults=0` fix → Task 3 ✓
- CI integration → Task 4 ✓
- Confederation championships → not needed (FIE API covers 2003+; all confederation sites dead)

**Placeholder scan:** No TBDs, no "add validation" notes, no forward references to undefined functions. All code complete.

**Type consistency:**
- `parse_ranking_overview` returns `list[dict]` with keys `id, weapon, gender, category` — used in `scrape_rankings` loop ✓
- `parse_ranking_page` returns `list[dict]` with keys `rank, name, country, points` — used in `scrape_rankings` ✓
- `parse_event_label` returns `(weapon, gender, category)` — used in `parse_results_page` and `scrape_results` ✓
- `parse_results_page` returns `list[dict]` with keys `weapon, gender, category, rows` — used in `scrape_results` ✓
- `upsert_event_results` takes `result_rows` each with `name, country, rank, club` — matches `parse_results_page` output ✓
- SECTION_MAP used in `parse_section` (Task 1) ✓

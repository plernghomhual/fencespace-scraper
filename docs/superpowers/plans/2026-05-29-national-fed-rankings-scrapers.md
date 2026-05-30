# National Federation Rankings Scrapers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scrape domestic rankings from 5 national fencing federations — British Fencing, FFF (France), DFB (Germany), FIS (Italy), CFF (Canada) — into a new `fs_national_fed_rankings` table, with best-effort linking to existing `fs_fencers` rows.

**Architecture:** New DB table `fs_national_fed_rankings` (one row per fencer per fed/season/weapon/gender/category/rank). One scraper file per federation (`scrape_fed_*.py`) sharing a common `fed_rankings_common.py` helper. Each scraper writes to the same table via the common writer. A new CI step calls all 5. Each federation's site has a different format — each scraper owns its own parser. All parsers have failing tests before implementation.

**Tech Stack:** Python 3.11, requests, BeautifulSoup4, supabase-py, existing `run_logger.py`, `scraper_state.py`

---

## File Map

| Action | Path |
|--------|------|
| Migrate | `supabase/migrations/20260529_national_fed_rankings.sql` |
| Create | `fed_rankings_common.py` |
| Create | `scrape_fed_british.py` |
| Create | `scrape_fed_france.py` |
| Create | `scrape_fed_germany.py` |
| Create | `scrape_fed_italy.py` |
| Create | `scrape_fed_canada.py` |
| Create | `tests/test_fed_rankings_common.py` |
| Create | `tests/test_fed_british.py` |
| Create | `tests/test_fed_france.py` |
| Create | `tests/test_fed_germany.py` |
| Create | `tests/test_fed_italy.py` |
| Create | `tests/test_fed_canada.py` |
| Modify | `.github/workflows/scraper.yml` |

---

### Task 1: DB migration — create `fs_national_fed_rankings`

**Files:**
- Create: `supabase/migrations/20260529_national_fed_rankings.sql`

- [ ] **Step 1: Write migration**

```sql
-- supabase/migrations/20260529_national_fed_rankings.sql

CREATE TABLE IF NOT EXISTS fs_national_fed_rankings (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source      text NOT NULL,
    season      text NOT NULL,
    weapon      text NOT NULL,
    gender      text NOT NULL,
    category    text NOT NULL,
    rank        integer NOT NULL,
    name        text,
    country     text,
    club        text,
    points      numeric,
    fencer_id   uuid REFERENCES fs_fencers(id),
    fie_id      text,
    metadata    jsonb NOT NULL DEFAULT '{}',
    scraped_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_national_fed_rankings_unique
        UNIQUE (source, season, weapon, gender, category, rank)
);

CREATE INDEX IF NOT EXISTS fs_national_fed_rankings_source_idx
    ON fs_national_fed_rankings (source, season);

CREATE INDEX IF NOT EXISTS fs_national_fed_rankings_fencer_idx
    ON fs_national_fed_rankings (fencer_id)
    WHERE fencer_id IS NOT NULL;
```

- [ ] **Step 2: Apply migration via Supabase MCP**

Run via Supabase MCP tool (not manually):
```
apply_migration(project_id="aqisovwkxlyauxeknrne", name="national_fed_rankings", query=<above SQL>)
```

- [ ] **Step 3: Verify table exists**

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'fs_national_fed_rankings' ORDER BY ordinal_position;
```

Expected: 14 columns listed.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/20260529_national_fed_rankings.sql
git commit -m "feat: add fs_national_fed_rankings table"
```

---

### Task 2: Common writer module

**Files:**
- Create: `fed_rankings_common.py`
- Create: `tests/test_fed_rankings_common.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_fed_rankings_common.py
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_build_ranking_row_minimal():
    from fed_rankings_common import build_ranking_row
    row = build_ranking_row(
        source="british_fencing",
        season="2025-2026",
        weapon="Foil",
        gender="Men",
        category="Senior",
        rank=1,
        name="James Davis",
        country="GBR",
    )
    assert row["source"] == "british_fencing"
    assert row["season"] == "2025-2026"
    assert row["weapon"] == "Foil"
    assert row["gender"] == "Men"
    assert row["category"] == "Senior"
    assert row["rank"] == 1
    assert row["name"] == "James Davis"
    assert row["country"] == "GBR"
    assert row["club"] is None
    assert row["points"] is None
    assert row["fencer_id"] is None
    assert row["fie_id"] is None
    assert isinstance(row["metadata"], dict)


def test_build_ranking_row_with_optionals():
    from fed_rankings_common import build_ranking_row
    row = build_ranking_row(
        source="fff",
        season="2025-2026",
        weapon="Epee",
        gender="Women",
        category="Junior",
        rank=3,
        name="Marie Dupont",
        country="FRA",
        club="Paris FC",
        points=1250.5,
        fie_id="98765",
    )
    assert row["club"] == "Paris FC"
    assert row["points"] == 1250.5
    assert row["fie_id"] == "98765"


def test_normalize_weapon():
    from fed_rankings_common import normalize_weapon
    assert normalize_weapon("foil") == "Foil"
    assert normalize_weapon("EPÉE") == "Epee"
    assert normalize_weapon("épée") == "Epee"
    assert normalize_weapon("sabre") == "Sabre"
    assert normalize_weapon("saber") == "Sabre"
    assert normalize_weapon("fleuret") == "Foil"
    assert normalize_weapon("degen") == "Epee"


def test_normalize_gender():
    from fed_rankings_common import normalize_gender
    assert normalize_gender("men") == "Men"
    assert normalize_gender("M") == "Men"
    assert normalize_gender("women") == "Women"
    assert normalize_gender("F") == "Women"
    assert normalize_gender("dames") == "Women"
    assert normalize_gender("hommes") == "Men"
    assert normalize_gender("herren") == "Men"
    assert normalize_gender("damen") == "Women"


def test_normalize_category():
    from fed_rankings_common import normalize_category
    assert normalize_category("senior") == "Senior"
    assert normalize_category("junior") == "Junior"
    assert normalize_category("cadet") == "Cadet"
    assert normalize_category("veteran") == "Veteran"
    assert normalize_category("u20") == "Junior"
    assert normalize_category("u17") == "Cadet"
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_fed_rankings_common.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'build_ranking_row' from 'fed_rankings_common'`

- [ ] **Step 3: Implement `fed_rankings_common.py`**

```python
# fed_rankings_common.py
import os
import re
import time
from datetime import datetime, timezone

from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

_supabase = None


def get_supabase():
    global _supabase
    if _supabase is None and SUPABASE_URL and SUPABASE_KEY:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


WEAPON_ALIASES = {
    "foil": "Foil", "fleuret": "Foil", "fioretto": "Foil", "florett": "Foil",
    "epee": "Epee", "épée": "Epee", "épee": "Epee", "degen": "Epee", "estoc": "Epee",
    "sabre": "Sabre", "saber": "Sabre", "sciabola": "Sabre", "säbel": "Sabre",
}
GENDER_ALIASES = {
    "men": "Men", "m": "Men", "male": "Men", "hommes": "Men", "herren": "Men",
    "männer": "Men", "uomini": "Men",
    "women": "Women", "w": "Women", "f": "Women", "female": "Women",
    "dames": "Women", "femmes": "Women", "damen": "Women", "frauen": "Women", "donne": "Women",
}
CATEGORY_ALIASES = {
    "senior": "Senior", "s": "Senior", "senioren": "Senior", "seniores": "Senior",
    "junior": "Junior", "j": "Junior", "u20": "Junior", "u21": "Junior",
    "cadet": "Cadet", "c": "Cadet", "u17": "Cadet", "u18": "Cadet",
    "veteran": "Veteran", "v": "Veteran", "masters": "Veteran",
}


def normalize_weapon(raw: str) -> str | None:
    key = re.sub(r"[^a-z]", "", raw.lower().replace("é", "e").replace("è", "e").replace("ä", "a"))
    return WEAPON_ALIASES.get(key) or WEAPON_ALIASES.get(raw.lower())


def normalize_gender(raw: str) -> str | None:
    return GENDER_ALIASES.get(raw.lower().strip())


def normalize_category(raw: str) -> str | None:
    return CATEGORY_ALIASES.get(raw.lower().strip())


def build_ranking_row(
    *,
    source: str,
    season: str,
    weapon: str,
    gender: str,
    category: str,
    rank: int,
    name: str,
    country: str | None = None,
    club: str | None = None,
    points: float | None = None,
    fie_id: str | None = None,
    fencer_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "source": source,
        "season": season,
        "weapon": weapon,
        "gender": gender,
        "category": category,
        "rank": rank,
        "name": name,
        "country": country,
        "club": club,
        "points": points,
        "fie_id": fie_id,
        "fencer_id": fencer_id,
        "metadata": metadata or {},
    }


def match_fencer(name: str, country: str | None, fie_id: str | None) -> str | None:
    client = get_supabase()
    if not client:
        return None
    try:
        if fie_id:
            rows = client.table("fs_fencers").select("id").eq("fie_id", fie_id).limit(1).execute().data
            if rows:
                return rows[0]["id"]
        if name and country:
            rows = client.table("fs_fencers").select("id").ilike("name", name).eq("country", country).limit(1).execute().data
            if rows:
                return rows[0]["id"]
    except Exception:
        pass
    return None


def write_rankings(rows: list[dict], source: str, season: str) -> int:
    client = get_supabase()
    if not client or not rows:
        return 0
    # Enrich with fencer_id matches
    enriched = []
    for row in rows:
        if not row.get("fencer_id"):
            row = dict(row)
            row["fencer_id"] = match_fencer(row.get("name", ""), row.get("country"), row.get("fie_id"))
        enriched.append(row)

    # Delete existing rankings for this source/season/weapon/gender/category combinations
    combos = {(r["weapon"], r["gender"], r["category"]) for r in enriched}
    for weapon, gender, category in combos:
        try:
            client.table("fs_national_fed_rankings").delete()\
                .eq("source", source).eq("season", season)\
                .eq("weapon", weapon).eq("gender", gender).eq("category", category)\
                .execute()
        except Exception as exc:
            print(f"  Delete existing failed ({source}/{season}/{weapon}/{gender}/{category}): {exc}")

    # Insert in batches
    written = 0
    for i in range(0, len(enriched), 100):
        try:
            client.table("fs_national_fed_rankings").insert(enriched[i:i+100]).execute()
            written += len(enriched[i:i+100])
        except Exception as exc:
            print(f"  Insert batch failed: {exc}")
    return written
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_fed_rankings_common.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add fed_rankings_common.py tests/test_fed_rankings_common.py
git commit -m "feat: fed_rankings_common writer + normalizers + tests"
```

---

### Task 3: British Fencing scraper

**Files:**
- Create: `scrape_fed_british.py`
- Create: `tests/test_fed_british.py`

**Probe first:** `https://www.britishfencing.com/rankings/`

- [ ] **Step 1: Write probe**

```python
# probe_british_fencing.py — run once manually
import requests
from bs4 import BeautifulSoup

BASE = "https://www.britishfencing.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)"}

r = requests.get(f"{BASE}/rankings/", headers=HEADERS, timeout=15)
soup = BeautifulSoup(r.text, "html.parser")

# Look for ranking tables, dropdown selectors, or API calls
print("Status:", r.status_code)
print("Title:", soup.find("title").text if soup.find("title") else "N/A")
# Print all forms (may have weapon/gender selectors)
for form in soup.find_all("form")[:3]:
    print("FORM:", form.get("action"), [i.get("name") for i in form.find_all("input")])
# Print any tables
for table in soup.find_all("table")[:2]:
    rows = table.find_all("tr")[:3]
    for row in rows:
        print([td.text.strip() for td in row.find_all(["td","th"])])
# Check for JS fetch calls to an API
import re
api_calls = re.findall(r'fetch\(["\']([^"\']+)["\']', r.text)
print("API calls:", api_calls[:5])
```

Run: `python probe_british_fencing.py`

- [ ] **Step 2: Write fixture-based tests using probe findings**

Update `BRITISH_RANKINGS_HTML` fixture below to match actual HTML structure found in probe. Then:

```python
# tests/test_fed_british.py
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# UPDATE THIS FIXTURE after running probe to match actual HTML structure
BRITISH_RANKINGS_HTML = """
<html><body>
<table>
  <thead><tr><th>Rank</th><th>Name</th><th>Club</th><th>Points</th></tr></thead>
  <tbody>
    <tr><td>1</td><td>James Davis</td><td>Leon Paul</td><td>2500</td></tr>
    <tr><td>2</td><td>Oliver Stell</td><td>British Swords</td><td>2200</td></tr>
    <tr><td>3</td><td>Marcus Mepstead</td><td>Leon Paul</td><td>2100</td></tr>
  </tbody>
</table>
</body></html>
"""


def test_parse_british_rankings_table():
    from scrape_fed_british import parse_rankings_table
    rows = parse_rankings_table(BRITISH_RANKINGS_HTML)
    assert len(rows) == 3
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "James Davis"
    assert rows[0]["club"] == "Leon Paul"
    assert rows[0]["points"] == 2500.0


def test_parse_british_rankings_empty_table():
    from scrape_fed_british import parse_rankings_table
    html = "<html><body><table><thead><tr><th>Rank</th></tr></thead><tbody></tbody></table></body></html>"
    rows = parse_rankings_table(html)
    assert rows == []
```

- [ ] **Step 3: Run to confirm failure**

```bash
python -m pytest tests/test_fed_british.py -v 2>&1 | head -10
```

Expected: `ImportError`

- [ ] **Step 4: Implement `scrape_fed_british.py`**

**Update `BASE_URL` and `parse_rankings_table` after running probe to match actual site structure.**

```python
# scrape_fed_british.py
import os
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from fed_rankings_common import build_ranking_row, write_rankings, normalize_weapon, normalize_gender, normalize_category

SOURCE = "british_fencing"
BASE_URL = "https://www.britishfencing.com"
COUNTRY = "GBR"
REQUEST_DELAY = 1.5
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)"}

# UPDATE THESE after running probe
RANKING_COMBOS = [
    ("Foil",  "Men",   "Senior"),
    ("Foil",  "Women", "Senior"),
    ("Epee",  "Men",   "Senior"),
    ("Epee",  "Women", "Senior"),
    ("Sabre", "Men",   "Senior"),
    ("Sabre", "Women", "Senior"),
    ("Foil",  "Men",   "Junior"),
    ("Foil",  "Women", "Junior"),
    ("Epee",  "Men",   "Junior"),
    ("Epee",  "Women", "Junior"),
    ("Sabre", "Men",   "Junior"),
    ("Sabre", "Women", "Junior"),
]


def parse_rankings_table(html: str) -> list[dict]:
    """Parse a British Fencing rankings table. Update after probe confirms HTML structure."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    rows = []
    for i, tr in enumerate(table.find_all("tr")):
        cells = [td.text.strip() for td in tr.find_all(["td", "th"])]
        if not cells or not cells[0].isdigit():
            continue
        try:
            rank = int(cells[0])
            name = cells[1] if len(cells) > 1 else None
            club = cells[2] if len(cells) > 2 else None
            points_raw = cells[3] if len(cells) > 3 else None
            points = float(re.sub(r"[^\d.]", "", points_raw)) if points_raw and re.search(r"\d", points_raw) else None
            if name:
                rows.append({"rank": rank, "name": name, "club": club, "points": points})
        except (ValueError, IndexError):
            continue
    return rows


def fetch_rankings_page(weapon: str, gender: str, category: str) -> str | None:
    """
    Fetch HTML for a specific rankings page. URL structure must be confirmed via probe.
    This is a PLACEHOLDER — update after probe.
    Expected URL pattern: /rankings/?weapon=foil&gender=men&category=senior
    """
    weapon_slug = weapon.lower()
    gender_slug = gender.lower()
    category_slug = category.lower()
    url = f"{BASE_URL}/rankings/?weapon={weapon_slug}&gender={gender_slug}&category={category_slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        return r.text if r.status_code == 200 else None
    except Exception as exc:
        print(f"  Fetch failed {url}: {exc}")
        return None


def current_season() -> str:
    now = datetime.now(timezone.utc)
    year = now.year
    return f"{year-1}-{year}" if now.month < 7 else f"{year}-{year+1}"


def main():
    run_log = ScraperRunLogger("scrape_fed_british").start()
    season = current_season()
    print(f"British Fencing rankings scraper — season {season}")

    total_written = total_failed = 0
    for weapon, gender, category in RANKING_COMBOS:
        print(f"  {weapon} {gender} {category}...")
        html = fetch_rankings_page(weapon, gender, category)
        if not html:
            print(f"    No page returned")
            total_failed += 1
            continue
        parsed = parse_rankings_table(html)
        if not parsed:
            print(f"    No rows parsed")
            total_failed += 1
            time.sleep(REQUEST_DELAY)
            continue
        rows = [
            build_ranking_row(
                source=SOURCE, season=season, weapon=weapon, gender=gender, category=category,
                rank=r["rank"], name=r["name"], country=COUNTRY,
                club=r.get("club"), points=r.get("points"),
            )
            for r in parsed
        ]
        n = write_rankings(rows, source=SOURCE, season=season)
        print(f"    Written {n} rows")
        total_written += n
        time.sleep(REQUEST_DELAY)

    run_log.complete(written=total_written, failed=total_failed)
    print(f"\nDone — written={total_written}, failed={total_failed}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_fed_british.py -v
```

Expected: All 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scrape_fed_british.py tests/test_fed_british.py
git commit -m "feat: British Fencing rankings scraper + tests"
```

---

### Task 4: FFF France scraper

**Files:**
- Create: `scrape_fed_france.py`
- Create: `tests/test_fed_france.py`

**Probe first:** `https://www.escrime-info.com/classements` or `https://ranking.escrime-info.com`

- [ ] **Step 1: Write probe**

```python
# probe_fff_france.py — run once manually
import requests
from bs4 import BeautifulSoup

URLS_TO_TRY = [
    "https://www.escrime-info.com/classements",
    "https://www.escrime-info.com/classement",
    "https://ranking.escrime-info.com",
    "https://www.escrime-info.com/rankings",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)"}

for url in URLS_TO_TRY:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"{url}: HTTP {r.status_code}, {len(r.text)} bytes")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            print("  Title:", soup.find("title").text.strip() if soup.find("title") else "N/A")
            tables = soup.find_all("table")
            print(f"  Tables: {len(tables)}")
            if tables:
                rows = tables[0].find_all("tr")[:3]
                for row in rows:
                    print("  ", [td.text.strip() for td in row.find_all(["td","th"])])
    except Exception as e:
        print(f"{url}: ERROR {e}")
```

Run: `python probe_fff_france.py`

- [ ] **Step 2: Write tests + implement**

After the probe, write `tests/test_fed_france.py` with fixture HTML matching the actual structure, then implement `scrape_fed_france.py` following the same pattern as `scrape_fed_british.py`:
- Same imports from `fed_rankings_common`
- `SOURCE = "fff_france"`, `COUNTRY = "FRA"`
- `parse_rankings_table(html)` adapted to the actual HTML structure
- `fetch_rankings_page(weapon, gender, category)` with real URL
- `main()` identical pattern to British scraper

```python
# tests/test_fed_france.py — fill fixture after probe
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# UPDATE after probe
FFF_RANKINGS_HTML = """
<html><body>
<table>
  <tr><th>Rang</th><th>Nom</th><th>Club</th><th>Points</th></tr>
  <tr><td>1</td><td>Romain Cannone</td><td>Paris UC</td><td>3200</td></tr>
  <tr><td>2</td><td>Alexandre Bardenet</td><td>Mérignac</td><td>2800</td></tr>
</table>
</body></html>
"""


def test_parse_fff_rankings():
    from scrape_fed_france import parse_rankings_table
    rows = parse_rankings_table(FFF_RANKINGS_HTML)
    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Romain Cannone"
    assert rows[0]["points"] == 3200.0
```

- [ ] **Step 3: Commit**

```bash
git add scrape_fed_france.py tests/test_fed_france.py
git commit -m "feat: FFF France rankings scraper + tests"
```

---

### Task 5: DFB Germany scraper

**Files:**
- Create: `scrape_fed_germany.py`
- Create: `tests/test_fed_germany.py`

**Probe first:** `https://www.fechten.org/fechtsport/ranglisten/`

- [ ] **Step 1: Write probe**

```python
# probe_dfb_germany.py — run once manually
import requests
from bs4 import BeautifulSoup

BASE = "https://www.fechten.org"
URLS = [
    f"{BASE}/fechtsport/ranglisten/",
    f"{BASE}/ranglisten/",
    f"{BASE}/leistungssport/ranglisten/",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)"}

for url in URLS:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"{url}: HTTP {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            print(" ", soup.find("title").text.strip() if soup.find("title") else "N/A")
            for table in soup.find_all("table")[:1]:
                for row in table.find_all("tr")[:4]:
                    print(" ", [td.text.strip() for td in row.find_all(["td","th"])])
    except Exception as e:
        print(f"{url}: ERROR {e}")
```

- [ ] **Step 2: Write tests + implement `scrape_fed_germany.py`**

Same pattern as British/France scrapers. `SOURCE = "dfb_germany"`, `COUNTRY = "GER"`. Update fixture HTML from probe.

```python
# tests/test_fed_germany.py — fill fixture after probe
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DFB_HTML = """
<html><body>
<table>
  <tr><th>Platz</th><th>Name</th><th>Verein</th><th>Punkte</th></tr>
  <tr><td>1</td><td>Peter Joppich</td><td>FC Tauberbischofsheim</td><td>4100</td></tr>
  <tr><td>2</td><td>Andre Thiem</td><td>Heidenheimer SB</td><td>3800</td></tr>
</table>
</body></html>
"""


def test_parse_dfb_rankings():
    from scrape_fed_germany import parse_rankings_table
    rows = parse_rankings_table(DFB_HTML)
    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Peter Joppich"
```

- [ ] **Step 3: Commit**

```bash
git add scrape_fed_germany.py tests/test_fed_germany.py
git commit -m "feat: DFB Germany rankings scraper + tests"
```

---

### Task 6: FIS Italy scraper

**Files:**
- Create: `scrape_fed_italy.py`
- Create: `tests/test_fed_italy.py`

**Probe first:** `https://www.federscherma.it/classifiche/` or `https://www.federscherma.it/rankings/`

- [ ] **Step 1: Write probe**

```python
# probe_fis_italy.py — run once manually
import requests
from bs4 import BeautifulSoup

URLS = [
    "https://www.federscherma.it/classifiche/",
    "https://www.federscherma.it/rankings/",
    "https://www.federscherma.it/sportivi/classifiche/",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)"}

for url in URLS:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"{url}: HTTP {r.status_code}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            print(" ", soup.find("title").text.strip() if soup.find("title") else "N/A")
            for table in soup.find_all("table")[:1]:
                for row in table.find_all("tr")[:3]:
                    print(" ", [td.text.strip() for td in row.find_all(["td","th"])])
    except Exception as e:
        print(f"{url}: ERROR {e}")
```

- [ ] **Step 2: Write tests + implement `scrape_fed_italy.py`**

`SOURCE = "fis_italy"`, `COUNTRY = "ITA"`. Update fixture from probe.

```python
# tests/test_fed_italy.py — fill fixture after probe
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

FIS_HTML = """
<html><body>
<table>
  <tr><th>Pos</th><th>Atleta</th><th>Società</th><th>Punti</th></tr>
  <tr><td>1</td><td>Aldo Montano</td><td>Fiamme Oro</td><td>5200</td></tr>
  <tr><td>2</td><td>Luigi Samele</td><td>CS Aeronautica</td><td>4800</td></tr>
</table>
</body></html>
"""


def test_parse_fis_rankings():
    from scrape_fed_italy import parse_rankings_table
    rows = parse_rankings_table(FIS_HTML)
    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Aldo Montano"
```

- [ ] **Step 3: Commit**

```bash
git add scrape_fed_italy.py tests/test_fed_italy.py
git commit -m "feat: FIS Italy rankings scraper + tests"
```

---

### Task 7: CFF Canada scraper

**Files:**
- Create: `scrape_fed_canada.py`
- Create: `tests/test_fed_canada.py`

**Probe first:** `https://www.fencing.ca/rankings/` or `https://fencing.ca/rankings`

- [ ] **Step 1: Write probe**

```python
# probe_cff_canada.py — run once manually
import requests
from bs4 import BeautifulSoup

URLS = [
    "https://www.fencing.ca/rankings/",
    "https://fencing.ca/rankings",
    "https://www.fencing.ca/athlete-rankings/",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)"}

for url in URLS:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        print(f"{url}: HTTP {r.status_code} -> {r.url}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            print(" ", soup.find("title").text.strip() if soup.find("title") else "N/A")
            for table in soup.find_all("table")[:1]:
                for row in table.find_all("tr")[:3]:
                    print(" ", [td.text.strip() for td in row.find_all(["td","th"])])
    except Exception as e:
        print(f"{url}: ERROR {e}")
```

- [ ] **Step 2: Write tests + implement `scrape_fed_canada.py`**

`SOURCE = "cff_canada"`, `COUNTRY = "CAN"`. Update fixture from probe.

```python
# tests/test_fed_canada.py — fill fixture after probe
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

CFF_HTML = """
<html><body>
<table>
  <tr><th>Rank</th><th>Name</th><th>Club</th><th>Points</th></tr>
  <tr><td>1</td><td>Maximilien Van Haaster</td><td>Club Dandalion</td><td>1800</td></tr>
  <tr><td>2</td><td>Eleanor Harvey</td><td>Ottawa Fencing Club</td><td>1600</td></tr>
</table>
</body></html>
"""


def test_parse_cff_rankings():
    from scrape_fed_canada import parse_rankings_table
    rows = parse_rankings_table(CFF_HTML)
    assert len(rows) == 2
    assert rows[0]["name"] == "Maximilien Van Haaster"
```

- [ ] **Step 3: Commit**

```bash
git add scrape_fed_canada.py tests/test_fed_canada.py
git commit -m "feat: CFF Canada rankings scraper + tests"
```

---

### Task 8: Add all 5 scrapers to GitHub Actions

**Files:**
- Modify: `.github/workflows/scraper.yml`

- [ ] **Step 1: Add steps after `scrape_clubs.py`**

```yaml
      - name: Scrape British Fencing rankings
        continue-on-error: true
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python scrape_fed_british.py

      - name: Scrape FFF France rankings
        continue-on-error: true
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python scrape_fed_france.py

      - name: Scrape DFB Germany rankings
        continue-on-error: true
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python scrape_fed_germany.py

      - name: Scrape FIS Italy rankings
        continue-on-error: true
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python scrape_fed_italy.py

      - name: Scrape CFF Canada rankings
        continue-on-error: true
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python scrape_fed_canada.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/scraper.yml
git commit -m "ci: add 5 national fed rankings scraper steps"
```

---

### Task 9: First run + verify all 5

- [ ] **Step 1: Run each locally after probing and updating URL/parse logic**

```bash
SUPABASE_URL=<v> SUPABASE_SERVICE_KEY=<v> python scrape_fed_british.py
SUPABASE_URL=<v> SUPABASE_SERVICE_KEY=<v> python scrape_fed_france.py
SUPABASE_URL=<v> SUPABASE_SERVICE_KEY=<v> python scrape_fed_germany.py
SUPABASE_URL=<v> SUPABASE_SERVICE_KEY=<v> python scrape_fed_italy.py
SUPABASE_URL=<v> SUPABASE_SERVICE_KEY=<v> python scrape_fed_canada.py
```

- [ ] **Step 2: Verify in DB**

```sql
SELECT source, season, weapon, gender, category, COUNT(*) as fencers
FROM fs_national_fed_rankings
GROUP BY source, season, weapon, gender, category
ORDER BY source, weapon, gender, category;
```

Expected: Rows for each federation with reasonable fencer counts (50–500 per combination).

```sql
SELECT source, COUNT(*) as total, COUNT(fencer_id) as linked_to_fs_fencers
FROM fs_national_fed_rankings
GROUP BY source;
```

Expected: `linked_to_fs_fencers` is a meaningful fraction of `total` (varies by federation's FIE representation).

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: all 5 national fed rankings scrapers — first run verified"
```

---

## Self-Review

- DB migration creates table + indexes before any scraper code is written ✓
- Common module tested independently before federation scrapers ✓
- Each federation has a probe step before implementation ✓
- All fixture HTML is a placeholder marked "UPDATE after probe" ✓
- `write_rankings` deletes then re-inserts per combo — idempotent reruns ✓
- `match_fencer` tries FIE ID first, name+country fallback — never blocks insert ✓
- `continue-on-error: true` — one bad federation won't break CI ✓
- `SOURCE` constants are unique per federation for clean DB queries ✓

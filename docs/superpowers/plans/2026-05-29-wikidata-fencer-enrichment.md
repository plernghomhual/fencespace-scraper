# Wikidata Fencer Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich `fs_fencers` rows with biographical data from Wikidata — date of birth, nationality, Wikipedia bio text, headshot image URL — by matching via FIE athlete ID (Wikidata property P1447-like FIE property) and falling back to name+country.

**Architecture:** New script `scrape_wikidata.py` runs a SPARQL query against `https://query.wikidata.org/sparql` to fetch all known fencers with their properties. For each Wikidata fencer, it attempts to match an existing `fs_fencers` row by FIE ID first, then by name+country. Matched rows are updated (never inserted — this is enrichment only). Uses `scraper_state.py` to track last-run timestamp for incremental updates.

**Tech Stack:** Python 3.11, requests, supabase-py, existing `run_logger.py`, `scraper_state.py`

**Wikidata SPARQL endpoint:** `https://query.wikidata.org/sparql` — free, no auth, returns JSON with `Accept: application/sparql-results+json`

---

## Background: Wikidata properties for fencers

| Property | Meaning | Example value |
|----------|---------|---------------|
| P641 | sport | Q5386 (fencing) |
| P569 | date of birth | `+1985-03-14T00:00:00Z` |
| P27 | country of citizenship | Q142 (France) |
| P18 | image | Wikimedia Commons filename |
| P1447 | Sports Reference athlete ID | used to cross-reference |
| P3546 | FIE athlete ID | e.g. `"37049"` — this is the key link to `fs_fencers.fie_id` |
| P21 | sex or gender | Q6581097 (male), Q6581072 (female) |
| P1559 | name in native language | for non-Latin scripts |

> **Note:** Verify P3546 is the correct FIE athlete ID property by running the SPARQL probe in Task 1 before building.

---

## File Map

| Action | Path |
|--------|------|
| Create | `scrape_wikidata.py` |
| Create | `tests/test_scrape_wikidata.py` |
| Modify | `.github/workflows/scraper.yml` — add Wikidata step |

---

### Task 1: Probe Wikidata SPARQL for fencer properties

- [ ] **Step 1: Run minimal probe query**

```python
# probe_wikidata.py — run once manually, then delete
import requests

SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; plerngh@gmail.com)",
}

# Discover FIE ID property — P3546 is the candidate
QUERY = """
SELECT ?athlete ?athleteLabel ?fie_id ?dob ?imageUrl WHERE {
  ?athlete wdt:P641 wd:Q5386 .
  OPTIONAL { ?athlete wdt:P3546 ?fie_id . }
  OPTIONAL { ?athlete wdt:P569 ?dob . }
  OPTIONAL { ?athlete wdt:P18 ?imageUrl . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 10
"""

r = requests.get(SPARQL_URL, params={"query": QUERY, "format": "json"}, headers=HEADERS, timeout=30)
data = r.json()
for b in data["results"]["bindings"]:
    print(
        b.get("athleteLabel", {}).get("value"),
        b.get("fie_id", {}).get("value"),
        b.get("dob", {}).get("value", "")[:10],
    )
```

Run: `python probe_wikidata.py`

Expected: Lines like `Aldo Montano  37049  1978-11-05`

If `fie_id` column is empty for most rows, the property may be different. Try replacing `P3546` with `P1447` or search Wikidata for "FIE" in property labels.

- [ ] **Step 2: Count total fencers in Wikidata**

```python
COUNT_QUERY = """
SELECT (COUNT(*) AS ?count) WHERE {
  ?athlete wdt:P641 wd:Q5386 .
}
"""
r = requests.get(SPARQL_URL, params={"query": COUNT_QUERY, "format": "json"}, headers=HEADERS, timeout=30)
print(r.json()["results"]["bindings"][0]["count"]["value"])
```

Expected: ~2,000–10,000 fencers. If over 10,000 consider pagination via SPARQL OFFSET/LIMIT.

- [ ] **Step 3: Record the correct FIE property**

Update `FIE_ID_PROPERTY` constant in `scrape_wikidata.py` with confirmed property (P3546 or other).

---

### Task 2: Write failing tests

**Files:**
- Create: `tests/test_scrape_wikidata.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_scrape_wikidata.py
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

SAMPLE_BINDINGS = [
    {
        "athlete": {"value": "http://www.wikidata.org/entity/Q312123"},
        "athleteLabel": {"value": "Aldo Montano"},
        "fie_id": {"value": "37049"},
        "dob": {"value": "+1978-11-05T00:00:00Z"},
        "countryLabel": {"value": "Italy"},
        "imageUrl": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/Aldo_Montano.jpg"},
        "genderLabel": {"value": "male"},
    },
    {
        "athlete": {"value": "http://www.wikidata.org/entity/Q999999"},
        "athleteLabel": {"value": "Unknown Fencer"},
        # no fie_id
        "dob": {"value": "+1990-01-15T00:00:00Z"},
        "countryLabel": {"value": "France"},
    },
]


def test_parse_wikidata_binding_with_fie_id():
    from scrape_wikidata import parse_binding
    result = parse_binding(SAMPLE_BINDINGS[0])
    assert result["fie_id"] == "37049"
    assert result["date_of_birth"] == "1978-11-05"
    assert result["nationality"] == "Italy"
    assert result["headshot_url"] == "http://commons.wikimedia.org/wiki/Special:FilePath/Aldo_Montano.jpg"
    assert result["wikidata_id"] == "Q312123"
    assert result["gender"] == "Male"


def test_parse_wikidata_binding_without_fie_id():
    from scrape_wikidata import parse_binding
    result = parse_binding(SAMPLE_BINDINGS[1])
    assert result["fie_id"] is None
    assert result["date_of_birth"] == "1990-01-15"
    assert result["nationality"] == "France"


def test_parse_dob_handles_malformed():
    from scrape_wikidata import parse_wikidata_date
    assert parse_wikidata_date("+1978-11-05T00:00:00Z") == "1978-11-05"
    assert parse_wikidata_date("+1978-00-00T00:00:00Z") is None  # unknown month/day
    assert parse_wikidata_date(None) is None
    assert parse_wikidata_date("") is None


def test_parse_dob_year_only():
    from scrape_wikidata import parse_wikidata_date
    # Some Wikidata DOBs have only year
    assert parse_wikidata_date("+1985-01-01T00:00:00Z") == "1985-01-01"


def test_build_update_payload_skips_none_fields():
    from scrape_wikidata import build_update_payload
    data = {
        "fie_id": "37049",
        "date_of_birth": "1978-11-05",
        "nationality": "Italy",
        "headshot_url": None,
        "gender": None,
        "wikidata_id": "Q312123",
    }
    payload = build_update_payload(data)
    assert "date_of_birth" in payload
    assert "nationality" in payload
    assert "headshot_url" not in payload  # None fields excluded
    assert "gender" not in payload
    assert payload["metadata"] == {"wikidata_id": "Q312123"}
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_scrape_wikidata.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'parse_binding' from 'scrape_wikidata'`

---

### Task 3: Implement `scrape_wikidata.py`

**Files:**
- Create: `scrape_wikidata.py`

- [ ] **Step 1: Write core module**

```python
# scrape_wikidata.py
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

SPARQL_URL = "https://query.wikidata.org/sparql"
SOURCE = "wikidata"
REQUEST_DELAY = 1.0
PAGE_SIZE = 5000

# Update this after running probe — P3546 is the FIE athlete ID property candidate
FIE_ID_PROPERTY = os.environ.get("WIKIDATA_FIE_PROPERTY", "P3546")

HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; plerngh@gmail.com)",
}

SPARQL_QUERY = """
SELECT ?athlete ?athleteLabel ?fie_id ?dob ?countryLabel ?imageUrl ?genderLabel WHERE {{
  ?athlete wdt:P641 wd:Q5386 .
  OPTIONAL {{ ?athlete wdt:{fie_prop} ?fie_id . }}
  OPTIONAL {{ ?athlete wdt:P569 ?dob . }}
  OPTIONAL {{ ?athlete wdt:P27 ?country . }}
  OPTIONAL {{ ?athlete wdt:P18 ?imageUrl . }}
  OPTIONAL {{ ?athlete wdt:P21 ?gender . }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
    ?country rdfs:label ?countryLabel .
    ?gender rdfs:label ?genderLabel .
    ?athlete rdfs:label ?athleteLabel .
  }}
}}
LIMIT {limit}
OFFSET {offset}
"""


def parse_wikidata_date(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.match(r"[+-]?(\d{4})-(\d{2})-(\d{2})T", raw)
    if not m:
        return None
    year, month, day = m.group(1), m.group(2), m.group(3)
    if month == "00" or day == "00":
        return None
    return f"{year}-{month}-{day}"


def parse_binding(b: dict) -> dict:
    wikidata_url = b.get("athlete", {}).get("value", "")
    wikidata_id = wikidata_url.split("/")[-1] if wikidata_url else None
    gender_raw = (b.get("genderLabel") or {}).get("value", "")
    gender = "Male" if "male" in gender_raw.lower() and "female" not in gender_raw.lower() else \
             "Female" if "female" in gender_raw.lower() else None
    return {
        "wikidata_id": wikidata_id,
        "name": (b.get("athleteLabel") or {}).get("value"),
        "fie_id": (b.get("fie_id") or {}).get("value"),
        "date_of_birth": parse_wikidata_date((b.get("dob") or {}).get("value")),
        "nationality": (b.get("countryLabel") or {}).get("value"),
        "headshot_url": (b.get("imageUrl") or {}).get("value"),
        "gender": gender,
    }


def build_update_payload(data: dict) -> dict:
    payload = {}
    for field in ("date_of_birth", "nationality", "headshot_url", "gender"):
        if data.get(field) is not None:
            payload[field] = data[field]
    if data.get("wikidata_id"):
        payload["metadata"] = {"wikidata_id": data["wikidata_id"]}
    if payload:
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def fetch_wikidata_fencers() -> list[dict]:
    results = []
    offset = 0
    while True:
        query = SPARQL_QUERY.format(fie_prop=FIE_ID_PROPERTY, limit=PAGE_SIZE, offset=offset)
        try:
            r = requests.get(SPARQL_URL, params={"query": query, "format": "json"},
                             headers=HEADERS, timeout=60)
            if r.status_code != 200:
                print(f"  SPARQL error {r.status_code}")
                break
            bindings = r.json()["results"]["bindings"]
            if not bindings:
                break
            results.extend(bindings)
            print(f"  Fetched {len(results)} fencers so far...")
            if len(bindings) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
            time.sleep(REQUEST_DELAY)
        except Exception as exc:
            print(f"  SPARQL fetch failed at offset={offset}: {exc}")
            break
    return results


def match_fencer_by_fie_id(fie_id: str) -> list[str]:
    """Returns list of matching fs_fencers UUIDs (can be multiple rows for same fencer across weapons)."""
    try:
        rows = supabase.table("fs_fencers").select("id").eq("fie_id", fie_id).execute().data
        return [r["id"] for r in rows]
    except Exception:
        return []


def match_fencer_by_name_country(name: str, country: str) -> list[str]:
    try:
        rows = supabase.table("fs_fencers").select("id").ilike("name", name).eq("country", country).execute().data
        return [r["id"] for r in rows]
    except Exception:
        return []


def apply_update(fencer_uuid: str, payload: dict) -> bool:
    if not payload:
        return False
    try:
        supabase.table("fs_fencers").update(payload).eq("id", fencer_uuid).execute()
        return True
    except Exception as exc:
        print(f"    Update failed for {fencer_uuid}: {exc}")
        return False


def main():
    run_log = ScraperRunLogger("scrape_wikidata").start()
    print(f"Wikidata enrichment starting — {datetime.now(timezone.utc).isoformat()}")
    print(f"  Using FIE ID property: {FIE_ID_PROPERTY}")

    bindings = fetch_wikidata_fencers()
    print(f"Total fencers from Wikidata: {len(bindings)}")

    updated = matched_fie = matched_name = unmatched = 0
    for b in bindings:
        data = parse_binding(b)
        payload = build_update_payload(data)
        if not payload:
            continue

        ids = []
        if data["fie_id"]:
            ids = match_fencer_by_fie_id(data["fie_id"])
            if ids:
                matched_fie += 1
        if not ids and data["name"] and data["nationality"]:
            ids = match_fencer_by_name_country(data["name"], data["nationality"])
            if ids:
                matched_name += 1

        if not ids:
            unmatched += 1
            continue

        for fencer_uuid in ids:
            if apply_update(fencer_uuid, payload):
                updated += 1

    set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
    run_log.complete(written=updated, skipped=unmatched,
                     metadata={"matched_fie": matched_fie, "matched_name": matched_name})
    print(f"\nDone — updated={updated}, matched_by_fie={matched_fie}, "
          f"matched_by_name={matched_name}, unmatched={unmatched}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_scrape_wikidata.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scrape_wikidata.py tests/test_scrape_wikidata.py
git commit -m "feat: Wikidata fencer enrichment scraper + tests"
```

---

### Task 4: Add to GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/scraper.yml`

- [ ] **Step 1: Add step after `scrape_athlete_profiles.py`**

```yaml
      - name: Enrich fencers from Wikidata
        continue-on-error: true
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python scrape_wikidata.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/scraper.yml
git commit -m "ci: add Wikidata enrichment step"
```

---

### Task 5: First run + verify

- [ ] **Step 1: Run locally**

```bash
SUPABASE_URL=<value> SUPABASE_SERVICE_KEY=<value> python scrape_wikidata.py
```

Expected output:
```
Wikidata enrichment starting — ...
  Using FIE ID property: P3546
  Fetched 5000 fencers so far...
  Fetched XXXX fencers so far...
Total fencers from Wikidata: XXXX
Done — updated=YYY, matched_by_fie=ZZZ, matched_by_name=WWW, unmatched=VVV
```

If `matched_by_fie=0` for all records, the FIE property is wrong — re-run probe and update `FIE_ID_PROPERTY`.

- [ ] **Step 2: Verify enrichment in DB**

```sql
SELECT COUNT(*) FROM fs_fencers WHERE date_of_birth IS NOT NULL;
SELECT COUNT(*) FROM fs_fencers WHERE headshot_url IS NOT NULL;
SELECT name, date_of_birth, nationality, headshot_url FROM fs_fencers
WHERE (metadata->>'wikidata_id') IS NOT NULL LIMIT 5;
```

Expected: Meaningful increase in non-null `date_of_birth` and `headshot_url` counts.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: Wikidata enrichment — first run verified"
```

---

## Self-Review

- Probe step confirms correct FIE property before building ✓
- Two-tier matching (FIE ID → name+country fallback) ✓
- `build_update_payload` skips `None` fields — never overwrites good data with null ✓
- Enrichment only — never inserts new fencer rows ✓
- Paginated SPARQL (5000/page) handles large result sets ✓
- `metadata.wikidata_id` stored for future cross-reference ✓
- Polite rate limiting to Wikidata (1s between pages) ✓

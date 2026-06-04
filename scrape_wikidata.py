import os
import re
import time
from datetime import datetime, timezone

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SPARQL_URL = "https://query.wikidata.org/sparql"
SOURCE = "wikidata"
REQUEST_DELAY = 1.0
PAGE_SIZE = 5000

# P2423: International Fencing Federation fencer ID (confirmed via probe)
FIE_ID_PROPERTY = os.environ.get("WIKIDATA_FIE_PROPERTY", "P2423")
assert re.fullmatch(r"P\d+", FIE_ID_PROPERTY), f"Invalid FIE property: {FIE_ID_PROPERTY}"

HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; plerngh@gmail.com)",
}

# Q12100 = fencing (sport); P641 = sport of participant
SPARQL_QUERY = """
SELECT ?athlete ?athleteLabel ?fie_id ?dob ?countryLabel ?imageUrl ?genderLabel WHERE {{
  ?athlete wdt:P641 wd:Q12100 .
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


def parse_wikidata_date(raw):
    if not raw:
        return None
    m = re.match(r"[+-]?(\d{4})-(\d{2})-(\d{2})T", raw)
    if not m:
        return None
    year, month, day = m.group(1), m.group(2), m.group(3)
    if month == "00" or day == "00":
        return None
    return f"{year}-{month}-{day}"


def parse_binding(b):
    wikidata_url = b.get("athlete", {}).get("value", "")
    wikidata_id = wikidata_url.split("/")[-1] if wikidata_url else None
    gender_raw = (b.get("genderLabel") or {}).get("value", "")
    if "female" in gender_raw.lower():
        gender = "Female"
    elif "male" in gender_raw.lower():
        gender = "Male"
    else:
        gender = None
    return {
        "wikidata_id": wikidata_id,
        "name": (b.get("athleteLabel") or {}).get("value"),
        "fie_id": (b.get("fie_id") or {}).get("value"),
        "date_of_birth": parse_wikidata_date((b.get("dob") or {}).get("value")),
        "nationality": (b.get("countryLabel") or {}).get("value"),
        "headshot_url": (b.get("imageUrl") or {}).get("value"),
        "gender": gender,
    }


def build_update_payload(data):
    payload = {}
    for field in ("date_of_birth", "nationality", "headshot_url", "gender"):
        if data.get(field) is not None:
            payload[field] = data[field]
    if data.get("wikidata_id"):
        payload["metadata"] = {"wikidata_id": data["wikidata_id"]}
    return payload


def _sparql_fetch(query):
    for attempt in range(3):
        try:
            r = requests.get(
                SPARQL_URL,
                params={"query": query, "format": "json"},
                headers=HEADERS,
                timeout=45,
            )
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == 2:
                raise
            wait = 15 * (attempt + 1)
            print(f"  [wikidata] SPARQL timeout (attempt {attempt + 1}/3), retrying in {wait}s: {exc}")
            time.sleep(wait)


def fetch_wikidata_fencers():
    results = []
    offset = 0
    while True:
        query = SPARQL_QUERY.format(fie_prop=FIE_ID_PROPERTY, limit=PAGE_SIZE, offset=offset)
        try:
            data = _sparql_fetch(query)
            if data is None:
                break
            bindings = data["results"]["bindings"]
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


def match_fencer_by_fie_id(fie_id):
    try:
        rows = supabase.table("fs_fencers").select("id").eq("fie_id", fie_id).execute().data
        return [r["id"] for r in rows]
    except Exception:
        return []


def match_fencer_by_name_country(name, country):
    try:
        rows = supabase.table("fs_fencers").select("id").ilike("name", name).eq("country", country).execute().data
        return [r["id"] for r in rows]
    except Exception:
        return []


def apply_update(fencer_uuid, payload):
    if not payload:
        return False
    try:
        existing = supabase.table("fs_fencers").select(
            "date_of_birth,nationality,headshot_url,gender,metadata"
        ).eq("id", fencer_uuid).single().execute().data

        # Never overwrite existing non-null data
        for field in ("date_of_birth", "nationality", "headshot_url", "gender"):
            if existing.get(field) is not None:
                payload.pop(field, None)

        # Merge metadata — don't replace entire JSONB column
        if "metadata" in payload:
            existing_meta = existing.get("metadata") or {}
            existing_meta = existing_meta if isinstance(existing_meta, dict) else {}
            merged = {**existing_meta, **payload["metadata"]}
            payload["metadata"] = merged

        if not payload:
            return False

        supabase.table("fs_fencers").update(payload).eq("id", fencer_uuid).execute()
        return True
    except Exception as exc:
        print(f"    Update failed for {fencer_uuid}: {exc}")
        return False


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_wikidata").start()
    try:
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
                candidates = match_fencer_by_name_country(data["name"], data["nationality"])
                if len(candidates) == 1:  # skip ambiguous multi-match
                    ids = candidates
                    matched_name += 1

            if not ids:
                unmatched += 1
                continue

            for fencer_uuid in ids:
                if apply_update(fencer_uuid, dict(payload)):
                    updated += 1
            time.sleep(0.05)

        set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
        run_log.complete(written=updated, skipped=unmatched,
                         metadata={"matched_fie": matched_fie, "matched_name": matched_name})
        print(f"\nDone — updated={updated}, matched_by_fie={matched_fie}, "
              f"matched_by_name={matched_name}, unmatched={unmatched}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

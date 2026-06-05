"""
FISU World University Games / Universiade fencing results scraper.

Source probe (verified 2026-06-01):
  FISU sport page:      GET /sports/fencing/ -> event links and result archives
  Official stats PDF:   SUMMER-STATS-1959-2025_Final-20260109.pdf
  PDF fencing tables:   FENCING section has extractable medal tables for 1959-2025

Olympedia was probed first, but accessible fencing/editions pages did not expose
Universiade event routes. FISU's official statistics PDF is used as the canonical
source because it covers historical editions and naturally omits missing editions.
"""
from typing import Any
import io
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

SOURCE = "universiade"
FISU_STATS_PDF_URL = (
    "https://www.fisu.net/app/uploads/2026/01/"
    "SUMMER-STATS-1959-2025_Final-20260109.pdf"
)
REQUEST_DELAY = 1.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "application/pdf,text/html,*/*;q=0.8",
}

WEAPONS = {
    "EPEE": "Epee",
    "FOIL": "Foil",
    "SABRE": "Sabre",
    "SABER": "Sabre",
}
MEDAL_COLUMNS = [
    (1, "Gold", 1),
    (2, "Silver", 2),
    (3, "Bronze", 3),
]


def _clean_cell(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def _raw_cell(value):
    return "" if value is None else str(value).strip()


def _event_code(weapon, gender, team):
    kind = "team" if team else "individual"
    return f"{weapon.lower()}-{gender.lower()}-{kind}"


def _event_name(year, weapon, gender, team):
    kind = "Team" if team else "Individual"
    return f"{year} Summer Universiade — {weapon}, {kind}, {gender}"


def _split_medal_cell(value, weapon_label=None):
    text = _raw_cell(value)
    if not text:
        return []
    if weapon_label:
        text = re.sub(rf"^\s*{re.escape(weapon_label)}\s+", "", text, flags=re.I)
    if "(" in text and ")" in text:
        chunks = re.split(r"\s*/\s*", text.replace("\n", " ")) if "/" in text else text.splitlines()
        entries = []
        for chunk in chunks:
            chunk = _clean_cell(chunk)
            matches = re.findall(r".+?\(\s*[A-Z]{3}\s*\)", chunk)
            entries.extend(matches or [chunk])
        return [_clean_cell(part) for part in entries if _clean_cell(part)]
    return [_clean_cell(part) for part in re.split(r"\s*/\s*|\n+", text) if _clean_cell(part)]


def _parse_individual_entry(entry):
    match = re.search(r"^(?P<name>.+?)\s*\(\s*(?P<country>[A-Z]{3})\s*\)", entry)
    if not match:
        return {"name": _clean_cell(entry), "country": None}
    return {
        "name": _clean_cell(match.group("name")),
        "country": match.group("country"),
    }


def _parse_team_entry(entry):
    country = _clean_cell(entry).upper()
    return {"name": country, "country": country}


def _result_rows(row, team, weapon_label=None):
    results = []
    for column_index, medal, rank in MEDAL_COLUMNS:
        for entry in _split_medal_cell(row[column_index] if len(row) > column_index else "", weapon_label):
            parsed = _parse_team_entry(entry) if team else _parse_individual_entry(entry)
            if not parsed["name"]:
                continue
            results.append({
                "rank": rank,
                "name": parsed["name"],
                "country": parsed["country"],
                "medal": medal,
                "team": team,
            })
    return results


def parse_fisu_stats_tables(tables):
    """Parse pdfplumber table output from FISU's official statistics PDF."""
    events = []
    for table in tables:
        current_year = None
        section = None
        current_weapon_label = None

        for row in table:
            if not row:
                continue
            cells = [_clean_cell(cell) for cell in row]
            first = cells[0].upper() if cells else ""
            row_text = " ".join(cells).upper()

            if re.fullmatch(r"\d{4}", cells[0] if cells else ""):
                current_year = cells[0]
                section = "individual" if "INDIVIDUAL EVENTS" in row_text else None
                current_weapon_label = None
                continue
            if "TEAM EVENTS" in row_text:
                section = "team"
                current_weapon_label = None
                continue
            if not current_year or section not in {"individual", "team"}:
                continue
            if "GOLD" in row_text and "SILVER" in row_text and "BRONZE" in row_text:
                continue

            gender = None
            if first in WEAPONS:
                if first == current_weapon_label and _clean_cell(row[1] if len(row) > 1 else "").upper().startswith(first):
                    gender = "Women"
                else:
                    current_weapon_label = first
                    gender = "Men"
            elif current_weapon_label:
                gender = "Women"
            if not gender or not current_weapon_label:
                continue

            team = section == "team"
            weapon = WEAPONS[current_weapon_label]
            results = _result_rows(row, team, current_weapon_label)
            if not results:
                continue

            event_code = _event_code(weapon, gender, team)
            events.append({
                "source_id": f"universiade:{current_year}:{event_code}",
                "edition_id": current_year,
                "edition_year": current_year,
                "season": current_year,
                "event_code": event_code,
                "name": _event_name(current_year, weapon, gender, team),
                "weapon": weapon,
                "gender": gender,
                "team": team,
                "results": results,
            })
    return events


def fetch_fisu_stats_tables():
    """Download FISU's official statistics PDF and extract fencing tables."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required to parse FISU statistics PDFs.") from exc

    response = requests.get(FISU_STATS_PDF_URL, headers=HEADERS, timeout=90)
    response.raise_for_status()

    tables: list[Any] = []
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            if "FENCING" not in text.upper():
                continue
            tables.extend(page.extract_tables() or [])
    return tables


def discover_events():
    return parse_fisu_stats_tables(fetch_fisu_stats_tables())


def upsert_tournament(event):
    row = {
        "source_id": event["source_id"],
        "name": event["name"],
        "season": event["season"],
        "type": "universiade",
        "weapon": event["weapon"],
        "gender": event["gender"],
        "category": "Senior",
        "country": None,
        "has_results": True,
        "metadata": {
            "source": "fisu_statistics_pdf",
            "fisu_stats_pdf_url": FISU_STATS_PDF_URL,
            "edition_id": event["edition_id"],
            "edition_year": event["edition_year"],
            "event_code": event["event_code"],
            "team": event["team"],
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()  # type: ignore[union-attr]
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {event['source_id']}: {exc}")
        return None


def _match_fencer(name, country):
    if not name or not country:
        return None
    try:
        rows = (
            supabase.table("fs_fencers")  # type: ignore[union-attr]
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


def upsert_results(tournament_id, event):
    db_rows = []
    for result in event["results"]:
        fencer_id = None
        if not result.get("team"):
            fencer_id = _match_fencer(result["name"], result["country"])
        db_rows.append({
            "tournament_id": tournament_id,
            "name": result["name"],
            "nationality": result["country"],
            "rank": result["rank"],
            "medal": result["medal"],
            "fencer_id": fencer_id,
            "metadata": {
                "source_id": event["source_id"],
                "team": result["team"],
            },
        })

    if not db_rows:
        return 0

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()  # type: ignore[union-attr]
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i:i + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()  # type: ignore[union-attr]
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed for {event['source_id']}: {exc}")
    if written < len(db_rows):
        return 0
    return written


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_universiade").start()
    try:
        print(f"Universiade scraper starting — {datetime.now(timezone.utc).isoformat()}")
        done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])
        print(f"  {len(done_source_ids)} events already done")

        events = discover_events()
        editions = {event["edition_id"] for event in events}
        print(f"  {len(events)} events found across {len(editions)} editions")

        written = failed = skipped = 0
        for event in events:
            if event["source_id"] in done_source_ids:
                skipped += 1
                continue

            print(f"  {event['name']} ({event['source_id']})")
            tournament_id = upsert_tournament(event)
            if not tournament_id:
                failed += 1
                time.sleep(REQUEST_DELAY)
                continue

            result_count = upsert_results(tournament_id, event)
            if result_count == 0:
                failed += 1
                time.sleep(REQUEST_DELAY)
                continue

            print(f"    {result_count} results inserted")
            done_source_ids.add(event["source_id"])
            set_state(SOURCE, "done_source_ids", sorted(done_source_ids))
            written += 1
            time.sleep(REQUEST_DELAY)

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"Done — written={written}, skipped={skipped}, failed={failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

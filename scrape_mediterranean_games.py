"""
Mediterranean Games fencing results scraper.

Probe findings (2026-06-01):
  - Olympedia has a manual Mediterranean Games medalist list, but it is not
    complete enough for full fencing result imports.
  - Tarragona 2018 has structured Bornan HTML final-rank pages.
  - Oran 2022 has a structured Microplus PDF result book with standings pages.
  - Earlier public edition pages found during probing were archival/prose-only,
    so they are skipped with warnings until a structured source is confirmed.
"""

from __future__ import annotations

import io
import os
import re
import time
from datetime import UTC, datetime, timezone
from urllib.parse import urljoin

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

SOURCE = "mediterranean_games"
REQUEST_DELAY = 1.5
TARRAGONA_BASE = "https://results.tarragona2018.bornan.net/"
ORAN_RESULT_BOOK_URLS = [
    "https://gdm2022-pdf.microplustimingservices.com/FEN/ResultBook/GDM2022_FEN_v1.3.pdf",
    "https://web.archive.org/web/20220706154452/https://gdm2022-pdf.microplustimingservices.com/FEN/ResultBook/GDM2022_FEN_v1.3.pdf",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}

WEAPON_PATTERNS = [
    (re.compile(r"\b[ée]p[ée]e\b|\bepee\b", re.I), "Epee"),
    (re.compile(r"\bfoil\b", re.I), "Foil"),
    (re.compile(r"\bsabre\b|\bsaber\b|\bsable\b", re.I), "Sabre"),
]
GENDER_PATTERNS = [
    (re.compile(r"\bwomen\b|\bwomen['’]s\b", re.I), "Women"),
    (re.compile(r"\bmen\b|\bmen['’]s\b", re.I), "Men"),
]
MEDALS_BY_RANK = {1: "Gold", 2: "Silver", 3: "Bronze"}
MEDAL_WORDS = {"gold": (1, "Gold"), "silver": (2, "Silver"), "bronze": (3, "Bronze")}

STRUCTURED_EDITIONS = [
    {
        "edition_id": "2018",
        "edition_name": "Tarragona 2018",
        "year": "2018",
        "host_country": "ESP",
        "source_type": "tarragona_html",
        "schedule_url": urljoin(TARRAGONA_BASE, "en/FEN/schedule/daily"),
    },
    {
        "edition_id": "2022",
        "edition_name": "Oran 2022",
        "year": "2022",
        "host_country": "ALG",
        "source_type": "oran_pdf",
        "result_book_urls": ORAN_RESULT_BOOK_URLS,
    },
]

SKIPPED_EDITIONS = [
    ("1951", "Alexandria 1951"),
    ("1955", "Barcelona 1955"),
    ("1959", "Beirut 1959"),
    ("1963", "Naples 1963"),
    ("1967", "Tunis 1967"),
    ("1971", "Izmir 1971"),
    ("1975", "Algiers 1975"),
    ("1979", "Split 1979"),
    ("1983", "Casablanca 1983"),
    ("1987", "Latakia 1987"),
    ("1991", "Athens 1991"),
    ("1993", "Languedoc-Roussillon 1993"),
    ("1997", "Bari 1997"),
    ("2001", "Tunis 2001"),
    ("2005", "Almeria 2005"),
    ("2009", "Pescara 2009"),
    ("2013", "Mersin 2013"),
]


def discover_editions() -> tuple[list[dict], list[dict]]:
    structured = [dict(edition) for edition in STRUCTURED_EDITIONS]  # type: ignore[call-overload]
    skipped = [
        {
            "edition_id": edition_id,
            "edition_name": edition_name,
            "reason": (
                "unstructured public coverage; Olympedia manual coverage is incomplete "
                "and no static structured fencing result table was confirmed"
            ),
        }
        for edition_id, edition_name in SKIPPED_EDITIONS
    ]
    return structured, skipped


def classify_event(event_name: str) -> dict:
    weapon = next((weapon for pattern, weapon in WEAPON_PATTERNS if pattern.search(event_name)), None)
    gender = next((gender for pattern, gender in GENDER_PATTERNS if pattern.search(event_name)), None)
    team = bool(re.search(r"\bteam\b", event_name, re.I))
    return {"weapon": weapon, "gender": gender, "team": team}


def medal_for_rank(rank: int | None) -> str | None:
    if rank is None:
        return None
    return MEDALS_BY_RANK.get(rank)


def parse_tarragona_schedule_page(html: str, edition_id: str, edition_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen_codes = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        match = re.search(r"/?FEN/schedule/event/([^/?#]+)", href)
        if not match:
            continue
        event_code = match.group(1)
        if event_code in seen_codes:
            continue
        seen_codes.add(event_code)
        event_name = link.get_text(" ", strip=True)
        if not event_name:
            continue
        result_url = urljoin(TARRAGONA_BASE, f"en/FEN/final-rank/{event_code}")
        events.append({
            "edition_id": str(edition_id),
            "edition_name": edition_name,
            "event_code": event_code,
            "event_name": event_name,
            "source_id": f"mediterranean:{edition_id}:{event_code}",
            "source_type": "tarragona_html",
            "source_url": result_url,
            "result_url": result_url,
        })
    return events


def _parse_rank(raw: str) -> tuple[int | None, str | None]:
    text = raw.strip()
    if not text:
        return None, None
    medal = MEDAL_WORDS.get(text.lower())
    if medal:
        return medal
    match = re.search(r"\d+", text)
    if not match:
        return None, None
    rank = int(match.group(0))
    return rank, medal_for_rank(rank)


def _extract_country_and_name(name_cell) -> tuple[str | None, str | None, str | None]:
    country = None
    athlete_id = None

    country_link = name_cell.find("a", href=re.compile(r"/entries/noc/[A-Z]{3}"))
    if country_link:
        match = re.search(r"/entries/noc/([A-Z]{3})", country_link["href"])
        country = match.group(1) if match else country_link.get_text(" ", strip=True)

    athlete_link = name_cell.find("a", href=re.compile(r"/athlete/\d+"))
    if athlete_link:
        athlete_match = re.search(r"/athlete/(\d+)", athlete_link["href"])
        athlete_id = athlete_match.group(1) if athlete_match else None
        name = athlete_link.get_text(" ", strip=True)
    else:
        name = name_cell.get_text(" ", strip=True)
        if country and name.startswith(country):
            name = name[len(country):].strip()
        else:
            match = re.match(r"^([A-Z]{3})\s+(.+)$", name)
            if match:
                country = country or match.group(1)
                name = match.group(2).strip()

    return country or None, name or None, athlete_id


def parse_tarragona_final_rank_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = None
    for candidate in soup.find_all("table"):
        header = " ".join(cell.get_text(" ", strip=True).lower() for cell in candidate.find_all("th"))
        if "rank" in header and "name" in header:
            table = candidate
            break
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2 or cells[0].name == "th":
            continue
        rank, medal = _parse_rank(cells[0].get_text(" ", strip=True))
        if rank is None:
            continue
        country, name, athlete_id = _extract_country_and_name(cells[1])
        if not name:
            continue
        rows.append({
            "rank": rank,
            "name": name,
            "country": country,
            "medal": medal,
            "athlete_id": athlete_id,
        })
    return rows


def parse_oran_standings_text(text: str) -> dict | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if "Standings" not in lines or "Rank Name Country" not in lines:
        return None

    standings_idx = lines.index("Standings")
    if standings_idx == 0:
        return None
    event_name = lines[standings_idx - 1]

    event_code_match = re.search(r"\b(FEN[A-Z]+)-+_76I\b", text)
    event_code = event_code_match.group(1) if event_code_match else None

    rows = []
    row_start = lines.index("Rank Name Country") + 1
    row_pattern = re.compile(r"^(Gold|Silver|Bronze|\d+)\s+(.+?)\s+([A-Z]{3})\s+-\s+.+$", re.I)
    for line in lines[row_start:]:
        if line.startswith("FEN") or line.startswith("Data Processing"):
            break
        match = row_pattern.match(line)
        if not match:
            continue
        rank, medal = _parse_rank(match.group(1))
        if rank is None:
            continue
        rows.append({
            "rank": rank,
            "name": re.sub(r"\s+", " ", match.group(2)).strip(),
            "country": match.group(3),
            "medal": medal,
            "athlete_id": None,
        })

    if not rows:
        return None

    return {
        "event_code": event_code,
        "event_name": event_name,
        "rows": rows,
    }


def parse_oran_result_book_pdf(content: bytes) -> list[dict]:
    import pdfplumber

    events = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            event = parse_oran_standings_text(text)
            if event and event.get("event_code"):
                events.append(event)
    return events


def _get(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                return response.text
            if response.status_code == 404:
                return None
            print(f"  HTTP {response.status_code} for {url}")
        except requests.RequestException as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
        time.sleep(2 ** attempt)
    return None


def _get_bytes(urls: list[str], retries: int = 2) -> tuple[bytes | None, str | None]:
    for url in urls:
        for attempt in range(retries):
            try:
                response = requests.get(url, headers=HEADERS, timeout=60)
                if response.status_code == 200 and response.content.startswith(b"%PDF"):
                    return response.content, response.url
                print(f"  HTTP {response.status_code} or non-PDF for {url}")
            except requests.RequestException as exc:
                print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None, None


def fetch_edition_events(edition: dict) -> list[dict]:
    if edition["source_type"] == "tarragona_html":
        html = _get(edition["schedule_url"])
        if not html:
            return []
        return parse_tarragona_schedule_page(html, edition["edition_id"], edition["edition_name"])

    if edition["source_type"] == "oran_pdf":
        content, source_url = _get_bytes(edition["result_book_urls"])
        if not content:
            return []
        events = []
        for parsed in parse_oran_result_book_pdf(content):
            event_code = parsed["event_code"]
            events.append({
                "edition_id": edition["edition_id"],
                "edition_name": edition["edition_name"],
                "event_code": event_code,
                "event_name": parsed["event_name"],
                "source_id": f"mediterranean:{edition['edition_id']}:{event_code}",
                "source_type": "oran_pdf",
                "source_url": source_url,
                "rows": parsed["rows"],
            })
        return events

    return []


def fetch_result_rows(event: dict) -> list[dict]:
    if event.get("rows") is not None:
        return event["rows"]
    if event["source_type"] == "tarragona_html":
        html = _get(event["result_url"])
        if not html:
            return []
        return parse_tarragona_final_rank_page(html)
    return []


def _extract_year(edition_name: str) -> str | None:
    match = re.search(r"\b(\d{4})\b", edition_name)
    return match.group(1) if match else None


def upsert_tournament(event: dict, classification: dict) -> str | None:
    year = _extract_year(event["edition_name"])
    row = {
        "source_id": event["source_id"],
        "name": f"{event['edition_name']} — {event['event_name']}",
        "season": year,
        "type": "mediterranean_games",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": "Senior",
        "country": None,
        "has_results": True,
        "metadata": {
            "source": SOURCE,
            "edition_id": event["edition_id"],
            "edition_name": event["edition_name"],
            "event_code": event["event_code"],
            "event_name": event["event_name"],
            "source_url": event.get("source_url"),
            "source_type": event.get("source_type"),
            "team": classification["team"],
        },
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()  # type: ignore[union-attr]
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {event['source_id']}: {exc}")
        return None


def _match_fencer(name: str | None, country: str | None) -> str | None:
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


def upsert_results(tournament_id: str, event: dict, result_rows: list[dict]) -> int:
    db_rows = []
    for row in result_rows:
        if row.get("rank") is None:
            continue
        db_rows.append({
            "tournament_id": tournament_id,
            "name": row.get("name"),
            "nationality": row.get("country"),
            "rank": row.get("rank"),
            "medal": row.get("medal"),
            "fencer_id": _match_fencer(row.get("name"), row.get("country")),
            "metadata": {
                "source": SOURCE,
                "source_id": event["source_id"],
                "edition_id": event["edition_id"],
                "event_code": event["event_code"],
                "athlete_id": row.get("athlete_id"),
            },
        })

    if not db_rows:
        return 0

    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).execute()  # type: ignore[union-attr]
    written = 0
    for idx in range(0, len(db_rows), 100):
        batch = db_rows[idx:idx + 100]
        try:
            supabase.table("fs_results").insert(batch).execute()  # type: ignore[union-attr]
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed for {event['source_id']}: {exc}")
    return written if written == len(db_rows) else 0


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_mediterranean_games").start()
    try:
        print(f"Mediterranean Games scraper starting — {datetime.now(UTC).isoformat()}")

        structured_editions, skipped_editions = discover_editions()
        for skipped_edition in skipped_editions:
            print(
                f"  Skipping edition {skipped_edition['edition_name']}: "
                f"{skipped_edition['reason']}"
            )

        done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])
        imported_editions = set()
        written = failed = skipped = 0

        for edition in structured_editions:
            print(f"\n  Edition: {edition['edition_name']} ({edition['source_type']})")
            events = fetch_edition_events(edition)
            if not events:
                print("    No structured fencing events found")
                skipped += 1
                continue

            print(f"    {len(events)} events found")
            for event in events:
                if event["source_id"] in done_source_ids:
                    skipped += 1
                    continue

                classification = classify_event(event["event_name"])
                if not classification["weapon"] or not classification["gender"]:
                    print(f"    Skipping unclassifiable: {event['event_name']}")
                    skipped += 1
                    continue

                tournament_id = upsert_tournament(event, classification)
                if not tournament_id:
                    failed += 1
                    time.sleep(REQUEST_DELAY)
                    continue

                rows = fetch_result_rows(event)
                if not rows:
                    print(f"      Missing result table for {event['source_id']}")
                    skipped += 1
                    time.sleep(REQUEST_DELAY)
                    continue

                result_count = upsert_results(tournament_id, event, rows)
                if result_count == 0:
                    print(f"      Insert failed or partial for {event['source_id']}")
                    failed += 1
                    time.sleep(REQUEST_DELAY)
                    continue

                print(f"      {event['event_name']}: {result_count} results inserted")
                done_source_ids.add(event["source_id"])
                set_state(SOURCE, "done_source_ids", sorted(done_source_ids))
                imported_editions.add(event["edition_id"])
                written += 1
                time.sleep(REQUEST_DELAY)

            time.sleep(REQUEST_DELAY)

        metadata = {
            "editions_found": len(structured_editions),
            "editions_imported": len(imported_editions),
            "skipped_editions": skipped_editions,
        }
        set_state(SOURCE, "last_run", {**metadata, "updated_at": datetime.now(UTC).isoformat()})
        run_log.complete(written=written, failed=failed, skipped=skipped, metadata=metadata)
        print(
            f"\nDone — events_written={written}, skipped={skipped}, failed={failed}; "
            f"editions_imported={len(imported_editions)}/{len(structured_editions)}"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

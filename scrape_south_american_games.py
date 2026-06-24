"""
South American Games fencing results scraper.

Probe notes (verified 2026-06-01):
  - Olympedia has Olympic/YOG fencing pages, but no ODESUR South American Games edition model.
  - odesur.org is a Squarespace news/event site and does not expose historical fencing result tables.
  - ASU2022 official result URLs referenced by public records no longer resolve.
  - Public structured medalist tables currently exist for 2010 and 2022; the scraper imports those
    editions and keeps source metadata so official URLs can be added later without changing IDs.
"""
import os
import re
import time
import unicodedata
from datetime import UTC, datetime, timezone
from typing import Any

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

SOURCE = "south_american_games"
REQUEST_DELAY = 2.0
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,*/*;q=0.8",
}

KNOWN_EDITIONS: list[dict[str, Any]] = [
    {"edition_id": "1978", "edition_name": "La Paz 1978", "year": "1978", "source_url": None},
    {"edition_id": "1982", "edition_name": "Rosario 1982", "year": "1982", "source_url": None},
    {"edition_id": "1986", "edition_name": "Santiago 1986", "year": "1986", "source_url": None},
    {"edition_id": "1990", "edition_name": "Lima 1990", "year": "1990", "source_url": None},
    {"edition_id": "1994", "edition_name": "Valencia 1994", "year": "1994", "source_url": None},
    {"edition_id": "1998", "edition_name": "Cuenca 1998", "year": "1998", "source_url": None},
    {"edition_id": "2002", "edition_name": "Brazil 2002", "year": "2002", "source_url": None},
    {"edition_id": "2006", "edition_name": "Buenos Aires 2006", "year": "2006", "source_url": None},
    {
        "edition_id": "2010",
        "edition_name": "Medellin 2010",
        "year": "2010",
        "source_url": "https://en.wikipedia.org/wiki/Fencing_at_the_2010_South_American_Games",
    },
    {"edition_id": "2014", "edition_name": "Santiago 2014", "year": "2014", "source_url": None},
    {"edition_id": "2018", "edition_name": "Cochabamba 2018", "year": "2018", "source_url": None},
    {
        "edition_id": "2022",
        "edition_name": "Asuncion 2022",
        "year": "2022",
        "source_url": "https://en.wikipedia.org/wiki/Fencing_at_the_2022_South_American_Games",
    },
]

COUNTRY_TO_NOC = {
    "argentina": "ARG",
    "aruba": "ARU",
    "bolivia": "BOL",
    "brazil": "BRA",
    "brasil": "BRA",
    "chile": "CHI",
    "colombia": "COL",
    "curacao": "CUR",
    "curazao": "CUR",
    "ecuador": "ECU",
    "guyana": "GUY",
    "panama": "PAN",
    "paraguay": "PAR",
    "peru": "PER",
    "suriname": "SUR",
    "surinam": "SUR",
    "uruguay": "URU",
    "venezuela": "VEN",
}

MEDAL_TO_RANK = {"Gold": 1, "Silver": 2, "Bronze": 3}


def _strip_accents(value):
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _norm(value):
    return re.sub(r"\s+", " ", _strip_accents(value).lower()).strip()


def _slug(value):
    value = _norm(value)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def classify_event(event_name):
    """Return {weapon, gender, team} for English, Spanish, or Portuguese fencing labels."""
    text = _norm(event_name)
    weapon = None
    if re.search(r"\b(epee|epée|espada)\b", text):
        weapon = "Epee"
    elif re.search(r"\b(foil|florete|fleuret)\b", text):
        weapon = "Foil"
    elif re.search(r"\b(sabre|saber|sable)\b", text):
        weapon = "Sabre"

    gender = None
    if re.search(r"\b(women|woman|female|femenino|femenina|feminino|feminina|mujeres|damas)\b", text):
        gender = "Women"
    elif re.search(r"\b(men|man|male|masculino|masculina|hombres|homens)\b", text):
        gender = "Men"

    team = bool(re.search(r"\b(team|teams|equipo|equipos|equipe|equipes)\b", text))
    return {"weapon": weapon, "gender": gender, "team": team}


def _event_code(classification, fallback):
    weapon = {"Epee": "epee", "Foil": "foil", "Sabre": "sabre"}.get(classification.get("weapon"))
    gender = {"Men": "men", "Women": "women"}.get(classification.get("gender"))
    if weapon and gender:
        return f"{gender}_{weapon}_{'team' if classification.get('team') else 'individual'}"
    return _slug(fallback)


def _clean_cell_text(cell):
    for tag in cell.find_all(["sup", "style"]):
        tag.decompose()
    text = cell.get_text(" ", strip=True)
    text = re.sub(r"\[\s*\d+\s*\]", "", text)
    text = re.sub(r"\bdetails\b", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _split_cell_lines(cell):
    html = re.sub(r"<br\s*/?>", "\n", str(cell), flags=re.I)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["sup", "style"]):
        tag.decompose()
    return [re.sub(r"\s+", " ", p).strip() for p in soup.get_text("\n").split("\n") if p.strip()]


def _normalize_country(value):
    if not value:
        return None
    value = re.sub(r"\([^)]*\)", "", value).strip()
    code = re.sub(r"[^A-Za-z]", "", value).upper()
    if len(code) == 3:
        return code
    return COUNTRY_TO_NOC.get(_norm(value))


def _normalize_medal(value):
    text = _norm(value)
    if text in {"gold", "oro", "ouro"}:
        return "Gold"
    if text in {"silver", "plata", "prata"}:
        return "Silver"
    if text in {"bronze", "bronce"}:
        return "Bronze"
    return None


def _parse_rank(value):
    text = _norm(value)
    medal = _normalize_medal(text)
    if medal:
        return MEDAL_TO_RANK[medal]
    m = re.search(r"\d+", text)
    return int(m.group(0)) if m else None


def _find_header_index(headers, options):
    for i, header in enumerate(headers):
        normalized = _norm(header)
        if any(option in normalized for option in options):
            return i
    return None


def parse_result_rows(html):
    """Parse a generic ODESUR-style result table into placement rows."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if not trs:
            continue
        headers = [_clean_cell_text(c) for c in trs[0].find_all(["th", "td"])]
        rank_idx = _find_header_index(headers, ["rank", "pos", "puesto", "clasificacion", "clasificación"])
        name_idx = _find_header_index(headers, ["athlete", "atleta", "competitor", "competidor", "name", "nombre", "team", "equipo"])
        country_idx = _find_header_index(headers, ["country", "pais", "país", "nation", "noc", "nacionalidad"])
        medal_idx = _find_header_index(headers, ["medal", "medalla"])
        if rank_idx is None or name_idx is None:
            continue

        for tr in trs[1:]:
            cells = tr.find_all(["td", "th"], recursive=False)
            if len(cells) <= max(rank_idx, name_idx):
                continue
            rank = _parse_rank(_clean_cell_text(cells[rank_idx]))
            if rank is None:
                continue
            medal = None
            if medal_idx is not None and medal_idx < len(cells):
                medal = _normalize_medal(_clean_cell_text(cells[medal_idx]))
            if medal is None:
                medal = {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)

            names = _split_cell_lines(cells[name_idx])
            countries = _split_cell_lines(cells[country_idx]) if country_idx is not None and country_idx < len(cells) else []
            if not names:
                continue
            for idx, name in enumerate(names):
                country = countries[idx] if idx < len(countries) else (countries[0] if countries else None)
                athlete_link = cells[name_idx].find("a", href=re.compile(r"/athletes?/(\d+)"))
                athlete_match = re.search(r"/athletes?/(\d+)", athlete_link["href"]) if athlete_link else None
                athlete_id = athlete_match.group(1) if athlete_match else None
                rows.append(
                    {
                        "rank": rank,
                        "name": name,
                        "country": _normalize_country(country) or country,
                        "medal": medal,
                        "athlete_id": athlete_id,
                    }
                )
    return rows


def _nearest_gender_hint(table):
    heading = table.find_previous(["h2", "h3", "h4"])
    while heading:
        text = _norm(heading.get_text(" ", strip=True))
        if re.search(r"\b(men|masculinos|masculino|hombres|homens)\b", text):
            return "Men"
        if re.search(r"\b(women|femeninos|femenino|femininos|feminino|mujeres|damas)\b", text):
            return "Women"
        heading = heading.find_previous(["h2", "h3", "h4"])
    return None


def _wiki_links(cell):
    links = []
    for link in cell.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(" ", strip=True)
        if not text or href.startswith("#") or "cite_note" in href:
            continue
        if text.lower() in {"edit", "details"}:
            continue
        links.append(text)
    return links


def _rows_from_medal_cell(cell, rank, medal):
    links = _wiki_links(cell)
    lines = _split_cell_lines(cell)
    line_countries = [(i, _normalize_country(line)) for i, line in enumerate(lines) if _normalize_country(line)]
    if not links:
        if line_countries:
            first_country_idx, country = line_countries[0]
            names = [p for i, p in enumerate(lines) if i != first_country_idx and not _normalize_country(p)]
        else:
            country = None
            names = lines
        return [{"rank": rank, "name": name, "country": country, "medal": medal, "athlete_id": None} for name in names if name]

    country_positions = [(i, _normalize_country(text)) for i, text in enumerate(links) if _normalize_country(text)]
    if not country_positions:
        names = links
        country = line_countries[-1][1] if line_countries else None
    elif country_positions[0][0] == 0:
        country = country_positions[0][1]
        names = [text for text in links[1:] if not _normalize_country(text)]
    else:
        country_idx, country = country_positions[-1]
        names = [text for i, text in enumerate(links[:country_idx]) if not _normalize_country(text)]

    if not names and country:
        names = [country]
    return [{"rank": rank, "name": name, "country": country, "medal": medal, "athlete_id": None} for name in names if name]


def _is_medalist_table(table):
    first_row = table.find("tr")
    if not first_row:
        return False
    headers = [_norm(_clean_cell_text(c)) for c in first_row.find_all(["th", "td"], recursive=False)]
    return (
        len(headers) >= 4
        and any("event" in h or "prueba" in h for h in headers)
        and any("gold" in h or "oro" in h for h in headers)
        and any("silver" in h or "plata" in h for h in headers)
        and any("bronze" in h or "bronce" in h for h in headers)
    )


def parse_medalist_events(html, edition):
    """Parse public South American Games medalist tables into event dicts with result rows."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for table in soup.find_all("table"):
        if not _is_medalist_table(table):
            continue
        gender_hint = _nearest_gender_hint(table)
        current_event = None
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all(["td", "th"], recursive=False)
            if len(cells) >= 4:
                label = _clean_cell_text(cells[0])
                if not label:
                    continue
                event_label = f"{label} {gender_hint or ''}".strip()
                classification = classify_event(event_label)
                if not classification["weapon"] or not classification["gender"]:
                    current_event = None
                    continue
                event_name = f"{label}, {classification['gender']}"
                current_event = {
                    "edition_id": edition["edition_id"],
                    "edition_name": edition["edition_name"],
                    "year": edition.get("year"),
                    "event_name": event_name,
                    "event_code": _event_code(classification, event_name),
                    "classification": classification,
                    "source_url": edition.get("source_url"),
                    "rows": [],
                }
                current_event["rows"].extend(_rows_from_medal_cell(cells[1], 1, "Gold"))
                current_event["rows"].extend(_rows_from_medal_cell(cells[2], 2, "Silver"))
                current_event["rows"].extend(_rows_from_medal_cell(cells[3], 3, "Bronze"))
                events.append(current_event)
            elif len(cells) == 1 and current_event and not cells[0].get("colspan"):
                current_event["rows"].extend(_rows_from_medal_cell(cells[0], 3, "Bronze"))
    return events


def build_tournament_row(event, classification):
    source_id = f"south_american_games:{event['edition_id']}:{event['event_code']}"
    return {
        "source_id": source_id,
        "name": f"{event['edition_name']} - {event['event_name']}",
        "season": event.get("year"),
        "type": "south_american_games",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": "Senior",
        "country": None,
        "has_results": True,
        "metadata": {
            "edition_id": event["edition_id"],
            "edition_name": event["edition_name"],
            "event_code": event["event_code"],
            "event_name": event["event_name"],
            "team": classification["team"],
            "source_url": event.get("source_url"),
        },
    }


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            result = requests.get(url, headers=HEADERS, timeout=20)
            if result.status_code == 200:
                return result.text
            if result.status_code == 404:
                return None
            print(f"  HTTP {result.status_code} for {url}")
            if result.status_code in (429, 500, 502, 503):
                time.sleep(2**attempt * (10 if result.status_code == 429 else 2))
            else:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2**attempt)
    return None


def discover_events():
    """Fetch all currently public structured South American Games fencing editions."""
    all_events = []
    for edition in KNOWN_EDITIONS:
        url = edition.get("source_url")
        if not url:
            continue
        print(f"  Probing {edition['edition_name']}: {url}")
        html = _get(url)
        if not html:
            print("    no structured page available")
            continue
        events = parse_medalist_events(html, edition)
        print(f"    {len(events)} events found")
        all_events.extend(events)
        time.sleep(REQUEST_DELAY)
    return all_events


def _match_fencer(name, country):
    try:
        rows = _db().table("fs_fencers").select("id").ilike("name", name).eq("country", country).limit(2).execute().data
        return rows[0]["id"] if len(rows) == 1 else None
    except Exception:
        return None


def upsert_tournament(event):
    row = build_tournament_row(event, event["classification"])
    try:
        result = _db().table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {row['source_id']}: {exc}")
        return None


def upsert_results(tournament_id, result_rows):
    db_rows = []
    for row in result_rows:
        if row["rank"] is None:
            continue
        fencer_id = _match_fencer(row["name"], row["country"]) if row.get("name") and row.get("country") else None
        db_rows.append(
            {
                "tournament_id": tournament_id,
                "name": row["name"],
                "nationality": row.get("country"),
                "rank": row["rank"],
                "medal": row.get("medal"),
                "fencer_id": fencer_id,
                "metadata": {"south_american_games_source": SOURCE, "athlete_id": row.get("athlete_id")},
            }
        )
    if not db_rows:
        return 0
    _db().table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i : i + 100]
        try:
            _db().table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    return written if written == len(db_rows) else 0


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_south_american_games").start()
    try:
        print(f"South American Games scraper starting - {datetime.now(UTC).isoformat()}")
        done_ids = set(get_state(SOURCE, "done_event_ids") or [])
        events = discover_events()
        written = failed = skipped = 0

        for event in events:
            event_id = f"{event['edition_id']}:{event['event_code']}"
            if event_id in done_ids:
                skipped += 1
                continue
            if not event["rows"]:
                print(f"  No result rows found for {event_id}")
                failed += 1
                continue

            tournament_id = upsert_tournament(event)
            if not tournament_id:
                failed += 1
                continue

            count = upsert_results(tournament_id, event["rows"])
            if count == 0:
                failed += 1
                continue

            print(f"  {event_id}: {count} rows inserted")
            done_ids.add(event_id)
            set_state(SOURCE, "done_event_ids", list(done_ids))
            written += 1
            time.sleep(REQUEST_DELAY)

        run_log.complete(
            written=written,
            failed=failed,
            skipped=skipped,
            metadata={"editions_with_public_structured_sources": len([e for e in KNOWN_EDITIONS if e.get("source_url")])},
        )
        print(f"Done - written={written}, skipped={skipped}, failed={failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

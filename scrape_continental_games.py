"""
Continental multi-sport Games fencing results scraper.

Sources verified 2026-06-01:
  - Olympedia manual medal lists:
    Pan American Games: /lists/11/manual
    Asian Games: /lists/114/manual
    European Games: /lists/143/manual
  - African Games 2019 official result book PDF:
    /resultats/resJA2019/pdf/JA2019/FE/JA2019_FE_C99_FE0000000.pdf
"""
import io
import os
import re
import time
import unicodedata
from collections import OrderedDict
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

OLYMPEDIA_BASE = "https://www.olympedia.org"
SOURCE = "continental_games"
REQUEST_DELAY = 1.0
ATHLETE_DELAY = 0.2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}

MEDAL_RANK = {"Gold": 1, "Silver": 2, "Bronze": 3}

WEAPON_PATTERNS = [
    (re.compile(r"\b(epee|epée|épée)\b", re.I), "Epee"),
    (re.compile(r"\b(foil|fleuret)\b", re.I), "Foil"),
    (re.compile(r"\b(sabre|saber|sabr)\b", re.I), "Sabre"),
]

GENDER_PATTERNS = [
    (re.compile(r"\b(women|women's|female|femmes|feminin|féminin|dames)\b", re.I), "Women"),
    (re.compile(r"\b(men|men's|male|hommes|masculin)\b", re.I), "Men"),
]

COUNTRY_NAME_TO_CODE = {
    "Algeria": "ALG",
    "Angola": "ANG",
    "Cote D'Ivoire": "CIV",
    "Cote d'Ivoire": "CIV",
    "Democratic Republic of the Congo": "COD",
    "Egypt": "EGY",
    "Ghana": "GHA",
    "Libya": "LBA",
    "Madagascar": "MAD",
    "Mali": "MLI",
    "Mauritius": "MRI",
    "Morocco": "MAR",
    "Namibia": "NAM",
    "Senegal": "SEN",
    "Togo": "TOG",
    "Tunisia": "TUN",
}

GAMES_CONFIGS = {
    "pan_american_games": {
        "list_id": 11,
        "min_year": 1951,
        "allowed_years": None,
    },
    "asian_games": {
        "list_id": 114,
        "min_year": 1974,
        "allowed_years": None,
    },
    "european_games": {
        "list_id": 143,
        "min_year": None,
        "allowed_years": {2015, 2019, 2023},
    },
}

AFRICAN_GAMES_2019_PDF_URL = (
    "https://www.jar2019.ma/resultats/resJA2019/pdf/JA2019/FE/"
    "JA2019_FE_C99_FE0000000.pdf"
)


def classify_event(event_name):
    """Return {weapon, gender, team} classification for normalized event names."""
    weapon = next((w for pat, w in WEAPON_PATTERNS if pat.search(event_name)), None)
    gender = next((g for pat, g in GENDER_PATTERNS if pat.search(event_name)), None)
    team = bool(re.search(r"\b(team|par équipe|par equipe)\b", event_name, re.I))
    return {"weapon": weapon, "gender": gender, "team": team}


def parse_olympedia_list_page(
    html,
    games_type,
    min_year=None,
    allowed_years=None,
    athlete_gender_by_id=None,
    gender_resolver=None,
):
    """Parse one Olympedia manual-list HTML page into medal-placement rows."""
    if athlete_gender_by_id is None:
        athlete_gender_by_id = {}
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 6:
            continue
        if cells[2].get_text(" ", strip=True) != "FEN":
            continue

        athlete_link = cells[0].find("a", href=re.compile(r"/athletes/\d+"))
        athlete_id = None
        if athlete_link:
            athlete_match = re.search(r"/athletes/(\d+)", athlete_link["href"])
            athlete_id = athlete_match.group(1) if athlete_match else None
        athlete_name = cells[0].get_text(" ", strip=True)
        country = _extract_country_code(cells[1].get_text(" ", strip=True))
        notes = cells[5].get_text(" ", strip=True)
        mentions = [
            mention for mention in _parse_olympedia_fen_notes(notes)
            if not (min_year is not None and mention["year"] < min_year)
            and not (allowed_years is not None and mention["year"] not in allowed_years)
        ]
        if not mentions:
            continue

        athlete_gender = athlete_gender_by_id.get(athlete_id)
        if not athlete_gender and athlete_id and gender_resolver:
            athlete_gender = gender_resolver(athlete_id)
            athlete_gender_by_id[athlete_id] = athlete_gender

        for mention in mentions:
            year = mention["year"]
            event = _normalize_event_fragment(mention["event_fragment"], athlete_gender)
            if not event:
                continue

            rows.append({
                "games_type": games_type,
                "edition_id": _slugify(mention["edition_name"]),
                "edition_name": mention["edition_name"],
                "year": year,
                "event_code": event["event_code"],
                "event_name": event["event_name"],
                "team": event["team"],
                "athlete_name": athlete_name,
                "country": country,
                "rank": MEDAL_RANK[mention["medal"]],
                "medal": mention["medal"],
                "source": "olympedia",
                "source_athlete_id": athlete_id,
                "source_note": notes,
            })
    return rows


def parse_african_pdf_final_standings_text(text, edition_name="2019 Rabat"):
    """Parse one official African Games final-standings page extracted by pdfplumber."""
    event_name = _extract_pdf_event_name(text)
    if not event_name:
        return []

    classification = classify_event(event_name)
    if not classification["weapon"] or not classification["gender"]:
        return []

    year = _extract_year(edition_name)
    event_code = _event_code(classification)
    is_team = classification["team"]
    header_seen = False
    rows = []

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        if line.startswith("Rank "):
            header_seen = True
            continue
        if not header_seen:
            continue
        if line in {"Finals", "Semifinals", "Quarterfinals", "Table of 16", "Table of 32", "Classification Matches", "Round of Pools"}:
            continue
        if line.startswith("FEN") or line.startswith("Report Created"):
            break

        parsed = _parse_african_team_line(line) if is_team else _parse_african_individual_line(line)
        if not parsed:
            continue
        rank, name, country, medal = parsed
        rows.append({
            "games_type": "african_games",
            "edition_id": _slugify(edition_name),
            "edition_name": edition_name,
            "year": year,
            "event_code": event_code,
            "event_name": event_name,
            "team": is_team,
            "athlete_name": name,
            "country": country,
            "rank": rank,
            "medal": medal,
            "source": "african_games_official_pdf",
            "source_athlete_id": None,
            "source_note": None,
        })

    return rows


def group_rows_by_event(rows):
    """Return [(event, result_rows)] preserving source order and exact duplicate rows once."""
    grouped: OrderedDict[tuple[Any, Any, Any], list[Any]] = OrderedDict()
    seen = set()
    for row in rows:
        key = (row["games_type"], row["edition_id"], row["event_code"])
        event = {
            "games_type": row["games_type"],
            "edition_id": row["edition_id"],
            "edition_name": row["edition_name"],
            "event_code": row["event_code"],
            "event_name": row["event_name"],
            "year": row["year"],
            "source": row["source"],
        }
        grouped.setdefault(key, [event, []])
        dedupe_key = (
            key,
            row["athlete_name"],
            row["country"],
            row["rank"],
            row["medal"],
            row.get("source_athlete_id"),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        grouped[key][1].append(row)
    return list(grouped.values())


def build_tournament_row(event):
    classification = classify_event(event["event_name"])
    return {
        "source_id": _source_id(event),
        "name": f"{event['edition_name']} — {event['event_name']}",
        "season": str(event["year"]) if event.get("year") else None,
        "type": event["games_type"],
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": "Senior",
        "country": None,
        "has_results": True,
        "metadata": {
            "games_type": event["games_type"],
            "edition_id": event["edition_id"],
            "edition_name": event["edition_name"],
            "event_code": event["event_code"],
            "event_name": event["event_name"],
            "team": classification["team"],
            "source": event.get("source"),
        },
    }


def discover_all_results():
    rows = []
    for games_type, config in GAMES_CONFIGS.items():
        rows.extend(discover_olympedia_results(games_type, config))
    rows.extend(discover_african_games_results())
    return rows


def discover_olympedia_results(games_type, config):
    athlete_gender_cache: dict[Any, Any] = {}
    rows = []
    list_id = config["list_id"]
    first_html = _get(f"{OLYMPEDIA_BASE}/lists/{list_id}/manual")
    if not first_html:
        return []

    rows.extend(parse_olympedia_list_page(
        first_html,
        games_type=games_type,
        min_year=config.get("min_year"),
        allowed_years=config.get("allowed_years"),
        athlete_gender_by_id=athlete_gender_cache,
        gender_resolver=fetch_athlete_gender,
    ))

    page_count = _max_page_number(first_html)
    for page in range(2, page_count + 1):
        time.sleep(REQUEST_DELAY)
        html = _get(f"{OLYMPEDIA_BASE}/lists/{list_id}/manual?page={page}")
        if not html:
            continue
        rows.extend(parse_olympedia_list_page(
            html,
            games_type=games_type,
            min_year=config.get("min_year"),
            allowed_years=config.get("allowed_years"),
            athlete_gender_by_id=athlete_gender_cache,
            gender_resolver=fetch_athlete_gender,
        ))
    return rows


def discover_african_games_results():
    pdf_bytes = _get_bytes(AFRICAN_GAMES_2019_PDF_URL)
    if not pdf_bytes:
        return []

    import pdfplumber

    rows = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "Final Standings" not in text:
                continue
            rows.extend(parse_african_pdf_final_standings_text(text, edition_name="2019 Rabat"))
    return rows


def fetch_athlete_gender(athlete_id):
    html = _get(f"{OLYMPEDIA_BASE}/athletes/{athlete_id}")
    if not html:
        return None
    time.sleep(ATHLETE_DELAY)
    return parse_athlete_gender_page(html)


def parse_athlete_gender_page(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    m = re.search(r"\bSex\s+(Male|Female)\b", text, re.I)
    if not m:
        return None
    return "Women" if m.group(1).lower() == "female" else "Men"


def upsert_tournament(event):
    row = build_tournament_row(event)
    try:
        result = _db().table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
        if result.data and result.data[0].get("id"):
            return result.data[0]["id"]
        selected = (
            _db().table("fs_tournaments")
            .select("id")
            .eq("source_id", row["source_id"])
            .limit(1)
            .execute()
        )
        return selected.data[0]["id"] if selected.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {row['source_id']}: {exc}")
        return None


def upsert_results(tournament_id, result_rows):
    db_rows = []
    for row in result_rows:
        if row["rank"] is None:
            continue
        fencer_id = None
        if not row.get("team") and row.get("athlete_name") and row.get("country"):
            fencer_id = _match_fencer(row["athlete_name"], row["country"])
        db_rows.append({
            "tournament_id": tournament_id,
            "name": row["athlete_name"],
            "nationality": row["country"],
            "rank": row["rank"],
            "medal": row["medal"],
            "fencer_id": fencer_id,
            "metadata": {
                "games_type": row["games_type"],
                "edition_id": row["edition_id"],
                "edition_name": row["edition_name"],
                "event_code": row["event_code"],
                "team": row["team"],
                "source": row["source"],
                "source_athlete_id": row.get("source_athlete_id"),
                "source_note": row.get("source_note"),
            },
        })
    if not db_rows:
        return 0

    _db().table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    written = 0
    for i in range(0, len(db_rows), 100):
        batch = db_rows[i:i + 100]
        try:
            _db().table("fs_results").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  Results insert batch failed: {exc}")
    return written if written == len(db_rows) else 0


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_continental_games").start()
    try:
        print(f"Continental Games scraper starting — {datetime.now(UTC).isoformat()}")
        done_source_ids = set(get_state(SOURCE, "done_source_ids") or [])
        all_rows = discover_all_results()
        events = group_rows_by_event(all_rows)
        print(f"  {len(events)} event result sets discovered")

        written = failed = skipped = 0
        for event, result_rows in events:
            source_id = _source_id(event)
            if source_id in done_source_ids:
                skipped += 1
                continue

            classification = classify_event(event["event_name"])
            if not classification["weapon"] or not classification["gender"]:
                skipped += 1
                continue

            tournament_id = upsert_tournament(event)
            if not tournament_id:
                failed += 1
                continue

            n = upsert_results(tournament_id, result_rows)
            if n == 0:
                failed += 1
                continue

            done_source_ids.add(source_id)
            set_state(SOURCE, "done_source_ids", list(done_source_ids))
            written += 1
            print(f"  {source_id}: {n} result rows")

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"Done — written={written}, skipped={skipped}, failed={failed}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


def _parse_olympedia_fen_notes(notes):
    mentions = []
    for segment in re.split(r";\s*", notes):
        m = re.search(r"\b(\d{4})\s+(.+?)\s+FEN\s+(.+)$", segment)
        if not m:
            continue
        year = int(m.group(1))
        edition_name = f"{year} {m.group(2).strip()}"
        details = m.group(3).strip()
        for medal, event_fragment in _parse_medal_details(details):
            mentions.append({
                "year": year,
                "edition_name": edition_name,
                "medal": medal,
                "event_fragment": event_fragment,
            })
    return mentions


def _parse_medal_details(details):
    details = _strip_parentheticals(details)
    pieces = re.split(r"\b(gold|silver|bronze):", details, flags=re.I)
    parsed = []
    for idx in range(1, len(pieces), 2):
        medal = pieces[idx].capitalize()
        event_text = pieces[idx + 1]
        for fragment in re.split(r"\s*,\s*|\s+\band\b\s+", event_text):
            fragment = fragment.strip(" .")
            if fragment:
                parsed.append((medal, fragment))
    return parsed


def _normalize_event_fragment(fragment, athlete_gender=None):
    cleaned = _strip_parentheticals(fragment).strip()
    weapon = next((w for pat, w in WEAPON_PATTERNS if pat.search(cleaned)), None)
    if not weapon:
        return None
    explicit = classify_event(cleaned)
    gender = explicit["gender"] or athlete_gender
    if not gender:
        return None
    team = explicit["team"]
    event_kind = "Team" if team else "Individual"
    event_name = f"{gender}'s {weapon} {event_kind}"
    return {
        "event_name": event_name,
        "event_code": _event_code({"gender": gender, "weapon": weapon, "team": team}),
        "team": team,
    }


def _extract_pdf_event_name(text):
    normalized = " ".join(text.split())
    m = re.search(r"Fencing\s*\|\s*Escrime\s*\|\s*(.*?)\s*\|", normalized)
    if m:
        raw = m.group(1).strip()
    else:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        raw = None
        for idx, line in enumerate(lines[:-1]):
            if line == "Fencing" and lines[idx + 1] == "Escrime" and idx + 2 < len(lines):
                raw = lines[idx + 2]
                break
        if not raw:
            return None
    classification = classify_event(raw)
    if not classification["weapon"] or not classification["gender"]:
        return None
    event_kind = "Team" if classification["team"] else "Individual"
    return f"{classification['gender']}'s {classification['weapon']} {event_kind}"


def _parse_african_individual_line(line):
    m = re.match(r"^(\d+)\s+(.+?)\s+([A-Z]{3})\s+-\s+(.+?)(?:\s+(Gold|Silver|Bronze))?$", line)
    if not m:
        return None
    rank = int(m.group(1))
    name = m.group(2).strip()
    country = m.group(3).strip()
    medal = m.group(5)
    return rank, name, country, medal


def _parse_african_team_line(line):
    m = re.match(r"^(\d+)\s+(.+?)(?:\s+(Gold|Silver|Bronze))?$", line)
    if not m:
        return None
    rank = int(m.group(1))
    team_name = m.group(2).strip()
    medal = m.group(3)
    country = COUNTRY_NAME_TO_CODE.get(team_name, team_name)
    return rank, team_name, country, medal


def _event_code(classification):
    gender = classification["gender"].lower()
    weapon = classification["weapon"].lower()
    kind = "team" if classification["team"] else "individual"
    return f"{gender}_{weapon}_{kind}"


def _source_id(event):
    return f"{event['games_type']}:{event['edition_id']}:{event['event_code']}"


def _extract_country_code(text):
    m = re.search(r"\b[A-Z]{3}\b", text)
    return m.group(0) if m else text.strip() or None


def _strip_parentheticals(text):
    return re.sub(r"\s*\([^)]*\)", "", text)


def _slugify(text):
    text = text.replace("ı", "i").replace("İ", "I")
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug


def _extract_year(text):
    m = re.search(r"\b(\d{4})\b", text)
    return int(m.group(1)) if m else None


def _max_page_number(html):
    return max([int(m.group(1)) for m in re.finditer(r"page=(\d+)", html)] or [1])


def _match_fencer(name, country):
    try:
        rows = (
            _db().table("fs_fencers")
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


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                return response.text
            if response.status_code == 404:
                return None
            if response.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt * (10 if response.status_code == 429 else 2))
            else:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def _get_bytes(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=60)
            if response.status_code == 200:
                return response.content
            if response.status_code == 404:
                return None
            if response.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt * (10 if response.status_code == 429 else 2))
            else:
                return None
        except Exception as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


if __name__ == "__main__":
    main()

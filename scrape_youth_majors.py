"""
Youth and junior major results scraper.

Sources:
- FIE /competitions/search for Cadet/Junior World Championships.
- Olympedia pages for European Youth Olympic Festival fencing, if Olympedia
  exposes EYOF edition pages or they are supplied with EYOF_OLYMPEDIA_EDITIONS.
"""

import calendar
import json
import os
import re
import time
import unicodedata
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

SOURCE = "youth_majors"
FIE_BASE = "https://fie.org"
OLYMPEDIA_BASE = "https://www.olympedia.org"
FIE_EARLIEST_SEASON = int(os.environ.get("YOUTH_MAJORS_FIE_EARLIEST_SEASON", "2003"))
REQUEST_DELAY = float(os.environ.get("YOUTH_MAJORS_REQUEST_DELAY", "1.0"))
BATCH_SIZE = 100

COMP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://fie.org/competitions",
}

OLYMPEDIA_HEADERS = {
    "User-Agent": COMP_HEADERS["User-Agent"],
    "Accept": "text/html,*/*;q=0.8",
}

WEAPON_MAP = {"epee": "Epee", "foil": "Foil", "sabre": "Sabre"}
GENDER_MAP = {"men": "Men", "women": "Women"}
CATEGORY_MAP = {"senior": "Senior", "junior": "Junior", "cadet": "Cadet", "veteran": "Veteran"}

YOUTH_WORLD_RE = re.compile(
    r"("
    r"\bchamp(?:ionnats?|ionnat)?\s+du\s+monde\s+juniors?-cadets?\b"
    r"|\bworld\s+championships?\b.*\b(junior|cadet)\b"
    r"|\b(junior|cadet)\b.*\bworld\s+championships?\b"
    r")",
    re.I,
)

EYOF_RE = re.compile(r"European Youth Olympic (Festival|Days)|\bEYOF\b", re.I)
RESULT_LINK_RE = re.compile(r"^/results/\d+$")

WEAPON_PATTERNS = [
    (re.compile(r"\bépée\b|\bepee\b", re.I), "Epee"),
    (re.compile(r"\bfoil\b", re.I), "Foil"),
    (re.compile(r"\bsabre\b|\bsaber\b", re.I), "Sabre"),
]
GENDER_PATTERNS = [
    (re.compile(r"\bwomen\b|\bwomen's\b|\bfemmes\b|\bgirls\b|\bgirl's\b", re.I), "Women"),
    (re.compile(r"\bmen\b|\bmen's\b|\bboys\b|\bboy's\b", re.I), "Men"),
]


def clean_text(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def title_case(value):
    text = clean_text(value)
    return text.title() if text else None


def normalize_fie_date(date_str):
    if not date_str:
        return None
    try:
        parts = str(date_str).split("-")
        if len(parts) != 3 or len(parts[2]) != 4:
            return None
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
        return None


def normalize_country(value):
    text = clean_text(value)
    if not text:
        return None
    key = text.upper().replace(".", "")
    key = re.sub(r"\s+", " ", key)
    country_map = {
        "_AIN": "Russia",
        "AIN_": "Russia",
        "AIN": "Russia",
        "INDIVIDUAL NEUTRAL ATHLETES": "Russia",
        "FIE": "FIE",
        "USA": "United States",
        "US": "United States",
        "UNITED STATES": "United States",
        "UNITED STATES OF AMERICA": "United States",
        "GBR": "Great Britain",
        "GREAT BRITAIN": "Great Britain",
        "KOREA": "South Korea",
        "KOR": "South Korea",
        "HONG KONG, CHINA": "Hong Kong",
        "HONG KONG CHINA": "Hong Kong",
        "MACAO, CHINA": "Macau",
        "MACAO CHINA": "Macau",
        "TURKIYE": "Turkey",
        "TÜRKIYE": "Turkey",
        "TÜRKİYE": "Turkey",
        "COTE D'IVOIRE": "Côte d'Ivoire",
        "COTE DIVOIRE": "Côte d'Ivoire",
    }
    return country_map.get(key, title_case(text))


def normalize_person_name(value):
    text = clean_text(value)
    if not text:
        return None
    parts = text.split()
    leading = 0
    while leading < len(parts) and any(ch.isalpha() for ch in parts[leading]) and parts[leading].upper() == parts[leading]:
        leading += 1
    if 0 < leading < len(parts):
        last = title_case(" ".join(parts[:leading]))
        first = title_case(" ".join(parts[leading:]))
        return first if first.lower() == last.lower() else f"{first} {last}"
    trailing = 0
    while trailing < len(parts) and any(ch.isalpha() for ch in parts[-1 - trailing]) and parts[-1 - trailing].upper() == parts[-1 - trailing]:
        trailing += 1
    if 0 < trailing < len(parts):
        first = title_case(" ".join(parts[:-trailing]))
        last = title_case(" ".join(parts[-trailing:]))
        return first if first.lower() == last.lower() else f"{first} {last}"
    return title_case(text)


def to_int(value):
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except Exception:
        return None


def _strip_accents(value):
    return "".join(c for c in unicodedata.normalize("NFD", value or "") if unicodedata.category(c) != "Mn")


def is_youth_world_championship(comp):
    category = (comp.get("category") or "").lower()
    name = _strip_accents(comp.get("name") or "")
    return category in {"junior", "cadet"} and bool(YOUTH_WORLD_RE.search(name))


def fie_source_id(comp, season):
    competition_id = comp.get("competitionId")
    return f"fie:youth_worlds:{season}:{competition_id}"


def missing_fie_competitions(*, season, competitions, existing_source_ids):
    existing = {str(value) for value in existing_source_ids}
    return [comp for comp in competitions if fie_source_id(comp, season) not in existing]


def competition_to_tournament_row(comp, season):
    start_date = normalize_fie_date(comp.get("startDate"))
    end_date = normalize_fie_date(comp.get("endDate"))
    if start_date and end_date and end_date < start_date:
        start_date, end_date = end_date, start_date
    competition_id = comp["competitionId"]
    return {
        "source_id": fie_source_id(comp, season),
        "fie_id": competition_id,
        "competition_url_id": competition_id,
        "name": comp.get("name"),
        "season": str(season),
        "country": comp.get("country"),
        "location": comp.get("location"),
        "start_date": start_date,
        "end_date": end_date,
        "weapon": WEAPON_MAP.get(comp.get("weapon", ""), comp.get("weapon")),
        "gender": GENDER_MAP.get(comp.get("gender", ""), comp.get("gender")),
        "category": CATEGORY_MAP.get(comp.get("category", ""), comp.get("category")),
        "type": comp.get("type"),
        # FIE reports hasResults=0 for youth worlds even when result pages have rows.
        "has_results": bool(comp.get("hasResults", 0)) or bool(end_date),
        "metadata": {
            "scraped_by": "scrape_youth_majors",
            "source": "fie",
            "fie_competition_id": str(competition_id),
            "competition_family": "cadet_junior_world_championships",
        },
    }


def _make_fie_session():
    session = requests.Session()
    session.headers.update({"User-Agent": COMP_HEADERS["User-Agent"]})
    try:
        session.get(f"{FIE_BASE}/competitions", timeout=20)
    except Exception as exc:
        print(f"  Warning: FIE session setup failed: {exc}")
    return session


def fetch_competitions_page(session, season, page=1, from_date="", to_date=""):
    payload = {
        "name": "",
        "status": "passed",
        "gender": [],
        "weapon": [],
        "type": [],
        "season": season,
        "level": "",
        "competitionCategory": "",
        "fromDate": from_date,
        "toDate": to_date,
        "fetchPage": page,
    }
    response = session.post(
        f"{FIE_BASE}/competitions/search",
        headers=COMP_HEADERS,
        json=payload,
        timeout=20,
    )
    if response.status_code != 200 or not response.text.strip():
        raise RuntimeError(f"FIE search HTTP {response.status_code} season={season} page={page}")
    return response.json()


def fetch_competitions(session, season, from_date="", to_date="", max_pages=20):
    results = []
    for page in range(1, max_pages + 1):
        data = fetch_competitions_page(session, season, page, from_date, to_date)
        items = data.get("items") or []
        if not items:
            break
        results.extend(items)
        page_size = data.get("pageSize") or 300
        if len(items) < page_size:
            break
        time.sleep(0.2)
    return results


def fetch_competitions_by_month(session, season):
    by_id = {}
    for month in range(1, 13):
        from_date = f"{season}-{month:02d}-01"
        to_date = f"{season}-{month:02d}-{calendar.monthrange(season, month)[1]}"
        try:
            for comp in fetch_competitions(session, season, from_date=from_date, to_date=to_date, max_pages=5):
                competition_id = comp.get("competitionId")
                if competition_id is not None:
                    by_id[str(competition_id)] = comp
        except Exception as exc:
            print(f"    FIE month fallback failed season={season} month={month}: {exc}")
        time.sleep(0.1)
    return list(by_id.values())


def fetch_youth_world_competitions(session, season):
    try:
        comps = fetch_competitions(session, season)
    except Exception as exc:
        print(f"  FIE season search failed for {season}: {exc}; trying monthly fallback")
        comps = fetch_competitions_by_month(session, season)
    return [comp for comp in comps if is_youth_world_championship(comp)]


def extract_inline_json(html):
    blocks = []
    for match in re.findall(r"window\.\w+\s*=\s*(\{.*?\}|\[.*?\]);", html, re.DOTALL):
        try:
            blocks.append(json.loads(match))
        except Exception:
            pass
    return blocks


def fetch_fie_result_rows(season, competition_url_id):
    url = f"{FIE_BASE}/competitions/{season}/{competition_url_id}"
    try:
        response = requests.get(url, headers={"User-Agent": COMP_HEADERS["User-Agent"]}, timeout=20)
        if response.status_code != 200:
            print(f"    FIE result page HTTP {response.status_code}: {url}")
            return []
        rows = []
        for block in extract_inline_json(response.text):
            if isinstance(block, dict) and block.get("rows"):
                rows = block["rows"]
        return rows
    except Exception as exc:
        print(f"    FIE result fetch failed {url}: {exc}")
        return []


def dedupe_result_rows(rows):
    seen = {}
    for row in rows:
        fencer_key = row.get("fie_fencer_id") or row.get("name")
        key = (row.get("tournament_id"), fencer_key, row.get("rank"))
        if key not in seen:
            seen[key] = row
    return list(seen.values())


def parse_fie_result_rows(tournament_id, rows):
    parsed = []
    for row in rows:
        if not row.get("name") or not row.get("rank"):
            continue
        country = normalize_country(row.get("country") or row.get("nationality"))
        parsed.append(
            {
                "tournament_id": tournament_id,
                "fie_fencer_id": str(row.get("fencerId")) if row.get("fencerId") is not None else None,
                "name": normalize_person_name(row.get("name")),
                "nationality": normalize_country(row.get("nationality")),
                "country": country,
                "rank": to_int(row.get("rank")),
                "placement": to_int(row.get("rank")),
                "victory": to_int(row.get("victory")),
                "matches": to_int(row.get("matches")),
                "td": to_int(row.get("td")),
                "tr": to_int(row.get("tr")),
                "diff": to_int(row.get("diff")),
            }
        )
    return dedupe_result_rows(parsed)


def classify_event(event_name):
    weapon = next((weapon for pattern, weapon in WEAPON_PATTERNS if pattern.search(event_name)), None)
    gender = None
    for pattern, value in GENDER_PATTERNS:
        if pattern.search(event_name):
            gender = value
            break
    if gender == "Men" and re.search(r"\bwomen\b|\bgirls\b", event_name, re.I):
        gender = "Women"
    team = bool(re.search(r"\bteam\b", event_name, re.I))
    return {"weapon": weapon, "gender": gender, "team": team}


def parse_eyof_editions(html):
    soup = BeautifulSoup(html, "html.parser")
    editions = []
    seen = set()
    for row in soup.find_all("tr"):
        text = clean_text(row.get_text(" ")) or ""
        if not EYOF_RE.search(text):
            continue
        link = row.find("a", href=re.compile(r"/editions/\d+"))
        if not link:
            continue
        edition_id = re.search(r"/editions/(\d+)", link["href"]).group(1)
        if edition_id in seen:
            continue
        seen.add(edition_id)
        year_match = re.search(r"\b(19|20)\d{2}\b", text)
        year = year_match.group(0) if year_match else None
        city = ""
        cells = [clean_text(cell.get_text(" ")) for cell in row.find_all(["td", "th"])]
        cells = [cell for cell in cells if cell]
        if len(cells) >= 3:
            city = cells[2]
        edition_name = clean_text(" ".join(part for part in [city, year, "European Youth Olympic Festival"] if part))
        editions.append({"edition_id": edition_id, "edition_name": edition_name, "year": year})
    return editions


def _configured_eyof_editions():
    raw = os.environ.get("EYOF_OLYMPEDIA_EDITIONS", "")
    editions = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            edition_id, edition_name = item.split(":", 1)
        else:
            edition_id, edition_name = item, f"EYOF {item}"
        year_match = re.search(r"\b(19|20)\d{2}\b", edition_name)
        editions.append(
            {
                "edition_id": edition_id.strip(),
                "edition_name": clean_text(edition_name) or f"EYOF {edition_id.strip()}",
                "year": year_match.group(0) if year_match else None,
            }
        )
    return editions


def fetch_eyof_editions():
    configured = _configured_eyof_editions()
    if configured:
        return configured
    html = _get_olympedia(f"{OLYMPEDIA_BASE}/editions")
    return parse_eyof_editions(html or "")


def parse_eyof_sport_page(html, edition_id, edition_name):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()
    for td in soup.find_all("td"):
        result_link = td.find("a", href=RESULT_LINK_RE)
        if not result_link:
            continue
        result_id = re.search(r"/results/(\d+)", result_link["href"]).group(1)
        if result_id in seen:
            continue
        seen.add(result_id)
        events.append(
            {
                "result_id": result_id,
                "event_name": result_link.text.strip(),
                "edition_id": str(edition_id),
                "edition_name": edition_name,
            }
        )
    return events


def parse_olympedia_results_page(html, result_id):
    soup = BeautifulSoup(html, "html.parser")
    table = None
    for candidate in soup.find_all("table"):
        classes = candidate.get("class", [])
        if "biodata" in classes:
            continue
        if "table-striped" in classes or "table" in classes:
            table = candidate
            break
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        pos_text = cells[0].text.strip()
        rank = to_int(re.sub(r"\D", "", pos_text)) if pos_text else None
        competitor_td = cells[2]
        athlete_link = competitor_td.find("a", href=re.compile(r"/athletes/\d+"))
        athlete_id = re.search(r"/athletes/(\d+)", athlete_link["href"]).group(1) if athlete_link else None
        name = clean_text(competitor_td.text)
        if not name:
            continue
        noc = clean_text(cells[3].text) if len(cells) > 3 else None
        medal_raw = clean_text(cells[4].text) if len(cells) > 4 else None
        medal = medal_raw if medal_raw in {"Gold", "Silver", "Bronze"} else None
        rows.append({"rank": rank, "name": name, "country": noc, "medal": medal, "athlete_id": athlete_id})
    return rows


def olympedia_rows_to_db(tournament_id, placements):
    rows = []
    for placement in placements:
        if placement.get("rank") is None:
            continue
        rows.append(
            {
                "tournament_id": tournament_id,
                "name": placement.get("name"),
                "nationality": placement.get("country"),
                "rank": placement.get("rank"),
                "medal": placement.get("medal"),
                "fencer_id": None,
                "metadata": {"olympedia_athlete_id": placement.get("athlete_id")},
            }
        )
    return rows


def _get_olympedia(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=OLYMPEDIA_HEADERS, timeout=20)
            if response.status_code == 200:
                return response.text
            if response.status_code == 404:
                return None
            print(f"  Olympedia HTTP {response.status_code}: {url}")
            if response.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt * (10 if response.status_code == 429 else 2))
            else:
                return None
        except Exception as exc:
            print(f"  Olympedia fetch failed {url}: {exc}")
            time.sleep(2 ** attempt)
    return None


def fetch_eyof_events(edition):
    html = _get_olympedia(f"{OLYMPEDIA_BASE}/editions/{edition['edition_id']}/sports/FEN")
    if not html:
        return []
    return parse_eyof_sport_page(html, edition["edition_id"], edition["edition_name"])


def fetch_olympedia_result_page(result_id):
    html = _get_olympedia(f"{OLYMPEDIA_BASE}/results/{result_id}")
    if not html:
        return []
    return parse_olympedia_results_page(html, result_id)


def existing_source_ids(prefix):
    if supabase is None:
        return set()
    source_ids = set()
    offset = 0
    while True:
        rows = (
            supabase.table("fs_tournaments")
            .select("source_id")
            .like("source_id", f"{prefix}%")
            .range(offset, offset + 999)
            .execute()
            .data
            or []
        )
        for row in rows:
            if row.get("source_id"):
                source_ids.add(row["source_id"])
        if len(rows) < 1000:
            break
        offset += 1000
    return source_ids


def _fetch_tournament_id_by_source_id(source_id):
    result = supabase.table("fs_tournaments").select("id").eq("source_id", source_id).limit(1).execute()
    return result.data[0]["id"] if result.data else None


def fetch_tournament_id_map(source_ids):
    id_map = {}
    for i in range(0, len(source_ids), BATCH_SIZE):
        batch = source_ids[i : i + BATCH_SIZE]
        result = supabase.table("fs_tournaments").select("id,source_id").in_("source_id", batch).execute()
        for row in result.data or []:
            id_map[row["source_id"]] = row["id"]
    return id_map


def _insert_missing_tournament_rows(rows):
    source_ids = [row["source_id"] for row in rows if row.get("source_id")]
    existing = fetch_tournament_id_map(source_ids)
    new_rows = [row for row in rows if row.get("source_id") not in existing]
    if not new_rows:
        return
    try:
        for i in range(0, len(new_rows), BATCH_SIZE):
            supabase.table("fs_tournaments").insert(new_rows[i : i + BATCH_SIZE]).execute()
    except Exception as exc:
        print(f"  Tournament insert failed; retrying without fie_id: {exc}")
        fallback_rows = []
        for row in new_rows:
            fallback = dict(row)
            fallback["fie_id"] = None
            fallback_rows.append(fallback)
        for i in range(0, len(fallback_rows), BATCH_SIZE):
            supabase.table("fs_tournaments").insert(fallback_rows[i : i + BATCH_SIZE]).execute()


def upsert_tournament_rows(rows, *, on_conflict="source_id"):
    if not rows or supabase is None:
        return {}
    try:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            supabase.table("fs_tournaments").upsert(batch, on_conflict=on_conflict).execute()
    except Exception as exc:
        msg = str(exc).lower()
        if "no unique" in msg or "no exclusion" in msg or "constraint" in msg and "on conflict" in msg:
            print(f"  Tournament upsert unsupported for {on_conflict}; inserting missing rows: {exc}")
            _insert_missing_tournament_rows(rows)
            return fetch_tournament_id_map([row["source_id"] for row in rows if row.get("source_id")])
        # Some deployed schemas have a unique fie_id left over from older FIE
        # scrapers. Youth-world competitionUrl IDs repeat by season, so retry
        # with source_id as the only external uniqueness field.
        print(f"  Tournament upsert failed; retrying without fie_id: {exc}")
        fallback_rows = []
        for row in rows:
            fallback = dict(row)
            fallback["fie_id"] = None
            fallback_rows.append(fallback)
        for i in range(0, len(fallback_rows), BATCH_SIZE):
            batch = fallback_rows[i : i + BATCH_SIZE]
            try:
                supabase.table("fs_tournaments").upsert(batch, on_conflict=on_conflict).execute()
            except Exception as retry_exc:
                retry_msg = str(retry_exc).lower()
                if "no unique" in retry_msg or "no exclusion" in retry_msg or "constraint" in retry_msg and "on conflict" in retry_msg:
                    print(f"  Tournament retry upsert unsupported; inserting missing rows: {retry_exc}")
                    _insert_missing_tournament_rows(fallback_rows)
                    break
                raise

    source_ids = [row["source_id"] for row in rows if row.get("source_id")]
    return fetch_tournament_id_map(source_ids)


def upsert_tournament_row(row, *, on_conflict="source_id"):
    ids = upsert_tournament_rows([row], on_conflict=on_conflict)
    return ids.get(row["source_id"]) or _fetch_tournament_id_by_source_id(row["source_id"])


def replace_results(tournament_id, rows):
    if not rows or supabase is None:
        return 0
    try:
        for i in range(0, len(rows), BATCH_SIZE):
            supabase.table("fs_results").upsert(
                rows[i : i + BATCH_SIZE],
                on_conflict="tournament_id,name",
            ).execute()
    except Exception as exc:
        print(f"  Results upsert failed for {tournament_id}; existing rows were preserved: {exc}")
        return 0
    return len(rows)


def remember_done_value(key, value):
    values = {str(item) for item in (get_state(SOURCE, key) or [])}
    values.add(str(value))
    set_state(SOURCE, key, sorted(values))


def _current_season_year():
    return datetime.now(timezone.utc).year


def scrape_fie_youth_worlds():
    session = _make_fie_session()
    current_year = _current_season_year()
    done_seasons = {int(season) for season in (get_state(SOURCE, "fie_done_seasons") or [])}
    done_competitions = {str(value) for value in (get_state(SOURCE, "fie_done_competition_source_ids") or [])}
    existing = existing_source_ids("fie:youth_worlds:")
    total_written = 0
    total_failed = 0
    total_skipped = 0

    for season in range(FIE_EARLIEST_SEASON, current_year + 1):
        print(f"  FIE youth worlds season {season}")
        competitions = fetch_youth_world_competitions(session, season)
        if not competitions:
            if season < current_year:
                remember_done_value("fie_done_seasons", season)
            total_skipped += 1
            time.sleep(REQUEST_DELAY)
            continue

        missing = missing_fie_competitions(season=season, competitions=competitions, existing_source_ids=existing)
        rows = [competition_to_tournament_row(comp, season) for comp in competitions]
        id_map = upsert_tournament_rows(rows)
        existing.update(row["source_id"] for row in rows)
        total_written += len(missing)

        for comp in competitions:
            source_id = fie_source_id(comp, season)
            if source_id in done_competitions:
                total_skipped += 1
                continue
            tournament_id = id_map.get(source_id) or _fetch_tournament_id_by_source_id(source_id)
            if not tournament_id:
                total_failed += 1
                continue
            raw_rows = fetch_fie_result_rows(season, comp["competitionId"])
            result_rows = parse_fie_result_rows(tournament_id, raw_rows)
            if not result_rows:
                total_failed += 1
                time.sleep(REQUEST_DELAY)
                continue
            written = replace_results(tournament_id, result_rows)
            if written == len(result_rows):
                remember_done_value("fie_done_competition_source_ids", source_id)
                done_competitions.add(source_id)
            else:
                total_failed += 1
            time.sleep(REQUEST_DELAY)

        if season < current_year:
            remember_done_value("fie_done_seasons", season)
            done_seasons.add(season)
        time.sleep(REQUEST_DELAY)
    return total_written, total_failed, total_skipped


def eyof_tournament_row(event, classification):
    year_match = re.search(r"\b(19|20)\d{2}\b", event.get("edition_name") or "")
    year = year_match.group(0) if year_match else None
    source_id = f"olympedia:eyof:{event['edition_id']}:{event['result_id']}"
    return {
        "source_id": source_id,
        "name": f"{event['edition_name']} - {event['event_name']}",
        "season": year,
        "type": "eyof",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": "Cadet",
        "country": None,
        "has_results": True,
        "metadata": {
            "scraped_by": "scrape_youth_majors",
            "source": "olympedia",
            "olympedia_result_id": event["result_id"],
            "olympedia_edition_id": event["edition_id"],
            "edition_name": event["edition_name"],
            "event_name": event["event_name"],
            "team": classification["team"],
            "competition_family": "eyof",
        },
    }


def scrape_eyof():
    done_result_ids = {str(value) for value in (get_state(SOURCE, "eyof_done_result_ids") or [])}
    written = failed = skipped = 0
    editions = fetch_eyof_editions()
    if not editions:
        print("  No Olympedia EYOF fencing editions discovered.")
        return written, failed, skipped

    for edition in editions:
        events = fetch_eyof_events(edition)
        for event in events:
            result_id = str(event["result_id"])
            if result_id in done_result_ids:
                skipped += 1
                continue
            classification = classify_event(event["event_name"])
            if not classification["weapon"] or not classification["gender"]:
                skipped += 1
                continue
            tournament_id = upsert_tournament_row(eyof_tournament_row(event, classification))
            if not tournament_id:
                failed += 1
                continue
            placements = fetch_olympedia_result_page(result_id)
            db_rows = olympedia_rows_to_db(tournament_id, placements)
            if not db_rows:
                failed += 1
                continue
            n = replace_results(tournament_id, db_rows)
            if n == len(db_rows):
                remember_done_value("eyof_done_result_ids", result_id)
                done_result_ids.add(result_id)
                written += 1
            else:
                failed += 1
            time.sleep(REQUEST_DELAY)
    return written, failed, skipped


def main():
    if not SUPABASE_URL or not SUPABASE_KEY or supabase is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_youth_majors").start()
    try:
        print(f"Youth majors scraper starting - {datetime.now(timezone.utc).isoformat()}")
        fie_written, fie_failed, fie_skipped = scrape_fie_youth_worlds()
        eyof_written, eyof_failed, eyof_skipped = scrape_eyof()
        written = fie_written + eyof_written
        failed = fie_failed + eyof_failed
        skipped = fie_skipped + eyof_skipped
        run_log.complete(
            written=written,
            failed=failed,
            skipped=skipped,
            metadata={"fie_written": fie_written, "eyof_written": eyof_written},
        )
        print(f"Done - written={written}, failed={failed}, skipped={skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

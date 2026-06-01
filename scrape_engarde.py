import html
import json
import os
import re
import time
import traceback
import unicodedata
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE = None

BASE_URL = "https://engarde-service.com"
SOURCE = "engarde"
STATE_KEY_DONE_IDS = "done_ids"
REQUEST_DELAY_SECONDS = float(os.environ.get("ENGARDE_REQUEST_DELAY", "1.5"))
DEFAULT_NROWS = int(os.environ.get("ENGARDE_NROWS", "50"))
MAX_PAGES = int(os.environ.get("ENGARDE_MAX_PAGES", "10"))
MAX_RETRIES = int(os.environ.get("ENGARDE_MAX_RETRIES", "3"))
STATE_MAX_IDS = int(os.environ.get("ENGARDE_STATE_MAX_IDS", "10000"))
COMPETITION_TYPES = os.environ.get("ENGARDE_TYPES", "international,national,local")
SKIP_FIE_TYPE = os.environ.get("ENGARDE_SKIP_FIE_TYPE", "1") != "0"
SCRAPE_TEAMS = os.environ.get("ENGARDE_SCRAPE_TEAMS", "0") == "1"
FORCE_RESCRAPE = os.environ.get("ENGARDE_FORCE", "0") == "1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
}

ENDPOINT_NOTES = """
Engarde endpoint findings from 2026-06-01 probe:
- GET https://engarde-service.com/ -> 200 text/html.
- POST https://engarde-service.com/prog/getCompeForDisplay.php with form body
  option=history, sexe, arme=e,f,s, indiv, categorie, orderby=date, datefrom,
  dateto, country, city, type=international,national,local, state, page, lang=en,
  large=E, nrows, organism, event, order=DESC, show_test=0, cache=1 -> 200 text/xml.
  Works for global listing and country filters GBR, AUS, FRA. IRL probe returned
  a valid empty XML page. organism/event params were ignored on the global page.
- POST https://engarde-service.com/prog/getTournoisForDisplay.php with form body
  page, option=recent|next|full, contains -> 200 text/json event listing.
- POST https://engarde-service.com/prog/getTournois.php with form body option,
  sexe, arme, indiv, type, country, orderby, datefrom, dateto, page, lang, nrows,
  organism, order, show_test -> 200 JSON organism event listing for rfee, scfu,
  nsw_sfl, life, hunfencing, occ; fencingireland returned {"status":"error"}.
- GET https://engarde-service.com/competition/{org}/{event}/{competition}/clasfinal.htm
  -> final classification HTML table.
- GET .../poules1.htm -> pool matrix HTML tables.
- GET .../tableauPreliminaire.htm, .../tableau64.htm, .../tableau16.htm and
  related tableau links -> direct-elimination bracket HTML.
- Legacy index.php?Compe=...&Event=...&Organisme=...&page=...&zz=menu returned
  menu HTML only in the probe, not the result table body.
"""


WEAPON_MAP = {"e": "Epee", "f": "Foil", "s": "Sabre"}
GENDER_MAP = {"m": "Men", "f": "Women", "n": "Mixed"}

IOC_COUNTRY_MAP = {
    "AIN": "AIN",
    "AIN_": "AIN",
    "AUS": "Australia",
    "AUT": "Austria",
    "BEL": "Belgium",
    "BRA": "Brazil",
    "BUL": "Bulgaria",
    "CAN": "Canada",
    "CHI": "Chile",
    "CHN": "China",
    "CRO": "Croatia",
    "CZE": "Czech Republic",
    "EGY": "Egypt",
    "ESP": "Spain",
    "EST": "Estonia",
    "FRA": "France",
    "GBR": "Great Britain",
    "GEO": "Georgia",
    "GER": "Germany",
    "GRE": "Greece",
    "HKG": "Hong Kong",
    "HUN": "Hungary",
    "IRL": "Ireland",
    "ISR": "Israel",
    "ITA": "Italy",
    "JPN": "Japan",
    "KOR": "South Korea",
    "NED": "Netherlands",
    "POL": "Poland",
    "ROU": "Romania",
    "SUI": "Switzerland",
    "TUR": "Turkey",
    "UKR": "Ukraine",
    "USA": "United States",
}


@dataclass(frozen=True)
class EngardeService:
    label: str
    base_url: str = BASE_URL
    country: str = ""
    types: str = COMPETITION_TYPES


ENGARDE_SERVICES = [
    EngardeService("global"),
    EngardeService("uk", country="GBR"),
    EngardeService("ireland", country="IRL"),
    EngardeService("australia", country="AUS"),
    EngardeService("france", country="FRA"),
]


def get_supabase_client():
    global SUPABASE
    if SUPABASE is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        from supabase import create_client

        SUPABASE = create_client(SUPABASE_URL, SUPABASE_KEY)
    return SUPABASE


def clean_text(value):
    text = html.unescape(str(value or "")).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def strip_accents(value):
    return "".join(
        c for c in unicodedata.normalize("NFD", value or "")
        if unicodedata.category(c) != "Mn"
    )


def normalize_key(value):
    text = strip_accents(clean_text(value) or "").lower()
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def title_case(value):
    text = clean_text(value)
    return text.title() if text else None


def normalize_country(value):
    text = clean_text(value)
    if not text:
        return None
    key = strip_accents(text).upper().replace(".", "")
    key = re.sub(r"\s+", " ", key)
    return IOC_COUNTRY_MAP.get(key, title_case(text))


def country_key(value):
    return normalize_key(normalize_country(value) or value)


def to_int(value):
    try:
        if value is None or value == "":
            return None
        return int(float(str(value).strip()))
    except Exception:
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def parse_engarde_date(value):
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%Y %m %d", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def medal_for_rank(rank):
    return {1: "gold", 2: "silver", 3: "bronze"}.get(rank)


def make_bout_id(tournament_id, source_key):
    seed = f"fencespace:engarde-bout:{tournament_id}:{source_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def table_rows(table):
    rows = []
    for tr in table.find_all("tr"):
        cells = [
            clean_text(cell.get_text(" ", strip=True)) or ""
            for cell in tr.find_all(["th", "td"])
        ]
        if any(cells):
            rows.append(cells)
    return rows


def parse_score_cell(value):
    text = (clean_text(value) or "").upper()
    if not text or text in {"-", "—"}:
        return None
    if re.fullmatch(r"V\d*", text):
        digits = re.search(r"\d+", text)
        return int(digits.group(0)) if digits else 5
    return to_int(text)


def parse_score_pair(value):
    text = clean_text(value) or ""
    match = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def batch_upsert(table, rows, on_conflict=None, batch_size=100):
    if not rows:
        return
    client = get_supabase_client()
    for i in range(0, len(rows), batch_size):
        kwargs = {"on_conflict": on_conflict} if on_conflict else {}
        client.table(table).upsert(rows[i:i + batch_size], **kwargs).execute()


class EngardeClient:
    def __init__(
        self,
        base_url=BASE_URL,
        request_delay=REQUEST_DELAY_SECONDS,
        max_retries=MAX_RETRIES,
    ):
        self.base_url = base_url.rstrip("/")
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def request(self, method, path_or_url, **kwargs):
        url = path_or_url if path_or_url.startswith("http") else urljoin(self.base_url + "/", path_or_url)
        last_response = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(method, url, timeout=30, **kwargs)
                content_type = response.headers.get("content-type", "")
                print(f"  {method} {url} -> {response.status_code} {content_type}")
                if response.status_code not in {429, 500, 502, 503, 504}:
                    time.sleep(self.request_delay)
                    return response
                last_response = response
            except requests.RequestException as exc:
                print(f"  {method} {url} failed (attempt {attempt}/{self.max_retries}): {exc}")
            if attempt < self.max_retries:
                time.sleep(2 ** attempt)
        time.sleep(self.request_delay)
        return last_response

    def post_form(self, path, data, accept="*/*"):
        headers = {
            "Accept": accept,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }
        return self.request("POST", path, data=urlencode(data, doseq=False), headers=headers)

    def get_text(self, url):
        response = self.request("GET", url)
        if response is None or response.status_code != 200:
            return None
        return response.text


def competition_payload(service, page):
    return {
        "option": "history",
        "sexe": "",
        "arme": "e,f,s",
        "indiv": "",
        "categorie": "",
        "orderby": "date",
        "datefrom": "",
        "dateto": "",
        "country": service.country,
        "city": "",
        "type": service.types,
        "state": "",
        "page": page,
        "lang": "en",
        "large": "E",
        "nrows": DEFAULT_NROWS,
        "organism": "",
        "event": "",
        "order": "DESC",
        "show_test": 0,
        "cache": 1,
    }


def parse_tournament_listing(body, service_label):
    try:
        payload = json.loads(body or "{}")
    except json.JSONDecodeError:
        return []

    raw_rows = payload.get("events")
    source_shape = "events"
    if raw_rows is None:
        raw_rows = payload.get("result")
        source_shape = "result"
    if not isinstance(raw_rows, list):
        return []

    rows = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        if source_shape == "events":
            organism = clean_text(item.get("org"))
            event_id = clean_text(item.get("ev"))
            name = clean_text(item.get("title"))
            start_date = parse_engarde_date(item.get("date_from"))
            end_date = parse_engarde_date(item.get("date_to")) or start_date
            country = clean_text(item.get("ioc_competition") or item.get("ioc_organisme"))
            city = clean_text(item.get("city"))
            competition_count = to_int(item.get("competitions"))
        else:
            organism = clean_text(item.get("Organisme"))
            event_id = clean_text(item.get("Event"))
            name = clean_text(item.get("Titre"))
            start_date = parse_engarde_date(item.get("date"))
            end_date = start_date
            country = clean_text(item.get("Pays") or item.get("ioc_competition"))
            city = clean_text(item.get("ville") or item.get("city"))
            competition_count = to_int(item.get("compet"))
        if not organism or not event_id:
            continue
        rows.append({
            "service": service_label,
            "organism": organism,
            "event_id": event_id,
            "name": name or event_id,
            "start_date": start_date,
            "end_date": end_date,
            "country": normalize_country(country),
            "city": city,
            "competition_count": competition_count,
            "source_id": f"engarde:{service_label}:{organism}:{event_id}",
            "raw": item,
        })
    return rows


def parse_competition_node(node, service_label):
    children = [clean_text("".join(child.itertext())) for child in list(node)]
    attrs = dict(node.attrib)
    org = attrs.get("org")
    event = attrs.get("evt")
    competition = attrs.get("compe")
    event_id = f"{org}:{event}:{competition}"
    source_id = f"engarde:{service_label}:{event_id}"
    return {
        "service": service_label,
        "source_id": source_id,
        "event_id": event_id,
        "event_source_id": f"engarde:{service_label}:{org}:{event}",
        "org": org,
        "event": event,
        "competition": competition,
        "gender_code": attrs.get("sexe"),
        "weapon_code": attrs.get("arme"),
        "type": attrs.get("type"),
        "status": attrs.get("etat"),
        "date": parse_engarde_date(attrs.get("date")),
        "country_code": attrs.get("pays"),
        "city": attrs.get("ville"),
        "is_individual": attrs.get("estindividuelle") == "1",
        "category": children[0] if len(children) > 0 else None,
        "name": children[1] if len(children) > 1 else None,
        "raw": {"attrs": attrs, "children": children},
    }


def parse_competition_listing_xml(body, service_label):
    text = body or ""
    if not text.strip() or text.lstrip().startswith("false|"):
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    return [
        parse_competition_node(node, service_label)
        for node in root.findall(".//comp")
    ]


def fetch_competitions_for_service(client, service):
    print(f"Fetching Engarde competitions for {service.label}: country={service.country or 'all'}")
    competitions = []
    for page in range(1, MAX_PAGES + 1):
        response = client.post_form(
            "/prog/getCompeForDisplay.php",
            competition_payload(service, page),
            accept="text/xml,*/*",
        )
        if response is None or response.status_code != 200:
            print(f"  Stopping {service.label} at page {page}: non-200 response")
            break
        page_rows = parse_competition_listing_xml(response.text, service.label)
        print(f"  {service.label} page {page}: {len(page_rows)} competitions")
        if not page_rows:
            break
        competitions.extend(page_rows)
        if len(page_rows) < DEFAULT_NROWS:
            break
    return competitions


def fetch_engarde_competitions(client):
    seen = {}
    for service in ENGARDE_SERVICES:
        for comp in fetch_competitions_for_service(client, service):
            existing = seen.get(comp["event_id"])
            if existing is None or (existing.get("service") == "global" and comp.get("service") != "global"):
                seen[comp["event_id"]] = comp
    return list(seen.values())


def competition_url(comp, suffix=""):
    base = f"{BASE_URL}/competition/{comp['org']}/{comp['event']}/{comp['competition']}"
    return f"{base}/{suffix}" if suffix else base


def tournament_row(comp):
    name = comp.get("name") or comp.get("category") or comp["event_id"]
    country = normalize_country(comp.get("country_code"))
    start_date = comp.get("date")
    return {
        "source_id": comp["source_id"],
        "season": start_date[:4] if start_date else None,
        "name": name,
        "location": comp.get("city"),
        "country": country,
        "weapon": WEAPON_MAP.get((comp.get("weapon_code") or "").lower(), comp.get("weapon_code")),
        "gender": GENDER_MAP.get((comp.get("gender_code") or "").lower(), comp.get("gender_code")),
        "category": comp.get("category"),
        "start_date": start_date,
        "end_date": start_date,
        "is_sub_competition": False,
        "has_results": comp.get("status") == "completed",
        "metadata": {
            "source": SOURCE,
            "service": comp.get("service"),
            "event_id": comp.get("event_id"),
            "event_source_id": comp.get("event_source_id"),
            "org": comp.get("org"),
            "event": comp.get("event"),
            "competition": comp.get("competition"),
            "type": comp.get("type"),
            "status": comp.get("status"),
            "result_url": competition_url(comp, "clasfinal.htm"),
            "raw": comp.get("raw"),
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def upsert_tournament(comp):
    client = get_supabase_client()
    row = tournament_row(comp)
    client.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()
    data = (
        client.table("fs_tournaments")
        .select("id")
        .eq("source_id", comp["source_id"])
        .limit(1)
        .execute()
        .data
    )
    if not data:
        raise RuntimeError(f"upserted tournament not found: {comp['source_id']}")
    return data[0]["id"]


def upsert_tournaments(comps):
    rows = [tournament_row(comp) for comp in comps]
    batch_upsert("fs_tournaments", rows, on_conflict="source_id")
    return fetch_tournament_id_map([comp["source_id"] for comp in comps])


def fetch_tournament_id_map(source_ids):
    client = get_supabase_client()
    tournament_ids = {}
    for i in range(0, len(source_ids), 100):
        batch = source_ids[i:i + 100]
        data = (
            client.table("fs_tournaments")
            .select("id,source_id")
            .in_("source_id", batch)
            .execute()
            .data
        )
        for row in data or []:
            tournament_ids[row["source_id"]] = row["id"]
    return tournament_ids


def fetch_all_fencers():
    client = get_supabase_client()
    print("Loading fs_fencers for name/country matching...")
    rows = []
    start = 0
    page_size = 1000
    while True:
        data = (
            client.table("fs_fencers")
            .select("id,fie_id,name,country")
            .range(start, start + page_size - 1)
            .execute()
            .data
        )
        rows.extend(data or [])
        if not data or len(data) < page_size:
            break
        start += page_size
    print(f"Loaded {len(rows)} fencer rows")
    return build_fencer_index(rows)


def build_fencer_index(rows):
    exact = {}
    last = {}
    for row in rows:
        name = clean_text(row.get("name"))
        ckey = country_key(row.get("country"))
        if not name or not ckey:
            continue
        exact.setdefault((normalize_key(name), ckey), row)
        parts = normalize_key(name).split()
        for size in range(1, min(3, len(parts)) + 1):
            key = (" ".join(parts[-size:]), ckey)
            last.setdefault(key, []).append(row)
    return {"exact": exact, "last": last}


def match_fencer(index, full_name, country, last_name=None):
    ckey = country_key(country)
    if not full_name or not ckey:
        return None, None
    exact = index["exact"].get((normalize_key(full_name), ckey))
    if exact:
        return exact, "exact_name_country"
    reverse_name = " ".join(reversed(normalize_key(full_name).split()))
    if reverse_name:
        exact = index["exact"].get((reverse_name, ckey))
        if exact:
            return exact, "reverse_name_country"
    parts = normalize_key(full_name).split()
    last_key = normalize_key(last_name) if last_name else (parts[-1] if parts else "")
    candidates = index["last"].get((last_key, ckey), []) if last_key else []
    if len(candidates) == 1:
        return candidates[0], "last_name_country"
    return None, None


def discover_links(base_url, html_text, wanted):
    soup = BeautifulSoup(html_text or "", "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag.get("href") or ""
        lower = href.lower()
        if any(token in lower for token in wanted):
            links.append(urljoin(base_url, href))
    return list(dict.fromkeys(links))


def discover_result_links(base_url, html_text):
    return discover_links(base_url, html_text, ["clasfinal.htm", "classement.htm"])


def discover_bout_links(base_url, html_text):
    links = discover_links(base_url, html_text, ["poule", "tableau"])
    ignored = ("clas", "ranking")
    return [
        link for link in links
        if not any(token in link.lower().rsplit("/", 1)[-1] for token in ignored)
    ]


def parse_results_table(html_text):
    soup = BeautifulSoup(html_text or "", "html.parser")
    result_rows = []
    for table in soup.find_all("table"):
        rows = table_rows(table)
        if len(rows) < 2:
            continue
        header = [normalize_key(cell) for cell in rows[0]]
        rank_col = next(
            (
                idx for idx, label in enumerate(header)
                if any(token in label for token in ("rg", "rank", "rang", "place"))
            ),
            None,
        )
        if rank_col is None:
            continue

        last_name_col = None
        first_name_col = None
        club_col = None
        country_col = None
        for idx, label in enumerate(header):
            if idx == rank_col:
                continue
            if last_name_col is None and any(
                token in label
                for token in ("nom", "name", "surname", "last", "nev", "achternaam", "lastname")
            ):
                last_name_col = idx
            if first_name_col is None and any(token in label for token in ("prenom", "first", "forename", "kereszt")):
                first_name_col = idx
            if club_col is None and any(token in label for token in ("club", "team", "equipe", "egyesulet", "vereniging")):
                club_col = idx
            if country_col is None and any(token in label for token in ("country", "pays", "nation", "ioc")):
                country_col = idx
        if last_name_col is None:
            last_name_col = next((i for i in range(len(header)) if i != rank_col), None)

        for row in rows[1:]:
            if len(row) <= rank_col:
                continue
            rank = to_int(row[rank_col])
            if not rank:
                continue
            last_name = clean_text(row[last_name_col]) if last_name_col is not None and len(row) > last_name_col else None
            first_name = clean_text(row[first_name_col]) if first_name_col is not None and len(row) > first_name_col else None
            if first_name and last_name:
                full_name = title_case(f"{first_name} {last_name}")
            else:
                full_name = title_case(last_name)
            result_rows.append({
                "rank": rank,
                "name": full_name,
                "last_name": title_case(last_name),
                "first_name": title_case(first_name),
                "club": clean_text(row[club_col]) if club_col is not None and len(row) > club_col else None,
                "country": clean_text(row[country_col]) if country_col is not None and len(row) > country_col else None,
                "raw_cells": row,
            })
        if result_rows:
            break
    return result_rows


parse_result_rows = parse_results_table


def parse_pool_bouts(html_text):
    soup = BeautifulSoup(html_text or "", "html.parser")
    bouts = []
    for table_index, table in enumerate(soup.find_all("table"), start=1):
        rows = table_rows(table)
        if len(rows) < 3:
            continue
        round_name = clean_text(rows[0][0] if rows[0] else "") or f"Pool {table_index}"
        if not re.search(r"\b(poule|pool)\b", round_name, flags=re.I):
            continue

        fencer_rows = [
            row for row in rows[1:]
            if len(row) >= 4 and clean_text(row[0]) and clean_text(row[1])
        ]
        fencer_count = len(fencer_rows)
        if fencer_count < 2:
            continue

        matrix_offset = 3
        if any(len(row) <= matrix_offset for row in fencer_rows):
            matrix_offset = max(2, min(len(row) for row in fencer_rows) - fencer_count)

        for i, row_a in enumerate(fencer_rows):
            for j in range(i + 1, fencer_count):
                row_b = fencer_rows[j]
                score_a = parse_score_cell(row_a[matrix_offset + j]) if len(row_a) > matrix_offset + j else None
                score_b = parse_score_cell(row_b[matrix_offset + i]) if len(row_b) > matrix_offset + i else None
                if score_a is None and score_b is None:
                    continue
                name_a = clean_text(row_a[0])
                name_b = clean_text(row_b[0])
                source_key = f"pool:{round_name}:{i}:{j}:{normalize_key(name_a)}:{normalize_key(name_b)}"
                bouts.append({
                    "source_key": source_key,
                    "round": round_name,
                    "fencer_a": name_a,
                    "country_a": clean_text(row_a[1]),
                    "score_a": score_a,
                    "fencer_b": name_b,
                    "country_b": clean_text(row_b[1]),
                    "score_b": score_b,
                })
    return bouts


def parse_de_heading_bout(text):
    match = re.match(r"^(.+?)\s*:\s*(.+?)\s+(\d+)\s*/\s*(\d+)\s+(.+?)\s*\^?$", clean_text(text) or "")
    if not match:
        return None
    round_name, fencer_a, score_a, score_b, fencer_b = match.groups()
    return {
        "source_key": f"de:{normalize_key(round_name)}:{normalize_key(fencer_a)}:{normalize_key(fencer_b)}:{score_a}-{score_b}",
        "round": clean_text(round_name),
        "fencer_a": clean_text(fencer_a),
        "country_a": None,
        "score_a": int(score_a),
        "fencer_b": clean_text(fencer_b),
        "country_b": None,
        "score_b": int(score_b),
    }


def row_score_text(row):
    for cell in row[3:6]:
        if parse_score_pair(cell):
            return cell
    return None


def row_text(rows):
    return " ".join(" ".join(row) for row in rows)


def parse_seed_rows(rows):
    seed_rows = []
    for index, row in enumerate(rows):
        if len(row) < 3 or to_int(row[0]) is None:
            continue
        name = clean_text(row[1])
        country = clean_text(row[2])
        if not name:
            continue
        seed_rows.append({
            "row_index": index,
            "seed": to_int(row[0]),
            "name": name,
            "country": country,
            "score_text": row_score_text(row),
        })
    return seed_rows


def bracket_round_name(rows, fallback):
    if rows:
        for cell in rows[0]:
            text = clean_text(cell)
            if text and re.search(r"tableau|table|final|preliminary", text, flags=re.I):
                return text
    return fallback or "Direct elimination"


def parse_de_bouts(html_text):
    soup = BeautifulSoup(html_text or "", "html.parser")
    bouts = []
    for heading in soup.find_all(["h2", "h3", "h4"]):
        parsed = parse_de_heading_bout(heading.get_text(" ", strip=True))
        if parsed:
            bouts.append(parsed)

    fallback_heading = None
    for heading in soup.find_all(["h1", "h2", "h3"]):
        text = clean_text(heading.get_text(" ", strip=True))
        if text and re.search(r"tableau|table|final|preliminary", text, flags=re.I):
            fallback_heading = text

    for table in soup.find_all("table"):
        rows = table_rows(table)
        seeds = parse_seed_rows(rows)
        if len(seeds) < 2:
            continue
        round_name = bracket_round_name(rows, fallback_heading)
        for pair_index in range(0, len(seeds) - 1, 2):
            fencer_a = seeds[pair_index]
            fencer_b = seeds[pair_index + 1]
            score_text = fencer_a.get("score_text") or fencer_b.get("score_text")
            scores = parse_score_pair(score_text)
            if not scores:
                continue

            between = row_text(rows[fencer_a["row_index"] + 1:fencer_b["row_index"]])
            between_key = normalize_key(between)
            name_a_key = normalize_key(fencer_a["name"])
            name_b_key = normalize_key(fencer_b["name"])
            high, low = max(scores), min(scores)
            if name_a_key and name_a_key in between_key:
                score_a, score_b = high, low
            elif name_b_key and name_b_key in between_key:
                score_a, score_b = low, high
            else:
                score_a, score_b = scores

            source_key = (
                f"de:{round_name}:{pair_index // 2}:"
                f"{normalize_key(fencer_a['name'])}:{normalize_key(fencer_b['name'])}"
            )
            bouts.append({
                "source_key": source_key,
                "round": round_name,
                "fencer_a": fencer_a["name"],
                "country_a": fencer_a["country"],
                "score_a": score_a,
                "fencer_b": fencer_b["name"],
                "country_b": fencer_b["country"],
                "score_b": score_b,
            })
    deduped = {}
    for bout in bouts:
        deduped[bout["source_key"]] = bout
    return list(deduped.values())


def fetch_result_rows(client, comp):
    final_url = competition_url(comp, "clasfinal.htm")
    html_text = client.get_text(final_url)
    rows = parse_results_table(html_text or "")
    if rows:
        return rows, final_url

    base_url = competition_url(comp)
    base_html = client.get_text(base_url)
    if not base_html:
        return [], final_url
    for link in discover_result_links(base_url, base_html):
        if link == final_url:
            continue
        link_html = client.get_text(link)
        rows = parse_results_table(link_html or "")
        if rows:
            return rows, link
    return [], final_url


def fetch_bout_rows(client, comp):
    base_url = competition_url(comp)
    base_html = client.get_text(base_url)
    links = discover_bout_links(base_url, base_html or "")
    if not links:
        links = [
            competition_url(comp, "poules1.htm"),
            competition_url(comp, "tableauPreliminaire.htm"),
            competition_url(comp, "tableau64.htm"),
            competition_url(comp, "tableau16.htm"),
            competition_url(comp, "tableau8.htm"),
            competition_url(comp, "tableau4.htm"),
        ]

    deduped = {}
    for link in links:
        page_html = client.get_text(link)
        if not page_html:
            continue
        parsed = parse_pool_bouts(page_html) if "poule" in link.lower() else parse_de_bouts(page_html)
        for bout in parsed:
            source_key = f"{link.rsplit('/', 1)[-1]}:{bout['source_key']}"
            deduped[source_key] = {**bout, "source_key": source_key, "source_url": link}
    return list(deduped.values())


def result_rows_for_db(tournament_id, comp, scraped_rows, fencer_index, result_url):
    tournament_country = normalize_country(comp.get("country_code"))
    rows = []
    for row in scraped_rows:
        country = normalize_country(row.get("country")) or tournament_country
        matched, match_method = match_fencer(
            fencer_index,
            row.get("name"),
            country,
            last_name=row.get("last_name"),
        )
        rows.append({
            "tournament_id": tournament_id,
            "fencer_id": matched.get("id") if matched else None,
            "fie_fencer_id": str(matched.get("fie_id")) if matched and matched.get("fie_id") else None,
            "rank": row["rank"],
            "placement": row["rank"],
            "name": row.get("name"),
            "country": country,
            "nationality": country,
            "medal": medal_for_rank(row["rank"]),
            "metadata": {
                "source": SOURCE,
                "source_id": comp["source_id"],
                "result_url": result_url,
                "club": row.get("club"),
                "first_name": row.get("first_name"),
                "last_name": row.get("last_name"),
                "match_method": match_method,
                "raw_cells": row.get("raw_cells"),
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    return rows


def bout_rows_for_db(tournament_id, parsed_bouts, fencer_index):
    rows = []
    for bout in parsed_bouts:
        country_a = normalize_country(bout.get("country_a"))
        country_b = normalize_country(bout.get("country_b"))
        fencer_a, _ = match_fencer(fencer_index, bout.get("fencer_a"), country_a)
        fencer_b, _ = match_fencer(fencer_index, bout.get("fencer_b"), country_b)
        score_a = to_int(bout.get("score_a"))
        score_b = to_int(bout.get("score_b"))
        winner = None
        if score_a is not None and score_b is not None and score_a != score_b:
            winner = fencer_a if score_a > score_b else fencer_b
        rows.append({
            "id": make_bout_id(tournament_id, bout["source_key"]),
            "tournament_id": tournament_id,
            "fencer_a": fencer_a.get("id") if fencer_a else None,
            "fencer_b": fencer_b.get("id") if fencer_b else None,
            "score_a": score_a,
            "score_b": score_b,
            "round": bout.get("round"),
            "winner": winner.get("id") if winner else None,
        })
    return rows


def replace_results(tournament_id, rows):
    client = get_supabase_client()
    client.table("fs_results").delete().eq("tournament_id", tournament_id).execute()
    if rows:
        batch_upsert("fs_results", rows)


def strip_generated_ids(rows):
    return [{key: value for key, value in row.items() if key != "id"} for row in rows]


def replace_bouts(tournament_id, rows):
    client = get_supabase_client()
    client.table("fs_bouts").delete().eq("tournament_id", tournament_id).execute()
    if not rows:
        return
    try:
        batch_upsert("fs_bouts", rows, on_conflict="id")
    except Exception as exc:
        message = str(exc).lower()
        if "id" not in message or (
            "invalid input syntax" not in message
            and "type integer" not in message
            and "type bigint" not in message
        ):
            raise
        print("  fs_bouts.id rejected generated UUIDs; retrying with database IDs")
        batch_upsert("fs_bouts", strip_generated_ids(rows))


def should_scrape(comp):
    if comp.get("status") != "completed":
        return False
    if not SCRAPE_TEAMS and not comp.get("is_individual"):
        return False
    if SKIP_FIE_TYPE and (comp.get("type") or "").lower() == "fie":
        return False
    return True


def load_done_ids():
    state = get_state(SOURCE, STATE_KEY_DONE_IDS)
    if isinstance(state, list):
        return set(str(item) for item in state)
    if isinstance(state, dict) and isinstance(state.get("ids"), list):
        return set(str(item) for item in state["ids"])
    return set()


def save_done_ids(done_ids):
    ordered = sorted(done_ids)[-STATE_MAX_IDS:]
    set_state(SOURCE, STATE_KEY_DONE_IDS, ordered)


def scrape_engarde():
    print(ENDPOINT_NOTES.strip())
    print(f"Engarde scraper starting - {datetime.now(timezone.utc).isoformat()}")
    run_log = ScraperRunLogger("scrape_engarde").start()

    try:
        client = EngardeClient()
        fencer_index = fetch_all_fencers()
        competitions = fetch_engarde_competitions(client)
        to_scrape = [comp for comp in competitions if should_scrape(comp)]
        print(f"Found {len(competitions)} competition rows; {len(to_scrape)} eligible to scrape")

        done_ids = load_done_ids()
        pending = [
            comp for comp in to_scrape
            if FORCE_RESCRAPE or comp["source_id"] not in done_ids
        ]
        skipped = len(to_scrape) - len(pending)
        if skipped:
            print(f"Skipping {skipped} already completed Engarde IDs from scraper_state")

        tournament_ids = upsert_tournaments(pending) if pending else {}
        written = 0
        failed = 0

        for comp in pending:
            label = f"{comp.get('name')} ({comp['source_id']})"
            try:
                print(f"Scraping {label}")
                tournament_id = tournament_ids.get(comp["source_id"]) or upsert_tournament(comp)
                scraped_rows, result_url = fetch_result_rows(client, comp)
                if not scraped_rows:
                    print(f"  No final result rows found for {label}")
                    failed += 1
                    continue
                result_rows = result_rows_for_db(tournament_id, comp, scraped_rows, fencer_index, result_url)
                replace_results(tournament_id, result_rows)

                parsed_bouts = fetch_bout_rows(client, comp)
                bout_rows = bout_rows_for_db(tournament_id, parsed_bouts, fencer_index)
                replace_bouts(tournament_id, bout_rows)

                print(f"  Wrote {len(result_rows)} results and {len(bout_rows)} bouts")
                written += 1
                done_ids.add(comp["source_id"])
                save_done_ids(done_ids)
            except Exception as exc:
                failed += 1
                print(f"  Error scraping {label}: {exc}")
                traceback.print_exc()

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"Done - {written} competitions scraped, {skipped} skipped, {failed} failed")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    scrape_engarde()

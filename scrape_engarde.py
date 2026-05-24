import html
import os
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin

import requests
from supabase import create_client


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE_URL = "https://engarde-service.com"
SOURCE = "engarde"
REQUEST_DELAY_SECONDS = 2
DEFAULT_NROWS = int(os.environ.get("ENGARDE_NROWS", "50"))
MAX_PAGES = int(os.environ.get("ENGARDE_MAX_PAGES", "5"))
COMPETITION_TYPES = os.environ.get("ENGARDE_TYPES", "international,national,local")
SKIP_FIE_TYPE = os.environ.get("ENGARDE_SKIP_FIE_TYPE", "1") != "0"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
}

ENDPOINT_NOTES = """
Engarde endpoint findings:
- GET https://engarde-service.com/api: 404 fallback HTML, no clean public REST API found.
- POST /prog/getTournoisForDisplay.php: form-encoded JSON event listing. Known params: page, option=next|recent|full, contains.
- POST /prog/getCompeForDisplay.php: form-encoded XML competition listing. Known params include option, sexe, arme, indiv, categorie, orderby, datefrom, dateto, country, city, type, state, page, lang, large, nrows, organism, event, order, show_test, cache.
- GET /competition/{org}/{event}/{competition}: HTML competition page with links to result pages.
- GET /competition/{org}/{event}/{competition}/clasfinal.htm: final individual classification table when published.
Known blockers:
- /api/tournaments, /api/competitions, /api/events, /api/results and plain /tournaments, /competitions, /events, /results returned 404 fallback HTML in probing.
- Some legacy PHP parameter combinations return server-side SQL errors.
- Team result pages and detailed pool/direct-elimination bout parsing are not implemented here yet.
"""


WEAPON_MAP = {"e": "Epee", "f": "Foil", "s": "Sabre"}
GENDER_MAP = {"m": "Men", "f": "Women", "n": "Mixed"}

IOC_COUNTRY_MAP = {
    "AFG": "Afghanistan",
    "ALB": "Albania",
    "ALG": "Algeria",
    "AND": "Andorra",
    "ANG": "Angola",
    "ARG": "Argentina",
    "ARM": "Armenia",
    "AUS": "Australia",
    "AUT": "Austria",
    "AZE": "Azerbaijan",
    "BEL": "Belgium",
    "BRA": "Brazil",
    "BUL": "Bulgaria",
    "CAN": "Canada",
    "CHI": "Chile",
    "CHN": "China",
    "COL": "Colombia",
    "CRO": "Croatia",
    "CUB": "Cuba",
    "CYP": "Cyprus",
    "CZE": "Czech Republic",
    "DEN": "Denmark",
    "EGY": "Egypt",
    "ESP": "Spain",
    "EST": "Estonia",
    "FIN": "Finland",
    "FRA": "France",
    "GBR": "Great Britain",
    "GEO": "Georgia",
    "GER": "Germany",
    "GRE": "Greece",
    "HKG": "Hong Kong",
    "HUN": "Hungary",
    "IND": "India",
    "IRL": "Ireland",
    "ISR": "Israel",
    "ITA": "Italy",
    "JPN": "Japan",
    "KOR": "South Korea",
    "LAT": "Latvia",
    "LTU": "Lithuania",
    "LUX": "Luxembourg",
    "MEX": "Mexico",
    "NED": "Netherlands",
    "NOR": "Norway",
    "NZL": "New Zealand",
    "POL": "Poland",
    "POR": "Portugal",
    "ROU": "Romania",
    "RSA": "South Africa",
    "RUS": "Russia",
    "SGP": "Singapore",
    "SLO": "Slovenia",
    "SRB": "Serbia",
    "SUI": "Switzerland",
    "SVK": "Slovakia",
    "SWE": "Sweden",
    "TPE": "Chinese Taipei",
    "TUR": "Turkey",
    "UKR": "Ukraine",
    "USA": "United States",
    "VEN": "Venezuela",
}


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
    text = re.sub(r"[^a-z0-9]+", " ", text)
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
    country_map = {
        **IOC_COUNTRY_MAP,
        "US": "United States",
        "UNITED STATES": "United States",
        "UNITED STATES OF AMERICA": "United States",
        "GREAT BRITAIN": "Great Britain",
        "KOREA": "South Korea",
        "HONG KONG, CHINA": "Hong Kong",
        "HONG KONG CHINA": "Hong Kong",
        "TURKIYE": "Turkey",
        "COTE D'IVOIRE": "Cote d'Ivoire",
        "COTE DIVOIRE": "Cote d'Ivoire",
    }
    return country_map.get(key, title_case(text))


def country_key(value):
    return normalize_key(normalize_country(value) or value)


def to_int(value):
    try:
        if value is None or value == "":
            return None
        return int(float(str(value).strip()))
    except Exception:
        return None


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


def batch_upsert(table, rows, on_conflict=None, batch_size=100):
    for i in range(0, len(rows), batch_size):
        kwargs = {"on_conflict": on_conflict} if on_conflict else {}
        supabase.table(table).upsert(rows[i:i + batch_size], **kwargs).execute()


class EngardeClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def request(self, method, path_or_url, **kwargs):
        url = path_or_url if path_or_url.startswith("http") else urljoin(BASE_URL, path_or_url)
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            print(f"  {method} {url} -> {response.status_code} {response.headers.get('content-type', '')}")
            return response
        except requests.RequestException as exc:
            print(f"  {method} {url} failed: {exc}")
            return None
        finally:
            time.sleep(REQUEST_DELAY_SECONDS)

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


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_table = None
        self.current_row = None
        self.current_cell = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "table":
            self.in_table = True
            self.current_table = {"attrs": data, "rows": []}
        elif self.in_table and tag == "tr":
            self.in_row = True
            self.current_row = []
        elif self.in_table and tag in {"td", "th"}:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag):
        if self.in_table and tag in {"td", "th"} and self.in_cell:
            self.current_row.append(clean_text(" ".join(self.current_cell)) or "")
            self.in_cell = False
            self.current_cell = []
        elif self.in_table and tag == "tr" and self.in_row:
            if self.current_row:
                self.current_table["rows"].append(self.current_row)
            self.in_row = False
            self.current_row = None
        elif tag == "table" and self.in_table:
            self.tables.append(self.current_table)
            self.in_table = False
            self.current_table = None

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data)


def fetch_engarde_competitions(client):
    print(f"Fetching Engarde competition list: max_pages={MAX_PAGES}, nrows={DEFAULT_NROWS}")
    competitions = []
    for page in range(1, MAX_PAGES + 1):
        payload = {
            "option": "history",
            "sexe": "",
            "arme": "e,f,s",
            "indiv": "",
            "categorie": "",
            "orderby": "date",
            "datefrom": "",
            "dateto": "",
            "country": "",
            "city": "",
            "type": COMPETITION_TYPES,
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
        response = client.post_form("/prog/getCompeForDisplay.php", payload, accept="text/xml,*/*")
        if response is None or response.status_code != 200 or not response.text.strip():
            print(f"  Stopping at page {page}: empty/non-200 response")
            break
        if response.text.lstrip().startswith("false|"):
            print(f"  Stopping at page {page}: endpoint error {clean_text(response.text)}")
            break
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            print(f"  Stopping at page {page}: XML parse error {exc}")
            break
        page_comps = root.findall(".//comp")
        print(f"  Page {page}: {len(page_comps)} competition rows")
        if not page_comps:
            break
        competitions.extend(parse_competition_node(node) for node in page_comps)
        pagination = root.find(".//pagination")
        if pagination is not None:
            last_page = to_int(pagination.attrib.get("nbpages"))
            if last_page and page >= last_page:
                break
    return competitions


def parse_competition_node(node):
    children = [clean_text("".join(child.itertext())) for child in list(node)]
    attrs = dict(node.attrib)
    source_id = f"engarde:{attrs.get('org')}:{attrs.get('evt')}:{attrs.get('compe')}"
    return {
        "source_id": source_id,
        "org": attrs.get("org"),
        "event": attrs.get("evt"),
        "competition": attrs.get("compe"),
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


def competition_url(comp, suffix=""):
    base = f"{BASE_URL}/competition/{comp['org']}/{comp['event']}/{comp['competition']}"
    return f"{base}/{suffix}" if suffix else base


def tournament_row(comp):
    name = comp.get("name") or comp.get("category") or comp["source_id"]
    country = normalize_country(comp.get("country_code"))
    start_date = comp.get("date")
    return {
        "fie_id": comp["source_id"],
        "source": SOURCE,
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
        "competition_url_id": f"{comp['org']}/{comp['event']}/{comp['competition']}",
        "has_results": comp.get("status") == "completed",
        "metadata": {
            "source": SOURCE,
            "source_id": comp["source_id"],
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
    row = tournament_row(comp)
    supabase.table("fs_tournaments").upsert([row], on_conflict="fie_id").execute()
    data = supabase.table("fs_tournaments").select("id").eq("fie_id", comp["source_id"]).limit(1).execute().data
    if not data:
        raise RuntimeError(f"upserted tournament not found: {comp['source_id']}")
    return data[0]["id"]


def upsert_tournaments(comps):
    rows = [tournament_row(comp) for comp in comps]
    for i in range(0, len(rows), 100):
        batch = rows[i:i + 100]
        try:
            supabase.table("fs_tournaments").upsert(batch, on_conflict="fie_id").execute()
        except Exception as exc:
            print(f"  Tournament batch upsert failed, falling back to per-row upserts: {exc}")
            for row in batch:
                try:
                    supabase.table("fs_tournaments").upsert([row], on_conflict="fie_id").execute()
                except Exception as row_exc:
                    print(f"  Tournament row upsert failed for {row.get('fie_id')}: {row_exc}")
    return fetch_tournament_id_map([comp["source_id"] for comp in comps])


def fetch_tournament_id_map(source_ids):
    tournament_ids = {}
    for i in range(0, len(source_ids), 100):
        batch = source_ids[i:i + 100]
        data = (
            supabase.table("fs_tournaments")
            .select("id,fie_id")
            .in_("fie_id", batch)
            .execute()
            .data
        )
        for row in data or []:
            tournament_ids[row["fie_id"]] = row["id"]
    return tournament_ids


def fetch_all_fencers():
    print("Loading fs_fencers for name/country matching...")
    rows = []
    start = 0
    page_size = 1000
    while True:
        data = (
            supabase.table("fs_fencers")
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
        exact[(normalize_key(name), ckey)] = row
        parts = normalize_key(name).split()
        for size in range(1, min(3, len(parts)) + 1):
            key = (" ".join(parts[-size:]), ckey)
            last.setdefault(key, []).append(row)
    return {"exact": exact, "last": last}


def match_fencer(index, full_name, last_name, country):
    ckey = country_key(country)
    if not full_name or not ckey:
        return None, None
    exact = index["exact"].get((normalize_key(full_name), ckey))
    if exact:
        return exact, "exact_name_country"
    last_key = normalize_key(last_name)
    if last_key:
        candidates = index["last"].get((last_key, ckey), [])
        if len(candidates) == 1:
            return candidates[0], "last_name_country"
    return None, None


def discover_result_links(base_url, html_text):
    parser = LinkCollector()
    parser.feed(html_text)
    links = []
    for href in parser.links:
        lower = href.lower()
        if lower.endswith("clasfinal.htm") or lower.endswith("classement.htm"):
            links.append(urljoin(base_url, href))
    return list(dict.fromkeys(links))


def parse_result_rows(html_text):
    parser = TableParser()
    parser.feed(html_text)
    result_rows = []
    for table in parser.tables:
        rows = table.get("rows", [])
        if len(rows) < 2:
            continue
        header = [normalize_key(cell) for cell in rows[0]]
        rank_col = 0
        if not any(token in (header[rank_col] if header else "") for token in ("rg", "rank", "rang", "place")):
            continue
        first_name_col = None
        club_col = None
        country_col = None
        for idx, label in enumerate(header):
            if any(token in label for token in ("prenom", "first", "forename", "kereszt")):
                first_name_col = idx
            if any(token in label for token in ("club", "team", "equipe", "egyesulet", "vereniging")):
                club_col = idx
            if any(token in label for token in ("country", "pays", "nation", "ioc")):
                country_col = idx
        for row in rows[1:]:
            if len(row) < 2:
                continue
            rank = to_int(row[rank_col])
            if not rank:
                continue
            last_name = clean_text(row[1])
            first_name = clean_text(row[first_name_col]) if first_name_col is not None and len(row) > first_name_col else None
            if first_name and last_name:
                full_name = title_case(f"{first_name} {last_name}")
            else:
                full_name = title_case(last_name)
            club = clean_text(row[club_col]) if club_col is not None and len(row) > club_col else None
            row_country = clean_text(row[country_col]) if country_col is not None and len(row) > country_col else None
            result_rows.append({
                "rank": rank,
                "name": full_name,
                "last_name": title_case(last_name),
                "first_name": title_case(first_name),
                "club": club,
                "country": row_country,
                "raw_cells": row,
            })
        if result_rows:
            break
    return result_rows


def fetch_result_rows(client, comp):
    final_url = competition_url(comp, "clasfinal.htm")
    html_text = client.get_text(final_url)
    rows = parse_result_rows(html_text or "")
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
        rows = parse_result_rows(link_html or "")
        if rows:
            return rows, link
    return [], final_url


def result_rows_for_db(tournament_id, comp, scraped_rows, fencer_index, result_url):
    tournament_country = normalize_country(comp.get("country_code"))
    rows = []
    for row in scraped_rows:
        country = normalize_country(row.get("country")) or tournament_country
        matched, match_method = match_fencer(
            fencer_index,
            row.get("name"),
            row.get("last_name"),
            country,
        )
        rows.append({
            "tournament_id": tournament_id,
            "fencer_id": matched.get("id") if matched else None,
            "fie_fencer_id": str(matched.get("fie_id")) if matched and matched.get("fie_id") else None,
            "source": SOURCE,
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


def replace_results(tournament_id, rows):
    supabase.table("fs_results").delete().eq("tournament_id", tournament_id).eq("source", SOURCE).execute()
    if rows:
        batch_upsert("fs_results", rows)


def should_scrape(comp):
    if comp.get("status") != "completed":
        return False
    if not comp.get("is_individual"):
        return False
    if SKIP_FIE_TYPE and (comp.get("type") or "").lower() == "fie":
        return False
    return True


def scrape_engarde():
    print(ENDPOINT_NOTES.strip())
    print(f"Engarde scraper starting - {datetime.now(timezone.utc).isoformat()}")
    client = EngardeClient()
    fencer_index = fetch_all_fencers()
    competitions = fetch_engarde_competitions(client)
    to_scrape = [comp for comp in competitions if should_scrape(comp)]
    print(f"Found {len(competitions)} competition rows; {len(to_scrape)} completed individual non-FIE rows to scrape")
    tournament_ids = upsert_tournaments(to_scrape) if to_scrape else {}

    scraped = 0
    failed = 0
    for comp in to_scrape:
        label = f"{comp.get('name')} ({comp['source_id']})"
        try:
            print(f"Scraping {label}")
            tournament_id = tournament_ids.get(comp["source_id"]) or upsert_tournament(comp)
            scraped_rows, result_url = fetch_result_rows(client, comp)
            if not scraped_rows:
                print(f"  No final individual result rows found for {label}")
                failed += 1
                continue
            rows = result_rows_for_db(tournament_id, comp, scraped_rows, fencer_index, result_url)
            replace_results(tournament_id, rows)
            print(f"  Upserted {len(rows)} results from {result_url}")
            scraped += 1
        except Exception as exc:
            failed += 1
            print(f"  Error scraping {label}: {exc}")
            continue

    print(f"Done - {scraped} Engarde competitions scraped, {failed} failed/skipped after fetch")


if __name__ == "__main__":
    scrape_engarde()

"""
Maccabiah Games fencing results scraper.

Probe findings (2026-06-01):
  - Olympedia has Olympic fencing result pages and Maccabiah mentions in athlete
    bios, but no public Maccabiah editions/results index was found.
  - m21.maccabiah.com fencing page links to EngardeSmart
    (app.php?id=2502G6). Engarde public endpoints expose 2022 Maccabiah
    individual/team competition listings and final classifications.
  - m20.maccabiah.com fencing page is regulations-only; no public structured
    fencing result link was found.
"""

import html
import os
import re
import time
from datetime import UTC, datetime, timezone
from typing import Any, cast
from urllib.parse import parse_qs, urljoin, urlparse

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


SOURCE = "maccabiah"
ENGARDE_BASE = "https://engarde-service.com"
REQUEST_DELAY = 2.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

FORM_HEADERS = {
    **HEADERS,
    "Accept": "text/html,*/*;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

MACCABIAH_EDITIONS = [
    {
        "edition_id": "m21",
        "edition_name": "21st Maccabiah 2022",
        "official_url": "https://m21.maccabiah.com/en/the-games/m21-sports/fencing",
        "source_format": "official_engarde",
    },
    {
        "edition_id": "m20",
        "edition_name": "20th Maccabiah 2017",
        "official_url": "https://m20.maccabiah.com/the-games/667-fencing",
        "source_format": "official_html_stub",
    },
]

WEAPON_CODE_MAP = {"e": "Epee", "f": "Foil", "s": "Sabre"}
GENDER_CODE_MAP = {"m": "Men", "f": "Women", "n": "Mixed"}
CATEGORY_MAP = {
    "junior": "Junior",
    "cadet": "Cadet",
    "senior": "Senior",
    "open": "Senior",
    "veteran": "Veteran",
    "masters": "Veteran",
    "master": "Veteran",
}

WEAPON_PATTERNS = [
    (re.compile(r"\b(?:epee|epée|[eé]p[ée]e)\b|\u05d3\u05e7\u05e8", re.I), "Epee"),
    (re.compile(r"\bfoil\b|\u05e8\u05d5\u05de\u05d7", re.I), "Foil"),
    (re.compile(r"\b(?:sabre|saber)\b|\u05d7\u05e8\u05d1", re.I), "Sabre"),
]
GENDER_PATTERNS = [
    (re.compile(r"\b(?:women|woman|female|girls?)\b|\u05e0\u05e9\u05d9\u05dd|\u05e0\u05e2\u05e8\u05d5\u05ea", re.I), "Women"),
    (re.compile(r"\b(?:men|man|male|boys?)\b|\u05d2\u05d1\u05e8\u05d9\u05dd|\u05e0\u05e2\u05e8\u05d9\u05dd", re.I), "Men"),
]


def clean_text(value):
    text = html.unescape(str(value or "")).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _title_name(value):
    text = clean_text(value)
    return text.title() if text else None


def _strip_quotes(value):
    text = clean_text(value) or ""
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    return html.unescape(text)


def _to_int(value):
    try:
        if value is None:
            return None
        return int(re.sub(r"\D", "", str(value)))
    except Exception:
        return None


def _medal_for_rank(rank):
    return {1: "Gold", 2: "Silver", 3: "Bronze"}.get(rank)


def _source_id(edition_id, event_code):
    return f"{SOURCE}:{edition_id}:{event_code}"


def _extract_year(*values):
    for value in values:
        match = re.search(r"\b(20\d{2}|19\d{2})\b", str(value or ""))
        if match:
            return match.group(1)
    return None


def _normalize_date(value):
    text = clean_text(value)
    if not text:
        return None
    for pattern, order in (
        (r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", "mdy"),
        (r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", "ymd"),
    ):
        match = re.search(pattern, text)
        if not match:
            continue
        parts = [int(p) for p in match.groups()]
        if order == "mdy":
            month, day, year = parts
            if year < 100:
                year += 2000
        else:
            year, month, day = parts
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def classify_event(event_title, fields=None):
    fields = fields or {}
    title = clean_text(event_title) or ""

    weapon = WEAPON_CODE_MAP.get((fields.get("arme") or "").lower())
    if not weapon:
        weapon = next((w for pattern, w in WEAPON_PATTERNS if pattern.search(title)), None)

    gender = GENDER_CODE_MAP.get((fields.get("sexe") or "").lower())
    if not gender:
        gender = next((g for pattern, g in GENDER_PATTERNS if pattern.search(title)), None)

    if fields.get("indiv") in {"0", 0}:
        team = True
    elif fields.get("indiv") in {"1", 1}:
        team = False
    else:
        team = bool(re.search(r"\bteam\b|\u05e7\u05d1\u05d5\u05e6", title, re.I))

    raw_category = (fields.get("categorie") or "").lower()
    category = CATEGORY_MAP.get(raw_category)
    if not category:
        lowered = title.lower()
        category = next((label for key, label in CATEGORY_MAP.items() if key in lowered), "Senior")

    return {"weapon": weapon, "gender": gender, "team": team, "category": category}


def parse_olympedia_like_events(html_text, edition):
    soup = BeautifulSoup(html_text or "", "html.parser")
    events = []
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 1:
            continue
        link = row.find("a", href=re.compile(r"/results/[^/?#]+"))
        if not link:
            continue
        match = re.search(r"/results/([^/?#]+)", link.get("href", ""))
        if not match:
            continue
        event_code = match.group(1)
        original_title = clean_text(link.get_text(" "))
        classification = classify_event(original_title)
        if not classification["weapon"] or not classification["gender"]:
            continue
        event_url = urljoin(edition.get("base_url") or edition.get("official_url") or "", link["href"])
        events.append({
            "source_id": _source_id(edition["edition_id"], event_code),
            "source_format": "olympedia_like_html",
            "edition_id": edition["edition_id"],
            "edition_name": edition["edition_name"],
            "event_code": event_code,
            "event_title": original_title,
            "original_title": original_title,
            "result_url": event_url,
            "date": clean_text(cells[2].get_text(" ")) if len(cells) > 2 else None,
            "classification": classification,
            "metadata": {
                "source": SOURCE,
                "source_format": "olympedia_like_html",
                "original_title": original_title,
                "result_url": event_url,
            },
        })
    return events


def _header_map(cells):
    labels = [
        re.sub(r"[^a-z0-9]+", " ", (clean_text(c.get_text(" ")) or "").lower()).strip()
        for c in cells
    ]
    mapping: dict[Any, Any] = {}
    for idx, label in enumerate(labels):
        if not label:
            continue
        if any(token in label for token in ("pos", "rank", "place", "rang")):
            mapping.setdefault("rank", idx)
        elif any(token in label for token in ("competitor", "athlete", "name", "fencer")):
            mapping.setdefault("name", idx)
        elif any(token in label for token in ("noc", "country", "nation", "delegation")):
            mapping.setdefault("country", idx)
        elif "medal" in label:
            mapping.setdefault("medal", idx)
    return mapping


def parse_olympedia_like_results(html_text):
    soup = BeautifulSoup(html_text or "", "html.parser")
    for table in soup.find_all("table"):
        classes = table.get("class", [])
        if "biodata" in classes:
            continue
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        header_cells = rows[0].find_all(["td", "th"])
        mapping = _header_map(header_cells)
        if "rank" not in mapping:
            continue
        mapping.setdefault("name", 2)
        mapping.setdefault("country", 3)
        mapping.setdefault("medal", 4)

        result_rows = []
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(mapping.values()):
                continue
            rank = _to_int(cells[mapping["rank"]].get_text(" "))
            name_cell = cells[mapping["name"]]
            name = clean_text(name_cell.get_text(" "))
            if not rank or not name:
                continue
            athlete_link = name_cell.find("a", href=re.compile(r"/athletes/\d+"))
            athlete_id = None
            if athlete_link:
                match = re.search(r"/athletes/(\d+)", athlete_link.get("href", ""))
                athlete_id = match.group(1) if match else None
            medal = clean_text(cells[mapping["medal"]].get_text(" "))
            result_rows.append({
                "rank": rank,
                "name": name,
                "country": clean_text(cells[mapping["country"]].get_text(" ")),
                "medal": medal if medal in {"Gold", "Silver", "Bronze"} else _medal_for_rank(rank),
                "athlete_id": athlete_id,
            })
        if result_rows:
            return result_rows
    return []


def parse_official_table_rows(html_text):
    """Parse simple official HTML result tables with rank/name/delegation columns."""
    soup = BeautifulSoup(html_text or "", "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        header_cells = rows[0].find_all(["td", "th"])
        mapping = _header_map(header_cells)
        if not {"rank", "name", "country"}.issubset(mapping):
            continue

        result_rows = []
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(mapping["rank"], mapping["name"], mapping["country"]):
                continue
            rank = _to_int(cells[mapping["rank"]].get_text(" "))
            name_cell = cells[mapping["name"]]
            name = clean_text(name_cell.get_text(" "))
            if not rank or not name:
                continue
            athlete_link = name_cell.find("a", href=re.compile(r"/athletes/\d+"))
            athlete_id = None
            if athlete_link:
                match = re.search(r"/athletes/(\d+)", athlete_link.get("href", ""))
                athlete_id = match.group(1) if match else None
            medal = None
            if "medal" in mapping and len(cells) > mapping["medal"]:
                medal = clean_text(cells[mapping["medal"]].get_text(" "))
            result_rows.append({
                "rank": rank,
                "name": name,
                "country": clean_text(cells[mapping["country"]].get_text(" ")),
                "medal": medal if medal in {"Gold", "Silver", "Bronze"} else _medal_for_rank(rank),
                "athlete_id": athlete_id,
            })
        if result_rows:
            return result_rows
    return []


def discover_official_page(html_text, edition, source_url):
    soup = BeautifulSoup(html_text or "", "html.parser")
    engarde_ids = []
    for link in soup.find_all("a", href=True):
        href = urljoin(source_url, link["href"])
        if "engarde-service.com" not in href:
            continue
        query = parse_qs(urlparse(href).query)
        engarde_values = query.get("id") or []
        engarde_id = engarde_values[0] if engarde_values else None
        if engarde_id and engarde_id not in engarde_ids:
            engarde_ids.append(engarde_id)

    probe_dates = []
    for match in re.finditer(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b20\d{2}-\d{1,2}-\d{1,2}\b", soup.get_text(" ")):
        normalized = _normalize_date(match.group(0))
        if normalized and normalized not in probe_dates:
            probe_dates.append(normalized)

    page = {
        "edition_id": edition["edition_id"],
        "edition_name": edition["edition_name"],
        "source_url": source_url,
        "engarde_ids": engarde_ids,
        "probe_dates": probe_dates,
        "stub": None,
    }
    text = (soup.get_text(" ") or "").lower()
    if not engarde_ids and "fencing" in text:
        page["stub"] = {
            "source_id": _source_id(edition["edition_id"], "no-structured-results"),
            "source_format": "stub",
            "edition_id": edition["edition_id"],
            "edition_name": edition["edition_name"],
            "event_code": "no-structured-results",
            "event_title": "Fencing",
            "original_title": clean_text(soup.find(["h1", "h2"]).get_text(" ")) if soup.find(["h1", "h2"]) else "Fencing",
            "result_url": source_url,
            "classification": {"weapon": None, "gender": None, "team": False, "category": "Senior"},
            "metadata": {
                "source": SOURCE,
                "source_format": "stub",
                "official_url": source_url,
                "source_limitations": "official page contains fencing regulations but no structured result link",
            },
        }
    return page


def _parse_field_pairs(block):
    fields = {}
    for match in re.finditer(r"\[([A-Za-z_][A-Za-z0-9_]*)\s*([^\]]*)\]", block, re.S):
        key = match.group(1)
        value = _strip_quotes(match.group(2))
        fields[key] = value
    return fields


def _parse_braced_objects(text):
    return [match.group(1) for match in re.finditer(r"\{([^{}]*)\}", text or "", re.S)]


def parse_official_event_listing(listing_text, edition, source_url):
    events = []
    seen = set()
    for block in _parse_braced_objects(listing_text):
        fields = _parse_field_pairs(block)
        if not fields.get("compe") or not fields.get("IdSmart"):
            continue
        title = fields.get("titre") or fields.get("compe")
        event_name = fields.get("event") or ""
        if "maccab" not in f"{event_name} {title}".lower():
            continue
        classification = classify_event(title, fields)
        if not classification["weapon"] or not classification["gender"]:
            continue
        event_code = fields["IdSmart"]
        if event_code in seen:
            continue
        seen.add(event_code)
        source_id = _source_id(edition["edition_id"], event_code)
        result_url = f"{ENGARDE_BASE}/app.php?id={event_code}"
        metadata = {
            "source": SOURCE,
            "source_format": "official_engarde",
            "official_url": source_url,
            "original_title": title,
            "event_code": event_code,
            "event": fields.get("event"),
            "compe": fields.get("compe"),
            "id_smart": event_code,
            "raw": fields,
        }
        events.append({
            "source_id": source_id,
            "source_format": "official_engarde",
            "edition_id": edition["edition_id"],
            "edition_name": edition["edition_name"],
            "event_code": event_code,
            "event_title": title,
            "original_title": title,
            "result_url": result_url,
            "date": fields.get("date"),
            "date_end": fields.get("dateFin"),
            "country": fields.get("pays"),
            "city": fields.get("ville"),
            "classification": classification,
            "metadata": metadata,
        })
    return events


def _objects_with_class(data_text, class_name):
    objects = []
    expected = f"[classe {class_name}]"
    for block in _parse_braced_objects(data_text):
        if expected in block:
            objects.append(_parse_field_pairs(block))
    return objects


def _classification_objects(data_text):
    objects = []
    for block in _parse_braced_objects(data_text):
        fields = _parse_field_pairs(block)
        if fields.get("nom") in {"clas_gene", "clastab_prov", "clas_fin_poules"} and fields.get("classement"):
            objects.append(fields)
    return objects


def _format_person_name(first_name, last_name):
    parts = [_title_name(first_name), _title_name(last_name)]
    return clean_text(" ".join(part for part in parts if part))


def parse_official_result_data(data_text):
    if not data_text or data_text.lstrip().startswith("false"):
        return []

    nations = {
        fields.get("cle"): fields.get("nom")
        for fields in _objects_with_class(data_text, "nation")
        if fields.get("cle")
    }

    entities = {}
    for fields in _objects_with_class(data_text, "tireur"):
        key = fields.get("cle")
        if not key:
            continue
        country = nations.get(fields.get("nation1")) or fields.get("nation1")
        entities[key] = {
            "name": _format_person_name(fields.get("prenom"), fields.get("nom")) or key,
            "country": country,
            "raw": fields,
        }

    for fields in _objects_with_class(data_text, "equipe"):
        key = fields.get("cle")
        if not key:
            continue
        country = nations.get(fields.get("nation1")) or fields.get("nation1")
        entities[key] = {
            "name": _title_name(fields.get("nom")) or country or key,
            "country": country,
            "raw": fields,
        }

    classifications = _classification_objects(data_text)
    final = next((item for item in classifications if item.get("nom") == "clas_gene"), None)
    if not final:
        final = next((item for item in classifications if item.get("nom") == "clastab_prov"), None)
    if not final:
        return []

    ranking = re.sub(r"\(\s*\)", " nil ", final.get("classement") or "")
    rows = []
    for match in re.finditer(r"\(([qe])\s+(\d+)\s+([A-Za-z0-9_-]+)\b[^)]*\)", ranking):
        rank = int(match.group(2))
        entity_key = match.group(3)
        entity = entities.get(entity_key, {})
        rows.append({
            "rank": rank,
            "name": entity.get("name") or entity_key,
            "country": entity.get("country"),
            "medal": _medal_for_rank(rank),
            "entity_key": entity_key,
        })
    return rows


def _get(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                return response.text
            if response.status_code == 404:
                return None
            print(f"  HTTP {response.status_code} for {url}")
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
            else:
                return None
        except requests.RequestException as exc:
            print(f"  fetch {url} attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** attempt)
    return None


def _post_engarde(path, data, retries=3):
    url = urljoin(f"{ENGARDE_BASE}/", path)
    for attempt in range(retries):
        try:
            response = requests.post(url, data=data, headers=FORM_HEADERS, timeout=30)
            if response.status_code == 200:
                return response.text
            print(f"  HTTP {response.status_code} for {url}")
        except requests.RequestException as exc:
            print(f"  post {url} attempt {attempt + 1} failed: {exc}")
        time.sleep(2 ** attempt)
    return None


def fetch_official_event_listing(probe_date):
    return _post_engarde(
        "/prog/smart_get_event_and_compeV2.php",
        {"Date": probe_date, "Test": "0", "NumTache": "1"},
    )


def fetch_official_result_data(event_code):
    return _post_engarde(
        "/prog/smart_get_data.php",
        {"IdCompe": event_code, "ceci": "*", "competition": event_code, "NumTache": "2"},
    )


def fetch_official_result_url(event_code):
    text = _post_engarde(
        "/prog/smart_get_url_repertoire_html.php",
        {"IdCompe": event_code, "NumTache": "3"},
    )
    if not text or text.startswith("false"):
        return None
    return clean_text(text.split(";#!", 1)[0])


def discover_events():
    discovered = []
    for edition in MACCABIAH_EDITIONS:
        url = edition.get("official_url")
        if not url:
            continue
        html_text = _get(url)
        if not html_text:
            continue
        page = discover_official_page(html_text, edition, url)
        if page.get("stub"):
            discovered.append(page["stub"])
            continue
        probe_dates = cast(list[str], page["probe_dates"] or edition.get("probe_dates") or [])
        edition_events = []
        for probe_date in probe_dates:
            listing = fetch_official_event_listing(probe_date)
            edition_events.extend(parse_official_event_listing(listing or "", edition, url))
            time.sleep(0.5)
        unique = {event["event_code"]: event for event in edition_events}
        discovered.extend(unique.values())
    return discovered


def upsert_tournament(event):
    classification = event["classification"]
    metadata = {
        "source": SOURCE,
        "source_id": event["source_id"],
        "edition_id": event["edition_id"],
        "edition_name": event["edition_name"],
        "event_code": event["event_code"],
        "original_title": event.get("original_title") or event.get("event_title"),
        "team": classification["team"],
        **(event.get("metadata") or {}),
    }
    row = {
        "source_id": event["source_id"],
        "name": f"{event['edition_name']} - {event['event_title']}",
        "season": _extract_year(event.get("date"), event.get("edition_name")),
        "type": "maccabiah",
        "weapon": classification["weapon"],
        "gender": classification["gender"],
        "category": classification["category"],
        "country": event.get("country"),
        "location": event.get("city"),
        "start_date": event.get("date"),
        "end_date": event.get("date_end") or event.get("date"),
        "has_results": True,
        "metadata": metadata,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    try:
        result = supabase.table("fs_tournaments").upsert(row, on_conflict="source_id").execute()  # type: ignore[union-attr]
        return result.data[0]["id"] if result.data else None
    except Exception as exc:
        print(f"  Tournament upsert failed for {event['source_id']}: {exc}")
        return None


def _match_fencer(name, country):
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


def upsert_results(tournament_id, event, result_rows):
    db_rows = []
    for row in result_rows:
        rank = row.get("rank")
        name = row.get("name")
        if not rank or not name:
            continue
        country = row.get("country")
        fencer_id = _match_fencer(name, country) if country else None
        db_rows.append({
            "tournament_id": tournament_id,
            "fencer_id": fencer_id,
            "rank": rank,
            "placement": rank,
            "name": name,
            "country": country,
            "nationality": country,
            "medal": row.get("medal") or _medal_for_rank(rank),
            "metadata": {
                "source": SOURCE,
                "source_id": event["source_id"],
                "event_code": event["event_code"],
                "athlete_id": row.get("athlete_id"),
                "entity_key": row.get("entity_key"),
                "raw": row.get("raw"),
            },
            "updated_at": datetime.now(UTC).isoformat(),
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
            print(f"  Results insert failed for {event['source_id']}: {exc}")
    return written if written == len(db_rows) else 0


def fetch_result_rows(event):
    if event["source_format"] == "official_engarde":
        result_url = fetch_official_result_url(event["event_code"])
        if result_url:
            event.setdefault("metadata", {})["result_url"] = result_url
        data_text = fetch_official_result_data(event["event_code"])
        return parse_official_result_data(data_text or "")
    if event["source_format"] == "olympedia_like_html":
        html_text = _get(event["result_url"])
        return parse_olympedia_like_results(html_text or "")
    return []


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_maccabiah").start()
    try:
        print(f"Maccabiah scraper starting - {datetime.now(UTC).isoformat()}")
        done_codes = set(get_state(SOURCE, "done_event_codes") or [])
        events = discover_events()
        print(f"  {len(events)} Maccabiah fencing event/stub rows discovered")

        written = failed = skipped = 0
        for event in events:
            if event["source_format"] == "stub":
                print(f"  Skipping stub {event['source_id']}: {event['metadata'].get('source_limitations')}")
                skipped += 1
                continue
            if event["event_code"] in done_codes:
                skipped += 1
                continue
            classification = event["classification"]
            if not classification["weapon"] or not classification["gender"]:
                print(f"  Skipping unclassifiable event: {event.get('event_title')}")
                skipped += 1
                continue

            print(f"  Scraping {event['event_title']} ({event['source_id']})")
            result_rows = fetch_result_rows(event)
            if not result_rows:
                print(f"    No structured result rows found")
                skipped += 1
                continue

            tournament_id = upsert_tournament(event)
            if not tournament_id:
                failed += 1
                continue
            inserted = upsert_results(tournament_id, event, result_rows)
            if inserted == 0:
                failed += 1
                continue

            done_codes.add(event["event_code"])
            set_state(SOURCE, "done_event_codes", list(done_codes))
            written += 1
            time.sleep(REQUEST_DELAY)

        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"Done - written={written}, failed={failed}, skipped={skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

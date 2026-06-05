import html
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, unquote, urlparse

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

SOURCE = "wikipedia_bios"
REQUEST_DELAY = float(os.environ.get("WIKIPEDIA_BIO_REQUEST_DELAY", "1.0"))
PAGE_SIZE = int(os.environ.get("WIKIPEDIA_BIO_PAGE_SIZE", "100"))
MAX_FENCERS = int(os.environ.get("WIKIPEDIA_BIO_LIMIT", "0"))
REQUEST_TIMEOUT = int(os.environ.get("WIKIPEDIA_BIO_TIMEOUT", "30"))

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; plerngh@gmail.com)",
}

FENCER_SELECT = (
    "id,name,country,metadata,birth_place,"
    "bio_source,bio_text,wikipedia_url,nickname,height,weight"
)
PENDING_FIELD_FILTER = "birth_place.is.null,bio_source.is.null"
MATCH_FILTERS = (
    ("metadata->>wikidata_id", "not.is", "null"),
    ("wikipedia_url", "not.is", "null"),
    ("metadata->>wikipedia_url", "not.is", "null"),
    ("metadata->>wiki_url", "not.is", "null"),
    ("metadata->>wikipedia_title", "not.is", "null"),
    ("metadata->>wiki_title", "not.is", "null"),
)
BIO_REFRESH_MIN_EXTRA_CHARS = 24

COUNTRY_LANGUAGES = {
    "ARG": ["es"],
    "ARGENTINA": ["es"],
    "AUS": ["en"],
    "AUSTRALIA": ["en"],
    "AUT": ["de"],
    "AUSTRIA": ["de"],
    "BEL": ["fr", "nl"],
    "BELGIUM": ["fr", "nl"],
    "BRA": ["pt"],
    "BRAZIL": ["pt"],
    "CAN": ["en", "fr"],
    "CANADA": ["en", "fr"],
    "CHE": ["de", "fr", "it"],
    "SWITZERLAND": ["de", "fr", "it"],
    "CHN": ["zh"],
    "CHINA": ["zh"],
    "DEU": ["de"],
    "GER": ["de"],
    "GERMANY": ["de"],
    "EGY": ["ar"],
    "EGYPT": ["ar"],
    "ESP": ["es"],
    "SPAIN": ["es"],
    "FRA": ["fr"],
    "FRANCE": ["fr"],
    "GBR": ["en"],
    "GREAT BRITAIN": ["en"],
    "UNITED KINGDOM": ["en"],
    "HUN": ["hu"],
    "HUNGARY": ["hu"],
    "IRL": ["en"],
    "IRELAND": ["en"],
    "ITA": ["it"],
    "ITALY": ["it"],
    "JPN": ["ja"],
    "JAPAN": ["ja"],
    "KOR": ["ko"],
    "KOREA": ["ko"],
    "SOUTH KOREA": ["ko"],
    "MEX": ["es"],
    "MEXICO": ["es"],
    "NED": ["nl"],
    "NETHERLANDS": ["nl"],
    "POL": ["pl"],
    "POLAND": ["pl"],
    "ROU": ["ro"],
    "ROMANIA": ["ro"],
    "RUS": ["ru"],
    "RUSSIA": ["ru"],
    "UKR": ["uk"],
    "UKRAINE": ["uk"],
    "USA": ["en"],
    "UNITED STATES": ["en"],
    "UNITED STATES OF AMERICA": ["en"],
}

BORN_LABELS = {
    "born",
    "nato",
    "nata",
    "natoa",
    "nataa",
    "ne",
    "nee",
    "naissance",
    "geboren",
    "nacido",
    "nacida",
    "nacimiento",
    "urodzony",
    "urodzona",
}
BIRTH_PLACE_LABELS = {
    "birthplace",
    "placeofbirth",
    "luogodinascita",
    "lieudenaissance",
    "geburtsort",
    "lugardenacimiento",
    "miejsceurodzenia",
}
HEIGHT_LABELS = {"height", "altezza", "taille", "grosse", "groesse", "estatura", "wzrost"}
WEIGHT_LABELS = {"weight", "peso", "poids", "gewicht", "waga"}
NICKNAME_LABELS = {
    "nickname",
    "nicknames",
    "surnom",
    "surnoms",
    "soprannome",
    "soprannomi",
    "spitzname",
    "apodo",
    "apodos",
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = html.unescape(str(value)).replace("\xa0", " ")
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" \t\r\n,;")
    return text or None


def normalize_label(value: str | None) -> str:
    text = clean_text(value) or ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return re.sub(r"[^A-Za-z0-9 ]+", "", text).upper()


def normalize_wikidata_id(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\bQ(\d+)\b", text, flags=re.IGNORECASE)
    if match:
        return f"Q{match.group(1)}"
    if re.fullmatch(r"\d+", text):
        return f"Q{text}"
    return None


def metadata_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def fencer_wikidata_id(fencer: dict[str, Any]) -> str | None:
    metadata = metadata_dict(fencer.get("metadata"))
    return normalize_wikidata_id(metadata.get("wikidata_id") or fencer.get("wikidata_id"))


def value_from_fencer_or_metadata(fencer: dict[str, Any], keys: list[str]) -> Any:
    metadata = metadata_dict(fencer.get("metadata"))
    for key in keys:
        if fencer.get(key) not in (None, ""):
            return fencer.get(key)
        if metadata.get(key) not in (None, ""):
            return metadata.get(key)
    return None


def language_candidates(fencer: dict[str, Any]) -> list[str]:
    languages: list[str] = []
    for field in ("country", "nationality"):
        key = normalize_country(fencer.get(field))
        for lang in COUNTRY_LANGUAGES.get(key or "", []):
            if lang not in languages:
                languages.append(lang)
    if "en" not in languages:
        languages.append("en")
    return languages


def request_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    sleep_func=time.sleep,
) -> dict[str, Any] | None:
    try:
        response = session.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    finally:
        if REQUEST_DELAY > 0:
            sleep_func(REQUEST_DELAY)


def fetch_wikidata_entity(
    qid: str,
    *,
    session: requests.Session,
    sleep_func=time.sleep,
) -> dict[str, Any]:
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    payload = request_json(session, url, sleep_func=sleep_func)
    entity = (payload or {}).get("entities", {}).get(qid, {})
    return entity if isinstance(entity, dict) else {}


def wikidata_sitelinks_from_entity(entity: dict[str, Any]) -> dict[str, str]:
    sitelinks = entity.get("sitelinks") or {}
    if not isinstance(sitelinks, dict):
        return {}
    return {
        key.removesuffix("wiki"): str(value.get("title"))
        for key, value in sitelinks.items()
        if key.endswith("wiki") and isinstance(value, dict) and value.get("title") is not None
    }


def fetch_wikidata_sitelinks(
    qid: str,
    *,
    session: requests.Session,
    sleep_func=time.sleep,
) -> dict[str, str]:
    return wikidata_sitelinks_from_entity(
        fetch_wikidata_entity(qid, session=session, sleep_func=sleep_func)
    )


def first_wikidata_claim_value(entity: dict[str, Any], property_id: str) -> Any:
    claims = entity.get("claims") or {}
    property_claims = claims.get(property_id) if isinstance(claims, dict) else None
    if not isinstance(property_claims, list):
        return None
    for claim in property_claims:
        snak = claim.get("mainsnak") if isinstance(claim, dict) else None
        datavalue = (snak or {}).get("datavalue") if isinstance(snak, dict) else None
        value = (datavalue or {}).get("value") if isinstance(datavalue, dict) else None
        if value is not None:
            return value
    return None


def parse_wikidata_time_value(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    try:
        precision = int(value.get("precision") or 0)
    except (TypeError, ValueError):
        precision = 0
    if precision < 11:
        return None

    raw_time = str(value.get("time") or "")
    match = re.match(r"^\+?(\d{4})-(\d{2})-(\d{2})T", raw_time)
    if not match:
        return None
    year, month, day = match.groups()
    if month == "00" or day == "00":
        return None
    try:
        datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
    except ValueError:
        return None
    return f"{year}-{month}-{day}"


def wikidata_item_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    qid = normalize_wikidata_id(value.get("id"))
    if qid:
        return qid
    numeric_id = value.get("numeric-id")
    return normalize_wikidata_id(str(numeric_id)) if numeric_id is not None else None


def wikidata_entity_label(entity: dict[str, Any]) -> str | None:
    labels = entity.get("labels") or {}
    if not isinstance(labels, dict):
        return None
    preferred = labels.get("en")
    if isinstance(preferred, dict):
        label = clean_text(preferred.get("value"))
        if label:
            return label
    for value in labels.values():
        if isinstance(value, dict):
            label = clean_text(value.get("value"))
            if label:
                return label
    return None


def fetch_wikidata_birth_details(
    entity: dict[str, Any],
    *,
    session: requests.Session,
    sleep_func=time.sleep,
) -> dict[str, str]:
    details: dict[str, str] = {}

    birth_date = parse_wikidata_time_value(first_wikidata_claim_value(entity, "P569"))
    if birth_date:
        details["birth_date"] = birth_date

    place_qid = wikidata_item_id(first_wikidata_claim_value(entity, "P19"))
    if place_qid:
        place_entity = fetch_wikidata_entity(place_qid, session=session, sleep_func=sleep_func)
        birth_place = wikidata_entity_label(place_entity)
        if birth_place:
            details["birth_place"] = birth_place

    return details


def first_paragraph(extract: str | None) -> str | None:
    text = (extract or "").strip()
    if not text:
        return None
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return clean_text(paragraphs[0] if paragraphs else text)


def parse_wikipedia_summary(payload: dict[str, Any] | None) -> dict[str, str] | None:
    if not payload or payload.get("type") == "disambiguation":
        return None
    bio = first_paragraph(payload.get("extract"))
    if not bio:
        return None
    content_urls = payload.get("content_urls") or {}
    desktop = content_urls.get("desktop") if isinstance(content_urls, dict) else {}
    page_url = (desktop or {}).get("page") or payload.get("page_url")
    result = {"bio": bio, "bio_text": bio}
    source = clean_text(page_url)
    if source:
        result["wikipedia_url"] = source
        result["bio_source"] = source
    return result


def summary_to_enrichment(payload: dict[str, Any] | None) -> dict[str, str] | None:
    parsed = parse_wikipedia_summary(payload)
    if not parsed:
        return None
    return {
        key: parsed[key]
        for key in ("bio_text", "wikipedia_url")
        if parsed.get(key)
    }


def fetch_summary(
    title: str,
    lang: str,
    *,
    session: requests.Session,
    sleep_func=time.sleep,
) -> dict[str, str] | None:
    encoded = quote(title, safe="")
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    return summary_to_enrichment(request_json(session, url, sleep_func=sleep_func))


def is_birth_date_fragment(text: str) -> bool:
    month_names = (
        "january|february|march|april|may|june|july|august|"
        "september|october|november|december|jan|feb|mar|apr|jun|jul|"
        "aug|sep|sept|oct|nov|dec"
    )
    lowered = text.lower()
    if re.fullmatch(r"[()]+", text):
        return True
    if re.fullmatch(r"\(?age\s+\d+\)?", lowered):
        return True
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return True
    if re.search(r"\b\d{4}\b", text):
        return True
    if re.search(rf"\b({month_names})\b", lowered) and re.search(r"\b\d{4}\b", text):
        return True
    return False


def join_place_fragments(parts: list[str]) -> str | None:
    joined = ""
    for part in parts:
        if not joined:
            joined = part.lstrip(", ")
        elif part.startswith(","):
            joined = f"{joined}{part}"
        else:
            joined = f"{joined}, {part}"
    return clean_text(joined)


def extract_birth_place_from_parts(parts: list[str]) -> str | None:
    candidates = []
    for part in parts:
        text = clean_text(part)
        if not text or is_birth_date_fragment(text):
            continue
        if re.search(r"[A-Za-z]", text):
            candidates.append(text)
    return join_place_fragments(candidates)


def extract_birth_place_from_bio_text(extract: str | None) -> str | None:
    text = clean_text(extract)
    if not text:
        return None
    patterns = [
        r"\bborn\s+(?:on\s+)?[^.;()]*?\bin\s+([^.;)]+)",
        r"\bwas born in\s+([^.;)]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return None


def parse_infobox_details(page_html: str | None) -> dict[str, str]:
    if not page_html:
        return {}
    soup = BeautifulSoup(page_html, "html.parser")
    details: dict[str, str] = {}

    for table in soup.select("table.infobox"):
        for row in table.select("tr"):
            label_cell = row.find("th")
            value_cell = row.find("td")
            if not label_cell or not value_cell:
                continue

            label = normalize_label(label_cell.get_text(" ", strip=True))
            raw_value = value_cell.get_text("\n", strip=True)
            value = clean_text(raw_value)
            if not value:
                continue

            if label in NICKNAME_LABELS and "nickname" not in details:
                details["nickname"] = value
            elif label in HEIGHT_LABELS and "height" not in details:
                details["height"] = value
            elif label in WEIGHT_LABELS and "weight" not in details:
                details["weight"] = value
            elif label in BIRTH_PLACE_LABELS and "birth_place" not in details:
                details["birth_place"] = value
            elif label in BORN_LABELS and "birth_place" not in details:
                parts = [part for part in raw_value.splitlines() if clean_text(part)]
                birth_place = extract_birth_place_from_parts(parts)
                if birth_place:
                    details["birth_place"] = birth_place

    return details


def fetch_infobox_details(
    title: str,
    lang: str,
    *,
    session: requests.Session,
    sleep_func=time.sleep,
) -> dict[str, str]:
    payload = request_json(
        session,
        f"https://{lang}.wikipedia.org/w/api.php",
        params={
            "action": "parse",
            "page": title,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        },
        sleep_func=sleep_func,
    )
    text_payload = (payload or {}).get("parse", {}).get("text")
    if isinstance(text_payload, dict):
        page_html = text_payload.get("*")
    else:
        page_html = text_payload
    return parse_infobox_details(page_html if isinstance(page_html, str) else None)


def wikipedia_reference_from_url(url: Any) -> tuple[str, str] | None:
    text = clean_text(url)
    if not text:
        return None
    parsed = urlparse(text)
    host_parts = parsed.netloc.lower().split(".")
    if len(host_parts) < 3 or host_parts[-2:] != ["wikipedia", "org"]:
        return None
    lang = host_parts[0]
    path = parsed.path or ""
    if not path.startswith("/wiki/"):
        return None
    title = clean_text(unquote(path.removeprefix("/wiki/")).replace("_", " "))
    if not title:
        return None
    return lang, title


def existing_wikipedia_references(fencer: dict[str, Any]) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []

    url = value_from_fencer_or_metadata(
        fencer,
        ["wikipedia_url", "wiki_url", "wikipedia_page_url"],
    )
    parsed_url = wikipedia_reference_from_url(url)
    if parsed_url:
        references.append(parsed_url)

    title = clean_text(
        value_from_fencer_or_metadata(
            fencer,
            ["wikipedia_title", "wiki_title", "wikipedia_page_title"],
        )
    )
    if title:
        lang = clean_text(
            value_from_fencer_or_metadata(
                fencer,
                ["wikipedia_lang", "wikipedia_language", "wiki_lang"],
            )
        )
        languages = [lang] if lang else language_candidates(fencer)
        for candidate_lang in languages:
            ref = (candidate_lang, title)
            if ref not in references:
                references.append(ref)

    return references


def fetch_page_enrichment(
    title: str,
    lang: str,
    *,
    session: requests.Session,
    wikidata_details: dict[str, str] | None = None,
    sleep_func=time.sleep,
) -> dict[str, str] | None:
    summary = fetch_summary(title, lang, session=session, sleep_func=sleep_func)
    if not summary:
        return None

    details = fetch_infobox_details(title, lang, session=session, sleep_func=sleep_func)
    if "birth_place" not in details:
        birth_place = extract_birth_place_from_bio_text(summary.get("bio_text"))
        if birth_place:
            details["birth_place"] = birth_place

    result = {
        **summary,
        **(wikidata_details or {}),
        **details,
        "language": lang,
        "title": title,
    }
    return {key: value for key, value in result.items() if value}


def fetch_wikipedia_enrichment(
    fencer: dict[str, Any],
    *,
    session: requests.Session | None = None,
    sleep_func=time.sleep,
) -> dict[str, str] | None:
    qid = fencer_wikidata_id(fencer)
    session = session or requests.Session()

    if qid:
        entity = fetch_wikidata_entity(qid, session=session, sleep_func=sleep_func)
        wikidata_details = fetch_wikidata_birth_details(
            entity,
            session=session,
            sleep_func=sleep_func,
        )
        sitelinks = wikidata_sitelinks_from_entity(entity)
        for lang in language_candidates(fencer):
            title = sitelinks.get(lang)
            if not title:
                continue

            result = fetch_page_enrichment(
                title,
                lang,
                session=session,
                wikidata_details=wikidata_details,
                sleep_func=sleep_func,
            )
            if result:
                return result

        if wikidata_details:
            wikidata_details["bio_source"] = f"https://www.wikidata.org/wiki/{qid}"
            return wikidata_details

    for lang, title in existing_wikipedia_references(fencer):
        result = fetch_page_enrichment(
            title,
            lang,
            session=session,
            wikidata_details=None,
            sleep_func=sleep_func,
        )
        if result:
            return result

    return None


def source_matches(existing_source: str | None, new_source: str | None) -> bool:
    existing = clean_text(existing_source)
    new = clean_text(new_source)
    return bool(existing and new and existing.rstrip("/") == new.rstrip("/"))


def should_update_bio(fencer: dict[str, Any], new_bio: str, new_source: str | None) -> bool:
    existing_bio = clean_text(fencer.get("bio"))
    if not existing_bio:
        return True
    if not source_matches(clean_text(fencer.get("bio_source")), new_source):
        return False
    return len(new_bio) >= len(existing_bio) + BIO_REFRESH_MIN_EXTRA_CHARS


def build_update_payload(
    fencer: dict[str, Any],
    enrichment: dict[str, Any] | None,
) -> dict[str, str]:
    if not enrichment:
        return {}
    payload: dict[str, str] = {}

    bio = clean_text(enrichment.get("bio") or enrichment.get("bio_text"))
    source = clean_text(enrichment.get("bio_source") or enrichment.get("wikipedia_url"))

    if bio:
        if "bio" in fencer and should_update_bio(fencer, bio, source):
            payload["bio"] = bio
        if "bio_text" in fencer and not clean_text(fencer.get("bio_text")):
            payload["bio_text"] = bio

    if source:
        if "wikipedia_url" in fencer and not clean_text(fencer.get("wikipedia_url")):
            payload["wikipedia_url"] = source
        if (
            "bio_source" in fencer
            and not clean_text(fencer.get("bio_source"))
            and any(field in payload for field in ("birth_place", "bio_text"))
        ):
            payload["bio_source"] = source

    for field in ("birth_place", "nickname", "height", "weight"):
        value = clean_text(enrichment.get(field))
        if value and field in fencer and not clean_text(fencer.get(field)):
            payload[field] = value

    if source and "bio_source" in fencer and not clean_text(fencer.get("bio_source")):
        if any(field in payload for field in ("birth_place", "bio_text")):
            payload["bio_source"] = source

    return payload


def apply_pending_field_filter(query: Any) -> Any:
    or_filter = getattr(query, "or_", None)
    if callable(or_filter):
        return or_filter(PENDING_FIELD_FILTER)
    return query.is_("bio_text", "null")


def fencer_has_confident_wikipedia_source(fencer: dict[str, Any]) -> bool:
    return bool(fencer_wikidata_id(fencer) or existing_wikipedia_references(fencer))


def load_pending_fencers(limit: int = PAGE_SIZE) -> list[dict[str, Any]]:
    if supabase is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    last_fencer_id = get_state(SOURCE, "last_fencer_id")
    rows_by_id: dict[str, dict[str, Any]] = {}

    for column, operator, value in MATCH_FILTERS:
        query = (
            supabase.table("fs_fencers")
            .select(FENCER_SELECT)
            .filter(column, operator, value)
        )
        query = apply_pending_field_filter(query)
        if last_fencer_id:
            query = query.gt("id", last_fencer_id)
        result = query.order("id").limit(limit).execute()
        for row in result.data or []:
            if not fencer_has_confident_wikipedia_source(row):
                continue
            key = clean_text(row.get("id")) or json.dumps(row, sort_keys=True)
            rows_by_id.setdefault(key, row)
            if len(rows_by_id) >= limit:
                return list(rows_by_id.values())

    return list(rows_by_id.values())


def update_fencer(fencer_id: str, payload: dict[str, str]) -> bool:
    if not payload:
        return False
    supabase.table("fs_fencers").update(payload).eq("id", fencer_id).execute()  # type: ignore[union-attr]
    return True


def process_fencer(
    fencer: dict[str, Any],
    *,
    session: requests.Session,
    sleep_func=time.sleep,
) -> str:
    enrichment = fetch_wikipedia_enrichment(fencer, session=session, sleep_func=sleep_func)
    if not enrichment:
        print(f"  Skipped fencer {fencer.get('id')}: no confident Wikipedia/Wikidata match")
        return "skipped"
    payload = build_update_payload(fencer, enrichment)
    if not payload:
        print(f"  Skipped fencer {fencer.get('id')}: no empty or lower-quality bio fields")
        return "skipped"
    update_fencer(fencer["id"], payload)
    return "written"


def main():
    if supabase is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    run_log = ScraperRunLogger("scrape_wikipedia_bios").start()
    session = requests.Session()
    written = failed = skipped = processed = 0
    seen_ids: set[str] = set()

    try:
        print(f"Wikipedia bio enrichment starting - {datetime.now(timezone.utc).isoformat()}")
        while True:
            if MAX_FENCERS and processed >= MAX_FENCERS:
                break
            batch_limit = PAGE_SIZE
            if MAX_FENCERS:
                batch_limit = min(PAGE_SIZE, MAX_FENCERS - processed)

            rows = [
                row for row in load_pending_fencers(batch_limit)
                if row.get("id") not in seen_ids
            ]
            if not rows:
                if get_state(SOURCE, "last_fencer_id"):
                    set_state(SOURCE, "last_fencer_id", None)
                    rows = [
                        row for row in load_pending_fencers(batch_limit)
                        if row.get("id") not in seen_ids
                    ]
                if not rows:
                    break

            for fencer in rows:
                if fencer.get("id"):
                    seen_ids.add(fencer["id"])
                try:
                    status = process_fencer(fencer, session=session)
                    if status == "written":
                        written += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    failed += 1
                    print(f"  Failed fencer {fencer.get('id')}: {exc}")
                finally:
                    if fencer.get("id"):
                        set_state(SOURCE, "last_fencer_id", fencer["id"])
                    processed += 1
                if MAX_FENCERS and processed >= MAX_FENCERS:
                    break

        set_state(SOURCE, "last_run", datetime.now(timezone.utc).isoformat())
        run_log.complete(written=written, failed=failed, skipped=skipped)
        print(f"Done - written={written}, failed={failed}, skipped={skipped}")
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

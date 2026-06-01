import html
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

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
    "id,name,country,nationality,metadata,bio_text,wikipedia_url,"
    "birth_place,nickname,height,weight"
)

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


def fetch_wikidata_sitelinks(
    qid: str,
    *,
    session: requests.Session,
    sleep_func=time.sleep,
) -> dict[str, str]:
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    payload = request_json(session, url, sleep_func=sleep_func)
    entity = (payload or {}).get("entities", {}).get(qid, {})
    sitelinks = entity.get("sitelinks") or {}
    if not isinstance(sitelinks, dict):
        return {}
    return {
        key.removesuffix("wiki"): value.get("title")
        for key, value in sitelinks.items()
        if key.endswith("wiki") and isinstance(value, dict) and value.get("title")
    }


def first_paragraph(extract: str | None) -> str | None:
    text = (extract or "").strip()
    if not text:
        return None
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return clean_text(paragraphs[0] if paragraphs else text)


def summary_to_enrichment(payload: dict[str, Any] | None) -> dict[str, str] | None:
    if not payload or payload.get("type") == "disambiguation":
        return None
    bio_text = first_paragraph(payload.get("extract"))
    if not bio_text:
        return None
    content_urls = payload.get("content_urls") or {}
    desktop = content_urls.get("desktop") if isinstance(content_urls, dict) else {}
    page_url = (desktop or {}).get("page") or payload.get("page_url")
    return {
        "bio_text": bio_text,
        "wikipedia_url": clean_text(page_url),
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


def fetch_wikipedia_enrichment(
    fencer: dict[str, Any],
    *,
    session: requests.Session | None = None,
    sleep_func=time.sleep,
) -> dict[str, str] | None:
    qid = fencer_wikidata_id(fencer)
    if not qid:
        return None

    session = session or requests.Session()
    sitelinks = fetch_wikidata_sitelinks(qid, session=session, sleep_func=sleep_func)
    for lang in language_candidates(fencer):
        title = sitelinks.get(lang)
        if not title:
            continue

        summary = fetch_summary(title, lang, session=session, sleep_func=sleep_func)
        if not summary:
            continue

        details = fetch_infobox_details(title, lang, session=session, sleep_func=sleep_func)
        if "birth_place" not in details:
            birth_place = extract_birth_place_from_bio_text(summary.get("bio_text"))
            if birth_place:
                details["birth_place"] = birth_place

        result = {**summary, **details, "language": lang, "title": title}
        return {key: value for key, value in result.items() if value}

    return None


def build_update_payload(
    fencer: dict[str, Any],
    enrichment: dict[str, Any] | None,
) -> dict[str, str]:
    if not enrichment:
        return {}
    payload: dict[str, str] = {}
    for field in ("bio_text", "wikipedia_url", "birth_place", "nickname", "height", "weight"):
        value = clean_text(enrichment.get(field))
        if value and not clean_text(fencer.get(field)):
            payload[field] = value
    return payload


def load_pending_fencers(limit: int = PAGE_SIZE) -> list[dict[str, Any]]:
    if supabase is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

    last_fencer_id = get_state(SOURCE, "last_fencer_id")
    query = (
        supabase.table("fs_fencers")
        .select(FENCER_SELECT)
        .filter("metadata->>wikidata_id", "not.is", "null")
        .is_("bio_text", "null")
    )
    if last_fencer_id:
        query = query.gt("id", last_fencer_id)
    result = query.order("id").limit(limit).execute()
    return result.data or []


def update_fencer(fencer_id: str, payload: dict[str, str]) -> bool:
    if not payload:
        return False
    supabase.table("fs_fencers").update(payload).eq("id", fencer_id).execute()
    return True


def process_fencer(
    fencer: dict[str, Any],
    *,
    session: requests.Session,
    sleep_func=time.sleep,
) -> str:
    enrichment = fetch_wikipedia_enrichment(fencer, session=session, sleep_func=sleep_func)
    payload = build_update_payload(fencer, enrichment)
    if not payload:
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

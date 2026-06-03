from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

try:
    from compute_transfers import country_key as transfer_country_key
    from compute_transfers import normalize_country as transfer_normalize_country
except Exception:  # pragma: no cover - fallback keeps tests/imports isolated.
    transfer_country_key = None
    transfer_normalize_country = None

try:
    from scrape_club_reviews import display_club_name as review_display_club_name
    from scrape_club_reviews import normalize_club_name as review_normalize_club_name
except Exception:  # pragma: no cover - local fallbacks below cover import failures.
    review_display_club_name = None
    review_normalize_club_name = None

try:
    from supabase import create_client
except Exception:  # pragma: no cover - import errors surface when a client is required.
    create_client = None


SOURCE = "enrich_clubs"
SPARQL_URL = "https://query.wikidata.org/sparql"
FIE_ID_PROPERTY = os.environ.get("WIKIDATA_FIE_PROPERTY", "P2423")
PAGE_SIZE = int(os.environ.get("CLUB_ENRICHMENT_PAGE_SIZE", "1000"))
BATCH_SIZE = int(os.environ.get("CLUB_ENRICHMENT_BATCH_SIZE", "100"))
REQUEST_DELAY = float(os.environ.get("CLUB_ENRICHMENT_DELAY", "1.0"))
OFFICIAL_TIMEOUT = int(os.environ.get("CLUB_ENRICHMENT_OFFICIAL_TIMEOUT", "20"))
CONFLICT_COLUMNS = "normalized_club_name,country"

HEADERS = {
    "User-Agent": "FenceSpaceBot/1.0 (club enrichment; +https://fencespace.app)",
    "Accept": "application/sparql-results+json, application/json;q=0.9, text/html;q=0.8, */*;q=0.7",
}

COUNTRY_ALIASES = {
    "CAN": "Canada",
    "CA": "Canada",
    "FRA": "France",
    "FR": "France",
    "ITA": "Italy",
    "IT": "Italy",
    "USA": "United States",
    "US": "United States",
    "UNITED STATES": "United States",
    "UNITED STATES OF AMERICA": "United States",
    "GBR": "Great Britain",
    "GB": "Great Britain",
    "KOR": "South Korea",
}

WIKIDATA_QUERY_TEMPLATE = """
SELECT ?club ?clubLabel ?countryLabel ?website ?inception ?article ?athlete ?athleteLabel ?fie_id WHERE {{
  {{
    ?club wdt:P641 wd:Q12100 .
  }}
  UNION
  {{
    ?athlete wdt:P641 wd:Q12100 ;
             wdt:P54 ?club .
  }}
  OPTIONAL {{ ?club wdt:P17 ?country . }}
  OPTIONAL {{ ?club wdt:P856 ?website . }}
  OPTIONAL {{ ?club wdt:P571 ?inception . }}
  OPTIONAL {{
    ?article schema:about ?club ;
             schema:isPartOf <https://en.wikipedia.org/> .
  }}
  OPTIONAL {{ ?athlete wdt:{fie_prop} ?fie_id . }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
    ?club rdfs:label ?clubLabel .
    ?country rdfs:label ?countryLabel .
    ?athlete rdfs:label ?athleteLabel .
  }}
}}
LIMIT {limit}
OFFSET {offset}
"""


@dataclass(frozen=True)
class ClubCandidate:
    name: str
    normalized_name: str
    country: str
    source_tables: tuple[str, ...] = ()
    source_urls: tuple[str, ...] = ()
    websites: tuple[str, ...] = ()
    fencer_ids: tuple[str, ...] = ()
    fie_ids: tuple[str, ...] = ()


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def ensure_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def stable_unique(values: list[Any] | tuple[Any, ...]) -> list[Any]:
    seen = set()
    result = []
    for value in values:
        if value is None:
            continue
        key = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = unicodedata.normalize("NFD", text)
    key = "".join(char for char in key if unicodedata.category(char) != "Mn")
    key = re.sub(r"[.\s]+", " ", key.upper()).strip()
    compact = key.replace(" ", "")
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]
    if compact in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[compact]
    if transfer_normalize_country:
        normalized = transfer_normalize_country(text)
        if normalized:
            return normalized
    return text.title()


def country_key(value: Any) -> str:
    if transfer_country_key:
        return transfer_country_key(normalize_country(value))
    normalized = normalize_country(value) or ""
    return normalized.casefold()


def display_club_name(value: Any) -> str | None:
    if review_display_club_name:
        return review_display_club_name(value)
    text = clean_text(str(value or "").replace("-", " "))
    if not text:
        return None
    return text.title() if text.islower() or text.isupper() else text


def normalize_club_name(value: Any) -> str | None:
    if review_normalize_club_name:
        return review_normalize_club_name(value)
    text = clean_text(value)
    if not text:
        return None
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\b(?:a\s*s\s*d|s\s*s\s*d|a\s*s|s\s*c|asd|ssd)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def club_key(name: Any, country: Any) -> tuple[str, str]:
    normalized = normalize_club_name(name) or ""
    return normalized, country_key(country)


def binding_value(binding: dict[str, Any], key: str) -> str | None:
    return clean_text((binding.get(key) or {}).get("value"))


def wikidata_entity_id(url: str | None) -> str | None:
    if not url:
        return None
    return url.rstrip("/").split("/")[-1] or None


def parse_wikidata_time(raw: str | None) -> str | None:
    if not raw:
        return None
    match = re.match(r"[+-]?(\d+)-(\d{2})-(\d{2})T", raw)
    if not match:
        return None
    year, month, day = match.groups()
    if month == "00":
        return year
    if day == "00":
        return f"{year}-{month}"
    return f"{year}-{month}-{day}"


def source_urls_from_metadata(metadata: dict[str, Any]) -> list[str]:
    urls = []
    for key in (
        "source_url",
        "source_urls",
        "ranking_url",
        "result_url",
        "event_url",
        "profile_url",
        "club_url",
        "federation_url",
    ):
        value = metadata.get(key)
        if isinstance(value, str):
            urls.append(value)
        elif isinstance(value, list):
            urls.extend(item for item in value if isinstance(item, str))
    return [url for url in stable_unique(urls) if url.startswith(("http://", "https://"))]


def website_from_row(row: dict[str, Any], metadata: dict[str, Any]) -> str | None:
    for value in (
        row.get("website"),
        row.get("club_website"),
        metadata.get("website"),
        metadata.get("club_website"),
        metadata.get("official_website"),
    ):
        text = clean_text(value)
        if text and text.startswith(("http://", "https://")):
            return text
    return None


def fetch_all_rows(client, table: str, columns: str, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        page = (
            client.table(table)
            .select(columns)
            .range(start, start + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < page_size:
            return rows
        start += page_size


def fetch_rows_with_fallback(
    client,
    table: str,
    column_options: tuple[str, ...],
    *,
    page_size: int,
) -> list[dict[str, Any]]:
    last_error = None
    for columns in column_options:
        try:
            return fetch_all_rows(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    print(f"  Skipping {table}: {last_error}")
    return []


def fetch_club_candidates(client, *, page_size: int = PAGE_SIZE) -> list[ClubCandidate]:
    source_specs = (
        (
            "fs_national_fed_rankings",
            (
                "id,club,country,fencer_id,fie_id,name,metadata",
                "club,country,fencer_id,fie_id,name,metadata",
                "club,country,metadata",
                "club,country",
            ),
        ),
        (
            "fs_results",
            (
                "id,club,country,nationality,fencer_id,fie_fencer_id,name,metadata",
                "club,country,fencer_id,fie_fencer_id,name,metadata",
                "club,country,metadata",
                "club,country",
            ),
        ),
        (
            "fs_fencers",
            (
                "id,club,country,fie_id,name,metadata",
                "club,country,fie_id,name,metadata",
                "club,country,metadata",
                "club,country",
            ),
        ),
        (
            "fs_club_rankings",
            (
                "id,club,country,metadata",
                "club,country,metadata",
                "club,country",
            ),
        ),
        (
            "fs_clubs",
            (
                "id,name,country,website,metadata",
                "name,country,website",
            ),
        ),
    )

    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for table, column_options in source_specs:
        rows = fetch_rows_with_fallback(client, table, column_options, page_size=page_size)
        for row in rows:
            metadata = ensure_metadata(row.get("metadata"))
            raw_name = clean_text(row.get("club") or row.get("club_name") or row.get("name"))
            normalized = normalize_club_name(raw_name)
            country = normalize_country(row.get("country") or row.get("nationality") or metadata.get("country"))
            if not raw_name or not normalized or not country:
                continue

            key = (normalized, country_key(country))
            if key not in candidates:
                candidates[key] = {
                    "name": display_club_name(raw_name) or raw_name,
                    "normalized_name": normalized,
                    "country": country,
                    "source_tables": [],
                    "source_urls": [],
                    "websites": [],
                    "fencer_ids": [],
                    "fie_ids": [],
                }

            candidate = candidates[key]
            if table not in candidate["source_tables"]:
                candidate["source_tables"].append(table)
            candidate["source_urls"].extend(source_urls_from_metadata(metadata))

            website = website_from_row(row, metadata)
            if website:
                candidate["websites"].append(website)

            if table == "fs_fencers":
                fencer_id = clean_text(row.get("fencer_id") or row.get("id"))
            else:
                fencer_id = clean_text(row.get("fencer_id"))
            fie_id = clean_text(row.get("fie_id") or row.get("fie_fencer_id"))
            if fencer_id:
                candidate["fencer_ids"].append(fencer_id)
            if fie_id:
                candidate["fie_ids"].append(fie_id)

    result = []
    for candidate in candidates.values():
        result.append(
            ClubCandidate(
                name=candidate["name"],
                normalized_name=candidate["normalized_name"],
                country=candidate["country"],
                source_tables=tuple(stable_unique(candidate["source_tables"])),
                source_urls=tuple(stable_unique(candidate["source_urls"])),
                websites=tuple(stable_unique(candidate["websites"])),
                fencer_ids=tuple(stable_unique(candidate["fencer_ids"])),
                fie_ids=tuple(stable_unique(candidate["fie_ids"])),
            )
        )
    return sorted(result, key=lambda item: (country_key(item.country), item.normalized_name))


def ids_from_index(index_value: Any) -> set[str]:
    if not index_value:
        return set()
    if isinstance(index_value, set):
        return {str(item) for item in index_value if item}
    if isinstance(index_value, (list, tuple)):
        return {str(item) for item in index_value if item}
    return {str(index_value)}


def build_fencer_index(client, *, page_size: int = PAGE_SIZE) -> dict[str, dict[str, set[str]]]:
    rows = fetch_rows_with_fallback(
        client,
        "fs_fencers",
        ("id,fie_id,name,country,metadata", "id,fie_id,metadata", "id,fie_id"),
        page_size=page_size,
    )
    by_fie_id: dict[str, set[str]] = {}
    by_wikidata_id: dict[str, set[str]] = {}
    for row in rows:
        fencer_id = clean_text(row.get("id"))
        if not fencer_id:
            continue
        fie_id = clean_text(row.get("fie_id"))
        if fie_id:
            by_fie_id.setdefault(fie_id, set()).add(fencer_id)
        wikidata_id = clean_text(ensure_metadata(row.get("metadata")).get("wikidata_id"))
        if wikidata_id:
            by_wikidata_id.setdefault(wikidata_id, set()).add(fencer_id)
    return {"by_fie_id": by_fie_id, "by_wikidata_id": by_wikidata_id}


def notable_alumni_item(
    *,
    athlete_name: str | None,
    athlete_id: str | None,
    fie_id: str | None,
    fencer_id: str | None = None,
) -> dict[str, Any] | None:
    if not athlete_name and not athlete_id and not fencer_id:
        return None
    item: dict[str, Any] = {"source": "wikidata:P54"}
    if athlete_name:
        item["name"] = athlete_name
    if fencer_id:
        item["fencer_id"] = fencer_id
    if fie_id:
        item["fie_id"] = fie_id
    if athlete_id:
        item["wikidata_id"] = athlete_id
    return item


def build_wikidata_enrichments(
    bindings: list[dict[str, Any]],
    *,
    fencer_index: dict[str, Any] | None = None,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    fencer_index = fencer_index or {"by_fie_id": {}, "by_wikidata_id": {}}
    by_entity: dict[str, dict[str, Any]] = {}

    for binding in bindings:
        club_url = binding_value(binding, "club")
        club_id = wikidata_entity_id(club_url)
        club_name = binding_value(binding, "clubLabel")
        normalized = normalize_club_name(club_name)
        country = normalize_country(binding_value(binding, "countryLabel"))
        if not club_id or not club_name or not normalized or not country:
            continue

        entry = by_entity.setdefault(
            club_id,
            {
                "club_name": club_name,
                "normalized_club_name": normalized,
                "country": country,
                "website": None,
                "founding_date": None,
                "history_summary": None,
                "notable_alumni": [],
                "source_urls": [],
                "metadata": {
                    "status": "source_backed",
                    "source": "wikidata",
                    "wikidata_id": club_id,
                },
            },
        )

        website = binding_value(binding, "website")
        if website and not entry["website"]:
            entry["website"] = website
        founding_date = parse_wikidata_time(binding_value(binding, "inception"))
        if founding_date and not entry["founding_date"]:
            entry["founding_date"] = founding_date

        for url in (club_url, binding_value(binding, "article")):
            if url:
                entry["source_urls"].append(url)

        athlete_id = wikidata_entity_id(binding_value(binding, "athlete"))
        athlete_name = binding_value(binding, "athleteLabel")
        fie_id = binding_value(binding, "fie_id")
        matched_ids = set()
        if fie_id:
            matched_ids.update(ids_from_index((fencer_index.get("by_fie_id") or {}).get(fie_id)))
        if athlete_id:
            matched_ids.update(ids_from_index((fencer_index.get("by_wikidata_id") or {}).get(athlete_id)))

        alumni = []
        if matched_ids:
            for fencer_id in sorted(matched_ids):
                item = notable_alumni_item(
                    athlete_name=athlete_name,
                    athlete_id=athlete_id,
                    fie_id=fie_id,
                    fencer_id=fencer_id,
                )
                if item:
                    alumni.append(item)
        elif athlete_id or athlete_name:
            item = notable_alumni_item(
                athlete_name=athlete_name,
                athlete_id=athlete_id,
                fie_id=fie_id,
            )
            if item:
                alumni.append(item)
        entry["notable_alumni"].extend(alumni)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in by_entity.values():
        entry["source_urls"] = stable_unique(entry["source_urls"])
        entry["notable_alumni"] = stable_unique(entry["notable_alumni"])
        grouped.setdefault(club_key(entry["club_name"], entry["country"]), []).append(entry)

    for rows in grouped.values():
        rows.sort(key=lambda row: row["metadata"].get("wikidata_id") or "")
    return grouped


def compact_summary(text: str | None, *, max_length: int = 500) -> str | None:
    text = clean_text(text)
    if not text:
        return None
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rsplit(" ", 1)[0].rstrip(".,; ")
    return f"{truncated}."


def json_ld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    objects = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            parsed = json.loads(script.get_text(" ") or "{}")
        except Exception:
            continue
        queue = parsed if isinstance(parsed, list) else [parsed]
        for item in queue:
            if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                queue.extend(obj for obj in item["@graph"] if isinstance(obj, dict))
            elif isinstance(item, dict):
                objects.append(item)
    return objects


def first_json_value(objects: list[dict[str, Any]], *keys: str) -> str | None:
    for obj in objects:
        for key in keys:
            value = obj.get(key)
            if isinstance(value, str) and clean_text(value):
                return clean_text(value)
            if isinstance(value, dict) and clean_text(value.get("@value")):
                return clean_text(value.get("@value"))
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and clean_text(item):
                        return clean_text(item)
    return None


def founded_date_from_text(text: str | None) -> str | None:
    text = clean_text(text)
    if not text:
        return None
    match = re.search(r"\b(?:founded|established|formed|created)\s+(?:in\s+)?(\d{4})(?:[-/](\d{1,2})(?:[-/](\d{1,2}))?)?", text, re.I)
    if not match:
        return None
    year, month, day = match.groups()
    if month and day:
        return f"{year}-{int(month):02d}-{int(day):02d}"
    if month:
        return f"{year}-{int(month):02d}"
    return year


def history_summary_from_html(soup: BeautifulSoup) -> str | None:
    candidate_sections = []
    for tag in soup.find_all(["section", "article", "div", "main"]):
        attrs = " ".join(
            str(value)
            for value in [
                tag.get("id"),
                " ".join(tag.get("class") or []),
                tag.get("aria-label"),
            ]
            if value
        ).lower()
        heading = " ".join(h.get_text(" ", strip=True) for h in tag.find_all(["h1", "h2", "h3"], recursive=False)).lower()
        if any(token in f"{attrs} {heading}" for token in ("history", "about", "club")):
            candidate_sections.append(tag)

    for section in candidate_sections:
        for paragraph in section.find_all("p"):
            text = compact_summary(paragraph.get_text(" ", strip=True))
            if text and len(text) >= 40:
                return text

    meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    if meta:
        return compact_summary(meta.get("content"))
    return None


def parse_official_club_page(html: str, *, source_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "html.parser")
    json_objects = json_ld_objects(soup)

    website = first_json_value(json_objects, "url", "sameAs")
    if not website:
        canonical = soup.find("link", attrs={"rel": re.compile(r"canonical", re.I)})
        website = clean_text(canonical.get("href")) if canonical else None
    if website:
        website = urljoin(source_url, website)

    founding_date = first_json_value(json_objects, "foundingDate", "foundingYear")
    if not founding_date:
        founding_date = founded_date_from_text(soup.get_text(" ", strip=True))

    summary = history_summary_from_html(soup)
    if not summary:
        summary = compact_summary(first_json_value(json_objects, "description"))

    return {
        "website": website,
        "founding_date": founding_date,
        "history_summary": summary,
        "notable_alumni": [],
        "source_urls": [source_url],
        "metadata": {"source_type": "official_club_page"},
    }


def fetch_official_page_enrichment(
    candidate: ClubCandidate,
    *,
    session: requests.Session | None = None,
    timeout: int = OFFICIAL_TIMEOUT,
) -> dict[str, Any] | None:
    if not candidate.websites:
        return None
    http = session or requests.Session()
    url = candidate.websites[0]
    try:
        try:
            response = http.get(url, headers=HEADERS, timeout=timeout)
        except TypeError:
            response = http.get(url, timeout=timeout)
        if response.status_code != 200:
            return {
                "metadata": {
                    "status": "official_source_unavailable",
                    "source_type": "official_club_page",
                    "http_status": response.status_code,
                }
            }
        parsed = parse_official_club_page(response.text, source_url=url)
        parsed["metadata"]["http_status"] = response.status_code
        return parsed
    except Exception as exc:
        return {
            "metadata": {
                "status": "official_source_unavailable",
                "source_type": "official_club_page",
                "error": str(exc)[:500],
            }
        }


def merge_enrichment(primary: dict[str, Any], secondary: dict[str, Any] | None) -> dict[str, Any]:
    if not secondary:
        return primary
    merged = dict(primary)
    for field in ("website", "founding_date", "history_summary"):
        if not merged.get(field) and secondary.get(field):
            merged[field] = secondary[field]
    merged["notable_alumni"] = stable_unique(
        list(merged.get("notable_alumni") or []) + list(secondary.get("notable_alumni") or [])
    )
    merged["source_urls"] = stable_unique(
        list(merged.get("source_urls") or []) + list(secondary.get("source_urls") or [])
    )
    metadata = dict(merged.get("metadata") or {})
    secondary_meta = secondary.get("metadata") if isinstance(secondary.get("metadata"), dict) else {}
    sources = list(metadata.get("sources") or [])
    if metadata.get("source"):
        sources.append(metadata["source"])
    if secondary_meta.get("source_type"):
        sources.append(secondary_meta["source_type"])
    metadata.update({key: value for key, value in secondary_meta.items() if key != "status"})
    metadata["status"] = metadata.get("status") or secondary_meta.get("status") or "source_backed"
    metadata["sources"] = stable_unique(sources)
    merged["metadata"] = metadata
    return merged


def stub_row(
    candidate: ClubCandidate,
    *,
    status: str,
    enriched_at: str,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {
        "status": status,
        "source_tables": list(candidate.source_tables),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return {
        "club_name": candidate.name,
        "normalized_club_name": candidate.normalized_name,
        "country": candidate.country,
        "website": None,
        "founding_date": None,
        "history_summary": None,
        "notable_alumni": [],
        "source_urls": list(candidate.source_urls),
        "metadata": metadata,
        "enriched_at": enriched_at,
    }


def source_backed_row(
    candidate: ClubCandidate,
    source: dict[str, Any],
    *,
    enriched_at: str,
) -> dict[str, Any]:
    metadata = dict(source.get("metadata") or {})
    metadata["status"] = "source_backed"
    metadata["source_tables"] = list(candidate.source_tables)
    source_urls = stable_unique(list(candidate.source_urls) + list(source.get("source_urls") or []))
    website = source.get("website") or (candidate.websites[0] if candidate.websites else None)
    return {
        "club_name": candidate.name,
        "normalized_club_name": candidate.normalized_name,
        "country": candidate.country,
        "website": website,
        "founding_date": source.get("founding_date"),
        "history_summary": source.get("history_summary"),
        "notable_alumni": list(source.get("notable_alumni") or []),
        "source_urls": source_urls,
        "metadata": metadata,
        "enriched_at": enriched_at,
    }


def fetch_wikidata_club_bindings(
    *,
    page_size: int = PAGE_SIZE,
    delay: float = REQUEST_DELAY,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = WIKIDATA_QUERY_TEMPLATE.format(
            fie_prop=FIE_ID_PROPERTY,
            limit=page_size,
            offset=offset,
        )
        response = requests.get(
            SPARQL_URL,
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=60,
        )
        if response.status_code != 200:
            print(f"  Wikidata club query failed with HTTP {response.status_code}")
            break
        bindings = response.json()["results"]["bindings"]
        if not bindings:
            break
        results.extend(bindings)
        if len(bindings) < page_size:
            break
        offset += page_size
        if delay:
            time.sleep(delay)
    return results


def upsert_enrichment_rows(client, rows: list[dict[str, Any]], *, batch_size: int = BATCH_SIZE) -> tuple[int, int]:
    written = failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index:index + batch_size]
        try:
            client.table("fs_club_enrichment").upsert(batch, on_conflict=CONFLICT_COLUMNS).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_club_enrichment upsert batch {index // batch_size} failed: {exc}")
    return written, failed


def get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    if create_client is None:
        raise RuntimeError("supabase package is required.")
    return create_client(url, key)


def enrich_clubs(
    *,
    client=None,
    wikidata_bindings: list[dict[str, Any]] | None = None,
    session: requests.Session | None = None,
    fetch_official_pages: bool = True,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    request_delay: float = REQUEST_DELAY,
    log_run: bool = True,
    update_state: bool = True,
    enriched_at: str | None = None,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    get_state(SOURCE, "last_run") if update_state else None
    enriched_at = enriched_at or datetime.now(timezone.utc).isoformat()

    try:
        client = client or get_client()
        candidates = fetch_club_candidates(client, page_size=page_size)
        fencer_index = build_fencer_index(client, page_size=page_size)
        bindings = wikidata_bindings if wikidata_bindings is not None else fetch_wikidata_club_bindings(delay=request_delay)
        wikidata_by_key = build_wikidata_enrichments(bindings, fencer_index=fencer_index)

        rows = []
        source_backed = stubbed = ambiguous = skipped = 0
        for candidate in candidates:
            matches = wikidata_by_key.get(club_key(candidate.name, candidate.country), [])
            if len(matches) > 1:
                rows.append(
                    stub_row(
                        candidate,
                        status="ambiguous_source",
                        enriched_at=enriched_at,
                        extra_metadata={
                            "source_count": len(matches),
                            "wikidata_ids": sorted(
                                row.get("metadata", {}).get("wikidata_id")
                                for row in matches
                                if row.get("metadata", {}).get("wikidata_id")
                            ),
                        },
                    )
                )
                stubbed += 1
                ambiguous += 1
                continue

            source = dict(matches[0]) if matches else {}
            official = None
            if fetch_official_pages and candidate.websites:
                official = fetch_official_page_enrichment(candidate, session=session)
                if request_delay:
                    time.sleep(request_delay)
            if source:
                source = merge_enrichment(source, official)
            elif official and any(official.get(field) for field in ("website", "founding_date", "history_summary")):
                source = merge_enrichment(
                    {
                        "club_name": candidate.name,
                        "normalized_club_name": candidate.normalized_name,
                        "country": candidate.country,
                        "website": None,
                        "founding_date": None,
                        "history_summary": None,
                        "notable_alumni": [],
                        "source_urls": [],
                        "metadata": {"status": "source_backed"},
                    },
                    official,
                )

            if source:
                rows.append(source_backed_row(candidate, source, enriched_at=enriched_at))
                source_backed += 1
            else:
                official_meta = official.get("metadata") if isinstance(official, dict) else {}
                if isinstance(official_meta, dict) and official_meta.get("status"):
                    rows.append(
                        stub_row(
                            candidate,
                            status=official_meta["status"],
                            enriched_at=enriched_at,
                            extra_metadata={
                                key: value
                                for key, value in official_meta.items()
                                if key != "status"
                            },
                        )
                    )
                else:
                    rows.append(stub_row(candidate, status="no_public_source", enriched_at=enriched_at))
                stubbed += 1

        written, failed = upsert_enrichment_rows(client, rows, batch_size=batch_size) if rows else (0, 0)
        summary = {
            "clubs_seen": len(candidates),
            "source_backed": source_backed,
            "stubbed": stubbed,
            "ambiguous": ambiguous,
            "written": written,
            "failed": failed,
            "skipped": skipped,
        }

        if update_state:
            set_state(SOURCE, "last_run", {**summary, "completed_at": datetime.now(timezone.utc).isoformat()})
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Club enrichment starting - {datetime.now(timezone.utc).isoformat()}")
    summary = enrich_clubs()
    print(
        "Club enrichment complete: "
        f"{summary['written']} written, {summary['source_backed']} source-backed, "
        f"{summary['stubbed']} stubbed, {summary['failed']} failed"
    )


if __name__ == "__main__":
    main()

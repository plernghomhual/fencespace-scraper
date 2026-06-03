from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SOURCE = "enrich_education"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
SPARQL_URL = "https://query.wikidata.org/sparql"
REQUEST_DELAY_SECONDS = float(os.environ.get("EDUCATION_ENRICH_DELAY", "0.5"))
PAGE_SIZE = int(os.environ.get("EDUCATION_ENRICH_PAGE_SIZE", "100"))
REQUEST_TIMEOUT = int(os.environ.get("EDUCATION_ENRICH_TIMEOUT", "20"))
SELECT_COLUMNS = "id,name,metadata"

CLAIM_PROPERTIES = {
    "education": "P69",
    "occupation": "P106",
}
PROPERTY_TO_FIELD = {property_id: field for field, property_id in CLAIM_PROPERTIES.items()}
RANK_CONFIDENCE = {
    "preferred": 0.95,
    "normal": 0.9,
}
LABEL_LANGUAGES = ("en", "mul", "fr", "de", "it", "es", "ru", "uk", "ja", "ko", "zh", "pt", "pl", "ar")

HEADERS = {
    "User-Agent": os.environ.get(
        "EDUCATION_ENRICH_USER_AGENT",
        "FenceSpace-Scraper/education-occupation (+https://fencespace.app)",
    ),
    "Accept": "application/json, application/sparql-results+json;q=0.9, */*;q=0.8",
}

SPARQL_QUERY_TEMPLATE = """
SELECT ?athlete ?statement ?property ?value ?valueLabel ?rank WHERE {{
  VALUES ?athlete {{ {qid_values} }}
  VALUES (?property ?claimValue) {{
    (p:P69 ps:P69)
    (p:P106 ps:P106)
  }}
  ?athlete ?property ?statement .
  ?statement ?claimValue ?value .
  ?statement wikibase:rank ?rank .
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "{languages}" .
    ?value rdfs:label ?valueLabel .
  }}
}}
"""


def clean_text(value: Any) -> str | None:
    text = html.unescape(str(value or "")).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
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
            return {}
    return {}


def normalize_wikidata_id(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if "/" in text:
        text = text.rstrip("/").rsplit("/", 1)[-1]
    text = text.upper()
    return text if re.fullmatch(r"Q\d+", text) else None


def claim_source_url(qid: str, property_id: str) -> str:
    return f"https://www.wikidata.org/wiki/{qid}#{property_id}"


def confidence_for_rank(rank: str | None) -> float:
    return RANK_CONFIDENCE.get(rank or "", 0.85)


def label_for_qid(value_qid: str, entities: dict[str, Any]) -> str:
    labels = ((entities.get(value_qid) or {}).get("labels") or {})
    for language in LABEL_LANGUAGES:
        label = clean_text((labels.get(language) or {}).get("value"))
        if label:
            return label
    for label_data in labels.values():
        label = clean_text((label_data or {}).get("value"))
        if label:
            return label
    return value_qid


def qid_from_datavalue(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    qid = normalize_wikidata_id(value.get("id"))
    if qid:
        return qid
    numeric_id = value.get("numeric-id")
    if numeric_id is None:
        return None
    try:
        return f"Q{int(numeric_id)}"
    except (TypeError, ValueError):
        return None


def sort_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rank_order = {"preferred": 0, "normal": 1}
    return sorted(
        claims,
        key=lambda claim: (
            rank_order.get(str(claim.get("rank") or ""), 2),
            str(claim.get("label") or ""),
            str(claim.get("claim_id") or ""),
        ),
    )


def empty_claims() -> dict[str, list[dict[str, Any]]]:
    return {"education": [], "occupation": []}


def parse_entity_claims(qid: str, payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    qid = normalize_wikidata_id(qid) or qid
    entities = payload.get("entities") if isinstance(payload, dict) else {}
    if not isinstance(entities, dict):
        return empty_claims()
    entity = entities.get(qid) or {}
    raw_claims = entity.get("claims") or {}
    parsed = empty_claims()

    for field, property_id in CLAIM_PROPERTIES.items():
        for claim in raw_claims.get(property_id) or []:
            rank = clean_text(claim.get("rank")) or "normal"
            if rank == "deprecated":
                continue
            mainsnak = claim.get("mainsnak") or {}
            if mainsnak.get("snaktype") != "value":
                continue
            datavalue = mainsnak.get("datavalue") or {}
            value_qid = qid_from_datavalue(datavalue.get("value"))
            if not value_qid:
                continue
            parsed[field].append(
                {
                    "id": value_qid,
                    "label": label_for_qid(value_qid, entities),
                    "property": property_id,
                    "claim_id": clean_text(claim.get("id")),
                    "rank": rank,
                    "source_url": claim_source_url(qid, property_id),
                    "confidence": confidence_for_rank(rank),
                }
            )

    return {field: sort_claims(claims) for field, claims in parsed.items()}


def _last_url_segment(binding: dict[str, Any], key: str) -> str | None:
    value = clean_text((binding.get(key) or {}).get("value"))
    if not value:
        return None
    return value.rstrip("/").rsplit("/", 1)[-1]


def rank_from_sparql(value: Any) -> str:
    text = clean_text((value or {}).get("value")) if isinstance(value, dict) else clean_text(value)
    if not text:
        return "normal"
    if text.endswith("PreferredRank"):
        return "preferred"
    if text.endswith("DeprecatedRank"):
        return "deprecated"
    return "normal"


def parse_sparql_claim_bindings(bindings: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for binding in bindings:
        qid = normalize_wikidata_id(_last_url_segment(binding, "athlete"))
        property_id = clean_text(_last_url_segment(binding, "property"))
        value_qid = normalize_wikidata_id(_last_url_segment(binding, "value"))
        field = PROPERTY_TO_FIELD.get(property_id or "")
        rank = rank_from_sparql(binding.get("rank"))
        if not qid or not field or not property_id or not value_qid or rank == "deprecated":
            continue
        claims = grouped.setdefault(qid, empty_claims())
        claims[field].append(
            {
                "id": value_qid,
                "label": clean_text((binding.get("valueLabel") or {}).get("value")) or value_qid,
                "property": property_id,
                "claim_id": clean_text(_last_url_segment(binding, "statement")),
                "rank": rank,
                "source_url": claim_source_url(qid, property_id),
                "confidence": confidence_for_rank(rank),
            }
        )

    return {qid: {field: sort_claims(rows) for field, rows in claims.items()} for qid, claims in grouped.items()}


def fetch_sparql_claim_bindings(
    qids: list[str],
    *,
    session: requests.Session | None = None,
    languages: tuple[str, ...] = LABEL_LANGUAGES,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    normalized = [qid for qid in (normalize_wikidata_id(qid) for qid in qids) if qid]
    if not normalized:
        return {}
    qid_values = " ".join(f"wd:{qid}" for qid in dict.fromkeys(normalized))
    query = SPARQL_QUERY_TEMPLATE.format(qid_values=qid_values, languages=",".join(languages))
    http = session or requests.Session()
    response = http.get(
        SPARQL_URL,
        params={"query": query, "format": "json"},
        headers={**HEADERS, "Accept": "application/sparql-results+json"},
        timeout=60,
    )
    response.raise_for_status()
    return parse_sparql_claim_bindings(response.json().get("results", {}).get("bindings", []))


def fetch_entity_claims(qid: str, session: requests.Session | None = None) -> dict[str, list[dict[str, Any]]]:
    normalized = normalize_wikidata_id(qid)
    if not normalized:
        return empty_claims()
    http = session or requests.Session()
    response = http.get(
        WIKIDATA_ENTITY_URL.format(qid=normalized),
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return parse_entity_claims(normalized, response.json())


def get_supabase_client() -> Any | None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    from supabase import create_client

    return create_client(url, key)


def query_fencers_with_wikidata_id(client: Any, *, offset: int, limit: int) -> list[dict[str, Any]]:
    result = (
        client.table("fs_fencers")
        .select(SELECT_COLUMNS)
        .not_("metadata->>wikidata_id", "is", "null")
        .order("id")
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data or []


def wikidata_id_from_row(row: dict[str, Any]) -> str | None:
    qid = normalize_wikidata_id(row.get("wikidata_id"))
    if qid:
        return qid
    metadata = ensure_metadata(row.get("metadata"))
    return normalize_wikidata_id(metadata.get("wikidata_id"))


def build_update_payload(
    row: dict[str, Any],
    claims: dict[str, list[dict[str, Any]]],
    *,
    attempted_at: str,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    metadata = ensure_metadata(row.get("metadata"))
    education = list(claims.get("education") or [])
    occupation = list(claims.get("occupation") or [])
    field_names = []
    if education:
        field_names.append("education")
    if occupation:
        field_names.append("occupation")
    clean_errors = [clean_text(error)[:500] for error in errors or [] if clean_text(error)]

    if clean_errors and not field_names:
        status = "error"
    elif field_names:
        status = "updated"
    else:
        status = "no_claims"

    metadata["education"] = education
    metadata["occupation"] = occupation
    metadata["education_occupation_scrape"] = {
        "attempted_at": attempted_at,
        "status": status,
        "source": "wikidata",
        "fields_found": field_names,
        "errors": clean_errors,
    }
    return {"metadata": metadata}


def update_fencer(client: Any, fencer_id: str, payload: dict[str, Any]) -> None:
    client.table("fs_fencers").update(payload).eq("id", fencer_id).execute()


def _state_offset(value: Any) -> int:
    if isinstance(value, dict):
        try:
            return max(0, int(value.get("offset", 0)))
        except (TypeError, ValueError):
            return 0
    return 0


def run_enrichment(
    *,
    client: Any | None = None,
    get_client: Callable[[], Any | None] = get_supabase_client,
    claim_fetcher: Callable[[str], dict[str, list[dict[str, Any]]]] | None = None,
    page_size: int = PAGE_SIZE,
    limit: int | None = None,
    delay: float = REQUEST_DELAY_SECONDS,
    dry_run: bool = False,
    log_run: bool = True,
    update_state: bool = True,
    now: Callable[[], str] | None = None,
    emit: Callable[[str], None] = print,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    timestamp = now or (lambda: datetime.now(timezone.utc).isoformat())
    claim_fetcher = claim_fetcher or fetch_entity_claims
    summary: dict[str, Any] = {
        "queried": 0,
        "processed": 0,
        "written": 0,
        "emitted": 0,
        "failed": 0,
        "skipped": 0,
        "dry_run": dry_run,
        "reason": None,
        "errors": [],
    }

    try:
        client = client or get_client()
        if client is None:
            summary["dry_run"] = True
            summary["reason"] = "missing_supabase_credentials"
            emit("Dry run: SUPABASE_URL and SUPABASE_SERVICE_KEY are missing; no rows queried or written.")
            if run_log:
                run_log.complete(written=0, failed=0, skipped=0, metadata=summary)
            return summary

        cursor = get_state(SOURCE, "cursor") if update_state else None
        offset = _state_offset(cursor)
        remaining = limit

        while remaining is None or remaining > 0:
            batch_limit = page_size if remaining is None else min(page_size, remaining)
            rows = query_fencers_with_wikidata_id(client, offset=offset, limit=batch_limit)
            summary["queried"] += len(rows)
            if not rows:
                offset = 0
                break

            for row in rows:
                fencer_id = clean_text(row.get("id"))
                qid = wikidata_id_from_row(row)
                if not fencer_id or not qid:
                    summary["skipped"] += 1
                    continue

                try:
                    claims = claim_fetcher(qid)
                    payload = build_update_payload(row, claims, attempted_at=timestamp())
                    if dry_run:
                        emit(json.dumps({"id": fencer_id, "wikidata_id": qid, "payload": payload}, sort_keys=True))
                        summary["emitted"] += 1
                    else:
                        update_fencer(client, fencer_id, payload)
                        summary["written"] += 1
                    summary["processed"] += 1
                except Exception as exc:
                    summary["failed"] += 1
                    summary["errors"].append(f"{qid}: {str(exc)[:500]}")

                if delay > 0:
                    time.sleep(delay)

            offset += len(rows)
            if remaining is not None:
                remaining -= len(rows)
            if len(rows) < batch_limit:
                offset = 0
                break

        if update_state:
            set_state(SOURCE, "cursor", {"offset": offset, "updated_at": timestamp()})
            set_state(SOURCE, "last_run", timestamp())
            set_state(SOURCE, "last_summary", summary)

        if run_log:
            run_log.complete(
                written=summary["written"],
                failed=summary["failed"],
                skipped=summary["skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich fencer education and occupation metadata from sourced Wikidata claims."
    )
    parser.add_argument("--dry-run", action="store_true", help="Emit payloads without writing Supabase updates.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum fencers to process this run.")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE, help="Supabase page size.")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY_SECONDS, help="Delay between Wikidata requests.")
    args = parser.parse_args()

    summary = run_enrichment(
        dry_run=args.dry_run,
        limit=args.limit,
        page_size=args.page_size,
        delay=args.delay,
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

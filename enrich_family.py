import json
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

try:
    from supabase import create_client
except Exception:  # pragma: no cover - import errors surface when a client is required.
    create_client = None


SOURCE = "enrich_family"
SPARQL_URL = "https://query.wikidata.org/sparql"
PAGE_SIZE = int(os.environ.get("FAMILY_WIKIDATA_PAGE_SIZE", "5000"))
REQUEST_DELAY = float(os.environ.get("FAMILY_WIKIDATA_DELAY", "1.0"))
BATCH_SELECT_SIZE = int(os.environ.get("FAMILY_SELECT_BATCH_SIZE", "1000"))
BATCH_UPSERT_SIZE = int(os.environ.get("FAMILY_UPSERT_BATCH_SIZE", "500"))
FIE_ID_PROPERTY = os.environ.get("WIKIDATA_FIE_PROPERTY", "P2423")

if not re.fullmatch(r"P\d+", FIE_ID_PROPERTY):
    raise ValueError(f"Invalid FIE property: {FIE_ID_PROPERTY}")

HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; plerngh@gmail.com)",
}

RELATIONSHIP_TYPES = {"sibling", "parent", "spouse", "child", "relative"}

SPARQL_QUERY_TEMPLATE = """
SELECT ?athlete ?athleteLabel ?fie_id ?relationship ?property ?related ?relatedLabel ?statement WHERE {{
  ?athlete wdt:P641 wd:Q12100 .
  OPTIONAL {{ ?athlete wdt:{fie_prop} ?fie_id . }}
  {{
    BIND("sibling" AS ?relationship)
    BIND("P3373" AS ?property)
    ?athlete p:P3373 ?statement .
    ?statement ps:P3373 ?related .
  }}
  UNION
  {{
    BIND("parent" AS ?relationship)
    BIND("P22" AS ?property)
    ?athlete p:P22 ?statement .
    ?statement ps:P22 ?related .
  }}
  UNION
  {{
    BIND("parent" AS ?relationship)
    BIND("P25" AS ?property)
    ?athlete p:P25 ?statement .
    ?statement ps:P25 ?related .
  }}
  UNION
  {{
    BIND("spouse" AS ?relationship)
    BIND("P26" AS ?property)
    ?athlete p:P26 ?statement .
    ?statement ps:P26 ?related .
  }}
  UNION
  {{
    BIND("child" AS ?relationship)
    BIND("P40" AS ?property)
    ?athlete p:P40 ?statement .
    ?statement ps:P40 ?related .
  }}
  UNION
  {{
    BIND("relative" AS ?relationship)
    BIND("P1038" AS ?property)
    ?athlete p:P1038 ?statement .
    ?statement ps:P1038 ?related .
  }}
  FILTER(?athlete != ?related)
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
    ?athlete rdfs:label ?athleteLabel .
    ?related rdfs:label ?relatedLabel .
  }}
}}
ORDER BY ?athlete ?relationship ?relatedLabel
LIMIT {limit}
OFFSET {offset}
"""


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


def binding_value(binding: dict[str, Any], key: str) -> str | None:
    return clean_text((binding.get(key) or {}).get("value"))


def normalize_wikidata_id(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\bQ(\d+|[A-Z]+)\b", text, flags=re.IGNORECASE)
    if match:
        return f"Q{match.group(1).upper()}"
    if re.fullmatch(r"\d+", text):
        return f"Q{text}"
    return None


def wikidata_entity_id(url: str | None) -> str | None:
    return normalize_wikidata_id(url)


def wikidata_statement_id(url: str | None) -> str | None:
    text = clean_text(url)
    if not text:
        return None
    return text.rstrip("/").split("/")[-1] or None


def build_sparql_query(*, limit: int = PAGE_SIZE, offset: int = 0) -> str:
    return SPARQL_QUERY_TEMPLATE.format(
        fie_prop=FIE_ID_PROPERTY,
        limit=max(1, int(limit)),
        offset=max(0, int(offset)),
    )


def parse_family_binding(binding: dict[str, Any]) -> dict[str, Any] | None:
    fencer_wikidata_id = wikidata_entity_id(binding_value(binding, "athlete"))
    related_wikidata_id = wikidata_entity_id(binding_value(binding, "related"))
    relationship_type = clean_text(binding_value(binding, "relationship"))
    related_name = clean_text(binding_value(binding, "relatedLabel")) or related_wikidata_id

    if (
        not fencer_wikidata_id
        or not related_wikidata_id
        or relationship_type not in RELATIONSHIP_TYPES
        or not related_name
    ):
        return None

    return {
        "fencer_wikidata_id": fencer_wikidata_id,
        "fencer_name": clean_text(binding_value(binding, "athleteLabel")),
        "fie_id": clean_text(binding_value(binding, "fie_id")),
        "relationship_type": relationship_type,
        "related_wikidata_id": related_wikidata_id,
        "related_name": related_name,
        "wikidata_property": clean_text(binding_value(binding, "property")),
        "wikidata_statement": wikidata_statement_id(binding_value(binding, "statement")),
    }


def build_family_claims(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for binding in bindings:
        claim = parse_family_binding(binding)
        if not claim:
            continue
        key = (
            claim["fencer_wikidata_id"],
            claim["relationship_type"],
            claim["related_wikidata_id"],
        )
        claims_by_key.setdefault(key, claim)
    return list(claims_by_key.values())


def fetch_wikidata_family_bindings(
    *,
    page_size: int = PAGE_SIZE,
    delay: float = REQUEST_DELAY,
) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = build_sparql_query(limit=page_size, offset=offset)
        response = requests.get(
            SPARQL_URL,
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Wikidata SPARQL error {response.status_code}: {response.text[:500]}")
        page = response.json().get("results", {}).get("bindings", [])
        if not page:
            break
        bindings.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
        if delay > 0:
            time.sleep(delay)
    return bindings


def fencer_wikidata_id(fencer: dict[str, Any]) -> str | None:
    metadata = ensure_metadata(fencer.get("metadata"))
    return normalize_wikidata_id(metadata.get("wikidata_id") or fencer.get("wikidata_id"))


def build_fencer_indexes(fencers: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    by_wikidata_id: dict[str, set[str]] = defaultdict(set)

    for fencer in fencers:
        fencer_id = clean_text(fencer.get("id"))
        if not fencer_id:
            continue
        by_id[fencer_id] = fencer
        wikidata_id = fencer_wikidata_id(fencer)
        if wikidata_id:
            by_wikidata_id[wikidata_id].add(fencer_id)

    return {"by_id": by_id, "by_wikidata_id": by_wikidata_id}


def build_identity_maps(
    identities: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, str]]:
    row_groups: dict[str, set[str]] = defaultdict(set)
    row_identity_ids: dict[str, str] = {}

    for identity in identities:
        identity_id = clean_text(identity.get("id"))
        row_ids = {
            row_id
            for row_id in (clean_text(raw) for raw in identity.get("fs_fencer_row_ids") or [])
            if row_id
        }
        if not row_ids:
            continue
        for row_id in row_ids:
            row_groups[row_id].update(row_ids)
            if identity_id:
                row_identity_ids[row_id] = identity_id
    return row_groups, row_identity_ids


def expand_with_identity(fencer_ids: set[str], row_groups: dict[str, set[str]]) -> set[str]:
    expanded = set(fencer_ids)
    for fencer_id in list(fencer_ids):
        expanded.update(row_groups.get(fencer_id, {fencer_id}))
    return expanded


def relationship_key(claim: dict[str, Any]) -> str:
    related_wikidata_id = clean_text(claim.get("related_wikidata_id"))
    if related_wikidata_id:
        return related_wikidata_id
    return re.sub(r"[^a-z0-9]+", "-", clean_text(claim.get("related_name")) or "unknown").strip("-")


def relationship_row_id(
    *,
    fencer_id: str,
    relationship_type: str,
    source: str,
    key: str,
) -> str:
    raw = f"fs_fencer_family_relationships:{fencer_id}:{relationship_type}:{source}:{key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


def related_fencer_match(
    related_wikidata_id: str | None,
    *,
    indexes: dict[str, Any],
    row_groups: dict[str, set[str]],
    row_identity_ids: dict[str, str],
) -> dict[str, Any]:
    if not related_wikidata_id:
        return {"status": "unmatched", "fencer_id": None, "identity_id": None, "candidate_count": 0}

    candidate_ids = set(indexes["by_wikidata_id"].get(related_wikidata_id, set()))
    if not candidate_ids:
        return {"status": "unmatched", "fencer_id": None, "identity_id": None, "candidate_count": 0}

    if len(candidate_ids) == 1:
        fencer_id = next(iter(candidate_ids))
        return {
            "status": "matched",
            "fencer_id": fencer_id,
            "identity_id": row_identity_ids.get(fencer_id),
            "candidate_count": 1,
        }

    identity_ids = {row_identity_ids.get(fencer_id) for fencer_id in candidate_ids}
    identity_ids.discard(None)
    if len(identity_ids) == 1:
        identity_id = next(iter(identity_ids))
        row_ids_in_identity = {
            row_id for row_id, mapped_identity_id in row_identity_ids.items() if mapped_identity_id == identity_id
        }
        if candidate_ids.issubset(row_ids_in_identity):
            return {
                "status": "matched",
                "fencer_id": sorted(candidate_ids)[0],
                "identity_id": identity_id,
                "candidate_count": len(candidate_ids),
            }

    return {
        "status": "ambiguous_wikidata_match",
        "fencer_id": None,
        "identity_id": None,
        "candidate_count": len(candidate_ids),
    }


def relationship_metadata(claim: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "fencer_wikidata_label": claim.get("fencer_name"),
        "related_wikidata_label": claim.get("related_name"),
        "wikidata_property": claim.get("wikidata_property"),
        "wikidata_statement": claim.get("wikidata_statement"),
        "related_match_status": match["status"],
    }
    if claim.get("fie_id"):
        metadata["fie_id"] = claim["fie_id"]
    if match["status"] == "ambiguous_wikidata_match":
        metadata["related_match_candidate_count"] = match["candidate_count"]
    return {key: value for key, value in metadata.items() if value is not None}


def _build_relationship_rows(
    claims: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    identities: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    indexes = build_fencer_indexes(fencers)
    row_groups, row_identity_ids = build_identity_maps(identities)
    rows_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    matched_claims = 0

    for claim in claims:
        source_ids = set(indexes["by_wikidata_id"].get(claim["fencer_wikidata_id"], set()))
        source_ids = expand_with_identity(source_ids, row_groups)
        source_ids = {fencer_id for fencer_id in source_ids if fencer_id in indexes["by_id"]}
        if not source_ids:
            continue
        matched_claims += 1

        source = "wikidata"
        key = relationship_key(claim)
        match = related_fencer_match(
            claim.get("related_wikidata_id"),
            indexes=indexes,
            row_groups=row_groups,
            row_identity_ids=row_identity_ids,
        )
        confidence = 1.0 if match["status"] == "matched" else 0.95
        metadata = relationship_metadata(claim, match)

        for fencer_id in sorted(source_ids):
            row = {
                "id": relationship_row_id(
                    fencer_id=fencer_id,
                    relationship_type=claim["relationship_type"],
                    source=source,
                    key=key,
                ),
                "fencer_id": fencer_id,
                "fencer_identity_id": row_identity_ids.get(fencer_id),
                "fencer_wikidata_id": claim["fencer_wikidata_id"],
                "fencer_name": claim.get("fencer_name"),
                "relationship_type": claim["relationship_type"],
                "related_name": claim["related_name"],
                "related_wikidata_id": claim.get("related_wikidata_id"),
                "related_fencer_id": match["fencer_id"],
                "related_fencer_identity_id": match["identity_id"],
                "relationship_key": key,
                "source": source,
                "confidence": confidence,
                "metadata": metadata,
            }
            rows_by_key[(fencer_id, claim["relationship_type"], source, key)] = row

    return list(rows_by_key.values()), matched_claims


def build_relationship_rows(
    claims: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    identities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _build_relationship_rows(claims, fencers, identities)[0]


def get_client():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    if create_client is None:
        raise RuntimeError("supabase package is required.")
    return create_client(supabase_url, supabase_key)


def fetch_all(client, table: str, columns: str, *, page_size: int = BATCH_SELECT_SIZE) -> list[dict[str, Any]]:
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


def fetch_optional(client, table: str, columns: str, *, page_size: int = BATCH_SELECT_SIZE) -> list[dict[str, Any]]:
    try:
        return fetch_all(client, table, columns, page_size=page_size)
    except Exception as exc:
        print(f"  Optional table {table} unavailable: {exc}")
        return []


def upsert_relationship_rows(
    client,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = BATCH_UPSERT_SIZE,
) -> int:
    written = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        client.table("fs_fencer_family_relationships").upsert(
            batch,
            on_conflict="fencer_id,relationship_type,source,relationship_key",
        ).execute()
        written += len(batch)
    return written


def enrich_family_relationships(
    *,
    client=None,
    bindings: list[dict[str, Any]] | None = None,
    page_size: int = BATCH_SELECT_SIZE,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    client = client or get_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    get_state(SOURCE, "last_run") if update_state else None

    try:
        raw_bindings = bindings if bindings is not None else fetch_wikidata_family_bindings()
        claims = build_family_claims(raw_bindings)
        fencers = fetch_all(client, "fs_fencers", "id,fie_id,name,metadata", page_size=page_size)
        identities = fetch_optional(
            client,
            "fs_fencer_identities",
            "id,fs_fencer_row_ids,metadata",
            page_size=page_size,
        )
        rows, matched_claims = _build_relationship_rows(claims, fencers, identities)
        written = upsert_relationship_rows(client, rows)
        failed = 0
        skipped = len(claims) - matched_claims

        summary = {
            "claims_found": len(claims),
            "relationships_built": len(rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
        }

        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Family relationship enrichment starting - {datetime.now(timezone.utc).isoformat()}")
    summary = enrich_family_relationships()
    print(f"Family claims found: {summary['claims_found']}")
    print(f"Relationships built: {summary['relationships_built']}")
    print(f"Rows written: {summary['written']}")
    print(f"Failed rows: {summary['failed']}")
    print(f"Skipped claims: {summary['skipped']}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timezone
from typing import Any

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

try:
    from supabase import create_client
except Exception:  # pragma: no cover - import errors surface when a client is required.
    create_client = None

try:
    from compute_transfers import country_key as transfer_country_key
    from compute_transfers import normalize_country as transfer_normalize_country
except Exception:  # pragma: no cover - keep enrichment usable before Agent 26 is installed.
    transfer_country_key = None  # type: ignore[assignment]
    transfer_normalize_country = None  # type: ignore[assignment]


SOURCE = "enrich_nationality_history"
SPARQL_URL = "https://query.wikidata.org/sparql"
PAGE_SIZE = 5000
REQUEST_DELAY = 1.0
BATCH_SELECT_SIZE = 1000
BATCH_UPSERT_SIZE = 100
MAX_TRANSFER_CONFLICTS = 10
HISTORY_TABLE = "fs_fencer_nationality_history"
DISCREPANCY_TABLE = "fs_fencer_nationality_discrepancies"
HISTORY_NAMESPACE = uuid.UUID("8f62a35a-4d2b-4bb8-8a93-6e4efb832f3f")
DISCREPANCY_NAMESPACE = uuid.UUID("bb29342d-cc1f-44d6-b79f-fb7dd445aa3a")

CLAIM_SOURCES = {
    "P27": {"source": "wikidata_citizenship", "confidence": 0.95},
    "P1532": {"source": "wikidata_country_for_sport", "confidence": 0.85},
    "P54": {"source": "wikidata_national_team", "confidence": 0.65},
}

COUNTRY_CODE_ALIASES = {
    "canada": "CAN",
    "czechoslovakia": "TCH",
    "east germany": "GDR",
    "france": "FRA",
    "germany": "GER",
    "great britain": "GBR",
    "hong kong": "HKG",
    "italy": "ITA",
    "macau": "MAC",
    "russia": "RUS",
    "soviet union": "URS",
    "south korea": "KOR",
    "united states": "USA",
    "united states of america": "USA",
    "west germany": "FRG",
    "yugoslavia": "YUG",
}

class NationalityHistoryItem(dict):
    def _legacy_view(self) -> dict[str, Any]:
        legacy = {
            "country": self.get("country"),
            "country_id": self.get("country_id"),
            "source": "wikidata" if (clean_text(self.get("source", "")) or "").startswith("wikidata") else self.get("source"),
        }
        if self.get("start_date"):
            legacy["start_time"] = self["start_date"]
        if self.get("end_date"):
            legacy["end_time"] = self["end_date"]
        if "sequence_index" in self:
            legacy["sequence_index"] = self["sequence_index"]
        return {key: value for key, value in legacy.items() if value is not None}

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, dict) and other.get("source") == "wikidata" and "confidence" not in other:
            return self._legacy_view() == other
        return dict.__eq__(self, other)


FIE_ID_PROPERTY = os.environ.get("WIKIDATA_FIE_PROPERTY", "P2423")
if not re.fullmatch(r"P\d+", FIE_ID_PROPERTY):
    raise ValueError(f"Invalid FIE property: {FIE_ID_PROPERTY}")

HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; plerngh@gmail.com)",
}

SPARQL_QUERY_TEMPLATE = """
SELECT ?athlete ?athleteLabel ?fie_id ?statement ?claim_property ?country ?countryLabel
       ?country_code ?country_iso_code ?team ?teamLabel ?start_time ?end_time ?point_in_time WHERE {{
  {{
    SELECT ?athlete WHERE {{
      ?athlete wdt:P641 wd:Q12100 .
      {{
        ?athlete wdt:P27 ?country .
      }}
      UNION
      {{
        ?athlete wdt:P1532 ?country .
      }}
      UNION
      {{
        ?athlete p:P54 ?team_statement .
        ?team_statement ps:P54 ?team .
        ?team wdt:P17 ?country .
      }}
    }}
    GROUP BY ?athlete
    HAVING(COUNT(DISTINCT ?country) > 1)
  }}
  ?athlete wdt:P641 wd:Q12100 .
  OPTIONAL {{ ?athlete wdt:{fie_prop} ?fie_id . }}
  {{
    BIND(wd:P27 AS ?claim_property)
    ?athlete p:P27 ?statement .
    ?statement ps:P27 ?country .
  }}
  UNION
  {{
    BIND(wd:P1532 AS ?claim_property)
    ?athlete p:P1532 ?statement .
    ?statement ps:P1532 ?country .
  }}
  UNION
  {{
    BIND(wd:P54 AS ?claim_property)
    ?athlete p:P54 ?statement .
    ?statement ps:P54 ?team .
    OPTIONAL {{ ?statement pq:P1532 ?statement_country . }}
    OPTIONAL {{ ?team wdt:P17 ?team_country . }}
    BIND(COALESCE(?statement_country, ?team_country) AS ?country)
    FILTER(BOUND(?country))
  }}
  OPTIONAL {{ ?statement pq:P580 ?start_time . }}
  OPTIONAL {{ ?statement pq:P582 ?end_time . }}
  OPTIONAL {{ ?statement pq:P585 ?point_in_time . }}
  OPTIONAL {{ ?country wdt:P984 ?country_code . }}
  OPTIONAL {{ ?country wdt:P298 ?country_iso_code . }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
    ?athlete rdfs:label ?athleteLabel .
    ?country rdfs:label ?countryLabel .
    ?team rdfs:label ?teamLabel .
  }}
}}
ORDER BY ?athlete ?start_time ?point_in_time ?end_time ?countryLabel
LIMIT {limit}
OFFSET {offset}
"""


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_country(value: Any) -> str | None:
    if transfer_normalize_country is not None:
        return transfer_normalize_country(value)
    text = clean_text(value)
    return text.title() if text else None


def country_key(value: Any) -> str:
    if transfer_country_key is not None:
        return transfer_country_key(value)
    return (normalize_country(value) or "").casefold()


def normalize_country_code(country: Any, source_code: Any = None) -> str | None:
    code = clean_text(source_code)
    if code:
        normalized = re.sub(r"[^A-Za-z0-9]", "", code).upper()
        if normalized:
            return normalized

    country_name = normalize_country(country) or clean_text(country)
    if not country_name:
        return None
    return COUNTRY_CODE_ALIASES.get(country_key(country_name))


def binding_value(binding: dict[str, Any], key: str) -> str | None:
    return clean_text((binding.get(key) or {}).get("value"))


def wikidata_entity_id(url: str | None) -> str | None:
    if not url:
        return None
    return url.rstrip("/").split("/")[-1] or None


def parse_wikidata_time(raw: str | None) -> str | None:
    if not raw:
        return None
    match = re.match(r"[+-]?(\d{1,})-(\d{2})-(\d{2})T", raw)
    if not match:
        return None
    year, month, day = match.groups()
    if month == "00":
        return year
    if day == "00":
        return f"{year}-{month}"
    return f"{year}-{month}-{day}"


def time_sort_key(value: str | None) -> tuple[int, int, int, int]:
    if not value:
        return (1, 9999, 12, 31)
    parts = value.split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return (0, year, month, day)
    except (TypeError, ValueError):
        return (1, 9999, 12, 31)


def build_sparql_query(*, limit: int = PAGE_SIZE, offset: int = 0) -> str:
    return SPARQL_QUERY_TEMPLATE.format(
        fie_prop=FIE_ID_PROPERTY,
        limit=int(limit),
        offset=int(offset),
    )


def parse_binding(binding: dict[str, Any]) -> dict[str, Any]:
    claim_property = wikidata_entity_id(binding_value(binding, "claim_property"))
    country = binding_value(binding, "countryLabel")
    source_code = binding_value(binding, "country_code") or binding_value(binding, "country_iso_code")
    return {
        "wikidata_id": wikidata_entity_id(binding_value(binding, "athlete")),
        "name": binding_value(binding, "athleteLabel"),
        "fie_id": binding_value(binding, "fie_id"),
        "statement_id": wikidata_entity_id(binding_value(binding, "statement")),
        "claim_property": claim_property,
        "country": country,
        "country_code": normalize_country_code(country, source_code=source_code),
        "country_id": wikidata_entity_id(binding_value(binding, "country")),
        "team": binding_value(binding, "teamLabel"),
        "team_id": wikidata_entity_id(binding_value(binding, "team")),
        "start_date": parse_wikidata_time(binding_value(binding, "start_time")),
        "end_date": parse_wikidata_time(binding_value(binding, "end_time")),
        "point_in_time": parse_wikidata_time(binding_value(binding, "point_in_time")),
    }


def build_history_items(rows: list[dict[str, Any]], *, ordered: bool) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str | None, ...]] = set()
    for row in rows:
        country = clean_text(row.get("country"))
        if not country:
            continue
        key = (
            row.get("statement_id"),
            row.get("claim_property"),
            row.get("country_id") or country_key(country),
            row.get("country_code"),
            row.get("start_date"),
            row.get("end_date"),
            row.get("point_in_time"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    if ordered:
        deduped.sort(
            key=lambda row: (
                time_sort_key(row.get("start_date") or row.get("point_in_time")),
                time_sort_key(row.get("end_date")),
                country_key(row.get("country")),
                row.get("claim_property") or "",
            )
        )
    else:
        deduped.sort(key=lambda row: country_key(row.get("country")))

    history: list[dict[str, Any]] = []
    ambiguous = not ordered and len({country_key(row.get("country")) for row in deduped}) > 1
    for index, row in enumerate(deduped):
        claim_property = row.get("claim_property") or "P27"
        source_config = CLAIM_SOURCES.get(claim_property, {"source": "wikidata", "confidence": 0.5})
        item: dict[str, Any] = NationalityHistoryItem({
            "country": row["country"],
            "country_code": row.get("country_code"),
            "country_id": row.get("country_id"),
            "source": source_config["source"],
            "confidence": 0.55 if ambiguous else source_config["confidence"],
            "claim_property": claim_property,
            "wikidata_statement_id": row.get("statement_id"),
        })
        if not item["country_code"]:
            item.pop("country_code")
        if not item["country_id"]:
            item.pop("country_id")
        if not item["wikidata_statement_id"]:
            item.pop("wikidata_statement_id")
        if row.get("start_date"):
            item["start_date"] = row["start_date"]
        if row.get("end_date"):
            item["end_date"] = row["end_date"]
        if row.get("point_in_time"):
            item["point_in_time"] = row["point_in_time"]
        metadata = {}
        if row.get("team"):
            metadata["team"] = row["team"]
        if row.get("team_id"):
            metadata["team_id"] = row["team_id"]
        if metadata:
            item["metadata"] = metadata
        if ordered:
            item["sequence_index"] = index
        history.append(item)
    return history


def build_nationality_histories(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for binding in bindings:
        row = parse_binding(binding)
        if row.get("wikidata_id") and row.get("country"):
            grouped[row["wikidata_id"]].append(row)

    histories: list[dict[str, Any]] = []
    for wikidata_id, rows in sorted(grouped.items()):
        distinct_countries = {country_key(row.get("country")) for row in rows if row.get("country")}
        if len(distinct_countries) < 2:
            continue

        ordered = any(row.get("start_date") or row.get("end_date") or row.get("point_in_time") for row in rows)
        nationality_history = build_history_items(rows, ordered=ordered)
        if len({country_key(item["country"]) for item in nationality_history}) < 2:
            continue

        histories.append(
            {
                "wikidata_id": wikidata_id,
                "name": next((row.get("name") for row in rows if row.get("name")), None),
                "fie_id": next((row.get("fie_id") for row in rows if row.get("fie_id")), None),
                "ordered": ordered,
                "nationality_history": nationality_history,
            }
        )
    return histories


def fetch_wikidata_nationality_history() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = build_sparql_query(limit=PAGE_SIZE, offset=offset)
        response = requests.get(
            SPARQL_URL,
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Wikidata SPARQL error {response.status_code}: {response.text[:500]}")
        bindings = response.json()["results"]["bindings"]
        if not bindings:
            break
        results.extend(bindings)
        if len(bindings) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(REQUEST_DELAY)
    return results


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


def build_identity_maps(
    identities: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    row_groups: dict[str, set[str]] = defaultdict(set)
    fie_groups: dict[str, set[str]] = defaultdict(set)

    for identity in identities:
        row_ids = set()
        for raw_row_id in identity.get("fs_fencer_row_ids") or []:
            row_id = clean_text(raw_row_id)
            if row_id:
                row_ids.add(row_id)
        if not row_ids:
            continue
        for row_id in row_ids:
            row_groups[row_id].update(row_ids)
        for fie_id in identity.get("fie_ids") or []:
            clean_fie_id = clean_text(fie_id)
            if clean_fie_id:
                fie_groups[clean_fie_id].update(row_ids)
    return row_groups, fie_groups


def build_identity_index(identities: list[dict[str, Any]]) -> dict[str, str]:
    identity_by_row_id: dict[str, str] = {}
    for identity in identities:
        identity_id = clean_text(identity.get("id"))
        if not identity_id:
            continue
        for raw_row_id in identity.get("fs_fencer_row_ids") or []:
            row_id = clean_text(raw_row_id)
            if row_id:
                identity_by_row_id[row_id] = identity_id
    return identity_by_row_id


def build_fencer_indexes(fencers: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    by_fie_id: dict[str, set[str]] = defaultdict(set)
    by_wikidata_id: dict[str, set[str]] = defaultdict(set)
    by_name_country: dict[tuple[str, str], set[str]] = defaultdict(set)

    for fencer in fencers:
        fencer_id = clean_text(fencer.get("id"))
        if not fencer_id:
            continue
        by_id[fencer_id] = fencer
        fie_id = clean_text(fencer.get("fie_id"))
        if fie_id:
            by_fie_id[fie_id].add(fencer_id)
        metadata = ensure_metadata(fencer.get("metadata"))
        wikidata_id = clean_text(metadata.get("wikidata_id"))
        if wikidata_id:
            by_wikidata_id[wikidata_id].add(fencer_id)
        name = clean_text(fencer.get("name"))
        country = normalize_country(fencer.get("country"))
        if name and country:
            by_name_country[(name.casefold(), country_key(country))].add(fencer_id)

    return {
        "by_id": by_id,
        "by_fie_id": by_fie_id,
        "by_wikidata_id": by_wikidata_id,
        "by_name_country": by_name_country,
    }


def expand_with_identity(
    fencer_ids: set[str],
    *,
    fie_id: str | None,
    row_groups: dict[str, set[str]],
    fie_groups: dict[str, set[str]],
) -> set[str]:
    expanded = set(fencer_ids)
    for fencer_id in list(fencer_ids):
        expanded.update(row_groups.get(fencer_id, {fencer_id}))
    if fie_id:
        expanded.update(fie_groups.get(fie_id, set()))
    return expanded


def match_history_to_fencers(
    history: dict[str, Any],
    *,
    indexes: dict[str, Any],
    row_groups: dict[str, set[str]],
    fie_groups: dict[str, set[str]],
) -> set[str]:
    matched: set[str] = set()
    wikidata_id = clean_text(history.get("wikidata_id"))
    fie_id = clean_text(history.get("fie_id"))

    if wikidata_id:
        matched.update(indexes["by_wikidata_id"].get(wikidata_id, set()))
    if fie_id:
        matched.update(indexes["by_fie_id"].get(fie_id, set()))

    if matched:
        return expand_with_identity(matched, fie_id=fie_id, row_groups=row_groups, fie_groups=fie_groups)

    name = clean_text(history.get("name"))
    if not name:
        return set()

    candidate_groups: set[frozenset[str]] = set()
    for item in history.get("nationality_history") or []:
        key = (name.casefold(), country_key(item.get("country")))
        for fencer_id in indexes["by_name_country"].get(key, set()):
            candidate_groups.add(frozenset(row_groups.get(fencer_id, {fencer_id})))

    if len(candidate_groups) == 1:
        matched.update(next(iter(candidate_groups)))

    return expand_with_identity(matched, fie_id=fie_id, row_groups=row_groups, fie_groups=fie_groups)


def build_transfer_check(
    fencer_ids: set[str],
    nationality_history: list[dict[str, Any]],
    transfers: list[dict[str, Any]],
) -> dict[str, Any] | None:
    history_keys = {country_key(item.get("country")) for item in nationality_history if item.get("country")}
    if not history_keys:
        return None

    relevant = [row for row in transfers if clean_text(row.get("fencer_id")) in fencer_ids]
    if not relevant:
        return None

    matched = 0
    conflicts: list[dict[str, Any]] = []
    for row in relevant:
        from_key = country_key(row.get("from_country"))
        to_key = country_key(row.get("to_country"))
        if from_key in history_keys and to_key in history_keys:
            matched += 1
            continue
        if len(conflicts) < MAX_TRANSFER_CONFLICTS:
            conflicts.append(
                {
                    "from_country": normalize_country(row.get("from_country")),
                    "to_country": normalize_country(row.get("to_country")),
                    "season": clean_text(row.get("season")),
                    "source": clean_text(row.get("source")),
                    "confirmed": bool(row.get("confirmed")),
                }
            )

    return {
        "source": "fs_fencer_transfers",
        "checked": len(relevant),
        "matched": matched,
        "not_matched": len(relevant) - matched,
        "conflicts": conflicts,
    }


def stable_uuid(namespace: uuid.UUID, key: str) -> str:
    return str(uuid.uuid5(namespace, key))


def source_url(wikidata_id: str | None) -> str | None:
    if not wikidata_id:
        return None
    return f"https://www.wikidata.org/wiki/{wikidata_id}"


def country_tokens(country: Any, country_code: Any = None) -> set[str]:
    tokens: set[str] = set()
    normalized_country = normalize_country(country)
    if normalized_country:
        tokens.add(country_key(normalized_country))
    normalized_code = normalize_country_code(country, source_code=country_code)
    if normalized_code:
        tokens.add(normalized_code.casefold())
    return tokens


def history_country_tokens(nationality_history: list[dict[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for item in nationality_history:
        tokens.update(country_tokens(item.get("country"), item.get("country_code")))
    return tokens


def build_history_row(
    *,
    fencer_id: str,
    fencer_identity_id: str | None,
    history: dict[str, Any],
    item: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    wikidata_id = clean_text(history.get("wikidata_id"))
    country = normalize_country(item.get("country")) or clean_text(item.get("country"))
    country_code = normalize_country_code(country, source_code=item.get("country_code"))
    key_parts = [
        fencer_id,
        wikidata_id or "",
        clean_text(item.get("wikidata_statement_id")) or "",
        clean_text(item.get("source")) or "",
        country_code or country_key(country),
        clean_text(item.get("start_date")) or "",
        clean_text(item.get("end_date")) or "",
        clean_text(item.get("point_in_time")) or "",
    ]
    history_key = "|".join(key_parts)
    metadata = {
        "ordered": bool(history.get("ordered")),
        "source_url": source_url(wikidata_id),
    }
    metadata.update(item.get("metadata") or {})
    return {
        "id": stable_uuid(HISTORY_NAMESPACE, history_key),
        "history_key": history_key,
        "fencer_id": fencer_id,
        "fencer_identity_id": fencer_identity_id,
        "wikidata_id": wikidata_id,
        "wikidata_country_id": clean_text(item.get("country_id")),
        "wikidata_statement_id": clean_text(item.get("wikidata_statement_id")),
        "claim_property": clean_text(item.get("claim_property")),
        "country": country,
        "country_code": country_code,
        "start_date": clean_text(item.get("start_date")),
        "end_date": clean_text(item.get("end_date")),
        "point_in_time": clean_text(item.get("point_in_time")),
        "source": clean_text(item.get("source")) or "wikidata",
        "confidence": float(item.get("confidence") or 0.5),
        "sequence_index": item.get("sequence_index"),
        "metadata": metadata,
        "updated_at": updated_at,
    }


def build_discrepancy_row(
    *,
    fencer_id: str,
    fencer_identity_id: str | None,
    wikidata_id: str | None,
    discrepancy_type: str,
    source: str,
    description: str,
    confidence: float,
    updated_at: str,
    metadata: dict[str, Any],
    country_code: str | None = None,
    observed_country_code: str | None = None,
) -> dict[str, Any]:
    key_parts = [
        fencer_id,
        wikidata_id or "",
        discrepancy_type,
        source,
        country_code or "",
        observed_country_code or "",
        json.dumps(metadata, sort_keys=True, default=str),
    ]
    discrepancy_key = "|".join(key_parts)
    return {
        "id": stable_uuid(DISCREPANCY_NAMESPACE, discrepancy_key),
        "discrepancy_key": discrepancy_key,
        "fencer_id": fencer_id,
        "fencer_identity_id": fencer_identity_id,
        "wikidata_id": wikidata_id,
        "discrepancy_type": discrepancy_type,
        "source": source,
        "severity": "needs_review",
        "country_code": country_code,
        "observed_country_code": observed_country_code,
        "description": description,
        "confidence": confidence,
        "metadata": metadata,
        "updated_at": updated_at,
    }


def build_discrepancy_rows(
    *,
    fencer: dict[str, Any],
    fencer_identity_id: str | None,
    history: dict[str, Any],
    transfers: list[dict[str, Any]],
    updated_at: str,
) -> list[dict[str, Any]]:
    fencer_id = clean_text(fencer.get("id"))
    if not fencer_id:
        return []
    wikidata_id = clean_text(history.get("wikidata_id"))
    nationality_history = history.get("nationality_history") or []
    known_tokens = history_country_tokens(nationality_history)
    rows: list[dict[str, Any]] = []

    if nationality_history and not history.get("ordered") and len(known_tokens) > 1:
        rows.append(
            build_discrepancy_row(
                fencer_id=fencer_id,
                fencer_identity_id=fencer_identity_id,
                wikidata_id=wikidata_id,
                discrepancy_type="ambiguous_wikidata_claims",
                source="wikidata",
                description="Multiple Wikidata nationality claims lack start, end, or point-in-time qualifiers.",
                confidence=0.35,
                updated_at=updated_at,
                metadata={"nationality_history": nationality_history},
            )
        )

    current_country = normalize_country(fencer.get("country"))
    current_code = normalize_country_code(current_country)
    if current_country and not country_tokens(current_country, current_code).issubset(known_tokens):
        rows.append(
            build_discrepancy_row(
                fencer_id=fencer_id,
                fencer_identity_id=fencer_identity_id,
                wikidata_id=wikidata_id,
                discrepancy_type="current_country_not_in_wikidata",
                source="fs_fencers",
                description="Current fs_fencers.country is not present in source-backed Wikidata nationality history.",
                confidence=0.6,
                updated_at=updated_at,
                metadata={
                    "current_country": current_country,
                    "current_country_code": current_code,
                    "wikidata_country_codes": sorted(
                        code
                        for item in nationality_history
                        for code in [normalize_country_code(item.get("country"), item.get("country_code"))]
                        if code
                    ),
                },
                observed_country_code=current_code,
            )
        )

    for transfer in transfers:
        if clean_text(transfer.get("fencer_id")) != fencer_id:
            continue
        from_country = normalize_country(transfer.get("from_country"))
        to_country = normalize_country(transfer.get("to_country"))
        from_code = normalize_country_code(from_country)
        to_code = normalize_country_code(to_country)
        if country_tokens(from_country, from_code).issubset(known_tokens) and country_tokens(
            to_country, to_code
        ).issubset(known_tokens):
            continue
        rows.append(
            build_discrepancy_row(
                fencer_id=fencer_id,
                fencer_identity_id=fencer_identity_id,
                wikidata_id=wikidata_id,
                discrepancy_type="transfer_country_not_in_wikidata",
                source="fs_fencer_transfers",
                description="A ranking/result transfer country is not present in Wikidata nationality history.",
                confidence=0.75 if transfer.get("confirmed") else 0.5,
                updated_at=updated_at,
                metadata={
                    "transfer": {
                        "from_country": from_country,
                        "from_country_code": from_code,
                        "to_country": to_country,
                        "to_country_code": to_code,
                        "season": clean_text(transfer.get("season")),
                        "source": clean_text(transfer.get("source")),
                        "confirmed": bool(transfer.get("confirmed")),
                        "metadata": transfer.get("metadata") or {},
                    }
                },
                country_code=from_code,
                observed_country_code=to_code,
            )
        )
    return rows


def upsert_rows(
    client,
    table: str,
    rows: list[dict[str, Any]],
    *,
    on_conflict: str,
    batch_size: int = BATCH_UPSERT_SIZE,
) -> tuple[int, int]:
    if not rows:
        return 0, 0
    probe = client.table(table)
    if not hasattr(probe, "upsert"):
        print(f"  Optional table {table} upsert unavailable: client table has no upsert")
        return 0, 0

    written = failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table(table).upsert(batch, on_conflict=on_conflict).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  {table} upsert batch {index // batch_size} failed: {exc}")
            failed += len(batch)
    return written, failed


def update_fencer_history(
    client,
    fencer: dict[str, Any],
    *,
    nationality_history: list[dict[str, Any]],
    transfer_check: dict[str, Any] | None,
    updated_at: str,
) -> None:
    metadata = ensure_metadata(fencer.get("metadata"))
    metadata["nationality_history"] = nationality_history
    metadata["nationality_history_source"] = "wikidata"
    metadata["nationality_history_updated_at"] = updated_at
    if transfer_check:
        metadata["nationality_history_transfer_check"] = transfer_check
    else:
        metadata.pop("nationality_history_transfer_check", None)
    client.table("fs_fencers").update({"metadata": metadata}).eq("id", fencer["id"]).execute()


def enrich_nationality_history(
    *,
    client=None,
    bindings: list[dict[str, Any]] | None = None,
    page_size: int = BATCH_SELECT_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    updated_at: str | None = None,
) -> dict[str, int]:
    client = client or get_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    get_state(SOURCE, "last_run") if update_state else None
    updated_at = updated_at or datetime.now(UTC).isoformat()

    try:
        raw_bindings = bindings if bindings is not None else fetch_wikidata_nationality_history()
        histories = build_nationality_histories(raw_bindings)
        fencers = fetch_all(client, "fs_fencers", "id,fie_id,name,country,metadata", page_size=page_size)
        identities = fetch_optional(
            client,
            "fs_fencer_identities",
            "id,fie_ids,fs_fencer_row_ids,metadata",
            page_size=page_size,
        )
        transfers = fetch_optional(
            client,
            "fs_fencer_transfers",
            "fencer_id,from_country,to_country,season,source,confirmed,competition_id,metadata",
            page_size=page_size,
        )

        indexes = build_fencer_indexes(fencers)
        row_groups, fie_groups = build_identity_maps(identities)
        identity_by_row_id = build_identity_index(identities)

        written = failed = skipped = 0
        matched_fencer_ids: set[str] = set()
        for history in histories:
            matched_ids = match_history_to_fencers(
                history,
                indexes=indexes,
                row_groups=row_groups,
                fie_groups=fie_groups,
            )
            matched_ids = {fencer_id for fencer_id in matched_ids if fencer_id in indexes["by_id"]}
            if not matched_ids:
                skipped += 1
                continue

            transfer_check = build_transfer_check(
                matched_ids,
                history["nationality_history"],
                transfers,
            )
            history_rows: list[dict[str, Any]] = []
            discrepancy_rows: list[dict[str, Any]] = []
            for fencer_id in sorted(matched_ids):
                fencer = indexes["by_id"][fencer_id]
                fencer_identity_id = identity_by_row_id.get(fencer_id)
                for item in history["nationality_history"]:
                    history_rows.append(
                        build_history_row(
                            fencer_id=fencer_id,
                            fencer_identity_id=fencer_identity_id,
                            history=history,
                            item=item,
                            updated_at=updated_at,
                        )
                    )
                discrepancy_rows.extend(
                    build_discrepancy_rows(
                        fencer=fencer,
                        fencer_identity_id=fencer_identity_id,
                        history=history,
                        transfers=transfers,
                        updated_at=updated_at,
                    )
                )
            _, history_failed = upsert_rows(client, HISTORY_TABLE, history_rows, on_conflict="history_key")
            _, discrepancy_failed = upsert_rows(
                client,
                DISCREPANCY_TABLE,
                discrepancy_rows,
                on_conflict="discrepancy_key",
            )
            failed += history_failed + discrepancy_failed
            for fencer_id in sorted(matched_ids):
                try:
                    update_fencer_history(
                        client,
                        indexes["by_id"][fencer_id],
                        nationality_history=history["nationality_history"],
                        transfer_check=transfer_check,
                        updated_at=updated_at,
                    )
                    written += 1
                    matched_fencer_ids.add(fencer_id)
                except Exception as exc:
                    failed += 1
                    print(f"  Failed to update nationality history for {fencer_id}: {exc}")

        summary = {
            "histories_found": len(histories),
            "fencers_matched": len(matched_fencer_ids),
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
                    "completed_at": datetime.now(UTC).isoformat(),
                },
            )
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=skipped,
                metadata={
                    "histories_found": len(histories),
                    "fencers_matched": len(matched_fencer_ids),
                },
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Nationality history enrichment starting - {datetime.now(UTC).isoformat()}")
    summary = enrich_nationality_history()
    print(f"Nationality histories found: {summary['histories_found']}")
    print(f"Fencers matched: {summary['fencers_matched']}")
    print(f"Rows written: {summary['written']}")
    print(f"Failed rows: {summary['failed']}")
    print(f"Skipped histories: {summary['skipped']}")


if __name__ == "__main__":
    main()

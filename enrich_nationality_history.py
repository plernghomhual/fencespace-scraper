from __future__ import annotations

import json
import os
import re
import time
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

try:
    from compute_transfers import country_key as transfer_country_key
    from compute_transfers import normalize_country as transfer_normalize_country
except Exception:  # pragma: no cover - keep enrichment usable before Agent 26 is installed.
    transfer_country_key = None
    transfer_normalize_country = None


SOURCE = "enrich_nationality_history"
SPARQL_URL = "https://query.wikidata.org/sparql"
PAGE_SIZE = 5000
REQUEST_DELAY = 1.0
BATCH_SELECT_SIZE = 1000
MAX_TRANSFER_CONFLICTS = 10

FIE_ID_PROPERTY = os.environ.get("WIKIDATA_FIE_PROPERTY", "P2423")
if not re.fullmatch(r"P\d+", FIE_ID_PROPERTY):
    raise ValueError(f"Invalid FIE property: {FIE_ID_PROPERTY}")

HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "FenceSpace/1.0 (https://fencespace.app; plerngh@gmail.com)",
}

SPARQL_QUERY_TEMPLATE = """
SELECT ?athlete ?athleteLabel ?fie_id ?statement ?country ?countryLabel ?start_time ?end_time WHERE {{
  {{
    SELECT ?athlete WHERE {{
      ?athlete wdt:P641 wd:Q12100 .
      ?athlete wdt:P27 ?country .
      ?athlete p:P27 ?statement .
    }}
    GROUP BY ?athlete
    HAVING(COUNT(DISTINCT ?country) > 1)
  }}
  ?athlete wdt:P641 wd:Q12100 .
  OPTIONAL {{ ?athlete wdt:{fie_prop} ?fie_id . }}
  ?athlete wdt:P27 ?country .
  ?athlete p:P27 ?statement .
  ?statement ps:P27 ?country .
  OPTIONAL {{ ?statement pq:P580 ?start_time . }}
  OPTIONAL {{ ?statement pq:P582 ?end_time . }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
    ?athlete rdfs:label ?athleteLabel .
    ?country rdfs:label ?countryLabel .
  }}
}}
ORDER BY ?athlete ?start_time ?end_time ?countryLabel
LIMIT {limit}
OFFSET {offset}
"""


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_country(value: Any) -> str | None:
    if transfer_normalize_country:
        return transfer_normalize_country(value)
    text = clean_text(value)
    return text.title() if text else None


def country_key(value: Any) -> str:
    if transfer_country_key:
        return transfer_country_key(value)
    return (normalize_country(value) or "").casefold()


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
    return {
        "wikidata_id": wikidata_entity_id(binding_value(binding, "athlete")),
        "name": binding_value(binding, "athleteLabel"),
        "fie_id": binding_value(binding, "fie_id"),
        "country": binding_value(binding, "countryLabel"),
        "country_id": wikidata_entity_id(binding_value(binding, "country")),
        "start_time": parse_wikidata_time(binding_value(binding, "start_time")),
        "end_time": parse_wikidata_time(binding_value(binding, "end_time")),
    }


def build_history_items(rows: list[dict[str, Any]], *, ordered: bool) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for row in rows:
        country = clean_text(row.get("country"))
        if not country:
            continue
        key = (row.get("country_id") or country_key(country), row.get("start_time"), row.get("end_time"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    if ordered:
        deduped.sort(
            key=lambda row: (
                time_sort_key(row.get("start_time")),
                time_sort_key(row.get("end_time")),
                country_key(row.get("country")),
            )
        )
    else:
        deduped.sort(key=lambda row: country_key(row.get("country")))

    history: list[dict[str, Any]] = []
    for index, row in enumerate(deduped):
        item: dict[str, Any] = {
            "country": row["country"],
            "country_id": row.get("country_id"),
            "source": "wikidata",
        }
        if not item["country_id"]:
            item.pop("country_id")
        if row.get("start_time"):
            item["start_time"] = row["start_time"]
        if row.get("end_time"):
            item["end_time"] = row["end_time"]
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

        ordered = any(row.get("start_time") or row.get("end_time") for row in rows)
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
    updated_at = updated_at or datetime.now(timezone.utc).isoformat()

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
                    "completed_at": datetime.now(timezone.utc).isoformat(),
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
    print(f"Nationality history enrichment starting - {datetime.now(timezone.utc).isoformat()}")
    summary = enrich_nationality_history()
    print(f"Nationality histories found: {summary['histories_found']}")
    print(f"Fencers matched: {summary['fencers_matched']}")
    print(f"Rows written: {summary['written']}")
    print(f"Failed rows: {summary['failed']}")
    print(f"Skipped histories: {summary['skipped']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Merge duplicate fs_fencers rows into canonical identity groups."""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from supabase import create_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from run_logger import ScraperRunLogger
from scraper_state import set_state

MODULE_NAME = "merge_fencer_identities"
FENCER_COLUMNS = "id,fie_id,name,country,weapon,category"
IDENTITY_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "fencespace:fencer-identities")


@dataclass
class IdentityBuildResult:
    total_fencers: int
    identities: list[dict[str, Any]]
    ambiguous_cases: list[dict[str, Any]]

    @property
    def ambiguous_cases_left(self) -> int:
        return len(self.ambiguous_cases)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def normalize_identity_text(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = unicodedata.normalize("NFKC", text).lower().strip()
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def deterministic_identity_id(identity_key: str) -> str:
    return str(uuid.uuid5(IDENTITY_NAMESPACE, identity_key))


def most_common_text(rows: list[dict[str, Any]], field: str) -> str | None:
    values = [clean_text(row.get(field)) for row in rows]
    values = [value for value in values if value]
    if not values:
        return None
    counts = Counter(values)
    return sorted(counts, key=lambda value: (-counts[value], value))[0]


def sorted_unique_text(rows: list[dict[str, Any]], field: str) -> list[str]:
    return sorted({value for row in rows if (value := clean_text(row.get(field)))})


def row_identity_key(row: dict[str, Any]) -> tuple[str, str] | None:
    name_key = normalize_identity_text(row.get("name"))
    country_key = normalize_identity_text(row.get("country"))
    if not name_key or not country_key:
        return None
    return name_key, country_key


def build_identity_payload(
    *,
    identity_key: str,
    rows: list[dict[str, Any]],
    fie_ids: set[str],
    match_type: str,
    normalized_key: tuple[str, str] | None,
) -> dict[str, Any] | None:
    row_ids = sorted({value for row in rows if (value := clean_text(row.get("id")))})
    if not row_ids:
        return None

    metadata: dict[str, Any] = {
        "identity_key": identity_key,
        "match_type": match_type,
        "row_count": len(row_ids),
        "weapons": sorted_unique_text(rows, "weapon"),
        "categories": sorted_unique_text(rows, "category"),
        "source": MODULE_NAME,
    }
    if normalized_key:
        metadata["normalized_name"] = normalized_key[0]
        metadata["normalized_country"] = normalized_key[1]

    return {
        "id": deterministic_identity_id(identity_key),
        "canonical_name": most_common_text(rows, "name"),
        "country": most_common_text(rows, "country"),
        "fie_ids": sorted(fie_ids),
        "fs_fencer_row_ids": row_ids,
        "metadata": metadata,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def build_identity_groups(fencers: list[dict[str, Any]]) -> IdentityBuildResult:
    fie_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    no_fie_rows: list[dict[str, Any]] = []

    for row in fencers:
        fie_id = clean_text(row.get("fie_id"))
        if fie_id:
            fie_groups[fie_id].append(row)
        else:
            no_fie_rows.append(row)

    working_groups: dict[str, dict[str, Any]] = {}
    name_country_to_fie_groups: dict[tuple[str, str], set[str]] = defaultdict(set)

    for fie_id, rows in sorted(fie_groups.items()):
        identity_key = f"fie:{fie_id}"
        working_groups[identity_key] = {
            "identity_key": identity_key,
            "rows": list(rows),
            "fie_ids": {fie_id},
            "match_type": "fie_id",
            "normalized_key": None,
        }
        for row in rows:
            normalized_key = row_identity_key(row)
            if normalized_key:
                name_country_to_fie_groups[normalized_key].add(identity_key)

    ambiguous_cases: list[dict[str, Any]] = []
    no_fie_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in no_fie_rows:
        normalized_key = row_identity_key(row)
        if not normalized_key:
            ambiguous_cases.append({
                "fs_fencer_row_id": clean_text(row.get("id")),
                "name": clean_text(row.get("name")),
                "country": clean_text(row.get("country")),
                "reason": "missing_name_country_key",
            })
            continue

        candidate_fie_groups = sorted(name_country_to_fie_groups.get(normalized_key, set()))
        if len(candidate_fie_groups) == 1:
            working_groups[candidate_fie_groups[0]]["rows"].append(row)
        elif len(candidate_fie_groups) > 1:
            ambiguous_cases.append({
                "fs_fencer_row_id": clean_text(row.get("id")),
                "name": clean_text(row.get("name")),
                "country": clean_text(row.get("country")),
                "normalized_name": normalized_key[0],
                "normalized_country": normalized_key[1],
                "candidate_identity_ids": [
                    deterministic_identity_id(candidate_key) for candidate_key in candidate_fie_groups
                ],
                "reason": "matched_multiple_fie_identities",
            })
        else:
            no_fie_groups[normalized_key].append(row)

    for normalized_key, rows in sorted(no_fie_groups.items()):
        identity_key = f"name_country:{normalized_key[0]}:{normalized_key[1]}"
        working_groups[identity_key] = {
            "identity_key": identity_key,
            "rows": list(rows),
            "fie_ids": set(),
            "match_type": "name_country",
            "normalized_key": normalized_key,
        }

    identities = []
    for identity_key in sorted(working_groups):
        group = working_groups[identity_key]
        payload = build_identity_payload(
            identity_key=group["identity_key"],
            rows=group["rows"],
            fie_ids=group["fie_ids"],
            match_type=group["match_type"],
            normalized_key=group["normalized_key"],
        )
        if payload:
            identities.append(payload)

    return IdentityBuildResult(
        total_fencers=len(fencers),
        identities=identities,
        ambiguous_cases=ambiguous_cases,
    )


def get_supabase_client():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(supabase_url, supabase_key)


def fetch_fencers(client, page_size: int = 1000) -> list[dict[str, Any]]:
    fencers: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + page_size - 1
        result = (
            client.table("fs_fencers")
            .select(FENCER_COLUMNS)
            .range(start, end)
            .execute()
        )
        batch = result.data or []
        fencers.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return fencers


def upsert_identity_groups(client, identities: list[dict[str, Any]], batch_size: int = 100) -> int:
    written = 0
    for start in range(0, len(identities), batch_size):
        batch = identities[start:start + batch_size]
        client.table("fs_fencer_identities").upsert(batch, on_conflict="id").execute()
        written += len(batch)
    return written


def merge_fencer_identities(
    *,
    client=None,
    page_size: int = 1000,
    batch_size: int = 100,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    run_log = ScraperRunLogger(MODULE_NAME).start() if log_run else None
    try:
        client = client or get_supabase_client()
        fencers = fetch_fencers(client, page_size=page_size)
        result = build_identity_groups(fencers)
        written = upsert_identity_groups(client, result.identities, batch_size=batch_size)
        report = {
            "total_fencers": result.total_fencers,
            "identities_found": len(result.identities),
            "ambiguous_cases_left": result.ambiguous_cases_left,
            "identity_groups_created": written,
        }
        if update_state:
            set_state(
                MODULE_NAME,
                "last_run",
                {
                    **report,
                    "completed_at": datetime.now(UTC).isoformat(),
                },
            )
        if run_log:
            run_log.complete(
                written=written,
                failed=0,
                skipped=result.ambiguous_cases_left,
                metadata=report,
            )
        return report
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge fs_fencers rows into canonical fencer identities.")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = merge_fencer_identities(page_size=args.page_size, batch_size=args.batch_size)
    print(f"Total fencers: {report['total_fencers']}")
    print(f"Identities found: {report['identities_found']}")
    print(f"Ambiguous cases left: {report['ambiguous_cases_left']}")
    print(f"Identity groups created: {report['identity_groups_created']}")


if __name__ == "__main__":
    main()

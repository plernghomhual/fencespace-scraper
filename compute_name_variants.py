#!/usr/bin/env python3
"""Compute per-identity fencer name variants across source tables."""

from __future__ import annotations

import argparse
import os
import re
import unicodedata
from datetime import UTC, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state

MODULE_NAME = "compute_name_variants"
PAGE_SIZE = 1000
BATCH_SIZE = 100

NAME_VARIANT_CONFLICT = "fencer_id,name,script"
SOURCE_PRIORITY = {
    "fs_fencers": 0,
    "fs_results": 1,
    "fs_national_fed_rankings": 2,
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _contains_range(text: str, start: int, end: int) -> bool:
    return any(start <= ord(char) <= end for char in text)


def _contains_latin_letter(text: str) -> bool:
    for char in text:
        if not unicodedata.category(char).startswith("L"):
            continue
        if "LATIN" in unicodedata.name(char, ""):
            return True
    return False


def detect_script(value: Any) -> str:
    text = clean_text(value) or ""
    if _contains_range(text, 0xAC00, 0xD7AF):
        return "Hangul"
    if _contains_range(text, 0x4E00, 0x9FFF):
        return "CJK"
    if _contains_range(text, 0x0400, 0x04FF):
        return "Cyrillic"
    if _contains_range(text, 0x0600, 0x06FF):
        return "Arabic"
    if _contains_latin_letter(text):
        return "Latin"
    return "Other"


def build_identity_indexes(
    identities: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, str], dict[str, str | None]]:
    by_fencer_row_id: dict[str, str] = {}
    by_fie_id: dict[str, str] = {}
    country_by_identity: dict[str, str | None] = {}

    for identity in identities:
        identity_id = clean_text(identity.get("id"))
        if not identity_id:
            continue

        country_by_identity[identity_id] = clean_text(identity.get("country"))

        for row_id in identity.get("fs_fencer_row_ids") or []:
            cleaned_row_id = clean_text(row_id)
            if cleaned_row_id:
                by_fencer_row_id.setdefault(cleaned_row_id, identity_id)

        for fie_id in identity.get("fie_ids") or []:
            cleaned_fie_id = clean_text(fie_id)
            if cleaned_fie_id:
                by_fie_id.setdefault(cleaned_fie_id, identity_id)

    return by_fencer_row_id, by_fie_id, country_by_identity


def _identity_for_source_row(
    row: dict[str, Any],
    *,
    row_id_field: str,
    fie_id_field: str | None,
    by_fencer_row_id: dict[str, str],
    by_fie_id: dict[str, str],
) -> str | None:
    row_id = clean_text(row.get(row_id_field))
    if row_id and row_id in by_fencer_row_id:
        return by_fencer_row_id[row_id]

    if fie_id_field:
        fie_id = clean_text(row.get(fie_id_field))
        if fie_id and fie_id in by_fie_id:
            return by_fie_id[fie_id]

    return None


def _row_country(row: dict[str, Any], identity_id: str, country_by_identity: dict[str, str | None]) -> str | None:
    return clean_text(row.get("country")) or clean_text(row.get("nationality")) or country_by_identity.get(identity_id)


def _add_variant(
    variants: dict[tuple[str, str, str], dict[str, Any]],
    *,
    identity_id: str,
    name: str,
    source: str,
    country: str | None,
    source_row_id: Any,
) -> None:
    script = detect_script(name)
    key = (identity_id, name, script)
    priority = SOURCE_PRIORITY[source]
    row = variants.setdefault(
        key,
        {
            "fencer_id": identity_id,
            "name": name,
            "script": script,
            "source": source,
            "country": country,
            "metadata": {
                "sources": [],
                "source_row_ids": [],
                "countries": [],
            },
            "_source_priority": priority,
        },
    )

    if priority < row["_source_priority"]:
        row["source"] = source
        row["_source_priority"] = priority

    if country and not row.get("country"):
        row["country"] = country

    metadata = row["metadata"]
    if source not in metadata["sources"]:
        metadata["sources"].append(source)

    cleaned_source_row_id = clean_text(source_row_id)
    if cleaned_source_row_id and cleaned_source_row_id not in metadata["source_row_ids"]:
        metadata["source_row_ids"].append(cleaned_source_row_id)

    if country and country not in metadata["countries"]:
        metadata["countries"].append(country)


def _finalize_variants(variants: dict[tuple[str, str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in variants.values():
        metadata = row["metadata"]
        metadata["sources"] = sorted(metadata["sources"], key=lambda source: SOURCE_PRIORITY[source])
        metadata["source_row_ids"] = sorted(metadata["source_row_ids"])
        metadata["countries"] = sorted(metadata["countries"])
        clean_row = {key: value for key, value in row.items() if not key.startswith("_")}
        rows.append(clean_row)
    return sorted(rows, key=lambda row: (row["fencer_id"], row["name"], row["script"]))


def _build_name_variants_with_stats(
    identities: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    results: list[dict[str, Any]],
    national_fed_rankings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_fencer_row_id, by_fie_id, country_by_identity = build_identity_indexes(identities)
    variants: dict[tuple[str, str, str], dict[str, Any]] = {}
    source_names_seen = 0
    skipped_without_identity = 0

    for row in fencers:
        name = clean_text(row.get("name"))
        if not name:
            continue
        source_names_seen += 1
        identity_id = _identity_for_source_row(
            row,
            row_id_field="id",
            fie_id_field="fie_id",
            by_fencer_row_id=by_fencer_row_id,
            by_fie_id=by_fie_id,
        )
        if not identity_id:
            skipped_without_identity += 1
            continue
        _add_variant(
            variants,
            identity_id=identity_id,
            name=name,
            source="fs_fencers",
            country=_row_country(row, identity_id, country_by_identity),
            source_row_id=row.get("id"),
        )

    for row in results:
        name = clean_text(row.get("name"))
        if not name:
            continue
        source_names_seen += 1
        identity_id = _identity_for_source_row(
            row,
            row_id_field="fencer_id",
            fie_id_field="fie_fencer_id",
            by_fencer_row_id=by_fencer_row_id,
            by_fie_id=by_fie_id,
        )
        if not identity_id:
            skipped_without_identity += 1
            continue
        _add_variant(
            variants,
            identity_id=identity_id,
            name=name,
            source="fs_results",
            country=_row_country(row, identity_id, country_by_identity),
            source_row_id=row.get("id"),
        )

    for row in national_fed_rankings:
        name = clean_text(row.get("name"))
        if not name:
            continue
        source_names_seen += 1
        identity_id = _identity_for_source_row(
            row,
            row_id_field="fencer_id",
            fie_id_field="fie_id",
            by_fencer_row_id=by_fencer_row_id,
            by_fie_id=by_fie_id,
        )
        if not identity_id:
            skipped_without_identity += 1
            continue
        _add_variant(
            variants,
            identity_id=identity_id,
            name=name,
            source="fs_national_fed_rankings",
            country=_row_country(row, identity_id, country_by_identity),
            source_row_id=row.get("id"),
        )

    return _finalize_variants(variants), {
        "source_names_seen": source_names_seen,
        "skipped_without_identity": skipped_without_identity,
    }


def build_name_variants(
    identities: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    results: list[dict[str, Any]],
    national_fed_rankings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    variants, _ = _build_name_variants_with_stats(identities, fencers, results, national_fed_rankings)
    return variants


def get_supabase_client():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(supabase_url, supabase_key)


def fetch_all(client, table: str, select_columns: str, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + page_size - 1
        result = client.table(table).select(select_columns).range(start, end).execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return rows


def fetch_results(client, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    try:
        return fetch_all(
            client,
            "fs_results",
            "id,fencer_id,fie_fencer_id,name,country,nationality",
            page_size=page_size,
        )
    except Exception:
        return fetch_all(
            client,
            "fs_results",
            "id,fencer_id,fie_fencer_id,name,nationality",
            page_size=page_size,
        )


def upsert_name_variants(client, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for i, start in enumerate(range(0, len(rows), batch_size)):
        batch = rows[start:start + batch_size]
        try:
            client.table("fs_fencer_name_variants").upsert(batch, on_conflict=NAME_VARIANT_CONFLICT).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  fs_fencer_name_variants upsert batch {i + 1} failed: {exc}")
    return written


def compute_name_variants(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    run_log = ScraperRunLogger(MODULE_NAME).start() if log_run else None
    try:
        client = client or get_supabase_client()
        identities = fetch_all(
            client,
            "fs_fencer_identities",
            "id,country,fie_ids,fs_fencer_row_ids",
            page_size=page_size,
        )
        fencers = fetch_all(client, "fs_fencers", "id,fie_id,name,country", page_size=page_size)
        results = fetch_results(client, page_size=page_size)
        national_fed_rankings = fetch_all(
            client,
            "fs_national_fed_rankings",
            "id,fencer_id,fie_id,name,country",
            page_size=page_size,
        )

        variants, stats = _build_name_variants_with_stats(identities, fencers, results, national_fed_rankings)
        valid_identity_ids = {str(identity["id"]) for identity in identities if identity.get("id")}
        variants = [v for v in variants if str(v.get("fencer_id", "")) in valid_identity_ids]
        written = upsert_name_variants(client, variants, batch_size=batch_size) if variants else 0
        report = {
            "identities_loaded": len(identities),
            "source_names_seen": stats["source_names_seen"],
            "variants_found": len(variants),
            "variants_written": written,
            "skipped_without_identity": stats["skipped_without_identity"],
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
                failed=max(len(variants) - written, 0),
                skipped=stats["skipped_without_identity"],
                metadata=report,
            )
        return report
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute fs_fencer_name_variants from identity-linked names.")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    print(f"Name variant computation starting - {datetime.now(UTC).isoformat()}")
    report = compute_name_variants(page_size=args.page_size, batch_size=args.batch_size)
    print(
        "Name variant computation complete - "
        f"variants={report['variants_written']}/{report['variants_found']}, "
        f"source_names={report['source_names_seen']}, "
        f"skipped_without_identity={report['skipped_without_identity']}"
    )


if __name__ == "__main__":
    main()

"""Cross-source fencer data reconciliation."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_logger import ScraperRunLogger
from scraper_state import set_state

MODULE_NAME = "reconcile_data"
PAGE_SIZE = 1000
SAMPLE_LIMIT = 25

FIE_SOURCES = {"fie", "fs_fencers"}
RESULT_SOURCE_METADATA_KEYS = {
    "olympedia": "olympedia_athlete_id",
}
NATIONAL_SOURCE_ALIASES = {
    "aus": "aus_fencing",
    "australia": "aus_fencing",
    "british": "british_fencing",
    "british_fencing": "british_fencing",
    "canada": "cff_canada",
    "canada_fencing": "cff_canada",
    "cff": "cff_canada",
    "china": "chn_fencing",
    "chn": "chn_fencing",
    "denmark": "den_fencing",
    "den": "den_fencing",
    "egypt": "egy_fencing",
    "egy": "egy_fencing",
    "france": "fff_france",
    "french_fencing": "fff_france",
    "fff": "fff_france",
    "germany": "dfb_germany",
    "dfb": "dfb_germany",
    "hong_kong": "hkg_fencing",
    "hkg": "hkg_fencing",
    "hungary": "hun_fencing",
    "hun": "hun_fencing",
    "israel": "isr_fencing",
    "isr": "isr_fencing",
    "italy": "fis_italy",
    "italian_fencing": "fis_italy",
    "fis": "fis_italy",
    "japan": "jpn_fencing",
    "jpn": "jpn_fencing",
    "new_zealand": "nzl_fencing",
    "nzl": "nzl_fencing",
    "poland": "pol_fencing",
    "pol": "pol_fencing",
    "romania": "rou_fencing",
    "rou": "rou_fencing",
    "russia": "rus_fencing",
    "rus": "rus_fencing",
    "spain": "esp_fencing",
    "esp": "esp_fencing",
    "sweden": "swe_fencing",
    "swe": "swe_fencing",
    "switzerland": "sui_fencing",
    "sui": "sui_fencing",
    "ukraine": "ukr_fencing",
    "ukr": "ukr_fencing",
}

COMPARE_FIELDS = ("name", "country", "weapon", "rank")


def _build_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(url, key)


def _clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def _normalized_text(value: Any) -> str | None:
    text = _clean_text(value)
    return text.lower() if text else None


def _normalized_source(source: str) -> str:
    return re.sub(r"\s+", "_", source.strip().lower())


def _source_filter_values(source: str) -> list[str]:
    normalized = _normalized_source(source)
    values = [normalized]
    alias = NATIONAL_SOURCE_ALIASES.get(normalized)
    if alias and alias not in values:
        values.append(alias)
    return values


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return None


def _jsonable_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _fetch_paginated(
    client: Any,
    table_name: str,
    select_columns: str,
    *,
    eq_filters: list[tuple[str, Any]] | None = None,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        query = client.table(table_name).select(select_columns)
        for column, value in eq_filters or []:
            query = query.eq(column, value)
        page = query.range(start, start + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def _fetch_fie_rows(client: Any, *, page_size: int) -> list[dict[str, Any]]:
    return _fetch_paginated(
        client,
        "fs_fencers",
        "id,fie_id,name,country,weapon,category,world_rank,fie_points,metadata",
        page_size=page_size,
    )


def _fetch_national_ranking_rows(client: Any, source: str, *, page_size: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for source_value in _source_filter_values(source):
        page_rows = _fetch_paginated(
            client,
            "fs_national_fed_rankings",
            "id,fencer_id,fie_id,name,country,weapon,category,gender,rank,points,source,season,metadata",
            eq_filters=[("source", source_value)],
            page_size=page_size,
        )
        for row in page_rows:
            row_id = _clean_text(row.get("id")) or json.dumps(row, sort_keys=True, default=str)
            if row_id in seen_ids:
                continue
            seen_ids.add(row_id)
            rows.append(row)
    return rows


def _fetch_result_rows(client: Any, source: str, *, page_size: int) -> list[dict[str, Any]]:
    try:
        rows = _fetch_paginated(
            client,
            "fs_results",
            "id,fencer_id,fie_fencer_id,name,country,nationality,weapon,rank,metadata",
            page_size=page_size,
        )
    except Exception as exc:
        if "country" not in str(exc).lower():
            raise
        rows = _fetch_paginated(
            client,
            "fs_results",
            "id,fencer_id,fie_fencer_id,name,nationality,weapon,rank,metadata",
            page_size=page_size,
        )

    metadata_key = RESULT_SOURCE_METADATA_KEYS[_normalized_source(source)]
    return [
        row
        for row in rows
        if _jsonable_metadata(row.get("metadata")).get(metadata_key)
        or _normalized_text(_jsonable_metadata(row.get("metadata")).get("source")) == _normalized_source(source)
    ]


def _fetch_source_rows(client: Any, source: str, *, page_size: int) -> tuple[str, list[dict[str, Any]]]:
    normalized = _normalized_source(source)
    if normalized in FIE_SOURCES:
        return "fs_fencers", _fetch_fie_rows(client, page_size=page_size)
    if normalized in RESULT_SOURCE_METADATA_KEYS:
        return "fs_results", _fetch_result_rows(client, source, page_size=page_size)
    return "fs_national_fed_rankings", _fetch_national_ranking_rows(client, source, page_size=page_size)


def _normalize_record(row: dict[str, Any], *, source: str, table_name: str) -> dict[str, Any]:
    rank = row.get("rank")
    if rank in (None, "") and table_name == "fs_fencers":
        rank = row.get("world_rank")

    return {
        "id": _clean_text(row.get("id")),
        "source": source,
        "source_table": table_name,
        "fencer_id": _clean_text(row.get("fencer_id")),
        "fie_id": _clean_text(row.get("fie_id") or row.get("fie_fencer_id")),
        "name": _clean_text(row.get("name")),
        "country": _clean_text(row.get("country") or row.get("nationality")),
        "weapon": _clean_text(row.get("weapon")),
        "category": _clean_text(row.get("category")),
        "gender": _clean_text(row.get("gender")),
        "rank": _to_int(rank),
        "points": row.get("points") if row.get("points") not in ("", None) else row.get("fie_points"),
    }


def _record_completeness(record: dict[str, Any]) -> tuple[int, int]:
    compared = sum(1 for field in COMPARE_FIELDS if record.get(field) not in (None, ""))
    identifiers = sum(1 for field in ("fie_id", "fencer_id", "id") if record.get(field))
    return compared, identifiers


def _dedupe_key(record: dict[str, Any]) -> tuple[Any, ...]:
    fie_id = _normalized_text(record.get("fie_id"))
    name = _normalized_text(record.get("name"))
    country = _normalized_text(record.get("country"))
    weapon = _normalized_text(record.get("weapon"))
    category = _normalized_text(record.get("category"))
    gender = _normalized_text(record.get("gender"))
    if fie_id:
        return ("fie_id", fie_id, weapon, category, gender)
    if name and country:
        return ("name_country", name, country, weapon, category, gender)
    return ("row_id", record.get("id"))


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    order: list[tuple[Any, ...]] = []
    for record in records:
        key = _dedupe_key(record)
        if key not in best_by_key:
            best_by_key[key] = record
            order.append(key)
            continue
        if _record_completeness(record) > _record_completeness(best_by_key[key]):
            best_by_key[key] = record
    return [best_by_key[key] for key in order]


def _fie_match_key(record: dict[str, Any]) -> str | None:
    fie_id = _normalized_text(record.get("fie_id"))
    return f"fie_id:{fie_id}" if fie_id else None


def _fallback_match_key(record: dict[str, Any]) -> str | None:
    name = _normalized_text(record.get("name"))
    country = _normalized_text(record.get("country"))
    if name and country:
        return f"name_country:{name}|{country}"
    return None


def _compatibility_score(source_a: dict[str, Any], source_b: dict[str, Any]) -> tuple[int, int, int]:
    score = 0
    for field in ("country", "weapon", "category", "gender"):
        left = _normalized_text(source_a.get(field))
        right = _normalized_text(source_b.get(field))
        if left and right and left == right:
            score += 2
    if source_a.get("rank") is not None and source_a.get("rank") == source_b.get("rank"):
        score += 2
    if _normalized_text(source_a.get("name")) == _normalized_text(source_b.get("name")):
        score += 1
    return score, *_record_completeness(source_a)


def _match_by_key(
    source_a: list[dict[str, Any]],
    source_b: list[dict[str, Any]],
    remaining_a: set[int],
    remaining_b: set[int],
    key_fn,
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    groups_a: dict[str, list[int]] = {}
    groups_b: dict[str, list[int]] = {}
    for index in sorted(remaining_a):
        key = key_fn(source_a[index])
        if key:
            groups_a.setdefault(key, []).append(index)
    for index in sorted(remaining_b):
        key = key_fn(source_b[index])
        if key:
            groups_b.setdefault(key, []).append(index)

    pairs: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for key in sorted(groups_a.keys() & groups_b.keys()):
        a_indices = list(groups_a[key])
        b_indices = list(groups_b[key])
        while a_indices and b_indices:
            best_pair = max(
                ((a_index, b_index) for a_index in a_indices for b_index in b_indices),
                key=lambda pair: _compatibility_score(source_a[pair[0]], source_b[pair[1]]),
            )
            a_index, b_index = best_pair
            pairs.append((key, source_a[a_index], source_b[b_index]))
            remaining_a.remove(a_index)
            remaining_b.remove(b_index)
            a_indices.remove(a_index)
            b_indices.remove(b_index)
    return pairs


def _match_records(
    source_a: list[dict[str, Any]],
    source_b: list[dict[str, Any]],
) -> tuple[list[tuple[str, dict[str, Any], dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    remaining_a = set(range(len(source_a)))
    remaining_b = set(range(len(source_b)))
    pairs: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    pairs.extend(_match_by_key(source_a, source_b, remaining_a, remaining_b, _fie_match_key))
    pairs.extend(_match_by_key(source_a, source_b, remaining_a, remaining_b, _fallback_match_key))
    return (
        pairs,
        [source_a[index] for index in sorted(remaining_a)],
        [source_b[index] for index in sorted(remaining_b)],
    )


def _values_differ(field: str, source_a: Any, source_b: Any) -> bool:
    if source_a in (None, "") or source_b in (None, ""):
        return False
    if field == "rank":
        return _to_int(source_a) != _to_int(source_b)
    return _normalized_text(source_a) != _normalized_text(source_b)


def _compare_records(source_a: dict[str, Any], source_b: dict[str, Any]) -> dict[str, dict[str, Any]]:
    differences: dict[str, dict[str, Any]] = {}
    for field in COMPARE_FIELDS:
        left = source_a.get(field)
        right = source_b.get(field)
        if _values_differ(field, left, right):
            differences[field] = {"source_a": left, "source_b": right}
    return differences


def _sample(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if value not in (None, "")}


def _summary_state(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_a": report["source_a"],
        "source_b": report["source_b"],
        "matched": report["matched"],
        "mismatched": report["mismatched"],
        "in_a_only": report["in_a_only"],
        "in_b_only": report["in_b_only"],
        "completed_at": report["generated_at"],
    }


def reconcile(
    source_a: str,
    source_b: str,
    *,
    client: Any | None = None,
    page_size: int = PAGE_SIZE,
    sample_limit: int = SAMPLE_LIMIT,
    log_run: bool = True,
    update_state: bool = True,
) -> dict:
    """Compare fencer data between two sources.

    Args:
        source_a: Name of first source (e.g., "FIE", "british_fencing", "olympedia").
        source_b: Name of second source.

    Returns:
        dict with keys: matched, mismatched, in_a_only, in_b_only, samples.
    """
    run_log = ScraperRunLogger(MODULE_NAME).start() if log_run else None
    try:
        supabase = client or _build_client()
        table_a, raw_a = _fetch_source_rows(supabase, source_a, page_size=page_size)
        table_b, raw_b = _fetch_source_rows(supabase, source_b, page_size=page_size)
        records_a = _dedupe_records(
            [_normalize_record(row, source=source_a, table_name=table_a) for row in raw_a]
        )
        records_b = _dedupe_records(
            [_normalize_record(row, source=source_b, table_name=table_b) for row in raw_b]
        )

        pairs, a_only, b_only = _match_records(records_a, records_b)
        matched_samples: list[dict[str, Any]] = []
        mismatched_samples: list[dict[str, Any]] = []

        for key, record_a, record_b in pairs:
            differences = _compare_records(record_a, record_b)
            pair_sample = {
                "key": key,
                "source_a": _sample(record_a),
                "source_b": _sample(record_b),
            }
            if differences:
                if len(mismatched_samples) < sample_limit:
                    mismatched_samples.append({**pair_sample, "differences": differences})
            elif len(matched_samples) < sample_limit:
                matched_samples.append(pair_sample)

        report = {
            "source_a": source_a,
            "source_b": source_b,
            "generated_at": datetime.now(UTC).isoformat(),
            "matched": len(pairs),
            "mismatched": sum(1 for _, record_a, record_b in pairs if _compare_records(record_a, record_b)),
            "in_a_only": len(a_only),
            "in_b_only": len(b_only),
            "samples": {
                "matched": matched_samples,
                "mismatched": mismatched_samples,
                "in_a_only": [_sample(record) for record in a_only[:sample_limit]],
                "in_b_only": [_sample(record) for record in b_only[:sample_limit]],
            },
        }

        state = _summary_state(report)
        if update_state:
            set_state(MODULE_NAME, "last_run", state)
        if run_log:
            run_log.complete(
                written=cast(int, report["matched"]),
                failed=cast(int, report["mismatched"]),
                skipped=cast(int, report["in_a_only"]) + cast(int, report["in_b_only"]),
                metadata=state,
            )
        return report
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def _print_report(report: dict[str, Any]) -> None:
    print(f"Reconciliation: {report['source_a']} vs {report['source_b']}")
    print(f"matched: {report['matched']}")
    print(f"mismatched: {report['mismatched']}")
    print(f"in_a_only: {report['in_a_only']}")
    print(f"in_b_only: {report['in_b_only']}")
    if report["samples"]["mismatched"]:
        print("Sample mismatches:")
        for sample in report["samples"]["mismatched"][:5]:
            fields = ", ".join(sorted(sample["differences"]))
            print(f"  {sample['key']}: {fields}")


def main(argv=None) -> int:
    """CLI entrypoint for cross-source reconciliation."""
    parser = argparse.ArgumentParser(
        description="Compare fencer data between two stored sources.",
    )
    parser.add_argument("--source-a", default=None, help="First source, e.g. FIE")
    parser.add_argument("--source-b", default=None, help="Second source, e.g. british_fencing")
    parser.add_argument("--output", help="Optional path to write the detailed JSON report")
    args = parser.parse_args(argv)

    if args.source_a is None or args.source_b is None:
        print("No --source-a / --source-b provided; skipping reconciliation.")
        return 0

    report = reconcile(args.source_a, args.source_b)
    _print_report(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

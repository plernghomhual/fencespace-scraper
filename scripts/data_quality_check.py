from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Callable

from supabase import create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


EXIT_HEALTHY = 0
EXIT_WARNING = 1
EXIT_CRITICAL = 2

STATE_SOURCE = "data_quality_check"
ORPHAN_STATE_KEY = "orphan_counts"
REFRESH_RPC = "refresh_data_quality_views"

VIEW_NAMES = (
    "v_fencer_source_coverage",
    "v_scraper_health",
    "v_orphan_results",
    "v_stale_sources",
)

EXPECTED_FENCER_SOURCES = (
    "fs_fencers",
    "fs_national_fed_rankings",
    "fs_results_linked",
)

StateGetter = Callable[[str, str], Any]
StateSetter = Callable[[str, str, Any], None]


def _build_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(url, key)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _fetch_view(client: Any, view_name: str) -> list[dict[str, Any]]:
    result = client.table(view_name).select("*").execute()
    return list(result.data or [])


def refresh_views(client: Any) -> None:
    client.rpc(REFRESH_RPC).execute()


def fetch_views(client: Any) -> dict[str, list[dict[str, Any]]]:
    return {view_name: _fetch_view(client, view_name) for view_name in VIEW_NAMES}


def _analyze_source_coverage(rows: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    counts = {
        str(row.get("source_name") or row.get("source") or ""): _to_int(row.get("fencer_count"))
        for row in rows
    }

    for source_name in EXPECTED_FENCER_SOURCES:
        if source_name not in counts:
            warnings.append(f"Missing source coverage row for {source_name}")
        elif counts[source_name] <= 0:
            warnings.append(f"Zero fencers reported for {source_name}")

    for source_name, fencer_count in sorted(counts.items()):
        if source_name and source_name not in EXPECTED_FENCER_SOURCES and fencer_count <= 0:
            warnings.append(f"Zero fencers reported for {source_name}")

    return warnings


def _module_set(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(row["module"])
        for row in rows
        if row.get("module") and str(row["module"]) != STATE_SOURCE
    }


def _analyze_stale_sources(
    health_rows: list[dict[str, Any]],
    stale_rows: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    criticals: list[str] = []
    health_modules = _module_set(health_rows)
    stale_modules = _module_set(stale_rows)

    if not health_modules:
        criticals.append("No scraper health rows found in the last 7 days")
        return warnings, criticals

    if stale_modules and health_modules.issubset(stale_modules):
        criticals.append("All scraper modules are stale")
        return warnings, criticals

    if stale_modules:
        warnings.append(f"Stale scraper modules: {', '.join(sorted(stale_modules))}")

    return warnings, criticals


def _current_orphan_counts(rows: list[dict[str, Any]]) -> tuple[int, dict[str, int]]:
    by_type: dict[str, int] = {}
    total = 0
    for row in rows:
        tournament_type = str(row.get("tournament_type") or "unknown")
        count = _to_int(row.get("orphan_count"))
        by_type[tournament_type] = count
        total += count
    return total, by_type


def _previous_orphan_counts(state: Any) -> tuple[int | None, dict[str, int]]:
    if state is None:
        return None, {}

    if not isinstance(state, dict):
        return _optional_int(state), {}

    total = _optional_int(state.get("total"))
    raw_by_type = (
        state.get("by_tournament_type")
        or state.get("counts_by_type")
        or state.get("counts")
        or {}
    )
    by_type: dict[str, int] = {}
    if isinstance(raw_by_type, dict):
        by_type = {
            str(tournament_type): count
            for tournament_type, raw_count in raw_by_type.items()
            if (count := _optional_int(raw_count)) is not None
        }

    if total is None and by_type:
        total = sum(by_type.values())

    return total, by_type


def _increase_warning(label: str, previous: int | None, current: int) -> str | None:
    if previous is None or current <= previous:
        return None
    if previous == 0:
        return f"Orphan results increased for {label}: 0 -> {current}"
    if (current - previous) / previous > 0.20:
        return f"Orphan results increased >20% for {label}: {previous} -> {current}"
    return None


def _analyze_orphans(
    rows: list[dict[str, Any]],
    previous_state: Any,
) -> tuple[list[str], dict[str, Any]]:
    warnings: list[str] = []
    current_total, current_by_type = _current_orphan_counts(rows)
    previous_total, previous_by_type = _previous_orphan_counts(previous_state)

    total_warning = _increase_warning("all tournament types", previous_total, current_total)
    if total_warning:
        warnings.append(total_warning)
    elif previous_total is None:
        for tournament_type, current_count in sorted(current_by_type.items()):
            type_warning = _increase_warning(
                tournament_type,
                previous_by_type.get(tournament_type),
                current_count,
            )
            if type_warning:
                warnings.append(type_warning)

    next_state = {
        "total": current_total,
        "by_tournament_type": current_by_type,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    return warnings, next_state


def _print_report(
    views: dict[str, list[dict[str, Any]]],
    warnings: list[str],
    criticals: list[str],
) -> None:
    print("Data quality report")
    for view_name in VIEW_NAMES:
        print(f"{view_name}: {len(views.get(view_name, []))} rows")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for critical in criticals:
        print(f"CRITICAL: {critical}")

    if criticals:
        print("Status: critical")
    elif warnings:
        print("Status: warnings")
    else:
        print("Status: healthy")


def run_check(
    *,
    client: Any | None = None,
    get_state_fn: StateGetter = get_state,
    set_state_fn: StateSetter = set_state,
    log_run: bool = True,
) -> int:
    run_log = ScraperRunLogger(STATE_SOURCE).start() if log_run else None
    warnings: list[str] = []
    criticals: list[str] = []

    try:
        supabase = client or _build_client()
        refresh_views(supabase)
    except Exception as exc:
        message = f"Failed to refresh materialized views: {exc}"
        print("Data quality report")
        print(f"CRITICAL: {message}")
        print("Status: critical")
        if run_log:
            run_log.error(message)
        return EXIT_CRITICAL

    try:
        views = fetch_views(supabase)
    except Exception as exc:
        message = f"Failed to read data quality views: {exc}"
        print("Data quality report")
        print(f"CRITICAL: {message}")
        print("Status: critical")
        if run_log:
            run_log.error(message)
        return EXIT_CRITICAL

    warnings.extend(_analyze_source_coverage(views["v_fencer_source_coverage"]))

    stale_warnings, stale_criticals = _analyze_stale_sources(
        views["v_scraper_health"],
        views["v_stale_sources"],
    )
    warnings.extend(stale_warnings)
    criticals.extend(stale_criticals)

    previous_orphan_state = get_state_fn(STATE_SOURCE, ORPHAN_STATE_KEY)
    orphan_warnings, next_orphan_state = _analyze_orphans(
        views["v_orphan_results"],
        previous_orphan_state,
    )
    warnings.extend(orphan_warnings)
    set_state_fn(STATE_SOURCE, ORPHAN_STATE_KEY, next_orphan_state)

    _print_report(views, warnings, criticals)

    if criticals:
        exit_code = EXIT_CRITICAL
    elif warnings:
        exit_code = EXIT_WARNING
    else:
        exit_code = EXIT_HEALTHY

    if run_log:
        run_log.complete(
            written=len(VIEW_NAMES),
            failed=1 if exit_code == EXIT_CRITICAL else 0,
            skipped=len(warnings),
            metadata={
                "warnings": warnings,
                "criticals": criticals,
                "exit_code": exit_code,
            },
        )

    return exit_code


def main() -> int:
    return run_check()


if __name__ == "__main__":
    raise SystemExit(main())

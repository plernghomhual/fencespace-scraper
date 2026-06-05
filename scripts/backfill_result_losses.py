#!/usr/bin/env python3
"""Backfill fs_results.defeats from reliable fs_bouts outcomes."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SOURCE = "backfill_result_losses"
PAGE_SIZE = 1000

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

RESULT_SELECTS = [
    (
        "id,tournament_id,fencer_id,fie_fencer_id,name,placement,rank,"
        "defeats,metadata,elimination_loss_metadata"
    ),
    "id,tournament_id,fencer_id,fie_fencer_id,name,placement,rank,metadata",
]
BOUT_SELECTS = [
    "id,tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,round",
]
TOURNAMENT_SELECTS = [
    "id,name,type,category,weapon,gender,event_type,is_individual,metadata",
    "id,name,type,category,weapon,gender,event_type,metadata",
    "id,name,type,category,weapon,gender,metadata",
    "id,name,type,metadata",
    "id,name",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def missing_column_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "column" in message
        or "schema cache" in message
        or "could not find" in message
        or "pgrst204" in message
    )


def fetch_all(supabase, table: str, select_columns: str, page_size: int = PAGE_SIZE):
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            supabase.table(table)
            .select(select_columns)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def fetch_all_with_fallbacks(supabase, table: str, select_options: list[str]):
    last_error: Exception | None = None
    for select_columns in select_options:
        try:
            return fetch_all(supabase, table, select_columns)
        except Exception as exc:
            if not missing_column_error(exc):
                raise
            last_error = exc
    if last_error:
        raise last_error
    return []


def fetch_results(supabase):
    return fetch_all_with_fallbacks(supabase, "fs_results", RESULT_SELECTS)


def fetch_bouts(supabase):
    return fetch_all_with_fallbacks(supabase, "fs_bouts", BOUT_SELECTS)


def fetch_tournaments(supabase):
    rows = fetch_all_with_fallbacks(supabase, "fs_tournaments", TOURNAMENT_SELECTS)
    return {str(row["id"]): row for row in rows if row.get("id") is not None}


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_id(value: Any) -> str | None:
    text = clean_text(value)
    return text if text and text.lower() not in {"none", "null"} else None


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def metadata_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def first_id(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = normalize_id(row.get(key))
        if value:
            return value
    return None


def fencer_identity(result: dict[str, Any]) -> str | None:
    return first_id(result, ("fencer_id", "fie_fencer_id"))


def bout_fencer_a(bout: dict[str, Any]) -> str | None:
    return first_id(bout, ("fencer_a", "fencer_a_id", "fencer_a_uuid"))


def bout_fencer_b(bout: dict[str, Any]) -> str | None:
    return first_id(bout, ("fencer_b", "fencer_b_id", "fencer_b_uuid"))


def bout_winner(bout: dict[str, Any]) -> str | None:
    return first_id(bout, ("winner", "winner_id", "winner_fencer_id"))


def reason_text(bout: dict[str, Any]) -> str:
    metadata = metadata_dict(bout.get("metadata"))
    values = [
        bout.get("decision"),
        bout.get("status"),
        bout.get("outcome"),
        metadata.get("decision"),
        metadata.get("status"),
        metadata.get("outcome"),
        metadata.get("result"),
        metadata.get("bout_status"),
        metadata.get("victory_type"),
    ]
    return " ".join(str(value) for value in values if value is not None).casefold()


def loss_reason(bout: dict[str, Any]) -> str:
    text = reason_text(bout)
    if re.search(r"\bdns\b|did not start", text):
        return "dns"
    if re.search(r"\bdq\b|disqual", text):
        return "dq"
    if "withdraw" in text or re.search(r"\bwd\b|\bwdr\b", text):
        return "withdrawal"
    if "forfeit" in text:
        return "forfeit"
    return "score"


def is_non_score_reason(reason: str) -> bool:
    return reason in {"dns", "dq", "withdrawal", "forfeit"}


def is_bye_bout(bout: dict[str, Any]) -> bool:
    metadata = metadata_dict(bout.get("metadata"))
    for key in ("is_bye", "isBye", "bye"):
        if truthy(bout.get(key)) or truthy(metadata.get(key)):
            return True
    text = reason_text(bout)
    return "bye" in text


def is_elimination_round(value: Any) -> bool:
    text = clean_text(value)
    if not text:
        return False
    lowered = text.casefold()
    if "pool" in lowered or "poule" in lowered:
        return False
    return bool(
        re.search(
            r"final|semi|quarter|table|tableau|direct|elimin|round of|last\s+\d+|\bt\s*\d+\b|\bde\b",
            lowered,
        )
    )


def is_team_event(tournament: dict[str, Any] | None) -> bool:
    if not tournament:
        return False
    metadata = metadata_dict(tournament.get("metadata"))
    if truthy(tournament.get("is_individual")) or truthy(metadata.get("is_individual")):
        return False
    for key in ("is_team_event", "team_event", "is_team"):
        if truthy(tournament.get(key)) or truthy(metadata.get(key)):
            return True
    text_parts = [
        tournament.get("event_type"),
        tournament.get("type"),
        tournament.get("category"),
        tournament.get("name"),
        metadata.get("event_type"),
        metadata.get("category"),
    ]
    text = " ".join(str(part) for part in text_parts if part is not None).casefold()
    return bool(re.search(r"(^|[\s_-])team($|[\s_-])|relay|squad", text))


def score_for_fencer(
    fencer_id: str,
    fencer_a: str | None,
    fencer_b: str | None,
    score_a: int | None,
    score_b: int | None,
) -> tuple[int | None, int | None]:
    if fencer_id == fencer_a:
        return score_a, score_b
    if fencer_id == fencer_b:
        return score_b, score_a
    return None, None


def classify_outcome(
    fencer_id: str,
    bout: dict[str, Any],
) -> tuple[str | None, str | None]:
    fencer_a = bout_fencer_a(bout)
    fencer_b = bout_fencer_b(bout)
    winner = bout_winner(bout)
    if fencer_id not in {fencer_a, fencer_b}:
        return None, None

    opponent = fencer_b if fencer_id == fencer_a else fencer_a
    if not opponent:
        return None, None

    if winner:
        if winner == fencer_id:
            return "win", "winner"
        if winner == opponent:
            return "loss", "winner"
        return None, None

    score_a = to_int(bout.get("score_a"))
    score_b = to_int(bout.get("score_b"))
    if score_a is None or score_b is None or score_a == score_b:
        return None, None
    score_for, score_against = score_for_fencer(fencer_id, fencer_a, fencer_b, score_a, score_b)
    if score_for is None or score_against is None:
        return None, None
    return ("loss", "score") if score_for < score_against else ("win", "score")


def make_loss_entry(
    fencer_id: str,
    bout: dict[str, Any],
    decision_source: str,
) -> dict[str, Any]:
    fencer_a = bout_fencer_a(bout)
    fencer_b = bout_fencer_b(bout)
    opponent = fencer_b if fencer_id == fencer_a else fencer_a
    score_a = to_int(bout.get("score_a"))
    score_b = to_int(bout.get("score_b"))
    score_for, score_against = score_for_fencer(fencer_id, fencer_a, fencer_b, score_a, score_b)
    return {
        "bout_id": bout.get("id"),
        "round": clean_text(bout.get("round")),
        "opponent_fencer_id": opponent,
        "score_for": score_for,
        "score_against": score_against,
        "loss_reason": loss_reason(bout),
        "decision_source": decision_source,
    }


def empty_counters() -> dict[str, int]:
    return {
        "decisive_bouts": 0,
        "loss_bouts": 0,
        "bye_bouts_skipped": 0,
        "missing_score_bouts": 0,
        "missing_participant_bouts_skipped": 0,
        "missing_outcome_bouts_skipped": 0,
        "non_score_losses": 0,
    }


def base_summary(results: list[dict[str, Any]], bouts: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "results_loaded": len(results),
        "bouts_loaded": len(bouts),
        "rows_to_update": 0,
        "updates_written": 0,
        "rows_without_identity_skipped": 0,
        "rows_without_bout_evidence_skipped": 0,
        "team_tournaments_skipped": 0,
        "team_result_rows_skipped": 0,
        "bye_bouts_skipped": 0,
        "missing_score_bouts": 0,
        "missing_participant_bouts_skipped": 0,
        "missing_outcome_bouts_skipped": 0,
        "non_score_losses": 0,
    }
    for bout in bouts:
        if is_bye_bout(bout):
            summary["bye_bouts_skipped"] += 1
            continue
        fencer_a = bout_fencer_a(bout)
        fencer_b = bout_fencer_b(bout)
        if not fencer_a or not fencer_b:
            summary["missing_participant_bouts_skipped"] += 1
            continue
        winner = bout_winner(bout)
        score_a = to_int(bout.get("score_a"))
        score_b = to_int(bout.get("score_b"))
        if winner and (score_a is None or score_b is None):
            summary["missing_score_bouts"] += 1
            if is_non_score_reason(loss_reason(bout)):
                summary["non_score_losses"] += 1
        elif not winner and (score_a is None or score_b is None or score_a == score_b):
            summary["missing_outcome_bouts_skipped"] += 1
    return summary


def build_update(result: dict[str, Any], values: dict[str, Any]) -> dict[str, Any] | None:
    if result.get("id"):
        return {"filters": {"id": result["id"]}, "values": values}
    tournament_id = result.get("tournament_id")
    fencer_id = result.get("fencer_id")
    if tournament_id and fencer_id:
        return {"filters": {"tournament_id": tournament_id, "fencer_id": fencer_id}, "values": values}
    if tournament_id and result.get("name"):
        return {"filters": {"tournament_id": tournament_id, "name": result["name"]}, "values": values}
    return None


def build_result_loss_updates(
    results: list[dict[str, Any]],
    bouts: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    summary = base_summary(results, bouts)
    bouts_by_tournament: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bout in bouts:
        if bout.get("tournament_id") is not None:
            bouts_by_tournament[str(bout["tournament_id"])].append(bout)

    team_tournament_ids = {
        tournament_id
        for tournament_id, tournament in tournaments.items()
        if is_team_event(tournament)
    }
    summary["team_tournaments_skipped"] = len(team_tournament_ids)

    updates: list[dict[str, Any]] = []
    for result in results:
        tournament_id = normalize_id(result.get("tournament_id"))
        if tournament_id in team_tournament_ids:
            summary["team_result_rows_skipped"] += 1
            continue

        fencer_id = fencer_identity(result)
        if not fencer_id:
            summary["rows_without_identity_skipped"] += 1
            continue

        counters = empty_counters()
        losses: list[dict[str, Any]] = []
        elimination_losses: list[dict[str, Any]] = []
        for bout in bouts_by_tournament.get(tournament_id or "", []):
            fencer_a = bout_fencer_a(bout)
            fencer_b = bout_fencer_b(bout)
            if fencer_id not in {fencer_a, fencer_b}:
                continue
            if is_bye_bout(bout):
                counters["bye_bouts_skipped"] += 1
                continue
            if not fencer_a or not fencer_b:
                counters["missing_participant_bouts_skipped"] += 1
                continue

            score_a = to_int(bout.get("score_a"))
            score_b = to_int(bout.get("score_b"))
            if score_a is None or score_b is None:
                counters["missing_score_bouts"] += 1

            outcome, decision_source = classify_outcome(fencer_id, bout)
            if outcome is None or decision_source is None:
                counters["missing_outcome_bouts_skipped"] += 1
                continue

            counters["decisive_bouts"] += 1
            if outcome != "loss":
                continue

            counters["loss_bouts"] += 1
            entry = make_loss_entry(fencer_id, bout, decision_source)
            losses.append(entry)
            if is_non_score_reason(entry["loss_reason"]):
                counters["non_score_losses"] += 1
            if is_elimination_round(bout.get("round")):
                elimination_losses.append(entry)

        if counters["decisive_bouts"] == 0:
            summary["rows_without_bout_evidence_skipped"] += 1
            continue

        metadata = {
            "source": SOURCE,
            "evidence": "fs_bouts",
            "defeats": counters["loss_bouts"],
            "placement": to_int(result.get("placement")) or to_int(result.get("rank")),
            "loss_bout_ids": [entry["bout_id"] for entry in losses if entry.get("bout_id")],
            "backfill_counters": counters,
        }
        if elimination_losses:
            metadata["elimination_loss"] = elimination_losses[-1]

        update = build_update(
            result,
            {
                "defeats": counters["loss_bouts"],
                "elimination_loss_metadata": metadata,
            },
        )
        if not update:
            summary["rows_without_identity_skipped"] += 1
            continue
        updates.append(update)

    summary["rows_to_update"] = len(updates)
    return updates, summary


def apply_result_updates(supabase, updates: list[dict[str, Any]]) -> int:
    payload = []
    for update in updates:
        filters = update["filters"]
        values = update["values"]
        row = {
            key: filters[key]
            for key in ("id", "tournament_id", "fencer_id", "name")
            if filters.get(key) is not None
        }
        row.update(
            {
                "defeats": values.get("defeats"),
                "elimination_loss_metadata": values.get("elimination_loss_metadata"),
            }
        )
        payload.append(row)
    if not payload:
        return 0
    supabase.rpc("fs_bulk_update_result_losses", {"p_updates": payload}).execute()
    return len(payload)


def backfill_result_losses(supabase, *, dry_run: bool = False) -> dict[str, int]:
    results = fetch_results(supabase)
    bouts = fetch_bouts(supabase)
    tournaments = fetch_tournaments(supabase)
    updates, summary = build_result_loss_updates(results, bouts, tournaments)
    if not dry_run and updates:
        summary["updates_written"] = apply_result_updates(supabase, updates)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="compute updates and counters without writing fs_results",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous result-loss backfill state: {previous_state}")

        supabase = get_supabase_client()
        summary = backfill_result_losses(supabase, dry_run=args.dry_run)
        set_state(SOURCE, "last_run", {**summary, "dry_run": args.dry_run, "updated_at": utc_now()})
        run_log.complete(
            written=summary["updates_written"],
            failed=0,
            skipped=summary["rows_without_bout_evidence_skipped"]
            + summary["team_result_rows_skipped"]
            + summary["rows_without_identity_skipped"],
            metadata={**summary, "dry_run": args.dry_run},
        )
        print(
            "Result-loss backfill complete: "
            f"{summary['updates_written']} rows written, "
            f"{summary['rows_to_update']} rows eligible, "
            f"{summary['rows_without_bout_evidence_skipped']} rows skipped without bout evidence"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

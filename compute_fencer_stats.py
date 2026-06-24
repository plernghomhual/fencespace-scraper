#!/usr/bin/env python3
"""Compute per-fencer bout stats from fs_bouts."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_fencer_stats"

BOUT_SELECT = "id,tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,round"
TOURNAMENT_SELECT = "id,weapon,gender,category,end_date,start_date"
IDENTITY_SELECTS = (
    "canonical_id,fs_fencer_row_ids",
    "id,canonical_id,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
    "canonical_id,fencer_ids",
)
SKIP_COUNTERS = (
    "skipped_missing_fencer",
    "skipped_missing_score",
    "skipped_missing_dimensions",
    "skipped_self_bout",
    "skipped_no_winner",
)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold()
    if key in {"e", "epee", "épée"}:
        return "Epee"
    if key in {"f", "foil"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return text.title()


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold().replace(".", "")
    if key in {"f", "female", "women", "woman", "womens", "women's"}:
        return "Women's"
    if key in {"m", "male", "men", "man", "mens", "men's"}:
        return "Men's"
    return text.title()


def normalize_category(category: Any, gender: Any = None) -> str | None:
    category_text = clean_text(category)
    if not category_text:
        return None
    category_label = category_text if "'" in category_text else category_text.title()
    gender_label = normalize_gender(gender)
    if not gender_label:
        return category_label
    if category_label.casefold().startswith(gender_label.casefold()):
        return category_label
    return f"{gender_label} {category_label}"


def normalize_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = clean_text(value)
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def fetch_all(client, table: str, columns: str, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table(table)
            .select(columns)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def parse_identity_members(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if clean_text(item)})


def build_identity_map(identity_rows: list[dict[str, Any]]) -> dict[str, str]:
    identity_map: dict[str, str] = {}
    for row in identity_rows:
        members = parse_identity_members(
            row.get("fs_fencer_row_ids")
            or row.get("fencer_ids")
            or row.get("source_fencer_ids")
        )
        identity_id = clean_text(row.get("id")) or clean_text(row.get("canonical_id"))
        if not identity_id and members:
            identity_id = members[0]
        if not identity_id:
            continue

        identity_map[identity_id] = identity_id
        for member in members:
            identity_map[member] = identity_id
    return identity_map


def load_identity_map(client, page_size: int = PAGE_SIZE) -> tuple[dict[str, str], int]:
    last_error: Exception | None = None
    for columns in IDENTITY_SELECTS:
        try:
            rows = fetch_all(client, "fs_fencer_identities", columns, page_size=page_size)
            return build_identity_map(rows), len(rows)
        except Exception as exc:
            last_error = exc
    print(f"Identity table unavailable; using raw fs_bouts fencer grouping: {last_error}")
    return {}, 0


def canonical_fencer_id(fencer_id: Any, identity_map: dict[str, str] | None) -> str | None:
    text = clean_text(fencer_id)
    if not text:
        return None
    if identity_map:
        return identity_map.get(text, text)
    return text


def tournament_lookup(tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def raw_fencer_id(bout: dict[str, Any], side: str) -> Any:
    if side == "a":
        return bout.get("fencer_a_id")
    return bout.get("fencer_b_id")


def bout_dimensions(
    bout: dict[str, Any],
    tournaments: dict[str, dict[str, Any]],
) -> tuple[str | None, str | None]:
    tournament_id = clean_text(bout.get("tournament_id"))
    tournament = tournaments.get(tournament_id) if tournament_id else None
    source = tournament or {}

    weapon = normalize_weapon(bout.get("weapon")) or normalize_weapon(source.get("weapon"))
    category = normalize_category(
        bout.get("category") if bout.get("category") is not None else source.get("category"),
        bout.get("gender") if bout.get("gender") is not None else source.get("gender"),
    )
    return weapon, category


def bout_date(bout: dict[str, Any], tournaments: dict[str, dict[str, Any]]) -> str | None:
    for key in ("bout_date", "meeting_date", "date", "played_at", "completed_at"):
        value = normalize_date(bout.get(key))
        if value:
            return value

    tournament_id = clean_text(bout.get("tournament_id"))
    tournament = tournaments.get(tournament_id) if tournament_id else None
    if not tournament:
        return None
    for key in ("end_date", "date", "start_date"):
        value = normalize_date(tournament.get(key))
        if value:
            return value
    return None


def empty_counters(bouts_read: int = 0) -> dict[str, int]:
    return {
        "bouts_read": bouts_read,
        "completed_bouts": 0,
        "rows_built": 0,
        **{key: 0 for key in SKIP_COUNTERS},
    }


def new_stat(identity_id: str, weapon: str, category: str) -> dict[str, Any]:
    return {
        "identity_id": identity_id,
        "weapon": weapon,
        "category": category,
        "total_bouts": 0,
        "wins": 0,
        "losses": 0,
        "touches_scored": 0,
        "touches_received": 0,
        "events": [],
    }


def winner_for_bout(
    bout: dict[str, Any],
    fencer_a: str,
    fencer_b: str,
    score_a: int,
    score_b: int,
    identity_map: dict[str, str] | None,
) -> str | None:
    winner = canonical_fencer_id(bout.get("winner_id"), identity_map)
    if winner in {fencer_a, fencer_b}:
        return winner
    if score_a == score_b:
        return None
    return fencer_a if score_a > score_b else fencer_b


def add_fencer_event(
    stat: dict[str, Any],
    *,
    won: bool,
    touches_scored: int,
    touches_received: int,
    date_value: str | None,
    sort_id: str,
) -> None:
    stat["total_bouts"] += 1
    if won:
        stat["wins"] += 1
    else:
        stat["losses"] += 1
    stat["touches_scored"] += touches_scored
    stat["touches_received"] += touches_received
    stat["events"].append(
        {
            "won": won,
            "date": date_value,
            "sort_id": sort_id,
        }
    )


def streaks(events: list[dict[str, Any]]) -> tuple[int, int, str | None]:
    current_streak = 0
    longest_win_streak = 0
    last_bout_at = None

    for event in sorted(events, key=lambda item: (item.get("date") or "", item.get("sort_id") or "")):
        if event["won"]:
            current_streak = current_streak + 1 if current_streak > 0 else 1
            longest_win_streak = max(longest_win_streak, current_streak)
        else:
            current_streak = current_streak - 1 if current_streak < 0 else -1
        if event.get("date"):
            last_bout_at = event["date"]

    return current_streak, longest_win_streak, last_bout_at


def build_fencer_stat_rows(
    bouts: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    identity_map: dict[str, str] | None = None,
    now: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    tournaments_by_id = tournament_lookup(tournaments)
    counters = empty_counters(len(bouts))
    stats: dict[tuple[str, str, str], dict[str, Any]] = {}
    updated_at = now or datetime.now(UTC).isoformat()

    for index, bout in enumerate(bouts):
        fencer_a = canonical_fencer_id(raw_fencer_id(bout, "a"), identity_map)
        fencer_b = canonical_fencer_id(raw_fencer_id(bout, "b"), identity_map)
        if not fencer_a or not fencer_b:
            counters["skipped_missing_fencer"] += 1
            continue
        if fencer_a == fencer_b:
            counters["skipped_self_bout"] += 1
            continue

        score_a = to_int(bout.get("score_a"))
        score_b = to_int(bout.get("score_b"))
        if score_a is None or score_b is None:
            counters["skipped_missing_score"] += 1
            continue

        weapon, category = bout_dimensions(bout, tournaments_by_id)
        if not weapon or not category:
            counters["skipped_missing_dimensions"] += 1
            continue

        winner = winner_for_bout(bout, fencer_a, fencer_b, score_a, score_b, identity_map)
        if not winner:
            counters["skipped_no_winner"] += 1
            continue

        current_date = bout_date(bout, tournaments_by_id)
        sort_id = clean_text(bout.get("id")) or f"bout:{index}"
        a_key = (fencer_a, weapon, category)
        b_key = (fencer_b, weapon, category)
        a_stat = stats.setdefault(a_key, new_stat(fencer_a, weapon, category))
        b_stat = stats.setdefault(b_key, new_stat(fencer_b, weapon, category))

        add_fencer_event(
            a_stat,
            won=winner == fencer_a,
            touches_scored=score_a,
            touches_received=score_b,
            date_value=current_date,
            sort_id=sort_id,
        )
        add_fencer_event(
            b_stat,
            won=winner == fencer_b,
            touches_scored=score_b,
            touches_received=score_a,
            date_value=current_date,
            sort_id=sort_id,
        )
        counters["completed_bouts"] += 1

    rows: list[dict[str, Any]] = []
    for key in sorted(stats):
        stat = stats[key]
        current_streak, longest_win_streak, last_bout_at = streaks(stat["events"])
        total_bouts = stat["total_bouts"]
        rows.append(
            {
                "identity_id": stat["identity_id"],
                "weapon": stat["weapon"],
                "category": stat["category"],
                "total_bouts": total_bouts,
                "wins": stat["wins"],
                "losses": stat["losses"],
                "touches_scored": stat["touches_scored"],
                "touches_received": stat["touches_received"],
                "win_pct": round((stat["wins"] / total_bouts) * 100, 2) if total_bouts else 0.0,
                "current_streak": current_streak,
                "longest_win_streak": longest_win_streak,
                "last_bout_at": last_bout_at,
                "updated_at": updated_at,
            }
        )

    counters["rows_built"] = len(rows)
    return rows, counters


def batch_upsert_fencer_stats(client, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = [
            {key: value for key, value in row.items() if key != "win_pct"}
            for row in rows[index : index + batch_size]
        ]
        client.table("fs_fencer_stats").upsert(
            batch,
            on_conflict="identity_id,weapon,category",
        ).execute()
        written += len(batch)
    return written


def no_credentials_summary() -> dict[str, int]:
    return {
        **empty_counters(),
        "stats_rows": 0,
        "written": 0,
        "identity_rows": 0,
        "skipped_no_credentials": 1,
    }


def compute_fencer_stats(
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    now: str | None = None,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        if client is None and (not SUPABASE_URL or not SUPABASE_KEY):
            summary = no_credentials_summary()
            if run_log:
                run_log.complete(written=0, failed=0, skipped=1, metadata=summary)
            return summary

        client = client or get_supabase_client()
        bouts = fetch_all(client, "fs_bouts", BOUT_SELECT, page_size=page_size)
        tournaments = fetch_all(client, "fs_tournaments", TOURNAMENT_SELECT, page_size=page_size)
        identity_map, identity_rows = load_identity_map(client, page_size=page_size)
        rows, counters = build_fencer_stat_rows(
            bouts,
            tournaments,
            identity_map=identity_map,
            now=now,
        )
        written = batch_upsert_fencer_stats(client, rows, batch_size=batch_size) if rows else 0
        skipped = sum(counters[key] for key in SKIP_COUNTERS)
        summary = {
            **counters,
            "stats_rows": len(rows),
            "written": written,
            "identity_rows": identity_rows,
        }

        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )
        if run_log:
            run_log.complete(written=written, failed=0, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous fencer stats state: {previous_state}")

    summary = compute_fencer_stats()
    if summary.get("skipped_no_credentials"):
        print("Fencer stats computation skipped: SUPABASE_URL and SUPABASE_SERVICE_KEY are not set.")
        return
    print(
        "Fencer stats computation complete: "
        f"{summary['stats_rows']} rows built, "
        f"{summary['written']} rows written, "
        f"{sum(summary[key] for key in SKIP_COUNTERS)} bouts skipped"
    )


if __name__ == "__main__":
    main()

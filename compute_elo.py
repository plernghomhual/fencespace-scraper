from __future__ import annotations

import argparse
import json
import math
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_elo"
ELO_VERSION = 1
STARTING_RATING = 1500.0

BOUT_SELECTS = (
    "id,tournament_id,fencer_a,fencer_b,fencer_a_id,fencer_b_id,winner,winner_id,"
    "score_a,score_b,weapon,category,bout_date,meeting_date,date,played_at,round,metadata",
    "id,tournament_id,fencer_a,fencer_b,winner,winner_id,score_a,score_b,weapon,category,metadata",
    "id,tournament_id,fencer_a,fencer_b,score_a,score_b,weapon",
    "id,tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b",
)
TOURNAMENT_SELECTS = (
    "id,weapon,category,level,tier,competition_tier,end_date,start_date,date,status,"
    "has_results,team,is_team,is_individual,type,event_type,gender,metadata",
    "id,weapon,category,end_date,start_date,date,status,has_results,team,is_team,is_individual",
    "id,weapon,category,end_date",
)
IDENTITY_SELECTS = (
    "id,canonical_id,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
    "id,canonical_id,fencer_ids",
)

WEAPON_MAP = {
    "s": "Sabre",
    "sabre": "Sabre",
    "saber": "Sabre",
    "e": "Epee",
    "epee": "Epee",
    "epée": "Epee",
    "f": "Foil",
    "foil": "Foil",
}
CATEGORY_MAP = {
    "senior": "Senior",
    "junior": "Junior",
    "cadet": "Cadet",
    "veteran": "Veteran",
    "veterans": "Veteran",
    "u23": "U23",
    "u_23": "U23",
    "under_23": "U23",
}

# Defaults favor higher K for elite open events, lower K for developmental,
# veteran, local, and college contexts where volatility should be damped.
DEFAULT_K_BY_TIER = {
    "olympic": 48,
    "olympics": 48,
    "world_championship": 48,
    "world_championships": 48,
    "grand_prix": 40,
    "world_cup": 40,
    "zonal": 36,
    "continental": 36,
    "satellite": 32,
    "national": 24,
    "ncaa": 24,
    "college": 24,
    "regional": 20,
    "local": 16,
}
DEFAULT_K_BY_CATEGORY = {
    "senior": 32,
    "u23": 28,
    "u_23": 28,
    "junior": 28,
    "cadet": 24,
    "veteran": 24,
    "veterans": 24,
}

INCOMPLETE_STATUSES = {
    "scheduled",
    "pending",
    "upcoming",
    "cancelled",
    "canceled",
    "in_progress",
    "running",
    "open",
}


@dataclass
class KFactorConfig:
    default: int = 32
    by_tier: dict[str, int] = field(default_factory=lambda: DEFAULT_K_BY_TIER.copy())
    by_category: dict[str, int] = field(
        default_factory=lambda: DEFAULT_K_BY_CATEGORY.copy()
    )


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_key(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")
    return key or None


def normalize_uuid(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return str(uuid.UUID(text))
    except (TypeError, ValueError):
        return None


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = clean_text(value)
    return bool(text and text.casefold() in {"1", "true", "t", "yes", "y"})


def falsey(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    text = clean_text(value)
    return bool(text and text.casefold() in {"0", "false", "f", "no", "n"})


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def parse_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [value]
    return value if isinstance(value, list) else []


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


def round_rating(value: float) -> float:
    return float(
        Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def fetch_all(
    client,
    table: str,
    columns: str,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
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


def fetch_with_fallback(
    client, table: str, column_sets: Iterable[str], page_size: int = PAGE_SIZE
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in column_sets:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def fetch_bouts(client, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    return fetch_with_fallback(client, "fs_bouts", BOUT_SELECTS, page_size=page_size)


def fetch_tournaments(client, page_size: int = PAGE_SIZE) -> dict[str, dict[str, Any]]:
    rows = fetch_with_fallback(
        client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size
    )
    return {str(row["id"]): row for row in rows if row.get("id") is not None}


def load_identity_rows(client, page_size: int = PAGE_SIZE) -> tuple[list[dict[str, Any]], int]:
    try:
        rows = fetch_with_fallback(
            client, "fs_fencer_identities", IDENTITY_SELECTS, page_size=page_size
        )
    except Exception:
        return [], 0
    return rows, len(rows)


def build_identity_indexes(
    identity_rows: list[dict[str, Any]] | None,
) -> tuple[dict[str, str], dict[str, str]]:
    canonical_by_member: dict[str, str] = {}
    identity_by_canonical: dict[str, str] = {}

    for row in identity_rows or []:
        members = [
            member
            for member in (
                normalize_uuid(item)
                for item in parse_list(
                    row.get("fs_fencer_row_ids")
                    or row.get("fencer_ids")
                    or row.get("source_fencer_ids")
                )
            )
            if member
        ]
        canonical = normalize_uuid(row.get("canonical_id"))
        if not canonical and members:
            canonical = sorted(set(members))[0]
        if not canonical:
            continue

        identity_id = normalize_uuid(row.get("id"))
        canonical_by_member[canonical] = canonical
        if identity_id:
            identity_by_canonical[canonical] = identity_id
        for member in members:
            canonical_by_member[member] = canonical

    return canonical_by_member, identity_by_canonical


def canonical_fencer_id(
    fencer_id: Any, canonical_by_member: dict[str, str] | None = None
) -> str | None:
    row_id = normalize_uuid(fencer_id)
    if not row_id:
        return None
    return (canonical_by_member or {}).get(row_id, row_id)


def first_value(*values: Any) -> Any:
    for value in values:
        if clean_text(value):
            return value
    return None


def normalize_weapon(*values: Any) -> str | None:
    for value in values:
        key = normalize_key(value)
        if key:
            return WEAPON_MAP.get(key, clean_text(value).title())
    return None


def normalize_category(*values: Any) -> str:
    for value in values:
        key = normalize_key(value)
        if key:
            return CATEGORY_MAP.get(key, clean_text(value).title())
    return "Open"


def bout_date(
    bout: dict[str, Any],
    tournament: dict[str, Any],
    metadata: dict[str, Any],
) -> str | None:
    for source in (bout, metadata, tournament):
        for key in ("bout_date", "meeting_date", "date", "played_at", "end_date", "start_date"):
            value = normalize_date(source.get(key))
            if value:
                return value
    return None


def is_completed_event(
    bout: dict[str, Any], tournament: dict[str, Any], metadata: dict[str, Any]
) -> bool:
    for source in (bout, metadata, tournament):
        if falsey(source.get("has_results")):
            return False
    status = first_value(
        bout.get("status"),
        metadata.get("status"),
        tournament.get("status"),
    )
    status_key = normalize_key(status)
    return status_key not in INCOMPLETE_STATUSES


def is_team_event(
    bout: dict[str, Any], tournament: dict[str, Any], metadata: dict[str, Any]
) -> bool:
    for source in (tournament, bout, metadata):
        for key in ("team", "is_team", "team_event", "is_team_event"):
            if truthy(source.get(key)):
                return True
        if falsey(source.get("is_individual")):
            return True

    for source in (tournament, bout, metadata):
        for key in ("type", "event_type"):
            text = clean_text(source.get(key))
            if text and re.search(r"\bteam\b", text, flags=re.I):
                return True
    return False


def bout_duplicate_key(
    bout: dict[str, Any],
    metadata: dict[str, Any],
    fencer_a: str | None,
    fencer_b: str | None,
    bout_at: str | None,
) -> str:
    bout_id = clean_text(bout.get("id"))
    if bout_id:
        return f"id:{bout_id}"

    source_key = clean_text(metadata.get("source_key"))
    tournament_id = clean_text(bout.get("tournament_id"))
    if source_key and tournament_id:
        return f"source:{tournament_id}:{source_key}"

    parts = (
        tournament_id,
        fencer_a,
        fencer_b,
        clean_text(bout.get("score_a")),
        clean_text(bout.get("score_b")),
        bout_at,
        clean_text(bout.get("round")),
    )
    return "fallback:" + "|".join(part or "" for part in parts)


def k_factor_for(
    tournament: dict[str, Any],
    bout: dict[str, Any],
    config: KFactorConfig | None = None,
) -> int:
    config = config or KFactorConfig()
    metadata = parse_json_object(bout.get("metadata"))
    tier_lookup = {normalize_key(key): value for key, value in config.by_tier.items()}
    category_lookup = {
        normalize_key(key): value for key, value in config.by_category.items()
    }

    for value in (
        bout.get("competition_tier"),
        bout.get("tier"),
        bout.get("level"),
        metadata.get("competition_tier"),
        metadata.get("tier"),
        metadata.get("level"),
        tournament.get("competition_tier"),
        tournament.get("tier"),
        tournament.get("level"),
        tournament.get("type"),
    ):
        key = normalize_key(value)
        if key in tier_lookup:
            return tier_lookup[key]

    for value in (
        bout.get("category"),
        metadata.get("category"),
        tournament.get("category"),
    ):
        key = normalize_key(value)
        if key in category_lookup:
            return category_lookup[key]

    return config.default


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))


def build_elo_rows(
    bouts: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    identity_rows: list[dict[str, Any]] | None = None,
    k_config: KFactorConfig | None = None,
    now: str | None = None,
    version: int = ELO_VERSION,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if isinstance(tournaments, list):
        tournaments_by_id = {
            str(row["id"]): row for row in tournaments if row.get("id") is not None
        }
    else:
        tournaments_by_id = tournaments

    updated_at = now or datetime.now(timezone.utc).isoformat()
    canonical_by_member, identity_by_canonical = build_identity_indexes(identity_rows)
    seen_bouts: set[str] = set()
    normalized_bouts: list[dict[str, Any]] = []
    summary = {
        "bouts_read": len(bouts),
        "bouts_used": 0,
        "rows_computed": 0,
        "skipped": 0,
        "skipped_duplicate_bouts": 0,
        "skipped_null_scores": 0,
        "skipped_missing_fencers": 0,
        "skipped_team_events": 0,
        "skipped_incomplete_events": 0,
        "skipped_missing_context": 0,
        "skipped_tied_scores": 0,
    }

    for bout in bouts:
        metadata = parse_json_object(bout.get("metadata"))
        tournament_id = clean_text(bout.get("tournament_id"))
        tournament = tournaments_by_id.get(str(tournament_id), {}) if tournament_id else {}

        raw_a = first_value(
            bout.get("fencer_a"),
            bout.get("fencer_a_id"),
            metadata.get("fencer_a"),
            metadata.get("fencer_a_id"),
        )
        raw_b = first_value(
            bout.get("fencer_b"),
            bout.get("fencer_b_id"),
            metadata.get("fencer_b"),
            metadata.get("fencer_b_id"),
        )
        fencer_a = canonical_fencer_id(raw_a, canonical_by_member)
        fencer_b = canonical_fencer_id(raw_b, canonical_by_member)
        score_a = to_int(bout.get("score_a"))
        score_b = to_int(bout.get("score_b"))
        bout_at = bout_date(bout, tournament, metadata)
        duplicate_key = bout_duplicate_key(bout, metadata, fencer_a, fencer_b, bout_at)

        if duplicate_key in seen_bouts:
            summary["skipped_duplicate_bouts"] += 1
            continue
        seen_bouts.add(duplicate_key)

        if score_a is None or score_b is None:
            summary["skipped_null_scores"] += 1
            continue
        if not fencer_a or not fencer_b or fencer_a == fencer_b:
            summary["skipped_missing_fencers"] += 1
            continue
        if is_team_event(bout, tournament, metadata):
            summary["skipped_team_events"] += 1
            continue
        if not is_completed_event(bout, tournament, metadata):
            summary["skipped_incomplete_events"] += 1
            continue
        if score_a == score_b:
            summary["skipped_tied_scores"] += 1
            continue

        weapon = normalize_weapon(
            bout.get("weapon"), metadata.get("weapon"), tournament.get("weapon")
        )
        category = normalize_category(
            bout.get("category"), metadata.get("category"), tournament.get("category")
        )
        if not weapon or not bout_at:
            summary["skipped_missing_context"] += 1
            continue

        normalized_bouts.append(
            {
                "sort_key": (
                    bout_at,
                    tournament_id or "",
                    clean_text(bout.get("round")) or "",
                    duplicate_key,
                ),
                "date": bout_at,
                "fencer_a": fencer_a,
                "fencer_b": fencer_b,
                "score_a": score_a,
                "score_b": score_b,
                "weapon": weapon,
                "category": category,
                "tournament": tournament,
                "bout": bout,
            }
        )

    ratings: dict[tuple[str, str, str], dict[str, Any]] = {}
    for bout in sorted(normalized_bouts, key=lambda item: item["sort_key"]):
        key_a = (bout["fencer_a"], bout["weapon"], bout["category"])
        key_b = (bout["fencer_b"], bout["weapon"], bout["category"])
        state_a = ratings.setdefault(
            key_a,
            {
                "rating": STARTING_RATING,
                "games": 0,
                "peak_rating": STARTING_RATING,
                "last_bout_at": None,
            },
        )
        state_b = ratings.setdefault(
            key_b,
            {
                "rating": STARTING_RATING,
                "games": 0,
                "peak_rating": STARTING_RATING,
                "last_bout_at": None,
            },
        )

        rating_a = state_a["rating"]
        rating_b = state_b["rating"]
        actual_a = 1.0 if bout["score_a"] > bout["score_b"] else 0.0
        actual_b = 1.0 - actual_a
        expected_a = expected_score(rating_a, rating_b)
        expected_b = 1.0 - expected_a
        k_factor = k_factor_for(bout["tournament"], bout["bout"], k_config)

        state_a["rating"] = rating_a + k_factor * (actual_a - expected_a)
        state_b["rating"] = rating_b + k_factor * (actual_b - expected_b)
        state_a["games"] += 1
        state_b["games"] += 1
        state_a["peak_rating"] = max(state_a["peak_rating"], state_a["rating"])
        state_b["peak_rating"] = max(state_b["peak_rating"], state_b["rating"])
        state_a["last_bout_at"] = bout["date"]
        state_b["last_bout_at"] = bout["date"]

    rows: list[dict[str, Any]] = []
    for (fencer_id, weapon, category), state in sorted(ratings.items()):
        rows.append(
            {
                "fencer_id": fencer_id,
                "identity_id": identity_by_canonical.get(fencer_id),
                "weapon": weapon,
                "category": category,
                "rating": round_rating(state["rating"]),
                "games": state["games"],
                "peak_rating": round_rating(state["peak_rating"]),
                "last_bout_at": state["last_bout_at"],
                "version": version,
                "updated_at": updated_at,
            }
        )

    summary["bouts_used"] = len(normalized_bouts)
    summary["rows_computed"] = len(rows)
    summary["skipped"] = sum(
        summary[key]
        for key in (
            "skipped_duplicate_bouts",
            "skipped_null_scores",
            "skipped_missing_fencers",
            "skipped_team_events",
            "skipped_incomplete_events",
            "skipped_missing_context",
            "skipped_tied_scores",
        )
    )
    return rows, summary


def batch_upsert_elo(client, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_fencer_elo").upsert(
            batch, on_conflict="fencer_id,weapon,category,version"
        ).execute()
        written += len(batch)
    return written


def compute_elo(
    client=None,
    *,
    dry_run: bool = False,
    page_size: int = PAGE_SIZE,
    k_config: KFactorConfig | None = None,
    now: str | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        bouts = fetch_bouts(client, page_size=page_size)
        tournaments = fetch_tournaments(client, page_size=page_size)
        identity_rows, identity_count = load_identity_rows(client, page_size=page_size)
        rows, summary = build_elo_rows(
            bouts,
            tournaments,
            identity_rows=identity_rows,
            k_config=k_config,
            now=now,
            version=ELO_VERSION,
        )
        written = 0 if dry_run else batch_upsert_elo(client, rows)
        summary.update(
            {
                "identity_rows": identity_count,
                "rows_written": written,
                "dry_run": dry_run,
            }
        )

        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        if run_log:
            run_log.complete(
                written=written,
                failed=0,
                skipped=summary["skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute fencer Elo ratings.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="compute ratings and summary without writing fs_fencer_elo rows",
    )
    args = parser.parse_args()

    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous Elo state: {previous_state}")
    summary = compute_elo(dry_run=args.dry_run)
    print(
        "Elo recompute complete: "
        f"{summary['rows_computed']} rows computed, "
        f"{summary['rows_written']} rows written, "
        f"{summary['skipped']} bouts skipped"
    )


if __name__ == "__main__":
    main()

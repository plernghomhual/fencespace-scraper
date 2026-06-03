from __future__ import annotations

from collections import OrderedDict
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query


BRACKET_TABLE = "fs_tournament_brackets"
DEFAULT_MAX_ROWS = 1000
MAX_BRACKET_ROWS = 2000

BRACKET_SELECT = ",".join(
    [
        "id",
        "tournament_id",
        "event_id",
        "event_key",
        "weapon",
        "gender",
        "category",
        "round_name",
        "round_order",
        "bout_order",
        "fencer_a_id",
        "fencer_a_name",
        "fencer_a_country",
        "fencer_a_seed",
        "fencer_b_id",
        "fencer_b_name",
        "fencer_b_country",
        "fencer_b_seed",
        "score_a",
        "score_b",
        "winner_id",
        "is_bye",
        "source",
        "source_url",
        "metadata",
    ]
)

router = APIRouter(tags=["tournaments"])


def get_supabase_client():
    try:
        from api import get_supabase_client as get_client
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Supabase client dependency unavailable") from exc
    return get_client()


def validate_uuid(value: str, field_name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}") from exc


def clean_filter(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > 80:
        raise ValueError(f"{field_name} is too long")
    return text


def first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def score_value(row: dict[str, Any], side: str) -> Any:
    score = row.get(f"score_{side}")
    if score is not None:
        return score

    scores = row.get("scores")
    if isinstance(scores, dict):
        return first_present(scores, side, f"score_{side}", f"fencer_{side}")
    return None


def fencer_payload(row: dict[str, Any], side: str) -> dict[str, Any] | None:
    prefix = f"fencer_{side}"
    fencer_id = first_present(row, f"{prefix}_id", prefix, f"fie_fencer_id_{side}")
    name = first_present(row, f"{prefix}_name", f"name_{side}")
    country = first_present(row, f"{prefix}_country", f"country_{side}", f"nationality_{side}")
    seed = int_or_none(first_present(row, f"{prefix}_seed", f"seed_{side}"))

    if fencer_id is None and name is None and seed is None:
        return None

    return {
        "id": fencer_id,
        "name": name,
        "country": country,
        "seed": seed,
    }


def event_key_for_row(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("event_id") or "",
        row.get("event_key") or "",
        row.get("weapon") or "",
        row.get("gender") or "",
        row.get("category") or "",
    )


def round_key_for_row(row: dict[str, Any], fallback_order: int) -> tuple[Any, ...]:
    round_name = row.get("round_name") or "Unknown round"
    round_order = int_or_none(row.get("round_order"))
    return (round_order if round_order is not None else fallback_order, round_name)


def bout_sort_key(index_and_bout: tuple[int, dict[str, Any]]) -> tuple[int, int]:
    original_index, bout = index_and_bout
    bout_order = int_or_none(bout.get("bout_order"))
    return (bout_order if bout_order is not None else original_index, original_index)


def is_truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def bout_status(row: dict[str, Any], fencer_a: dict[str, Any] | None, fencer_b: dict[str, Any] | None) -> str:
    explicit_bye = is_truthy(row.get("is_bye"))
    one_fencer = (fencer_a is None) != (fencer_b is None)
    winner_id = row.get("winner_id")
    if explicit_bye or (one_fencer and winner_id):
        return "bye"

    score_a = score_value(row, "a")
    score_b = score_value(row, "b")
    if score_a is not None and score_b is not None and winner_id:
        return "complete"
    return "incomplete"


def bout_payload(row: dict[str, Any]) -> dict[str, Any]:
    fencer_a = fencer_payload(row, "a")
    fencer_b = fencer_payload(row, "b")
    score_a = score_value(row, "a")
    score_b = score_value(row, "b")
    status = bout_status(row, fencer_a, fencer_b)

    return {
        "id": row.get("id"),
        "round_name": row.get("round_name") or "Unknown round",
        "bout_order": int_or_none(row.get("bout_order")),
        "status": status,
        "is_bye": status == "bye",
        "fencer_a": fencer_a,
        "fencer_b": fencer_b,
        "score": {"a": score_a, "b": score_b},
        "winner_id": row.get("winner_id"),
        "source": row.get("source"),
        "source_url": row.get("source_url"),
        "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
    }


def empty_payload(tournament_id: str, filters: dict[str, str | None]) -> dict[str, Any]:
    return {
        "tournament_id": tournament_id,
        "filters": filters,
        "events": [],
        "count": {"events": 0, "rounds": 0, "bouts": 0},
    }


def fetch_bracket_rows(
    supabase: Any,
    tournament_id: str,
    *,
    event_id: str | None = None,
    event_key: str | None = None,
    weapon: str | None = None,
    gender: str | None = None,
    category: str | None = None,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> list[dict[str, Any]]:
    if max_rows < 1 or max_rows > MAX_BRACKET_ROWS:
        raise ValueError(f"max_rows must be between 1 and {MAX_BRACKET_ROWS}")

    query = supabase.table(BRACKET_TABLE).select(BRACKET_SELECT).eq("tournament_id", tournament_id)
    for column, value in (
        ("event_id", event_id),
        ("event_key", event_key),
        ("weapon", weapon),
        ("gender", gender),
        ("category", category),
    ):
        if value is not None:
            query = query.eq(column, value)

    try:
        rows = query.range(0, max_rows).execute().data or []
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase query failed for {BRACKET_TABLE}") from exc

    if len(rows) > max_rows:
        raise HTTPException(status_code=413, detail=f"Bracket response exceeds max_rows={max_rows}")
    return rows


def group_bracket_rows(tournament_id: str, rows: list[dict[str, Any]], filters: dict[str, str | None]) -> dict[str, Any]:
    if not rows:
        return empty_payload(tournament_id, filters)

    events: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
    round_order_seen: dict[tuple[Any, ...], OrderedDict[tuple[Any, ...], list[tuple[int, dict[str, Any]]]]] = {}

    for index, row in enumerate(rows):
        event_key = event_key_for_row(row)
        if event_key not in events:
            events[event_key] = {
                "event_id": row.get("event_id"),
                "event_key": row.get("event_key"),
                "weapon": row.get("weapon"),
                "gender": row.get("gender"),
                "category": row.get("category"),
                "rounds": [],
            }
            round_order_seen[event_key] = OrderedDict()

        rounds = round_order_seen[event_key]
        round_key = round_key_for_row(row, len(rounds) + 1)
        if round_key not in rounds:
            rounds[round_key] = []
        rounds[round_key].append((index, row))

    total_rounds = 0
    total_bouts = 0
    for event_key, event in events.items():
        rounds = round_order_seen[event_key]
        for (round_order, round_name), indexed_rows in rounds.items():
            bouts = [
                bout_payload(row)
                for _, row in sorted(indexed_rows, key=bout_sort_key)
            ]
            event["rounds"].append(
                {
                    "round_name": round_name,
                    "round_order": round_order,
                    "bouts": bouts,
                }
            )
            total_bouts += len(bouts)
        total_rounds += len(event["rounds"])

    return {
        "tournament_id": tournament_id,
        "filters": filters,
        "events": list(events.values()),
        "count": {
            "events": len(events),
            "rounds": total_rounds,
            "bouts": total_bouts,
        },
    }


def get_tournament_bracket_payload(
    supabase: Any,
    tournament_id: str,
    *,
    event_id: str | None = None,
    event_key: str | None = None,
    weapon: str | None = None,
    gender: str | None = None,
    category: str | None = None,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> dict[str, Any]:
    tournament_id = validate_uuid(tournament_id, "tournament_id")
    filters = {
        "event_id": clean_filter(event_id, "event_id"),
        "event_key": clean_filter(event_key, "event_key"),
        "weapon": clean_filter(weapon, "weapon"),
        "gender": clean_filter(gender, "gender"),
        "category": clean_filter(category, "category"),
    }
    rows = fetch_bracket_rows(supabase, tournament_id, max_rows=max_rows, **filters)
    return group_bracket_rows(tournament_id, rows, filters)


@router.get("/tournaments/{tournament_id}/brackets")
def tournament_brackets(
    tournament_id: str,
    event_id: str | None = None,
    event_key: str | None = None,
    weapon: str | None = None,
    gender: str | None = None,
    category: str | None = None,
    max_rows: int = Query(DEFAULT_MAX_ROWS, ge=1, le=MAX_BRACKET_ROWS),
    supabase: Any = Depends(get_supabase_client),
):
    try:
        return get_tournament_bracket_payload(
            supabase,
            tournament_id,
            event_id=event_id,
            event_key=event_key,
            weapon=weapon,
            gender=gender,
            category=category,
            max_rows=max_rows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

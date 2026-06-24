from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

MAX_IDENTITY_MEMBERS = 25
MAX_STATS_ROWS = 250
MAX_SEASON_ROWS = 25
IDENTITY_SELECTS = (
    ("id,fs_fencer_row_ids", "fs_fencer_row_ids"),
    ("id,fencer_ids", "fencer_ids"),
    ("id,source_fencer_ids", "source_fencer_ids"),
    ("id,canonical_id,fs_fencer_row_ids", "fs_fencer_row_ids"),
)

router = APIRouter(tags=["fencer-stats"])


def get_supabase_client():
    from api import get_supabase_client as api_get_supabase_client

    return api_get_supabase_client()


def validate_fencer_id(fencer_id: str) -> str:
    try:
        return str(UUID(str(fencer_id)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid fencer_id") from exc


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def to_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else 0


def optional_int(value: Any) -> int | None:
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
    key = text.casefold().replace("é", "e")
    if key in {"e", "epee"}:
        return "Epee"
    if key in {"f", "foil"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    raise HTTPException(status_code=422, detail="Invalid weapon")


def validate_season(value: Any) -> int | None:
    if value is None or value == "":
        return None
    season = optional_int(value)
    if season is None or season < 1900 or season > 2200:
        raise HTTPException(status_code=422, detail="Invalid season")
    return season


def validate_category(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if len(text) > 64:
        raise HTTPException(status_code=422, detail="Invalid category")
    return text


def validate_limit(value: int, maximum: int, name: str) -> int:
    if value < 1 or value > maximum:
        raise HTTPException(status_code=422, detail=f"{name} must be between 1 and {maximum}")
    return value


def execute_required_rows(query, table_name: str) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase query failed for {table_name}") from exc


def execute_optional_rows(query) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except Exception:
        return []


def first_required_row(client, table_name: str, column: str, value: Any) -> dict[str, Any] | None:
    rows = execute_required_rows(
        client.table(table_name).select("id").eq(column, value).limit(1),
        table_name,
    )
    return rows[0] if rows else None


def parse_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        try:
            ids.append(str(UUID(str(item))))
        except (TypeError, ValueError):
            continue
    return ids


def resolve_identity_fencer_ids(client, fencer_id: str) -> list[str]:
    rows: list[dict[str, Any]] = []
    for columns, member_column in IDENTITY_SELECTS:
        rows = execute_optional_rows(
            client.table("fs_fencer_identities")
            .select(columns)
            .contains(member_column, [fencer_id])
            .limit(MAX_IDENTITY_MEMBERS)
        )
        if rows:
            break

    ordered = [fencer_id]
    seen = {fencer_id}
    for row in rows:
        members = (
            parse_id_list(row.get("fs_fencer_row_ids"))
            or parse_id_list(row.get("fencer_ids"))
            or parse_id_list(row.get("source_fencer_ids"))
        )
        for member in members:
            if member not in seen and len(ordered) < MAX_IDENTITY_MEMBERS:
                ordered.append(member)
                seen.add(member)
    return ordered


def apply_optional_filters(query, *, season: int | None, weapon: str | None, category: str | None):
    if season is not None:
        query = query.eq("season", season)
    if weapon is not None:
        query = query.eq("weapon", weapon)
    if category is not None:
        query = query.eq("category", category)
    return query


def fetch_public_rows(
    client,
    table_name: str,
    fencer_ids: list[str],
    *,
    season: int | None = None,
    weapon: str | None = None,
    category: str | None = None,
    limit: int = MAX_STATS_ROWS,
) -> list[dict[str, Any]]:
    if not fencer_ids:
        return []

    try:
        query = client.table(table_name).select("*").in_("fencer_id", fencer_ids)
        query = apply_optional_filters(query, season=season, weapon=weapon, category=category)
        return execute_optional_rows(query.limit(limit))
    except AttributeError:
        rows: list[dict[str, Any]] = []
        per_id_limit = max(1, limit // len(fencer_ids))
        for fencer_id in fencer_ids[:MAX_IDENTITY_MEMBERS]:
            query = client.table(table_name).select("*").eq("fencer_id", fencer_id)
            query = apply_optional_filters(query, season=season, weapon=weapon, category=category)
            rows.extend(execute_optional_rows(query.limit(per_id_limit)))
            if len(rows) >= limit:
                return rows[:limit]
        return rows


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = row.get("id")
        if not key:
            key = tuple(sorted((str(k), repr(v)) for k, v in row.items() if k not in {"updated_at", "created_at"}))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def value_from(row: dict[str, Any], *columns: str) -> Any:
    for column in columns:
        value = row.get(column)
        if value is not None and value != "":
            return value
    return None


def empty_count_stats() -> dict[str, Any]:
    return {
        "bouts": 0,
        "wins": 0,
        "losses": 0,
        "touches_scored": 0,
        "touches_received": 0,
        "starts": 0,
        "gold": 0,
        "silver": 0,
        "bronze": 0,
        "top8": 0,
        "top16": 0,
        "top32": 0,
        "best_finish": None,
    }


def add_count_row(target: dict[str, Any], row: dict[str, Any]) -> None:
    wins = to_int(value_from(row, "wins", "total_wins"))
    losses = to_int(value_from(row, "losses", "total_losses"))
    bouts = optional_int(value_from(row, "total_bouts", "bouts", "bout_count"))
    target["wins"] += wins
    target["losses"] += losses
    target["bouts"] += bouts if bouts is not None else wins + losses
    target["touches_scored"] += to_int(value_from(row, "touches_scored", "total_touches_scored"))
    target["touches_received"] += to_int(value_from(row, "touches_received", "total_touches_received"))
    target["starts"] += to_int(value_from(row, "starts", "total_starts", "total_competitions"))
    target["gold"] += to_int(value_from(row, "gold_medals", "gold"))
    target["silver"] += to_int(value_from(row, "silver_medals", "silver"))
    target["bronze"] += to_int(value_from(row, "bronze_medals", "bronze"))
    target["top8"] += to_int(value_from(row, "top8_count", "top8"))
    target["top16"] += to_int(value_from(row, "top16_count", "top16"))
    target["top32"] += to_int(value_from(row, "top32_count", "top32"))

    finish = optional_int(value_from(row, "best_finish", "best_rank", "best_placement"))
    if finish is not None:
        current = target["best_finish"]
        target["best_finish"] = finish if current is None else min(current, finish)


def format_bout_record(stats: dict[str, Any]) -> dict[str, Any]:
    bouts = stats["bouts"]
    wins = stats["wins"]
    return {
        "bouts": bouts,
        "wins": wins,
        "losses": stats["losses"],
        "win_pct": round(wins / bouts, 4) if bouts else None,
    }


def format_touches(stats: dict[str, Any]) -> dict[str, int]:
    scored = stats["touches_scored"]
    received = stats["touches_received"]
    return {"scored": scored, "received": received, "differential": scored - received}


def format_medals(stats: dict[str, Any]) -> dict[str, int]:
    gold = stats["gold"]
    silver = stats["silver"]
    bronze = stats["bronze"]
    return {"gold": gold, "silver": silver, "bronze": bronze, "total": gold + silver + bronze}


def format_placements(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "starts": stats["starts"],
        "medals": format_medals(stats),
        "top8": stats["top8"],
        "top16": stats["top16"],
        "top32": stats["top32"],
        "best_finish": stats["best_finish"],
    }


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats = empty_count_stats()
    for row in dedupe_rows(rows):
        add_count_row(stats, row)
    return stats


def aggregate_weapon_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in dedupe_rows(rows):
        weapon = normalize_weapon(row.get("weapon")) if row.get("weapon") else None
        if not weapon:
            continue
        add_count_row(grouped.setdefault(weapon, empty_count_stats()), row)

    return [
        {
            "weapon": weapon,
            "bout_record": format_bout_record(stats),
            "touches": format_touches(stats),
        }
        for weapon, stats in sorted(grouped.items())
    ]


def aggregate_season_breakdown(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, str | None], dict[str, Any]] = {}
    for row in dedupe_rows(rows):
        season = row.get("season")
        weapon = normalize_weapon(row.get("weapon")) if row.get("weapon") else None
        key = (season, weapon)
        add_count_row(grouped.setdefault(key, empty_count_stats()), row)

    breakdown = []
    for (season, weapon), stats in grouped.items():
        breakdown.append(
            {
                "season": season,
                "weapon": weapon,
                "starts": stats["starts"],
                "bout_record": format_bout_record(stats),
                "touches": format_touches(stats),
                "placements": {
                    "medals": format_medals(stats),
                    "top8": stats["top8"],
                    "top16": stats["top16"],
                    "top32": stats["top32"],
                    "best_finish": stats["best_finish"],
                },
            }
        )
    return sorted(breakdown, key=lambda row: (str(row["season"]), str(row["weapon"])))[:limit]


def choose_primary_rows(
    bout_rows: list[dict[str, Any]],
    season_rows: list[dict[str, Any]],
    career_rows: list[dict[str, Any]],
    *,
    season: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if season is not None:
        return season_rows, season_rows
    return bout_rows, career_rows


def get_public_fencer_stats(
    fencer_id: str,
    *,
    client=None,
    season: int | None = None,
    weapon: str | None = None,
    category: str | None = None,
    season_limit: int = MAX_SEASON_ROWS,
) -> dict[str, Any]:
    fencer_id = validate_fencer_id(fencer_id)
    season = validate_season(season)
    weapon = normalize_weapon(weapon) if weapon else None
    category = validate_category(category)
    season_limit = validate_limit(season_limit, MAX_SEASON_ROWS, "season_limit")

    client = client or get_supabase_client()
    if not first_required_row(client, "fs_fencers", "id", fencer_id):
        raise HTTPException(status_code=404, detail="Fencer not found")

    identity_ids = resolve_identity_fencer_ids(client, fencer_id)
    bout_rows = fetch_public_rows(
        client,
        "fs_fencer_stats",
        identity_ids,
        weapon=weapon,
        category=category,
        limit=MAX_STATS_ROWS,
    )
    career_rows = fetch_public_rows(
        client,
        "fs_fencer_career_stats",
        identity_ids,
        limit=MAX_STATS_ROWS,
    )
    season_rows = fetch_public_rows(
        client,
        "fs_fencer_season_stats",
        identity_ids,
        season=season,
        weapon=weapon,
        category=category,
        limit=season_limit,
    )

    primary_bout_rows, placement_rows = choose_primary_rows(
        bout_rows,
        season_rows,
        career_rows,
        season=season,
    )
    bout_stats = aggregate_rows(primary_bout_rows)
    placement_stats = aggregate_rows(placement_rows)

    return {
        "fencer_id": fencer_id,
        "filters": {"season": season, "weapon": weapon, "category": category},
        "bout_record": format_bout_record(bout_stats),
        "touches": format_touches(bout_stats),
        "placements": format_placements(placement_stats),
        "streaks": {"current": None, "longest_win": None},
        "weapon_breakdown": aggregate_weapon_breakdown(primary_bout_rows),
        "season_breakdown": aggregate_season_breakdown(season_rows, season_limit),
        "available_sources": {
            "bout_stats": bool(bout_rows),
            "career_stats": bool(career_rows),
            "season_stats": bool(season_rows),
        },
    }


@router.get("/fencer/{fencer_id}/stats")
def fencer_stats_route(
    fencer_id: str,
    season: int | None = Query(None, ge=1900, le=2200),
    weapon: str | None = None,
    category: str | None = Query(None, max_length=64),
    season_limit: int = Query(MAX_SEASON_ROWS, ge=1, le=MAX_SEASON_ROWS),
):
    return get_public_fencer_stats(
        fencer_id,
        season=season,
        weapon=weapon,
        category=category,
        season_limit=season_limit,
    )

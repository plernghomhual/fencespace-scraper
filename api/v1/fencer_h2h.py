import os
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

DEFAULT_LIMIT = 50
MAX_LIMIT = 500
PAGE_SIZE = 1000

WEAPON_ALIASES = {
    "e": "Epee",
    "epee": "Epee",
    "épée": "Epee",
    "f": "Foil",
    "foil": "Foil",
    "s": "Sabre",
    "sabre": "Sabre",
    "saber": "Sabre",
}
CATEGORY_ALIASES = {
    "senior": "Senior",
    "seniors": "Senior",
    "junior": "Junior",
    "juniors": "Junior",
    "u20": "Junior",
    "cadet": "Cadet",
    "cadets": "Cadet",
    "u17": "Cadet",
    "veteran": "Veteran",
    "veterans": "Veteran",
    "youth": "Youth",
}

PUBLIC_FENCER_FIELDS = (
    "id",
    "fie_id",
    "name",
    "country",
    "weapon",
    "category",
    "gender",
    "world_rank",
    "fie_points",
)

router = APIRouter(prefix="/fencer", tags=["fencers"])
_supabase_client = None


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_uuid(value: Any) -> str:
    text = clean_text(value)
    if not text:
        raise HTTPException(status_code=422, detail="Invalid fencer ID")
    try:
        return str(uuid.UUID(text))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid fencer ID") from exc


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    weapon = WEAPON_ALIASES.get(text.casefold())
    if not weapon:
        raise HTTPException(status_code=422, detail="Invalid weapon")
    return weapon


def normalize_category(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    category = CATEGORY_ALIASES.get(text.casefold())
    if not category:
        raise HTTPException(status_code=422, detail="Invalid category")
    return category


def validate_pagination(limit: int, offset: int) -> None:
    if limit < 1 or limit > MAX_LIMIT or offset < 0:
        raise HTTPException(status_code=422, detail="Invalid pagination")


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase credentials are not configured")

    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def execute_rows(query, table_name: str, *, optional: bool = False) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except HTTPException:
        raise
    except Exception as exc:
        if optional:
            return []
        raise HTTPException(status_code=502, detail=f"Supabase query failed for {table_name}") from exc


def apply_in_filter(query, column: str, values: list[str]):
    if hasattr(query, "in_"):
        return query.in_(column, values)
    raise AttributeError("Supabase query object does not support in_")


def apply_overlap_filter(query, column: str, values: list[str]):
    if hasattr(query, "overlaps"):
        return query.overlaps(column, values)
    raise AttributeError("Supabase query object does not support overlaps")


def fetch_all_rows(supabase, table_name: str, columns: str = "*", *, optional: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = execute_rows(
            supabase.table(table_name)
            .select(columns)
            .range(offset, offset + PAGE_SIZE - 1),
            table_name,
            optional=optional,
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def fetch_fencer_rows(supabase, fencer_ids: list[str]) -> list[dict[str, Any]]:
    if not fencer_ids:
        return []
    ids = sorted(set(fencer_ids))
    try:
        query = apply_in_filter(supabase.table("fs_fencers").select("*"), "id", ids)
        return execute_rows(query, "fs_fencers")
    except AttributeError:
        rows = fetch_all_rows(supabase, "fs_fencers")
        wanted = set(ids)
        return [row for row in rows if str(row.get("id")) in wanted]


def fetch_fencer_row(supabase, fencer_id: str) -> dict[str, Any] | None:
    rows = execute_rows(
        supabase.table("fs_fencers")
        .select("*")
        .eq("id", fencer_id)
        .range(0, 0),
        "fs_fencers",
    )
    return rows[0] if rows else None


def fetch_identity_rows(supabase, fencer_ids: list[str]) -> list[dict[str, Any]]:
    columns = "id,canonical_name,country,fie_ids,fs_fencer_row_ids"
    if not fencer_ids:
        return []
    ids = sorted(set(fencer_ids))
    try:
        query = apply_overlap_filter(
            supabase.table("fs_fencer_identities").select(columns),
            "fs_fencer_row_ids",
            ids,
        )
        return execute_rows(query, "fs_fencer_identities", optional=True)
    except AttributeError:
        rows = fetch_all_rows(supabase, "fs_fencer_identities", columns, optional=True)
        wanted = set(ids)
        return [
            row
            for row in rows
            if wanted.intersection({str(item) for item in identity_member_ids(row)})
        ]


def identity_member_ids(row: dict[str, Any]) -> list[str]:
    members = (
        row.get("fs_fencer_row_ids")
        or row.get("fencer_ids")
        or row.get("source_fencer_ids")
        or []
    )
    if isinstance(members, str):
        members = [members]
    if not isinstance(members, list):
        return []
    return sorted({str(item) for item in members if clean_text(item)})


def identity_key(row: dict[str, Any] | None, fallback_id: str) -> str:
    if not row:
        return fallback_id
    return clean_text(row.get("canonical_id")) or clean_text(row.get("id")) or fallback_id


def build_identity_lookup(
    identity_rows: list[dict[str, Any]],
    fallback_ids: list[str],
) -> tuple[dict[str, str], dict[str, dict[str, Any]], str]:
    row_to_identity: dict[str, str] = {}
    identities: dict[str, dict[str, Any]] = {}

    for row in identity_rows:
        members = identity_member_ids(row)
        fallback = members[0] if members else clean_text(row.get("id")) or ""
        key = identity_key(row, fallback)
        if not key:
            continue
        identities[key] = row
        for member in members:
            row_to_identity[member] = key

    for fallback_id in fallback_ids:
        row_to_identity.setdefault(fallback_id, fallback_id)
        identities.setdefault(fallback_id, {"id": fallback_id, "fs_fencer_row_ids": [fallback_id]})

    first = fallback_ids[0] if fallback_ids else ""
    return row_to_identity, identities, row_to_identity.get(first, first)


def fencer_matches_category(row: dict[str, Any], category: str | None) -> bool:
    if not category:
        return True
    text = clean_text(row.get("category"))
    if not text:
        return False
    lowered = text.casefold()
    return lowered == category.casefold() or lowered.endswith(f" {category.casefold()}")


def sanitize_fencer(row: dict[str, Any] | None, identity: dict[str, Any] | None, fallback_id: str) -> dict[str, Any]:
    source = row or {}
    public = {
        key: source[key]
        for key in PUBLIC_FENCER_FIELDS
        if key in source and source[key] is not None
    }
    public.setdefault("id", fallback_id)
    if identity:
        name = clean_text(identity.get("canonical_name"))
        country = clean_text(identity.get("country"))
        if name:
            public.setdefault("name", name)
        if country:
            public.setdefault("country", country)
    return public


def fetch_h2h_rows_for_target_ids(supabase, target_ids: list[str]) -> list[dict[str, Any]]:
    if not target_ids:
        return []
    ids = sorted(set(target_ids))

    try:
        left_rows = execute_rows(
            apply_in_filter(
                supabase.table("fs_head_to_head").select("*"),
                "fencer_a_id",
                ids,
            ),
            "fs_head_to_head",
        )
        right_rows = execute_rows(
            apply_in_filter(
                supabase.table("fs_head_to_head").select("*"),
                "fencer_b_id",
                ids,
            ),
            "fs_head_to_head",
        )
        rows = left_rows + right_rows
    except AttributeError:
        all_rows = fetch_all_rows(supabase, "fs_head_to_head")
        id_set = set(ids)
        rows = [
            row
            for row in all_rows
            if str(row.get("fencer_a_id")) in id_set or str(row.get("fencer_b_id")) in id_set
        ]

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("fencer_a_id")),
            str(row.get("fencer_b_id")),
            str(row.get("weapon")),
        )
        deduped[key] = row
    return list(deduped.values())


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def latest_meeting(current: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any] | None:
    if not candidate.get("date"):
        return current
    if not current or str(candidate["date"]) > str(current.get("date") or ""):
        return candidate
    return current


def empty_payload(fencer_id: str, weapon: str | None, category: str | None) -> dict[str, Any]:
    return {
        "fencer_id": fencer_id,
        "filters": {"weapon": weapon, "category": category},
        "weapon_filters": [],
        "opponents": [],
        "pagination": {"limit": DEFAULT_LIMIT, "offset": 0, "count": 0, "total": 0},
    }


def get_fencer_h2h(
    supabase,
    fencer_id: str,
    *,
    weapon: str | None = None,
    category: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    fencer_id = normalize_uuid(fencer_id)
    weapon = normalize_weapon(weapon)
    category = normalize_category(category)
    validate_pagination(limit, offset)

    requested_fencer = fetch_fencer_row(supabase, fencer_id)
    if not requested_fencer:
        raise HTTPException(status_code=404, detail="Fencer not found")

    target_identity_rows = fetch_identity_rows(supabase, [fencer_id])
    target_members = sorted(
        {
            member
            for row in target_identity_rows
            for member in identity_member_ids(row)
        }
        or {fencer_id}
    )
    target_rows = fetch_fencer_rows(supabase, target_members)
    target_rows_by_id = {str(row.get("id")): row for row in target_rows}
    scoped_target_ids = [
        row_id
        for row_id in target_members
        if fencer_matches_category(target_rows_by_id.get(row_id, {}), category)
    ]

    all_target_h2h_rows = fetch_h2h_rows_for_target_ids(supabase, target_members)
    weapon_filters = sorted(
        {
            normalize_weapon(row.get("weapon"))
            for row in all_target_h2h_rows
            if row.get("weapon")
        },
        key=lambda w: w or "",
    )

    if not scoped_target_ids:
        payload = empty_payload(fencer_id, weapon, category)
        payload["weapon_filters"] = weapon_filters
        payload["pagination"] = {"limit": limit, "offset": offset, "count": 0, "total": 0}
        return payload

    target_h2h_rows = [
        row
        for row in all_target_h2h_rows
        if str(row.get("fencer_a_id")) in scoped_target_ids
        or str(row.get("fencer_b_id")) in scoped_target_ids
    ]
    if weapon:
        target_h2h_rows = [
            row
            for row in target_h2h_rows
            if normalize_weapon(row.get("weapon")) == weapon
        ]

    target_row_to_identity, target_identities, target_key = build_identity_lookup(
        target_identity_rows,
        target_members,
    )

    opponent_ids = sorted(
        {
            str(row.get("fencer_b_id"))
            if str(row.get("fencer_a_id")) in scoped_target_ids
            else str(row.get("fencer_a_id"))
            for row in target_h2h_rows
            if row.get("fencer_a_id") and row.get("fencer_b_id")
        }
    )
    opponent_identity_rows = fetch_identity_rows(supabase, opponent_ids)
    opponent_row_to_identity, opponent_identities, _ = build_identity_lookup(
        opponent_identity_rows,
        opponent_ids,
    )
    all_profile_rows = fetch_fencer_rows(supabase, sorted(set(opponent_ids + target_members)))
    profiles_by_id = {str(row.get("id")): row for row in all_profile_rows}

    groups: dict[str, dict[str, Any]] = {}
    for row in target_h2h_rows:
        fencer_a_id = str(row.get("fencer_a_id"))
        fencer_b_id = str(row.get("fencer_b_id"))
        if fencer_a_id in scoped_target_ids:
            opponent_id = fencer_b_id
            fencer_wins = int_value(row.get("a_wins"))
            opponent_wins = int_value(row.get("b_wins"))
            fencer_touches = int_value(row.get("a_touches"))
            opponent_touches = int_value(row.get("b_touches"))
        elif fencer_b_id in scoped_target_ids:
            opponent_id = fencer_a_id
            fencer_wins = int_value(row.get("b_wins"))
            opponent_wins = int_value(row.get("a_wins"))
            fencer_touches = int_value(row.get("b_touches"))
            opponent_touches = int_value(row.get("a_touches"))
        else:
            continue

        opponent_key = opponent_row_to_identity.get(opponent_id, opponent_id)
        if opponent_key == target_key or target_row_to_identity.get(opponent_id) == target_key:
            continue

        opponent_identity = opponent_identities.get(opponent_key)
        opponent_members = identity_member_ids(opponent_identity or {})
        profile_id = next(
            (member for member in opponent_members if member in profiles_by_id),
            opponent_id,
        )
        group = groups.setdefault(
            opponent_key,
            {
                "opponent": sanitize_fencer(
                    profiles_by_id.get(profile_id),
                    opponent_identity,
                    profile_id,
                ),
                "records_by_weapon": {},
                "total_bouts": 0,
                "fencer_wins": 0,
                "opponent_wins": 0,
                "last_meeting": None,
            },
        )

        row_weapon = normalize_weapon(row.get("weapon"))
        if not row_weapon:
            continue
        record = group["records_by_weapon"].setdefault(
            row_weapon,
            {
                "weapon": row_weapon,
                "bouts_total": 0,
                "fencer_wins": 0,
                "opponent_wins": 0,
                "fencer_touches": 0,
                "opponent_touches": 0,
                "last_meeting_date": None,
                "last_winner_id": None,
            },
        )
        bouts_total = int_value(row.get("bouts_total"))
        record["bouts_total"] += bouts_total
        record["fencer_wins"] += fencer_wins
        record["opponent_wins"] += opponent_wins
        record["fencer_touches"] += fencer_touches
        record["opponent_touches"] += opponent_touches

        candidate_meeting = {
            "date": row.get("last_meeting_date"),
            "weapon": row_weapon,
            "winner_id": row.get("last_winner_id"),
        }
        if latest_meeting(
            {"date": record.get("last_meeting_date")},
            candidate_meeting,
        ) == candidate_meeting:
            record["last_meeting_date"] = candidate_meeting["date"]
            record["last_winner_id"] = candidate_meeting["winner_id"]

        group["total_bouts"] += bouts_total
        group["fencer_wins"] += fencer_wins
        group["opponent_wins"] += opponent_wins
        group["last_meeting"] = latest_meeting(group["last_meeting"], candidate_meeting)

    opponents = []
    for group in groups.values():
        records = sorted(
            group.pop("records_by_weapon").values(),
            key=lambda record: record["weapon"],
        )
        group["records"] = records
        opponents.append(group)

    opponents.sort(
        key=lambda group: (
            -group["total_bouts"],
            str(group.get("last_meeting", {}).get("date") or ""),
            str(group["opponent"].get("name") or ""),
            str(group["opponent"].get("id") or ""),
        ),
        reverse=False,
    )
    total = len(opponents)
    page = opponents[offset : offset + limit]
    return {
        "fencer_id": fencer_id,
        "filters": {"weapon": weapon, "category": category},
        "weapon_filters": weapon_filters,
        "opponents": page,
        "pagination": {"limit": limit, "offset": offset, "count": len(page), "total": total},
    }


@router.get("/{fencer_id}/h2h")
def fencer_h2h_route(
    fencer_id: str,
    weapon: str | None = None,
    category: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    supabase=Depends(get_supabase_client),
):
    return get_fencer_h2h(
        supabase,
        fencer_id,
        weapon=weapon,
        category=category,
        limit=limit,
        offset=offset,
    )

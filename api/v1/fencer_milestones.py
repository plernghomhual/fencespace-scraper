from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Callable
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query


DEFAULT_LIMIT = 50
MAX_LIMIT = 500
MILESTONES_TABLE = "fs_career_milestones"

ALLOWED_MILESTONE_TYPES = {
    "first_result",
    "first_international_result",
    "first_medal",
    "first_gold",
    "first_top8",
    "first_top16",
    "personal_best_ranking",
    "country_change",
    "weapon_transition",
    "category_transition",
    "retirement",
    "reactivation",
}

IDENTITY_SELECTS = (
    "id,canonical_id,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
    "canonical_id,fs_fencer_row_ids",
    "id,canonical_id,fencer_ids",
    "canonical_id,fencer_ids",
)

PRIVATE_FIELD_PATTERNS = (
    "api_key",
    "auth",
    "fencer_id",
    "identity",
    "internal",
    "payload",
    "private",
    "raw",
    "secret",
    "service",
    "token",
)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_milestone_type(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return re.sub(r"[\s-]+", "_", text.casefold())


def validate_fencer_id(fencer_id: Any) -> str:
    text = clean_text(fencer_id)
    if not text:
        raise HTTPException(status_code=422, detail="Invalid fencer_id")
    try:
        UUID(text)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid fencer_id") from exc
    return text


def validate_milestone_type(milestone_type: str | None) -> str | None:
    normalized = normalize_milestone_type(milestone_type)
    if normalized is None:
        return None
    if normalized not in ALLOWED_MILESTONE_TYPES:
        raise HTTPException(status_code=422, detail="Invalid milestone_type")
    return normalized


def validate_pagination(limit: int, offset: int) -> tuple[int, int]:
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > MAX_LIMIT:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_LIMIT}")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise HTTPException(status_code=422, detail="offset must be greater than or equal to 0")
    return limit, offset


def execute_rows(query, table_name: str, *, optional: bool = False) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except HTTPException:
        raise
    except Exception as exc:
        if optional:
            return []
        raise HTTPException(status_code=502, detail=f"Supabase query failed for {table_name}") from exc


def parse_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        return []
    return sorted({text for item in value if (text := clean_text(item))})


def _identity_members(row: dict[str, Any]) -> list[str]:
    return parse_id_list(row.get("fs_fencer_row_ids") or row.get("fencer_ids") or row.get("source_fencer_ids"))


def _fetch_identity_rows(client, fencer_id: str) -> list[dict[str, Any]]:
    for columns in IDENTITY_SELECTS:
        rows = execute_rows(
            client.table("fs_fencer_identities")
            .select(columns)
            .contains("fs_fencer_row_ids", [fencer_id])
            .limit(1),
            "fs_fencer_identities",
            optional=True,
        )
        if rows:
            return rows

    for columns in IDENTITY_SELECTS:
        rows = execute_rows(
            client.table("fs_fencer_identities").select(columns).limit(1000),
            "fs_fencer_identities",
            optional=True,
        )
        matches = [row for row in rows if fencer_id in _identity_members(row)]
        if matches:
            return matches[:1]
    return []


def resolve_fencer_identity(client, fencer_id: str) -> dict[str, Any]:
    rows = execute_rows(
        client.table("fs_fencers").select("id").eq("id", fencer_id).limit(1),
        "fs_fencers",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Fencer not found")

    identity_rows = _fetch_identity_rows(client, fencer_id)
    if not identity_rows:
        return {
            "identity_id": None,
            "canonical_id": fencer_id,
            "member_ids": [fencer_id],
        }

    identity = identity_rows[0]
    members = _identity_members(identity)
    canonical_id = clean_text(identity.get("canonical_id"))
    if not canonical_id:
        canonical_id = fencer_id if fencer_id in members else (members[0] if members else fencer_id)
    identity_id = clean_text(identity.get("id")) or canonical_id
    member_ids = sorted({fencer_id, canonical_id, *members})
    return {
        "identity_id": identity_id,
        "canonical_id": canonical_id,
        "member_ids": member_ids,
    }


def _fetch_milestones_by_identity(client, identity_id: str | None, canonical_id: str) -> list[dict[str, Any]]:
    identity_values = [value for value in {identity_id, canonical_id} if value]
    rows: list[dict[str, Any]] = []
    for value in identity_values:
        rows.extend(
            execute_rows(
                client.table(MILESTONES_TABLE).select("*").eq("fencer_identity_id", value),
                MILESTONES_TABLE,
                optional=True,
            )
        )
    return rows


def _fetch_milestones_by_fencers(client, member_ids: list[str]) -> list[dict[str, Any]]:
    if not member_ids:
        return []
    return execute_rows(
        client.table(MILESTONES_TABLE).select("*").in_("fencer_id", member_ids),
        MILESTONES_TABLE,
    )


def fetch_milestone_rows(client, identity_scope: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _fetch_milestones_by_identity(
        client,
        identity_scope.get("identity_id"),
        identity_scope["canonical_id"],
    )
    rows.extend(_fetch_milestones_by_fencers(client, identity_scope["member_ids"]))
    return rows


def normalize_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = clean_text(value)
    if not text:
        return None
    match = re.match(r"^\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    return text


def _parsed_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _is_private_field(key: Any) -> bool:
    normalized = clean_text(key)
    if not normalized:
        return True
    folded = normalized.casefold()
    return any(pattern in folded for pattern in PRIVATE_FIELD_PATTERNS)


def sanitize_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        public = {
            str(key): sanitized
            for key, raw in value.items()
            if not _is_private_field(key)
            and (sanitized := sanitize_public_value(raw)) is not None
        }
        return public or None
    if isinstance(value, list):
        public_items = [sanitized for item in value if (sanitized := sanitize_public_value(item)) is not None]
        return public_items or None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (datetime, date)):
        return normalize_date(value)
    return clean_text(value)


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    return metadata if isinstance(metadata, dict) else {}


def public_source(row: dict[str, Any]) -> Any:
    metadata = _metadata(row)
    source = row.get("source")
    if source is None:
        source = row.get("source_url") or metadata.get("source") or metadata.get("source_url")
    return sanitize_public_value(source)


def public_evidence(row: dict[str, Any]) -> Any:
    metadata = _metadata(row)
    evidence = row.get("evidence")
    if evidence is None:
        evidence = metadata.get("evidence")
    if evidence is None:
        evidence = {
            key: row.get(key)
            for key in ("rank", "medal", "season", "source_id", "result_id", "ranking")
            if row.get(key) is not None
        }
    return sanitize_public_value(evidence)


def public_tournament(row: dict[str, Any]) -> dict[str, Any] | None:
    tournament = row.get("tournament")
    if isinstance(tournament, dict):
        tournament_id = clean_text(tournament.get("id"))
        tournament_name = clean_text(tournament.get("name"))
    else:
        tournament_id = clean_text(row.get("tournament_id"))
        tournament_name = clean_text(row.get("tournament_name") or tournament)
    payload = {
        key: value
        for key, value in {
            "id": tournament_id,
            "name": tournament_name,
        }.items()
        if value is not None
    }
    return payload or None


def fallback_title(milestone_type: str | None) -> str | None:
    if not milestone_type:
        return None
    return milestone_type.replace("_", " ").title()


def public_milestone(row: dict[str, Any]) -> dict[str, Any] | None:
    milestone_type = normalize_milestone_type(row.get("milestone_type"))
    if milestone_type not in ALLOWED_MILESTONE_TYPES:
        return None
    return {
        "type": milestone_type,
        "date": normalize_date(row.get("milestone_date") or row.get("date")),
        "title": clean_text(row.get("title")) or fallback_title(milestone_type),
        "description": clean_text(row.get("description")),
        "tournament": public_tournament(row),
        "weapon": clean_text(row.get("weapon")),
        "evidence": public_evidence(row),
        "source": public_source(row),
    }


def _tournament_id_for_key(row: dict[str, Any]) -> str:
    tournament = row.get("tournament")
    if isinstance(tournament, dict):
        return clean_text(tournament.get("id")) or ""
    return clean_text(row.get("tournament_id")) or ""


def milestone_dedupe_key(row: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    milestone_type = normalize_milestone_type(row.get("milestone_type")) or ""
    milestone_date = normalize_date(row.get("milestone_date") or row.get("date")) or ""
    tournament_id = _tournament_id_for_key(row)
    title = clean_text(row.get("title")) or ""
    weapon = clean_text(row.get("weapon")) or ""
    source_id = clean_text(row.get("source_id") or _metadata(row).get("source_id")) or ""
    return (milestone_type, milestone_date, tournament_id, weapon, title, source_id if not tournament_id else "")


def _dedupe_preference(row: dict[str, Any], canonical_id: str) -> tuple[int, int, str]:
    row_fencer = clean_text(row.get("fencer_id"))
    has_evidence = row.get("evidence") is not None or _metadata(row).get("evidence") is not None
    return (0 if row_fencer == canonical_id else 1, 0 if has_evidence else 1, clean_text(row.get("id")) or "")


def dedupe_milestones(rows: list[dict[str, Any]], canonical_id: str) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    for row in sorted(rows, key=lambda item: _dedupe_preference(item, canonical_id)):
        key = milestone_dedupe_key(row)
        if key[0] in ALLOWED_MILESTONE_TYPES and key not in deduped:
            deduped[key] = row
    return list(deduped.values())


def _source_sort_text(source: Any) -> str:
    if source is None:
        return ""
    if isinstance(source, dict):
        parts = [clean_text(source.get(key)) or "" for key in ("name", "id", "url", "type")]
        return "|".join(parts)
    return clean_text(source) or ""


def milestone_sort_key(row: dict[str, Any]) -> tuple[bool, int, str, str, str, str, str]:
    public = public_milestone(row) or {}
    parsed = _parsed_date(public.get("date"))
    tournament = public.get("tournament") or {}
    return (
        parsed is None,
        -parsed.toordinal() if parsed else 0,
        public.get("type") or "",
        public.get("title") or "",
        tournament.get("name") or "",
        tournament.get("id") or "",
        _source_sort_text(public.get("source")),
    )


def filter_milestones(rows: list[dict[str, Any]], milestone_type: str | None) -> list[dict[str, Any]]:
    if milestone_type is None:
        return rows
    return [row for row in rows if normalize_milestone_type(row.get("milestone_type")) == milestone_type]


def paginated_payload(rows: list[dict[str, Any]], limit: int, offset: int) -> dict[str, Any]:
    page = rows[offset : offset + limit]
    return {
        "data": page,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "count": len(page),
        },
    }


def get_fencer_milestone_timeline(
    client,
    fencer_id: str,
    milestone_type: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    fencer_id = validate_fencer_id(fencer_id)
    milestone_type = validate_milestone_type(milestone_type)
    limit, offset = validate_pagination(limit, offset)

    identity_scope = resolve_fencer_identity(client, fencer_id)
    rows = fetch_milestone_rows(client, identity_scope)
    rows = filter_milestones(rows, milestone_type)
    rows = dedupe_milestones(rows, identity_scope["canonical_id"])
    ordered_public_rows = [
        milestone
        for row in sorted(rows, key=milestone_sort_key)
        if (milestone := public_milestone(row)) is not None
    ]
    return paginated_payload(ordered_public_rows, limit, offset)


def default_get_supabase_client():
    import importlib

    api_module = importlib.import_module("api")
    return api_module.get_supabase_client()


def create_router(get_client: Callable[[], Any] = default_get_supabase_client) -> APIRouter:
    route = APIRouter()

    @route.get("/fencer/{fencer_id}/milestones")
    def fencer_milestones(
        fencer_id: str,
        milestone_type: str | None = None,
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(0, ge=0),
    ):
        return get_fencer_milestone_timeline(
            get_client(),
            fencer_id,
            milestone_type=milestone_type,
            limit=limit,
            offset=offset,
        )

    return route


router = create_router()

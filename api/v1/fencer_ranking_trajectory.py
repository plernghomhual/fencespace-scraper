from __future__ import annotations

import os
import re
import unicodedata
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from season_utils import normalize_season, season_from_string


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

TRAJECTORY_TABLE = "fs_ranking_history_trajectory"
TRAJECTORY_SELECT = (
    "fencer_id,source,season,weapon,gender,category,rank,points,"
    "rank_delta,points_delta,updated_at"
)
DEFAULT_LIMIT = 24
MAX_LIMIT = 100
DEFAULT_SOURCE = "fie"

_FENCER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SOURCE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

_WEAPON_ALIASES = {
    "foil": "Foil",
    "fleuret": "Foil",
    "florett": "Foil",
    "epee": "Epee",
    "degen": "Epee",
    "sabre": "Sabre",
    "saber": "Sabre",
}
_CATEGORY_ALIASES = {
    "senior": "Senior",
    "s": "Senior",
    "junior": "Junior",
    "j": "Junior",
    "u20": "Junior",
    "cadet": "Cadet",
    "c": "Cadet",
    "u17": "Cadet",
    "u18": "Cadet",
    "veteran": "Veteran",
    "v": "Veteran",
    "masters": "Veteran",
}

router = APIRouter(prefix="/fencers", tags=["fencers"])
_supabase_client = None


def get_supabase_client():
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        from supabase import create_client

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ascii_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


def _normalize_source(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    source = text.lower()
    if not _SOURCE_RE.fullmatch(source):
        raise ValueError("source must be a lowercase slug")
    return source


def _normalize_weapon(value: Any, *, strict: bool) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    weapon = _WEAPON_ALIASES.get(_ascii_key(text))
    if weapon is None and strict:
        raise ValueError("weapon must be one of Foil, Epee, or Sabre")
    return weapon or text


def _category_key(value: str) -> str:
    text = value.lower().strip()
    text = text.replace("’", "'")
    text = re.sub(r"\b(men|mens|men's|women|womens|women's|male|female)\b", "", text)
    return _ascii_key(text)


def _normalize_category(value: Any, *, strict: bool) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    category = _CATEGORY_ALIASES.get(_category_key(text))
    if category is None and strict:
        raise ValueError("category must be one of Senior, Junior, Cadet, or Veteran")
    return category or text


def _normalize_season_value(value: Any) -> tuple[str, int] | tuple[None, None]:
    if value is None or value == "":
        return None, None
    normalized = normalize_season(value)
    return normalized, season_from_string(normalized)


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result


def _coerce_positive_int(value: Any) -> int | None:
    result = _coerce_int(value)
    if result is None or result <= 0:
        return None
    return result


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def validate_trajectory_params(
    *,
    fencer_id: str,
    source: str | None = None,
    season: str | int | None = None,
    weapon: str | None = None,
    category: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    cleaned_fencer_id = _clean_text(fencer_id)
    if cleaned_fencer_id is None or not _FENCER_ID_RE.fullmatch(cleaned_fencer_id):
        raise ValueError("fencer_id must be a non-empty safe identifier")

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")

    normalized_season, season_end_year = _normalize_season_value(season)
    return {
        "fencer_id": cleaned_fencer_id,
        "source": _normalize_source(source),
        "season": normalized_season,
        "season_end_year": season_end_year,
        "weapon": _normalize_weapon(weapon, strict=True),
        "category": _normalize_category(category, strict=True),
        "limit": limit,
    }


def _normalize_trajectory_row(row: dict[str, Any]) -> dict[str, Any] | None:
    fencer_id = _clean_text(row.get("fencer_id") or row.get("fie_fencer_id"))
    if fencer_id is None:
        return None

    try:
        source = _normalize_source(row.get("source")) or DEFAULT_SOURCE
        season, season_end_year = _normalize_season_value(row.get("season"))
    except (TypeError, ValueError):
        return None

    weapon = _normalize_weapon(row.get("weapon"), strict=False)
    category = _normalize_category(row.get("category"), strict=False)
    rank = _coerce_positive_int(row.get("rank"))
    if not season or season_end_year is None or not weapon or not category or rank is None:
        return None

    return {
        "fencer_id": fencer_id,
        "source": source,
        "season": season,
        "season_end_year": season_end_year,
        "weapon": weapon,
        "category": category,
        "rank": rank,
        "points": _coerce_float(row.get("points")),
        "rank_delta": _coerce_int(row.get("rank_delta", row.get("rank_change"))),
        "points_delta": _coerce_float(row.get("points_delta", row.get("points_change"))),
        "updated_at": _clean_text(row.get("updated_at") or row.get("computed_at")),
    }


def _row_matches_filters(row: dict[str, Any], params: dict[str, Any]) -> bool:
    if row["fencer_id"] != params["fencer_id"]:
        return False
    for key in ("source", "season", "weapon", "category"):
        if params[key] is not None and row[key] != params[key]:
            return False
    return True


def _public_point(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": row["source"],
        "season": row["season"],
        "season_end_year": row["season_end_year"],
        "weapon": row["weapon"],
        "category": row["category"],
        "rank": row["rank"],
        "points": row["points"],
        "rank_delta": row["rank_delta"],
        "points_delta": row["points_delta"],
        "updated_at": row["updated_at"],
    }


def build_ranking_trajectory_payload(
    rows: list[dict[str, Any]],
    *,
    fencer_id: str,
    source: str | None = None,
    season: str | int | None = None,
    weapon: str | None = None,
    category: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    params = validate_trajectory_params(
        fencer_id=fencer_id,
        source=source,
        season=season,
        weapon=weapon,
        category=category,
        limit=limit,
    )
    normalized_rows = []
    for raw_row in rows:
        row = _normalize_trajectory_row(raw_row)
        if row is not None and _row_matches_filters(row, params):
            normalized_rows.append(row)

    normalized_rows.sort(
        key=lambda row: (
            row["source"],
            row["weapon"],
            row["category"],
            row["season_end_year"],
            row["rank"],
        )
    )
    history = [_public_point(row) for row in normalized_rows[: params["limit"]]]
    return {
        "fencer_id": params["fencer_id"],
        "filters": {
            "source": params["source"],
            "season": params["season"],
            "weapon": params["weapon"],
            "category": params["category"],
            "limit": params["limit"],
        },
        "count": len(history),
        "history": history,
    }


def fetch_ranking_trajectory_rows(client, params: dict[str, Any]) -> list[dict[str, Any]]:
    query = client.table(TRAJECTORY_TABLE).select(TRAJECTORY_SELECT).eq("fencer_id", params["fencer_id"])
    for column in ("source", "season", "weapon", "category"):
        if params[column] is not None:
            query = query.eq(column, params[column])
    return query.execute().data or []


def _is_missing_trajectory_table_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return TRAJECTORY_TABLE in message and (
        "does not exist" in message or "undefinedtable" in message or "42p01" in message
    )


@router.get("/{fencer_id}/ranking-trajectory")
def get_fencer_ranking_trajectory(
    fencer_id: str,
    source: str | None = None,
    season: str | None = None,
    weapon: str | None = None,
    category: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
):
    try:
        params = validate_trajectory_params(
            fencer_id=fencer_id,
            source=source,
            season=season,
            weapon=weapon,
            category=category,
            limit=limit,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        rows = fetch_ranking_trajectory_rows(get_supabase_client(), params)
    except Exception as exc:
        if _is_missing_trajectory_table_error(exc):
            rows = []
        else:
            raise HTTPException(status_code=502, detail="Ranking trajectory query failed") from exc

    return build_ranking_trajectory_payload(
        rows,
        fencer_id=params["fencer_id"],
        source=params["source"],
        season=params["season"],
        weapon=params["weapon"],
        category=params["category"],
        limit=params["limit"],
    )

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/tournaments", tags=["tournaments"])

TOURNAMENT_TABLE = "fs_tournaments"
DETAIL_TABLE = "fs_competition_details"

TOURNAMENT_FIELDS = (
    "id",
    "name",
    "season",
    "start_date",
    "end_date",
    "country",
    "weapon",
    "category",
    "type",
)

ORGANIZER_KEYS = ("organizer", "organiser", "host", "federation", "organization")
FORMAT_KEYS = ("format", "format_type", "competition_format", "formula", "competition_formula")
ENTRY_DEADLINE_KEYS = ("entry_deadline", "registration_deadline", "deadline", "entry_closes_at")
QUOTA_KEYS = ("quota", "entry_quota", "participant_quota", "max_participants", "max_entries")
REGISTRATION_URL_KEYS = ("registration_url", "registration_link", "entry_url", "entry_link")
LIVE_URL_KEYS = ("live_url", "live_results_url", "results_url", "live_link")
SOURCE_URL_KEYS = ("source_url", "detail_url")
SOURCE_TIME_KEYS = ("scraped_at", "updated_at", "last_scraped_at", "last_updated_at")


def get_supabase_client():
    from api import get_supabase_client as get_client

    return get_client()


def validate_tournament_id(tournament_id: str) -> str:
    try:
        return str(UUID(str(tournament_id).strip()))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid tournament ID") from exc


def _execute_first(client, table_name: str, column: str, value: str, *, optional: bool = False) -> dict[str, Any] | None:
    try:
        rows = client.table(table_name).select("*").eq(column, value).limit(1).execute().data or []
    except HTTPException:
        raise
    except Exception as exc:
        if optional:
            return None
        raise HTTPException(status_code=502, detail=f"Supabase query failed for {table_name}") from exc
    return rows[0] if rows else None


def _metadata(row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _rows_with_metadata(rows: Iterable[dict[str, Any] | None]) -> Iterable[dict[str, Any]]:
    for row in rows:
        if isinstance(row, dict):
            yield row
            metadata = _metadata(row)
            if metadata:
                yield metadata


def _values(rows: Iterable[dict[str, Any] | None], keys: Iterable[str]) -> Iterable[Any]:
    for row in _rows_with_metadata(rows):
        for key in keys:
            if key in row:
                yield row.get(key)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict | list | tuple | set):
        return None
    text = str(value).strip()
    return text or None


def _first_text(rows: Iterable[dict[str, Any] | None], keys: Iterable[str]) -> str | None:
    for value in _values(rows, keys):
        text = _clean_text(value)
        if text:
            return text
    return None


def _positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _first_positive_int(rows: Iterable[dict[str, Any] | None], keys: Iterable[str]) -> int | None:
    for value in _values(rows, keys):
        number = _positive_int(value)
        if number is not None:
            return number
    return None


def _normalize_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = _clean_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            return None


def _first_date(rows: Iterable[dict[str, Any] | None], keys: Iterable[str]) -> str | None:
    for value in _values(rows, keys):
        normalized = _normalize_date(value)
        if normalized:
            return normalized
    return None


def _normalize_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat()

    text = _clean_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def _first_datetime(rows: Iterable[dict[str, Any] | None], keys: Iterable[str]) -> str | None:
    for value in _values(rows, keys):
        normalized = _normalize_datetime(value)
        if normalized:
            return normalized
    return None


def _normalize_url(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        parts = urlsplit(text)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return None
        if parts.username or parts.password:
            return None
        netloc = parts.hostname.lower()
        if parts.port is not None:
            netloc = f"{netloc}:{parts.port}"
        return urlunsplit((parts.scheme.lower(), netloc, parts.path, parts.query, parts.fragment))
    except ValueError:
        return None


def _first_url(rows: Iterable[dict[str, Any] | None], keys: Iterable[str]) -> str | None:
    for value in _values(rows, keys):
        normalized = _normalize_url(value)
        if normalized:
            return normalized
    return None


def _tournament_summary(tournament: dict[str, Any]) -> dict[str, Any]:
    summary = {field: tournament.get(field) for field in TOURNAMENT_FIELDS}
    summary["start_date"] = _normalize_date(summary.get("start_date"))
    summary["end_date"] = _normalize_date(summary.get("end_date"))
    return summary


def _venue_payload(tournament: dict[str, Any], details: dict[str, Any] | None) -> dict[str, str | None]:
    rows = (details, tournament)
    return {
        "name": _first_text(rows, ("venue_name", "venue", "location")),
        "city": _first_text(rows, ("venue_city", "city")),
        "country": _first_text(rows, ("venue_country",)),
        "address": _first_text(rows, ("venue_address", "address")),
    }


def build_tournament_detail_payload(
    tournament: dict[str, Any],
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = (details, tournament)
    return {
        "tournament_id": str(tournament.get("id") or (details or {}).get("tournament_id") or ""),
        "tournament": _tournament_summary(tournament),
        "organizer": _first_text(rows, ORGANIZER_KEYS),
        "format": _first_text(rows, FORMAT_KEYS),
        "entry_deadline": _first_date(rows, ENTRY_DEADLINE_KEYS),
        "quota": _first_positive_int(rows, QUOTA_KEYS),
        "venue": _venue_payload(tournament, details),
        "registration_url": _first_url(rows, REGISTRATION_URL_KEYS),
        "live_url": _first_url(rows, LIVE_URL_KEYS),
        "source": {
            "url": _first_url(rows, SOURCE_URL_KEYS),
            "scraped_at": _first_datetime(rows, SOURCE_TIME_KEYS),
        },
    }


def get_tournament_detail_payload(client, tournament_id: str) -> dict[str, Any]:
    normalized_id = validate_tournament_id(tournament_id)
    tournament = _execute_first(client, TOURNAMENT_TABLE, "id", normalized_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    details = _execute_first(client, DETAIL_TABLE, "tournament_id", normalized_id, optional=True)
    return build_tournament_detail_payload(tournament, details)


@router.get("/{tournament_id}/details")
def tournament_details(tournament_id: str):
    return get_tournament_detail_payload(get_supabase_client(), tournament_id)

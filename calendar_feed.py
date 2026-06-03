#!/usr/bin/env python3
"""Generate read-only iCalendar feeds from FenceSpace tournament rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

DEFAULT_RESULT_LIMIT = 250
MAX_RESULT_LIMIT = 500
DEFAULT_TIMEZONE = "UTC"
UID_DOMAIN = "calendar.fencespace.app"
PRODID = "-//FenceSpace//Tournament Calendar//EN"
TOURNAMENT_SELECT_COLUMNS = (
    "id,source_id,name,season,type,country,location,weapon,gender,category,"
    "start_date,end_date,updated_at,metadata"
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
WEAPON_ALIASES = {
    "foil": "Foil",
    "floret": "Foil",
    "epee": "Epee",
    "épée": "Epee",
    "sabre": "Sabre",
    "saber": "Sabre",
}
FEDERATION_ALIASES = {
    "fie": "FIE",
    "fred": "FRED",
    "askfred": "AskFRED",
    "ask fred": "AskFRED",
}
CATEGORY_ALIASES = {
    "senior": "Senior",
    "junior": "Junior",
    "cadet": "Cadet",
    "veteran": "Veteran",
    "youth": "Youth",
}


@dataclass(frozen=True)
class CalendarFeedFilters:
    federation: str | None = None
    country: str | None = None
    weapon: str | None = None
    category: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    timezone_name: str = DEFAULT_TIMEZONE
    limit: int = DEFAULT_RESULT_LIMIT


def _reject_control_chars(value: str, field_name: str) -> None:
    if CONTROL_RE.search(value):
        raise ValueError(f"{field_name} contains control characters")


def _compact(value: str) -> str:
    return " ".join(value.strip().split())


def _normalize_free_text(value: str | None, field_name: str, *, max_length: int = 80) -> str | None:
    if value is None:
        return None
    raw = str(value)
    _reject_control_chars(raw, field_name)
    text = _compact(raw)
    if not text:
        return None
    if len(text) > max_length:
        raise ValueError(f"{field_name} is too long")
    return text


def normalize_weapon(value: str | None) -> str | None:
    text = _normalize_free_text(value, "weapon", max_length=24)
    if text is None:
        return None
    normalized = WEAPON_ALIASES.get(text.casefold())
    if not normalized:
        raise ValueError("weapon must be Foil, Epee, or Sabre")
    return normalized


def normalize_federation(value: str | None) -> str | None:
    text = _normalize_free_text(value, "federation", max_length=80)
    if text is None:
        return None
    alias = FEDERATION_ALIASES.get(text.casefold())
    if alias:
        return alias
    if len(text) <= 6 and text.replace("-", "").isalnum():
        return text.upper()
    return text.title()


def normalize_country(value: str | None) -> str | None:
    text = _normalize_free_text(value, "country", max_length=80)
    if text is None:
        return None
    if len(text) in {2, 3} and text.isalpha():
        return text.upper()
    return text.title()


def normalize_category(value: str | None) -> str | None:
    text = _normalize_free_text(value, "category", max_length=60)
    if text is None:
        return None
    return CATEGORY_ALIASES.get(text.casefold(), text.title())


def _parse_filter_date(value: str | date | datetime | None, field_name: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _normalize_free_text(str(value), field_name, max_length=10)
    if text is None:
        return None
    if not DATE_RE.match(text):
        raise ValueError(f"{field_name} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


def _validate_timezone(timezone_name: str | None) -> str:
    name = _normalize_free_text(timezone_name or DEFAULT_TIMEZONE, "timezone", max_length=64) or DEFAULT_TIMEZONE
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"timezone is not recognized: {name}") from exc
    return name


def validate_calendar_filters(
    *,
    federation: str | None = None,
    country: str | None = None,
    weapon: str | None = None,
    category: str | None = None,
    date_from: str | date | datetime | None = None,
    date_to: str | date | datetime | None = None,
    timezone_name: str | None = DEFAULT_TIMEZONE,
    limit: int | str | None = DEFAULT_RESULT_LIMIT,
) -> CalendarFeedFilters:
    parsed_from = _parse_filter_date(date_from, "date_from")
    parsed_to = _parse_filter_date(date_to, "date_to")
    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise ValueError("date_from must be before or equal to date_to")

    if limit is None:
        parsed_limit = DEFAULT_RESULT_LIMIT
    else:
        try:
            parsed_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit must be a positive integer") from exc
    if parsed_limit < 1:
        raise ValueError("limit must be a positive integer")

    return CalendarFeedFilters(
        federation=normalize_federation(federation),
        country=normalize_country(country),
        weapon=normalize_weapon(weapon),
        category=normalize_category(category),
        date_from=parsed_from,
        date_to=parsed_to,
        timezone_name=_validate_timezone(timezone_name),
        limit=min(parsed_limit, MAX_RESULT_LIMIT),
    )


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _safe_normalize(normalizer, value: Any) -> str | None:
    try:
        return normalizer(value)
    except ValueError:
        return None


def _row_federation(row: dict[str, Any]) -> str | None:
    metadata = _metadata(row)
    value = row.get("federation") or row.get("type") or metadata.get("federation") or metadata.get("source")
    return _safe_normalize(normalize_federation, str(value)) if value else None


def _row_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if DATE_RE.match(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _event_dates(row: dict[str, Any]) -> tuple[date, date] | None:
    start = _row_date(row.get("start_date"))
    if not start:
        return None
    end = _row_date(row.get("end_date")) or start
    if end < start:
        start, end = end, start
    return start, end


def tournament_matches_filters(row: dict[str, Any], filters: CalendarFeedFilters) -> bool:
    dates = _event_dates(row)
    if not dates:
        return False
    start, end = dates
    if filters.date_from and end < filters.date_from:
        return False
    if filters.date_to and start > filters.date_to:
        return False

    if filters.federation and (_row_federation(row) or "").casefold() != filters.federation.casefold():
        return False
    if filters.country and (_safe_normalize(normalize_country, row.get("country")) or "").casefold() != filters.country.casefold():
        return False
    if filters.weapon and (_safe_normalize(normalize_weapon, row.get("weapon")) or "").casefold() != filters.weapon.casefold():
        return False
    if filters.category and (
        _safe_normalize(normalize_category, row.get("category")) or ""
    ).casefold() != filters.category.casefold():
        return False
    return True


def filter_tournaments(rows: Iterable[dict[str, Any]], filters: CalendarFeedFilters) -> list[dict[str, Any]]:
    matched = [row for row in rows if tournament_matches_filters(row, filters)]
    matched.sort(
        key=lambda row: (
            _event_dates(row)[0],  # type: ignore[index]
            str(row.get("name") or ""),
            tournament_uid(row),
        )
    )
    return matched[: filters.limit]


def tournament_uid(row: dict[str, Any]) -> str:
    if row.get("source_id"):
        seed = f"source_id:{row['source_id']}"
    elif row.get("id"):
        seed = f"id:{row['id']}"
    else:
        dates = _event_dates(row)
        start = dates[0].isoformat() if dates else ""
        pieces = [
            str(row.get("name") or ""),
            start,
            str(row.get("country") or ""),
            str(row.get("weapon") or ""),
            str(row.get("category") or ""),
        ]
        seed = "fallback:" + "|".join(pieces)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    return f"fencespace-{digest}@{UID_DOMAIN}"


def _escape_ics_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", "\\n")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    return text


def _fold_ics_line(line: str) -> str:
    if len(line.encode("utf-8")) <= 75:
        return line
    chunks: list[str] = []
    current = ""
    current_len = 0
    for char in line:
        char_len = len(char.encode("utf-8"))
        limit = 75 if not chunks else 74
        if current and current_len + char_len > limit:
            chunks.append(current)
            current = char
            current_len = char_len
        else:
            current += char
            current_len += char_len
    if current:
        chunks.append(current)
    return "\r\n ".join(chunks)


def _ical_line(name: str, value: Any) -> str:
    return _fold_ics_line(f"{name}:{value}")


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_datetime(value: Any, timezone_name: str) -> tuple[datetime | date, bool] | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo(timezone_name))
        return value, False
    if isinstance(value, date):
        return value, True

    text = str(value).strip()
    if DATE_RE.match(text):
        try:
            return date.fromisoformat(text), True
        except ValueError:
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed, False


def _date_line(prefix: str, value: datetime | date, is_all_day: bool) -> str:
    if is_all_day:
        return f"{prefix};VALUE=DATE:{value.strftime('%Y%m%d')}"
    assert isinstance(value, datetime)
    return f"{prefix}:{_format_utc(value)}"


def _last_modified(row: dict[str, Any], generated_at: datetime) -> str:
    parsed = _parse_datetime(row.get("updated_at"), DEFAULT_TIMEZONE)
    if parsed and not parsed[1]:
        assert isinstance(parsed[0], datetime)
        return _format_utc(parsed[0])
    return _format_utc(generated_at)


def _event_lines(row: dict[str, Any], filters: CalendarFeedFilters, generated_at: datetime) -> list[str]:
    start = _parse_datetime(row.get("start_date"), filters.timezone_name)
    if not start:
        return []
    end = _parse_datetime(row.get("end_date"), filters.timezone_name) or start

    lines = [
        "BEGIN:VEVENT",
        _ical_line("UID", tournament_uid(row)),
        _ical_line("DTSTAMP", _format_utc(generated_at)),
        _date_line("DTSTART", start[0], start[1]),
    ]

    if start[1]:
        end_date = end[0] if isinstance(end[0], date) and not isinstance(end[0], datetime) else start[0]
        assert isinstance(end_date, date)
        if end_date < start[0]:
            end_date = start[0]  # type: ignore[assignment]
        lines.append(_date_line("DTEND", end_date + timedelta(days=1), True))
    else:
        start_dt = start[0]
        end_dt = end[0]
        assert isinstance(start_dt, datetime)
        if isinstance(end_dt, datetime) and end_dt > start_dt:
            lines.append(_date_line("DTEND", end_dt, False))

    lines.extend(
        [
            _ical_line("LAST-MODIFIED", _last_modified(row, generated_at)),
            _ical_line("SUMMARY", _escape_ics_text(row.get("name") or "FenceSpace Tournament")),
            _ical_line("STATUS", "CONFIRMED"),
            _ical_line("TRANSP", "TRANSPARENT"),
        ]
    )

    location = ", ".join(str(part) for part in (row.get("location"), row.get("country")) if part)
    if location:
        lines.append(_ical_line("LOCATION", _escape_ics_text(location)))

    description_parts = [
        part
        for part in (
            row.get("type"),
            row.get("weapon"),
            row.get("gender"),
            row.get("category"),
            f"Season {row.get('season')}" if row.get("season") else None,
        )
        if part
    ]
    if description_parts:
        lines.append(_ical_line("DESCRIPTION", _escape_ics_text(" | ".join(str(part) for part in description_parts))))

    categories = [part for part in (_row_federation(row), row.get("weapon"), row.get("category")) if part]
    if categories:
        lines.append(_ical_line("CATEGORIES", ",".join(_escape_ics_text(part) for part in categories)))

    metadata = _metadata(row)
    url = row.get("url") or metadata.get("url")
    if url:
        lines.append(_ical_line("URL", _escape_ics_text(url)))

    lines.append("END:VEVENT")
    return lines


def generate_ics_feed(
    rows: Iterable[dict[str, Any]],
    *,
    filters: CalendarFeedFilters | None = None,
    generated_at: datetime | None = None,
    calendar_name: str = "FenceSpace Tournaments",
) -> str:
    filters = filters or validate_calendar_filters()
    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        _ical_line("PRODID", PRODID),
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _ical_line("X-WR-CALNAME", _escape_ics_text(calendar_name)),
        _ical_line("X-WR-TIMEZONE", filters.timezone_name),
    ]
    for row in filter_tournaments(rows, filters):
        lines.extend(_event_lines(row, filters, generated_at))
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def configure_tournament_query(query, filters: CalendarFeedFilters):
    query = query.select(TOURNAMENT_SELECT_COLUMNS)
    if filters.federation:
        query = query.eq("type", filters.federation)
    if filters.country:
        query = query.eq("country", filters.country)
    if filters.weapon:
        query = query.eq("weapon", filters.weapon)
    if filters.category:
        query = query.eq("category", filters.category)
    if filters.date_from:
        query = query.gte("start_date", filters.date_from.isoformat())
    if filters.date_to:
        query = query.lte("start_date", filters.date_to.isoformat())
    return query.order("start_date").range(0, filters.limit - 1)


def fetch_tournaments(client, filters: CalendarFeedFilters) -> list[dict[str, Any]]:
    query = configure_tournament_query(client.table("fs_tournaments"), filters)
    return query.execute().data or []


def generate_ics_feed_from_client(
    client,
    *,
    federation: str | None = None,
    country: str | None = None,
    weapon: str | None = None,
    category: str | None = None,
    date_from: str | date | datetime | None = None,
    date_to: str | date | datetime | None = None,
    timezone_name: str | None = DEFAULT_TIMEZONE,
    limit: int | str | None = DEFAULT_RESULT_LIMIT,
    calendar_name: str = "FenceSpace Tournaments",
    generated_at: datetime | None = None,
) -> str:
    filters = validate_calendar_filters(
        federation=federation,
        country=country,
        weapon=weapon,
        category=category,
        date_from=date_from,
        date_to=date_to,
        timezone_name=timezone_name,
        limit=limit,
    )
    return generate_ics_feed(
        fetch_tournaments(client, filters),
        filters=filters,
        generated_at=generated_at,
        calendar_name=calendar_name,
    )


def _read_input_rows(path: str) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text())
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        payload = payload["data"]
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ValueError("--input must contain a JSON array of tournament rows or an object with a data array")
    return payload


def _write_output(content: str, output_path: str | None) -> None:
    if output_path:
        Path(output_path).write_text(content)
    else:
        sys.stdout.write(content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a FenceSpace tournament iCalendar feed")
    parser.add_argument("--input", help="JSON tournament rows. Defaults to querying fs_tournaments from Supabase.")
    parser.add_argument("--output", help="Output .ics path. Defaults to stdout.")
    parser.add_argument("--calendar-name", default="FenceSpace Tournaments")
    parser.add_argument("--federation", help="Federation/source filter. Supabase queries map this to fs_tournaments.type.")
    parser.add_argument("--country", help="Country name or 2/3-letter code.")
    parser.add_argument("--weapon", help="Foil, Epee, or Sabre.")
    parser.add_argument("--category", help="Tournament category, such as Senior, Junior, Cadet, or Veteran.")
    parser.add_argument("--from-date", dest="date_from", help="Inclusive lower date bound, YYYY-MM-DD.")
    parser.add_argument("--to-date", dest="date_to", help="Inclusive upper date bound, YYYY-MM-DD.")
    parser.add_argument("--timezone", dest="timezone_name", default=DEFAULT_TIMEZONE, help="IANA timezone name.")
    parser.add_argument("--limit", type=int, default=DEFAULT_RESULT_LIMIT, help=f"Max events, capped at {MAX_RESULT_LIMIT}.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        filters = validate_calendar_filters(
            federation=args.federation,
            country=args.country,
            weapon=args.weapon,
            category=args.category,
            date_from=args.date_from,
            date_to=args.date_to,
            timezone_name=args.timezone_name,
            limit=args.limit,
        )
        rows = _read_input_rows(args.input) if args.input else fetch_tournaments(get_supabase_client(), filters)
        content = generate_ics_feed(rows, filters=filters, calendar_name=args.calendar_name)
    except ValueError as exc:
        parser.error(str(exc))
    _write_output(content, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

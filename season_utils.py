import re
from datetime import UTC, datetime, timezone

_SEASON_RE = re.compile(r"^(\d{4})(?:-(\d{4}))?$")


def season_to_string(season_int: int) -> str:
    """Convert an end-year season integer to a YYYY-YYYY range."""
    if isinstance(season_int, bool) or not isinstance(season_int, int):
        raise TypeError("season_int must be an integer year")
    if season_int < 1000 or season_int > 9999:
        raise ValueError("season_int must be a four-digit year")
    return f"{season_int - 1:04d}-{season_int:04d}"


def season_from_string(season_str: str) -> int:
    """Convert YYYY-YYYY or YYYY to the end-year season integer."""
    if not isinstance(season_str, str):
        raise TypeError("season_str must be a string")

    value = season_str.strip()
    match = _SEASON_RE.fullmatch(value)
    if not match:
        raise ValueError(f"invalid season format: {season_str!r}")

    start_raw, end_raw = match.groups()
    if end_raw is None:
        return int(start_raw)

    start_year = int(start_raw)
    end_year = int(end_raw)
    if end_year != start_year + 1:
        raise ValueError(f"invalid season range: {season_str!r}")
    return end_year


def current_fie_season() -> int:
    now = datetime.now(UTC)
    return now.year if now.month >= 7 else now.year - 1


def normalize_season(raw) -> str:
    if isinstance(raw, bool):
        raise TypeError("season must be an integer year or string")
    if isinstance(raw, int):
        return season_to_string(raw)
    if isinstance(raw, str):
        return season_to_string(season_from_string(raw))
    raise TypeError("season must be an integer year or string")

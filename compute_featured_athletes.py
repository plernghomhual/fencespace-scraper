from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter
from datetime import UTC, date, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SOURCE = "compute_featured_athletes"
PAGE_SIZE = 1000
BATCH_SIZE = 100
DEFAULT_LIMIT = 24

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

FENCER_SELECTS = (
    "id,fie_id,name,country,weapon,category,world_rank,fie_points,image_url,bio_text,metadata,active,is_active,retired,is_retired,status",
    "id,fie_id,name,country,weapon,category,world_rank,fie_points,image_url,metadata,active,is_active,retired,is_retired,status",
    "id,fie_id,name,country,weapon,category,world_rank,fie_points,image_url,metadata",
    "id,fie_id,name,country,weapon,category,world_rank,fie_points",
)
IDENTITY_SELECTS = (
    "id,canonical_name,country,fie_ids,fs_fencer_row_ids,metadata",
    "id,canonical_name,country,fie_ids,fs_fencer_row_ids",
)
STATS_SELECTS = (
    "identity_id,weapon,category,total_bouts,last_bout_at,updated_at",
    "identity_id,weapon,category,total_bouts,updated_at",
)
RANKING_SELECTS = (
    "fencer_id,fie_fencer_id,fie_id,season,country,weapon,gender,category,rank,points,name,scraped_at",
    "fencer_id,fie_fencer_id,season,country,weapon,gender,category,rank,points,name,scraped_at",
    "fie_fencer_id,season,country,weapon,gender,category,rank,points,name,scraped_at",
)
RESULT_SELECTS = (
    "fencer_id,fie_fencer_id,tournament_id,country,nationality,rank,placement,medal,name,weapon,category",
    "fencer_id,fie_fencer_id,tournament_id,nationality,rank,placement,medal,name",
    "fie_fencer_id,tournament_id,nationality,rank,placement,medal,name",
)
TOURNAMENT_SELECTS = (
    "id,start_date,end_date,season,weapon,gender,category,type,name",
    "id,start_date,end_date,season,weapon,category,type,name",
    "id,start_date,end_date,season",
)

MEDAL_POINTS = {"gold": 30.0, "silver": 20.0, "bronze": 12.0}
MEDAL_BY_RANK = {1: "gold", 2: "silver", 3: "bronze"}
PRIVATE_FLAGS = {
    "private",
    "is_private",
    "unsafe",
    "do_not_feature",
    "exclude_from_featured",
    "restricted",
}
RETIRED_FLAGS = {"retired", "is_retired", "inactive", "is_inactive"}


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    aliases = {
        "USA": "USA",
        "US": "USA",
        "UNITED STATES": "USA",
        "UNITED STATES OF AMERICA": "USA",
        "KOR": "Korea",
        "KOREA": "Korea",
        "SOUTH KOREA": "Korea",
        "GBR": "Great Britain",
        "GB": "Great Britain",
    }
    key = re.sub(r"\s+", " ", text.upper().replace(".", ""))
    return aliases.get(key, text)


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


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    number: int | None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        number = int(match.group(0)) if match else None
    return number


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        return float(match.group(0)) if match else None


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def parse_list(value: Any) -> list[str]:
    value = parse_jsonish(value)
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip("{}")
        parts = value.split(",") if "," in value else [value]
    elif isinstance(value, list | tuple | set):
        parts = list(value)
    else:
        return []
    return sorted({text for item in parts if (text := clean_text(item))})


def parse_mapping(value: Any) -> dict[str, Any]:
    value = parse_jsonish(value)
    return value if isinstance(value, dict) else {}


def parse_datetime(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        if re.fullmatch(r"\d{4}", text):
            return datetime(int(text), 6, 30, tzinfo=UTC)
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if isinstance(parsed, datetime):
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None
    return None


def date_text(value: datetime | None) -> str | None:
    return value.date().isoformat() if value else None


def days_old(value: datetime | None, reference: datetime) -> int | None:
    if not value:
        return None
    return (reference.date() - value.date()).days


def is_false(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in {"false", "0", "no", "n"}
    return False


def is_true(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, int | float) and value == 1:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "yes", "y"}
    return False


def has_private_flag(row: dict[str, Any]) -> bool:
    metadata = parse_mapping(row.get("metadata"))
    for source in (row, metadata):
        for key in PRIVATE_FLAGS:
            if is_true(source.get(key)):
                return True
        if is_false(source.get("public_profile")):
            return True
        privacy = clean_text(source.get("privacy") or source.get("visibility"))
        if privacy and privacy.casefold() in {"private", "restricted", "unsafe"}:
            return True
    return False


def has_retired_flag(row: dict[str, Any]) -> bool:
    metadata = parse_mapping(row.get("metadata"))
    for source in (row, metadata):
        for key in RETIRED_FLAGS:
            if is_true(source.get(key)):
                return True
        if is_false(source.get("active")) or is_false(source.get("is_active")):
            return True
        status = clean_text(source.get("status"))
        if status and re.search(r"\b(retired|inactive)\b", status, flags=re.IGNORECASE):
            return True
    return False


def rank_score(rank: int | None) -> float:
    if rank is None or rank <= 0 or rank > 64:
        return 0.0
    return round(40.0 * (65 - rank) / 64.0, 3)


def medal_bucket(result: dict[str, Any]) -> str | None:
    medal = normalize_key(result.get("medal"))
    if medal in MEDAL_POINTS:
        return medal
    rank = to_int(result.get("rank") if result.get("rank") is not None else result.get("placement"))
    return MEDAL_BY_RANK.get(rank) if rank is not None else None


def medal_recency_multiplier(result_date: datetime | None, reference: datetime) -> float:
    age = days_old(result_date, reference)
    if age is None:
        return 0.5
    if age <= 365:
        return 1.0
    if age <= 730:
        return 0.6
    if age <= 1095:
        return 0.3
    return 0.1


def fetch_all(client, table: str, columns: str, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
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
            return rows
        offset += page_size


def fetch_with_fallbacks(
    client,
    table: str,
    select_options: tuple[str, ...],
    *,
    page_size: int,
    optional: bool = False,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in select_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    if optional:
        print(f"Optional source {table} unavailable: {last_error}")
        return []
    if last_error:
        raise last_error
    return []


def display_completeness(row: dict[str, Any]) -> tuple[int, int, str]:
    rank = to_int(row.get("world_rank"))
    score = 0
    score += 1 if clean_text(row.get("name")) else 0
    score += 1 if normalize_country(row.get("country")) else 0
    score += 1 if normalize_weapon(row.get("weapon")) else 0
    score += 1 if rank is not None else 0
    score += 1 if has_bio(row) else 0
    score += 1 if has_image(row) else 0
    return (-score, rank if rank is not None else 999999, clean_text(row.get("id")) or "")


def has_bio(row: dict[str, Any]) -> bool:
    return bool(clean_text(row.get("bio_text")))


def has_image(row: dict[str, Any]) -> bool:
    return bool(clean_text(row.get("image_url")))


def build_candidate_groups(
    fencers: list[dict[str, Any]],
    identities: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, str],
    dict[str, str],
    dict[tuple[str, str], str],
]:
    fencers_by_id = {
        fencer_id: row
        for row in fencers
        if (fencer_id := clean_text(row.get("id")))
    }
    groups: dict[str, dict[str, Any]] = {}
    fencer_to_key: dict[str, str] = {}
    fie_to_key: dict[str, str] = {}
    name_country_to_key: dict[tuple[str, str], str] = {}

    for identity in sorted(identities, key=lambda row: clean_text(row.get("id")) or ""):
        identity_id = clean_text(identity.get("id"))
        if not identity_id:
            continue
        members = parse_list(identity.get("fs_fencer_row_ids") or identity.get("fencer_ids"))
        member_rows = [fencers_by_id[member] for member in members if member in fencers_by_id]
        candidate_key = f"identity:{identity_id}"
        groups[candidate_key] = {
            "candidate_key": candidate_key,
            "identity_id": identity_id,
            "identity": identity,
            "fencers": member_rows,
        }
        for member in members:
            fencer_to_key[member] = candidate_key
        for fie_id in parse_list(identity.get("fie_ids")):
            fie_to_key.setdefault(fie_id, candidate_key)

    for fencer_id, row in sorted(fencers_by_id.items()):
        _maybe_key: str | None = fencer_to_key.get(fencer_id)
        if not _maybe_key:
            _maybe_key = f"fencer:{fencer_id}"
            groups[_maybe_key] = {
                "candidate_key": _maybe_key,
                "identity_id": None,
                "identity": {},
                "fencers": [row],
            }
            fencer_to_key[fencer_id] = _maybe_key
        candidate_key = _maybe_key
        fencer_fie_id: str | None = clean_text(row.get("fie_id"))
        if fencer_fie_id and candidate_key:
            fie_to_key.setdefault(fencer_fie_id, candidate_key)
        name = clean_text(row.get("name"))
        country = normalize_country(row.get("country"))
        if name and country and candidate_key:
            name_country_to_key.setdefault((normalize_key(name), normalize_key(country)), candidate_key)

    return groups, fencer_to_key, fie_to_key, name_country_to_key


def candidate_key_for_row(
    row: dict[str, Any],
    *,
    fencer_to_key: dict[str, str],
    fie_to_key: dict[str, str],
    name_country_to_key: dict[tuple[str, str], str],
) -> str | None:
    fencer_id = clean_text(row.get("fencer_id"))
    if fencer_id and fencer_id in fencer_to_key:
        return fencer_to_key[fencer_id]
    fie_id = clean_text(row.get("fie_fencer_id") or row.get("fie_id"))
    if fie_id and fie_id in fie_to_key:
        return fie_to_key[fie_id]
    name = clean_text(row.get("name"))
    country = normalize_country(row.get("country") or row.get("nationality"))
    if name and country:
        return name_country_to_key.get((normalize_key(name), normalize_key(country)))
    return None


def update_best_rank(candidate: dict[str, Any], row: dict[str, Any]) -> None:
    rank = to_int(row.get("rank") if row.get("rank") is not None else row.get("world_rank"))
    if rank is None or rank <= 0:
        return
    season = to_int(row.get("season"))
    current = candidate.get("best_rank")
    current_season = candidate.get("best_rank_season")
    if (
        current is None
        or rank < current
        or (rank == current and (season or 0) > (current_season or 0))
    ):
        candidate["best_rank"] = rank
        candidate["best_rank_season"] = season
        candidate["best_rank_weapon"] = normalize_weapon(row.get("weapon")) or candidate.get("weapon")
        candidate["best_rank_category"] = clean_text(row.get("category")) or candidate.get("category")
        candidate["points"] = to_float(row.get("points"))


def result_date(result: dict[str, Any], tournaments_by_id: dict[str, dict[str, Any]]) -> datetime | None:
    direct = parse_datetime(
        result.get("date")
        or result.get("result_date")
        or result.get("competition_date")
        or result.get("created_at")
    )
    if direct:
        return direct
    tournament_id = clean_text(result.get("tournament_id"))
    tournament = tournaments_by_id.get(tournament_id) if tournament_id else None
    if not tournament:
        return None
    return parse_datetime(tournament.get("end_date") or tournament.get("start_date") or tournament.get("season"))


def initialize_candidate(group: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    fencer_rows = sorted(group["fencers"], key=display_completeness)
    identity = group.get("identity") or {}
    if has_private_flag(identity) or has_retired_flag(identity):
        return None, True
    if any(has_private_flag(row) or has_retired_flag(row) for row in fencer_rows):
        return None, True
    display_row = fencer_rows[0] if fencer_rows else {}
    display_name = clean_text(identity.get("canonical_name")) or clean_text(display_row.get("name"))
    if not display_name:
        return None, True
    fencer_id = clean_text(display_row.get("id"))
    if not fencer_id:
        return None, True

    country = normalize_country(identity.get("country")) or normalize_country(display_row.get("country"))
    weapon = normalize_weapon(display_row.get("weapon"))
    candidate = {
        "candidate_key": group["candidate_key"],
        "identity_id": group.get("identity_id"),
        "fencer_id": fencer_id,
        "display_name": display_name,
        "country": country,
        "weapon": weapon,
        "category": clean_text(display_row.get("category")),
        "best_rank": None,
        "best_rank_season": None,
        "best_rank_weapon": None,
        "best_rank_category": None,
        "points": None,
        "medals": Counter(),
        "medal_score": 0.0,
        "recent_medals": 0,
        "results_last_365_days": 0,
        "last_result_at": None,
        "last_bout_at": None,
        "total_bouts": 0,
        "has_stats": False,
        "has_bio": any(has_bio(row) for row in fencer_rows),
        "has_image": any(has_image(row) for row in fencer_rows),
    }
    update_best_rank(candidate, display_row)
    return candidate, False


def score_candidate(candidate: dict[str, Any], reference: datetime) -> tuple[float, list[str]]:
    best_rank = candidate.get("best_rank")
    ranking = rank_score(best_rank)
    activity = min(10.0, float(candidate["total_bouts"]) * 0.5)
    activity += min(8.0, float(candidate["results_last_365_days"]) * 2.0)

    completeness = 0.0
    completeness += 3.0 if candidate.get("country") else 0.0
    completeness += 3.0 if candidate.get("weapon") else 0.0
    completeness += 3.0 if best_rank is not None else 0.0
    completeness += 4.0 if candidate.get("has_bio") else 0.0
    completeness += 2.0 if candidate.get("has_image") else 0.0
    completeness += 3.0 if candidate.get("has_stats") else 0.0

    reasons: list[str] = []
    if candidate["medals"]["gold"]:
        reasons.append("recent_gold_medal")
    if candidate["medals"]["silver"]:
        reasons.append("recent_silver_medal")
    if candidate["medals"]["bronze"]:
        reasons.append("recent_bronze_medal")
    if best_rank is not None and best_rank <= 5:
        reasons.append("top_5_world_rank")
    elif best_rank is not None and best_rank <= 16:
        reasons.append("top_16_world_rank")
    elif best_rank is not None and best_rank <= 64:
        reasons.append("ranked_top_64")
    if candidate["results_last_365_days"] > 0 or recent_datetime(candidate.get("last_bout_at"), reference):
        reasons.append("active_recent_results")
    if completeness >= 18.0:
        reasons.append("complete_public_profile")

    score = ranking + candidate["medal_score"] + activity + completeness
    return round(score, 3), reasons


def recent_datetime(value: datetime | None, reference: datetime | None = None) -> bool:
    if value is None:
        return False
    reference = reference or datetime.now(UTC)
    age = days_old(value, reference)
    return age is not None and age <= 365


def rank_context(candidate: dict[str, Any]) -> dict[str, Any]:
    if candidate.get("best_rank") is None:
        return {}
    context = {
        "best_rank": candidate["best_rank"],
        "best_rank_season": candidate.get("best_rank_season"),
        "best_rank_weapon": candidate.get("best_rank_weapon") or candidate.get("weapon"),
        "best_rank_category": candidate.get("best_rank_category"),
    }
    if candidate.get("points") is not None:
        context["points"] = candidate["points"]
    return {key: value for key, value in context.items() if value is not None}


def recency_context(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "last_result_date": date_text(candidate.get("last_result_at")),
        "last_bout_at": candidate["last_bout_at"].isoformat() if candidate.get("last_bout_at") else None,
        "recent_medals": int(candidate["recent_medals"]),
        "results_last_365_days": int(candidate["results_last_365_days"]),
    }


def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    recency = row.get("recency") or {}
    last_date = parse_datetime(recency.get("last_result_date"))
    best_rank = row.get("rank_context", {}).get("best_rank")
    return (
        -float(row["score"]),
        best_rank if best_rank is not None else 999999,
        -last_date.timestamp() if last_date else 0.0,
        row["display_name"].casefold(),
        row["candidate_key"],
    )


def apply_diversity_caps(
    rows: list[dict[str, Any]],
    *,
    limit: int,
    enforce_diversity: bool,
    max_per_country: int | None,
    max_per_weapon: int | None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    country_counts: Counter[str] = Counter()
    weapon_counts: Counter[str] = Counter()
    for row in rows:
        if len(selected) >= limit:
            break
        country = row.get("country")
        weapon = row.get("weapon")
        if enforce_diversity:
            if max_per_country is not None and country and country_counts[country] >= max_per_country:
                continue
            if max_per_weapon is not None and weapon and weapon_counts[weapon] >= max_per_weapon:
                continue
        selected.append(row)
        if country:
            country_counts[country] += 1
        if weapon:
            weapon_counts[weapon] += 1
    for index, row in enumerate(selected, 1):
        row["selection_rank"] = index
        row["selected"] = True
    return selected


def build_featured_athlete_rows(
    *,
    fencers: list[dict[str, Any]],
    identities: list[dict[str, Any]],
    stats: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    results: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    limit: int = DEFAULT_LIMIT,
    max_per_country: int | None = 2,
    max_per_weapon: int | None = 3,
    enforce_diversity: bool = True,
    updated_at: str | None = None,
    reference_date: str | datetime | date | None = None,
) -> tuple[list[dict[str, Any]], int]:
    now = updated_at or datetime.now(UTC).isoformat()
    if isinstance(reference_date, datetime):
        reference = reference_date if reference_date.tzinfo else reference_date.replace(tzinfo=UTC)
    elif isinstance(reference_date, date):
        reference = datetime.combine(reference_date, datetime.min.time(), tzinfo=UTC)
    else:
        reference = parse_datetime(reference_date) or datetime.now(UTC)

    groups, fencer_to_key, fie_to_key, name_country_to_key = build_candidate_groups(fencers, identities)
    candidates: dict[str, dict[str, Any]] = {}
    skipped = 0
    for key, group in sorted(groups.items()):
        candidate, was_skipped = initialize_candidate(group)
        if was_skipped:
            skipped += 1
        if candidate:
            candidates[key] = candidate

    for row in rankings:
        ranking_key: str | None = candidate_key_for_row(
            row,
            fencer_to_key=fencer_to_key,
            fie_to_key=fie_to_key,
            name_country_to_key=name_country_to_key,
        )
        candidate = candidates.get(ranking_key or "")
        if not candidate:
            continue
        candidate["country"] = candidate.get("country") or normalize_country(row.get("country"))
        candidate["weapon"] = candidate.get("weapon") or normalize_weapon(row.get("weapon"))
        candidate["category"] = candidate.get("category") or clean_text(row.get("category"))
        update_best_rank(candidate, row)

    stats_by_identity: dict[str, list[dict[str, Any]]] = {clean_text(row.get("identity_id")): [] for row in stats if clean_text(row.get("identity_id"))}  # type: ignore[misc]
    for row in stats:
        identity_id = clean_text(row.get("identity_id"))
        if identity_id in stats_by_identity:
            stats_by_identity[identity_id].append(row)
    for candidate in candidates.values():
        for stat in stats_by_identity.get(candidate.get("identity_id") or "", []):
            candidate["has_stats"] = True
            candidate["total_bouts"] += max(to_int(stat.get("total_bouts")) or 0, 0)
            candidate["weapon"] = candidate.get("weapon") or normalize_weapon(stat.get("weapon"))
            last_bout = parse_datetime(stat.get("last_bout_at") or stat.get("updated_at"))
            if last_bout and (
                candidate["last_bout_at"] is None or last_bout > candidate["last_bout_at"]
            ):
                candidate["last_bout_at"] = last_bout

    tournaments_by_id = {
        tournament_id: row
        for row in tournaments
        if (tournament_id := clean_text(row.get("id")))
    }
    for result in results:
        result_key: str | None = candidate_key_for_row(
            result,
            fencer_to_key=fencer_to_key,
            fie_to_key=fie_to_key,
            name_country_to_key=name_country_to_key,
        )
        candidate = candidates.get(result_key or "")
        if not candidate:
            continue
        tournament_id = clean_text(result.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id) if tournament_id else None
        candidate["country"] = candidate.get("country") or normalize_country(result.get("country") or result.get("nationality"))
        candidate["weapon"] = (
            candidate.get("weapon")
            or normalize_weapon(result.get("weapon"))
            or normalize_weapon(tournament.get("weapon") if tournament else None)
        )
        candidate["category"] = candidate.get("category") or clean_text(result.get("category"))

        occurred_at = result_date(result, tournaments_by_id)
        if occurred_at:
            if candidate["last_result_at"] is None or occurred_at > candidate["last_result_at"]:
                candidate["last_result_at"] = occurred_at
            age = days_old(occurred_at, reference)
            if age is not None and 0 <= age <= 365:
                candidate["results_last_365_days"] += 1

        medal = medal_bucket(result)
        if medal:
            multiplier = medal_recency_multiplier(occurred_at, reference)
            candidate["medal_score"] = min(
                50.0,
                candidate["medal_score"] + (MEDAL_POINTS[medal] * multiplier),
            )
            if occurred_at is None or (days_old(occurred_at, reference) or 0) <= 365:
                candidate["medals"][medal] += 1
                candidate["recent_medals"] += 1

    scored_rows: list[dict[str, Any]] = []
    for candidate in candidates.values():
        score, reasons = score_candidate(candidate, reference)
        row = {
            "candidate_key": candidate["candidate_key"],
            "identity_id": candidate.get("identity_id"),
            "fencer_id": candidate["fencer_id"],
            "display_name": candidate["display_name"],
            "country": candidate.get("country"),
            "weapon": candidate.get("weapon"),
            "score": score,
            "reasons": reasons,
            "rank_context": rank_context(candidate),
            "recency": recency_context(candidate),
            "selected": False,
            "selection_rank": None,
            "updated_at": now,
        }
        scored_rows.append(row)

    ranked = sorted(scored_rows, key=sort_key)
    return (
        apply_diversity_caps(
            ranked,
            limit=limit,
            enforce_diversity=enforce_diversity,
            max_per_country=max_per_country,
            max_per_weapon=max_per_weapon,
        ),
        skipped,
    )


def batch_upsert(client, rows: list[dict[str, Any]], *, batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_featured_athlete_candidates").upsert(
            batch,
            on_conflict="candidate_key",
        ).execute()
        written += len(batch)
    return written


def compute_featured_athletes(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    limit: int = DEFAULT_LIMIT,
    max_per_country: int | None = 2,
    max_per_weapon: int | None = 3,
    enforce_diversity: bool = True,
    updated_at: str | None = None,
    reference_date: str | datetime | date | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
        identities = fetch_with_fallbacks(
            client,
            "fs_fencer_identities",
            IDENTITY_SELECTS,
            page_size=page_size,
            optional=True,
        )
        stats = fetch_with_fallbacks(
            client,
            "fs_fencer_stats",
            STATS_SELECTS,
            page_size=page_size,
            optional=True,
        )
        rankings = fetch_with_fallbacks(client, "fs_rankings_history", RANKING_SELECTS, page_size=page_size)
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
        rows, skipped = build_featured_athlete_rows(
            fencers=fencers,
            identities=identities,
            stats=stats,
            rankings=rankings,
            results=results,
            tournaments=tournaments,
            limit=limit,
            max_per_country=max_per_country,
            max_per_weapon=max_per_weapon,
            enforce_diversity=enforce_diversity,
            updated_at=updated_at,
            reference_date=reference_date,
        )
        written = batch_upsert(client, rows, batch_size=batch_size) if rows else 0
        summary = {
            "fencers_read": len(fencers),
            "identity_rows": len(identities),
            "stats_read": len(stats),
            "rankings_read": len(rankings),
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "candidate_rows": len(rows),
            "written": written,
            "skipped": skipped,
        }
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": datetime.now(UTC).isoformat(), **summary})
        if run_log:
            run_log.complete(written=written, failed=0, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Featured athlete computation starting - {datetime.now(UTC).isoformat()}")
    previous = get_state(SOURCE, "last_run")
    if previous:
        print(f"Previous featured athlete state: {previous}")
    summary = compute_featured_athletes()
    print(
        "Featured athlete computation complete - "
        f"{summary['candidate_rows']} rows built, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} candidates skipped"
    )


if __name__ == "__main__":
    main()

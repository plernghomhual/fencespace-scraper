import hashlib
import math
import os
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_predictions"
MODEL_VERSION = "transparent_baseline_v1"
ANALYTICS_LABEL = "sports analytics - not betting advice or a guarantee"
GLOBAL_CAVEAT = (
    "Relative probability within the stored candidate set from available sports analytics inputs; "
    "not betting advice or a guarantee."
)
RECENT_WINDOW_DAYS = 730

TARGET_EVENT_SELECTS = (
    "id,name,type,weapon,category,start_date,end_date,date,season",
    "id,name,type,weapon,category,date,season",
    "id,name,type,weapon,category,season",
    "id,name,type,season",
)
FENCER_SELECTS = (
    "id,fie_id,name,country,weapon,category,world_rank,active,elo_rating",
    "id,fie_id,name,country,weapon,category,world_rank,active",
    "id,fie_id,name,country,weapon,category,world_rank",
    "id,fie_id,name,country,weapon,world_rank",
)
RESULT_SELECTS = (
    "id,tournament_id,fencer_id,rank,placement,medal,weapon",
    "id,tournament_id,fencer_id,rank,placement,medal",
    "id,tournament_id,fencer_id,rank,placement",
    "id,tournament_id,fencer_id,rank",
)
RANKINGS_SELECT = "fie_fencer_id,season,weapon,category,rank,points,name,country"
PERFORMANCE_SELECT = "fencer_id,weapon,competitions_count,avg_delta,overperformance_rate"
STRENGTH_SELECT = "tournament_id,strength_score,total_fie_ranked"
TREND_SELECT = "fencer_id,weapon,category,projected_next_rank,trend_direction,rank_change,points_change"
MEDAL_SELECT = "scope,fencer_id,tier,gold,silver,bronze,total"
CAREER_SELECT = "fencer_id,total_competitions,gold_medals,silver_medals,bronze_medals,legacy_score"
ELO_SELECT = "fencer_id,weapon,rating,peak_rating"

PREDICTION_CONFLICT = "id"
BACKTEST_CONFLICT = "id"

FEATURE_WEIGHTS = {
    "ranking": 0.34,
    "recent_results": 0.20,
    "performance": 0.13,
    "trend": 0.10,
    "strength": 0.08,
    "legacy": 0.08,
    "elo": 0.05,
    "calendar": 0.02,
}

TIER_CODES = {
    "OG": "Olympics",
    "OLYMPICS": "Olympics",
    "OLYMPICGAMES": "Olympics",
    "WCH": "Worlds",
    "CHM": "Worlds",
    "WORLDCHAMPIONSHIP": "Worlds",
    "WORLDCHAMPIONSHIPS": "Worlds",
    "WORLDS": "Worlds",
}


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", (clean_text(value) or "").casefold())


def stable_id(*parts: Any) -> str:
    body = "|".join(clean_text(part) or "" for part in parts)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:40]


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def coerce_int(value: Any) -> int | None:
    number = coerce_float(value)
    if number is None:
        match = re.search(r"\d+", str(value or ""))
        number = float(match.group(0)) if match else None
    if number is None:
        return None
    result = int(number)
    return result if result > 0 else None


def coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "active"}:
        return True
    if text in {"0", "false", "no", "n", "inactive", "retired"}:
        return False
    return None


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        try:
            return datetime.fromisoformat(match.group(0)).date()
        except ValueError:
            return None
    return None


def event_date(row: dict[str, Any]) -> date | None:
    for key in ("start_date", "date", "end_date", "event_date"):
        parsed = parse_date(row.get(key))
        if parsed:
            return parsed
    return None


def row_season(row: dict[str, Any]) -> int | None:
    season = coerce_int(row.get("season"))
    if season:
        return season
    parsed = event_date(row)
    return parsed.year if parsed else None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalized_key(text)
    if key in {"e", "epee", "eepee"}:
        return "Epee"
    if key in {"f", "foil"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return text.title()


def normalize_category(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    lower = text.casefold()
    gender = None
    if any(token in lower for token in ("women", "female", "feminine")):
        gender = "Women's"
    elif any(token in lower for token in ("men", "male", "masculine")):
        gender = "Men's"

    age = None
    for candidate in ("Senior", "Junior", "Cadet", "Veteran", "U23", "U20", "U17"):
        if candidate.casefold() in lower:
            age = candidate
            break
    if gender and age:
        return f"{gender} {age}"
    if gender:
        return gender
    return text.title()


def same_event_group(row: dict[str, Any], event: dict[str, Any]) -> bool:
    event_weapon = normalize_weapon(event.get("weapon"))
    row_weapon = normalize_weapon(row.get("weapon"))
    if event_weapon and row_weapon and event_weapon != row_weapon:
        return False

    event_category = normalize_category(event.get("category"))
    row_category = normalize_category(row.get("category"))
    if event_category and row_category and event_category != row_category:
        return False
    return True


def event_tier(event: dict[str, Any]) -> str | None:
    for field in ("type", "tier", "competition_type"):
        tier = TIER_CODES.get(normalized_key(event.get(field)).upper())
        if tier:
            return tier

    haystack = " ".join(
        clean_text(event.get(field)) or ""
        for field in ("name", "type", "tier", "category")
    ).casefold()
    if "olympic games" in haystack or "olympics" in haystack:
        return "Olympics"
    if "world championship" in haystack or "world championships" in haystack:
        return "Worlds"
    return None


def event_key(event: dict[str, Any]) -> str:
    return clean_text(event.get("id")) or stable_id(
        event.get("name"),
        event.get("weapon"),
        event.get("category"),
        event.get("season"),
        event_date(event),
    )


def is_target_tier(event: dict[str, Any]) -> bool:
    return event_tier(event) in {"Olympics", "Worlds"}


def is_upcoming_target(event: dict[str, Any], today: date) -> bool:
    if not is_target_tier(event):
        return False
    parsed = event_date(event)
    if parsed:
        return parsed >= today
    season = row_season(event)
    return bool(season and season >= today.year)


def is_historical_target(event: dict[str, Any], today: date) -> bool:
    if not is_target_tier(event):
        return False
    parsed = event_date(event)
    if parsed:
        return parsed < today
    season = row_season(event)
    return bool(season and season < today.year)


def fetch_all(client, table: str, columns: str, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
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


def fetch_with_fallbacks(
    client,
    table: str,
    column_options: tuple[str, ...],
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in column_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def fetch_optional(
    client,
    table: str,
    columns: str,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    try:
        return fetch_all(client, table, columns, page_size=page_size)
    except Exception as exc:
        print(f"Optional prediction input skipped: {table}: {exc}")
        return []


def batch_upsert(client, table: str, rows: list[dict[str, Any]], on_conflict: str) -> int:
    written = 0
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index : index + BATCH_SIZE]
        client.table(table).upsert(batch, on_conflict=on_conflict).execute()
        written += len(batch)
    return written


def fencer_fie_id(fencer: dict[str, Any]) -> str | None:
    return clean_text(fencer.get("fie_id") or fencer.get("fie_fencer_id"))


def fencer_name(fencer: dict[str, Any]) -> str | None:
    return clean_text(fencer.get("name") or fencer.get("full_name"))


def candidate_identity(candidate: dict[str, Any]) -> str:
    return (
        clean_text(candidate.get("fencer_id"))
        or clean_text(candidate.get("fie_fencer_id"))
        or stable_id(candidate.get("name"), candidate.get("country"))
    )


def build_candidates(
    event: dict[str, Any],
    fencers: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_fie_id = {
        fencer_fie_id(fencer): fencer
        for fencer in fencers
        if fencer_fie_id(fencer)
    }
    candidates: dict[str, dict[str, Any]] = {}

    for fencer in fencers:
        if not same_event_group(fencer, event):
            continue
        identity = clean_text(fencer.get("id")) or fencer_fie_id(fencer)
        if not identity:
            continue
        candidates[identity] = {
            "fencer_id": clean_text(fencer.get("id")),
            "fie_fencer_id": fencer_fie_id(fencer),
            "name": fencer_name(fencer),
            "country": clean_text(fencer.get("country") or fencer.get("nationality")),
            "weapon": normalize_weapon(fencer.get("weapon")),
            "category": normalize_category(fencer.get("category")),
            "world_rank": coerce_int(fencer.get("world_rank")),
            "active": coerce_bool(fencer.get("active")),
            "elo_rating": coerce_float(fencer.get("rating")),
        }

    for ranking in rankings:
        if not same_event_group(ranking, event):
            continue
        fie_id = clean_text(ranking.get("fie_fencer_id") or ranking.get("fencer_id"))
        if not fie_id:
            continue
        fencer = by_fie_id.get(fie_id, {})
        identity = clean_text(fencer.get("id")) or fie_id
        candidates.setdefault(
            identity,
            {
                "fencer_id": clean_text(fencer.get("id")),
                "fie_fencer_id": fie_id,
                "name": fencer_name(fencer) or clean_text(ranking.get("name")),
                "country": clean_text(fencer.get("country") or ranking.get("country")),
                "weapon": normalize_weapon(ranking.get("weapon")),
                "category": normalize_category(ranking.get("category")),
                "world_rank": coerce_int(fencer.get("world_rank")),
                "active": coerce_bool(fencer.get("active")),
                "elo_rating": coerce_float(fencer.get("rating")),
            },
        )

    return list(candidates.values())


def latest_ranking(
    candidate: dict[str, Any],
    event: dict[str, Any],
    rankings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    fie_id = clean_text(candidate.get("fie_fencer_id"))
    if not fie_id:
        return None
    event_season = row_season(event)
    matches = []
    for row in rankings:
        if clean_text(row.get("fie_fencer_id") or row.get("fencer_id")) != fie_id:
            continue
        if not same_event_group(row, event):
            continue
        season = coerce_int(row.get("season"))
        if event_season and season and season > event_season:
            continue
        matches.append(row)
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda row: (
            -(coerce_int(row.get("season")) or 0),
            coerce_int(row.get("rank")) or 10**9,
        ),
    )[0]


def tournament_lookup(tournaments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def result_rank(result: dict[str, Any]) -> int | None:
    return coerce_int(result.get("rank") if result.get("rank") is not None else result.get("placement"))


def relevant_result_rows(
    candidate: dict[str, Any],
    event: dict[str, Any],
    results: list[dict[str, Any]],
    tournaments_by_id: dict[str, dict[str, Any]],
    *,
    exclude_tournament_id: str | None = None,
) -> list[dict[str, Any]]:
    fencer_id = clean_text(candidate.get("fencer_id"))
    if not fencer_id:
        return []

    target_date = event_date(event)
    rows: list[dict[str, Any]] = []
    for result in results:
        if clean_text(result.get("fencer_id")) != fencer_id:
            continue
        tournament_id = clean_text(result.get("tournament_id"))
        if exclude_tournament_id and tournament_id == exclude_tournament_id:
            continue
        tournament = tournaments_by_id.get(tournament_id or "")
        group_source = {**(tournament or {}), **{k: v for k, v in result.items() if v is not None}}
        if not same_event_group(group_source, event):
            continue
        rank = result_rank(result)
        if rank is None:
            continue
        tournament_date = event_date(tournament or {})
        if target_date and tournament_date and tournament_date >= target_date:
            continue
        if target_date and tournament_date and (target_date - tournament_date).days > RECENT_WINDOW_DAYS:
            continue
        rows.append({**result, "_tournament": tournament or {}})
    return rows


def rank_score(rank: int | None) -> float:
    if rank is None:
        return 0.0
    return min(1.0, 1.0 / math.sqrt(rank))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalized_points(points: float | None, max_points: float | None) -> float:
    if points is None or not max_points or max_points <= 0:
        return 0.0
    return clamp(points / max_points)


def latest_rankings_by_candidate(
    candidates: list[dict[str, Any]],
    event: dict[str, Any],
    rankings: list[dict[str, Any]],
) -> dict[str, dict[str, Any] | None]:
    return {
        candidate_identity(candidate): latest_ranking(candidate, event, rankings)
        for candidate in candidates
    }


def build_performance_lookup(rows: list[dict[str, Any]]) -> dict[tuple[str, str | None], dict[str, Any]]:
    lookup = {}
    for row in rows:
        fencer_id = clean_text(row.get("fencer_id"))
        if not fencer_id:
            continue
        lookup[(fencer_id, normalize_weapon(row.get("weapon")))] = row
    return lookup


def build_strength_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["tournament_id"]): row
        for row in rows
        if row.get("tournament_id") is not None
    }


def build_trend_lookup(rows: list[dict[str, Any]]) -> dict[tuple[str, str | None, str | None], dict[str, Any]]:
    lookup = {}
    for row in rows:
        fencer_id = clean_text(row.get("fencer_id"))
        if not fencer_id:
            continue
        lookup[(fencer_id, normalize_weapon(row.get("weapon")), normalize_category(row.get("category")))] = row
    return lookup


def build_medal_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup = {}
    for row in rows:
        if clean_text(row.get("scope")) != "fencer":
            continue
        fencer_id = clean_text(row.get("fencer_id"))
        if fencer_id:
            lookup[fencer_id] = row
    return lookup


def build_career_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["fencer_id"]): row
        for row in rows
        if row.get("fencer_id") is not None
    }


def build_elo_lookup(rows: list[dict[str, Any]]) -> dict[tuple[str, str | None], dict[str, Any]]:
    lookup = {}
    for row in rows:
        fencer_id = clean_text(row.get("fencer_id"))
        if not fencer_id:
            continue
        lookup[(fencer_id, normalize_weapon(row.get("weapon")))] = row
    return lookup


def lookup_by_specificity(
    lookup: dict[tuple[str, str | None], dict[str, Any]],
    fencer_id: str | None,
    weapon: str | None,
) -> dict[str, Any] | None:
    if not fencer_id:
        return None
    return lookup.get((fencer_id, weapon)) or lookup.get((fencer_id, None))


def lookup_trend(
    lookup: dict[tuple[str, str | None, str | None], dict[str, Any]],
    fie_id: str | None,
    weapon: str | None,
    category: str | None,
) -> dict[str, Any] | None:
    if not fie_id:
        return None
    return (
        lookup.get((fie_id, weapon, category))
        or lookup.get((fie_id, weapon, None))
        or lookup.get((fie_id, None, category))
        or lookup.get((fie_id, None, None))
    )


def trend_score(row: dict[str, Any] | None) -> float:
    if not row:
        return 0.0
    direction = (clean_text(row.get("trend_direction")) or "").casefold()
    base = {
        "up": 0.65,
        "stable": 0.55,
        "new": 0.45,
        "down": 0.40,
    }.get(direction, 0.45)
    change = coerce_float(row.get("rank_change")) or 0.0
    return clamp(base + max(-0.10, min(0.10, change * 0.02)))


def performance_score(row: dict[str, Any] | None) -> float:
    if not row:
        return 0.0
    clutch = coerce_float(row.get("clutch_score"))
    if clutch is None:
        clutch = coerce_float(row.get("avg_delta"))
    clutch_score = clamp(0.5 + (clutch or 0.0) / 40.0)
    overperformance = coerce_float(row.get("overperformance_rate"))
    overperformance_score = clamp((overperformance or 0.0) / 100.0) if overperformance is not None else 0.5
    return clamp(0.6 * clutch_score + 0.4 * overperformance_score)


def legacy_score(medal_row: dict[str, Any] | None, career_row: dict[str, Any] | None) -> tuple[float, int]:
    if medal_row:
        medals = coerce_int(medal_row.get("total")) or 0
        gold = coerce_int(medal_row.get("gold")) or 0
    elif career_row:
        gold = coerce_int(career_row.get("gold_medals")) or 0
        medals = gold + (coerce_int(career_row.get("silver_medals")) or 0) + (coerce_int(career_row.get("bronze_medals")) or 0)
    else:
        medals = 0
        gold = 0
    score = clamp((math.log1p(medals) / math.log1p(10)) + min(gold, 5) * 0.04)
    return score, medals


def elo_score(candidate: dict[str, Any], row: dict[str, Any] | None) -> tuple[float, float | None]:
    rating = coerce_float(candidate.get("elo_rating"))
    if rating is None and row:
        rating = coerce_float(row.get("rating") if row.get("rating") is not None else row.get("elo_rating"))
    if rating is None:
        return 0.0, None
    return clamp((rating - 1200.0) / 800.0), rating


def recent_results_score(
    rows: list[dict[str, Any]],
    strength_by_tournament: dict[str, dict[str, Any]],
) -> tuple[float, float | None]:
    if not rows:
        return 0.0, None
    scores: list[float] = []
    strengths: list[float] = []
    for row in rows:
        rank = result_rank(row)
        tournament_id = clean_text(row.get("tournament_id"))
        strength = coerce_float((strength_by_tournament.get(tournament_id or "") or {}).get("strength_score"))
        if strength is not None:
            strengths.append(strength)
        multiplier = 1.0 + min((strength or 0.0) / 100.0, 1.0) * 0.25
        scores.append(clamp(rank_score(rank) * multiplier))
    average_strength = sum(strengths) / len(strengths) if strengths else None
    return sum(scores) / len(scores), average_strength


def add_caveat(caveats: list[str], text: str) -> None:
    if text not in caveats:
        caveats.append(text)


def build_feature_record(
    candidate: dict[str, Any],
    event: dict[str, Any],
    rankings: list[dict[str, Any]],
    results: list[dict[str, Any]],
    tournaments_by_id: dict[str, dict[str, Any]],
    *,
    max_points: float | None,
    performance_by_key: dict[tuple[str, str | None], dict[str, Any]],
    strength_by_tournament: dict[str, dict[str, Any]],
    trend_by_key: dict[tuple[str, str | None, str | None], dict[str, Any]],
    medal_by_fencer: dict[str, dict[str, Any]],
    career_by_fencer: dict[str, dict[str, Any]],
    elo_by_key: dict[tuple[str, str | None], dict[str, Any]],
    apply_current_activity_penalty: bool = True,
    exclude_tournament_id: str | None = None,
) -> dict[str, Any]:
    event_weapon = normalize_weapon(event.get("weapon"))
    event_category = normalize_category(event.get("category"))
    fencer_id = clean_text(candidate.get("fencer_id"))
    fie_id = clean_text(candidate.get("fie_fencer_id"))
    caveats = [GLOBAL_CAVEAT]

    ranking = latest_ranking(candidate, event, rankings)
    latest_rank = coerce_int(ranking.get("rank")) if ranking else coerce_int(candidate.get("world_rank"))
    latest_points = coerce_float(ranking.get("points")) if ranking else None
    ranking_component = (
        0.70 * rank_score(latest_rank)
        + 0.30 * normalized_points(latest_points, max_points)
    )

    recent_rows = relevant_result_rows(
        candidate,
        event,
        results,
        tournaments_by_id,
        exclude_tournament_id=exclude_tournament_id,
    )
    recent_component, average_strength = recent_results_score(recent_rows, strength_by_tournament)

    performance = lookup_by_specificity(performance_by_key, fencer_id, event_weapon)
    performance_component = performance_score(performance)

    trend = lookup_trend(trend_by_key, fie_id, event_weapon, event_category)
    trend_component = trend_score(trend)

    strength_component = clamp((average_strength or 0.0) / 100.0)

    medal_row = medal_by_fencer.get(fencer_id or "")
    career_row = career_by_fencer.get(fencer_id or "")
    legacy_component, medal_total = legacy_score(medal_row, career_row)

    elo_component, elo_rating = elo_score(candidate, lookup_by_specificity(elo_by_key, fencer_id, event_weapon))

    calendar_component = 1.0 if event_date(event) else 0.4

    weighted_score = (
        FEATURE_WEIGHTS["ranking"] * ranking_component
        + FEATURE_WEIGHTS["recent_results"] * recent_component
        + FEATURE_WEIGHTS["performance"] * performance_component
        + FEATURE_WEIGHTS["trend"] * trend_component
        + FEATURE_WEIGHTS["strength"] * strength_component
        + FEATURE_WEIGHTS["legacy"] * legacy_component
        + FEATURE_WEIGHTS["elo"] * elo_component
        + FEATURE_WEIGHTS["calendar"] * calendar_component
    )

    event_season = row_season(event)
    ranking_season = coerce_int(ranking.get("season")) if ranking else None
    penalty = 1.0
    if apply_current_activity_penalty:
        active = coerce_bool(candidate.get("active"))
        if active is False:
            penalty *= 0.55
            add_caveat(caveats, "Inactive fencer flag found; score is conservatively penalized.")
        if event_season and ranking_season and event_season - ranking_season > 1:
            penalty *= 0.75
            add_caveat(caveats, "Limited current data: latest ranking is more than one season before target event.")
        if not recent_rows:
            penalty *= 0.85
            add_caveat(caveats, "Limited current data: no recent result evidence before target event.")
        available_signals = sum(
            1
            for value in (
                ranking_component,
                recent_component,
                performance_component,
                trend_component,
                legacy_component,
                elo_component,
            )
            if value > 0
        )
        if available_signals < 3:
            penalty *= 0.80
            add_caveat(caveats, "Limited current data: fewer than three model inputs were available.")

    final_score = round(100.0 * weighted_score * penalty, 4)
    factors = {
        "model": {
            "version": MODEL_VERSION,
            "weights": FEATURE_WEIGHTS,
            "method": "deterministic weighted baseline over documented public sports analytics inputs",
        },
        "ranking": {
            "score": round(ranking_component, 6),
            "rank": latest_rank,
            "season": ranking_season,
            "points": latest_points,
        },
        "recent_results": {
            "score": round(recent_component, 6),
            "starts": len(recent_rows),
            "window_days": RECENT_WINDOW_DAYS,
        },
        "performance": {
            "score": round(performance_component, 6),
            "competitions_count": coerce_int(performance.get("competitions_count")) if performance else 0,
            "clutch_score": coerce_float(performance.get("clutch_score")) if performance else None,
        },
        "trend": {
            "score": round(trend_component, 6),
            "direction": clean_text(trend.get("trend_direction")) if trend else None,
            "rank_change": coerce_float(trend.get("rank_change")) if trend else None,
        },
        "strength": {
            "score": round(strength_component, 6),
            "average_recent_strength": average_strength,
        },
        "legacy": {
            "score": round(legacy_component, 6),
            "medal_total": medal_total,
        },
        "elo": {
            "score": round(elo_component, 6),
            "rating": elo_rating,
        },
        "calendar": {
            "score": calendar_component,
            "target_date": event_date(event).isoformat() if event_date(event) else None,
        },
        "data_quality": {
            "penalty_multiplier": round(penalty, 6),
        },
    }

    return {
        "candidate": candidate,
        "score": final_score,
        "sort_rank": latest_rank,
        "factors": factors,
        "caveats": caveats,
    }


def event_target_fields(event: dict[str, Any]) -> dict[str, Any]:
    parsed_date = event_date(event)
    return {
        "target_event_id": clean_text(event.get("id")),
        "target_event_key": event_key(event),
        "target_event_name": clean_text(event.get("name")) or event_key(event),
        "target_event_date": parsed_date.isoformat() if parsed_date else None,
        "target_tier": event_tier(event),
        "target_weapon": normalize_weapon(event.get("weapon")),
        "target_category": normalize_category(event.get("category")),
    }


def build_prediction_rows(
    *,
    target_events: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    results: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    performance_rows: list[dict[str, Any]] | None = None,
    strength_rows: list[dict[str, Any]] | None = None,
    trend_rows: list[dict[str, Any]] | None = None,
    medal_rows: list[dict[str, Any]] | None = None,
    career_rows: list[dict[str, Any]] | None = None,
    elo_rows: list[dict[str, Any]] | None = None,
    generated_at: str | None = None,
    model_version: str = MODEL_VERSION,
    top_n: int = 20,
    apply_current_activity_penalty: bool = True,
    exclude_tournament_id: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    tournaments_by_id = tournament_lookup(tournaments)
    performance_by_key = build_performance_lookup(performance_rows or [])
    strength_by_tournament = build_strength_lookup(strength_rows or [])
    trend_by_key = build_trend_lookup(trend_rows or [])
    medal_by_fencer = build_medal_lookup(medal_rows or [])
    career_by_fencer = build_career_lookup(career_rows or [])
    elo_by_key = build_elo_lookup(elo_rows or [])

    output: list[dict[str, Any]] = []
    skipped = 0

    for event in target_events:
        candidates = build_candidates(event, fencers, rankings)
        if not candidates:
            skipped += 1
            continue

        latest_by_candidate = latest_rankings_by_candidate(candidates, event, rankings)
        max_points = max(
            (
                coerce_float(row.get("points")) or 0.0
                for row in latest_by_candidate.values()
                if row
            ),
            default=0.0,
        )

        feature_records = [
            build_feature_record(
                candidate,
                event,
                rankings,
                results,
                tournaments_by_id,
                max_points=max_points,
                performance_by_key=performance_by_key,
                strength_by_tournament=strength_by_tournament,
                trend_by_key=trend_by_key,
                medal_by_fencer=medal_by_fencer,
                career_by_fencer=career_by_fencer,
                elo_by_key=elo_by_key,
                apply_current_activity_penalty=apply_current_activity_penalty,
                exclude_tournament_id=exclude_tournament_id,
            )
            for candidate in candidates
        ]
        feature_records.sort(
            key=lambda record: (
                -record["score"],
                record["sort_rank"] is None,
                record["sort_rank"] or 10**9,
                (clean_text(record["candidate"].get("name")) or "").casefold(),
                candidate_identity(record["candidate"]),
            )
        )
        feature_records = feature_records[:top_n]
        total_score = sum(record["score"] for record in feature_records)
        if total_score <= 0:
            probability_base = 1.0 / len(feature_records)
        else:
            probability_base = None

        target_fields = event_target_fields(event)
        for index, record in enumerate(feature_records, start=1):
            candidate = record["candidate"]
            probability = probability_base if probability_base is not None else record["score"] / total_score
            row = {
                "id": stable_id(model_version, target_fields["target_event_key"], candidate_identity(candidate)),
                **target_fields,
                "fencer_id": clean_text(candidate.get("fencer_id")),
                "fie_fencer_id": clean_text(candidate.get("fie_fencer_id")),
                "fencer_name": clean_text(candidate.get("name")),
                "country": clean_text(candidate.get("country")),
                "prediction_rank": index,
                "probability": round(probability, 8),
                "score": record["score"],
                "factors": record["factors"],
                "model_version": model_version,
                "generated_at": generated_at,
                "caveats": record["caveats"],
                "analytics_label": ANALYTICS_LABEL,
            }
            output.append(row)

    return output, skipped


def actual_rankings_for_event(
    event: dict[str, Any],
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    target_id = clean_text(event.get("id"))
    actuals = []
    for result in results:
        if clean_text(result.get("tournament_id")) != target_id:
            continue
        rank = result_rank(result)
        fencer_id = clean_text(result.get("fencer_id"))
        if rank is None or not fencer_id:
            continue
        medal = clean_text(result.get("medal"))
        actuals.append(
            {
                "fencer_id": fencer_id,
                "rank": rank,
                "medal": medal,
            }
        )
    actuals.sort(key=lambda row: (row["rank"], row["fencer_id"]))
    return actuals


def is_medal_actual(row: dict[str, Any]) -> bool:
    medal = normalized_key(row.get("medal"))
    return row.get("rank") in {1, 2, 3} or medal in {"gold", "silver", "bronze", "g", "s", "b"}


def build_backtest_rows(
    *,
    target_events: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    results: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    performance_rows: list[dict[str, Any]] | None = None,
    strength_rows: list[dict[str, Any]] | None = None,
    trend_rows: list[dict[str, Any]] | None = None,
    medal_rows: list[dict[str, Any]] | None = None,
    career_rows: list[dict[str, Any]] | None = None,
    elo_rows: list[dict[str, Any]] | None = None,
    generated_at: str | None = None,
    model_version: str = MODEL_VERSION,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for event in target_events:
        actuals = actual_rankings_for_event(event, results)
        if not actuals:
            continue

        predictions, skipped = build_prediction_rows(
            target_events=[event],
            fencers=fencers,
            rankings=rankings,
            results=results,
            tournaments=tournaments,
            performance_rows=[],
            strength_rows=strength_rows,
            trend_rows=[],
            medal_rows=[],
            career_rows=[],
            elo_rows=[],
            generated_at=generated_at,
            model_version=model_version,
            top_n=top_n,
            apply_current_activity_penalty=False,
            exclude_tournament_id=clean_text(event.get("id")),
        )
        if skipped or not predictions:
            continue

        actual_by_fencer = {row["fencer_id"]: row for row in actuals}
        predicted = [
            {
                "fencer_id": row["fencer_id"],
                "fie_fencer_id": row["fie_fencer_id"],
                "prediction_rank": row["prediction_rank"],
                "probability": row["probability"],
                "score": row["score"],
            }
            for row in predictions
        ]
        actual_payload = [
            {
                "fencer_id": row["fencer_id"],
                "rank": row["rank"],
                "medal": row["medal"],
            }
            for row in actuals
        ]

        top_prediction = predictions[0]
        top1_hit = actual_by_fencer.get(top_prediction["fencer_id"], {}).get("rank") == 1
        actual_podium = {row["fencer_id"] for row in actuals if is_medal_actual(row)}
        predicted_podium = {row["fencer_id"] for row in predictions[:3]}
        podium_recall = (
            len(actual_podium & predicted_podium) / len(actual_podium)
            if actual_podium
            else None
        )

        rank_errors = [
            abs(row["prediction_rank"] - actual_by_fencer[row["fencer_id"]]["rank"])
            for row in predictions
            if row["fencer_id"] in actual_by_fencer
        ]
        mean_abs_rank_error = (
            sum(rank_errors) / len(rank_errors)
            if rank_errors
            else None
        )

        brier_terms = []
        for row in predictions:
            actual = 1.0 if row["fencer_id"] in actual_podium else 0.0
            brier_terms.append((float(row["probability"]) - actual) ** 2)
        brier_score = sum(brier_terms) / len(brier_terms) if brier_terms else None

        target_fields = event_target_fields(event)
        rows.append(
            {
                "id": stable_id(model_version, "backtest", target_fields["target_event_key"]),
                **target_fields,
                "model_version": model_version,
                "generated_at": generated_at,
                "candidates_count": len(predictions),
                "actuals_count": len(actuals),
                "top1_hit": top1_hit,
                "podium_recall": round(podium_recall, 6) if podium_recall is not None else None,
                "mean_abs_rank_error": round(mean_abs_rank_error, 4) if mean_abs_rank_error is not None else None,
                "brier_score": round(brier_score, 8) if brier_score is not None else None,
                "expected_vs_actual": {
                    "predicted": predicted,
                    "actual": actual_payload,
                    "split": {
                        "target_event_date": target_fields["target_event_date"],
                        "excluded_tournament_id": clean_text(event.get("id")),
                        "method": "features computed from non-target results before the historical target event",
                    },
                },
                "caveats": [
                    "Historical split validation for sports analytics only; not a guarantee of future outcomes.",
                    "Unversioned aggregate Elo, legacy, performance, and trend metrics are excluded from split validation to avoid future-data leakage.",
                ],
            }
        )
    return rows


def compute_predictions(
    client=None,
    *,
    generated_at: str | None = None,
    today: str | date | None = None,
    top_n: int = 20,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    today_date = parse_date(today) if today is not None else datetime.now(timezone.utc).date()
    if today_date is None:
        today_date = datetime.now(timezone.utc).date()
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    try:
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TARGET_EVENT_SELECTS, page_size=page_size)
        fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
        rankings = fetch_all(client, "fs_rankings_history", RANKINGS_SELECT, page_size=page_size)
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)

        performance_rows = fetch_optional(client, "fs_fencer_performance_analysis", PERFORMANCE_SELECT, page_size=page_size)
        strength_rows = fetch_optional(client, "fs_competition_strength", STRENGTH_SELECT, page_size=page_size)
        trend_rows = fetch_optional(client, "fs_rankings_trends", TREND_SELECT, page_size=page_size)
        medal_rows = fetch_optional(client, "fs_medal_tables", MEDAL_SELECT, page_size=page_size)
        career_rows = fetch_optional(client, "fs_fencer_career_stats", CAREER_SELECT, page_size=page_size)
        elo_rows = fetch_optional(client, "fs_fencer_elo", ELO_SELECT, page_size=page_size)

        target_events = [row for row in tournaments if is_upcoming_target(row, today_date)]
        backtest_events = [
            row
            for row in tournaments
            if is_historical_target(row, today_date)
            and any(clean_text(result.get("tournament_id")) == clean_text(row.get("id")) for result in results)
        ]

        prediction_rows, skipped = build_prediction_rows(
            target_events=target_events,
            fencers=fencers,
            rankings=rankings,
            results=results,
            tournaments=tournaments,
            performance_rows=performance_rows,
            strength_rows=strength_rows,
            trend_rows=trend_rows,
            medal_rows=medal_rows,
            career_rows=career_rows,
            elo_rows=elo_rows,
            generated_at=generated_at,
            top_n=top_n,
        )
        backtest_rows = build_backtest_rows(
            target_events=backtest_events,
            fencers=fencers,
            rankings=rankings,
            results=results,
            tournaments=tournaments,
            performance_rows=performance_rows,
            strength_rows=strength_rows,
            trend_rows=trend_rows,
            medal_rows=medal_rows,
            career_rows=career_rows,
            elo_rows=elo_rows,
            generated_at=generated_at,
            top_n=top_n,
        )

        written_predictions = (
            batch_upsert(client, "fs_predictions", prediction_rows, PREDICTION_CONFLICT)
            if prediction_rows
            else 0
        )
        written_backtests = (
            batch_upsert(client, "fs_prediction_backtests", backtest_rows, BACKTEST_CONFLICT)
            if backtest_rows
            else 0
        )
        written = written_predictions + written_backtests

        summary = {
            "target_events": len(target_events),
            "backtest_events": len(backtest_events),
            "prediction_rows": len(prediction_rows),
            "backtest_rows": len(backtest_rows),
            "written": written,
            "failed": 0,
            "skipped": skipped,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {"updated_at": datetime.now(timezone.utc).isoformat(), **summary},
            )
        if run_log:
            run_log.complete(written=written, failed=0, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Prediction computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_predictions()
    print(
        "Prediction computation complete - "
        f"target_events={summary['target_events']}, "
        f"prediction_rows={summary['prediction_rows']}, "
        f"backtest_rows={summary['backtest_rows']}, "
        f"written={summary['written']}, skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()

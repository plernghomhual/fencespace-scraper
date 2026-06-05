import math
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from season_utils import season_to_string


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
SOURCE = "compute_difficulty_trend"
DEFAULT_MOVING_WINDOW = 3
MIN_HIGH_CONFIDENCE_SAMPLE = 3

TOURNAMENT_SELECTS = (
    "id,season,weapon,gender,category,competition_tier,tier,event_tier,event_type,competition_type,format_type,type,name",
    "id,season,weapon,gender,category,tier,event_type,competition_type,type,name",
    "id,season,weapon,gender,category,type,name",
)
STRENGTH_SELECT = (
    "tournament_id,strength_score,avg_world_rank,top8_count,top16_count,total_fie_ranked"
)
RANKING_SELECTS = (
    "fie_fencer_id,season,weapon,gender,category,rank,points",
    "fie_fencer_id,season,weapon,category,rank,points",
    "fencer_id,season,weapon,category,rank,points",
)
RESULT_SELECTS = (
    "tournament_id,fencer_id,rank",
    "tournament_id,fencer_id",
)

TIER_ALIASES = {
    "og": "Olympics",
    "olympics": "Olympics",
    "olympicgames": "Olympics",
    "wch": "Worlds",
    "chm": "Worlds",
    "worlds": "Worlds",
    "worldchampionship": "Worlds",
    "worldchampionships": "Worlds",
    "grandprix": "GP",
    "gp": "GP",
    "worldcup": "WC",
    "wc": "WC",
    "cc": "Continental",
    "zch": "Continental",
    "continentalchampionship": "Continental",
    "continentalchampionships": "Continental",
    "zonalchampionship": "Continental",
    "zonalchampionships": "Continental",
    "europeanchampionship": "Continental",
    "europeanchampionships": "Continental",
    "asianchampionship": "Continental",
    "asianchampionships": "Continental",
    "panamericanchampionship": "Continental",
    "panamericanchampionships": "Continental",
    "africanchampionship": "Continental",
    "africanchampionships": "Continental",
}

EVENT_TYPE_ALIASES = {
    "individual": "Individual",
    "ind": "Individual",
    "team": "Team",
    "teams": "Team",
    "mixed": "Mixed Team",
    "mixedteam": "Mixed Team",
}


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", (clean_text(value) or "").casefold())


def display_label(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return " ".join(part[:1].upper() + part[1:].lower() for part in text.split())


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def coerce_int(value: Any) -> int | None:
    number = coerce_float(value)
    if number is None:
        return None
    return int(number)


def round2(value: float | None) -> float | None:
    if value is None:
        return None
    decimal = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(decimal)


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return round2(sum(values) / len(values))


def normalize_season_end_year(value: Any) -> int | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1000 <= value <= 9999 else None
    if isinstance(value, float):
        if value.is_integer():
            return normalize_season_end_year(int(value))
        return None

    text = clean_text(value)
    if not text:
        return None

    range_match = re.fullmatch(r"(\d{4})\s*[-/]\s*(\d{4})", text)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        return end if end == start + 1 else None

    short_range = re.fullmatch(r"(\d{4})\s*[-/]\s*(\d{2})", text)
    if short_range:
        start = int(short_range.group(1))
        end_two = int(short_range.group(2))
        century = start // 100 * 100
        end = century + end_two
        if end < start:
            end += 100
        return end if end == start + 1 else None

    year_match = re.fullmatch(r"\d{4}", text)
    if year_match:
        return int(text)

    return None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = compact_key(text)
    if key in {"e", "epee", "epée"}:
        return "Epee"
    if key in {"f", "foil"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return display_label(text)


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = compact_key(text)
    if key in {"m", "male", "man", "men", "mens"}:
        return "Men's"
    if key in {"f", "female", "woman", "women", "womens"}:
        return "Women's"
    if key in {"mixed", "mix", "mixedteam"}:
        return "Mixed"
    return display_label(text)


def gender_from_category(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold()
    if re.match(r"^(men'?s|mens|men|male)\b", key):
        return "Men's"
    if re.match(r"^(women'?s|womens|women|female)\b", key):
        return "Women's"
    if re.match(r"^(mixed)\b", key):
        return "Mixed"
    return None


def normalize_category(value: Any, gender: str | None = None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(
        r"^(men'?s|mens|men|male|women'?s|womens|women|female|mixed)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return display_label(text)


def normalize_tier(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = compact_key(text)
    if key in TIER_ALIASES:
        return TIER_ALIASES[key]
    return None


def row_tier(row: dict[str, Any]) -> str:
    for field in ("competition_tier", "tier", "event_tier"):
        tier = normalize_tier(row.get(field))
        if tier:
            return tier

    type_tier = normalize_tier(row.get("type"))
    return type_tier or "Unknown"


def normalize_event_type(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = compact_key(text)
    return EVENT_TYPE_ALIASES.get(key)


def row_event_type(row: dict[str, Any]) -> str:
    for field in ("event_type", "competition_type", "format_type", "format"):
        event_type = normalize_event_type(row.get(field))
        if event_type:
            return event_type

    raw_type = row.get("type")
    if not normalize_tier(raw_type):
        event_type = normalize_event_type(raw_type)
        if event_type:
            return event_type
    return "Unknown"


def normalize_dimension_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    season = normalize_season_end_year(row.get("season"))
    if season is None:
        return None, "missing_season"

    weapon = normalize_weapon(row.get("weapon"))
    if not weapon:
        return None, "missing_weapon"

    gender = normalize_gender(row.get("gender")) or gender_from_category(row.get("category")) or "Unknown"
    category = normalize_category(row.get("category"), gender)
    if not category:
        return None, "missing_category"

    return (
        {
            "season": season,
            "weapon": weapon,
            "gender": gender,
            "category": category,
        },
        None,
    )


def tournament_lookup(tournaments: list[dict[str, Any]] | dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def result_counts_by_tournament(result_rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in result_rows:
        tournament_id = clean_text(row.get("tournament_id"))
        if tournament_id:
            counts[tournament_id] += 1
    return counts


def ranking_counts_by_dimension(ranking_rows: list[dict[str, Any]]) -> dict[tuple[int, str, str, str], int]:
    counts: dict[tuple[int, str, str, str], int] = defaultdict(int)
    for row in ranking_rows:
        dims, reason = normalize_dimension_row(row)
        if reason or dims is None:
            continue
        counts[(dims["season"], dims["weapon"], dims["gender"], dims["category"])] += 1
    return counts


def stable_row_id(*parts: Any) -> str:
    return "difficulty:" + ":".join(compact_key(part) or "unknown" for part in parts)


def trend_direction(current: float, previous: float | None) -> str:
    if previous is None:
        return "new"
    if current > previous:
        return "harder"
    if current < previous:
        return "easier"
    return "stable"


def confidence_score(sample_count: int, ranking_sample_count: int, result_sample_count: int) -> float:
    sample_quality = min(1.0, sample_count / MIN_HIGH_CONFIDENCE_SAMPLE)
    ranking_quality = 1.0 if ranking_sample_count else 0.65
    result_quality = 1.0 if result_sample_count else 0.75
    return round(sample_quality * ranking_quality * result_quality, 3)


def confidence_level(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def build_difficulty_trend_rows(
    tournaments: list[dict[str, Any]] | dict[str, dict[str, Any]],
    strength_rows: list[dict[str, Any]],
    ranking_rows: list[dict[str, Any]] | None = None,
    result_rows: list[dict[str, Any]] | None = None,
    moving_window: int = DEFAULT_MOVING_WINDOW,
    computed_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    computed_at = computed_at or datetime.now(timezone.utc).isoformat()
    moving_window = max(1, moving_window)
    tournaments_by_id = tournament_lookup(tournaments)
    result_counts = result_counts_by_tournament(result_rows or [])
    ranking_counts = ranking_counts_by_dimension(ranking_rows or [])

    skipped = {
        "missing_tournament_id": 0,
        "missing_tournament": 0,
        "missing_strength_score": 0,
        "missing_season": 0,
        "missing_weapon": 0,
        "missing_category": 0,
    }
    aggregates: dict[tuple[str, str, str, str, str, int], dict[str, Any]] = {}

    for strength in strength_rows:
        tournament_id = clean_text(strength.get("tournament_id"))
        if not tournament_id:
            skipped["missing_tournament_id"] += 1
            continue

        tournament = tournaments_by_id.get(tournament_id)
        if not tournament:
            skipped["missing_tournament"] += 1
            continue

        strength_score = coerce_float(strength.get("strength_score"))
        if strength_score is None:
            skipped["missing_strength_score"] += 1
            continue

        dims, reason = normalize_dimension_row(tournament)
        if reason or dims is None:
            skipped[reason or "missing_dims"] += 1
            continue

        key = (
            row_event_type(tournament),
            row_tier(tournament),
            dims["weapon"],
            dims["gender"],
            dims["category"],
            dims["season"],
        )
        aggregate = aggregates.setdefault(
            key,
            {
                "strength_scores": [],
                "avg_world_ranks": [],
                "top8_count": 0,
                "top16_count": 0,
                "total_fie_ranked": 0,
                "result_sample_count": 0,
                "tournament_ids": set(),
            },
        )
        aggregate["strength_scores"].append(strength_score)
        avg_world_rank = coerce_float(strength.get("avg_world_rank"))
        if avg_world_rank is not None:
            aggregate["avg_world_ranks"].append(avg_world_rank)
        aggregate["top8_count"] += coerce_int(strength.get("top8_count")) or 0
        aggregate["top16_count"] += coerce_int(strength.get("top16_count")) or 0
        aggregate["total_fie_ranked"] += coerce_int(strength.get("total_fie_ranked")) or 0
        aggregate["result_sample_count"] += result_counts.get(tournament_id, 0)
        aggregate["tournament_ids"].add(tournament_id)

    base_rows: list[dict[str, Any]] = []
    for key, aggregate in sorted(aggregates.items()):
        event_type, tier, weapon, gender, category, season = key
        sample_count = len(aggregate["strength_scores"])
        ranking_sample_count = ranking_counts.get((season, weapon, gender, category), 0)
        confidence = confidence_score(
            sample_count,
            ranking_sample_count,
            aggregate["result_sample_count"],
        )
        base_rows.append(
            {
                "id": stable_row_id(event_type, tier, weapon, gender, category, season),
                "event_type": event_type,
                "tier": tier,
                "weapon": weapon,
                "gender": gender,
                "category": category,
                "season": season,
                "season_label": season_to_string(season),
                "sample_count": sample_count,
                "tournament_count": sample_count,
                "ranking_sample_count": ranking_sample_count,
                "result_sample_count": aggregate["result_sample_count"],
                "ranked_participant_count": aggregate["total_fie_ranked"],
                "avg_total_fie_ranked": round2(aggregate["total_fie_ranked"] / sample_count),
                "avg_top8_count": round2(aggregate["top8_count"] / sample_count),
                "avg_top16_count": round2(aggregate["top16_count"] / sample_count),
                "avg_world_rank": average(aggregate["avg_world_ranks"]),
                "avg_strength_score": average(aggregate["strength_scores"]),
                "confidence": confidence,
                "confidence_level": confidence_level(confidence),
                "computed_at": computed_at,
            }
        )

    series_rows: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in base_rows:
        series_key = (
            row["event_type"],
            row["tier"],
            row["weapon"],
            row["gender"],
            row["category"],
        )
        series_rows[series_key].append(row)

    rows: list[dict[str, Any]] = []
    for series_key in sorted(series_rows):
        history = sorted(series_rows[series_key], key=lambda item: item["season"])
        for index, row in enumerate(history):
            previous = history[index - 1] if index > 0 else None
            window = history[max(0, index - moving_window + 1) : index + 1]
            moving_average = average([item["avg_strength_score"] for item in window])
            previous_score = previous["avg_strength_score"] if previous else None
            trend_delta = (
                round2(row["avg_strength_score"] - previous_score)
                if previous_score is not None
                else None
            )
            row.update(
                {
                    "previous_strength_score": previous_score,
                    "trend_delta": trend_delta,
                    "trend_direction": trend_direction(row["avg_strength_score"], previous_score),
                    "moving_avg_strength_score": moving_average,
                    "window_sample_count": len(window),
                    "window_tournament_count": sum(item["sample_count"] for item in window),
                }
            )
            rows.append(row)

    report = {
        "input_tournaments": len(tournaments_by_id),
        "input_strength_rows": len(strength_rows),
        "input_rankings": len(ranking_rows or []),
        "input_results": len(result_rows or []),
        "aggregate_rows": len(rows),
        "groups": len(series_rows),
        "moving_window": moving_window,
        "skipped": skipped,
        "skipped_total": sum(skipped.values()),
    }
    return rows, report


def fetch_all(
    client,
    table: str,
    columns: str,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
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
    selects: tuple[str, ...],
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in selects:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Unable to fetch {table}") from last_error


def compute_difficulty_trend(
    client=None,
    page_size: int = PAGE_SIZE,
    moving_window: int = DEFAULT_MOVING_WINDOW,
    log_run: bool = True,
    update_state: bool = True,
    computed_at: str | None = None,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
        strength_rows = fetch_all(client, "fs_competition_strength", STRENGTH_SELECT, page_size=page_size)
        ranking_rows = fetch_with_fallbacks(client, "fs_rankings_history", RANKING_SELECTS, page_size=page_size)
        result_rows = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)

        rows, report = build_difficulty_trend_rows(
            tournaments,
            strength_rows,
            ranking_rows=ranking_rows,
            result_rows=result_rows,
            moving_window=moving_window,
            computed_at=computed_at,
        )
        summary = {
            "tournaments_read": len(tournaments),
            "strength_rows_read": len(strength_rows),
            "rankings_read": len(ranking_rows),
            "results_read": len(result_rows),
            "trend_rows": len(rows),
            "skipped": report["skipped_total"],
            "rows": rows,
            "report": report,
        }

        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "tournaments_read": summary["tournaments_read"],
                    "strength_rows_read": summary["strength_rows_read"],
                    "rankings_read": summary["rankings_read"],
                    "results_read": summary["results_read"],
                    "trend_rows": summary["trend_rows"],
                    "skipped": summary["skipped"],
                },
            )
        if run_log:
            run_log.complete(written=len(rows), failed=0, skipped=report["skipped_total"], metadata=report)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous difficulty trend state: {previous_state}")

    print(f"Competition difficulty trend computation starting - {datetime.now(timezone.utc).isoformat()}")
    result = compute_difficulty_trend()
    print(
        "Competition difficulty trend computation complete - "
        f"trend_rows={result['trend_rows']}, skipped={result['skipped']}"
    )


if __name__ == "__main__":
    main()

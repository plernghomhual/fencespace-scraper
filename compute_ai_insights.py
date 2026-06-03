import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state

SOURCE = "compute_ai_insights"
RULE_VERSION = "ai_insights_rules_v1"
PAGE_SIZE = 1000
BATCH_SIZE = 100
INSIGHT_CONFLICT_COLUMNS = "entity_type,entity_id,insight_type"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

FENCER_SELECTS = (
    "id,name,full_name,display_name,country,weapon,world_rank,fie_fencer_id",
    "id,name,country,weapon,world_rank,fie_fencer_id",
    "id,name,country,weapon,world_rank",
    "id,name",
)
CAREER_SELECTS = (
    "fencer_id,total_competitions,gold_medals,silver_medals,bronze_medals,"
    "top8_count,best_rank,avg_rank,worst_rank,weapons_used,categories_competed,"
    "first_season,last_season,total_touches_scored,total_touches_received,"
    "touch_differential,updated_at",
)
PERFORMANCE_SELECTS = (
    "fencer_id,weapon,competitions_count,avg_delta,overperformance_rate,"
    "clutch_score,updated_at",
)
RANKING_TRENDS_SELECTS = (
    "fencer_id,weapon,category,season,rank,previous_rank,rank_change,points,"
    "previous_points,points_change,trend_direction,computed_at",
)
H2H_SELECTS = (
    "fencer_a_id,fencer_b_id,weapon,a_wins,b_wins,a_touches,b_touches,"
    "bouts_total,last_meeting_date,last_winner_id,updated_at",
)
RESULT_SELECTS = (
    "id,tournament_id,fencer_id,rank,placement,weapon,metadata",
    "id,tournament_id,fencer_id,rank,placement,weapon",
    "id,tournament_id,fencer_id,rank,placement",
)
TOURNAMENT_SELECTS = (
    "id,name,weapon,season,start_date,end_date,date",
    "id,name,weapon,season,end_date",
    "id,weapon,end_date",
)

SOURCE_TABLE_ORDER = [
    "fs_fencers",
    "fs_fencer_career_stats",
    "fs_fencer_performance_analysis",
    "fs_rankings_trends",
    "fs_head_to_head",
    "fs_results",
    "fs_tournaments",
]

WEAPON_MAP = {
    "s": "Sabre",
    "sabre": "Sabre",
    "saber": "Sabre",
    "e": "Epee",
    "epee": "Epee",
    "epée": "Epee",
    "f": "Foil",
    "foil": "Foil",
}


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = " ".join(str(value or "").split())
    return text or None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return WEAPON_MAP.get(text.casefold(), text)


def coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_date(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()[:10]

    text = clean_text(value)
    if not text:
        return None
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def format_count(count: int, singular: str, plural: str | None = None) -> str:
    label = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {label}"


def display_name(fencer: dict[str, Any] | None, fallback_id: Any = None) -> str:
    if fencer:
        for key in ("name", "full_name", "display_name"):
            value = clean_text(fencer.get(key))
            if value:
                return value
    fallback = clean_text(fallback_id)
    return f"Fencer {fallback}" if fallback else "Unknown fencer"


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
    *,
    page_size: int = PAGE_SIZE,
    optional: bool = False,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in column_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    if optional:
        print(f"Skipping optional AI insight source {table}: {last_error}")
        return []
    if last_error:
        raise last_error
    return []


def fetch_source_data(client, page_size: int = PAGE_SIZE) -> dict[str, list[dict[str, Any]]]:
    return {
        "fencers": fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size),
        "career_stats": fetch_with_fallbacks(
            client,
            "fs_fencer_career_stats",
            CAREER_SELECTS,
            page_size=page_size,
            optional=True,
        ),
        "performance": fetch_with_fallbacks(
            client,
            "fs_fencer_performance_analysis",
            PERFORMANCE_SELECTS,
            page_size=page_size,
            optional=True,
        ),
        "ranking_trends": fetch_with_fallbacks(
            client,
            "fs_rankings_trends",
            RANKING_TRENDS_SELECTS,
            page_size=page_size,
            optional=True,
        ),
        "head_to_head": fetch_with_fallbacks(
            client,
            "fs_head_to_head",
            H2H_SELECTS,
            page_size=page_size,
            optional=True,
        ),
        "results": fetch_with_fallbacks(
            client,
            "fs_results",
            RESULT_SELECTS,
            page_size=page_size,
            optional=True,
        ),
        "tournaments": fetch_with_fallbacks(
            client,
            "fs_tournaments",
            TOURNAMENT_SELECTS,
            page_size=page_size,
            optional=True,
        ),
    }


def rows_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(row[key]): row
        for row in rows
        if row.get(key) is not None and clean_text(row.get(key))
    }


def group_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = clean_text(row.get(key))
        if value:
            grouped[value].append(row)
    return grouped


def fencer_external_index(fencers: list[dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for row in fencers:
        row_id = clean_text(row.get("id"))
        if not row_id:
            continue
        index[row_id] = row_id
        for key in ("fie_fencer_id", "fie_id", "fencer_id"):
            value = clean_text(row.get(key))
            if value:
                index[value] = row_id
    return index


def latest_ranking(rows: list[dict[str, Any]], weapon: str | None = None) -> dict[str, Any] | None:
    normalized_weapon = normalize_weapon(weapon)
    candidates = [
        row
        for row in rows
        if coerce_int(row.get("rank")) is not None
        and (normalized_weapon is None or normalize_weapon(row.get("weapon")) == normalized_weapon)
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            coerce_int(row.get("season")) if coerce_int(row.get("season")) is not None else -1,
            clean_text(row.get("computed_at")) or "",
        ),
    )


def best_performance(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rows
        if coerce_int(row.get("competitions_count")) is not None
        and coerce_float(row.get("avg_delta")) is not None
        and coerce_float(row.get("overperformance_rate")) is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: coerce_int(row.get("competitions_count")) or 0)


def tournament_date(tournament: dict[str, Any] | None) -> str | None:
    if not tournament:
        return None
    for key in ("end_date", "date", "start_date"):
        value = normalize_date(tournament.get(key))
        if value:
            return value
    return None


def recent_result(
    rows: list[dict[str, Any]],
    tournaments_by_id: dict[str, dict[str, Any]],
    weapon: str | None = None,
) -> dict[str, Any] | None:
    normalized_weapon = normalize_weapon(weapon)
    candidates = []
    for row in rows:
        rank = coerce_int(row.get("rank") if row.get("rank") is not None else row.get("placement"))
        if rank is None:
            continue
        tournament = tournaments_by_id.get(str(row.get("tournament_id")))
        date = normalize_date(row.get("date")) or tournament_date(tournament)
        if not date:
            continue
        row_weapon = normalize_weapon(row.get("weapon")) or normalize_weapon((tournament or {}).get("weapon"))
        if normalized_weapon and row_weapon != normalized_weapon:
            continue
        candidates.append({**row, "_rank": rank, "_tournament": tournament or {}, "_date": date})

    if not candidates:
        return None
    return max(candidates, key=lambda row: row["_date"])


def sentence(text: str, sources: list[str], values: dict[str, Any]) -> dict[str, Any]:
    return {"text": text, "sources": sources, "values": values}


def source_tables(sentences: list[dict[str, Any]]) -> list[str]:
    present = {source for item in sentences for source in item["sources"]}
    return [source for source in SOURCE_TABLE_ORDER if source in present]


def confidence_for(sentences: list[dict[str, Any]]) -> float:
    return min(0.95, round(0.55 + 0.08 * len(sentences), 3))


def make_insight_row(
    *,
    entity_type: str,
    entity_id: str,
    insight_type: str,
    sentences: list[dict[str, Any]],
    generated_at: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tables = source_tables(sentences)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "insight_type": insight_type,
        "summary": " ".join(item["text"] for item in sentences),
        "evidence_json": {
            "source_tables": tables,
            "sentences": sentences,
        },
        "confidence": confidence_for(sentences),
        "provider": "rules",
        "model": None,
        "rule_version": RULE_VERSION,
        "generated_at": generated_at,
        "metadata": {
            "generation_mode": "rules",
            "rule_version": RULE_VERSION,
            "source_tables": tables,
            **(metadata or {}),
        },
    }


def build_performance_summary(
    fencer: dict[str, Any],
    *,
    career: dict[str, Any] | None,
    performance_rows: list[dict[str, Any]],
    ranking_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
    tournaments_by_id: dict[str, dict[str, Any]],
    generated_at: str,
) -> dict[str, Any] | None:
    fencer_id = clean_text(fencer.get("id"))
    if not fencer_id:
        return None

    name = display_name(fencer, fencer_id)
    sentences: list[dict[str, Any]] = []

    if career:
        competitions = coerce_int(career.get("total_competitions")) or 0
        gold = coerce_int(career.get("gold_medals")) or 0
        silver = coerce_int(career.get("silver_medals")) or 0
        bronze = coerce_int(career.get("bronze_medals")) or 0
        top8 = coerce_int(career.get("top8_count")) or 0
        if competitions > 0 or gold or silver or bronze or top8:
            sentences.append(
                sentence(
                    f"{name} has {competitions} recorded competitions, "
                    f"{format_count(gold, 'gold medal')}, "
                    f"{format_count(silver, 'silver medal')}, "
                    f"{format_count(bronze, 'bronze medal')}, and "
                    f"{format_count(top8, 'top-eight finish', 'top-eight finishes')}.",
                    ["fs_fencers", "fs_fencer_career_stats"],
                    {
                        "fencer_id": fencer_id,
                        "name": name,
                        "total_competitions": competitions,
                        "gold_medals": gold,
                        "silver_medals": silver,
                        "bronze_medals": bronze,
                        "top8_count": top8,
                    },
                )
            )

        best_rank = coerce_int(career.get("best_rank"))
        avg_rank = coerce_float(career.get("avg_rank"))
        first_season = clean_text(career.get("first_season"))
        last_season = clean_text(career.get("last_season"))
        if best_rank is not None and avg_rank is not None:
            season_text = (
                f" from {first_season} through {last_season}"
                if first_season and last_season
                else ""
            )
            sentences.append(
                sentence(
                    f"Best recorded finish is rank {best_rank} and average recorded finish is {avg_rank:.2f}{season_text}.",
                    ["fs_fencer_career_stats"],
                    {
                        "fencer_id": fencer_id,
                        "best_rank": best_rank,
                        "avg_rank": avg_rank,
                        "first_season": first_season,
                        "last_season": last_season,
                    },
                )
            )

    performance = best_performance(performance_rows)
    if performance:
        weapon = normalize_weapon(performance.get("weapon")) or "unknown weapon"
        competitions = coerce_int(performance.get("competitions_count")) or 0
        avg_delta = coerce_float(performance.get("avg_delta")) or 0.0
        rate = coerce_float(performance.get("overperformance_rate")) or 0.0
        sentences.append(
            sentence(
                f"In {weapon}, recorded performance delta is {avg_delta:+.2f} "
                f"with a {rate:.2f}% overperformance rate across {competitions} competitions.",
                ["fs_fencer_performance_analysis"],
                {
                    "fencer_id": fencer_id,
                    "weapon": weapon,
                    "competitions_count": competitions,
                    "avg_delta": avg_delta,
                    "overperformance_rate": rate,
                },
            )
        )

    ranking = latest_ranking(ranking_rows)
    if ranking:
        weapon = normalize_weapon(ranking.get("weapon")) or "unknown weapon"
        category = clean_text(ranking.get("category")) or "unknown category"
        season_value = coerce_int(ranking.get("season"))
        rank = coerce_int(ranking.get("rank"))
        previous_rank = coerce_int(ranking.get("previous_rank"))
        direction = clean_text(ranking.get("trend_direction")) or "available"
        if season_value is not None and rank is not None:
            if previous_rank is not None:
                text = (
                    f"Latest ranking evidence for {weapon} {category} is season {season_value} "
                    f"rank {rank}, marked {direction} from previous rank {previous_rank}."
                )
            else:
                text = (
                    f"Latest ranking evidence for {weapon} {category} is season {season_value} "
                    f"rank {rank}."
                )
            sentences.append(
                sentence(
                    text,
                    ["fs_rankings_trends"],
                    {
                        "fencer_id": fencer_id,
                        "weapon": weapon,
                        "category": category,
                        "season": season_value,
                        "rank": rank,
                        "previous_rank": previous_rank,
                        "trend_direction": direction,
                    },
                )
            )

    result = recent_result(result_rows, tournaments_by_id)
    if result:
        tournament = result["_tournament"]
        tournament_name = clean_text(tournament.get("name")) or clean_text(result.get("tournament_id")) or "recorded tournament"
        sentences.append(
            sentence(
                f"Most recent recorded result is rank {result['_rank']} at {tournament_name} on {result['_date']}.",
                ["fs_results", "fs_tournaments"],
                {
                    "fencer_id": fencer_id,
                    "result_id": result.get("id"),
                    "tournament_id": result.get("tournament_id"),
                    "tournament_name": tournament_name,
                    "rank": result["_rank"],
                    "date": result["_date"],
                },
            )
        )

    if not sentences:
        return None
    return make_insight_row(
        entity_type="fencer",
        entity_id=fencer_id,
        insight_type="performance_summary",
        sentences=sentences,
        generated_at=generated_at,
        metadata={"fencer_id": fencer_id, "fencer_name": name},
    )


def comparison_leader_text(name_a: str, name_b: str, a_wins: int, b_wins: int) -> str:
    if a_wins > b_wins:
        return f"{name_a} leads {a_wins}-{b_wins}"
    if b_wins > a_wins:
        return f"{name_b} leads {b_wins}-{a_wins}"
    return f"the series is tied {a_wins}-{b_wins}"


def touch_text(name_a: str, name_b: str, a_touches: int, b_touches: int) -> str:
    if a_touches > b_touches:
        return f"Touch evidence in those bouts is {a_touches}-{b_touches} for {name_a}."
    if b_touches > a_touches:
        return f"Touch evidence in those bouts is {b_touches}-{a_touches} for {name_b}."
    return f"Touch evidence in those bouts is tied {a_touches}-{b_touches}."


def ranking_label(row: dict[str, Any]) -> str:
    weapon = normalize_weapon(row.get("weapon")) or "unknown weapon"
    category = clean_text(row.get("category")) or "unknown category"
    season = coerce_int(row.get("season"))
    rank = coerce_int(row.get("rank"))
    return f"{weapon} {category} season {season} rank {rank}"


def build_comparison(
    h2h: dict[str, Any],
    *,
    fencers_by_id: dict[str, dict[str, Any]],
    career_by_fencer: dict[str, dict[str, Any]],
    rankings_by_fencer: dict[str, list[dict[str, Any]]],
    results_by_fencer: dict[str, list[dict[str, Any]]],
    tournaments_by_id: dict[str, dict[str, Any]],
    generated_at: str,
) -> dict[str, Any] | None:
    fencer_a_id = clean_text(h2h.get("fencer_a_id"))
    fencer_b_id = clean_text(h2h.get("fencer_b_id"))
    weapon = normalize_weapon(h2h.get("weapon"))
    bouts_total = coerce_int(h2h.get("bouts_total")) or 0
    if not fencer_a_id or not fencer_b_id or not weapon or bouts_total <= 0:
        return None

    fencer_a = fencers_by_id.get(fencer_a_id)
    fencer_b = fencers_by_id.get(fencer_b_id)
    if not fencer_a or not fencer_b:
        return None

    name_a = display_name(fencer_a, fencer_a_id)
    name_b = display_name(fencer_b, fencer_b_id)
    a_wins = coerce_int(h2h.get("a_wins")) or 0
    b_wins = coerce_int(h2h.get("b_wins")) or 0
    sentences: list[dict[str, Any]] = [
        sentence(
            f"{name_a} and {name_b} have {bouts_total} recorded {weapon} head-to-head bouts; "
            f"{comparison_leader_text(name_a, name_b, a_wins, b_wins)}.",
            ["fs_fencers", "fs_head_to_head"],
            {
                "fencer_a_id": fencer_a_id,
                "fencer_b_id": fencer_b_id,
                "weapon": weapon,
                "bouts_total": bouts_total,
                "a_wins": a_wins,
                "b_wins": b_wins,
            },
        )
    ]

    a_touches = coerce_int(h2h.get("a_touches")) or 0
    b_touches = coerce_int(h2h.get("b_touches")) or 0
    if a_touches or b_touches:
        sentences.append(
            sentence(
                touch_text(name_a, name_b, a_touches, b_touches),
                ["fs_fencers", "fs_head_to_head"],
                {
                    "fencer_a_id": fencer_a_id,
                    "fencer_b_id": fencer_b_id,
                    "a_touches": a_touches,
                    "b_touches": b_touches,
                },
            )
        )

    last_meeting_date = normalize_date(h2h.get("last_meeting_date"))
    last_winner_id = clean_text(h2h.get("last_winner_id"))
    if last_meeting_date and last_winner_id:
        winner = display_name(fencers_by_id.get(last_winner_id), last_winner_id)
        sentences.append(
            sentence(
                f"Their last recorded meeting was on {last_meeting_date}, won by {winner}.",
                ["fs_fencers", "fs_head_to_head"],
                {
                    "last_meeting_date": last_meeting_date,
                    "last_winner_id": last_winner_id,
                    "last_winner_name": winner,
                },
            )
        )

    career_a = career_by_fencer.get(fencer_a_id)
    career_b = career_by_fencer.get(fencer_b_id)
    if career_a and career_b:
        a_competitions = coerce_int(career_a.get("total_competitions")) or 0
        b_competitions = coerce_int(career_b.get("total_competitions")) or 0
        a_top8 = coerce_int(career_a.get("top8_count")) or 0
        b_top8 = coerce_int(career_b.get("top8_count")) or 0
        sentences.append(
            sentence(
                f"Career evidence lists {name_a} with {a_competitions} competitions and "
                f"{a_top8} top-eight finishes, while {name_b} has {b_competitions} "
                f"competitions and {b_top8} top-eight finishes.",
                ["fs_fencers", "fs_fencer_career_stats"],
                {
                    "fencer_a_id": fencer_a_id,
                    "fencer_b_id": fencer_b_id,
                    "a_total_competitions": a_competitions,
                    "b_total_competitions": b_competitions,
                    "a_top8_count": a_top8,
                    "b_top8_count": b_top8,
                },
            )
        )

    ranking_a = latest_ranking(rankings_by_fencer.get(fencer_a_id, []), weapon=weapon)
    ranking_b = latest_ranking(rankings_by_fencer.get(fencer_b_id, []), weapon=weapon)
    if ranking_a and ranking_b:
        sentences.append(
            sentence(
                f"Latest ranking evidence puts {name_a} at {ranking_label(ranking_a)} "
                f"and {name_b} at {ranking_label(ranking_b)}.",
                ["fs_fencers", "fs_rankings_trends"],
                {
                    "fencer_a_id": fencer_a_id,
                    "fencer_b_id": fencer_b_id,
                    "a_ranking": {
                        "weapon": clean_text(ranking_a.get("weapon")),
                        "category": clean_text(ranking_a.get("category")),
                        "season": coerce_int(ranking_a.get("season")),
                        "rank": coerce_int(ranking_a.get("rank")),
                    },
                    "b_ranking": {
                        "weapon": clean_text(ranking_b.get("weapon")),
                        "category": clean_text(ranking_b.get("category")),
                        "season": coerce_int(ranking_b.get("season")),
                        "rank": coerce_int(ranking_b.get("rank")),
                    },
                },
            )
        )

    result_a = recent_result(results_by_fencer.get(fencer_a_id, []), tournaments_by_id, weapon=weapon)
    result_b = recent_result(results_by_fencer.get(fencer_b_id, []), tournaments_by_id, weapon=weapon)
    if result_a and result_b:
        tournament_a = clean_text(result_a["_tournament"].get("name")) or clean_text(result_a.get("tournament_id")) or "recorded tournament"
        tournament_b = clean_text(result_b["_tournament"].get("name")) or clean_text(result_b.get("tournament_id")) or "recorded tournament"
        sentences.append(
            sentence(
                f"Most recent dated results are {name_a} rank {result_a['_rank']} at {tournament_a} "
                f"on {result_a['_date']} and {name_b} rank {result_b['_rank']} at {tournament_b} "
                f"on {result_b['_date']}.",
                ["fs_fencers", "fs_results", "fs_tournaments"],
                {
                    "fencer_a_id": fencer_a_id,
                    "fencer_b_id": fencer_b_id,
                    "a_result": {
                        "result_id": result_a.get("id"),
                        "rank": result_a["_rank"],
                        "tournament_id": result_a.get("tournament_id"),
                        "tournament_name": tournament_a,
                        "date": result_a["_date"],
                    },
                    "b_result": {
                        "result_id": result_b.get("id"),
                        "rank": result_b["_rank"],
                        "tournament_id": result_b.get("tournament_id"),
                        "tournament_name": tournament_b,
                        "date": result_b["_date"],
                    },
                },
            )
        )

    return make_insight_row(
        entity_type="fencer_pair",
        entity_id=f"{fencer_a_id}:{fencer_b_id}:{weapon}",
        insight_type="fencer_comparison",
        sentences=sentences,
        generated_at=generated_at,
        metadata={
            "fencer_a_id": fencer_a_id,
            "fencer_b_id": fencer_b_id,
            "weapon": weapon,
        },
    )


def build_ai_insight_rows(
    source_data: dict[str, list[dict[str, Any]]],
    *,
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    fencers = source_data.get("fencers", [])
    fencers_by_id = rows_by_key(fencers, "id")
    external_index = fencer_external_index(fencers)
    career_by_fencer = rows_by_key(source_data.get("career_stats", []), "fencer_id")
    performance_by_fencer = group_by_key(source_data.get("performance", []), "fencer_id")
    results_by_fencer = group_by_key(source_data.get("results", []), "fencer_id")
    tournaments_by_id = rows_by_key(source_data.get("tournaments", []), "id")

    rankings_by_fencer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_data.get("ranking_trends", []):
        raw_id = clean_text(row.get("fencer_id"))
        mapped_id = external_index.get(raw_id or "", raw_id)
        if mapped_id:
            rankings_by_fencer[mapped_id].append(row)

    rows: list[dict[str, Any]] = []
    skipped = {"performance_summaries": 0, "comparisons": 0}

    for fencer_id in sorted(fencers_by_id):
        row = build_performance_summary(
            fencers_by_id[fencer_id],
            career=career_by_fencer.get(fencer_id),
            performance_rows=performance_by_fencer.get(fencer_id, []),
            ranking_rows=rankings_by_fencer.get(fencer_id, []),
            result_rows=results_by_fencer.get(fencer_id, []),
            tournaments_by_id=tournaments_by_id,
            generated_at=generated_at,
        )
        if row:
            rows.append(row)
        else:
            skipped["performance_summaries"] += 1

    for h2h in source_data.get("head_to_head", []):
        row = build_comparison(
            h2h,
            fencers_by_id=fencers_by_id,
            career_by_fencer=career_by_fencer,
            rankings_by_fencer=rankings_by_fencer,
            results_by_fencer=results_by_fencer,
            tournaments_by_id=tournaments_by_id,
            generated_at=generated_at,
        )
        if row:
            rows.append(row)
        else:
            skipped["comparisons"] += 1

    return rows, skipped


def apply_provider_generation(
    rows: list[dict[str, Any]],
    *,
    provider=None,
    provider_dry_run: bool = True,
) -> tuple[list[dict[str, Any]], bool]:
    if provider is None:
        return rows, False
    if provider_dry_run:
        for row in rows:
            row["metadata"]["provider_dry_run"] = True
        return rows, False
    generated = provider.generate(rows)
    return generated, True


def upsert_insight_rows(
    client,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = BATCH_SIZE,
) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table("fs_ai_insights").upsert(
                batch,
                on_conflict=INSIGHT_CONFLICT_COLUMNS,
            ).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_ai_insights upsert batch {index // batch_size} failed: {exc}")
    return written, failed


def compute_ai_insights(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    generated_at: str | None = None,
    provider=None,
    provider_dry_run: bool = True,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        source_data = fetch_source_data(client, page_size=page_size)
        rows, skipped = build_ai_insight_rows(source_data, generated_at=generated_at)
        rows, provider_used = apply_provider_generation(
            rows,
            provider=provider,
            provider_dry_run=provider_dry_run,
        )
        written, failed = (
            upsert_insight_rows(client, rows, batch_size=batch_size) if rows else (0, 0)
        )

        summary = {
            "fencers_read": len(source_data["fencers"]),
            "career_stats_read": len(source_data["career_stats"]),
            "performance_rows_read": len(source_data["performance"]),
            "ranking_trends_read": len(source_data["ranking_trends"]),
            "head_to_head_read": len(source_data["head_to_head"]),
            "results_read": len(source_data["results"]),
            "tournaments_read": len(source_data["tournaments"]),
            "insights_built": len(rows),
            "written": written,
            "failed": failed,
            "skipped": skipped["performance_summaries"] + skipped["comparisons"],
            "skipped_detail": skipped,
            "provider_used": provider_used,
            "provider_dry_run": bool(provider is not None and provider_dry_run),
            "rule_version": RULE_VERSION,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {"updated_at": datetime.now(timezone.utc).isoformat(), **summary},
            )
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=summary["skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    summary = compute_ai_insights()
    print(
        "AI insights complete: "
        f"{summary['written']} rows written, "
        f"{summary['failed']} failed, "
        f"{summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()

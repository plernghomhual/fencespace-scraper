import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_clutch"

MIN_POOL_BOUTS = 3
MIN_ELIMINATION_BOUTS = 1
POOL_WEIGHT = 0.60
RANK_WEIGHT = 0.30
HISTORY_WEIGHT = 0.10
HISTORY_DELTA_SCALE = 100.0
CONFIDENCE_POOL_TARGET = 5
CONFIDENCE_ELIMINATION_TARGET = 3
CONFIDENCE_RANK_TARGET = 8

CLUTCH_CONFLICT = "fencer_id,tournament_id"
FORMULA_DESCRIPTION = (
    "expected_result = weighted average of pool_performance (60%), "
    "rank_percentile (30%), historical_performance (10%); "
    "delta = actual_result - expected_result"
)

RESULT_SELECTS = (
    "tournament_id,fencer_id,rank,placement,seed,entry_seed,pool_rank,status,weapon,category",
    "tournament_id,fencer_id,rank,placement,weapon,category",
    "tournament_id,fencer_id,rank,placement",
)
BOUT_SELECTS = (
    "tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,round,is_bye,status",
    "tournament_id,fencer_a,fencer_b,winner_id,score_a,score_b,round,is_bye,status",
    "tournament_id,fencer_a_id,fencer_b_id,score_a,score_b,round",
    "tournament_id,fencer_a,fencer_b,score_a,score_b,round",
)
FENCER_SELECTS = (
    "id,fie_id,name,country,world_rank,national_rank,weapon,category",
    "id,fie_id,name,country,world_rank,weapon,category",
    "id,world_rank,weapon",
)
TOURNAMENT_SELECTS = (
    "id,name,weapon,gender,category,season,type",
    "id,name,weapon,category",
    "id,name",
)
PERFORMANCE_SELECTS = (
    "fencer_id,weapon,competitions_count,avg_delta,clutch_score",
    "fencer_id,weapon,avg_delta,clutch_score",
)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_key(value: Any) -> str:
    return (clean_text(value) or "").casefold()


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        number = int(match.group(0)) if match else None
    return number


def positive_int(value: Any) -> int | None:
    number = to_int(value)
    return number if number is not None and number > 0 else None


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_metric(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold()
    if key in {"e", "epee", "epée"}:
        return "Epee"
    if key in {"f", "foil"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return text.title()


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


def lookup_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in rows if row.get("id") is not None}


def performance_lookup(rows: list[dict[str, Any]]) -> dict[tuple[str, str | None], dict[str, Any]]:
    lookup: dict[tuple[str, str | None], dict[str, Any]] = {}
    for row in rows:
        fencer_id = clean_text(row.get("fencer_id"))
        if not fencer_id:
            continue
        weapon = normalize_weapon(row.get("weapon"))
        lookup[(fencer_id, weapon)] = row
        lookup.setdefault((fencer_id, None), row)
    return lookup


def tournament_label(tournament: dict[str, Any] | None, tournament_id: str) -> str:
    return clean_text((tournament or {}).get("name")) or tournament_id


def row_weapon(
    result: dict[str, Any],
    fencer: dict[str, Any] | None,
    tournament: dict[str, Any] | None,
) -> str | None:
    return (
        normalize_weapon(result.get("weapon"))
        or normalize_weapon((tournament or {}).get("weapon"))
        or normalize_weapon((fencer or {}).get("weapon"))
    )


def row_category(result: dict[str, Any], fencer: dict[str, Any] | None, tournament: dict[str, Any] | None) -> str | None:
    return (
        clean_text(result.get("category"))
        or clean_text((tournament or {}).get("category"))
        or clean_text((fencer or {}).get("category"))
    )


def is_team_event(result: dict[str, Any], tournament: dict[str, Any] | None) -> bool:
    fields = [
        result.get("event_type"),
        result.get("category"),
        result.get("type"),
        (tournament or {}).get("name"),
        (tournament or {}).get("category"),
        (tournament or {}).get("type"),
    ]
    return any(re.search(r"\bteam\b", normalize_key(field)) for field in fields)


def is_withdrawal(row: dict[str, Any]) -> bool:
    status = normalize_key(row.get("status") or row.get("result_status"))
    return status in {"withdrawn", "withdrawal", "wd", "dns", "dnf", "scratched"}


def fencer_ids_from_bout(bout: dict[str, Any]) -> tuple[str | None, str | None]:
    return (
        clean_text(bout.get("fencer_a_id") or bout.get("fencer_a")),
        clean_text(bout.get("fencer_b_id") or bout.get("fencer_b")),
    )


def is_bye_bout(bout: dict[str, Any]) -> bool:
    if bout.get("is_bye") is True or bout.get("bye") is True:
        return True
    if normalize_key(bout.get("status")) == "bye":
        return True
    return "bye" in normalize_key(bout.get("round"))


def is_pool_round(round_name: Any) -> bool:
    text = normalize_key(round_name)
    return "pool" in text or "poule" in text


def is_elimination_round(round_name: Any) -> bool:
    text = normalize_key(round_name)
    if not text or is_pool_round(text) or "bye" in text:
        return False
    return bool(
        re.search(
            r"(tableau|table|direct elimination|\bde\b|round|final|semi|quarter|"
            r"last 64|last 32|last 16|last 8|last 4|\bt\s*\d+)",
            text,
        )
    )


def bout_phase_score(score_for: int, score_against: int, phase: str) -> float:
    target = 5 if phase == "pool" else 15
    target = max(target, score_for, score_against)
    return clamp(0.5 + ((score_for - score_against) / (2 * target)))


def rank_evidence(result: dict[str, Any], fencer: dict[str, Any] | None) -> tuple[int | None, str | None]:
    for key in ("seed", "entry_seed", "initial_seed", "pool_rank"):
        value = positive_int(result.get(key))
        if value is not None:
            return value, key
    if fencer:
        value = positive_int(fencer.get("world_rank"))
        if value is not None:
            return value, "world_rank"
        value = positive_int(fencer.get("national_rank"))
        if value is not None:
            return value, "national_rank"
    return None, None


def rank_percentile(rank_value: int, event_rank_values: list[int]) -> float | None:
    if len(event_rank_values) < 2:
        return None
    sorted_values = sorted(event_rank_values)
    positions = [index for index, value in enumerate(sorted_values) if value == rank_value]
    if not positions:
        return None
    position = sum(positions) / len(positions)
    return 1 - (position / (len(sorted_values) - 1))


def historical_component(performance_row: dict[str, Any] | None) -> float | None:
    if not performance_row:
        return None
    delta = to_float(performance_row.get("clutch_score"))
    if delta is None:
        delta = to_float(performance_row.get("avg_delta"))
    if delta is None:
        return None
    return clamp(0.5 + (delta / HISTORY_DELTA_SCALE))


def weighted_expected(
    pool_performance: float,
    rank_component: float,
    history_component: float | None,
) -> float:
    weighted_sum = (pool_performance * POOL_WEIGHT) + (rank_component * RANK_WEIGHT)
    total_weight = POOL_WEIGHT + RANK_WEIGHT
    if history_component is not None:
        weighted_sum += history_component * HISTORY_WEIGHT
        total_weight += HISTORY_WEIGHT
    return weighted_sum / total_weight


def confidence_score(pool_bouts: int, elimination_bouts: int, ranked_count: int) -> float:
    return (
        0.55 * min(pool_bouts / CONFIDENCE_POOL_TARGET, 1.0)
        + 0.35 * min(elimination_bouts / CONFIDENCE_ELIMINATION_TARGET, 1.0)
        + 0.10 * min(ranked_count / CONFIDENCE_RANK_TARGET, 1.0)
    )


def skip_entry(tournament_id: str, fencer_id: str | None, reason: str) -> dict[str, Any]:
    return {
        "tournament_id": tournament_id,
        "fencer_id": fencer_id,
        "reason": reason,
    }


def build_event_rank_context(
    results: list[dict[str, Any]],
    bouts_by_tournament: dict[str, list[dict[str, Any]]],
    fencers_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, tuple[int, str]]]:
    context: dict[str, dict[str, tuple[int, str]]] = defaultdict(dict)

    def add(tournament_id: str | None, fencer_id: str | None, result: dict[str, Any] | None = None) -> None:
        if not tournament_id or not fencer_id or fencer_id in context[tournament_id]:
            return
        fencer = fencers_by_id.get(fencer_id)
        rank, source = rank_evidence(result or {}, fencer)
        if rank is not None and source:
            context[tournament_id][fencer_id] = (rank, source)

    for result in results:
        add(clean_text(result.get("tournament_id")), clean_text(result.get("fencer_id")), result)

    for tournament_id, bouts in bouts_by_tournament.items():
        for bout in bouts:
            fencer_a, fencer_b = fencer_ids_from_bout(bout)
            add(tournament_id, fencer_a)
            add(tournament_id, fencer_b)
    return context


def collect_phase_scores(
    tournament_id: str,
    fencer_id: str,
    bouts_by_tournament: dict[str, list[dict[str, Any]]],
) -> tuple[list[float], list[float], list[dict[str, Any]]]:
    pool_scores: list[float] = []
    elimination_scores: list[float] = []
    skips: list[dict[str, Any]] = []

    for bout in bouts_by_tournament.get(tournament_id, []):
        fencer_a, fencer_b = fencer_ids_from_bout(bout)
        if fencer_id not in {fencer_a, fencer_b}:
            continue

        if is_bye_bout(bout):
            skips.append(skip_entry(tournament_id, fencer_id, "bye"))
            continue
        if is_withdrawal(bout):
            skips.append(skip_entry(tournament_id, fencer_id, "withdrawal"))
            continue

        score_a = to_int(bout.get("score_a"))
        score_b = to_int(bout.get("score_b"))
        if score_a is None or score_b is None:
            skips.append(skip_entry(tournament_id, fencer_id, "missing_score"))
            continue

        if fencer_id == fencer_a:
            score_for, score_against = score_a, score_b
        else:
            score_for, score_against = score_b, score_a

        round_name = bout.get("round")
        if is_pool_round(round_name):
            pool_scores.append(bout_phase_score(score_for, score_against, "pool"))
        elif is_elimination_round(round_name):
            elimination_scores.append(bout_phase_score(score_for, score_against, "elimination"))
        else:
            skips.append(skip_entry(tournament_id, fencer_id, "unknown_round"))

    return pool_scores, elimination_scores, skips


def append_skip(skips: list[dict[str, Any]], seen: set[tuple[str, str | None, str]], item: dict[str, Any]) -> None:
    key = (item["tournament_id"], item.get("fencer_id"), item["reason"])
    if key not in seen:
        seen.add(key)
        skips.append(item)


def build_clutch_rows(
    results: list[dict[str, Any]],
    bouts: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    performance_rows: list[dict[str, Any]],
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = updated_at or datetime.now(timezone.utc).isoformat()
    fencers_by_id = lookup_by_id(fencers)
    tournaments_by_id = lookup_by_id(tournaments)
    performance_by_key = performance_lookup(performance_rows)
    bouts_by_tournament: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bout in bouts:
        tournament_id = clean_text(bout.get("tournament_id"))
        if tournament_id:
            bouts_by_tournament[tournament_id].append(bout)

    rank_context = build_event_rank_context(results, bouts_by_tournament, fencers_by_id)
    rows: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    seen_skips: set[tuple[str, str | None, str]] = set()
    seen_result_keys: set[tuple[str, str]] = set()

    for result in results:
        tournament_id = clean_text(result.get("tournament_id"))
        fencer_id = clean_text(result.get("fencer_id"))
        if not tournament_id or not fencer_id:
            continue
        result_key = (tournament_id, fencer_id)
        if result_key in seen_result_keys:
            continue
        seen_result_keys.add(result_key)

        tournament = tournaments_by_id.get(tournament_id)
        if is_team_event(result, tournament):
            append_skip(skips, seen_skips, skip_entry(tournament_id, fencer_id, "team_event"))
            continue
        if is_withdrawal(result):
            append_skip(skips, seen_skips, skip_entry(tournament_id, fencer_id, "withdrawal"))
            continue

        fencer = fencers_by_id.get(fencer_id)
        if not fencer:
            append_skip(skips, seen_skips, skip_entry(tournament_id, fencer_id, "missing_fencer"))
            continue

        pool_scores, elimination_scores, phase_skips = collect_phase_scores(
            tournament_id,
            fencer_id,
            bouts_by_tournament,
        )
        for item in phase_skips:
            append_skip(skips, seen_skips, item)

        if not pool_scores and not elimination_scores and not phase_skips:
            continue
        if len(pool_scores) < MIN_POOL_BOUTS:
            append_skip(skips, seen_skips, skip_entry(tournament_id, fencer_id, "insufficient_pool_bouts"))
            continue
        if len(elimination_scores) < MIN_ELIMINATION_BOUTS:
            append_skip(skips, seen_skips, skip_entry(tournament_id, fencer_id, "insufficient_elimination_bouts"))
            continue

        rank_data = rank_context.get(tournament_id, {})
        rank_entry = rank_data.get(fencer_id)
        event_rank_values = [value for value, _ in rank_data.values()]
        if not rank_entry or len(event_rank_values) < 2:
            append_skip(skips, seen_skips, skip_entry(tournament_id, fencer_id, "insufficient_rank_evidence"))
            continue
        rank_value, rank_source = rank_entry
        rank_component = rank_percentile(rank_value, event_rank_values)
        if rank_component is None:
            append_skip(skips, seen_skips, skip_entry(tournament_id, fencer_id, "insufficient_rank_evidence"))
            continue

        weapon = row_weapon(result, fencer, tournament)
        performance_row = (
            performance_by_key.get((fencer_id, weapon))
            or performance_by_key.get((fencer_id, None))
        )
        history = historical_component(performance_row)
        pool_performance = sum(pool_scores) / len(pool_scores)
        elimination_performance = sum(elimination_scores) / len(elimination_scores)
        expected_result = weighted_expected(pool_performance, rank_component, history)
        actual_result = elimination_performance
        delta = actual_result - expected_result
        confidence = confidence_score(len(pool_scores), len(elimination_scores), len(event_rank_values))

        rows.append(
            {
                "fencer_id": fencer_id,
                "fie_id": clean_text(fencer.get("fie_id")),
                "fencer_name": clean_text(fencer.get("name")),
                "country": clean_text(fencer.get("country")),
                "tournament_id": tournament_id,
                "event_name": tournament_label(tournament, tournament_id),
                "weapon": weapon,
                "category": row_category(result, fencer, tournament),
                "pool_performance": round_metric(pool_performance),
                "elimination_performance": round_metric(elimination_performance),
                "expected_result": round_metric(expected_result),
                "actual_result": round_metric(actual_result),
                "delta": round_metric(delta),
                "confidence": round_metric(confidence),
                "pool_bouts": len(pool_scores),
                "elimination_bouts": len(elimination_scores),
                "rank_value": rank_value,
                "rank_source": rank_source,
                "historical_performance": round_metric(history),
                "updated_at": now,
                "evidence": {
                    "formula": FORMULA_DESCRIPTION,
                    "components": {
                        "pool_weight": POOL_WEIGHT,
                        "rank_weight": RANK_WEIGHT,
                        "history_weight": HISTORY_WEIGHT if history is not None else 0,
                        "rank_percentile": round_metric(rank_component),
                        "ranked_event_fencers": len(event_rank_values),
                    },
                    "skip_policy": {
                        "min_pool_bouts": MIN_POOL_BOUTS,
                        "min_elimination_bouts": MIN_ELIMINATION_BOUTS,
                    },
                },
            }
        )

    rows.sort(key=lambda row: (row["tournament_id"], row["fencer_id"]))
    return rows, skips


def batch_upsert(
    client,
    rows: list[dict[str, Any]],
    batch_size: int = BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_fencer_clutch_metrics").upsert(
            batch,
            on_conflict=CLUTCH_CONFLICT,
        ).execute()
        written += len(batch)
    return written


def compute_clutch(
    client=None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    updated_at: str | None = None,
) -> dict[str, int]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    try:
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        bouts = fetch_with_fallbacks(client, "fs_bouts", BOUT_SELECTS, page_size=page_size)
        fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
        performance_rows = fetch_with_fallbacks(
            client,
            "fs_fencer_performance_analysis",
            PERFORMANCE_SELECTS,
            page_size=page_size,
        )
        clutch_rows, skipped = build_clutch_rows(
            results,
            bouts,
            fencers,
            tournaments,
            performance_rows,
            updated_at=updated_at,
        )
        written = batch_upsert(client, clutch_rows) if clutch_rows else 0
        summary = {
            "results_read": len(results),
            "bouts_read": len(bouts),
            "fencers_read": len(fencers),
            "tournaments_read": len(tournaments),
            "performance_rows_read": len(performance_rows),
            "clutch_rows": len(clutch_rows),
            "written": written,
            "skipped": len(skipped),
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    **summary,
                    "skip_reasons": skipped[:100],
                },
            )
        if run_log:
            run_log.complete(written=written, failed=0, skipped=len(skipped), metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous clutch state: {previous_state}")

    print(f"Clutch computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_clutch()
    print(
        "Clutch computation complete - "
        f"{summary['clutch_rows']} rows built, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()

import os
import re
from collections import defaultdict
from datetime import UTC, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_performance_analysis"

RESULT_SELECTS = (
    "tournament_id,fencer_id,rank,placement,weapon",
    "tournament_id,fencer_id,rank,placement",
    "tournament_id,fencer_id,rank",
)
FENCER_SELECT = "id,world_rank,weapon"
TOURNAMENT_SELECT = "id,weapon"
PERFORMANCE_CONFLICT = "fencer_id,weapon"
CAREER_CONFLICT = "fencer_id"


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def coerce_positive_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    number: int | None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(value))
        number = int(match.group(0)) if match else None
    return number if number and number > 0 else None


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


def population_stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return variance ** 0.5


def round_metric(value: float) -> float:
    return round(value, 2)


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


def fencer_lookup(fencers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): row
        for row in fencers
        if row.get("id") is not None
    }


def tournament_lookup(tournaments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def result_weapon(
    result: dict[str, Any],
    fencer: dict[str, Any],
    tournaments_by_id: dict[str, dict[str, Any]],
) -> str | None:
    weapon = normalize_weapon(result.get("weapon"))
    if weapon:
        return weapon

    tournament_id = result.get("tournament_id")
    tournament = (
        tournaments_by_id.get(str(tournament_id))
        if tournament_id is not None
        else None
    )
    weapon = normalize_weapon(tournament.get("weapon")) if tournament else None
    if weapon:
        return weapon

    return normalize_weapon(fencer.get("weapon"))


def build_performance_rows(
    results: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    fencers_by_id = fencer_lookup(fencers)
    tournaments_by_id = tournament_lookup(tournaments)
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    skipped = 0

    for result in results:
        fencer_id = clean_text(result.get("fencer_id"))
        rank = coerce_positive_int(
            result.get("rank") if result.get("rank") is not None else result.get("placement")
        )
        fencer = fencers_by_id.get(fencer_id) if fencer_id else None
        expected = coerce_positive_int(fencer.get("world_rank")) if fencer else None
        weapon = result_weapon(result, fencer, tournaments_by_id) if fencer else None

        if not fencer_id or rank is None or expected is None or not weapon:
            skipped += 1
            continue

        grouped[(fencer_id, weapon)].append(expected - rank)

    now = updated_at or datetime.now(UTC).isoformat()
    rows: list[dict[str, Any]] = []
    for (fencer_id, weapon), deltas in sorted(grouped.items()):
        avg_delta = sum(deltas) / len(deltas)
        overperformance_rate = (
            sum(1 for delta in deltas if delta > 0) / len(deltas) * 100
        )
        rows.append(
            {
                "fencer_id": fencer_id,
                "weapon": weapon,
                "competitions_count": len(deltas),
                "avg_delta": round_metric(avg_delta),
                "stddev_delta": round_metric(population_stddev([float(delta) for delta in deltas])),
                "overperformance_rate": round_metric(overperformance_rate),
                "clutch_score": round_metric(avg_delta),
                "updated_at": now,
            }
        )
    return rows, skipped


def batch_upsert(
    client,
    table: str,
    rows: list[dict[str, Any]],
    on_conflict: str,
    batch_size: int = BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table(table).upsert(batch, on_conflict=on_conflict).execute()
        written += len(batch)
    return written


def career_clutch_score_column_exists(client) -> bool:
    try:
        client.table("fs_fencer_career_stats").select("fencer_id,clutch_score").limit(1).execute()
        return True
    except Exception as exc:
        print(f"Skipping career stats clutch_score mirror: {exc}")
        return False


def career_clutch_rows(performance_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"delta_sum": 0.0, "count": 0.0})
    for row in performance_rows:
        competitions = float(row["competitions_count"])
        grouped[row["fencer_id"]]["delta_sum"] += float(row["avg_delta"]) * competitions
        grouped[row["fencer_id"]]["count"] += competitions

    rows: list[dict[str, Any]] = []
    for fencer_id, stats in sorted(grouped.items()):
        if stats["count"] <= 0:
            continue
        rows.append(
            {
                "fencer_id": fencer_id,
                "clutch_score": round_metric(stats["delta_sum"] / stats["count"]),
            }
        )
    return rows


def mirror_career_clutch_scores(client, performance_rows: list[dict[str, Any]]) -> int:
    if not performance_rows or not career_clutch_score_column_exists(client):
        return 0

    rows = career_clutch_rows(performance_rows)
    if not rows:
        return 0
    try:
        return batch_upsert(
            client,
            "fs_fencer_career_stats",
            rows,
            on_conflict=CAREER_CONFLICT,
        )
    except Exception as exc:
        print(f"Skipping career stats clutch_score mirror after upsert failure: {exc}")
        return 0


def compute_performance_analysis(
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
        fencers = fetch_all(client, "fs_fencers", FENCER_SELECT, page_size=page_size)
        tournaments = fetch_all(client, "fs_tournaments", TOURNAMENT_SELECT, page_size=page_size)
        performance_rows, skipped = build_performance_rows(
            results,
            fencers,
            tournaments,
            updated_at=updated_at,
        )
        written = (
            batch_upsert(
                client,
                "fs_fencer_performance_analysis",
                performance_rows,
                on_conflict=PERFORMANCE_CONFLICT,
            )
            if performance_rows
            else 0
        )
        career_mirrored = mirror_career_clutch_scores(client, performance_rows)

        summary = {
            "results_read": len(results),
            "fencers_read": len(fencers),
            "tournaments_read": len(tournaments),
            "performance_rows": len(performance_rows),
            "written": written,
            "career_mirrored": career_mirrored,
            "skipped": skipped,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {"updated_at": datetime.now(UTC).isoformat(), **summary},
            )
        if run_log:
            run_log.complete(written=written, failed=0, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Performance analysis computation starting - {datetime.now(UTC).isoformat()}")
    summary = compute_performance_analysis()
    print(
        "Performance analysis computation complete - "
        f"{summary['performance_rows']} rows built, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} source rows skipped"
    )


if __name__ == "__main__":
    main()

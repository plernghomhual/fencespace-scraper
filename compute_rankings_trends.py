import os
from collections import defaultdict
from datetime import UTC, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
UPSERT_BATCH_SIZE = 200
TREND_CONFLICT_COLUMNS = "fie_fencer_id,weapon,category,season"
PROJECTION_WEIGHTS = (0.5, 0.3, 0.2)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        result = int(value)
        return result if result > 0 else None
    except (TypeError, ValueError):
        return None


def coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def round_half_up(value: float) -> int:
    return int(value + 0.5)


def weighted_projection(values: list[int | float | None]) -> float | None:
    """Return a recency-weighted projection from oldest-to-newest values."""
    usable: list[tuple[float, float]] = []
    for weight, value in zip(PROJECTION_WEIGHTS, reversed(values[-3:]), strict=False):
        if value is not None:
            usable.append((weight, float(value)))
    if not usable:
        return None
    total_weight = sum(weight for weight, _ in usable)
    return sum(weight * value for weight, value in usable) / total_weight


def normalize_history_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    fie_fencer_id = clean_text(row.get("fie_fencer_id") or row.get("fencer_id"))
    weapon = clean_text(row.get("weapon"))
    category = clean_text(row.get("category"))
    season = coerce_int(row.get("season"))
    rank = coerce_int(row.get("rank"))

    if not fie_fencer_id or not weapon or not category or season is None or rank is None:
        return None, True

    return (
        {
            "fie_fencer_id": fie_fencer_id,
            "weapon": weapon,
            "category": category,
            "season": season,
            "rank": rank,
            "points": coerce_float(row.get("points")),
        },
        False,
    )


def trend_direction(rank: int, previous_rank: int | None) -> str:
    if previous_rank is None:
        return "new"
    if rank < previous_rank:
        return "up"
    if rank > previous_rank:
        return "down"
    return "stable"


def build_trend_rows(
    history_rows: list[dict[str, Any]],
    computed_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    computed_at = computed_at or datetime.now(UTC).isoformat()
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    skipped = 0

    for raw_row in history_rows:
        row, was_skipped = normalize_history_row(raw_row)
        if was_skipped or row is None:
            skipped += 1
            continue
        grouped[(row["fie_fencer_id"], row["weapon"], row["category"])].append(row)

    trend_rows: list[dict[str, Any]] = []
    for (fie_fencer_id, weapon, category), rows in sorted(grouped.items()):
        rows_by_season: dict[int, dict[str, Any]] = {}
        for row in sorted(rows, key=lambda item: (item["season"], item["rank"])):
            rows_by_season.setdefault(row["season"], row)

        window: list[dict[str, Any]] = []
        previous: dict[str, Any] | None = None
        for row in sorted(rows_by_season.values(), key=lambda item: item["season"]):
            if previous and row["season"] != previous["season"] + 1:
                previous = None
                window = []

            previous_rank = previous["rank"] if previous else None
            previous_points = previous["points"] if previous else None
            rank_change = previous_rank - row["rank"] if previous_rank is not None else None
            points_change = (
                row["points"] - previous_points
                if row["points"] is not None and previous_points is not None
                else None
            )

            window.append(row)
            recent_ranks = [item["rank"] for item in window[-3:]]
            recent_points = [item["points"] for item in window[-3:]]
            projected_rank = weighted_projection(recent_ranks)
            projected_points = weighted_projection(recent_points)

            trend_rows.append(
                {
                    "fie_fencer_id": fie_fencer_id,
                    "weapon": weapon,
                    "category": category,
                    "season": row["season"],
                    "rank": row["rank"],
                    "previous_rank": previous_rank,
                    "rank_change": rank_change,
                    "points": row["points"],
                    "previous_points": previous_points,
                    "points_change": points_change,
                    "trend_direction": trend_direction(row["rank"], previous_rank),
                    "projected_next_rank": round_half_up(projected_rank) if projected_rank is not None else None,
                    "projected_next_points": projected_points,
                    "computed_at": computed_at,
                }
            )
            previous = row

    return trend_rows, skipped


def fetch_rankings_history(client) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table("fs_rankings_history")
            .select("fie_fencer_id,season,weapon,category,rank,points")
            .order("fie_fencer_id")
            .order("weapon")
            .order("category")
            .order("season")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def upsert_trend_rows(client, rows: list[dict[str, Any]]) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[index : index + UPSERT_BATCH_SIZE]
        try:
            client.table("fs_rankings_trends").upsert(
                batch,
                on_conflict=TREND_CONFLICT_COLUMNS,
            ).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_rankings_trends upsert batch {index // UPSERT_BATCH_SIZE} failed: {exc}")
    return written, failed


def _probe_trends_table(client) -> None:
    """Raise early if fs_rankings_trends does not exist, before wasting computation."""
    client.table("fs_rankings_trends").select("fie_fencer_id").limit(0).execute()


def compute_rankings_trends(client=None, log_run: bool = True) -> dict[str, int]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger("compute_rankings_trends").start() if log_run else None

    try:
        _probe_trends_table(client)
        history_rows = fetch_rankings_history(client)
        trend_rows, skipped = build_trend_rows(history_rows)
        written, failed = upsert_trend_rows(client, trend_rows) if trend_rows else (0, 0)

        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped)
        return {
            "read": len(history_rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
        }
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Rankings trends computation starting - {datetime.now(UTC).isoformat()}")
    result = compute_rankings_trends()
    print(
        "Rankings trends computation complete - "
        f"read={result['read']}, written={result['written']}, "
        f"failed={result['failed']}, skipped={result['skipped']}"
    )


if __name__ == "__main__":
    main()

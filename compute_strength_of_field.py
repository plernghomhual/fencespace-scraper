import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
UPSERT_BATCH_SIZE = 200
SOURCE = "compute_strength_of_field"

RESULT_SELECT = "tournament_id,fencer_id"
FENCER_SELECT = "id,world_rank"
STRENGTH_CONFLICT_COLUMNS = "tournament_id"


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


def coerce_world_rank(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not numeric.is_integer():
        return None
    rank = int(numeric)
    return rank if rank > 0 else None


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


def build_fencer_rank_lookup(fencers: list[dict[str, Any]] | dict[str, Any]) -> dict[str, int]:
    from typing import Iterable
    items: Iterable[tuple[Any, Any]]
    if isinstance(fencers, dict):
        items = fencers.items()
    else:
        items = ((row.get("id"), row.get("world_rank")) for row in fencers)

    ranks: dict[str, int] = {}
    for fencer_id, rank_value in items:
        fencer_key = clean_text(fencer_id)
        rank = coerce_world_rank(rank_value)
        if fencer_key and rank is not None:
            ranks[fencer_key] = rank
    return ranks


def joined_world_rank(result: dict[str, Any]) -> int | None:
    for key in ("fencer", "fs_fencers"):
        nested = result.get(key)
        if isinstance(nested, dict):
            rank = coerce_world_rank(nested.get("world_rank"))
            if rank is not None:
                return rank
        elif isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    rank = coerce_world_rank(item.get("world_rank"))
                    if rank is not None:
                        return rank
    return None


def result_world_rank(
    result: dict[str, Any],
    fencer_ranks: dict[str, int],
) -> int | None:
    joined_rank = joined_world_rank(result)
    if joined_rank is not None:
        return joined_rank

    fencer_id = clean_text(result.get("fencer_id"))
    if not fencer_id:
        return None
    return fencer_ranks.get(fencer_id)


def build_strength_rows(
    results: list[dict[str, Any]],
    fencers: list[dict[str, Any]] | dict[str, Any],
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    now = updated_at or datetime.now(timezone.utc).isoformat()
    fencer_ranks = build_fencer_rank_lookup(fencers)
    tournament_ids: set[str] = set()
    ranked_participants: dict[str, dict[str, int]] = defaultdict(dict)
    skipped = 0

    for result in results:
        tournament_id = clean_text(result.get("tournament_id"))
        if not tournament_id:
            skipped += 1
            continue
        tournament_ids.add(tournament_id)

        fencer_id = clean_text(result.get("fencer_id"))
        if not fencer_id:
            skipped += 1
            continue

        rank = result_world_rank(result, fencer_ranks)
        if rank is None:
            skipped += 1
            continue

        ranked_participants[tournament_id].setdefault(fencer_id, rank)

    rows: list[dict[str, Any]] = []
    for tournament_id in sorted(tournament_ids):
        ranks = list(ranked_participants.get(tournament_id, {}).values())
        total_ranked = len(ranks)
        if total_ranked:
            avg_world_rank = round(sum(ranks) / total_ranked, 2)
            strength_score = round(
                sum(101 - rank for rank in ranks) / total_ranked,
                2,
            )
        else:
            avg_world_rank = None
            strength_score = None

        rows.append(
            {
                "tournament_id": tournament_id,
                "avg_world_rank": avg_world_rank,
                "top8_count": sum(1 for rank in ranks if rank <= 8),
                "top16_count": sum(1 for rank in ranks if rank <= 16),
                "total_fie_ranked": total_ranked,
                "strength_score": strength_score,
                "updated_at": now,
            }
        )
    return rows, skipped


def upsert_strength_rows(
    client,
    rows: list[dict[str, Any]],
    batch_size: int = UPSERT_BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_competition_strength").upsert(
            batch,
            on_conflict=STRENGTH_CONFLICT_COLUMNS,
        ).execute()
        written += len(batch)
    return written


def compute_strength_of_field(
    client=None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    now: str | None = None,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        results = fetch_all(client, "fs_results", RESULT_SELECT, page_size=page_size)
        fencers = fetch_all(client, "fs_fencers", FENCER_SELECT, page_size=page_size)
        rows, skipped = build_strength_rows(results, fencers, updated_at=now)
        written = upsert_strength_rows(client, rows) if rows else 0

        summary = {
            "results_read": len(results),
            "fencers_read": len(fencers),
            "tournaments_scored": len(rows),
            "written": written,
            "skipped": skipped,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    **summary,
                },
            )
        if run_log:
            run_log.complete(written=written, failed=0, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous strength-of-field state: {previous_state}")

    print(f"Strength-of-field computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_strength_of_field()
    print(
        "Strength-of-field computation complete - "
        f"{summary['tournaments_scored']} tournaments scored, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} result rows skipped"
    )


if __name__ == "__main__":
    main()

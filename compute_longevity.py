from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state

try:
    from supabase import create_client
except Exception:  # pragma: no cover - surfaced when a live client is requested.
    create_client = None


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_longevity"


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    if create_client is None:
        raise RuntimeError("supabase package is required.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def season_to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = clean_text(value)
    if not text:
        return None

    short_range = re.match(r"^(\d{4})\s*[-/]\s*(\d{2})$", text)
    if short_range:
        start = int(short_range.group(1))
        end_two = int(short_range.group(2))
        end = (start // 100) * 100 + end_two
        if end < start:
            end += 100
        return end

    years = [int(part) for part in re.findall(r"\d{4}", text)]
    if years:
        return years[-1]

    try:
        return int(float(text))
    except ValueError:
        return None


def normalize_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = clean_text(value)
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    for fmt in ("%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def two_year_cutoff(today: date) -> date:
    try:
        return today.replace(year=today.year - 2)
    except ValueError:
        return today.replace(year=today.year - 2, day=28)


def status_from_last_competition(last_competition: date | None, today: date) -> str:
    if last_competition is None:
        return "unknown"
    return "likely_retired" if last_competition < two_year_cutoff(today) else "active"


def tournament_lookup(tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def build_longevity_rows(
    results: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    *,
    fencer_ids: list[str] | set[str] | None = None,
    today: date | None = None,
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    today = today or datetime.now(timezone.utc).date()
    updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    tournaments_by_id = tournament_lookup(tournaments)
    skipped = 0
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "competition_count": 0,
            "dates": [],
            "seasons": [],
        }
    )

    for result in results:
        fencer_id = clean_text(result.get("fencer_id"))
        tournament_id = clean_text(result.get("tournament_id"))
        if not fencer_id or not tournament_id:
            skipped += 1
            continue

        tournament = tournaments_by_id.get(tournament_id)
        if not tournament:
            skipped += 1
            continue

        stat = stats[fencer_id]
        stat["competition_count"] += 1

        competition_date = normalize_date(tournament.get("start_date"))
        if competition_date:
            stat["dates"].append(competition_date)

        season = season_to_int(tournament.get("season"))
        if season is not None:
            stat["seasons"].append(season)

    all_fencer_ids = {clean_text(fencer_id) for fencer_id in (fencer_ids or [])}
    all_fencer_ids.update(stats.keys())
    all_fencer_ids.discard(None)

    rows: list[dict[str, Any]] = []
    for fencer_id in sorted(all_fencer_ids):
        stat = stats.get(fencer_id)
        if not stat or stat["competition_count"] == 0:
            rows.append(
                {
                    "fencer_id": fencer_id,
                    "first_competition_date": None,
                    "last_competition_date": None,
                    "first_season": None,
                    "last_season": None,
                    "career_years": None,
                    "competitions_per_season": None,
                    "status": "unknown",
                    "updated_at": updated_at,
                }
            )
            continue

        dates = sorted(stat["dates"])
        seasons = sorted(stat["seasons"])
        first_date = dates[0] if dates else None
        last_date = dates[-1] if dates else None
        first_season = seasons[0] if seasons else None
        last_season = seasons[-1] if seasons else None
        career_years = None
        competitions_per_season = None
        if first_season is not None and last_season is not None:
            career_years = max(last_season - first_season, 0)
            denominator = career_years if career_years > 0 else 1
            competitions_per_season = round(stat["competition_count"] / denominator, 2)

        rows.append(
            {
                "fencer_id": fencer_id,
                "first_competition_date": first_date.isoformat() if first_date else None,
                "last_competition_date": last_date.isoformat() if last_date else None,
                "first_season": first_season,
                "last_season": last_season,
                "career_years": career_years,
                "competitions_per_season": competitions_per_season,
                "status": status_from_last_competition(last_date, today),
                "updated_at": updated_at,
            }
        )

    return rows, skipped


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


def batch_upsert(client, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_fencer_longevity").upsert(batch, on_conflict="fencer_id").execute()
        written += len(batch)
    return written


def compute_longevity(
    client=None,
    *,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    today: date | None = None,
    now: str | None = None,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        fencers = fetch_all(client, "fs_fencers", "id", page_size=page_size)
        results = fetch_all(client, "fs_results", "fencer_id,tournament_id", page_size=page_size)
        tournaments = fetch_all(
            client,
            "fs_tournaments",
            "id,start_date,season",
            page_size=page_size,
        )
        rows, skipped = build_longevity_rows(
            results,
            tournaments,
            fencer_ids=[row["id"] for row in fencers if row.get("id") is not None],
            today=today,
            updated_at=now,
        )
        written = batch_upsert(client, rows) if rows else 0
        summary = {
            "fencers_read": len(fencers),
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "longevity_rows": len(rows),
            "written": written,
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
    print(f"Longevity computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_longevity()
    print(
        "Longevity computation complete - "
        f"{summary['longevity_rows']} rows built, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} rows skipped"
    )


if __name__ == "__main__":
    main()

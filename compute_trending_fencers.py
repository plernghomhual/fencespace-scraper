from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "compute_trending_fencers"
PAGE_SIZE = 1000
BATCH_SIZE = 200
TRENDING_CONFLICT_COLUMNS = "fencer_id,week_start"

RESULT_SELECTS = (
    "id,tournament_id,fencer_id,rank,placement,medal,seed,entry_seed,expected_rank,world_rank,weapon,category,gender",
    "id,tournament_id,fencer_id,rank,placement,medal,seed,entry_seed",
    "id,tournament_id,fencer_id,rank,placement,medal",
)
TOURNAMENT_SELECTS = (
    "id,name,weapon,category,gender,end_date,start_date,season,type,status,has_results,is_team,team,event_type",
    "id,name,weapon,category,gender,end_date,start_date,season,type,status,has_results",
    "id,name,weapon,category,end_date,start_date,season,type",
    "id,weapon,category,season",
)
IDENTITY_SELECTS = (
    "id,fie_ids,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
)
FENCER_SELECTS = (
    "id,fie_id",
    "id",
)
RANK_TREND_SELECT = "fencer_id,weapon,category,season,rank_change,trend_direction,computed_at"
FORM_SELECT = "fencer_id,weapon,form_score,trend_direction,recent_medals,recent_avg_rank,metadata,updated_at"
SOCIAL_SELECT = "fencer_id,mention_count,mention_rank,is_stale,platform,normalized_handle,computed_at"

MEDAL_BONUS = {"gold": 25.0, "silver": 18.0, "bronze": 12.0}
MEDAL_MAP = {
    "gold": "gold",
    "g": "gold",
    "1": "gold",
    "1st": "gold",
    "silver": "silver",
    "s": "silver",
    "2": "silver",
    "2nd": "silver",
    "bronze": "bronze",
    "b": "bronze",
    "3": "bronze",
    "3rd": "bronze",
}


@dataclass
class IdentityIndexes:
    row_to_canonical: dict[str, str] = field(default_factory=dict)
    fie_to_canonical: dict[str, str] = field(default_factory=dict)


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


def round_score(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    number: int | None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        number = int(match.group(0)) if match else None
    return number


def coerce_rank(value: Any) -> int | None:
    number = coerce_int(value)
    return number if number and number > 0 else None


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_json_array(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if clean_text(item)})


def build_identity_indexes(
    identity_rows: list[dict[str, Any]] | None = None,
    fencer_rows: list[dict[str, Any]] | None = None,
) -> IdentityIndexes:
    indexes = IdentityIndexes()

    for row in identity_rows or []:
        members = parse_json_array(row.get("fs_fencer_row_ids") or row.get("fencer_ids"))
        fie_ids = parse_json_array(row.get("fie_ids"))
        canonical = clean_text(row.get("id"))
        row_id = canonical
        if not canonical and members:
            canonical = members[0]
        if not canonical:
            continue

        indexes.row_to_canonical[canonical] = canonical
        for member in members:
            indexes.row_to_canonical[member] = canonical
        for fie_id in fie_ids:
            indexes.fie_to_canonical[fie_id] = canonical

    for row in fencer_rows or []:
        row_id = clean_text(row.get("id"))
        if not row_id:
            continue
        canonical = indexes.row_to_canonical.get(row_id, row_id)
        indexes.row_to_canonical[row_id] = canonical
        fencer_fie_id: str | None = clean_text(row.get("fie_id"))
        if fencer_fie_id:
            indexes.fie_to_canonical.setdefault(fencer_fie_id, canonical)

    return indexes


def canonical_fencer_id(value: Any, indexes: IdentityIndexes | None = None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if not indexes:
        return text
    return indexes.row_to_canonical.get(text) or indexes.fie_to_canonical.get(text) or text


def medal_bucket(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return MEDAL_MAP.get(compact_key(text))


def medal_from_rank(rank: int | None) -> str | None:
    if rank == 1:
        return "gold"
    if rank == 2:
        return "silver"
    if rank == 3:
        return "bronze"
    return None


def result_medal(result: dict[str, Any], rank: int | None) -> str | None:
    return medal_bucket(result.get("medal")) or medal_from_rank(rank)


def rank_from_medal(medal: str | None) -> int | None:
    return {"gold": 1, "silver": 2, "bronze": 3}.get(medal or "")


def truthy(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    return compact_key(value) in {"1", "true", "yes", "y", "team"}


def contains_team_text(value: Any) -> bool:
    text = clean_text(value)
    return bool(text and re.search(r"\bteam\b", text, flags=re.IGNORECASE))


def is_team_event(result: dict[str, Any], tournament: dict[str, Any] | None) -> bool:
    for source in (result, tournament or {}):
        for key in ("team", "is_team", "team_event"):
            if truthy(source.get(key)):
                return True
        for key in ("category", "event_type", "type", "name"):
            if contains_team_text(source.get(key)):
                return True
    return False


def is_incomplete_event(result: dict[str, Any], tournament: dict[str, Any] | None) -> bool:
    source = tournament or result
    has_results = source.get("has_results")
    if has_results is False or compact_key(has_results) in {"false", "0", "no", "n"}:
        return True
    return compact_key(source.get("status")) in {
        "scheduled",
        "upcoming",
        "pending",
        "postponed",
        "cancelled",
        "canceled",
        "inprogress",
        "running",
    }


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        try:
            return date.fromisoformat(match.group(0))
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def normalize_week_start(week_start: Any = None, now: Any = None) -> str:
    base = parse_date(week_start) or parse_date(now) or datetime.now(timezone.utc).date()
    monday = base - timedelta(days=base.weekday())
    return monday.isoformat()


def competition_date(result: dict[str, Any], tournament: dict[str, Any] | None) -> date | None:
    for source in (result, tournament or {}):
        for key in ("end_date", "date", "start_date", "bout_date", "meeting_date", "played_at"):
            parsed = parse_date(source.get(key))
            if parsed:
                return parsed
    return None


def tournament_lookup(tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def placement_score(rank: int) -> float:
    return float(max(2, 52 - (rank * 2)))


def expected_seed(result: dict[str, Any]) -> int | None:
    for key in ("seed", "entry_seed", "expected_rank", "world_rank"):
        rank = coerce_rank(result.get(key))
        if rank:
            return rank
    return None


def result_score(result: dict[str, Any], tournament_id: str, rank: int, medal: str | None) -> tuple[float, list[str], int | None]:
    score = placement_score(rank)
    reasons = [f"rank {rank} at {tournament_id}"]

    if medal:
        score += MEDAL_BONUS[medal]
        reasons.append(f"{medal} medal at {tournament_id}")

    seed = expected_seed(result)
    upset_delta = seed - rank if seed and seed > rank else None
    if upset_delta:
        score += min(20.0, float(upset_delta * 2))
        reasons.append(f"seed upset +{upset_delta} at {tournament_id}")

    return score, reasons, upset_delta


def form_index(form_rows: list[dict[str, Any]], indexes: IdentityIndexes | None) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in form_rows:
        fencer_id = canonical_fencer_id(row.get("fencer_id"), indexes)
        form_score = coerce_float(row.get("form_score"))
        if not fencer_id or form_score is None:
            continue
        existing = grouped.get(fencer_id)
        if existing is None or form_score > existing["form_score"]:
            grouped[fencer_id] = {
                "form_score": form_score,
                "trend_direction": clean_text(row.get("trend_direction")) or "stable",
            }
    return grouped


def rank_trend_index(rank_trends: list[dict[str, Any]], indexes: IdentityIndexes | None) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rank_trends:
        fencer_id = canonical_fencer_id(row.get("fencer_id"), indexes)
        rank_change = coerce_int(row.get("rank_change"))
        if not fencer_id or rank_change is None:
            continue
        season = coerce_int(row.get("season")) or 0
        existing = grouped.get(fencer_id)
        if existing is None or (season, abs(rank_change)) > (existing["season"], abs(existing["rank_change"])):
            grouped[fencer_id] = {
                "rank_change": rank_change,
                "season": season,
                "trend_direction": clean_text(row.get("trend_direction")),
            }
    return grouped


def social_index(social_rows: list[dict[str, Any]], indexes: IdentityIndexes | None) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in social_rows:
        fencer_id = canonical_fencer_id(row.get("fencer_id"), indexes)
        mentions = coerce_int(row.get("mention_count")) or 0
        if not fencer_id or mentions <= 0:
            continue
        entry = grouped.setdefault(fencer_id, {"mention_count": 0, "platforms": set(), "has_fresh": False})
        entry["mention_count"] += mentions
        platform = clean_text(row.get("platform"))
        if platform:
            entry["platforms"].add(platform)
        if row.get("is_stale") is not True:
            entry["has_fresh"] = True
    return grouped


def build_trending_rows(
    results: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    rank_trends: list[dict[str, Any]] | None = None,
    form_rows: list[dict[str, Any]] | None = None,
    social_rows: list[dict[str, Any]] | None = None,
    identity_indexes: IdentityIndexes | None = None,
    week_start: Any = None,
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    indexes = identity_indexes or IdentityIndexes()
    week_start_iso = normalize_week_start(week_start, updated_at)
    week_start_date = date.fromisoformat(week_start_iso)
    week_end_date = week_start_date + timedelta(days=7)
    tournaments_by_id = tournament_lookup(tournaments)
    forms_by_fencer = form_index(form_rows or [], indexes)
    ranks_by_fencer = rank_trend_index(rank_trends or [], indexes)
    socials_by_fencer = social_index(social_rows or [], indexes)
    now = updated_at or datetime.now(timezone.utc).isoformat()

    summary = {
        "skipped_missing_fencer": 0,
        "skipped_missing_tournament": 0,
        "skipped_missing_date": 0,
        "skipped_outside_week": 0,
        "skipped_team_results": 0,
        "skipped_incomplete_events": 0,
        "skipped_insufficient_result": 0,
        "skipped_duplicate_results": 0,
        "recent_results_used": 0,
        "skipped": 0,
    }
    by_fencer_event: dict[tuple[str, str], dict[str, Any]] = {}

    for result in results:
        fencer_id = canonical_fencer_id(result.get("fencer_id"), indexes)
        if not fencer_id:
            summary["skipped_missing_fencer"] += 1
            continue

        tournament_id = clean_text(result.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id) if tournament_id else None
        if not tournament_id or not tournament:
            summary["skipped_missing_tournament"] += 1
            continue

        if is_team_event(result, tournament):
            summary["skipped_team_results"] += 1
            continue
        if is_incomplete_event(result, tournament):
            summary["skipped_incomplete_events"] += 1
            continue

        event_date = competition_date(result, tournament)
        if not event_date:
            summary["skipped_missing_date"] += 1
            continue
        if event_date < week_start_date or event_date >= week_end_date:
            summary["skipped_outside_week"] += 1
            continue

        rank = coerce_rank(result.get("rank") if result.get("rank") is not None else result.get("placement"))
        medal = result_medal(result, rank)
        rank = rank or rank_from_medal(medal)
        if rank is None and medal is None:
            summary["skipped_insufficient_result"] += 1
            continue

        event_score, event_reasons, upset_delta = result_score(result, tournament_id, rank or 0, medal)
        key = (fencer_id, tournament_id)
        event: dict[str, Any] = {
            "fencer_id": fencer_id,
            "tournament_id": tournament_id,
            "date": event_date.isoformat(),
            "rank": rank,
            "medal": medal,
            "event_score": event_score,
            "reasons": event_reasons,
            "upset_delta": upset_delta,
            "result_id": clean_text(result.get("id")),
        }
        existing = by_fencer_event.get(key)
        if existing is not None:
            summary["skipped_duplicate_results"] += 1
            existing_key = (existing["event_score"], -(existing["rank"] or 999999), existing.get("result_id") or "")
            event_key = (event["event_score"], -(event["rank"] or 999999), event.get("result_id") or "")
            if event_key > existing_key:
                by_fencer_event[key] = event
            continue
        by_fencer_event[key] = event

    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in by_fencer_event.values():
        grouped.setdefault(event["fencer_id"], []).append(event)

    rows: list[dict[str, Any]] = []
    for fencer_id, events in sorted(grouped.items()):
        events.sort(key=lambda item: (item["date"], item["tournament_id"], item.get("result_id") or ""))
        raw_recent_score = sum(event["event_score"] for event in events)
        best_rank = min(event["rank"] for event in events if event.get("rank") is not None)
        reasons: list[str] = []
        for event in sorted(events, key=lambda item: (-(item["event_score"]), item["date"], item["tournament_id"]))[:3]:
            for reason in event["reasons"]:
                if reason not in reasons:
                    reasons.append(reason)

        form = forms_by_fencer.get(fencer_id)
        if form:
            form_score_value = form["form_score"]
            form_bonus = min(15.0, form_score_value * 0.15)
            raw_recent_score += form_bonus
            reasons.append(f"form score {round_score(form_score_value)} ({form['trend_direction']})")

        recent_results_score = round_score(min(100.0, raw_recent_score))

        rank_trend = ranks_by_fencer.get(fencer_id)
        rank_delta = rank_trend["rank_change"] if rank_trend else None
        rank_score = min(25.0, max(0, rank_delta or 0) * 1.25)
        if rank_delta is not None and rank_delta > 0:
            reasons.append(f"rank jump +{rank_delta}")
        elif rank_delta is not None and rank_delta < 0:
            reasons.append(f"rank drop {rank_delta}")

        social = socials_by_fencer.get(fencer_id)
        if social:
            mention_count = social["mention_count"]
            social_score = 0.0 if not social["has_fresh"] else min(5.0, mention_count / 20.0)
            social_score = round_score(social_score)
            reasons.append(f"social mentions {mention_count}")
        else:
            social_score = 0.0
            reasons.append("social data unavailable")

        total_score = round_score(recent_results_score + rank_score + social_score)
        rows.append(
            {
                "fencer_id": fencer_id,
                "week_start": week_start_iso,
                "score": total_score,
                "rank_delta": rank_delta,
                "recent_results_score": recent_results_score,
                "social_score": social_score,
                "reasons": reasons,
                "updated_at": now,
                "_best_rank": best_rank,
            }
        )

    for row in rows:
        row.pop("_best_rank", None)

    rows.sort(
        key=lambda row: (
            -row["score"],
            -(row["rank_delta"] or 0),
            -row["recent_results_score"],
            -row["social_score"],
            row["fencer_id"],
        )
    )
    summary["recent_results_used"] = len(by_fencer_event)
    summary["skipped"] = sum(
        value
        for key, value in summary.items()
        if key.startswith("skipped_") and key != "skipped"
    )
    return rows, summary


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


def fetch_with_fallbacks(client, table: str, select_options: tuple[str, ...], page_size: int) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in select_options:
        try:
            return fetch_all(client, table, columns, page_size)
        except Exception as exc:
            last_error = exc
            print(f"  Select fallback for {table}: {exc}")
    if last_error:
        raise last_error
    return []


def fetch_optional(client, table: str, columns: str, page_size: int) -> list[dict[str, Any]]:
    try:
        return fetch_all(client, table, columns, page_size)
    except Exception as exc:
        print(f"Optional input {table} unavailable; continuing without it: {exc}")
        return []


def _probe_trending_table(client) -> None:
    client.table("fs_trending_fencers").select("fencer_id").limit(0).execute()


def batch_upsert(client, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_trending_fencers").upsert(
            batch,
            on_conflict=TRENDING_CONFLICT_COLUMNS,
        ).execute()
        written += len(batch)
    return written


def compute_trending_fencers(
    client=None,
    *,
    week_start: Any = None,
    now: str | None = None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        if update_state:
            previous_run = get_state(SOURCE, "last_run")
        else:
            previous_run = None

        _probe_trending_table(client)
        computed_at = now or datetime.now(timezone.utc).isoformat()
        week_start_iso = normalize_week_start(week_start, computed_at)

        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size)
        identity_rows = fetch_with_fallbacks(client, "fs_fencer_identities", IDENTITY_SELECTS, page_size)
        fencer_rows = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size)
        rank_trends = fetch_optional(client, "fs_rankings_trends", RANK_TREND_SELECT, page_size)
        form_rows = fetch_optional(client, "fs_fencer_form", FORM_SELECT, page_size)
        social_rows = fetch_optional(client, "fs_fencer_social_leaderboard", SOCIAL_SELECT, page_size)

        identity_indexes = build_identity_indexes(identity_rows, fencer_rows)
        rows, build_summary = build_trending_rows(
            results,
            tournaments,
            rank_trends=rank_trends,
            form_rows=form_rows,
            social_rows=social_rows,
            identity_indexes=identity_indexes,
            week_start=week_start_iso,
            updated_at=computed_at,
        )
        written = batch_upsert(client, rows) if rows else 0

        summary: dict[str, Any] = {
            "week_start": week_start_iso,
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "identity_rows": len(identity_rows),
            "fencer_rows": len(fencer_rows),
            "rank_trends_read": len(rank_trends),
            "form_rows_read": len(form_rows),
            "social_rows_read": len(social_rows),
            "leaderboard_rows": len(rows),
            "written": written,
            "failed": 0,
            **build_summary,
        }
        if isinstance(previous_run, dict) and previous_run.get("week_start"):
            summary["previous_week_start"] = previous_run["week_start"]
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": datetime.now(timezone.utc).isoformat(), **summary})
        if run_log:
            run_log.complete(written=written, failed=0, skipped=summary["skipped"], metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Trending fencers computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_trending_fencers()
    print(
        "Trending fencers computation complete - "
        f"week_start={summary['week_start']}, rows={summary['leaderboard_rows']}, "
        f"written={summary['written']}, skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()

"""Backend fantasy fencing league model helpers and scoring engine.

Game rules:
- League admins create leagues, teams, scoring periods, rosters, and draft
  picks manually or through a future authenticated frontend.
- Only active starter roster slots score. Bench and reserve slots are stored
  for roster management but do not earn weekly points.
- A verified result scores participation points, medal points, and an upset
  bonus when the final rank beats the pre-event seed/ranking by the configured
  threshold. Default scoring is 1 participation point, 12/8/5 medal points,
  and 10/6/3 upset points for 16/8/4+ place improvements.
- Duplicate result rows for the same fencer in the same tournament are scored
  once using the best final rank.
- Weekly scoring is idempotent: score rows use deterministic UUIDv5 IDs and
  upsert on period/team/fencer/result_key.

Manual setup:
1. Apply `supabase/migrations/20260602_fantasy_league.sql`.
2. Insert an admin-managed league row in `fs_fantasy_leagues`.
3. Insert teams, draft picks, and active roster rows. Keep user IDs optional
   unless a frontend/auth integration already exists.
4. Lock the scoring period after lineups are final, then run this module's
   scoring wrapper with service-role credentials.
"""

from __future__ import annotations

import copy
import json
import os
import re
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "fantasy_league"
PAGE_SIZE = 1000
BATCH_SIZE = 100
SCORE_CONFLICT_COLUMNS = "period_id,team_id,fencer_id,result_key"
SCORE_UUID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "fencespace:fantasy-score")

DEFAULT_SCORING_RULES: dict[str, Any] = {
    "participation_points": 1,
    "medal_points": {"gold": 12, "silver": 8, "bronze": 5},
    "upset_bonus": {
        "tiers": [
            {"improvement": 16, "points": 10},
            {"improvement": 8, "points": 6},
            {"improvement": 4, "points": 3},
        ],
    },
    "scoring_slot_types": ["starter"],
}

MEDAL_ALIASES = {
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

RESULT_SELECTS = (
    "id,tournament_id,fencer_id,rank,placement,medal,verified,status,metadata",
    "id,tournament_id,fencer_id,rank,placement,medal,metadata",
    "tournament_id,fencer_id,rank,placement,medal,metadata",
)


class FantasyValidationError(ValueError):
    """Raised when fantasy setup or scoring state violates league rules."""

    def __init__(self, issues: list[dict[str, Any]]):
        self.issues = issues
        super().__init__("; ".join(issue["code"] for issue in issues))


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", (clean_text(value) or "").casefold())


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value).strip())
    except Exception:
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None
    if number == number.to_integral_value():
        return int(number)
    return None


def to_positive_int(value: Any) -> int | None:
    number = to_int(value)
    return number if number is not None and number > 0 else None


def metadata_dict(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def row_value(row: dict[str, Any], *keys: str) -> Any:
    metadata = metadata_dict(row)
    for key in keys:
        if row.get(key) not in (None, ""):
            return row.get(key)
        if metadata.get(key) not in (None, ""):
            return metadata.get(key)
    return None


def issue(code: str, message: str, **context: Any) -> dict[str, Any]:
    payload = {"code": code, "message": message}
    payload.update({key: value for key, value in context.items() if value is not None})
    return payload


def parse_datetime(value: Any, end_of_day: bool = False) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        parsed_time = time.max if end_of_day else time.min
        return datetime.combine(date.fromisoformat(text), parsed_time, tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text[:10])
        except ValueError:
            return None
        parsed_time = time.max if end_of_day else time.min
        parsed = datetime.combine(parsed_date, parsed_time)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def active_roster_row(row: dict[str, Any]) -> bool:
    return clean_text(row.get("released_at")) is None


def league_id(league: dict[str, Any]) -> str | None:
    return clean_text(league.get("id"))


def team_ids_for_league(teams: list[dict[str, Any]], league: dict[str, Any]) -> set[str]:
    lid = league_id(league)
    return {
        team_id
        for team in teams
        if clean_text(team.get("league_id")) == lid
        for team_id in [clean_text(team.get("id"))]
        if team_id
    }


def rules_for_league(league: dict[str, Any]) -> dict[str, Any]:
    rules = copy.deepcopy(DEFAULT_SCORING_RULES)
    custom = league.get("rules") or league.get("scoring_rules") or {}
    if isinstance(custom, str):
        try:
            custom = json.loads(custom)
        except json.JSONDecodeError:
            custom = {}
    if not isinstance(custom, dict):
        return rules
    for key, value in custom.items():
        if isinstance(value, dict) and isinstance(rules.get(key), dict):
            rules[key].update(value)
        else:
            rules[key] = value
    return rules


def validate_draft_picks(
    league: dict[str, Any],
    teams: list[dict[str, Any]],
    picks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    lid = league_id(league)
    valid_team_ids = team_ids_for_league(teams, league)
    pick_numbers: Counter[int] = Counter()
    fencer_picks: Counter[str] = Counter()
    team_pick_counts: Counter[str] = Counter()

    for pick in picks:
        if clean_text(pick.get("league_id")) != lid:
            issues.append(issue("wrong_league", "Draft pick belongs to a different league."))
            continue

        team_id = clean_text(pick.get("team_id"))
        if team_id not in valid_team_ids:
            issues.append(issue("unknown_team", "Draft pick references an unknown team.", team_id=team_id))
        elif not pick.get("skipped"):
            team_pick_counts[team_id] += 1

        pick_number = to_positive_int(pick.get("pick_number"))
        round_number = to_positive_int(pick.get("round_number"))
        if pick_number is None:
            issues.append(issue("invalid_pick_number", "Draft pick number must be positive."))
        else:
            pick_numbers[pick_number] += 1
        if round_number is None:
            issues.append(issue("invalid_round_number", "Draft round number must be positive."))

        fencer_id = clean_text(pick.get("fencer_id"))
        if pick.get("skipped"):
            if fencer_id:
                issues.append(issue("skipped_pick_has_fencer", "Skipped draft picks cannot select a fencer."))
        elif not fencer_id:
            issues.append(issue("missing_fencer_pick", "Draft pick must select a fencer unless skipped."))
        else:
            fencer_picks[fencer_id] += 1

    for pick_number, count in pick_numbers.items():
        if count > 1:
            issues.append(issue("duplicate_pick_number", "Draft pick number is duplicated.", pick_number=pick_number))
    for fencer_id, count in fencer_picks.items():
        if count > 1:
            issues.append(issue("duplicate_fencer_pick", "Fencer was drafted more than once.", fencer_id=fencer_id))

    roster_size = to_positive_int(league.get("roster_size"))
    if roster_size:
        for team_id, count in team_pick_counts.items():
            if count > roster_size:
                issues.append(issue("team_draft_over_roster_size", "Team drafted more fencers than roster size.", team_id=team_id))

    return issues


def validate_roster(
    league: dict[str, Any],
    teams: list[dict[str, Any]],
    roster_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    lid = league_id(league)
    valid_team_ids = team_ids_for_league(teams, league)
    allowed_slots = {"starter", "bench", "reserve"}
    active_fencers: Counter[str] = Counter()
    team_active_counts: Counter[str] = Counter()
    team_starter_counts: Counter[str] = Counter()

    for row in roster_rows:
        if clean_text(row.get("league_id")) != lid:
            issues.append(issue("wrong_league", "Roster row belongs to a different league."))
            continue
        if not active_roster_row(row):
            continue

        team_id = clean_text(row.get("team_id"))
        if team_id not in valid_team_ids:
            issues.append(issue("unknown_team", "Roster row references an unknown team.", team_id=team_id))
            continue

        fencer_id = clean_text(row.get("fencer_id"))
        if not fencer_id:
            issues.append(issue("missing_roster_fencer", "Active roster rows must include a fencer."))
            continue

        slot_type = compact_key(row.get("slot_type") or "starter")
        if slot_type not in allowed_slots:
            issues.append(issue("invalid_slot_type", "Roster slot type is invalid.", slot_type=slot_type))
            continue

        active_fencers[fencer_id] += 1
        team_active_counts[team_id] += 1
        if slot_type == "starter":
            team_starter_counts[team_id] += 1

    for fencer_id, count in active_fencers.items():
        if count > 1:
            issues.append(issue("duplicate_active_fencer", "Fencer appears on more than one active roster.", fencer_id=fencer_id))

    roster_size = to_positive_int(league.get("roster_size"))
    if roster_size:
        for team_id, count in team_active_counts.items():
            if count > roster_size:
                issues.append(issue("roster_size_exceeded", "Team active roster exceeds league roster size.", team_id=team_id))

    starter_slots = to_positive_int(league.get("starter_slots"))
    if starter_slots:
        for team_id, count in team_starter_counts.items():
            if count > starter_slots:
                issues.append(issue("starter_slots_exceeded", "Team has too many active starters.", team_id=team_id))

    return issues


def validate_period_allows_roster_change(period: dict[str, Any]) -> list[dict[str, Any]]:
    status = compact_key(period.get("status") or "open")
    if status in {"locked", "scored", "closed", "final"} or clean_text(period.get("locked_at")):
        return [issue("period_locked", "Roster and draft changes are blocked for locked scoring periods.")]
    return []


def validate_period_allows_scoring(period: dict[str, Any]) -> list[dict[str, Any]]:
    status = compact_key(period.get("status") or "open")
    if status not in {"locked", "scored"} and not clean_text(period.get("locked_at")):
        return [issue("period_not_locked", "Scoring requires a locked or already-scored period.")]
    if not clean_text(period.get("id")):
        return [issue("missing_period_id", "Scoring period must have an id.")]
    return []


def result_rank(result: dict[str, Any]) -> int | None:
    return to_positive_int(result.get("rank") if result.get("rank") is not None else result.get("placement"))


def result_medal(result: dict[str, Any]) -> str | None:
    medal = MEDAL_ALIASES.get(compact_key(result.get("medal")))
    if medal:
        return medal
    rank = result_rank(result)
    if rank == 1:
        return "gold"
    if rank == 2:
        return "silver"
    if rank == 3:
        return "bronze"
    return None


def result_is_verified(result: dict[str, Any]) -> bool:
    metadata = metadata_dict(result)
    if result.get("verified") is False or metadata.get("verified") is False:
        return False
    status = compact_key(result.get("status") or metadata.get("status") or metadata.get("review_status"))
    if status in {"unverified", "pending", "draft", "rejected"}:
        return False
    has_identity = bool(clean_text(result.get("tournament_id")) and clean_text(result.get("fencer_id")))
    has_result = result_rank(result) is not None or result_medal(result) is not None
    return has_identity and has_result


def result_seed_or_rank(result: dict[str, Any]) -> int | None:
    return to_positive_int(
        row_value(
            result,
            "seed",
            "entry_seed",
            "pre_event_seed",
            "world_rank_before",
            "pre_event_world_rank",
            "ranking_before",
        )
    )


def upset_bonus_points(result: dict[str, Any], rules: dict[str, Any]) -> int:
    rank = result_rank(result)
    baseline = result_seed_or_rank(result)
    if rank is None or baseline is None or baseline <= rank:
        return 0
    improvement = baseline - rank
    tiers = rules.get("upset_bonus", {}).get("tiers", [])
    normalized_tiers: list[tuple[int, int]] = []
    for tier in tiers:
        if isinstance(tier, dict):
            threshold = to_positive_int(tier.get("improvement"))
            points = to_int(tier.get("points"))
        elif isinstance(tier, list | tuple) and len(tier) == 2:
            threshold = to_positive_int(tier[0])
            points = to_int(tier[1])
        else:
            continue
        if threshold is not None and points is not None:
            normalized_tiers.append((threshold, points))
    for threshold, points in sorted(normalized_tiers, reverse=True):
        if improvement >= threshold:
            return points
    return 0


def score_result(result: dict[str, Any], rules: dict[str, Any]) -> tuple[int, dict[str, int]]:
    medal = result_medal(result)
    medal_points = rules.get("medal_points", {})
    components: dict[str, int] = {
        "participation": to_int(rules.get("participation_points")) or 0,
        "medal": to_int(medal_points.get(medal)) or 0 if medal else 0,
        "upset": upset_bonus_points(result, rules),
    }
    return sum(components.values()), components


def tournament_lookup(tournaments: list[dict[str, Any]] | dict[str, dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if not tournaments:
        return {}
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {str(row["id"]): row for row in tournaments if row.get("id") is not None}


def result_date_range(result: dict[str, Any], tournament: dict[str, Any] | None) -> tuple[datetime | None, datetime | None]:
    source = tournament or {}
    start = (
        parse_datetime(row_value(result, "result_date", "date", "completed_at", "updated_at"))
        or parse_datetime(source.get("start_date"))
        or parse_datetime(source.get("date"))
    )
    end = parse_datetime(source.get("end_date"), end_of_day=True) or start
    return start, end


def result_in_period(
    result: dict[str, Any],
    tournament: dict[str, Any] | None,
    period: dict[str, Any],
) -> bool:
    period_start = parse_datetime(period.get("starts_at"))
    period_end = parse_datetime(period.get("ends_at"), end_of_day=True)
    if not period_start and not period_end:
        return True

    result_start, result_end = result_date_range(result, tournament)
    if not result_start and not result_end:
        return False
    result_start = result_start or result_end
    result_end = result_end or result_start
    if period_start and result_end and result_end < period_start:
        return False
    if period_end and result_start and result_start > period_end:
        return False
    return True


def result_key(result: dict[str, Any]) -> str:
    tournament_id = clean_text(result.get("tournament_id")) or "unknown-tournament"
    fencer_id = clean_text(result.get("fencer_id")) or "unknown-fencer"
    return f"{tournament_id}:{fencer_id}"


def stable_score_id(period_id: str, team_id: str, fencer_id: str, key: str) -> str:
    return str(uuid.uuid5(SCORE_UUID_NAMESPACE, f"{period_id}:{team_id}:{fencer_id}:{key}"))


def better_result(current: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if current is None:
        return candidate
    current_rank = result_rank(current)
    candidate_rank = result_rank(candidate)
    if current_rank is None:
        return candidate
    if candidate_rank is None:
        return current
    if candidate_rank < current_rank:
        return candidate
    return current


def scoring_rosters(
    league: dict[str, Any],
    roster_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    scoring_slots = {
        compact_key(slot)
        for slot in rules_for_league(league).get("scoring_slot_types", ["starter"])
        if clean_text(slot)
    }
    rows: dict[str, dict[str, Any]] = {}
    for row in roster_rows:
        if not active_roster_row(row):
            continue
        slot_type = compact_key(row.get("slot_type") or "starter")
        if slot_type not in scoring_slots:
            continue
        fencer_id = clean_text(row.get("fencer_id"))
        if fencer_id:
            rows[fencer_id] = row
    return rows


def source_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "result_id": clean_text(result.get("id")),
        "tournament_id": clean_text(result.get("tournament_id")),
        "rank": result_rank(result),
        "medal": result_medal(result),
        "seed": result_seed_or_rank(result),
    }


def compute_weekly_scores(
    league: dict[str, Any],
    period: dict[str, Any],
    teams: list[dict[str, Any]],
    roster_rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    tournaments: list[dict[str, Any]] | dict[str, dict[str, Any]] | None = None,
    scored_at: str | None = None,
    validate: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    issues = validate_period_allows_scoring(period)
    if validate:
        issues.extend(validate_roster(league, teams, roster_rows))
    if issues:
        raise FantasyValidationError(issues)

    now = scored_at or datetime.now(UTC).isoformat()
    lid = league_id(league)
    period_id = clean_text(period.get("id"))
    rules = rules_for_league(league)
    scoring_roster_by_fencer = scoring_rosters(league, roster_rows)
    tournaments_by_id = tournament_lookup(tournaments)
    best_results: dict[str, dict[str, Any]] = {}
    skipped = 0

    for result in results:
        if not result_is_verified(result):
            skipped += 1
            continue
        fencer_id = clean_text(result.get("fencer_id"))
        if fencer_id not in scoring_roster_by_fencer:
            skipped += 1
            continue
        tournament_id = clean_text(result.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id) if tournament_id else None
        if not result_in_period(result, tournament, period):
            skipped += 1
            continue
        key = result_key(result)
        best_results[key] = better_result(best_results.get(key), result)

    rows: list[dict[str, Any]] = []
    for key in sorted(best_results):
        result = best_results[key]
        fencer_id = clean_text(result.get("fencer_id"))
        roster = scoring_roster_by_fencer[fencer_id]  # type: ignore[index]
        team_id = clean_text(roster.get("team_id"))
        points, components = score_result(result, rules)
        rows.append(
            {
                "id": stable_score_id(period_id or "", team_id or "", fencer_id or "", key),
                "league_id": lid,
                "period_id": period_id,
                "team_id": team_id,
                "fencer_id": fencer_id,
                "tournament_id": clean_text(result.get("tournament_id")),
                "result_key": key,
                "points": points,
                "components": components,
                "source_result": source_result_payload(result),
                "scored_at": now,
                "updated_at": now,
            }
        )

    summary = {
        "results_read": len(results),
        "eligible_results": len(best_results),
        "scored_rows": len(rows),
        "skipped_results": skipped,
    }
    return rows, summary


def fetch_all(
    client,
    table: str,
    columns: str,
    configure: Callable[[Any], Any] | None = None,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = client.table(table).select(columns)
        if configure:
            query = configure(query)
        page = query.range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def fetch_first(
    client,
    table: str,
    columns: str,
    configure: Callable[[Any], Any],
) -> dict[str, Any]:
    rows = fetch_all(client, table, columns, configure=configure, page_size=1)
    if not rows:
        raise RuntimeError(f"No {table} row found for fantasy scoring.")
    return rows[0]


def fetch_results(client, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    last_error = None
    for columns in RESULT_SELECTS:
        try:
            return fetch_all(client, "fs_results", columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    raise RuntimeError("Unable to fetch fs_results rows for fantasy scoring.") from last_error


def upsert_weekly_scores(
    client,
    rows: list[dict[str, Any]],
    batch_size: int = BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_fantasy_weekly_scores").upsert(
            batch,
            on_conflict=SCORE_CONFLICT_COLUMNS,
        ).execute()
        written += len(batch)
    return written


def score_fantasy_period(
    league_id_value: str,
    period_key: str,
    client=None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    scored_at: str | None = None,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        league = fetch_first(
            client,
            "fs_fantasy_leagues",
            "id,name,season,roster_size,starter_slots,rules",
            lambda query: query.eq("id", league_id_value),
        )
        period = fetch_first(
            client,
            "fs_fantasy_scoring_periods",
            "id,league_id,period_key,status,starts_at,ends_at,locked_at",
            lambda query: query.eq("league_id", league_id_value).eq("period_key", period_key),
        )
        teams = fetch_all(
            client,
            "fs_fantasy_teams",
            "id,league_id,name",
            configure=lambda query: query.eq("league_id", league_id_value),
            page_size=page_size,
        )
        rosters = fetch_all(
            client,
            "fs_fantasy_rosters",
            "league_id,team_id,fencer_id,slot_type,released_at",
            configure=lambda query: query.eq("league_id", league_id_value),
            page_size=page_size,
        )
        results = fetch_results(client, page_size=page_size)
        tournaments = fetch_all(
            client,
            "fs_tournaments",
            "id,start_date,end_date",
            page_size=page_size,
        )
        rows, summary = compute_weekly_scores(
            league,
            period,
            teams,
            rosters,
            results,
            tournaments=tournaments,
            scored_at=scored_at,
        )
        written = upsert_weekly_scores(client, rows) if rows else 0
        summary = {**summary, "written": written}
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "league_id": league_id_value,
                    "period_key": period_key,
                    **summary,
                },
            )
        if run_log:
            run_log.complete(
                written=written,
                failed=0,
                skipped=summary["skipped_results"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous fantasy scoring state: {previous_state}")
    league = os.environ.get("FANTASY_LEAGUE_ID")
    period = os.environ.get("FANTASY_PERIOD_KEY")
    if not league or not period:
        raise RuntimeError("FANTASY_LEAGUE_ID and FANTASY_PERIOD_KEY must be set.")
    summary = score_fantasy_period(league, period)
    print(
        "Fantasy scoring complete - "
        f"{summary['scored_rows']} score rows, "
        f"{summary['written']} upserted, "
        f"{summary['skipped_results']} results skipped"
    )


if __name__ == "__main__":
    main()

import os
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"
LEAGUE_ID = "10000000-0000-0000-0000-000000000001"
PERIOD_ID = "20000000-0000-0000-0000-000000000001"
TEAM_A = "30000000-0000-0000-0000-000000000001"
TEAM_B = "30000000-0000-0000-0000-000000000002"
FENCER_ALICE = "40000000-0000-0000-0000-000000000001"
FENCER_BOB = "40000000-0000-0000-0000-000000000002"
FENCER_CAROL = "40000000-0000-0000-0000-000000000003"
FENCER_DAN = "40000000-0000-0000-0000-000000000004"


def base_league():
    return {
        "id": LEAGUE_ID,
        "name": "FenceSpace Worlds Draft",
        "season": "2026",
        "roster_size": 2,
        "starter_slots": 1,
    }


def base_teams():
    return [
        {"id": TEAM_A, "league_id": LEAGUE_ID, "name": "Lefty Line"},
        {"id": TEAM_B, "league_id": LEAGUE_ID, "name": "Right of Way"},
    ]


def locked_period():
    return {
        "id": PERIOD_ID,
        "league_id": LEAGUE_ID,
        "period_key": "2026-W23",
        "status": "locked",
        "starts_at": "2026-06-01T00:00:00+00:00",
        "ends_at": "2026-06-07T23:59:59+00:00",
        "locked_at": "2026-06-01T00:00:00+00:00",
    }


def test_fantasy_league_migration_defines_service_only_tables_and_rules_comments():
    migration = Path("supabase/migrations/20260602_fantasy_league.sql")

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    for table in (
        "fs_fantasy_leagues",
        "fs_fantasy_teams",
        "fs_fantasy_rosters",
        "fs_fantasy_draft_picks",
        "fs_fantasy_scoring_periods",
        "fs_fantasy_weekly_scores",
    ):
        assert f"create table if not exists public.{table}" in normalized
        assert f"alter table public.{table} enable row level security" in normalized

    assert "owner_user_id uuid" in normalized
    assert "manager_user_id uuid" in normalized
    assert "auth.users" not in normalized
    assert "unique (league_id, period_key)" in normalized
    assert "unique (league_id, pick_number)" in normalized
    assert "idx_fs_fantasy_rosters_active_fencer" in normalized
    assert "unique (period_id, team_id, fencer_id, result_key)" in normalized
    assert "revoke all on public.fs_fantasy_leagues from anon, authenticated" in normalized
    assert "game rules" in normalized
    assert "manual setup" in normalized


def test_validate_draft_picks_rosters_and_locked_periods():
    from fantasy_league import (
        validate_draft_picks,
        validate_period_allows_roster_change,
        validate_roster,
    )

    draft_issues = validate_draft_picks(
        base_league(),
        base_teams(),
        [
            {
                "league_id": LEAGUE_ID,
                "team_id": TEAM_A,
                "round_number": 1,
                "pick_number": 1,
                "fencer_id": FENCER_ALICE,
            },
            {
                "league_id": LEAGUE_ID,
                "team_id": TEAM_B,
                "round_number": 1,
                "pick_number": 1,
                "fencer_id": FENCER_BOB,
            },
            {
                "league_id": LEAGUE_ID,
                "team_id": TEAM_B,
                "round_number": 1,
                "pick_number": 2,
                "fencer_id": FENCER_ALICE,
            },
            {
                "league_id": LEAGUE_ID,
                "team_id": "missing-team",
                "round_number": 2,
                "pick_number": 3,
                "fencer_id": FENCER_CAROL,
            },
        ],
    )

    assert {issue["code"] for issue in draft_issues} == {
        "duplicate_pick_number",
        "duplicate_fencer_pick",
        "unknown_team",
    }

    roster_issues = validate_roster(
        base_league(),
        base_teams(),
        [
            {"league_id": LEAGUE_ID, "team_id": TEAM_A, "fencer_id": FENCER_ALICE, "slot_type": "starter"},
            {"league_id": LEAGUE_ID, "team_id": TEAM_A, "fencer_id": FENCER_BOB, "slot_type": "starter"},
            {"league_id": LEAGUE_ID, "team_id": TEAM_A, "fencer_id": FENCER_CAROL, "slot_type": "bench"},
            {"league_id": LEAGUE_ID, "team_id": TEAM_B, "fencer_id": FENCER_ALICE, "slot_type": "starter"},
            {
                "league_id": LEAGUE_ID,
                "team_id": TEAM_B,
                "fencer_id": FENCER_DAN,
                "slot_type": "starter",
                "released_at": "2026-05-31T00:00:00+00:00",
            },
        ],
    )

    assert {issue["code"] for issue in roster_issues} == {
        "duplicate_active_fencer",
        "roster_size_exceeded",
        "starter_slots_exceeded",
    }

    locked_issues = validate_period_allows_roster_change(locked_period())
    assert {issue["code"] for issue in locked_issues} == {"period_locked"}


def test_compute_weekly_scores_uses_verified_results_medals_upsets_and_starters_only():
    from fantasy_league import compute_weekly_scores

    rosters = [
        {"league_id": LEAGUE_ID, "team_id": TEAM_A, "fencer_id": FENCER_ALICE, "slot_type": "starter"},
        {"league_id": LEAGUE_ID, "team_id": TEAM_A, "fencer_id": FENCER_BOB, "slot_type": "bench"},
        {"league_id": LEAGUE_ID, "team_id": TEAM_B, "fencer_id": FENCER_CAROL, "slot_type": "starter"},
    ]
    tournaments = [
        {"id": "tournament-in-period", "start_date": "2026-06-03", "end_date": "2026-06-03"},
        {"id": "tournament-outside", "start_date": "2026-06-09", "end_date": "2026-06-09"},
    ]
    results = [
        {
            "id": "result-alice-gold",
            "tournament_id": "tournament-in-period",
            "fencer_id": FENCER_ALICE,
            "rank": 1,
            "medal": "Gold",
            "metadata": {"seed": 20, "source": "fie_results"},
        },
        {
            "id": "result-bob-silver",
            "tournament_id": "tournament-in-period",
            "fencer_id": FENCER_BOB,
            "rank": 2,
            "medal": "Silver",
            "metadata": {"seed": 2, "source": "fie_results"},
        },
        {
            "id": "result-carol-bronze",
            "tournament_id": "tournament-in-period",
            "fencer_id": FENCER_CAROL,
            "rank": 3,
            "medal": "Bronze",
            "metadata": {"seed": 6, "source": "fie_results"},
        },
        {
            "id": "result-carol-duplicate-worse",
            "tournament_id": "tournament-in-period",
            "fencer_id": FENCER_CAROL,
            "rank": 4,
            "medal": None,
            "metadata": {"seed": 6, "source": "fie_results"},
        },
        {
            "id": "result-alice-unverified",
            "tournament_id": "tournament-in-period",
            "fencer_id": FENCER_ALICE,
            "rank": 8,
            "verified": False,
            "metadata": {"seed": 1},
        },
        {
            "id": "result-alice-outside",
            "tournament_id": "tournament-outside",
            "fencer_id": FENCER_ALICE,
            "rank": 1,
            "medal": "Gold",
            "metadata": {"seed": 1, "source": "fie_results"},
        },
    ]

    rows, summary = compute_weekly_scores(
        base_league(),
        locked_period(),
        base_teams(),
        rosters,
        results,
        tournaments=tournaments,
        scored_at=NOW,
    )

    assert summary["scored_rows"] == 2
    by_fencer = {row["fencer_id"]: row for row in rows}
    assert set(by_fencer) == {FENCER_ALICE, FENCER_CAROL}

    assert by_fencer[FENCER_ALICE]["points"] == 23
    assert by_fencer[FENCER_ALICE]["components"] == {
        "participation": 1,
        "medal": 12,
        "upset": 10,
    }
    assert by_fencer[FENCER_ALICE]["team_id"] == TEAM_A

    assert by_fencer[FENCER_CAROL]["points"] == 6
    assert by_fencer[FENCER_CAROL]["components"] == {
        "participation": 1,
        "medal": 5,
        "upset": 0,
    }
    assert by_fencer[FENCER_CAROL]["source_result"]["result_id"] == "result-carol-bronze"


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.rows = None
        self.on_conflict = None

    def upsert(self, rows, on_conflict):
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        self.client.upserts.append(
            {
                "table": self.name,
                "rows": self.rows,
                "on_conflict": self.on_conflict,
            }
        )
        return FakeResult(self.rows)


class FakeSupabase:
    def __init__(self):
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_weekly_scoring_is_deterministic_and_upserts_on_natural_score_key():
    from fantasy_league import compute_weekly_scores, upsert_weekly_scores

    rosters = [
        {"league_id": LEAGUE_ID, "team_id": TEAM_A, "fencer_id": FENCER_ALICE, "slot_type": "starter"},
    ]
    results = [
        {
            "id": "result-alice-gold",
            "tournament_id": "tournament-in-period",
            "fencer_id": FENCER_ALICE,
            "rank": 1,
            "medal": "Gold",
            "metadata": {"seed": 20, "source": "fie_results"},
        },
    ]
    tournaments = [{"id": "tournament-in-period", "start_date": "2026-06-03"}]

    first_rows, first_summary = compute_weekly_scores(
        base_league(),
        locked_period(),
        base_teams(),
        rosters,
        results,
        tournaments=tournaments,
        scored_at=NOW,
    )
    second_rows, second_summary = compute_weekly_scores(
        base_league(),
        locked_period(),
        base_teams(),
        rosters,
        results,
        tournaments=tournaments,
        scored_at=NOW,
    )

    assert first_rows == second_rows
    assert first_summary == second_summary
    assert UUID(first_rows[0]["id"]).version == 5
    assert first_rows[0]["result_key"] == f"tournament-in-period:{FENCER_ALICE}"

    client = FakeSupabase()
    assert upsert_weekly_scores(client, first_rows) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_fantasy_weekly_scores"
    assert upsert["on_conflict"] == "period_id,team_id,fencer_id,result_key"
    assert upsert["rows"] == first_rows


def test_compute_weekly_scores_rejects_open_periods_before_scoring():
    from fantasy_league import FantasyValidationError, compute_weekly_scores

    period = {**locked_period(), "status": "open", "locked_at": None}

    try:
        compute_weekly_scores(
            base_league(),
            period,
            base_teams(),
            [{"league_id": LEAGUE_ID, "team_id": TEAM_A, "fencer_id": FENCER_ALICE, "slot_type": "starter"}],
            [
                {
                    "tournament_id": "tournament-in-period",
                    "fencer_id": FENCER_ALICE,
                    "rank": 1,
                    "medal": "Gold",
                }
            ],
            tournaments=[{"id": "tournament-in-period", "start_date": "2026-06-03"}],
            scored_at=NOW,
        )
    except FantasyValidationError as exc:
        assert {issue["code"] for issue in exc.issues} == {"period_not_locked"}
    else:
        raise AssertionError("open periods must not be scored")

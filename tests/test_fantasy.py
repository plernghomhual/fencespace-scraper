import os
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FENCER_ALICE = "00000000-0000-0000-0000-000000000001"
FENCER_ALICE_EPEE = "00000000-0000-0000-0000-000000000011"
FENCER_BOB = "00000000-0000-0000-0000-000000000002"
FENCER_CAROL = "00000000-0000-0000-0000-000000000003"
NOW = "2026-06-01T12:00:00+00:00"


def zero_skips():
    return {
        "results_missing_required_fields": 0,
        "duplicate_results": 0,
        "bouts_missing_required_fields": 0,
        "bouts_missing_scores": 0,
        "bouts_byes": 0,
        "bouts_missing_ranks": 0,
        "bouts_non_upsets": 0,
        "bouts_status_skipped": 0,
        "bouts_duplicate": 0,
    }


def test_fantasy_rules_are_versioned_and_document_component_weights():
    from compute_fantasy_points import FANTASY_SCORING_RULES

    weights = cast(dict[str, Any], FANTASY_SCORING_RULES["documented_weights"])
    assert FANTASY_SCORING_RULES["rules_version"] == "2026.06.v1"
    assert weights["participation"] == 2
    assert weights["placement"]["1"] == 32
    assert weights["placement"]["9-16"] == 6
    assert weights["medal"]["gold"] == 20
    assert weights["upset"]["base"] == 8
    assert weights["penalties"]["dns"] == -5
    assert weights["penalties"]["dq"] == -10
    assert weights["team_event_multiplier"] == 0.5


def test_build_fantasy_rows_scores_medals_placements_participation_and_tiers():
    from compute_fantasy_points import build_fantasy_rows

    rows, skipped = build_fantasy_rows(
        results=[
            {
                "id": "r1",
                "tournament_id": "olympics-foil",
                "fencer_id": FENCER_ALICE,
                "rank": 1,
                "medal": "Gold",
            },
            {
                "id": "r2",
                "tournament_id": "world-cup-epee",
                "fencer_id": FENCER_BOB,
                "rank": 12,
            },
        ],
        bouts=[],
        tournaments=[
            {"id": "olympics-foil", "season": 2026, "type": "OG", "name": "Olympic Games"},
            {"id": "world-cup-epee", "season": "2026", "competition_type": "World Cup"},
        ],
        fencers=[],
        identity_rows=[],
        updated_at=NOW,
    )

    assert skipped == zero_skips()
    by_fencer = {row["fencer_id"]: row for row in rows}
    assert by_fencer[FENCER_ALICE]["components"] == {
        "participation": 4.0,
        "placement": 64.0,
        "medal": 40.0,
        "upsets": 0.0,
        "penalties": 0.0,
        "tier": "Olympics",
        "tier_multiplier": 2.0,
        "team_event_multiplier": 1.0,
        "placement_rank": 1,
        "medal_type": "gold",
        "status": None,
        "upset_count": 0,
    }
    assert by_fencer[FENCER_ALICE]["total_points"] == 108.0
    assert by_fencer[FENCER_ALICE]["rules_version"] == "2026.06.v1"
    assert by_fencer[FENCER_BOB]["components"]["placement"] == 7.5
    assert by_fencer[FENCER_BOB]["components"]["participation"] == 2.5
    assert by_fencer[FENCER_BOB]["total_points"] == 10.0


def test_build_fantasy_rows_deduplicates_results_per_fencer_event_and_uses_identity_map():
    from compute_fantasy_points import build_fantasy_rows

    rows, skipped = build_fantasy_rows(
        results=[
            {"id": "dupe-b", "tournament_id": "worlds-epee", "fencer_id": FENCER_ALICE_EPEE, "rank": 3, "medal": "Bronze"},
            {"id": "dupe-a", "tournament_id": "worlds-epee", "fencer_id": FENCER_ALICE, "rank": 3, "medal": "Bronze"},
        ],
        bouts=[],
        tournaments=[{"id": "worlds-epee", "season": 2026, "tier": "World Championships"}],
        fencers=[],
        identity_rows=[
            {"canonical_id": FENCER_ALICE, "fs_fencer_row_ids": [FENCER_ALICE, FENCER_ALICE_EPEE]}
        ],
        updated_at=NOW,
    )

    assert skipped["duplicate_results"] == 1
    assert len(rows) == 1
    assert rows[0]["fencer_id"] == FENCER_ALICE
    assert rows[0]["components"]["placement_rank"] == 3
    assert rows[0]["components"]["medal_type"] == "bronze"
    assert rows[0]["total_points"] == 57.75


def test_build_fantasy_rows_scores_upsets_from_bouts_and_skips_byes_and_missing_scores():
    from compute_fantasy_points import build_fantasy_rows

    rows, skipped = build_fantasy_rows(
        results=[
            {"id": "winner-result", "tournament_id": "world-cup", "fencer_id": FENCER_ALICE, "rank": 8},
            {"id": "loser-result", "tournament_id": "world-cup", "fencer_id": FENCER_BOB, "rank": 16},
        ],
        bouts=[
            {
                "id": "upset-1",
                "tournament_id": "world-cup",
                "fencer_a": FENCER_ALICE,
                "fencer_b": FENCER_BOB,
                "score_a": 15,
                "score_b": 12,
            },
            {
                "id": "upset-1",
                "tournament_id": "world-cup",
                "fencer_a": FENCER_BOB,
                "fencer_b": FENCER_ALICE,
                "score_a": 12,
                "score_b": 15,
            },
            {
                "id": "upset-1",
                "tournament_id": "world-cup",
                "fencer_a": FENCER_ALICE,
                "fencer_b": FENCER_BOB,
                "score_a": 15,
                "score_b": 12,
            },
            {
                "id": "bye-1",
                "tournament_id": "world-cup",
                "fencer_a_id": FENCER_ALICE,
                "fencer_b_id": FENCER_CAROL,
                "score_a": 0,
                "score_b": 0,
                "is_bye": True,
            },
            {
                "id": "missing-score",
                "tournament_id": "world-cup",
                "fencer_a": FENCER_ALICE,
                "fencer_b": FENCER_CAROL,
                "score_a": None,
                "score_b": 9,
            },
        ],
        tournaments=[{"id": "world-cup", "season": 2026, "competition_tier": "WC"}],
        fencers=[
            {"id": FENCER_ALICE, "world_rank": 50},
            {"id": FENCER_BOB, "world_rank": 5},
            {"id": FENCER_CAROL, "world_rank": 3},
        ],
        identity_rows=[],
        updated_at=NOW,
    )

    by_fencer = {row["fencer_id"]: row for row in rows}
    assert skipped["bouts_duplicate"] == 2
    assert skipped["bouts_byes"] == 1
    assert skipped["bouts_missing_scores"] == 1
    assert by_fencer[FENCER_ALICE]["components"]["upsets"] == 10.0
    assert by_fencer[FENCER_ALICE]["components"]["upset_count"] == 1
    assert by_fencer[FENCER_ALICE]["total_points"] == 22.5


def test_build_fantasy_rows_handles_team_events_dns_and_dq_penalties():
    from compute_fantasy_points import build_fantasy_rows

    rows, skipped = build_fantasy_rows(
        results=[
            {"id": "team-result", "tournament_id": "team-gp", "fencer_id": FENCER_ALICE, "rank": 2, "medal": "Silver"},
            {"id": "dns-result", "tournament_id": "team-gp", "fencer_id": FENCER_BOB, "rank": "DNS", "status": "DNS"},
            {"id": "dq-result", "tournament_id": "team-gp", "fencer_id": FENCER_CAROL, "rank": 1, "medal": "Gold", "status": "DQ"},
        ],
        bouts=[],
        tournaments=[{"id": "team-gp", "season": 2026, "type": "GP", "is_team": True}],
        fencers=[],
        identity_rows=[],
        updated_at=NOW,
    )

    assert skipped["results_missing_required_fields"] == 0
    by_fencer = {row["fencer_id"]: row for row in rows}
    assert by_fencer[FENCER_ALICE]["components"]["team_event_multiplier"] == 0.5
    assert by_fencer[FENCER_ALICE]["components"]["placement"] == 16.2
    assert by_fencer[FENCER_ALICE]["components"]["medal"] == 9.45
    assert by_fencer[FENCER_ALICE]["total_points"] == 27.0
    assert by_fencer[FENCER_BOB]["components"]["participation"] == 0.0
    assert by_fencer[FENCER_BOB]["components"]["penalties"] == -5.0
    assert by_fencer[FENCER_BOB]["total_points"] == -5.0
    assert by_fencer[FENCER_CAROL]["components"]["placement"] == 0.0
    assert by_fencer[FENCER_CAROL]["components"]["medal"] == 0.0
    assert by_fencer[FENCER_CAROL]["components"]["penalties"] == -10.0
    assert by_fencer[FENCER_CAROL]["total_points"] == -10.0


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.range_start = 0
        self.range_end = None
        self.rows = None
        self.on_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            rows = list(self.client.tables.get(self.name, []))
            end = self.range_end + 1 if self.range_end is not None else None
            return FakeResult(rows[self.range_start : end])
        if self.operation == "upsert":
            self.client.upserts.append({"table": self.name, "rows": self.rows, "on_conflict": self.on_conflict})
            return FakeResult(self.rows)
        raise AssertionError(f"Unhandled operation for {self.name}")


class FakeClient:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_fantasy_points_upserts_by_fencer_event_season_and_rules_version():
    from compute_fantasy_points import compute_fantasy_points

    client = FakeClient(
        {
            "fs_results": [{"id": "r1", "tournament_id": "event-1", "fencer_id": FENCER_ALICE, "rank": 1, "medal": "Gold"}],
            "fs_bouts": [],
            "fs_tournaments": [{"id": "event-1", "season": 2026, "type": "OG"}],
            "fs_fencers": [{"id": FENCER_ALICE, "world_rank": 1}],
            "fs_fencer_identities": [],
        }
    )

    summary = compute_fantasy_points(
        client=client,
        page_size=2,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary == {
        "results_read": 1,
        "bouts_read": 0,
        "tournaments_read": 1,
        "fencers_read": 1,
        "identity_rows": 0,
        "fantasy_rows": 1,
        "written": 1,
        "skipped": zero_skips(),
        "rules_version": "2026.06.v1",
    }
    assert client.upserts[0]["table"] == "fs_fantasy_points"
    assert client.upserts[0]["on_conflict"] == "fencer_id,tournament_id,season,rules_version"
    row = client.upserts[0]["rows"][0]
    assert row["season"] == 2026
    assert row["rules_version"] == "2026.06.v1"
    assert row["total_points"] == 108.0


def test_rules_version_change_recalculates_points_without_overwriting_old_version():
    from compute_fantasy_points import build_fantasy_rows

    results = [{"id": "r1", "tournament_id": "event-1", "fencer_id": FENCER_ALICE, "rank": 1, "medal": "Gold"}]
    tournaments = [{"id": "event-1", "season": 2026, "type": "OG"}]
    rules = {
        "rules_version": "2026.06.v2",
        "participation": 3,
        "placement": {"1": 40},
        "medal": {"gold": 25, "silver": 15, "bronze": 10},
        "upset": {"base": 8, "min_rank_gap": 10},
        "penalties": {"dns": -5, "dq": -10},
        "tier_multipliers": {"olympics": 2.0, "unknown": 1.0},
        "team_event_multiplier": 0.5,
    }

    old_rows, _ = build_fantasy_rows(results, [], tournaments, [], [], updated_at=NOW)
    new_rows, _ = build_fantasy_rows(results, [], tournaments, [], [], updated_at=NOW, rules=rules)

    assert old_rows[0]["rules_version"] == "2026.06.v1"
    assert new_rows[0]["rules_version"] == "2026.06.v2"
    assert old_rows[0]["total_points"] == 108.0
    assert new_rows[0]["total_points"] == 136.0


def test_fantasy_migration_defines_versioned_points_table_shape():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_fantasy.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fantasy_points" in normalized
    assert "fencer_id uuid not null references public.fs_fencers(id)" in normalized
    assert "tournament_id uuid not null references public.fs_tournaments(id)" in normalized
    assert "season integer not null" in normalized
    assert "components jsonb not null default '{}'::jsonb" in normalized
    assert "total_points numeric not null default 0" in normalized
    assert "rules_version text not null" in normalized
    assert "updated_at timestamptz not null default now()" in normalized
    assert "unique (fencer_id, tournament_id, season, rules_version)" in normalized
    assert "fs_fantasy_points_rules_version_idx" in normalized
    assert "participation=2" in normalized
    assert "gold=20" in normalized
    assert "dns=-5" in normalized
    assert "dq=-10" in normalized

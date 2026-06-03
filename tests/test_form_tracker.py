import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ALICE_ROW = "00000000-0000-0000-0000-000000000001"
ALICE_ALT_ROW = "00000000-0000-0000-0000-000000000002"
BOB_ROW = "00000000-0000-0000-0000-000000000003"
CAROL_ROW = "00000000-0000-0000-0000-000000000004"
ALICE_IDENTITY = "10000000-0000-0000-0000-000000000001"
NOW = "2026-06-02T12:00:00+00:00"


def _dated_tournaments(prefix, *, weapon="Foil", category="Senior"):
    return {
        f"{prefix}-{index}": {
            "id": f"{prefix}-{index}",
            "weapon": weapon,
            "category": category,
            "end_date": f"2025-0{index}-01",
            "status": "completed",
            "has_results": True,
        }
        for index in range(1, 6)
    }


def _rank_results(fencer_id, prefix, ranks):
    return [
        {
            "id": f"{prefix}-result-{index}",
            "tournament_id": f"{prefix}-{index}",
            "fencer_id": fencer_id,
            "rank": rank,
        }
        for index, rank in enumerate(ranks, start=1)
    ]


def _row_by_fencer(rows):
    return {row["fencer_id"]: row for row in rows}


def test_build_form_rows_scores_improving_declining_and_stable_form():
    from compute_form_tracker import build_form_rows

    tournaments = {}
    tournaments.update(_dated_tournaments("improving"))
    tournaments.update(_dated_tournaments("declining"))
    tournaments.update(_dated_tournaments("stable"))
    results = []
    results.extend(_rank_results(ALICE_ROW, "improving", [20, 16, 12, 8, 4]))
    results.extend(_rank_results(BOB_ROW, "declining", [4, 8, 12, 16, 20]))
    results.extend(_rank_results(CAROL_ROW, "stable", [10, 9, 10, 11, 10]))

    rows, summary = build_form_rows(results, tournaments, now=NOW)

    assert summary["results_used"] == 15
    by_fencer = _row_by_fencer(rows)

    improving = by_fencer[ALICE_ROW]
    assert improving["trend_direction"] == "improving"
    assert improving["form_score"] == pytest.approx(66.67, abs=0.01)
    assert improving["recent_avg_rank"] == pytest.approx(12.0)

    declining = by_fencer[BOB_ROW]
    assert declining["trend_direction"] == "declining"
    assert declining["form_score"] == pytest.approx(45.33, abs=0.01)

    stable = by_fencer[CAROL_ROW]
    assert stable["trend_direction"] == "stable"
    assert stable["form_score"] == pytest.approx(63.47, abs=0.01)

    assert improving["form_score"] > stable["form_score"] > declining["form_score"]
    assert improving["metadata"]["score_components"]["rank_score_step"] == 4
    assert improving["metadata"]["score_components"]["recency_weights"] == [1, 2, 3, 4, 5]


def test_build_form_rows_handles_fewer_than_five_null_ranks_mixed_categories_and_dedupes():
    from compute_form_tracker import build_form_rows

    tournaments = {
        "junior-a": {
            "id": "junior-a",
            "weapon": "Epee",
            "category": "Women's Junior",
            "end_date": "2025-01-01",
            "status": "completed",
            "has_results": True,
        },
        "senior-b": {
            "id": "senior-b",
            "weapon": "Epee",
            "category": "Women's Senior",
            "end_date": "2025-02-01",
            "status": "completed",
            "has_results": True,
        },
        "senior-c": {
            "id": "senior-c",
            "weapon": "Epee",
            "category": "Women's Senior",
            "end_date": "2025-03-01",
            "status": "completed",
            "has_results": True,
        },
        "team-d": {
            "id": "team-d",
            "weapon": "Epee",
            "category": "Women's Senior Team",
            "end_date": "2025-04-01",
            "status": "completed",
            "has_results": True,
            "team": True,
        },
    }
    identity_rows = [
        {
            "id": ALICE_IDENTITY,
            "canonical_id": ALICE_ROW,
            "fs_fencer_row_ids": [ALICE_ROW, ALICE_ALT_ROW],
        }
    ]
    results = [
        {
            "id": "junior-result",
            "tournament_id": "junior-a",
            "fencer_id": ALICE_ROW,
            "rank": 3,
            "medal": "Bronze",
        },
        {
            "id": "missing-rank-result",
            "tournament_id": "senior-b",
            "fencer_id": ALICE_ALT_ROW,
            "rank": None,
        },
        {
            "id": "duplicate-worse-result",
            "tournament_id": "senior-c",
            "fencer_id": ALICE_ROW,
            "rank": 8,
        },
        {
            "id": "duplicate-better-result",
            "tournament_id": "senior-c",
            "fencer_id": ALICE_ALT_ROW,
            "rank": 6,
        },
        {
            "id": "team-result",
            "tournament_id": "team-d",
            "fencer_id": ALICE_ROW,
            "rank": 1,
        },
    ]

    rows, summary = build_form_rows(results, tournaments, identity_rows=identity_rows, now=NOW)

    assert summary["results_used"] == 3
    assert summary["skipped_duplicate_results"] == 1
    assert summary["skipped_team_results"] == 1
    assert len(rows) == 1

    row = rows[0]
    assert row["fencer_id"] == ALICE_ROW
    assert row["weapon"] == "Epee"
    assert row["trend_direction"] == "declining"
    assert row["last_competitions"] == [
        {
            "tournament_id": "junior-a",
            "date": "2025-01-01",
            "rank": 3,
            "category": "Women's Junior",
            "medal": "bronze",
        },
        {
            "tournament_id": "senior-b",
            "date": "2025-02-01",
            "rank": None,
            "category": "Women's Senior",
            "medal": None,
        },
        {
            "tournament_id": "senior-c",
            "date": "2025-03-01",
            "rank": 6,
            "category": "Women's Senior",
            "medal": None,
        },
    ]
    assert row["form_score"] == pytest.approx(83.75, abs=0.01)
    assert row["recent_medals"] == 1
    assert row["recent_avg_rank"] == pytest.approx(4.5)
    assert row["metadata"]["identity_id"] == ALICE_IDENTITY
    assert row["metadata"]["identity_grouping"] == "fs_fencer_identities"
    assert row["metadata"]["missing_rank_competitions"] == 1
    assert row["metadata"]["ranked_competitions"] == 2
    assert row["metadata"]["category_counts"] == {"Women's Junior": 1, "Women's Senior": 2}


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
            if self.name not in self.client.tables:
                raise RuntimeError(f"missing table {self.name}")
            return FakeResult(self.client.tables[self.name][self.range_start : self.range_end + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult(self.rows)
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_form_tracker_upserts_idempotently_with_conflict_key():
    from compute_form_tracker import compute_form_tracker

    client = FakeSupabase(
        {
            "fs_results": [
                {
                    "id": "r1",
                    "tournament_id": "a",
                    "fencer_id": ALICE_ROW,
                    "rank": 5,
                    "weapon": "Foil",
                },
                {
                    "id": "r2",
                    "tournament_id": "b",
                    "fencer_id": ALICE_ALT_ROW,
                    "rank": 2,
                    "weapon": "Foil",
                    "medal": "Silver",
                },
            ],
            "fs_tournaments": [
                {
                    "id": "a",
                    "weapon": "Foil",
                    "category": "Senior",
                    "end_date": "2025-01-01",
                    "status": "completed",
                    "has_results": True,
                },
                {
                    "id": "b",
                    "weapon": "Foil",
                    "category": "Senior",
                    "end_date": "2025-02-01",
                    "status": "completed",
                    "has_results": True,
                },
            ],
            "fs_fencer_identities": [
                {
                    "id": ALICE_IDENTITY,
                    "canonical_id": ALICE_ROW,
                    "fs_fencer_row_ids": [ALICE_ROW, ALICE_ALT_ROW],
                }
            ],
        }
    )

    first = compute_form_tracker(
        client=client,
        page_size=2,
        now=NOW,
        log_run=False,
        update_state=False,
    )
    second = compute_form_tracker(
        client=client,
        page_size=2,
        now=NOW,
        log_run=False,
        update_state=False,
    )

    assert first == second == {
        "results_read": 2,
        "tournaments_read": 2,
        "identity_rows": 1,
        "form_rows": 1,
        "written": 1,
        "skipped": 0,
        "skipped_missing_fencer": 0,
        "skipped_missing_weapon": 0,
        "skipped_team_results": 0,
        "skipped_incomplete_events": 0,
        "skipped_duplicate_results": 0,
        "results_used": 2,
    }
    assert len(client.upserts) == 2
    assert client.upserts[0] == client.upserts[1]
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_fencer_form"
    assert upsert["on_conflict"] == "fencer_id,weapon"
    assert upsert["rows"][0]["fencer_id"] == ALICE_ROW
    assert upsert["rows"][0]["metadata"]["source_result_ids"] == ["r1", "r2"]


def test_form_tracker_migration_defines_table_shape_and_indexes():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_form_tracker.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencer_form" in normalized
    assert "fencer_id uuid not null references public.fs_fencers(id)" in normalized
    assert "weapon text not null" in normalized
    assert "last_competitions jsonb not null default '[]'" in normalized
    assert "form_score numeric(6,2) not null default 0" in normalized
    assert "trend_direction text not null" in normalized
    assert "recent_medals integer not null default 0" in normalized
    assert "recent_avg_rank numeric(8,2)" in normalized
    assert "metadata jsonb not null default '{}'" in normalized
    assert "updated_at timestamptz not null default now()" in normalized
    assert "unique (fencer_id, weapon)" in normalized
    assert "check (trend_direction in ('improving', 'declining', 'stable'))" in normalized
    assert "fs_fencer_form_weapon_score_idx" in normalized
    assert "fs_fencer_form_trend_idx" in normalized
    assert "fs_fencer_form_updated_idx" in normalized
    assert "alter table public.fs_fencer_form enable row level security" in normalized

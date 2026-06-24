import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ALICE = "00000000-0000-0000-0000-000000000001"
BOB = "00000000-0000-0000-0000-000000000002"
CAROL = "00000000-0000-0000-0000-000000000003"
NOW = "2026-06-01T12:00:00+00:00"


def test_build_performance_rows_computes_deltas_and_splits_mixed_weapons():
    from compute_performance_analysis import build_performance_rows

    results: list[dict[str, Any]] = [
        {"id": "r1", "tournament_id": "foil-1", "fencer_id": ALICE, "rank": 5},
        {"id": "r2", "tournament_id": "foil-2", "fencer_id": ALICE, "rank": 15},
        {"id": "r3", "tournament_id": "epee-1", "fencer_id": ALICE, "rank": 4},
        {"id": "null-rank", "tournament_id": "foil-1", "fencer_id": ALICE, "rank": None},
        {"id": "missing-fencer", "tournament_id": "foil-1", "fencer_id": None, "rank": 1},
        {"id": "unranked-fencer", "tournament_id": "foil-1", "fencer_id": CAROL, "rank": 2},
        {"id": "bob", "tournament_id": "foil-1", "fencer_id": BOB, "rank": "T6."},
    ]
    fencers: list[dict[str, Any]] = [
        {"id": ALICE, "world_rank": 10, "weapon": "Foil"},
        {"id": BOB, "world_rank": "3", "weapon": "Foil"},
        {"id": CAROL, "world_rank": None, "weapon": "Foil"},
    ]
    tournaments: list[dict[str, Any]] = [
        {"id": "foil-1", "weapon": "foil"},
        {"id": "foil-2", "weapon": "Foil"},
        {"id": "epee-1", "weapon": "Epee"},
    ]

    rows, skipped = build_performance_rows(results, fencers, tournaments, updated_at=NOW)
    by_key = {(row["fencer_id"], row["weapon"]): row for row in rows}

    assert skipped == 3
    assert by_key[(ALICE, "Foil")] == {
        "fencer_id": ALICE,
        "weapon": "Foil",
        "competitions_count": 2,
        "avg_delta": 0.0,
        "stddev_delta": 5.0,
        "overperformance_rate": 50.0,
        "clutch_score": 0.0,
        "updated_at": NOW,
    }
    assert by_key[(ALICE, "Epee")]["competitions_count"] == 1
    assert by_key[(ALICE, "Epee")]["avg_delta"] == 6.0
    assert by_key[(ALICE, "Epee")]["stddev_delta"] == 0.0
    assert by_key[(ALICE, "Epee")]["overperformance_rate"] == 100.0
    assert by_key[(BOB, "Foil")]["avg_delta"] == -3.0
    assert by_key[(BOB, "Foil")]["overperformance_rate"] == 0.0


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = None
        self.columns = None
        self.start = 0
        self.end = None
        self.limit_count = None
        self.pending_rows = None
        self.pending_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.pending_rows = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.table_name,
                    "rows": self.pending_rows,
                    "on_conflict": self.pending_conflict,
                }
            )
            return FakeResult(self.pending_rows)

        if self.table_name == "fs_fencer_career_stats" and "clutch_score" in str(self.columns):
            if not self.client.career_clutch_score_column:
                raise RuntimeError("column fs_fencer_career_stats.clutch_score does not exist")
            return FakeResult([])

        rows = list(self.client.tables.get(self.table_name, []))
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        else:
            end = self.end + 1 if self.end is not None else None
            rows = rows[self.start : end]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self, *, career_clutch_score_column=True):
        self.tables = {
            "fs_results": [
                {"tournament_id": "foil-1", "fencer_id": ALICE, "rank": 5},
                {"tournament_id": "foil-2", "fencer_id": ALICE, "rank": 15},
                {"tournament_id": "foil-1", "fencer_id": BOB, "rank": 6},
            ],
            "fs_fencers": [
                {"id": ALICE, "world_rank": 10, "weapon": "Foil"},
                {"id": BOB, "world_rank": 3, "weapon": "Foil"},
            ],
            "fs_tournaments": [
                {"id": "foil-1", "weapon": "Foil"},
                {"id": "foil-2", "weapon": "Foil"},
            ],
        }
        self.career_clutch_score_column = career_clutch_score_column
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_compute_performance_analysis_upserts_metrics_and_mirrors_clutch_score():
    from compute_performance_analysis import compute_performance_analysis

    client = FakeSupabase(career_clutch_score_column=True)

    summary = compute_performance_analysis(
        client=client,
        page_size=2,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary == {
        "results_read": 3,
        "fencers_read": 2,
        "tournaments_read": 2,
        "performance_rows": 2,
        "written": 2,
        "career_mirrored": 2,
        "skipped": 0,
    }
    performance_upsert = client.upserts[0]
    assert performance_upsert["table"] == "fs_fencer_performance_analysis"
    assert performance_upsert["on_conflict"] == "fencer_id,weapon"
    assert len(performance_upsert["rows"]) == 2
    career_upsert = client.upserts[1]
    assert career_upsert["table"] == "fs_fencer_career_stats"
    assert career_upsert["on_conflict"] == "fencer_id"
    assert career_upsert["rows"] == [
        {"fencer_id": ALICE, "clutch_score": 0.0},
        {"fencer_id": BOB, "clutch_score": -3.0},
    ]


def test_compute_performance_analysis_skips_career_mirror_when_column_is_absent():
    from compute_performance_analysis import compute_performance_analysis

    client = FakeSupabase(career_clutch_score_column=False)

    summary = compute_performance_analysis(
        client=client,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary["written"] == 2
    assert summary["career_mirrored"] == 0
    assert [upsert["table"] for upsert in client.upserts] == [
        "fs_fencer_performance_analysis"
    ]


def test_performance_analysis_migration_defines_table_and_unique_key():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260601_performance_analysis.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencer_performance_analysis" in normalized
    assert "unique (fencer_id, weapon)" in normalized
    assert "references public.fs_fencers(id)" in normalized
    assert "avg_delta" in normalized
    assert "stddev_delta" in normalized
    assert "overperformance_rate" in normalized
    assert "clutch_score" in normalized

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-01T12:00:00+00:00"


def test_build_strength_rows_scores_ranked_participants_once_per_tournament():
    from compute_strength_of_field import build_strength_rows

    results = [
        {"tournament_id": "tournament-a", "fencer_id": "fencer-1"},
        {"tournament_id": "tournament-a", "fencer_id": "fencer-2"},
        {"tournament_id": "tournament-a", "fencer_id": "fencer-2"},
        {"tournament_id": "tournament-a", "fencer_id": "fencer-3"},
        {"tournament_id": "tournament-a", "fencer_id": "fencer-4"},
        {"tournament_id": "tournament-a", "fencer_id": None},
        {"tournament_id": "tournament-a", "fencer_id": "unranked"},
        {"tournament_id": "tournament-a", "fencer_id": "zero-rank"},
        {"tournament_id": "tournament-b", "fencer_id": "unranked"},
    ]
    fencers = [
        {"id": "fencer-1", "world_rank": 1},
        {"id": "fencer-2", "world_rank": "8"},
        {"id": "fencer-3", "world_rank": 16},
        {"id": "fencer-4", "world_rank": 120},
        {"id": "unranked", "world_rank": None},
        {"id": "zero-rank", "world_rank": 0},
    ]

    rows, skipped = build_strength_rows(results, fencers, updated_at=NOW)

    assert skipped == 4
    by_tournament = {row["tournament_id"]: row for row in rows}
    assert by_tournament["tournament-a"] == {
        "tournament_id": "tournament-a",
        "avg_world_rank": 36.25,
        "top8_count": 2,
        "top16_count": 3,
        "total_fie_ranked": 4,
        "strength_score": 64.75,
        "updated_at": NOW,
    }
    assert by_tournament["tournament-b"] == {
        "tournament_id": "tournament-b",
        "avg_world_rank": None,
        "top8_count": 0,
        "top16_count": 0,
        "total_fie_ranked": 0,
        "strength_score": None,
        "updated_at": NOW,
    }


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.columns = None
        self.range_start = 0
        self.range_end = None
        self.rows = None
        self.on_conflict = None

    def select(self, columns):
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def upsert(self, rows, on_conflict):
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.rows is not None:
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult([])

        rows = self.client.tables[self.name]
        end = self.range_end + 1 if self.range_end is not None else None
        return FakeResult(rows[self.range_start:end])


class FakeClient:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_strength_of_field_fetches_pages_and_upserts_per_tournament():
    from compute_strength_of_field import compute_strength_of_field

    client = FakeClient(
        {
            "fs_results": [
                {"tournament_id": "tournament-a", "fencer_id": "fencer-1"},
                {"tournament_id": "tournament-a", "fencer_id": "fencer-2"},
                {"tournament_id": "tournament-b", "fencer_id": "fencer-3"},
            ],
            "fs_fencers": [
                {"id": "fencer-1", "world_rank": 2},
                {"id": "fencer-2", "world_rank": 10},
                {"id": "fencer-3", "world_rank": None},
            ],
        }
    )

    summary = compute_strength_of_field(
        client=client,
        page_size=2,
        log_run=False,
        update_state=False,
        now=NOW,
    )

    assert summary == {
        "results_read": 3,
        "fencers_read": 3,
        "tournaments_scored": 2,
        "written": 2,
        "skipped": 1,
    }
    assert client.selects == [
        ("fs_results", "tournament_id,fencer_id"),
        ("fs_results", "tournament_id,fencer_id"),
        ("fs_fencers", "id,world_rank"),
        ("fs_fencers", "id,world_rank"),
    ]
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_competition_strength"
    assert upsert["on_conflict"] == "tournament_id"
    upserted = {row["tournament_id"]: row for row in upsert["rows"]}
    assert upserted["tournament-a"]["avg_world_rank"] == 6.0
    assert upserted["tournament-a"]["top8_count"] == 1
    assert upserted["tournament-a"]["top16_count"] == 2
    assert upserted["tournament-a"]["total_fie_ranked"] == 2
    assert upserted["tournament-a"]["strength_score"] == 95.0
    assert upserted["tournament-b"]["total_fie_ranked"] == 0
    assert upserted["tournament-b"]["strength_score"] is None


def test_strength_of_field_migration_defines_table_and_conflict_key():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260601_strength_of_field.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_competition_strength" in normalized
    assert "tournament_id uuid primary key" in normalized
    assert "references public.fs_tournaments(id)" in normalized
    assert "avg_world_rank numeric" in normalized
    assert "top8_count integer not null default 0" in normalized
    assert "top16_count integer not null default 0" in normalized
    assert "total_fie_ranked integer not null default 0" in normalized
    assert "strength_score numeric" in normalized

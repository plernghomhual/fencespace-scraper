from typing import Any
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


LOW_FENCER = "00000000-0000-0000-0000-000000000001"
HIGH_FENCER = "00000000-0000-0000-0000-000000000002"
OTHER_FENCER = "00000000-0000-0000-0000-000000000003"
NOW = "2026-06-01T12:00:00+00:00"


def test_build_head_to_head_rows_canonicalizes_pairs_and_skips_incomplete_bouts():
    from compute_head_to_head import build_head_to_head_rows

    tournaments: dict[str, dict[str, Any]] = {
        "foil-1": {"id": "foil-1", "weapon": "foil", "end_date": "2025-01-10"},
        "foil-2": {"id": "foil-2", "weapon": "Foil", "end_date": "2025-03-20T18:30:00+00:00"},
        "epee-1": {"id": "epee-1", "weapon": "epee", "end_date": "2025-02-05"},
        "missing-weapon": {"id": "missing-weapon", "end_date": "2025-04-01"},
    }
    bouts: list[dict[str, Any]] = [
        {
            "id": "bout-1",
            "tournament_id": "foil-1",
            "fencer_a_id": LOW_FENCER,
            "fencer_b_id": HIGH_FENCER,
            "score_a": 15,
            "score_b": 10,
        },
        {
            "id": "bout-2",
            "tournament_id": "foil-2",
            "fencer_a_id": HIGH_FENCER,
            "fencer_b_id": LOW_FENCER,
            "score_a": "15",
            "score_b": "14",
        },
        {
            "id": "bout-3",
            "tournament_id": "epee-1",
            "fencer_a_id": LOW_FENCER,
            "fencer_b_id": HIGH_FENCER,
            "score_a": 12,
            "score_b": 15,
        },
        {
            "id": "null-score",
            "tournament_id": "foil-1",
            "fencer_a_id": LOW_FENCER,
            "fencer_b_id": HIGH_FENCER,
            "score_a": None,
            "score_b": 15,
        },
        {
            "id": "null-fencer",
            "tournament_id": "foil-1",
            "fencer_a_id": LOW_FENCER,
            "fencer_b_id": None,
            "score_a": 15,
            "score_b": 9,
        },
        {
            "id": "self-bout",
            "tournament_id": "foil-1",
            "fencer_a_id": LOW_FENCER,
            "fencer_b_id": LOW_FENCER,
            "score_a": 15,
            "score_b": 9,
        },
        {
            "id": "missing-weapon",
            "tournament_id": "missing-weapon",
            "fencer_a_id": LOW_FENCER,
            "fencer_b_id": OTHER_FENCER,
            "score_a": 15,
            "score_b": 9,
        },
    ]

    rows, skipped = build_head_to_head_rows(bouts, tournaments, now=NOW)

    assert skipped == 4
    by_weapon = {row["weapon"]: row for row in rows if row["fencer_b_id"] == HIGH_FENCER}

    assert by_weapon["Foil"] == {
        "fencer_a_id": LOW_FENCER,
        "fencer_b_id": HIGH_FENCER,
        "weapon": "Foil",
        "a_wins": 1,
        "b_wins": 1,
        "a_touches": 29,
        "b_touches": 25,
        "bouts_total": 2,
        "last_meeting_date": "2025-03-20",
        "last_winner_id": HIGH_FENCER,
        "updated_at": NOW,
    }
    assert by_weapon["Epee"]["a_wins"] == 0
    assert by_weapon["Epee"]["b_wins"] == 1
    assert by_weapon["Epee"]["a_touches"] == 12
    assert by_weapon["Epee"]["b_touches"] == 15
    assert by_weapon["Epee"]["last_meeting_date"] == "2025-02-05"
    assert by_weapon["Epee"]["last_winner_id"] == HIGH_FENCER


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.start = 0
        self.end = None
        self.not_null_columns = []
        self.pending_upsert = None
        self.pending_conflict = None

    def select(self, _columns):
        return self

    @property
    def not_(self):
        return self

    def is_(self, column, value):
        assert value == "null"
        self.not_null_columns.append(column)
        self.client.not_null_filters.append((self.table_name, column))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, rows, on_conflict):
        self.pending_upsert = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.pending_upsert is not None:
            self.client.upserts.append(
                (self.table_name, self.pending_upsert, self.pending_conflict)
            )
            return FakeResponse(self.pending_upsert)

        rows = list(self.client.tables[self.table_name])
        for column in self.not_null_columns:
            rows = [row for row in rows if row.get(column) is not None]
        end = self.end + 1 if self.end is not None else None
        return FakeResponse(rows[self.start:end])


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "fs_bouts": [
                {
                    "id": "bout-1",
                    "tournament_id": "foil-1",
                    "fencer_a_id": LOW_FENCER,
                    "fencer_b_id": HIGH_FENCER,
                    "score_a": 15,
                    "score_b": 10,
                },
                {
                    "id": "incomplete",
                    "tournament_id": "foil-1",
                    "fencer_a_id": LOW_FENCER,
                    "fencer_b_id": HIGH_FENCER,
                    "score_a": None,
                    "score_b": 10,
                },
                {
                    "id": "filtered",
                    "tournament_id": "foil-1",
                    "fencer_a_id": LOW_FENCER,
                    "fencer_b_id": None,
                    "score_a": 15,
                    "score_b": 10,
                },
            ],
            "fs_tournaments": [
                {"id": "foil-1", "weapon": "foil", "end_date": "2025-01-10"}
            ],
        }
        self.not_null_filters = []
        self.upserts = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_compute_head_to_head_queries_non_null_bouts_and_upserts_rows():
    from compute_head_to_head import compute_head_to_head

    fake = FakeSupabase()

    summary = compute_head_to_head(fake, now=NOW)

    assert ("fs_bouts", "fencer_a_id") in fake.not_null_filters
    assert ("fs_bouts", "fencer_b_id") in fake.not_null_filters
    assert summary == {"bouts_loaded": 2, "rows_written": 1, "skipped": 1}
    assert len(fake.upserts) == 1
    table_name, rows, conflict = fake.upserts[0]
    assert table_name == "fs_head_to_head"
    assert conflict == "fencer_a_id,fencer_b_id,weapon"
    assert rows[0]["fencer_a_id"] == LOW_FENCER
    assert rows[0]["fencer_b_id"] == HIGH_FENCER
    assert rows[0]["weapon"] == "Foil"


def test_head_to_head_migration_defines_table_and_conflict_key():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260601_head_to_head.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_head_to_head" in normalized
    assert "unique (fencer_a_id, fencer_b_id, weapon)" in normalized
    assert "references public.fs_fencers(id)" in normalized

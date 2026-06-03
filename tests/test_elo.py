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
BOB_IDENTITY = "10000000-0000-0000-0000-000000000002"
NOW = "2026-06-02T12:00:00+00:00"


def by_fencer(rows):
    return {row["fencer_id"]: row for row in rows}


def test_build_elo_rows_orders_bouts_chronologically_and_groups_identities():
    from compute_elo import KFactorConfig, build_elo_rows

    tournaments = {
        "early": {
            "id": "early",
            "weapon": "foil",
            "category": "Senior",
            "end_date": "2025-01-01",
            "status": "completed",
            "has_results": True,
        },
        "late": {
            "id": "late",
            "weapon": "Foil",
            "category": "Senior",
            "end_date": "2025-02-01",
            "status": "completed",
            "has_results": True,
        },
    }
    identity_rows = [
        {
            "id": ALICE_IDENTITY,
            "canonical_id": ALICE_ROW,
            "fs_fencer_row_ids": [ALICE_ROW, ALICE_ALT_ROW],
        },
        {"id": BOB_IDENTITY, "canonical_id": BOB_ROW, "fs_fencer_row_ids": [BOB_ROW]},
    ]
    bouts = [
        {
            "id": "late-bout",
            "tournament_id": "late",
            "fencer_a": BOB_ROW,
            "fencer_b": ALICE_ALT_ROW,
            "score_a": 15,
            "score_b": 14,
        },
        {
            "id": "early-bout",
            "tournament_id": "early",
            "fencer_a": ALICE_ROW,
            "fencer_b": BOB_ROW,
            "score_a": 15,
            "score_b": 10,
        },
    ]

    rows, summary = build_elo_rows(
        bouts,
        tournaments,
        identity_rows=identity_rows,
        k_config=KFactorConfig(default=32),
        now=NOW,
    )

    ratings = by_fencer(rows)
    assert summary["bouts_used"] == 2
    assert summary["skipped"] == 0
    assert set(ratings) == {ALICE_ROW, BOB_ROW}
    assert ratings[ALICE_ROW]["identity_id"] == ALICE_IDENTITY
    assert ratings[ALICE_ROW]["weapon"] == "Foil"
    assert ratings[ALICE_ROW]["category"] == "Senior"
    assert ratings[ALICE_ROW]["games"] == 2
    assert ratings[ALICE_ROW]["rating"] == pytest.approx(1498.53, abs=0.01)
    assert ratings[ALICE_ROW]["peak_rating"] == pytest.approx(1516.0, abs=0.01)
    assert ratings[ALICE_ROW]["last_bout_at"] == "2025-02-01"
    assert ratings[ALICE_ROW]["version"] == 1
    assert ratings[ALICE_ROW]["updated_at"] == NOW
    assert ratings[BOB_ROW]["games"] == 2
    assert ratings[BOB_ROW]["rating"] == pytest.approx(1501.47, abs=0.01)
    assert ratings[BOB_ROW]["peak_rating"] == pytest.approx(1501.47, abs=0.01)


def test_build_elo_rows_skips_duplicates_incomplete_missing_fencers_and_team_events():
    from compute_elo import KFactorConfig, build_elo_rows

    tournaments = {
        "valid": {
            "id": "valid",
            "weapon": "Epee",
            "category": "Junior",
            "end_date": "2025-04-01",
            "status": "completed",
            "has_results": True,
        },
        "team": {
            "id": "team",
            "weapon": "Epee",
            "category": "Junior",
            "end_date": "2025-04-02",
            "status": "completed",
            "has_results": True,
            "team": True,
        },
        "pending": {
            "id": "pending",
            "weapon": "Epee",
            "category": "Junior",
            "end_date": "2025-04-03",
            "status": "scheduled",
            "has_results": False,
        },
    }
    bouts = [
        {
            "id": "bout-1",
            "tournament_id": "valid",
            "fencer_a": ALICE_ROW,
            "fencer_b": BOB_ROW,
            "score_a": 15,
            "score_b": 12,
        },
        {
            "id": "bout-1",
            "tournament_id": "valid",
            "fencer_a": ALICE_ROW,
            "fencer_b": BOB_ROW,
            "score_a": 15,
            "score_b": 12,
        },
        {
            "id": "null-score",
            "tournament_id": "valid",
            "fencer_a": ALICE_ROW,
            "fencer_b": BOB_ROW,
            "score_a": None,
            "score_b": 12,
        },
        {
            "id": "missing-fencer",
            "tournament_id": "valid",
            "fencer_a": ALICE_ROW,
            "fencer_b": None,
            "score_a": 15,
            "score_b": 12,
        },
        {
            "id": "team-event",
            "tournament_id": "team",
            "fencer_a": ALICE_ROW,
            "fencer_b": CAROL_ROW,
            "score_a": 15,
            "score_b": 13,
        },
        {
            "id": "pending-event",
            "tournament_id": "pending",
            "fencer_a": ALICE_ROW,
            "fencer_b": CAROL_ROW,
            "score_a": 15,
            "score_b": 13,
        },
    ]

    rows, summary = build_elo_rows(
        bouts,
        tournaments,
        k_config=KFactorConfig(default=32, by_tier={}, by_category={}),
        now=NOW,
    )

    assert summary["bouts_read"] == 6
    assert summary["bouts_used"] == 1
    assert summary["skipped_duplicate_bouts"] == 1
    assert summary["skipped_null_scores"] == 1
    assert summary["skipped_missing_fencers"] == 1
    assert summary["skipped_team_events"] == 1
    assert summary["skipped_incomplete_events"] == 1
    assert summary["skipped"] == 5
    assert len(rows) == 2
    ratings = by_fencer(rows)
    assert ratings[ALICE_ROW]["rating"] == pytest.approx(1516.0, abs=0.01)
    assert ratings[BOB_ROW]["rating"] == pytest.approx(1484.0, abs=0.01)


def test_build_elo_rows_handles_empty_input():
    from compute_elo import build_elo_rows

    rows, summary = build_elo_rows([], {}, now=NOW)

    assert rows == []
    assert summary["bouts_read"] == 0
    assert summary["bouts_used"] == 0
    assert summary["rows_computed"] == 0
    assert summary["skipped"] == 0


def test_k_factor_uses_tier_then_category_then_default():
    from compute_elo import KFactorConfig, k_factor_for

    config = KFactorConfig(
        default=32,
        by_tier={"world_cup": 40},
        by_category={"Veteran": 20},
    )

    assert k_factor_for({"level": "World Cup", "category": "Veteran"}, {}, config) == 40
    assert k_factor_for({"category": "Veteran"}, {}, config) == 20
    assert k_factor_for({"category": "Senior"}, {}, config) == 32


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.range_start = 0
        self.range_end = 999
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


def fake_tables():
    return {
        "fs_bouts": [
            {
                "id": "bout-1",
                "tournament_id": "foil-1",
                "fencer_a": ALICE_ROW,
                "fencer_b": BOB_ROW,
                "score_a": 15,
                "score_b": 10,
            }
        ],
        "fs_tournaments": [
            {
                "id": "foil-1",
                "weapon": "Foil",
                "category": "Senior",
                "end_date": "2025-01-10",
                "status": "completed",
                "has_results": True,
            }
        ],
        "fs_fencer_identities": [
            {
                "id": ALICE_IDENTITY,
                "canonical_id": ALICE_ROW,
                "fs_fencer_row_ids": [ALICE_ROW, ALICE_ALT_ROW],
            }
        ],
    }


def test_compute_elo_dry_run_reads_without_upserting():
    from compute_elo import compute_elo

    client = FakeSupabase(fake_tables())

    summary = compute_elo(
        client=client,
        dry_run=True,
        now=NOW,
        log_run=False,
        update_state=False,
    )

    assert summary["dry_run"] is True
    assert summary["bouts_read"] == 1
    assert summary["rows_computed"] == 2
    assert summary["rows_written"] == 0
    assert client.upserts == []
    assert any(table == "fs_bouts" for table, _columns in client.selects)


def test_compute_elo_upserts_idempotently_with_conflict_key():
    from compute_elo import compute_elo

    client = FakeSupabase(fake_tables())

    summary = compute_elo(
        client=client,
        dry_run=False,
        now=NOW,
        log_run=False,
        update_state=False,
    )

    assert summary["dry_run"] is False
    assert summary["rows_written"] == 2
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_fencer_elo"
    assert upsert["on_conflict"] == "fencer_id,weapon,category,version"
    assert {row["fencer_id"] for row in upsert["rows"]} == {ALICE_ROW, BOB_ROW}


def test_elo_migration_defines_table_shape_and_indexes():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_elo.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencer_elo" in normalized
    assert "fencer_id uuid not null references public.fs_fencers(id)" in normalized
    assert "identity_id uuid references public.fs_fencer_identities(id)" in normalized
    assert "weapon text not null" in normalized
    assert "category text not null" in normalized
    assert "rating numeric(8,2) not null" in normalized
    assert "games integer not null default 0" in normalized
    assert "peak_rating numeric(8,2) not null" in normalized
    assert "last_bout_at date" in normalized
    assert "version integer not null default 1" in normalized
    assert "updated_at timestamptz not null default now()" in normalized
    assert "unique (fencer_id, weapon, category, version)" in normalized
    assert "fs_fencer_elo_identity_idx" in normalized
    assert "fs_fencer_elo_weapon_category_idx" in normalized
    assert "fs_fencer_elo_rating_idx" in normalized
    assert "alter table public.fs_fencer_elo enable row level security" in normalized

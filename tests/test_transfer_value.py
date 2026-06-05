from typing import Any
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ALICE = "00000000-0000-0000-0000-000000000001"
BOB = "00000000-0000-0000-0000-000000000002"
CAROL = "00000000-0000-0000-0000-000000000003"
NOW = "2026-06-01T12:00:00+00:00"


def test_build_transfer_value_rows_scores_public_signals_with_transparent_components():
    from compute_transfer_value import build_transfer_value_rows

    fencers = [
        {
            "id": ALICE,
            "fie_id": "1001",
            "world_rank": 9,
            "weapon": "Epee",
            "category": "Senior",
            "gender": "Women",
            "date_of_birth": "2002-06-15",
        }
    ]
    ranking_history = [
        {
            "fie_fencer_id": "1001",
            "weapon": "Epee",
            "category": "Women's Senior",
            "season": 2025,
            "rank": 12,
            "points": 130.0,
        },
        {
            "fie_fencer_id": "1001",
            "weapon": "Epee",
            "category": "Women's Senior",
            "season": 2026,
            "rank": 7,
            "points": 180.0,
        },
    ]
    tournaments = [
        {"id": "t1", "season": 2026, "weapon": "Epee", "gender": "Women", "category": "Senior"},
        {"id": "t2", "season": 2026, "weapon": "Epee", "gender": "Women", "category": "Senior"},
        {"id": "t3", "season": 2026, "weapon": "Epee", "gender": "Women", "category": "Senior"},
        {"id": "old", "season": 2025, "weapon": "Epee", "gender": "Women", "category": "Senior"},
    ]
    results: list[dict[str, Any]] = [
        {"tournament_id": "t1", "fencer_id": ALICE, "rank": 1},
        {"tournament_id": "t2", "fencer_id": ALICE, "rank": 8},
        {"tournament_id": "t3", "fencer_id": ALICE, "rank": 17},
        {"tournament_id": "old", "fencer_id": ALICE, "rank": 2},
        {"tournament_id": "t1", "fencer_id": None, "rank": 3},
    ]

    rows, skipped = build_transfer_value_rows(
        fencers,
        ranking_history,
        results,
        tournaments,
        season=2026,
        updated_at=NOW,
    )

    assert skipped == 0
    assert len(rows) == 1
    row = rows[0]
    assert row["fencer_id"] == ALICE
    assert row["season"] == 2026
    assert row["value_score"] == pytest.approx(82.75)
    assert row["confidence"] == pytest.approx(0.87)
    assert row["updated_at"] == NOW

    components = row["score_components"]
    assert components["score_label"] == "transfer impact score"
    assert components["ranking"] == {
        "status": "scored",
        "score": 90.0,
        "confidence": 1.0,
        "source": "fs_rankings_history",
        "rank": 7,
        "points": 180.0,
        "weapon": "Epee",
        "category": "Women's Senior",
    }
    assert components["performance"]["score"] == pytest.approx(78.0)
    assert components["performance"]["competitions"] == 3
    assert components["performance"]["avg_rank"] == pytest.approx(8.67)
    assert components["form"]["rank_change"] == 5
    assert components["form"]["score"] == pytest.approx(75.0)
    assert components["age"]["age"] == 24
    assert components["age"]["score"] == pytest.approx(85.0)
    assert components["category"]["category"] == "Senior"
    assert components["missing_signals"] == []

    serialized = json.dumps(row, sort_keys=True).lower()
    assert "market_value" not in serialized
    assert "salary" not in serialized
    assert "personal worth" not in serialized


def test_missing_data_creates_low_confidence_no_score_row_without_fabricated_components():
    from compute_transfer_value import build_transfer_value_rows

    rows, skipped = build_transfer_value_rows(
        [{"id": BOB}],
        ranking_history=[],
        results=[],
        tournaments=[],
        season=2026,
        updated_at=NOW,
    )

    assert skipped == 0
    assert rows == [
        {
            "fencer_id": BOB,
            "season": 2026,
            "value_score": None,
            "score_components": {
                "score_label": "transfer impact score",
                "ranking": {"status": "missing", "reason": "no public ranking signal"},
                "performance": {"status": "missing", "reason": "no public result signal for season"},
                "form": {"status": "missing", "reason": "no comparable public form signal"},
                "age": {"status": "missing", "reason": "no public birth date or birth year"},
                "category": {"status": "missing", "reason": "no public category signal"},
                "missing_signals": ["ranking", "performance", "form", "age", "category"],
                "limitations": [
                    "Non-monetary decision-support score from public sport data only.",
                    "Excludes private, medical, financial, contract, academic, and consent-sensitive context.",
                    "Do not use as a sole recruiting, selection, eligibility, or compensation decision input.",
                ],
            },
            "confidence": 0.0,
            "updated_at": NOW,
        }
    ]


def test_missing_age_is_not_fabricated_when_other_signals_exist():
    from compute_transfer_value import build_transfer_value_rows

    rows, skipped = build_transfer_value_rows(
        [
            {
                "id": CAROL,
                "fie_id": "2002",
                "category": "Junior",
            }
        ],
        ranking_history=[
            {
                "fie_fencer_id": "2002",
                "weapon": "Foil",
                "category": "Women's Junior",
                "season": 2026,
                "rank": 5,
                "points": None,
            }
        ],
        results=[],
        tournaments=[],
        season=2026,
        updated_at=NOW,
    )

    assert skipped == 0
    row = rows[0]
    assert row["value_score"] is not None
    assert row["confidence"] < 0.5
    assert row["score_components"]["ranking"]["rank"] == 5
    assert row["score_components"]["age"] == {
        "status": "missing",
        "reason": "no public birth date or birth year",
    }
    assert "age" not in {
        key
        for key, value in row["score_components"]["age"].items()
        if value not in {"missing", "no public birth date or birth year"}
    }


def test_context_only_age_and_category_are_too_sparse_for_value_score():
    from compute_transfer_value import build_transfer_value_rows

    rows, skipped = build_transfer_value_rows(
        [
            {
                "id": ALICE,
                "category": "Senior",
                "date_of_birth": "1999-01-10",
            }
        ],
        ranking_history=[],
        results=[],
        tournaments=[],
        season=2026,
        updated_at=NOW,
    )

    assert skipped == 0
    row = rows[0]
    assert row["value_score"] is None
    assert row["confidence"] == pytest.approx(0.20)
    assert row["score_components"]["age"]["status"] == "scored"
    assert row["score_components"]["category"]["status"] == "scored"
    assert row["score_components"]["missing_signals"] == ["ranking", "performance", "form"]


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = None
        self.rows = None
        self.on_conflict = None
        self.start = 0
        self.end = 999

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.table_name, columns))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            if self.table_name == "fs_fencer_identities" and self.table_name not in self.client.tables:
                raise RuntimeError("missing identity table")
            page = self.client.tables.get(self.table_name, [])[self.start : self.end + 1]
            return FakeResult(page)
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.table_name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult([])
        raise AssertionError(f"unexpected operation for {self.table_name}")


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "fs_fencers": [
                {
                    "id": ALICE,
                    "fie_id": "1001",
                    "world_rank": 7,
                    "category": "Senior",
                    "date_of_birth": "2002-06-15",
                }
            ],
            "fs_rankings_history": [
                {"fie_fencer_id": "1001", "season": 2026, "weapon": "Epee", "category": "Senior", "rank": 7, "points": 180.0}
            ],
            "fs_results": [{"tournament_id": "t1", "fencer_id": ALICE, "rank": 1}],
            "fs_tournaments": [{"id": "t1", "season": 2026, "weapon": "Epee", "category": "Senior"}],
        }
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_compute_transfer_values_upserts_idempotently_by_fencer_and_season():
    from compute_transfer_value import compute_transfer_values

    client = FakeSupabase()

    first = compute_transfer_values(
        client=client,
        season=2026,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )
    second = compute_transfer_values(
        client=client,
        season=2026,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert first == second
    assert first["value_rows"] == 1
    assert first["written"] == 1
    assert len(client.upserts) == 2
    assert all(upsert["table"] == "fs_transfer_values" for upsert in client.upserts)
    assert all(upsert["on_conflict"] == "fencer_id,season" for upsert in client.upserts)
    assert client.upserts[0]["rows"] == client.upserts[1]["rows"]


def test_transfer_value_migration_defines_internal_non_monetary_table_and_limits():
    migration = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "20260602_transfer_value.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_transfer_values" in normalized
    assert "fencer_id uuid not null references public.fs_fencers(id)" in normalized
    assert "season integer not null" in normalized
    assert "value_score numeric(5,2)" in normalized
    assert "score_components jsonb not null default '{}'" in normalized
    assert "confidence numeric(4,2) not null default 0" in normalized
    assert "unique (fencer_id, season)" in normalized
    assert "check (value_score is null or (value_score >= 0 and value_score <= 100))" in normalized
    assert "check (confidence >= 0 and confidence <= 1)" in normalized
    assert "alter table public.fs_transfer_values enable row level security" in normalized
    assert "non-monetary" in normalized
    assert "public sport data only" in normalized
    assert "market_value" not in normalized
    assert "salary" not in normalized

from pathlib import Path

import pytest

from compute_rankings_trends import build_trend_rows, compute_rankings_trends


def by_season(rows):
    return {row["season"]: row for row in rows}


def test_build_trend_rows_computes_rank_and_points_changes():
    history = [
        {
            "fie_fencer_id": "1001",
            "weapon": "Epee",
            "category": "Men's Senior",
            "season": 2022,
            "rank": 10,
            "points": 100.0,
        },
        {
            "fie_fencer_id": "1001",
            "weapon": "Epee",
            "category": "Men's Senior",
            "season": 2023,
            "rank": 7,
            "points": 130.0,
        },
        {
            "fie_fencer_id": "1001",
            "weapon": "Epee",
            "category": "Men's Senior",
            "season": 2024,
            "rank": 7,
            "points": 120.0,
        },
        {
            "fie_fencer_id": "1001",
            "weapon": "Epee",
            "category": "Men's Senior",
            "season": 2025,
            "rank": 12,
            "points": 110.0,
        },
    ]

    rows, skipped = build_trend_rows(history, computed_at="2026-01-01T00:00:00+00:00")

    assert skipped == 0
    trends = by_season(rows)

    assert trends[2022]["trend_direction"] == "new"
    assert trends[2022]["previous_rank"] is None
    assert trends[2022]["rank_change"] is None
    assert trends[2022]["projected_next_rank"] == 10
    assert trends[2022]["projected_next_points"] == pytest.approx(100.0)

    assert trends[2023]["trend_direction"] == "up"
    assert trends[2023]["previous_rank"] == 10
    assert trends[2023]["rank_change"] == 3
    assert trends[2023]["previous_points"] == pytest.approx(100.0)
    assert trends[2023]["points_change"] == pytest.approx(30.0)
    assert trends[2023]["projected_next_rank"] == 8
    assert trends[2023]["projected_next_points"] == pytest.approx(118.75)

    assert trends[2024]["trend_direction"] == "stable"
    assert trends[2024]["rank_change"] == 0
    assert trends[2024]["points_change"] == pytest.approx(-10.0)
    assert trends[2024]["projected_next_rank"] == 8
    assert trends[2024]["projected_next_points"] == pytest.approx(119.0)

    assert trends[2025]["trend_direction"] == "down"
    assert trends[2025]["rank_change"] == -5
    assert trends[2025]["points_change"] == pytest.approx(-10.0)
    assert trends[2025]["projected_next_rank"] == 10
    assert trends[2025]["projected_next_points"] == pytest.approx(117.0)


def test_build_trend_rows_resets_previous_values_after_season_gap():
    history = [
        {
            "fie_fencer_id": "1001",
            "weapon": "Foil",
            "category": "Women's Junior",
            "season": 2021,
            "rank": 4,
            "points": 80.0,
        },
        {
            "fie_fencer_id": "1001",
            "weapon": "Foil",
            "category": "Women's Junior",
            "season": 2023,
            "rank": 2,
            "points": 120.0,
        },
    ]

    rows, skipped = build_trend_rows(history)

    assert skipped == 0
    trends = by_season(rows)
    assert trends[2021]["trend_direction"] == "new"
    assert trends[2023]["trend_direction"] == "new"
    assert trends[2023]["previous_rank"] is None
    assert trends[2023]["rank_change"] is None
    assert trends[2023]["previous_points"] is None
    assert trends[2023]["points_change"] is None
    assert trends[2023]["projected_next_rank"] == 2
    assert trends[2023]["projected_next_points"] == pytest.approx(120.0)


def test_build_trend_rows_groups_by_fencer_weapon_and_category():
    history = [
        {"fie_fencer_id": "1001", "weapon": "Epee", "category": "Men's Senior", "season": 2024, "rank": 5, "points": 200.0},
        {"fie_fencer_id": "1001", "weapon": "Foil", "category": "Men's Senior", "season": 2024, "rank": 15, "points": 70.0},
        {"fie_fencer_id": "1002", "weapon": "Epee", "category": "Men's Senior", "season": 2024, "rank": 9, "points": 90.0},
    ]

    rows, skipped = build_trend_rows(history)

    assert skipped == 0
    assert len(rows) == 3
    assert {row["trend_direction"] for row in rows} == {"new"}
    assert {(row["fencer_id"], row["weapon"], row["category"]) for row in rows} == {
        ("1001", "Epee", "Men's Senior"),
        ("1001", "Foil", "Men's Senior"),
        ("1002", "Epee", "Men's Senior"),
    }


def test_build_trend_rows_skips_rows_without_required_identity_or_rank():
    history = [
        {"fie_fencer_id": "", "weapon": "Epee", "category": "Men's Senior", "season": 2024, "rank": 5, "points": 200.0},
        {"fie_fencer_id": "1001", "weapon": "", "category": "Men's Senior", "season": 2024, "rank": 5, "points": 200.0},
        {"fie_fencer_id": "1001", "weapon": "Epee", "category": "Men's Senior", "season": 2024, "rank": None, "points": 200.0},
        {"fie_fencer_id": "1001", "weapon": "Epee", "category": "Men's Senior", "season": 2025, "rank": 3, "points": None},
    ]

    rows, skipped = build_trend_rows(history)

    assert skipped == 3
    assert len(rows) == 1
    assert rows[0]["trend_direction"] == "new"
    assert rows[0]["points"] is None
    assert rows[0]["projected_next_points"] is None


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.start = 0
        self.end = 999
        self.pending_upsert = None
        self.pending_conflict = None

    def select(self, columns):
        self.client.selects.append((self.table_name, columns))
        return self

    def order(self, column):
        self.client.orders.append(column)
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
                {
                    "table": self.table_name,
                    "rows": self.pending_upsert,
                    "on_conflict": self.pending_conflict,
                }
            )
            return FakeResult([])
        page = self.client.history[self.start : self.end + 1]
        return FakeResult(page)


class FakeClient:
    def __init__(self, history):
        self.history = history
        self.selects = []
        self.orders = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_compute_rankings_trends_fetches_history_and_upserts_rows():
    client = FakeClient(
        [
            {"fie_fencer_id": "1001", "weapon": "Sabre", "category": "Women's Senior", "season": 2024, "rank": 6, "points": 150.0},
            {"fie_fencer_id": "1001", "weapon": "Sabre", "category": "Women's Senior", "season": 2025, "rank": 4, "points": 170.0},
        ]
    )

    result = compute_rankings_trends(client=client, log_run=False)

    assert result == {"read": 2, "written": 2, "failed": 0, "skipped": 0}
    assert client.selects == [
        ("fs_rankings_history", "fie_fencer_id,season,weapon,category,rank,points")
    ]
    assert client.orders == ["fie_fencer_id", "weapon", "category", "season"]
    assert len(client.upserts) == 1
    assert client.upserts[0]["table"] == "fs_rankings_trends"
    assert client.upserts[0]["on_conflict"] == "fencer_id,weapon,category,season"
    assert client.upserts[0]["rows"][1]["trend_direction"] == "up"


def test_rankings_trends_migration_defines_table_and_constraints():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260601_rankings_trends.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_rankings_trends" in normalized
    assert "primary key (fencer_id, weapon, category, season)" in normalized
    assert "check (trend_direction in ('up', 'down', 'stable', 'new'))" in normalized

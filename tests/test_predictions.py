import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ALICE = "00000000-0000-0000-0000-000000000001"
BOB = "00000000-0000-0000-0000-000000000002"
CAROL = "00000000-0000-0000-0000-000000000003"
DAN = "00000000-0000-0000-0000-000000000004"
UPCOMING = "00000000-0000-0000-0000-000000000101"
PAST_WORLDS = "00000000-0000-0000-0000-000000000102"
PAST_GP = "00000000-0000-0000-0000-000000000103"
NOW = "2026-06-02T12:00:00+00:00"


def target_event(**overrides):
    row = {
        "id": UPCOMING,
        "name": "2027 World Championships Men's Epee",
        "type": "WCH",
        "weapon": "Epee",
        "category": "Men's Senior",
        "start_date": "2027-07-20",
        "season": 2027,
    }
    row.update(overrides)
    return row


def fencers_fixture():
    return [
        {
            "id": ALICE,
            "fie_id": "1001",
            "name": "Alice Prime",
            "country": "USA",
            "weapon": "Epee",
            "category": "Men's Senior",
            "world_rank": 1,
            "active": True,
            "rating": 1860,
        },
        {
            "id": BOB,
            "fie_id": "1002",
            "name": "Bob Veteran",
            "country": "ITA",
            "weapon": "Epee",
            "category": "Men's Senior",
            "world_rank": 12,
            "active": True,
        },
        {
            "id": CAROL,
            "fie_id": "1003",
            "name": "Carol Sparse",
            "country": "FRA",
            "weapon": "Epee",
            "category": "Men's Senior",
            "world_rank": None,
            "active": False,
        },
    ]


def rankings_fixture():
    return [
        {
            "fie_fencer_id": "1001",
            "season": 2026,
            "weapon": "Epee",
            "category": "Men's Senior",
            "rank": 1,
            "points": 310.0,
            "name": "Alice Prime",
            "country": "USA",
        },
        {
            "fie_fencer_id": "1002",
            "season": 2026,
            "weapon": "Epee",
            "category": "Men's Senior",
            "rank": 12,
            "points": 135.0,
            "name": "Bob Veteran",
            "country": "ITA",
        },
        {
            "fie_fencer_id": "1003",
            "season": 2023,
            "weapon": "Epee",
            "category": "Men's Senior",
            "rank": 18,
            "points": 70.0,
            "name": "Carol Sparse",
            "country": "FRA",
        },
    ]


def tournaments_fixture():
    return [
        {
            "id": PAST_GP,
            "name": "2026 Grand Prix Epee",
            "type": "GP",
            "weapon": "Epee",
            "category": "Men's Senior",
            "start_date": "2026-02-01",
            "season": 2026,
        },
        {
            "id": PAST_WORLDS,
            "name": "2025 World Championships Men's Epee",
            "type": "WCH",
            "weapon": "Epee",
            "category": "Men's Senior",
            "start_date": "2025-07-01",
            "season": 2025,
        },
    ]


def results_fixture():
    return [
        {"id": "r1", "tournament_id": PAST_GP, "fencer_id": ALICE, "rank": 1, "weapon": "Epee"},
        {"id": "r2", "tournament_id": PAST_GP, "fencer_id": BOB, "rank": 7, "weapon": "Epee"},
        {"id": "r3", "tournament_id": PAST_GP, "fencer_id": CAROL, "rank": 32, "weapon": "Epee"},
    ]


def metrics_fixture():
    return {
        "performance_rows": [
            {
                "fencer_id": ALICE,
                "weapon": "Epee",
                "competitions_count": 8,
                "avg_delta": 4.5,
                "clutch_score": 4.5,
                "overperformance_rate": 75.0,
            },
            {
                "fencer_id": BOB,
                "weapon": "Epee",
                "competitions_count": 6,
                "avg_delta": 0.0,
                "clutch_score": 0.0,
                "overperformance_rate": 50.0,
            },
        ],
        "strength_rows": [
            {"tournament_id": PAST_GP, "strength_score": 84.0, "total_fie_ranked": 64}
        ],
        "trend_rows": [
            {
                "fencer_id": "1001",
                "weapon": "Epee",
                "category": "Men's Senior",
                "trend_direction": "up",
                "rank_change": 2,
                "projected_next_rank": 1,
            },
            {
                "fencer_id": "1002",
                "weapon": "Epee",
                "category": "Men's Senior",
                "trend_direction": "stable",
                "rank_change": 0,
                "projected_next_rank": 11,
            },
        ],
        "medal_rows": [
            {"scope": "fencer", "fencer_id": ALICE, "tier": None, "gold": 2, "silver": 1, "bronze": 0, "total": 3},
            {"scope": "fencer", "fencer_id": BOB, "tier": None, "gold": 0, "silver": 1, "bronze": 2, "total": 3},
        ],
        "career_rows": [
            {"fencer_id": ALICE, "total_competitions": 30, "gold_medals": 2, "total_medals": 5},
            {"fencer_id": BOB, "total_competitions": 25, "gold_medals": 0, "total_medals": 3},
        ],
        "elo_rows": [
            {"fencer_id": BOB, "weapon": "Epee", "rating": 1710},
        ],
    }


def test_build_prediction_rows_calculates_transparent_factors_and_probabilities():
    from compute_predictions import build_prediction_rows

    rows, skipped = build_prediction_rows(
        target_events=[target_event()],
        fencers=fencers_fixture(),
        rankings=rankings_fixture(),
        results=results_fixture(),
        tournaments=tournaments_fixture(),
        generated_at=NOW,
        top_n=3,
        **metrics_fixture(),
    )

    assert skipped == 0
    assert [row["fencer_id"] for row in rows] == [ALICE, BOB, CAROL]
    assert sum(row["probability"] for row in rows) == pytest.approx(1.0)
    assert rows[0]["prediction_rank"] == 1
    assert rows[0]["probability"] > rows[1]["probability"] > rows[2]["probability"]
    assert rows[0]["score"] > rows[1]["score"] > rows[2]["score"]
    assert rows[0]["model_version"].startswith("transparent_baseline")
    assert rows[0]["analytics_label"] == "sports analytics - not betting advice or a guarantee"
    assert rows[0]["factors"]["ranking"]["rank"] == 1
    assert rows[0]["factors"]["recent_results"]["starts"] == 1
    assert rows[0]["factors"]["performance"]["competitions_count"] == 8
    assert rows[0]["factors"]["strength"]["average_recent_strength"] == pytest.approx(84.0)
    assert rows[0]["factors"]["legacy"]["medal_total"] == 3
    assert rows[0]["factors"]["elo"]["rating"] == 1860
    assert "relative probability" in " ".join(rows[0]["caveats"]).lower()


def test_prediction_ordering_is_deterministic_for_equal_scores():
    from compute_predictions import build_prediction_rows

    event = target_event()
    tied_fencers = [
        {"id": BOB, "fie_id": "1002", "name": "Bob", "country": "ITA", "weapon": "Epee", "category": "Men's Senior"},
        {"id": ALICE, "fie_id": "1001", "name": "Alice", "country": "USA", "weapon": "Epee", "category": "Men's Senior"},
    ]
    tied_rankings = [
        {"fie_fencer_id": "1002", "season": 2026, "weapon": "Epee", "category": "Men's Senior", "rank": 5, "points": 100.0},
        {"fie_fencer_id": "1001", "season": 2026, "weapon": "Epee", "category": "Men's Senior", "rank": 5, "points": 100.0},
    ]

    first_rows, _ = build_prediction_rows(
        target_events=[event],
        fencers=tied_fencers,
        rankings=tied_rankings,
        results=[],
        tournaments=[],
        generated_at=NOW,
    )
    second_rows, _ = build_prediction_rows(
        target_events=[event],
        fencers=list(reversed(tied_fencers)),
        rankings=list(reversed(tied_rankings)),
        results=[],
        tournaments=[],
        generated_at=NOW,
    )

    assert [row["fencer_id"] for row in first_rows] == [ALICE, BOB]
    assert [row["fencer_id"] for row in second_rows] == [ALICE, BOB]
    assert first_rows[0]["score"] == second_rows[0]["score"]


def test_missing_data_and_inactive_fencers_are_penalized_with_caveats():
    from compute_predictions import build_prediction_rows

    rows, skipped = build_prediction_rows(
        target_events=[target_event()],
        fencers=fencers_fixture(),
        rankings=rankings_fixture(),
        results=results_fixture()[:2],
        tournaments=tournaments_fixture(),
        generated_at=NOW,
        top_n=3,
        **metrics_fixture(),
    )
    by_id = {row["fencer_id"]: row for row in rows}

    assert skipped == 0
    assert by_id[CAROL]["score"] < by_id[BOB]["score"]
    caveats = " ".join(by_id[CAROL]["caveats"]).lower()
    assert "inactive" in caveats
    assert "limited current data" in caveats
    assert by_id[CAROL]["factors"]["data_quality"]["penalty_multiplier"] < 1.0


def test_backtest_rows_store_expected_vs_actual_validation_metrics():
    from compute_predictions import build_backtest_rows

    past_target = target_event(
        id=PAST_WORLDS,
        name="2025 World Championships Men's Epee",
        start_date="2025-07-01",
        season=2025,
    )
    earlier = {
        "id": PAST_GP,
        "name": "2025 Grand Prix Epee",
        "type": "GP",
        "weapon": "Epee",
        "category": "Men's Senior",
        "start_date": "2025-02-01",
        "season": 2025,
    }
    rankings = [
        {"fie_fencer_id": "1001", "season": 2025, "weapon": "Epee", "category": "Men's Senior", "rank": 1, "points": 300.0},
        {"fie_fencer_id": "1002", "season": 2025, "weapon": "Epee", "category": "Men's Senior", "rank": 2, "points": 250.0},
        {"fie_fencer_id": "1003", "season": 2025, "weapon": "Epee", "category": "Men's Senior", "rank": 3, "points": 225.0},
        {"fie_fencer_id": "1004", "season": 2025, "weapon": "Epee", "category": "Men's Senior", "rank": 4, "points": 200.0},
    ]
    fencers = fencers_fixture() + [
        {
            "id": DAN,
            "fie_id": "1004",
            "name": "Dan Fourth",
            "country": "KOR",
            "weapon": "Epee",
            "category": "Men's Senior",
            "world_rank": 4,
            "active": True,
        }
    ]
    results = [
        {"id": "gp1", "tournament_id": PAST_GP, "fencer_id": ALICE, "rank": 1},
        {"id": "gp2", "tournament_id": PAST_GP, "fencer_id": BOB, "rank": 2},
        {"id": "gp3", "tournament_id": PAST_GP, "fencer_id": CAROL, "rank": 3},
        {"id": "gp4", "tournament_id": PAST_GP, "fencer_id": DAN, "rank": 4},
        {"id": "w1", "tournament_id": PAST_WORLDS, "fencer_id": ALICE, "rank": 1, "medal": "gold"},
        {"id": "w2", "tournament_id": PAST_WORLDS, "fencer_id": BOB, "rank": 2, "medal": "silver"},
        {"id": "w3", "tournament_id": PAST_WORLDS, "fencer_id": CAROL, "rank": 3, "medal": "bronze"},
        {"id": "w4", "tournament_id": PAST_WORLDS, "fencer_id": DAN, "rank": 4},
    ]

    rows = build_backtest_rows(
        target_events=[past_target],
        fencers=fencers,
        rankings=rankings,
        results=results,
        tournaments=[earlier, past_target],
        generated_at=NOW,
        top_n=4,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["target_event_id"] == PAST_WORLDS
    assert row["candidates_count"] == 4
    assert row["actuals_count"] == 4
    assert row["top1_hit"] is True
    assert row["podium_recall"] == pytest.approx(1.0)
    assert row["mean_abs_rank_error"] == pytest.approx(0.0)
    assert row["brier_score"] >= 0.0
    assert row["expected_vs_actual"]["predicted"][0]["fencer_id"] == ALICE
    assert row["expected_vs_actual"]["actual"][0]["rank"] == 1


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.columns = None
        self.rows = None
        self.on_conflict = None
        self.range_start = 0
        self.range_end = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        self.client.selects.append((self.name, columns))
        if self.name not in self.client.tables:
            raise RuntimeError(f"relation {self.name} does not exist")
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def limit(self, _count):
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "upsert":
            self.client.upserts.append(
                {"table": self.name, "rows": self.rows, "on_conflict": self.on_conflict}
            )
            return FakeResult(self.rows)
        rows = list(self.client.tables.get(self.name, []))
        if self.range_end is not None:
            rows = rows[self.range_start : self.range_end + 1]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "fs_tournaments": [target_event(), *tournaments_fixture()],
            "fs_fencers": fencers_fixture(),
            "fs_rankings_history": rankings_fixture(),
            "fs_results": results_fixture()
            + [
                {"id": "w1", "tournament_id": PAST_WORLDS, "fencer_id": ALICE, "rank": 1, "medal": "gold"},
                {"id": "w2", "tournament_id": PAST_WORLDS, "fencer_id": BOB, "rank": 2, "medal": "silver"},
                {"id": "w3", "tournament_id": PAST_WORLDS, "fencer_id": CAROL, "rank": 3, "medal": "bronze"},
            ],
            "fs_fencer_performance_analysis": metrics_fixture()["performance_rows"],
            "fs_competition_strength": metrics_fixture()["strength_rows"],
            "fs_rankings_trends": metrics_fixture()["trend_rows"],
            "fs_medal_tables": metrics_fixture()["medal_rows"],
            "fs_fencer_career_stats": metrics_fixture()["career_rows"],
            "fs_fencer_elo": metrics_fixture()["elo_rows"],
        }
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_predictions_fetches_inputs_and_upserts_predictions_and_backtests():
    from compute_predictions import compute_predictions

    client = FakeSupabase()

    summary = compute_predictions(
        client=client,
        generated_at=NOW,
        today="2026-06-02",
        top_n=3,
        log_run=False,
        update_state=False,
    )

    assert summary["target_events"] == 1
    assert summary["prediction_rows"] == 3
    assert summary["backtest_rows"] == 1
    assert summary["written"] == 4
    assert ("fs_rankings_history", "fie_fencer_id,season,weapon,category,rank,points,name,country") in client.selects
    assert ("fs_fencer_elo", "fencer_id,weapon,rating,peak_rating") in client.selects

    prediction_upsert = client.upserts[0]
    assert prediction_upsert["table"] == "fs_predictions"
    assert prediction_upsert["on_conflict"] == "id"
    assert prediction_upsert["rows"][0]["analytics_label"] == "sports analytics - not betting advice or a guarantee"

    backtest_upsert = client.upserts[1]
    assert backtest_upsert["table"] == "fs_prediction_backtests"
    assert backtest_upsert["on_conflict"] == "id"
    assert backtest_upsert["rows"][0]["expected_vs_actual"]["actual"]


def test_predictions_migration_defines_prediction_and_backtest_storage():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_predictions.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_predictions" in normalized
    assert "id text primary key" in normalized
    assert "target_event_id uuid references public.fs_tournaments(id)" in normalized
    assert "fencer_id uuid references public.fs_fencers(id)" in normalized
    assert "probability numeric" in normalized
    assert "check (probability >= 0 and probability <= 1)" in normalized
    assert "score numeric" in normalized
    assert "factors jsonb not null default '{}'::jsonb" in normalized
    assert "model_version text not null" in normalized
    assert "generated_at timestamptz not null" in normalized
    assert "caveats text[] not null default '{}'::text[]" in normalized
    assert "sports analytics - not betting advice or a guarantee" in normalized
    assert "create table if not exists public.fs_prediction_backtests" in normalized
    assert "expected_vs_actual jsonb not null default '{}'::jsonb" in normalized
    assert "top1_hit boolean" in normalized
    assert "podium_recall numeric" in normalized
    assert "brier_score numeric" in normalized
    assert "alter table public.fs_predictions enable row level security" in normalized
    assert "alter table public.fs_prediction_backtests enable row level security" in normalized

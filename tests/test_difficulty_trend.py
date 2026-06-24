import os
import sys
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-01T12:00:00+00:00"


def row_key(row):
    return (
        row["event_type"],
        row["tier"],
        row["weapon"],
        row["gender"],
        row["category"],
        row["season"],
    )


def test_moving_average_uses_available_sparse_seasons_in_order():
    from compute_difficulty_trend import build_difficulty_trend_rows

    tournaments: list[dict[str, Any]] = [
        {"id": "t-2022", "season": "2021-2022", "weapon": "E", "gender": "M", "category": "Senior", "tier": "GP", "competition_type": "Individual"},
        {"id": "t-2024", "season": "2023/24", "weapon": "Epee", "gender": "Men", "category": "Senior", "tier": "Grand Prix", "competition_type": "Individual"},
        {"id": "t-2025", "season": 2025, "weapon": "epee", "gender": "Men's", "category": "Men's Senior", "tier": "GP", "competition_type": "Individual"},
    ]
    strength_rows: list[dict[str, Any]] = [
        {"tournament_id": "t-2024", "strength_score": 70, "avg_world_rank": 25, "top8_count": 2, "top16_count": 4, "total_fie_ranked": 12},
        {"tournament_id": "t-2022", "strength_score": 50, "avg_world_rank": 40, "top8_count": 1, "top16_count": 2, "total_fie_ranked": 8},
        {"tournament_id": "t-2025", "strength_score": 90, "avg_world_rank": 15, "top8_count": 3, "top16_count": 6, "total_fie_ranked": 16},
    ]

    rows, report = build_difficulty_trend_rows(
        tournaments,
        strength_rows,
        ranking_rows=[],
        result_rows=[],
        moving_window=2,
        computed_at=NOW,
    )

    assert report["skipped_total"] == 0
    assert [row["season"] for row in rows] == [2022, 2024, 2025]
    assert [row["season_label"] for row in rows] == ["2021-2022", "2023-2024", "2024-2025"]
    assert rows[0]["moving_avg_strength_score"] == pytest.approx(50.0)
    assert rows[1]["moving_avg_strength_score"] == pytest.approx(60.0)
    assert rows[1]["previous_strength_score"] == pytest.approx(50.0)
    assert rows[1]["trend_delta"] == pytest.approx(20.0)
    assert rows[2]["moving_avg_strength_score"] == pytest.approx(80.0)
    assert rows[2]["window_sample_count"] == 2
    assert rows[2]["window_tournament_count"] == 2
    assert rows[2]["trend_direction"] == "harder"


def test_tier_grouping_uses_explicit_fields_not_event_names():
    from compute_difficulty_trend import build_difficulty_trend_rows

    tournaments = [
        {
            "id": "explicit-gp",
            "name": "Senior World Cup That Should Not Override Tier",
            "season": 2024,
            "weapon": "foil",
            "gender": "women",
            "category": "Senior",
            "tier": "GP",
            "competition_type": "Individual",
        },
        {
            "id": "name-only",
            "name": "World Cup Name Without Explicit Tier",
            "season": 2024,
            "weapon": "foil",
            "gender": "women",
            "category": "Senior",
            "competition_type": "Individual",
        },
    ]
    strength_rows: list[dict[str, Any]] = [
        {"tournament_id": "explicit-gp", "strength_score": 80, "total_fie_ranked": 20},
        {"tournament_id": "name-only", "strength_score": 20, "total_fie_ranked": 6},
    ]

    rows, report = build_difficulty_trend_rows(
        tournaments,
        strength_rows,
        ranking_rows=[],
        result_rows=[],
        computed_at=NOW,
    )

    assert report["skipped_total"] == 0
    rows_by_tier = {row["tier"]: row for row in rows}
    assert set(rows_by_tier) == {"GP", "Unknown"}
    assert rows_by_tier["GP"]["avg_strength_score"] == pytest.approx(80.0)
    assert rows_by_tier["Unknown"]["avg_strength_score"] == pytest.approx(20.0)
    assert rows_by_tier["Unknown"]["sample_count"] == 1


def test_missing_strength_is_skipped_but_missing_rankings_reduce_confidence():
    from compute_difficulty_trend import build_difficulty_trend_rows

    tournaments = [
        {"id": "ranked", "season": 2025, "weapon": "S", "gender": "F", "category": "Junior", "type": "WC", "event_type": "Individual"},
        {"id": "no-ranking", "season": 2025, "weapon": "S", "gender": "M", "category": "Junior", "type": "WC", "event_type": "Individual"},
        {"id": "missing-strength", "season": 2025, "weapon": "S", "gender": "F", "category": "Junior", "type": "WC", "event_type": "Individual"},
    ]
    strength_rows: list[dict[str, Any]] = [
        {"tournament_id": "ranked", "strength_score": 77, "total_fie_ranked": 10},
        {"tournament_id": "no-ranking", "strength_score": 55, "total_fie_ranked": 9},
        {"tournament_id": "missing-strength", "strength_score": None, "total_fie_ranked": 3},
    ]
    ranking_rows = [
        {"season": "2024-2025", "weapon": "sabre", "gender": "women", "category": "Junior", "rank": 1, "fie_fencer_id": "1001"},
        {"season": 2025, "weapon": "S", "gender": "F", "category": "Women's Junior", "rank": 2, "fie_fencer_id": "1002"},
    ]
    result_rows = [
        {"tournament_id": "ranked", "fencer_id": "a"},
        {"tournament_id": "ranked", "fencer_id": "b"},
        {"tournament_id": "no-ranking", "fencer_id": "c"},
    ]

    rows, report = build_difficulty_trend_rows(
        tournaments,
        strength_rows,
        ranking_rows=ranking_rows,
        result_rows=result_rows,
        computed_at=NOW,
    )

    assert report["skipped"]["missing_strength_score"] == 1
    assert report["skipped_total"] == 1

    rows_by_gender = {row["gender"]: row for row in rows}
    assert rows_by_gender["Women's"]["ranking_sample_count"] == 2
    assert rows_by_gender["Women's"]["result_sample_count"] == 2
    assert rows_by_gender["Women's"]["confidence"] > rows_by_gender["Men's"]["confidence"]
    assert rows_by_gender["Men's"]["ranking_sample_count"] == 0
    assert rows_by_gender["Men's"]["confidence_level"] == "low"


def test_changing_event_formats_are_separate_trend_groups():
    from compute_difficulty_trend import build_difficulty_trend_rows

    tournaments = [
        {"id": "ind-2024", "season": 2024, "weapon": "Foil", "gender": "Men's", "category": "Senior", "tier": "World Championships", "competition_type": "Individual"},
        {"id": "team-2024", "season": 2024, "weapon": "Foil", "gender": "Men's", "category": "Senior", "tier": "World Championships", "competition_type": "Team"},
        {"id": "ind-2025", "season": 2025, "weapon": "Foil", "gender": "Men's", "category": "Senior", "tier": "Worlds", "competition_type": "Individual"},
    ]
    strength_rows = [
        {"tournament_id": "ind-2024", "strength_score": 90, "total_fie_ranked": 18},
        {"tournament_id": "team-2024", "strength_score": 65, "total_fie_ranked": 12},
        {"tournament_id": "ind-2025", "strength_score": 95, "total_fie_ranked": 20},
    ]

    rows, _ = build_difficulty_trend_rows(
        tournaments,
        strength_rows,
        ranking_rows=[],
        result_rows=[],
        computed_at=NOW,
    )

    assert [row_key(row) for row in rows] == [
        ("Individual", "Worlds", "Foil", "Men's", "Senior", 2024),
        ("Individual", "Worlds", "Foil", "Men's", "Senior", 2025),
        ("Team", "Worlds", "Foil", "Men's", "Senior", 2024),
    ]
    individual_2025 = rows[1]
    team_2024 = rows[2]
    assert individual_2025["previous_strength_score"] == pytest.approx(90.0)
    assert individual_2025["trend_direction"] == "harder"
    assert team_2024["previous_strength_score"] is None
    assert team_2024["trend_direction"] == "new"


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.range_start = 0
        self.range_end = None
        self.columns = None

    def select(self, columns):
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def execute(self):
        rows = self.client.tables[self.name]
        end = self.range_end + 1 if self.range_end is not None else None
        return FakeResult(rows[self.range_start:end])


class FakeClient:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_difficulty_trend_reads_source_tables_and_returns_report():
    from compute_difficulty_trend import compute_difficulty_trend

    client = FakeClient(
        {
            "fs_tournaments": [
                {"id": "t-1", "season": 2024, "weapon": "Epee", "gender": "Men's", "category": "Senior", "tier": "GP", "competition_type": "Individual"},
            ],
            "fs_competition_strength": [
                {"tournament_id": "t-1", "strength_score": 88, "avg_world_rank": 17, "top8_count": 2, "top16_count": 5, "total_fie_ranked": 14},
            ],
            "fs_rankings_history": [
                {"season": 2024, "weapon": "Epee", "gender": "Men's", "category": "Senior", "rank": 1, "fie_fencer_id": "1001"},
            ],
            "fs_results": [
                {"tournament_id": "t-1", "fencer_id": "1001"},
                {"tournament_id": "t-1", "fencer_id": "1002"},
            ],
        }
    )

    result = compute_difficulty_trend(
        client=client,
        page_size=2,
        log_run=False,
        update_state=False,
        computed_at=NOW,
    )

    assert result["trend_rows"] == 1
    assert result["skipped"] == 0
    assert result["report"]["input_strength_rows"] == 1
    assert result["rows"][0]["sample_count"] == 1
    assert result["rows"][0]["ranking_sample_count"] == 1
    assert result["rows"][0]["result_sample_count"] == 2
    assert [table for table, _ in client.selects] == [
        "fs_tournaments",
        "fs_competition_strength",
        "fs_rankings_history",
        "fs_results",
        "fs_results",
    ]

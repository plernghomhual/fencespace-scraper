import os
import sys
from typing import Any, cast

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-01T12:00:00+00:00"


def test_build_medal_efficiency_rows_computes_denominator_and_tier_metrics():
    from compute_medal_efficiency import build_medal_efficiency_rows

    medal_rows = [
        {
            "scope": "country",
            "country": "United States",
            "season": 2026,
            "gold": 1,
            "silver": 1,
            "bronze": 2,
            "total": 4,
        },
        {
            "scope": "tier_country",
            "country": "United States",
            "season": "2025-2026",
            "tier": "Olympics",
            "gold": 1,
            "silver": 1,
            "bronze": 0,
            "total": 2,
        },
        {
            "scope": "tier_country",
            "country": "United States",
            "season": "2025-2026",
            "tier": "WC",
            "gold": 0,
            "silver": 0,
            "bronze": 2,
            "total": 2,
        },
    ]
    country_depth_rows: list[dict[str, Any]] = [
        {"country": "USA", "weapon": "Foil", "category": "Senior", "total_ranked": 60},
        {"country": "USA", "weapon": "Epee", "category": "Senior", "total_ranked": "40"},
    ]
    country_code_rows = [
        {
            "country": "United States",
            "country_code": "USA",
            "ioc": "USA",
            "iso3": "USA",
            "name": "United States",
        }
    ]
    population_rows = [
        {"country_code": "USA", "season": "2025-2026", "population": "331,000,000"}
    ]
    fencer_count_rows = [
        {"country_code": "USA", "season": 2026, "active_fencers": "1,000"}
    ]
    competition_rows = [
        {
            "country_code": "USA",
            "season": 2026,
            "competition_count": "10",
            "competition_tier": "Olympics",
            "competition_type": "Individual",
        },
        {
            "country": "United States",
            "season": "2025-2026",
            "competition_count": 4,
            "competition_tier": "WC",
            "competition_type": "Team",
        },
    ]

    rows, skipped = build_medal_efficiency_rows(
        medal_rows,
        country_depth_rows=country_depth_rows,
        country_code_rows=country_code_rows,
        population_rows=population_rows,
        fencer_count_rows=fencer_count_rows,
        competition_rows=competition_rows,
        updated_at=NOW,
    )

    assert skipped == 0
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "2025-2026:USA"
    assert row["country_code"] == "USA"
    assert row["country"] == "United States"
    assert row["season"] == "2025-2026"
    assert row["gold"] == 1
    assert row["silver"] == 1
    assert row["bronze"] == 2
    assert row["total_medals"] == 4
    assert row["population"] == 331000000
    assert row["active_fencers"] == 1000
    assert row["competition_count"] == 14
    assert row["ranked_fencer_sample_count"] == 100
    assert row["country_depth_rows"] == 2
    assert row["medals_per_capita"] == pytest.approx(4 / 331000000)
    assert row["medals_per_million"] == pytest.approx(4 / 331000000 * 1_000_000)
    assert row["medals_per_active_fencer"] == pytest.approx(0.004)
    assert row["medals_per_competition"] == pytest.approx(4 / 14)
    assert row["tier_weighted_medal_score"] == pytest.approx(28.0)
    assert row["tier_weighted_efficiency"] == pytest.approx(2.0)
    assert row["competition_tiers"] == ["Olympics", "WC"]
    assert row["competition_types"] == ["Individual", "Team"]
    assert row["population_sample_count"] == 1
    assert row["active_fencer_sample_count"] == 1
    assert row["competition_sample_count"] == 2
    assert row["medal_sample_count"] == 4
    assert row["missing_denominators"] == []
    assert row["is_small_sample"] is False
    assert row["is_rankable"] is True
    assert row["sample_confidence"] == "medium"
    assert row["updated_at"] == NOW


def test_missing_population_and_fencer_counts_leave_null_efficiency_fields():
    from compute_medal_efficiency import build_medal_efficiency_rows

    country_depth_rows: list[dict[str, Any]] = [
        {"country": "ITA", "weapon": "Foil", "category": "Senior", "total_ranked": 75}
    ]

    rows, skipped = build_medal_efficiency_rows(
        [
            {
                "scope": "country",
                "country": "Italy",
                "season": "2025-2026",
                "gold": 0,
                "silver": 1,
                "bronze": 2,
                "total": 3,
            }
        ],
        country_depth_rows=country_depth_rows,
        country_code_rows=[
            {"country": "Italy", "country_code": "ITA", "ioc": "ITA", "name": "Italy"}
        ],
        population_rows=[],
        fencer_count_rows=[],
        competition_rows=[
            {
                "country_code": "ITA",
                "season": "2025-2026",
                "competition_count": 6,
                "competition_tier": "Worlds",
                "competition_type": "Individual",
            }
        ],
        updated_at=NOW,
    )

    assert skipped == 0
    row = rows[0]
    assert row["population"] is None
    assert row["active_fencers"] is None
    assert row["medals_per_capita"] is None
    assert row["medals_per_million"] is None
    assert row["medals_per_active_fencer"] is None
    assert row["medals_per_competition"] == pytest.approx(0.5)
    assert row["population_sample_count"] == 0
    assert row["active_fencer_sample_count"] == 0
    assert row["competition_sample_count"] == 1
    assert row["missing_denominators"] == ["active_fencers", "population"]


def test_denominator_normalization_rejects_zero_negative_and_non_numeric_values():
    from compute_medal_efficiency import build_medal_efficiency_rows

    rows, skipped = build_medal_efficiency_rows(
        [
            {
                "scope": "country",
                "country_code": "FRA",
                "season": "2025-2026",
                "gold": 2,
                "silver": 0,
                "bronze": 0,
                "total": 2,
            }
        ],
        country_code_rows=[{"country_code": "FRA", "name": "France"}],
        population_rows=[{"country_code": "FRA", "season": "2025-2026", "population": "0"}],
        fencer_count_rows=[
            {"country_code": "FRA", "season": "2025-2026", "active_fencers": "-25"}
        ],
        competition_rows=[
            {
                "country_code": "FRA",
                "season": "2025-2026",
                "competition_count": "not available",
                "competition_tier": "GP",
                "competition_type": "Individual",
            }
        ],
        updated_at=NOW,
    )

    assert skipped == 0
    row = rows[0]
    assert row["population"] is None
    assert row["active_fencers"] is None
    assert row["competition_count"] is None
    assert row["medals_per_capita"] is None
    assert row["medals_per_active_fencer"] is None
    assert row["medals_per_competition"] is None
    assert row["population_sample_count"] == 0
    assert row["active_fencer_sample_count"] == 0
    assert row["competition_sample_count"] == 0
    assert row["missing_denominators"] == [
        "active_fencers",
        "competition_count",
        "population",
    ]


def test_tier_weights_use_explicit_competition_tier_and_type_fields():
    from compute_medal_efficiency import build_medal_efficiency_rows

    rows, _ = build_medal_efficiency_rows(
        [
            {
                "scope": "tier_country",
                "country_code": "JPN",
                "season": "2025-2026",
                "competition_tier": "Grand Prix",
                "competition_type": "Individual",
                "gold": 1,
                "silver": 0,
                "bronze": 0,
                "total": 1,
            },
            {
                "scope": "tier_country",
                "country_code": "JPN",
                "season": "2025-2026",
                "competition_tier": "World Championships",
                "competition_type": "Team",
                "gold": 0,
                "silver": 1,
                "bronze": 0,
                "total": 1,
            },
        ],
        country_code_rows=[{"country_code": "JPN", "name": "Japan"}],
        competition_rows=[
            {
                "country_code": "JPN",
                "season": "2025-2026",
                "competition_count": 2,
                "competition_tier": "Grand Prix",
                "competition_type": "Individual",
            }
        ],
        updated_at=NOW,
    )

    row = rows[0]
    assert row["gold"] == 1
    assert row["silver"] == 1
    assert row["bronze"] == 0
    assert row["total_medals"] == 2
    assert row["tier_weighted_medal_score"] == pytest.approx(14.0)
    assert row["tier_weighted_efficiency"] == pytest.approx(7.0)
    assert row["competition_tiers"] == ["GP"]
    assert row["competition_types"] == ["Individual"]


def test_small_samples_are_flagged_and_not_rankable():
    from compute_medal_efficiency import build_medal_efficiency_rows

    rows, _ = build_medal_efficiency_rows(
        [
            {
                "scope": "country",
                "country_code": "KOR",
                "country": "Korea",
                "season": "2025-2026",
                "gold": 1,
                "silver": 0,
                "bronze": 0,
                "total": 1,
            }
        ],
        country_code_rows=[{"country": "Korea", "country_code": "KOR", "name": "Korea"}],
        population_rows=[{"country_code": "KOR", "season": "2025-2026", "population": 51_000_000}],
        fencer_count_rows=[{"country_code": "KOR", "season": "2025-2026", "active_fencers": 300}],
        competition_rows=[
            {
                "country_code": "KOR",
                "season": "2025-2026",
                "competition_count": 1,
                "competition_tier": "Worlds",
                "competition_type": "Team",
            }
        ],
        updated_at=NOW,
    )

    row = rows[0]
    assert row["medal_sample_count"] == 1
    assert row["minimum_medal_sample"] == 3
    assert row["competition_sample_count"] == 1
    assert row["minimum_competition_sample"] == 3
    assert row["is_small_sample"] is True
    assert row["is_rankable"] is False
    assert row["sample_confidence"] == "low"


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.rows = None
        self.on_conflict = None
        self.range_start = 0
        self.range_end = None

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
        if self.operation == "upsert":
            self.client.upserts.append(
                {"table": self.name, "rows": self.rows, "on_conflict": self.on_conflict}
            )
            return FakeResult(self.rows)

        rows = list(self.client.tables.get(self.name, []))
        return FakeResult(rows[self.range_start : cast(int, self.range_end) + 1])


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "fs_medal_tables": [
                {
                    "scope": "country",
                    "country": "United States",
                    "season": 2026,
                    "gold": 1,
                    "silver": 0,
                    "bronze": 0,
                    "total": 1,
                }
            ],
            "fs_country_depth": [
                {"country": "USA", "weapon": "Foil", "category": "Senior", "total_ranked": 25}
            ],
            "fs_country_codes": [
                {"country": "United States", "country_code": "USA", "name": "United States"}
            ],
            "fs_country_population": [
                {"country_code": "USA", "season": "2025-2026", "population": 331000000}
            ],
            "fs_country_fencer_counts": [
                {"country_code": "USA", "season": "2025-2026", "active_fencers": 100}
            ],
            "fs_country_competition_counts": [
                {
                    "country_code": "USA",
                    "season": "2025-2026",
                    "competition_count": 5,
                    "competition_tier": "Olympics",
                    "competition_type": "Individual",
                }
            ],
        }
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_medal_efficiency_fetches_sources_and_upserts_rows():
    from compute_medal_efficiency import compute_medal_efficiency

    client = FakeSupabase()

    summary = compute_medal_efficiency(
        client=client,
        page_size=2,
        batch_size=10,
        updated_at=NOW,
        log_run=False,
        update_state=False,
    )

    assert summary == {
        "medal_rows_read": 1,
        "country_depth_rows_read": 1,
        "country_code_rows_read": 1,
        "population_rows_read": 1,
        "fencer_count_rows_read": 1,
        "competition_rows_read": 1,
        "efficiency_rows": 1,
        "written": 1,
        "skipped": 0,
    }
    assert client.selects[0][0] == "fs_medal_tables"
    assert {name for name, _columns in client.selects} >= {
        "fs_country_depth",
        "fs_country_codes",
        "fs_country_population",
        "fs_country_fencer_counts",
        "fs_country_competition_counts",
    }
    assert client.upserts[0]["table"] == "fs_medal_efficiency"
    assert client.upserts[0]["on_conflict"] == "id"
    assert client.upserts[0]["rows"][0]["id"] == "2025-2026:USA"

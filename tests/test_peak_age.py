from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import cast

import pytest


NOW = "2026-06-02T12:00:00+00:00"


def test_age_calculation_requires_full_dates_and_excludes_implausible_ages():
    from compute_peak_age import (
        MAX_RELIABLE_AGE,
        MIN_RELIABLE_AGE,
        age_at_event,
        is_reliable_age,
        parse_reliable_date,
    )

    assert cast(date, parse_reliable_date("2000-06-01")).isoformat() == "2000-06-01"
    assert parse_reliable_date("2000-06") is None
    assert parse_reliable_date("2000") is None
    assert parse_reliable_date(None) is None

    age = age_at_event("2000-06-01", "2025-06-01")
    assert age == pytest.approx(25.0, abs=0.01)

    assert is_reliable_age(MIN_RELIABLE_AGE)
    assert is_reliable_age(MAX_RELIABLE_AGE)
    assert not is_reliable_age(MIN_RELIABLE_AGE - 0.01)
    assert not is_reliable_age(MAX_RELIABLE_AGE + 0.01)


def test_build_peak_age_rows_skips_missing_partial_dates_and_outliers():
    from compute_peak_age import build_peak_age_rows

    fencers = [
        {"id": "f1", "birth_date": "2000-06-01", "country": "USA"},
        {"id": "partial", "birth_date": "2000-06", "country": "USA"},
        {"id": "missing", "country": "USA"},
        {"id": "young", "birth_date": "2018-01-01", "country": "USA"},
        {"id": "old", "birth_date": "1900-01-01", "country": "USA"},
    ]
    tournaments = [
        {
            "id": "t1",
            "name": "World Cup Cairo",
            "start_date": "2025-06-01",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "competition_tier": "world_cup",
        }
    ]
    results = [
        {"id": "r1", "tournament_id": "t1", "fencer_id": "f1", "rank": 1},
        {"id": "r2", "tournament_id": "t1", "fencer_id": "partial", "rank": 2},
        {"id": "r3", "tournament_id": "t1", "fencer_id": "missing", "rank": 3},
        {"id": "r4", "tournament_id": "t1", "fencer_id": "young", "rank": 4},
        {"id": "r5", "tournament_id": "t1", "fencer_id": "old", "rank": 5},
        {"id": "r6", "tournament_id": "missing-date", "fencer_id": "f1", "rank": 1},
    ]

    rows, summary = build_peak_age_rows(
        results=results,
        fencers=fencers,
        tournaments=tournaments,
        ranking_rows=[],
        identity_rows=[],
        include_country=True,
        min_cohort_size=1,
        computed_at=NOW,
    )

    assert summary["observations_used"] == 1
    assert summary["skipped_missing_birth_date"] == 1
    assert summary["skipped_unreliable_birth_date"] == 1
    assert summary["skipped_implausible_age"] == 2
    assert summary["skipped_missing_result_date"] == 1
    assert rows[0]["sample_size"] == 1
    assert rows[0]["country"] == "USA"
    assert rows[0]["competition_tier"] == "world_cup"


def test_build_peak_age_rows_groups_weapon_gender_category_country_and_tier_stats():
    from compute_peak_age import build_peak_age_rows

    ages = [22, 24, 26, 28, 30]
    fencers = [
        {
            "id": f"f{age}",
            "birth_date": f"{2025 - age}-06-01",
            "country": "USA",
        }
        for age in ages
    ]
    tournaments = [
        {
            "id": "foil-world",
            "name": "World Championships",
            "start_date": "2025-06-01",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "tier": "championship",
        }
    ]
    results = [
        {
            "id": f"r{age}",
            "tournament_id": "foil-world",
            "fencer_id": f"f{age}",
            "rank": index + 1,
        }
        for index, age in enumerate(ages)
    ]

    rows, summary = build_peak_age_rows(
        results=results,
        fencers=fencers,
        tournaments=tournaments,
        ranking_rows=[],
        identity_rows=[],
        include_country=True,
        min_cohort_size=5,
        computed_at=NOW,
    )

    assert summary["cohort_rows"] == 1
    assert summary["sparse_cohort_rows"] == 0
    assert rows == [
        {
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "country": "USA",
            "competition_tier": "championship",
            "source_type": "result",
            "sample_size": 5,
            "is_sparse": False,
            "min_age": 22.0,
            "p25_age": 24.0,
            "median_age": 26.0,
            "mean_age": 26.0,
            "p75_age": 28.0,
            "max_age": 30.0,
            "peak_age_range_start": 24.0,
            "peak_age_range_end": 28.0,
            "age_distribution": {
                "under_18": 0,
                "18_21": 0,
                "22_25": 2,
                "26_29": 2,
                "30_34": 1,
                "35_plus": 0,
            },
            "threshold_note": "ages 10.0-90.0 inclusive; exact YYYY-MM-DD birth/result dates only; sparse cohorts need n>=5",
            "computed_at": NOW,
        }
    ]


def test_duplicate_identity_results_count_once_per_competition():
    from compute_peak_age import build_peak_age_rows

    fencers = [
        {"id": "alice-foil", "birth_date": "2000-06-01", "country": "FRA"},
        {"id": "alice-epee", "birth_date": "2000-06-01", "country": "FRA"},
    ]
    tournaments = [
        {
            "id": "t1",
            "name": "Grand Prix",
            "start_date": "2025-06-01",
            "weapon": "Epee",
            "gender": "Women",
            "category": "Senior",
            "tier": "grand_prix",
        }
    ]
    results = [
        {"id": "r1", "tournament_id": "t1", "fencer_id": "alice-foil", "rank": 2},
        {"id": "r2", "tournament_id": "t1", "fencer_id": "alice-epee", "rank": 1},
    ]
    identities = [
        {
            "canonical_id": "alice-foil",
            "fs_fencer_row_ids": ["alice-foil", "alice-epee"],
        }
    ]

    rows, summary = build_peak_age_rows(
        results=results,
        fencers=fencers,
        tournaments=tournaments,
        ranking_rows=[],
        identity_rows=identities,
        include_country=True,
        min_cohort_size=1,
        computed_at=NOW,
    )

    assert summary["observations_used"] == 1
    assert summary["skipped_duplicate_identity_event"] == 1
    assert rows[0]["sample_size"] == 1
    assert rows[0]["mean_age"] == 25.0


def test_sparse_cohorts_are_reported_without_peak_range():
    from compute_peak_age import build_peak_age_rows

    fencers = [
        {"id": "f1", "birth_date": "2000-06-01", "country": "ITA"},
        {"id": "f2", "birth_date": "2002-06-01", "country": "ITA"},
    ]
    tournaments = [
        {
            "id": "t1",
            "name": "National Championships",
            "start_date": "2025-06-01",
            "weapon": "Sabre",
            "gender": "Men",
            "category": "Senior",
        }
    ]
    results = [
        {"id": "r1", "tournament_id": "t1", "fencer_id": "f1", "rank": 1},
        {"id": "r2", "tournament_id": "t1", "fencer_id": "f2", "rank": 2},
    ]

    rows, summary = build_peak_age_rows(
        results=results,
        fencers=fencers,
        tournaments=tournaments,
        ranking_rows=[],
        identity_rows=[],
        include_country=True,
        min_cohort_size=3,
        computed_at=NOW,
    )

    assert summary["sparse_cohort_rows"] == 1
    assert rows[0]["is_sparse"] is True
    assert rows[0]["sample_size"] == 2
    assert rows[0]["mean_age"] is None
    assert rows[0]["peak_age_range_start"] is None
    assert rows[0]["peak_age_range_end"] is None
    assert rows[0]["age_distribution"] == {
        "under_18": 0,
        "18_21": 0,
        "22_25": 2,
        "26_29": 0,
        "30_34": 0,
        "35_plus": 0,
    }


def test_rankings_need_reliable_ranking_dates_and_do_not_emit_person_level_data():
    from compute_peak_age import build_peak_age_rows

    fencers = [
        {"id": "f1", "fie_id": "101", "birth_date": "2000-06-01", "country": "USA"},
        {"id": "f2", "fie_id": "102", "birth_date": "2001-06-01", "country": "USA"},
    ]
    rankings = [
        {
            "id": "rank-1",
            "fie_fencer_id": "101",
            "rank": 1,
            "ranking_date": "2025-06-01",
            "weapon": "Epee",
            "gender": "Men",
            "category": "Senior",
            "country": "USA",
        },
        {
            "id": "rank-2",
            "fie_fencer_id": "102",
            "rank": 2,
            "season": 2025,
            "weapon": "Epee",
            "gender": "Men",
            "category": "Senior",
            "country": "USA",
        },
    ]

    rows, summary = build_peak_age_rows(
        results=[],
        fencers=fencers,
        tournaments=[],
        ranking_rows=rankings,
        identity_rows=[],
        include_country=True,
        min_cohort_size=1,
        computed_at=NOW,
    )

    assert summary["ranking_rows_read"] == 2
    assert summary["observations_used"] == 1
    assert summary["skipped_missing_result_date"] == 1
    assert rows[0]["source_type"] == "ranking"
    assert rows[0]["competition_tier"] == "ranking"
    assert rows[0]["sample_size"] == 1
    assert not ({"fencer_id", "fie_fencer_id", "name"} & set(rows[0]))


class FakeResult:
    def __init__(self, data=None):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = "select"
        self.rows = None
        self.on_conflict = None
        self.start = None
        self.end = None

    def select(self, columns):
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
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.table_name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult(self.rows)

        rows = list(self.client.tables.get(self.table_name, []))
        if self.start is not None and self.end is not None:
            rows = rows[self.start : self.end + 1]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_compute_peak_age_fetches_sources_and_can_upsert_aggregate_rows_only():
    from compute_peak_age import compute_peak_age

    client = FakeSupabase(
        {
            "fs_results": [
                {"id": "r1", "tournament_id": "t1", "fencer_id": "f1", "rank": 1},
                {"id": "r2", "tournament_id": "t1", "fencer_id": "f2", "rank": 2},
                {"id": "r3", "tournament_id": "t1", "fencer_id": "f3", "rank": 3},
                {"id": "r4", "tournament_id": "t1", "fencer_id": "f4", "rank": 4},
                {"id": "r5", "tournament_id": "t1", "fencer_id": "f5", "rank": 5},
            ],
            "fs_fencers": [
                {"id": "f1", "birth_date": "2000-06-01", "country": "USA"},
                {"id": "f2", "birth_date": "1999-06-01", "country": "USA"},
                {"id": "f3", "birth_date": "1998-06-01", "country": "USA"},
                {"id": "f4", "birth_date": "1997-06-01", "country": "USA"},
                {"id": "f5", "birth_date": "1996-06-01", "country": "USA"},
            ],
            "fs_tournaments": [
                {
                    "id": "t1",
                    "name": "World Cup",
                    "start_date": "2025-06-01",
                    "weapon": "Foil",
                    "gender": "Women",
                    "category": "Senior",
                    "competition_tier": "world_cup",
                }
            ],
            "fs_rankings_history": [],
            "fs_fencer_identities": [],
            "fs_competition_details": [],
        }
    )

    summary = compute_peak_age(
        client=client,
        page_size=2,
        include_country=True,
        min_cohort_size=5,
        write_table=True,
        log_run=False,
        update_state=False,
        computed_at=NOW,
    )

    assert summary["results_read"] == 5
    assert summary["fencers_read"] == 5
    assert summary["tournaments_read"] == 1
    assert summary["ranking_rows_read"] == 0
    assert summary["report_rows"] == 1
    assert summary["written"] == 1
    assert client.upserts[0]["table"] == "fs_peak_age_analysis"
    assert client.upserts[0]["on_conflict"] == (
        "weapon,gender,category,country,competition_tier,source_type"
    )
    assert not ({"fencer_id", "fie_fencer_id", "name"} & set(client.upserts[0]["rows"][0]))


def test_format_peak_age_report_documents_thresholds_and_sparse_status():
    from compute_peak_age import format_peak_age_report

    report = format_peak_age_report(
        [
            {
                "weapon": "Foil",
                "gender": "Women",
                "category": "Senior",
                "country": "ALL",
                "competition_tier": "world_cup",
                "source_type": "result",
                "sample_size": 2,
                "is_sparse": True,
                "peak_age_range_start": None,
                "peak_age_range_end": None,
                "median_age": None,
                "mean_age": None,
                "threshold_note": "ages 10.0-90.0 inclusive; exact YYYY-MM-DD birth/result dates only; sparse cohorts need n>=5",
            }
        ],
        {"observations_used": 2, "skipped_missing_birth_date": 1},
    )

    assert "exact YYYY-MM-DD birth/result dates only" in report
    assert "sparse" in report.lower()
    assert "fencer_id" not in report

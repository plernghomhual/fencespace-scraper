import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-01T12:00:00+00:00"


def country_codes():
    return [
        {
            "alpha3": "USA",
            "alpha2": "US",
            "name": "United States",
            "olympic_code": "USA",
            "fie_code": "USA",
            "aliases": ["United States of America", "Team USA"],
        },
        {
            "alpha3": "FRA",
            "alpha2": "FR",
            "name": "France",
            "olympic_code": "FRA",
            "fie_code": "FRA",
            "aliases": ["French Republic"],
        },
        {
            "alpha3": "ITA",
            "alpha2": "IT",
            "name": "Italy",
            "olympic_code": "ITA",
            "fie_code": "ITA",
            "aliases": [],
        },
        {
            "alpha3": "SGP",
            "alpha2": "SG",
            "name": "Singapore",
            "olympic_code": "SGP",
            "fie_code": "SGP",
            "aliases": ["Republic of Singapore"],
        },
    ]


def test_country_code_index_uses_country_code_rows_as_single_source_of_truth():
    from compute_country_specialization import build_country_code_index

    index = build_country_code_index(country_codes()[:2])

    assert index.lookup("USA") == "USA"
    assert index.lookup("us") == "USA"
    assert index.lookup("United States") == "USA"
    assert index.lookup("United States of America") == "USA"
    assert index.lookup("Team USA") == "USA"
    assert index.lookup("French Republic") == "FRA"
    assert index.lookup("Italy") is None


def test_specialization_index_compares_country_weapon_share_to_country_baseline():
    from compute_country_specialization import build_country_specialization_rows

    rows, skipped = build_country_specialization_rows(
        country_codes=country_codes(),
        country_depth_rows=[
            {"country": "United States", "weapon": "Foil", "category": "Senior", "total_ranked": 8, "fencers_in_top16": 4, "fencers_in_top32": 5, "fencers_in_top64": 7},
            {"country": "USA", "weapon": "Epee", "category": "Senior", "total_ranked": 2, "fencers_in_top16": 0, "fencers_in_top32": 1, "fencers_in_top64": 2},
            {"country": "France", "weapon": "Foil", "category": "Senior", "total_ranked": 2, "fencers_in_top16": 0, "fencers_in_top32": 1, "fencers_in_top64": 2},
            {"country": "FRA", "weapon": "Epee", "category": "Senior", "total_ranked": 9, "fencers_in_top16": 5, "fencers_in_top32": 7, "fencers_in_top64": 9},
        ],
        ranking_rows=[
            {"country": "Team USA", "weapon": "Foil", "gender": "Women", "category": "Senior", "season": 2026, "rank": 1, "points": 120.0},
            {"country": "USA", "weapon": "Foil", "gender": "Women", "category": "Senior", "season": 2026, "rank": 8, "points": 80.0},
            {"country": "United States of America", "weapon": "Epee", "gender": "Women", "category": "Senior", "season": 2026, "rank": 40, "points": 10.0},
            {"country": "France", "weapon": "Epee", "gender": "Women", "category": "Senior", "season": 2026, "rank": 1, "points": 130.0},
            {"country": "FRA", "weapon": "Epee", "gender": "Women", "category": "Senior", "season": 2026, "rank": 2, "points": 110.0},
            {"country": "French Republic", "weapon": "Foil", "gender": "Women", "category": "Senior", "season": 2026, "rank": 36, "points": 12.0},
        ],
        result_rows=[
            {"country": "United States", "tournament_id": "foil-worlds", "rank": 1, "medal": "Gold"},
            {"nationality": "USA", "tournament_id": "foil-worlds", "rank": 2, "medal": "Silver"},
            {"country": "FRA", "tournament_id": "epee-worlds", "rank": 1, "medal": "Gold"},
            {"country": "France", "tournament_id": "epee-worlds", "rank": 3, "medal": "Bronze"},
        ],
        tournament_rows=[
            {"id": "foil-worlds", "season": 2026, "weapon": "Foil", "gender": "Women", "category": "Senior", "type": "WCH", "name": "World Championships"},
            {"id": "epee-worlds", "season": 2026, "weapon": "Epee", "gender": "Women", "category": "Senior", "type": "WCH", "name": "World Championships"},
        ],
        medal_rows=[],
        computed_at=NOW,
    )

    assert skipped == {
        "country_depth": 0,
        "rankings": 0,
        "results": 0,
        "medals": 0,
        "unknown_country": 0,
        "missing_group": 0,
        "zero_score": 0,
    }

    by_key = {
        (row["country_code"], row["weapon"], row["category"], row["tier"], row["season"]): row
        for row in rows
    }
    usa_foil = by_key[("USA", "Foil", "Women's Senior", "Worlds", 2026)]
    usa_epee = by_key[("USA", "Epee", "Women's Senior", "Ranking", 2026)]
    fra_epee = by_key[("FRA", "Epee", "Women's Senior", "Worlds", 2026)]

    assert usa_foil["specialization_index"] > 1.0
    assert fra_epee["specialization_index"] > 1.0
    assert usa_foil["specialization_index"] > usa_epee["specialization_index"]
    assert usa_foil["sample_count"] == 2
    assert usa_foil["source_counts"] == {"results": 2}
    assert usa_foil["medal_count"] == 2
    assert usa_foil["country_share_in_segment"] > usa_epee["country_share_in_segment"]
    assert usa_foil["computed_at"] == NOW


def test_sparse_samples_get_low_confidence_and_are_flagged_sparse():
    from compute_country_specialization import build_country_specialization_rows

    rows, skipped = build_country_specialization_rows(
        country_codes=country_codes(),
        country_depth_rows=[],
        ranking_rows=[
            {"country": "SGP", "weapon": "Sabre", "gender": "Men", "category": "Senior", "season": 2026, "rank": 17},
            *[
                {"country": "USA", "weapon": "Sabre", "gender": "Men", "category": "Senior", "season": 2026, "rank": rank}
                for rank in (1, 2, 3, 4, 5, 6, 7, 8)
            ],
        ],
        result_rows=[],
        tournament_rows=[],
        medal_rows=[],
        computed_at=NOW,
    )

    assert skipped["unknown_country"] == 0
    singapore = next(row for row in rows if row["country_code"] == "SGP")
    usa = next(row for row in rows if row["country_code"] == "USA")

    assert singapore["sample_count"] == 1
    assert singapore["confidence"] < 0.25
    assert singapore["confidence_label"] == "low"
    assert singapore["is_sparse"] is True
    assert usa["sample_count"] == 8
    assert usa["confidence"] > singapore["confidence"]
    assert usa["is_sparse"] is False


def test_tie_handling_uses_competition_ranking_for_equal_indexes():
    from compute_country_specialization import build_country_specialization_rows

    rows, skipped = build_country_specialization_rows(
        country_codes=country_codes()[:3],
        country_depth_rows=[],
        ranking_rows=[
            {"country": "USA", "weapon": "Foil", "gender": "Women", "category": "Senior", "season": 2026, "rank": 10},
            {"country": "FRA", "weapon": "Foil", "gender": "Women", "category": "Senior", "season": 2026, "rank": 10},
            {"country": "ITA", "weapon": "Foil", "gender": "Women", "category": "Senior", "season": 2026, "rank": 10},
            {"country": "ITA", "weapon": "Epee", "gender": "Women", "category": "Senior", "season": 2026, "rank": 10},
            {"country": "ITA", "weapon": "Epee", "gender": "Women", "category": "Senior", "season": 2026, "rank": 11},
        ],
        result_rows=[],
        tournament_rows=[],
        medal_rows=[],
        computed_at=NOW,
    )

    assert skipped["unknown_country"] == 0
    foil_rows = sorted(
        [
            row
            for row in rows
            if row["weapon"] == "Foil" and row["tier"] == "Ranking" and row["season"] == 2026
        ],
        key=lambda row: row["country_code"],
    )

    ranks = {row["country_code"]: row["segment_rank"] for row in foil_rows}
    indexes = {row["country_code"]: row["specialization_index"] for row in foil_rows}
    assert ranks == {"FRA": 1, "ITA": 3, "USA": 1}
    assert indexes["USA"] == indexes["FRA"]
    assert indexes["ITA"] < indexes["USA"]


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.range_start = 0
        self.range_end = None
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
            page = self.client.tables.get(self.name, [])[self.range_start : self.range_end + 1]
            return FakeResult(page)
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult(self.rows)
        raise AssertionError(f"unexpected operation {self.operation} on {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_country_specialization_fetches_inputs_and_upserts_rows():
    from compute_country_specialization import compute_country_specialization

    client = FakeSupabase(
        {
            "fs_country_codes": country_codes()[:2],
            "fs_country_depth": [
                {"country": "United States", "weapon": "Foil", "category": "Senior", "total_ranked": 3, "fencers_in_top16": 1, "fencers_in_top32": 2, "fencers_in_top64": 3}
            ],
            "fs_rankings_history": [
                {"country": "USA", "weapon": "Foil", "gender": "Women", "category": "Senior", "season": 2026, "rank": 1, "points": 100.0}
            ],
            "fs_results": [
                {"country": "USA", "tournament_id": "foil-worlds", "rank": 1, "medal": "Gold"}
            ],
            "fs_tournaments": [
                {"id": "foil-worlds", "season": 2026, "weapon": "Foil", "gender": "Women", "category": "Senior", "type": "WCH", "name": "World Championships"}
            ],
            "fs_medal_tables": [
                {"scope": "tier_country", "country": "United States", "tier": "Worlds", "gold": 1, "silver": 0, "bronze": 0, "total": 1}
            ],
        }
    )

    summary = compute_country_specialization(
        client=client,
        page_size=2,
        batch_size=2,
        computed_at=NOW,
        log_run=False,
        update_state=False,
    )

    assert summary["country_code_rows"] == 2
    assert summary["country_depth_rows"] == 1
    assert summary["ranking_rows"] == 1
    assert summary["result_rows"] == 1
    assert summary["tournament_rows"] == 1
    assert summary["medal_rows"] == 1
    assert summary["specialization_rows"] == 4
    assert summary["written"] == 4
    assert summary["failed"] == 0
    assert summary["skipped"]["unknown_country"] == 0
    assert {name for name, _ in client.selects} == {
        "fs_country_codes",
        "fs_country_depth",
        "fs_rankings_history",
        "fs_results",
        "fs_tournaments",
        "fs_medal_tables",
    }
    assert len(client.upserts) == 2
    assert {call["table"] for call in client.upserts} == {"fs_country_specialization"}
    assert {call["on_conflict"] for call in client.upserts} == {"id"}


def test_missing_country_code_rows_skip_all_country_observations_without_fallback_grouping():
    from compute_country_specialization import build_country_specialization_rows

    rows, skipped = build_country_specialization_rows(
        country_codes=[],
        country_depth_rows=[
            {"country": "United States", "weapon": "Foil", "category": "Senior", "total_ranked": 8, "fencers_in_top16": 4, "fencers_in_top32": 5, "fencers_in_top64": 7},
        ],
        ranking_rows=[
            {"country": "USA", "weapon": "Foil", "gender": "Women", "category": "Senior", "season": 2026, "rank": 1},
        ],
        result_rows=[
            {"country": "United States", "tournament_id": "foil-worlds", "rank": 1, "medal": "Gold"},
        ],
        tournament_rows=[
            {"id": "foil-worlds", "season": 2026, "weapon": "Foil", "gender": "Women", "category": "Senior", "type": "WCH", "name": "World Championships"},
        ],
        medal_rows=[
            {"scope": "tier_country", "country": "USA", "tier": "Worlds", "gold": 1, "silver": 0, "bronze": 0, "total": 1},
        ],
        computed_at=NOW,
    )

    assert rows == []
    assert skipped["unknown_country"] == 4
    assert skipped["country_depth"] == 1
    assert skipped["rankings"] == 1
    assert skipped["results"] == 1
    assert skipped["medals"] == 1

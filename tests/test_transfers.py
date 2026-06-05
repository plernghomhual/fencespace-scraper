import os
import sys
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FENCER_A = "00000000-0000-0000-0000-0000000000a1"
FENCER_B = "00000000-0000-0000-0000-0000000000b2"
FENCER_C = "00000000-0000-0000-0000-0000000000c3"
FENCER_D = "00000000-0000-0000-0000-0000000000d4"
TOURNAMENT_1 = "10000000-0000-0000-0000-000000000001"
TOURNAMENT_2 = "10000000-0000-0000-0000-000000000002"


def test_confirmed_transfers_from_consecutive_ranking_seasons_with_fie_fallback():
    from compute_transfers import compute_confirmed_ranking_transfers

    rankings = [
        {
            "fencer_id": FENCER_A,
            "fie_fencer_id": "111",
            "season": 2024,
            "country": "USA",
            "weapon": "Foil",
            "category": "Men's Senior",
            "rank": 8,
        },
        {
            "fencer_id": FENCER_A,
            "fie_fencer_id": "111",
            "season": 2025,
            "country": "United States",
            "weapon": "Foil",
            "category": "Men's Senior",
            "rank": 5,
        },
        {
            "fencer_id": FENCER_A,
            "fie_fencer_id": "111",
            "season": 2026,
            "country": "France",
            "weapon": "Foil",
            "category": "Men's Senior",
            "rank": 4,
        },
        {
            "fencer_id": FENCER_B,
            "fie_fencer_id": "222",
            "season": 2024,
            "country": "Italy",
            "weapon": "Epee",
            "category": "Women's Senior",
            "rank": 20,
        },
        {
            "fencer_id": FENCER_B,
            "fie_fencer_id": "222",
            "season": 2026,
            "country": "Canada",
            "weapon": "Epee",
            "category": "Women's Senior",
            "rank": 9,
        },
        {
            "fie_fencer_id": "999",
            "season": "2025",
            "country": "AIN",
            "weapon": "Sabre",
            "category": "Men's Senior",
            "rank": 12,
        },
        {
            "fie_fencer_id": "999",
            "season": "2026",
            "country": "Georgia",
            "weapon": "Sabre",
            "category": "Men's Senior",
            "rank": 11,
        },
    ]

    transfers = compute_confirmed_ranking_transfers(
        rankings,
        fencer_id_by_fie_id={"999": FENCER_D},
        fencer_metadata={
            FENCER_A: {
                "nationality_history": [
                    {"country": "United States", "start_time": "2018-01-01"},
                    {"country": "France", "start_time": "2026-01-01"},
                ]
            }
        },
    )

    assert [(row["fencer_id"], row["from_country"], row["to_country"], row["season"]) for row in transfers] == [
        (FENCER_A, "United States", "France", "2026"),
        (FENCER_D, "Russia", "Georgia", "2026"),
    ]
    assert all(row["confirmed"] is True for row in transfers)
    assert all(row["competition_id"] is None for row in transfers)
    assert {row["source"] for row in transfers} == {"rankings_history"}
    assert transfers[0]["metadata"]["previous_season"] == 2025
    assert transfers[0]["metadata"]["current_season"] == 2026
    assert transfers[0]["metadata"]["wikidata_cross_check"] == "matched"


def test_uncertain_transfers_from_same_season_results_use_tournament_order():
    from compute_transfers import compute_uncertain_result_transfers

    tournaments = {
        TOURNAMENT_1: {
            "id": TOURNAMENT_1,
            "season": "2026",
            "start_date": "2025-11-20",
            "name": "November World Cup",
        },
        TOURNAMENT_2: {
            "id": TOURNAMENT_2,
            "season": "2026",
            "start_date": "2026-02-10",
            "name": "February Grand Prix",
        },
    }
    results = [
        {
            "fencer_id": FENCER_A,
            "tournament_id": TOURNAMENT_1,
            "country": "USA",
            "nationality": "USA",
            "rank": 6,
        },
        {
            "fencer_id": FENCER_A,
            "tournament_id": TOURNAMENT_2,
            "country": "France",
            "nationality": "France",
            "rank": 3,
        },
        {
            "fencer_id": FENCER_C,
            "tournament_id": TOURNAMENT_1,
            "country": "Italy",
            "rank": 10,
        },
    ]

    transfers = compute_uncertain_result_transfers(results, tournaments)

    assert len(transfers) == 1
    row = transfers[0]
    assert row["fencer_id"] == FENCER_A
    assert row["from_country"] == "United States"
    assert row["to_country"] == "France"
    assert row["season"] == "2026"
    assert row["competition_id"] == TOURNAMENT_2
    assert row["source"] == "results_same_season"
    assert row["confirmed"] is False
    assert row["metadata"]["from_competition_id"] == TOURNAMENT_1
    assert row["metadata"]["to_competition_id"] == TOURNAMENT_2


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.columns = None
        self.range_start = 0
        self.range_end = None
        self.upsert_rows = None
        self.on_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.upsert_rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            rows = self.client.tables.get(self.name, [])
            end = self.range_end if self.range_end is not None else len(rows) - 1
            return FakeResult(rows[self.range_start : end + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": list(cast(list[Any], self.upsert_rows)),
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult([])
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_and_store_transfers_fetches_sources_and_upserts_idempotently():
    from compute_transfers import compute_and_store_transfers

    client = FakeSupabase(
        {
            "fs_fencers": [
                {
                    "id": FENCER_A,
                    "fie_id": "111",
                    "metadata": {
                        "nationality_history": [
                            {"country": "United States"},
                            {"country": "France"},
                        ]
                    },
                },
                {"id": FENCER_D, "fie_id": "999", "metadata": {}},
            ],
            "fs_rankings_history": [
                {"fencer_id": FENCER_A, "fie_fencer_id": "111", "season": 2025, "country": "USA", "rank": 5},
                {"fencer_id": FENCER_A, "fie_fencer_id": "111", "season": 2026, "country": "France", "rank": 4},
            ],
            "fs_tournaments": [
                {"id": TOURNAMENT_1, "season": "2026", "start_date": "2025-11-20", "name": "November World Cup"},
                {"id": TOURNAMENT_2, "season": "2026", "start_date": "2026-02-10", "name": "February Grand Prix"},
            ],
            "fs_results": [
                {"fencer_id": FENCER_D, "tournament_id": TOURNAMENT_1, "country": "Russia", "nationality": "Russia"},
                {"fencer_id": FENCER_D, "tournament_id": TOURNAMENT_2, "country": "Georgia", "nationality": "Georgia"},
            ],
        }
    )

    first = compute_and_store_transfers(client=client, page_size=2, log_run=False, update_state=False)
    first_ids = [row["id"] for call in client.upserts for row in call["rows"]]

    client.upserts.clear()
    second = compute_and_store_transfers(client=client, page_size=2, log_run=False, update_state=False)
    second_ids = [row["id"] for call in client.upserts for row in call["rows"]]

    assert first == {
        "confirmed_transfers": 1,
        "uncertain_transfers": 1,
        "written": 2,
        "failed": 0,
        "skipped": 0,
    }
    assert second == first
    assert first_ids == second_ids
    assert {call["table"] for call in client.upserts} == {"fs_fencer_transfers"}
    assert {call["on_conflict"] for call in client.upserts} == {"id"}

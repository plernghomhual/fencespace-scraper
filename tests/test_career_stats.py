from typing import Any, cast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FENCER_ALICE_FOIL = "00000000-0000-0000-0000-000000000001"
FENCER_ALICE_EPEE = "00000000-0000-0000-0000-000000000002"
FENCER_BOB = "00000000-0000-0000-0000-000000000003"
FENCER_CAROL = "00000000-0000-0000-0000-000000000004"


def test_aggregate_career_stats_groups_identities_and_counts_medals_average_and_touches():
    from compute_career_stats import aggregate_career_stats

    tournaments: dict[str, dict[str, Any]] = {
        "tournament-2025-foil": {
            "id": "tournament-2025-foil",
            "season": "2025",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
        },
        "tournament-2026-epee": {
            "id": "tournament-2026-epee",
            "season": "2026",
            "weapon": "Epee",
            "gender": "Women",
            "category": "Senior",
        },
        "tournament-2026-sabre": {
            "id": "tournament-2026-sabre",
            "season": "2026",
            "weapon": "Sabre",
            "gender": "Men",
            "category": "Senior",
        },
    }
    results: list[dict[str, Any]] = [
        {"tournament_id": "tournament-2025-foil", "fencer_id": FENCER_ALICE_FOIL, "rank": 1},
        {"tournament_id": "tournament-2026-epee", "fencer_id": FENCER_ALICE_EPEE, "rank": 3},
        {"tournament_id": "tournament-2025-foil", "fencer_id": FENCER_ALICE_EPEE, "rank": 1},
        {"tournament_id": "tournament-2025-foil", "fencer_id": FENCER_BOB, "rank": 2},
        {"tournament_id": "tournament-2026-sabre", "fencer_id": FENCER_BOB, "rank": "T8."},
        {"tournament_id": "tournament-2026-epee", "fencer_id": None, "rank": 4},
    ]
    bouts: list[dict[str, Any]] = [
        {
            "tournament_id": "tournament-2025-foil",
            "fencer_a_id": FENCER_ALICE_FOIL,
            "fencer_b_id": FENCER_BOB,
            "score_a": 15,
            "score_b": 10,
        },
        {
            "tournament_id": "tournament-2026-epee",
            "fencer_a_id": FENCER_CAROL,
            "fencer_b_id": FENCER_ALICE_EPEE,
            "score_a": 11,
            "score_b": 15,
        },
        {
            "tournament_id": "tournament-2026-sabre",
            "fencer_a_id": FENCER_BOB,
            "fencer_b_id": FENCER_CAROL,
            "score_a": None,
            "score_b": 7,
        },
    ]
    identity_map: dict[str, str] = {
        FENCER_ALICE_FOIL: FENCER_ALICE_FOIL,
        FENCER_ALICE_EPEE: FENCER_ALICE_FOIL,
    }

    rows = aggregate_career_stats(results, tournaments, bouts, identity_map)
    by_fencer = {row["fencer_id"]: row for row in rows}

    alice = by_fencer[FENCER_ALICE_FOIL]
    assert alice["total_competitions"] == 2
    assert alice["gold_medals"] == 1
    assert alice["silver_medals"] == 0
    assert alice["bronze_medals"] == 1
    assert alice["top8_count"] == 2
    assert alice["best_rank"] == 1
    assert alice["avg_rank"] == 2.0
    assert alice["worst_rank"] == 3
    assert alice["weapons_used"] == ["Epee", "Foil"]
    assert alice["categories_competed"] == ["Women's Senior"]
    assert alice["first_season"] == "2025"
    assert alice["last_season"] == "2026"
    assert alice["total_touches_scored"] == 30
    assert alice["total_touches_received"] == 21
    assert alice["touch_differential"] == 9

    bob = by_fencer[FENCER_BOB]
    assert bob["total_competitions"] == 2
    assert bob["silver_medals"] == 1
    assert bob["top8_count"] == 2
    assert bob["avg_rank"] == 5.0
    assert bob["total_touches_scored"] == 10
    assert bob["total_touches_received"] == 15

    assert FENCER_CAROL not in by_fencer


class FakeResult:
    def __init__(self, data):
        self.data = data


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
            if self.name not in self.client.tables:
                raise RuntimeError(f"missing table {self.name}")
            return FakeResult(self.client.tables[self.name][self.range_start : cast(int, self.range_end) + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
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


def test_compute_career_stats_fetches_tables_and_upserts_per_canonical_fencer():
    from compute_career_stats import compute_career_stats

    client = FakeSupabase(
        {
            "fs_results": [
                {"tournament_id": "tournament-2025-foil", "fencer_id": FENCER_ALICE_FOIL, "rank": 1},
                {"tournament_id": "tournament-2026-epee", "fencer_id": FENCER_ALICE_EPEE, "rank": 3},
                {"tournament_id": "tournament-2025-foil", "fencer_id": FENCER_BOB, "rank": 2},
            ],
            "fs_tournaments": [
                {
                    "id": "tournament-2025-foil",
                    "season": "2025",
                    "weapon": "Foil",
                    "gender": "Women",
                    "category": "Senior",
                },
                {
                    "id": "tournament-2026-epee",
                    "season": "2026",
                    "weapon": "Epee",
                    "gender": "Women",
                    "category": "Senior",
                },
            ],
            "fs_bouts": [
                {
                    "tournament_id": "tournament-2025-foil",
                    "fencer_a_id": FENCER_ALICE_FOIL,
                    "fencer_b_id": FENCER_BOB,
                    "score_a": 15,
                    "score_b": 9,
                }
            ],
            "fs_fencer_identities": [
                {
                    "canonical_id": FENCER_ALICE_FOIL,
                    "fs_fencer_row_ids": [FENCER_ALICE_FOIL, FENCER_ALICE_EPEE],
                }
            ],
        }
    )

    summary = compute_career_stats(client=client, page_size=2, log_run=False, update_state=False)

    assert summary == {
        "results_read": 3,
        "bouts_read": 1,
        "career_rows": 2,
        "written": 2,
        "identity_rows": 1,
    }
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_fencer_career_stats"
    assert upsert["on_conflict"] == "fencer_id"
    upserted = {row["fencer_id"]: row for row in upsert["rows"]}
    assert upserted[FENCER_ALICE_FOIL]["total_competitions"] == 2
    assert upserted[FENCER_ALICE_FOIL]["gold_medals"] == 1
    assert upserted[FENCER_ALICE_FOIL]["bronze_medals"] == 1
    assert upserted[FENCER_ALICE_FOIL]["avg_rank"] == 2.0
    assert upserted[FENCER_BOB]["silver_medals"] == 1

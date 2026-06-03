import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ALICE_FOIL = "00000000-0000-0000-0000-000000000001"
ALICE_EPEE_ROW = "00000000-0000-0000-0000-000000000002"
BOB = "00000000-0000-0000-0000-000000000003"
CAROL = "00000000-0000-0000-0000-000000000004"
NOW = "2026-06-01T12:00:00+00:00"


def tournament(
    row_id,
    *,
    season=2026,
    weapon="Foil",
    gender="Women",
    category="Senior",
    end_date="2026-02-01",
):
    return {
        "id": row_id,
        "season": season,
        "weapon": weapon,
        "gender": gender,
        "category": category,
        "end_date": end_date,
    }


def result(row_id, tournament_id, fencer_id, rank, **extra):
    data = {
        "id": row_id,
        "tournament_id": tournament_id,
        "fencer_id": fencer_id,
        "rank": rank,
    }
    data.update(extra)
    return data


def bout(row_id, tournament_id, fencer_a, fencer_b, score_a, score_b, **extra):
    data = {
        "id": row_id,
        "tournament_id": tournament_id,
        "fencer_a": fencer_a,
        "fencer_b": fencer_b,
        "score_a": score_a,
        "score_b": score_b,
    }
    data.update(extra)
    return data


def test_normalize_stat_season_never_leaves_int_or_single_year_strings():
    from compute_fencer_season_stats import normalize_stat_season

    assert normalize_stat_season(2026) == "2025-2026"
    assert normalize_stat_season("2026") == "2025-2026"
    assert normalize_stat_season("2025-2026") == "2025-2026"
    assert normalize_stat_season("2025/2026") == "2025-2026"

    with pytest.raises(ValueError):
        normalize_stat_season("2026-2024")

    with pytest.raises(TypeError):
        normalize_stat_season(True)


def test_aggregate_counts_placements_medals_bouts_and_duplicate_identities():
    from compute_fencer_season_stats import build_fencer_season_stat_rows

    tournaments = {
        "foil-1": tournament("foil-1", season=2026, end_date="2026-01-10"),
        "foil-2": tournament("foil-2", season="2025-2026", end_date="2026-02-10"),
    }
    results = [
        result("r1", "foil-1", ALICE_FOIL, 1, medal="Gold"),
        result("r2", "foil-1", ALICE_EPEE_ROW, 2),
        result("r3", "foil-2", ALICE_EPEE_ROW, "T8."),
        result("r4", "foil-1", BOB, 3, medal="Bronze"),
        result("orphan", "foil-1", None, 4),
    ]
    bouts = [
        bout("b1", "foil-1", ALICE_FOIL, BOB, 15, 10),
        bout("b2", "foil-2", BOB, ALICE_EPEE_ROW, "15", "14"),
        bout("missing-score", "foil-2", ALICE_FOIL, BOB, None, 10),
    ]
    identity_rows = [
        {
            "id": "identity-alice-a",
            "fs_fencer_row_ids": [ALICE_FOIL, ALICE_EPEE_ROW],
            "fie_ids": ["1001"],
        },
        {
            "id": "identity-alice-b",
            "fs_fencer_row_ids": [ALICE_EPEE_ROW, ALICE_FOIL],
            "fie_ids": ["1001"],
        },
    ]

    rows, counters = build_fencer_season_stat_rows(
        results=results,
        tournaments=tournaments,
        bouts=bouts,
        identity_rows=identity_rows,
        updated_at=NOW,
    )
    by_key = {
        (row["fencer_id"], row["season"], row["weapon"], row["gender"], row["category"]): row
        for row in rows
    }

    assert counters["results_read"] == 5
    assert counters["bouts_read"] == 3
    assert counters["skipped_orphan_results"] == 1
    assert counters["skipped_missing_score_bouts"] == 1
    assert counters["duplicate_identity_members"] == 2

    alice = by_key[(ALICE_FOIL, "2025-2026", "Foil", "Women", "Senior")]
    assert alice["starts"] == 2
    assert alice["best_finish"] == 1
    assert alice["avg_finish"] == 4.5
    assert alice["gold_medals"] == 1
    assert alice["silver_medals"] == 0
    assert alice["bronze_medals"] == 0
    assert alice["medal_count"] == 1
    assert alice["top4_count"] == 1
    assert alice["top8_count"] == 2
    assert alice["top16_count"] == 2
    assert alice["top32_count"] == 2
    assert alice["wins"] == 1
    assert alice["losses"] == 1
    assert alice["bouts_total"] == 2
    assert alice["touches_scored"] == 29
    assert alice["touches_received"] == 25
    assert alice["touch_differential"] == 4
    assert alice["win_pct"] == 0.5
    assert alice["source_confidence"] == "unknown"
    assert alice["updated_at"] == NOW

    bob = by_key[(BOB, "2025-2026", "Foil", "Women", "Senior")]
    assert bob["starts"] == 1
    assert bob["bronze_medals"] == 1
    assert bob["wins"] == 1
    assert bob["losses"] == 1

    assert (ALICE_EPEE_ROW, "2025-2026", "Foil", "Women", "Senior") not in by_key


def test_aggregate_computes_finish_deltas_between_normalized_seasons():
    from compute_fencer_season_stats import build_fencer_season_stat_rows

    tournaments = {
        "old": tournament("old", season=2025, end_date="2025-03-01"),
        "new-1": tournament("new-1", season="2025-2026", end_date="2026-03-01"),
        "new-2": tournament("new-2", season="2025-2026", end_date="2026-04-01"),
    }
    results = [
        result("old-1", "old", ALICE_FOIL, 8),
        result("new-1", "new-1", ALICE_FOIL, 2),
        result("new-2", "new-2", ALICE_FOIL, 4),
    ]

    rows, counters = build_fencer_season_stat_rows(
        results=results,
        tournaments=tournaments,
        bouts=[],
        identity_rows=[],
        updated_at=NOW,
    )
    by_season = {row["season"]: row for row in rows}

    assert counters["skipped_orphan_results"] == 0
    assert by_season["2024-2025"]["best_finish"] == 8
    assert by_season["2024-2025"]["previous_best_finish"] is None
    assert by_season["2025-2026"]["best_finish"] == 2
    assert by_season["2025-2026"]["avg_finish"] == 3.0
    assert by_season["2025-2026"]["previous_best_finish"] == 8
    assert by_season["2025-2026"]["best_finish_delta"] == -6
    assert by_season["2025-2026"]["previous_avg_finish"] == 8.0
    assert by_season["2025-2026"]["avg_finish_delta"] == -5.0


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
            return FakeResult([])
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_fencer_season_stats_upserts_with_deterministic_conflict_key():
    from compute_fencer_season_stats import compute_fencer_season_stats

    client = FakeSupabase(
        {
            "fs_results": [
                result("r1", "foil-1", ALICE_FOIL, 1),
                result("r2", "foil-2", ALICE_EPEE_ROW, 8),
            ],
            "fs_bouts": [
                {
                    "id": "b1",
                    "tournament_id": "foil-1",
                    "fencer_a_id": ALICE_FOIL,
                    "fencer_b_id": BOB,
                    "score_a": 15,
                    "score_b": 9,
                }
            ],
            "fs_tournaments": [
                tournament("foil-1", season=2026),
                tournament("foil-2", season=2026),
            ],
            "fs_fencer_identities": [
                {
                    "id": "identity-alice",
                    "fs_fencer_row_ids": [ALICE_FOIL, ALICE_EPEE_ROW],
                    "fie_ids": ["1001"],
                }
            ],
        }
    )

    summary = compute_fencer_season_stats(
        client=client,
        page_size=2,
        batch_size=1,
        updated_at=NOW,
        log_run=False,
        update_state=False,
    )

    assert summary["results_read"] == 2
    assert summary["bouts_read"] == 1
    assert summary["season_stat_rows"] == 2
    assert summary["written"] == 2
    assert summary["failed"] == 0
    assert summary["skipped"] == 0
    assert summary["identity_rows"] == 1
    assert len(client.upserts) == 2
    assert {call["table"] for call in client.upserts} == {"fs_fencer_season_stats"}
    assert {call["on_conflict"] for call in client.upserts} == {
        "fencer_id,season,weapon,gender,category,source_confidence"
    }
    upserted = [row for call in client.upserts for row in call["rows"]]
    alice = next(row for row in upserted if row["fencer_id"] == ALICE_FOIL)
    assert alice["starts"] == 2
    assert alice["season"] == "2025-2026"


def test_compute_fencer_season_stats_empty_inputs_do_not_upsert():
    from compute_fencer_season_stats import compute_fencer_season_stats

    client = FakeSupabase(
        {
            "fs_results": [],
            "fs_bouts": [],
            "fs_tournaments": [],
            "fs_fencer_identities": [],
        }
    )

    summary = compute_fencer_season_stats(
        client=client,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary["results_read"] == 0
    assert summary["bouts_read"] == 0
    assert summary["season_stat_rows"] == 0
    assert summary["written"] == 0
    assert summary["failed"] == 0
    assert summary["skipped"] == 0
    assert client.upserts == []

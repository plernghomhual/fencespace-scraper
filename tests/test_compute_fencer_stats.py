import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ALICE_FOIL = "00000000-0000-0000-0000-000000000001"
ALICE_EPEE = "00000000-0000-0000-0000-000000000002"
BOB = "00000000-0000-0000-0000-000000000003"
CAROL = "00000000-0000-0000-0000-000000000004"
ALICE_IDENTITY = "10000000-0000-0000-0000-000000000001"
NOW = "2026-06-01T12:00:00+00:00"


def tournament(row_id, weapon="Foil", category="Senior", gender="Women", end_date="2025-01-01"):
    return {
        "id": row_id,
        "weapon": weapon,
        "category": category,
        "gender": gender,
        "end_date": end_date,
    }


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


def test_build_fencer_stat_rows_counts_wins_losses_touches_and_streaks():
    from compute_fencer_stats import build_fencer_stat_rows

    tournaments = {
        "foil-1": tournament("foil-1", end_date="2025-01-10"),
        "foil-2": tournament("foil-2", end_date="2025-02-10"),
        "foil-3": tournament("foil-3", end_date="2025-03-10"),
    }
    bouts = [
        bout("bout-1", "foil-1", ALICE_FOIL, BOB, 15, 10),
        bout("bout-2", "foil-2", BOB, ALICE_FOIL, "15", "14"),
        bout("bout-3", "foil-3", ALICE_FOIL, CAROL, 15, 8),
    ]

    rows, counters = build_fencer_stat_rows(bouts, tournaments, now=NOW)
    by_identity = {row["identity_id"]: row for row in rows}

    assert counters == {
        "bouts_read": 3,
        "completed_bouts": 3,
        "rows_built": 3,
        "skipped_missing_fencer": 0,
        "skipped_missing_score": 0,
        "skipped_missing_dimensions": 0,
        "skipped_self_bout": 0,
        "skipped_no_winner": 0,
    }
    assert by_identity[ALICE_FOIL] == {
        "identity_id": ALICE_FOIL,
        "weapon": "Foil",
        "category": "Women's Senior",
        "total_bouts": 3,
        "wins": 2,
        "losses": 1,
        "touches_scored": 44,
        "touches_received": 33,
        "win_pct": 66.67,
        "current_streak": 1,
        "longest_win_streak": 1,
        "last_bout_at": "2025-03-10",
        "updated_at": NOW,
    }
    assert by_identity[BOB]["total_bouts"] == 2
    assert by_identity[BOB]["wins"] == 1
    assert by_identity[BOB]["losses"] == 1
    assert by_identity[BOB]["current_streak"] == 1
    assert by_identity[BOB]["longest_win_streak"] == 1
    assert by_identity[CAROL]["current_streak"] == -1
    assert by_identity[CAROL]["longest_win_streak"] == 0


def test_build_fencer_stat_rows_skips_incomplete_bouts_with_counters():
    from compute_fencer_stats import build_fencer_stat_rows

    tournaments = {
        "foil-1": tournament("foil-1"),
        "missing-category": tournament("missing-category", category=None, gender=None),
    }
    bouts = [
        bout("complete", "foil-1", ALICE_FOIL, BOB, 15, 9),
        bout("missing-score-a", "foil-1", ALICE_FOIL, BOB, None, 9),
        bout("missing-score-b", "foil-1", ALICE_FOIL, BOB, 15, None),
        bout("missing-fencer", "foil-1", ALICE_FOIL, None, 15, 9),
        bout("self-bout", "foil-1", ALICE_FOIL, ALICE_FOIL, 15, 9),
        bout("missing-dimensions", "missing-category", ALICE_FOIL, BOB, 15, 9, weapon=None, category=None),
        bout("tie-without-winner", "foil-1", ALICE_FOIL, BOB, 14, 14),
    ]

    rows, counters = build_fencer_stat_rows(bouts, tournaments, now=NOW)

    assert len(rows) == 2
    assert counters == {
        "bouts_read": 7,
        "completed_bouts": 1,
        "rows_built": 2,
        "skipped_missing_fencer": 1,
        "skipped_missing_score": 2,
        "skipped_missing_dimensions": 1,
        "skipped_self_bout": 1,
        "skipped_no_winner": 1,
    }


def test_build_fencer_stat_rows_handles_empty_input():
    from compute_fencer_stats import build_fencer_stat_rows

    rows, counters = build_fencer_stat_rows([], {}, now=NOW)

    assert rows == []
    assert counters == {
        "bouts_read": 0,
        "completed_bouts": 0,
        "rows_built": 0,
        "skipped_missing_fencer": 0,
        "skipped_missing_score": 0,
        "skipped_missing_dimensions": 0,
        "skipped_self_bout": 0,
        "skipped_no_winner": 0,
    }


def test_identity_rows_collapse_duplicate_fencers_for_same_weapon_category():
    from compute_fencer_stats import build_fencer_stat_rows

    tournaments = {
        "foil-1": tournament("foil-1", end_date="2025-01-10"),
        "foil-2": tournament("foil-2", end_date="2025-02-10"),
    }
    bouts = [
        bout("bout-1", "foil-1", ALICE_FOIL, BOB, 15, 9),
        bout("bout-2", "foil-2", ALICE_EPEE, BOB, 15, 10),
    ]
    identity_map = {
        ALICE_FOIL: ALICE_IDENTITY,
        ALICE_EPEE: ALICE_IDENTITY,
    }

    rows, counters = build_fencer_stat_rows(bouts, tournaments, identity_map=identity_map, now=NOW)
    by_key = {(row["identity_id"], row["weapon"], row["category"]): row for row in rows}

    alice = by_key[(ALICE_IDENTITY, "Foil", "Women's Senior")]
    assert counters["completed_bouts"] == 2
    assert alice["total_bouts"] == 2
    assert alice["wins"] == 2
    assert alice["touches_scored"] == 30
    assert alice["touches_received"] == 19
    assert alice["longest_win_streak"] == 2
    assert alice["current_streak"] == 2
    assert (ALICE_EPEE, "Foil", "Women's Senior") not in by_key


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


def test_compute_fencer_stats_fetches_bouts_and_upserts_idempotent_conflict_key():
    from compute_fencer_stats import compute_fencer_stats

    client = FakeSupabase(
        {
            "fs_bouts": [
                {
                    "id": "bout-1",
                    "tournament_id": "foil-1",
                    "fencer_a_id": ALICE_FOIL,
                    "fencer_b_id": BOB,
                    "score_a": 15,
                    "score_b": 9,
                },
                {
                    "id": "bout-2",
                    "tournament_id": "foil-2",
                    "fencer_a_id": ALICE_EPEE,
                    "fencer_b_id": BOB,
                    "score_a": 15,
                    "score_b": 10,
                },
                {
                    "id": "incomplete",
                    "tournament_id": "foil-1",
                    "fencer_a_id": ALICE_FOIL,
                    "fencer_b_id": BOB,
                    "score_a": None,
                    "score_b": 9,
                },
            ],
            "fs_tournaments": [
                tournament("foil-1", end_date="2025-01-10"),
                tournament("foil-2", end_date="2025-02-10"),
            ],
            "fs_fencer_identities": [
                {
                    "id": ALICE_IDENTITY,
                    "fs_fencer_row_ids": [ALICE_FOIL, ALICE_EPEE],
                }
            ],
        }
    )

    summary = compute_fencer_stats(client=client, page_size=2, log_run=False, update_state=False, now=NOW)

    assert summary["bouts_read"] == 3
    assert summary["completed_bouts"] == 2
    assert summary["skipped_missing_score"] == 1
    assert summary["stats_rows"] == 2
    assert summary["written"] == 2
    assert summary["identity_rows"] == 1
    assert ("fs_bouts", "id,tournament_id,fencer_a,fencer_b,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,weapon,category,gender,bout_date,meeting_date,date,played_at,completed_at") in client.selects
    assert ("fs_tournaments", "id,weapon,gender,category,end_date,date,start_date") in client.selects
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_fencer_stats"
    assert upsert["on_conflict"] == "identity_id,weapon,category"
    by_identity = {row["identity_id"]: row for row in upsert["rows"]}
    assert by_identity[ALICE_IDENTITY]["total_bouts"] == 2
    assert by_identity[ALICE_IDENTITY]["wins"] == 2
    assert by_identity[BOB]["losses"] == 2
    assert all("win_pct" not in row for row in upsert["rows"])


def test_compute_fencer_stats_empty_database_does_not_upsert():
    from compute_fencer_stats import compute_fencer_stats

    client = FakeSupabase(
        {
            "fs_bouts": [],
            "fs_tournaments": [],
            "fs_fencer_identities": [],
        }
    )

    summary = compute_fencer_stats(client=client, log_run=False, update_state=False, now=NOW)

    assert summary["bouts_read"] == 0
    assert summary["stats_rows"] == 0
    assert summary["written"] == 0
    assert client.upserts == []

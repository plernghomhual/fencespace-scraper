import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

ALICE = "00000000-0000-0000-0000-000000000001"
ALICE_ALT = "00000000-0000-0000-0000-000000000011"
BOB = "00000000-0000-0000-0000-000000000002"
CAROL = "00000000-0000-0000-0000-000000000003"
DAN = "00000000-0000-0000-0000-000000000004"

ALICE_IDENTITY = "10000000-0000-0000-0000-000000000001"
BOB_IDENTITY = "10000000-0000-0000-0000-000000000002"

NOW = "2026-06-02T12:00:00+00:00"


def identity_rows():
    return [
        {
            "id": ALICE_IDENTITY,
            "canonical_name": "Alice Example",
            "country": "USA",
            "fs_fencer_row_ids": [ALICE_ALT, ALICE],
        },
        {
            "id": BOB_IDENTITY,
            "canonical_name": "Bob Example",
            "country": "ITA",
            "fs_fencer_row_ids": [BOB],
        },
    ]


def fencer_rows():
    return [
        {"id": ALICE, "name": "Alice Example", "country": "USA"},
        {"id": ALICE_ALT, "name": "Alice Example", "country": "USA"},
        {"id": BOB, "name": "Bob Example", "country": "ITA"},
        {"id": CAROL, "name": "Carol Example", "country": "FRA"},
        {"id": DAN, "name": "Dan Example", "country": "KOR"},
    ]


def test_build_h2h_graph_rows_dedupes_identities_and_skips_bad_bouts():
    from compute_h2h_graph import build_h2h_graph_rows

    bouts = [
        {
            "id": "bout-1",
            "tournament_id": "t1",
            "fencer_a": ALICE,
            "fencer_b": BOB,
            "score_a": 5,
            "score_b": 3,
        },
        {
            "id": "bout-1",
            "tournament_id": "t1",
            "fencer_a": ALICE,
            "fencer_b": BOB,
            "score_a": 5,
            "score_b": 3,
        },
        {
            "id": "bout-2",
            "tournament_id": "t1",
            "fencer_a": ALICE_ALT,
            "fencer_b": BOB,
            "score_a": 2,
            "score_b": 5,
        },
        {
            "source_key": "semi-1",
            "tournament_id": "t1",
            "fencer_a": BOB,
            "fencer_b": ALICE,
            "score_a": 5,
            "score_b": 4,
        },
        {
            "id": "missing-fencer",
            "tournament_id": "t1",
            "fencer_a": None,
            "fencer_b": BOB,
            "score_a": 5,
            "score_b": 1,
        },
        {
            "id": "same-identity",
            "tournament_id": "t1",
            "fencer_a": ALICE,
            "fencer_b": ALICE_ALT,
            "score_a": 5,
            "score_b": 4,
        },
        {
            "id": "tie",
            "tournament_id": "t1",
            "fencer_a": ALICE,
            "fencer_b": BOB,
            "score_a": 5,
            "score_b": 5,
        },
    ]
    tournaments = [{"id": "t1", "weapon": "foil"}]

    rows, skipped = build_h2h_graph_rows(
        bouts,
        tournaments,
        identity_rows(),
        fencer_rows(),
        updated_at=NOW,
    )

    assert skipped == {
        "duplicate_bouts": 1,
        "incomplete_bouts": 1,
        "missing_fencers": 1,
        "missing_weapon": 0,
        "self_bouts": 1,
    }
    assert len(rows) == 2
    by_key = {(row["fencer_key"], row["weapon"]): row for row in rows}

    alice = by_key[(ALICE_IDENTITY, "Foil")]
    assert alice == {
        "fencer_key": ALICE_IDENTITY,
        "identity_id": ALICE_IDENTITY,
        "fencer_id": ALICE,
        "canonical_name": "Alice Example",
        "country": "USA",
        "weapon": "Foil",
        "degree": 1,
        "weighted_degree": 3,
        "total_bouts": 3,
        "wins": 1,
        "losses": 2,
        "strength": 3,
        "degree_centrality": 1.0,
        "weighted_degree_centrality": 1.0,
        "opponents": [
            {
                "opponent_key": BOB_IDENTITY,
                "opponent_identity_id": BOB_IDENTITY,
                "opponent_fencer_id": BOB,
                "opponent_name": "Bob Example",
                "opponent_country": "ITA",
                "weapon": "Foil",
                "bouts": 3,
                "wins": 1,
                "losses": 2,
                "strength": 3,
                "win_rate": 0.3333,
            }
        ],
        "updated_at": NOW,
    }

    bob = by_key[(BOB_IDENTITY, "Foil")]
    assert bob["wins"] == 2
    assert bob["losses"] == 1
    assert bob["opponents"][0]["opponent_key"] == ALICE_IDENTITY
    assert bob["opponents"][0]["win_rate"] == 0.6667


def test_build_h2h_graph_rows_handles_disconnected_components_and_bounds():
    from compute_h2h_graph import build_h2h_graph_rows

    bouts = [
        {
            "id": "a-b",
            "tournament_id": "t1",
            "fencer_a": ALICE,
            "fencer_b": BOB,
            "score_a": 5,
            "score_b": 3,
        },
        {
            "id": "c-d",
            "tournament_id": "t1",
            "fencer_a": CAROL,
            "fencer_b": DAN,
            "score_a": 1,
            "score_b": 5,
        },
    ]

    rows, skipped = build_h2h_graph_rows(
        bouts,
        [{"id": "t1", "weapon": "Epee"}],
        identity_rows(),
        fencer_rows(),
        updated_at=NOW,
        max_nodes=3,
        max_opponents=1,
    )

    assert sum(skipped.values()) == 0
    assert len(rows) == 3
    assert {row["degree_centrality"] for row in rows} == {0.3333}
    assert all(len(row["opponents"]) <= 1 for row in rows)
    assert rows == sorted(
        rows,
        key=lambda row: (
            row["weapon"],
            -row["weighted_degree"],
            -row["degree"],
            row["fencer_key"],
        ),
    )


def test_build_h2h_graph_rows_handles_empty_graph():
    from compute_h2h_graph import build_h2h_graph_rows

    rows, skipped = build_h2h_graph_rows([], [], [], [], updated_at=NOW)

    assert rows == []
    assert skipped == {
        "duplicate_bouts": 0,
        "incomplete_bouts": 0,
        "missing_fencers": 0,
        "missing_weapon": 0,
        "self_bouts": 0,
    }


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = None
        self.columns = None
        self.start = 0
        self.end = None
        self.pending_rows = None
        self.pending_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.pending_rows = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.table_name,
                    "rows": self.pending_rows,
                    "on_conflict": self.pending_conflict,
                }
            )
            return FakeResult(self.pending_rows)

        rows = list(self.client.tables.get(self.table_name, []))
        end = self.end + 1 if self.end is not None else None
        return FakeResult(rows[self.start : end])


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "fs_bouts": [
                {
                    "id": "bout-1",
                    "tournament_id": "t1",
                    "fencer_a": ALICE,
                    "fencer_b": BOB,
                    "score_a": 5,
                    "score_b": 3,
                },
                {
                    "id": "bout-2",
                    "tournament_id": "t1",
                    "fencer_a": CAROL,
                    "fencer_b": DAN,
                    "score_a": 5,
                    "score_b": 4,
                },
            ],
            "fs_tournaments": [{"id": "t1", "weapon": "Sabre"}],
            "fs_fencer_identities": identity_rows(),
            "fs_fencers": fencer_rows(),
        }
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_compute_h2h_graph_fetches_inputs_and_upserts_bounded_rows():
    from compute_h2h_graph import compute_h2h_graph

    client = FakeSupabase()

    summary = compute_h2h_graph(
        client=client,
        page_size=2,
        max_nodes=2,
        max_opponents=1,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary == {
        "bouts_read": 2,
        "tournaments_read": 1,
        "identity_rows": 2,
        "fencers_read": 5,
        "graph_rows": 2,
        "written": 2,
        "skipped": 0,
        "duplicate_bouts": 0,
        "incomplete_bouts": 0,
        "missing_fencers": 0,
        "missing_weapon": 0,
        "self_bouts": 0,
    }
    assert ("fs_bouts", client.selects[0][1]) in client.selects
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_h2h_graph"
    assert upsert["on_conflict"] == "fencer_key,weapon"
    assert len(upsert["rows"]) == 2
    assert all(len(row["opponents"]) <= 1 for row in upsert["rows"])


def test_h2h_graph_migration_defines_bounded_adjacency_table():
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "20260602_h2h_graph.sql"
    )

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_h2h_graph" in normalized
    assert "fencer_key text not null" in normalized
    assert "identity_id uuid references public.fs_fencer_identities(id)" in normalized
    assert "fencer_id uuid references public.fs_fencers(id)" in normalized
    assert "opponents jsonb not null default '[]'::jsonb" in normalized
    assert "degree_centrality numeric" in normalized
    assert "weighted_degree_centrality numeric" in normalized
    assert "unique (fencer_key, weapon)" in normalized
    assert "array_length" not in normalized
    assert "drop table" not in normalized
    assert "truncate" not in normalized

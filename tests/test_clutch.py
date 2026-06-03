import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ALICE = "00000000-0000-0000-0000-000000000001"
BOB = "00000000-0000-0000-0000-000000000002"
CAROL = "00000000-0000-0000-0000-000000000003"
DAN = "00000000-0000-0000-0000-000000000004"
ERIN = "00000000-0000-0000-0000-000000000005"
NOW = "2026-06-02T12:00:00+00:00"


def individual_tournament(**overrides):
    row = {
        "id": "event-1",
        "name": "Paris Foil World Cup",
        "weapon": "Foil",
        "category": "Senior",
        "gender": "Women's",
    }
    row.update(overrides)
    return row


def result(fencer_id, tournament_id="event-1", rank=1, **overrides):
    row = {
        "tournament_id": tournament_id,
        "fencer_id": fencer_id,
        "rank": rank,
    }
    row.update(overrides)
    return row


def fencer(fencer_id, rank, **overrides):
    row = {
        "id": fencer_id,
        "fie_id": f"fie-{fencer_id[-1]}",
        "name": f"Fencer {fencer_id[-1]}",
        "country": "USA",
        "weapon": "Foil",
        "world_rank": rank,
    }
    row.update(overrides)
    return row


def bout(
    fencer_a,
    fencer_b,
    score_a,
    score_b,
    round_name,
    tournament_id="event-1",
    **overrides,
):
    row = {
        "tournament_id": tournament_id,
        "fencer_a_id": fencer_a,
        "fencer_b_id": fencer_b,
        "score_a": score_a,
        "score_b": score_b,
        "round": round_name,
    }
    row.update(overrides)
    return row


def test_build_clutch_rows_scores_expected_vs_actual_delta():
    from compute_clutch import build_clutch_rows

    results = [
        result(ALICE, rank=3),
        result(BOB, rank=9),
        result(CAROL, rank=17),
        result(DAN, rank=32),
    ]
    fencers = [
        fencer(ALICE, 5),
        fencer(BOB, 20),
        fencer(CAROL, 50),
        fencer(DAN, 80),
    ]
    bouts = [
        bout(ALICE, BOB, 5, 2, "Pool 1"),
        bout(ALICE, CAROL, 5, 3, "Pool 1"),
        bout(ALICE, DAN, 4, 5, "Pool 1"),
        bout(ALICE, BOB, 15, 9, "Tableau of 64"),
        bout(ALICE, CAROL, 10, 15, "Tableau of 32"),
    ]
    performance_rows = [
        {
            "fencer_id": ALICE,
            "weapon": "Foil",
            "competitions_count": 8,
            "avg_delta": 10,
            "clutch_score": 10,
        }
    ]

    rows, skips = build_clutch_rows(
        results,
        bouts,
        fencers,
        [individual_tournament()],
        performance_rows,
        updated_at=NOW,
    )

    assert all(skip["fencer_id"] != ALICE for skip in skips)
    assert len(rows) == 1
    row = rows[0]
    assert row["fencer_id"] == ALICE
    assert row["fie_id"] == "fie-1"
    assert row["fencer_name"] == "Fencer 1"
    assert row["tournament_id"] == "event-1"
    assert row["event_name"] == "Paris Foil World Cup"
    assert row["pool_performance"] == 0.6333
    assert row["elimination_performance"] == 0.5167
    assert row["expected_result"] == 0.74
    assert row["actual_result"] == 0.5167
    assert row["delta"] == -0.2233
    assert row["confidence"] == 0.6133
    assert row["pool_bouts"] == 3
    assert row["elimination_bouts"] == 2
    assert row["rank_source"] == "world_rank"
    assert row["updated_at"] == NOW
    assert row["evidence"]["formula"] == (
        "expected_result = weighted average of pool_performance (60%), "
        "rank_percentile (30%), historical_performance (10%); "
        "delta = actual_result - expected_result"
    )


def test_build_clutch_rows_skips_when_pool_or_elimination_evidence_is_insufficient():
    from compute_clutch import build_clutch_rows

    results = [
        result(ALICE, tournament_id="event-alice"),
        result(BOB, tournament_id="event-bob"),
    ]
    fencers = [fencer(ALICE, 5), fencer(BOB, 20), fencer(CAROL, 50), fencer(DAN, 80)]
    bouts = [
        bout(ALICE, BOB, 5, 4, "Pool 1", tournament_id="event-alice"),
        bout(ALICE, CAROL, 5, 4, "Pool 1", tournament_id="event-alice"),
        bout(ALICE, BOB, 15, 14, "Tableau of 64", tournament_id="event-alice"),
        bout(BOB, ALICE, 5, 4, "Pool 1", tournament_id="event-bob"),
        bout(BOB, CAROL, 5, 4, "Pool 1", tournament_id="event-bob"),
        bout(BOB, DAN, 5, 4, "Pool 1", tournament_id="event-bob"),
    ]

    rows, skips = build_clutch_rows(
        results,
        bouts,
        fencers,
        [
            individual_tournament(id="event-alice"),
            individual_tournament(id="event-bob"),
        ],
        [],
        updated_at=NOW,
    )

    assert rows == []
    reasons = {(skip["fencer_id"], skip["reason"]) for skip in skips}
    assert (ALICE, "insufficient_pool_bouts") in reasons
    assert (BOB, "insufficient_elimination_bouts") in reasons


def test_build_clutch_rows_handles_byes_withdrawals_team_events_and_missing_scores():
    from compute_clutch import build_clutch_rows

    results = [
        result(ALICE, tournament_id="team-event"),
        result(BOB, tournament_id="withdrawal-event", status="withdrawn"),
        result(CAROL, tournament_id="missing-score-event"),
        result(DAN, tournament_id="missing-score-event"),
    ]
    fencers = [
        fencer(ALICE, 1),
        fencer(BOB, 2),
        fencer(CAROL, 3),
        fencer(DAN, 4),
        fencer(ERIN, 5),
    ]
    tournaments = [
        individual_tournament(id="team-event", name="Senior Men's Foil Team", category="Senior Team"),
        individual_tournament(id="withdrawal-event", name="Individual Foil"),
        individual_tournament(id="missing-score-event", name="Individual Foil"),
    ]
    bouts = [
        bout(CAROL, DAN, 5, 2, "Pool 1", tournament_id="missing-score-event"),
        bout(CAROL, ERIN, 5, 3, "Pool 1", tournament_id="missing-score-event"),
        bout(CAROL, ALICE, 4, 5, "Pool 1", tournament_id="missing-score-event"),
        bout(CAROL, None, None, None, "Tableau of 64", tournament_id="missing-score-event", is_bye=True),
        bout(CAROL, DAN, None, 15, "Tableau of 32", tournament_id="missing-score-event"),
    ]

    rows, skips = build_clutch_rows(
        results,
        bouts,
        fencers,
        tournaments,
        [],
        updated_at=NOW,
    )

    assert rows == []
    reasons = {(skip["fencer_id"], skip["tournament_id"], skip["reason"]) for skip in skips}
    assert (ALICE, "team-event", "team_event") in reasons
    assert (BOB, "withdrawal-event", "withdrawal") in reasons
    assert (CAROL, "missing-score-event", "bye") in reasons
    assert (CAROL, "missing-score-event", "missing_score") in reasons
    assert (CAROL, "missing-score-event", "insufficient_elimination_bouts") in reasons


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.columns = None
        self.start = 0
        self.end = None
        self.pending_rows = None
        self.pending_conflict = None

    def select(self, columns):
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, rows, on_conflict):
        self.pending_rows = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.pending_rows is not None:
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.pending_rows,
                    "on_conflict": self.pending_conflict,
                }
            )
            return FakeResult(self.pending_rows)

        rows = self.client.tables[self.name]
        end = self.end + 1 if self.end is not None else None
        return FakeResult(rows[self.start:end])


class FakeClient:
    def __init__(self):
        self.tables = {
            "fs_results": [
                result(ALICE, rank=3),
                result(BOB, rank=9),
                result(CAROL, rank=17),
                result(DAN, rank=32),
            ],
            "fs_bouts": [
                bout(ALICE, BOB, 5, 2, "Pool 1"),
                bout(ALICE, CAROL, 5, 3, "Pool 1"),
                bout(ALICE, DAN, 4, 5, "Pool 1"),
                bout(ALICE, BOB, 15, 9, "Tableau of 64"),
                bout(ALICE, CAROL, 10, 15, "Tableau of 32"),
            ],
            "fs_fencers": [
                fencer(ALICE, 5),
                fencer(BOB, 20),
                fencer(CAROL, 50),
                fencer(DAN, 80),
            ],
            "fs_tournaments": [individual_tournament()],
            "fs_fencer_performance_analysis": [
                {
                    "fencer_id": ALICE,
                    "weapon": "Foil",
                    "competitions_count": 8,
                    "avg_delta": 10,
                    "clutch_score": 10,
                }
            ],
        }
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_clutch_fetches_pages_and_upserts_clutch_rows():
    from compute_clutch import compute_clutch

    client = FakeClient()

    summary = compute_clutch(
        client=client,
        page_size=3,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary == {
        "results_read": 4,
        "bouts_read": 5,
        "fencers_read": 4,
        "tournaments_read": 1,
        "performance_rows_read": 1,
        "clutch_rows": 1,
        "written": 1,
        "skipped": 3,
    }
    assert client.selects == [
        ("fs_results", "tournament_id,fencer_id,rank,placement,seed,entry_seed,pool_rank,status,weapon,category"),
        ("fs_results", "tournament_id,fencer_id,rank,placement,seed,entry_seed,pool_rank,status,weapon,category"),
        ("fs_bouts", "tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,round,is_bye,status"),
        ("fs_bouts", "tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,round,is_bye,status"),
        ("fs_fencers", "id,fie_id,name,country,world_rank,national_rank,weapon,category"),
        ("fs_fencers", "id,fie_id,name,country,world_rank,national_rank,weapon,category"),
        ("fs_tournaments", "id,name,weapon,gender,category,season,type"),
        ("fs_fencer_performance_analysis", "fencer_id,weapon,competitions_count,avg_delta,clutch_score"),
    ]
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_fencer_clutch_metrics"
    assert upsert["on_conflict"] == "fencer_id,tournament_id"
    assert upsert["rows"][0]["fencer_id"] == ALICE
    assert upsert["rows"][0]["delta"] == -0.2233


def test_clutch_migration_defines_table_shape_and_constraints():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_clutch.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencer_clutch_metrics" in normalized
    assert "fencer_id uuid not null references public.fs_fencers(id)" in normalized
    assert "tournament_id uuid not null references public.fs_tournaments(id)" in normalized
    assert "event_name text not null" in normalized
    assert "pool_performance numeric(10,4) not null" in normalized
    assert "elimination_performance numeric(10,4) not null" in normalized
    assert "expected_result numeric(10,4) not null" in normalized
    assert "actual_result numeric(10,4) not null" in normalized
    assert "delta numeric(10,4) not null" in normalized
    assert "confidence numeric(6,4) not null" in normalized
    assert "evidence jsonb not null default '{}'::jsonb" in normalized
    assert "unique (fencer_id, tournament_id)" in normalized
    assert "alter table public.fs_fencer_clutch_metrics enable row level security" in normalized

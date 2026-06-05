from pathlib import Path
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"
WEEK_START = "2026-05-25"
ALICE = "00000000-0000-0000-0000-0000000000a1"
ALICE_ALT = "00000000-0000-0000-0000-0000000000a2"
BOB = "00000000-0000-0000-0000-0000000000b1"
CAROL = "00000000-0000-0000-0000-0000000000c1"
DANA = "00000000-0000-0000-0000-0000000000d1"
ERIN = "00000000-0000-0000-0000-0000000000e1"


def tournament(tournament_id, date_value, **overrides):
    row = {
        "id": tournament_id,
        "name": f"{tournament_id} World Cup",
        "weapon": "Foil",
        "category": "Senior",
        "gender": "Women",
        "end_date": date_value,
        "status": "completed",
        "has_results": True,
    }
    row.update(overrides)
    return row


def result(fencer_id, tournament_id, rank, **overrides):
    row = {
        "id": f"{tournament_id}:{fencer_id}",
        "tournament_id": tournament_id,
        "fencer_id": fencer_id,
        "rank": rank,
    }
    row.update(overrides)
    return row


def test_build_trending_rows_scores_rank_jumps_medals_and_missing_social_data():
    from compute_trending_fencers import build_trending_rows, build_identity_indexes

    identity_indexes = build_identity_indexes(
        [
            {
                "canonical_id": ALICE,
                "fs_fencer_row_ids": [ALICE, ALICE_ALT],
                "fie_ids": ["1001"],
            }
        ],
        [{"id": ALICE, "fie_id": "1001"}, {"id": ALICE_ALT, "fie_id": "1001"}],
    )
    rows, summary = build_trending_rows(
        results=[
            result(ALICE_ALT, "paris", 1, medal="Gold", seed=12),
            result(BOB, "paris", 2, medal="Silver", seed=3),
            result(CAROL, "seoul", 8),
            result(DANA, "old", 1, medal="Gold"),
            result(None, "paris", 1, medal="Gold"),
        ],
        tournaments=[
            tournament("paris", "2026-05-27"),
            tournament("seoul", "2026-05-30"),
            tournament("old", "2026-05-20"),
        ],
        rank_trends=[
            {"fie_fencer_id": "1001", "rank_change": 8, "trend_direction": "up", "season": 2026},
            {"fie_fencer_id": BOB, "rank_change": -2, "trend_direction": "down", "season": 2026},
            {"fie_fencer_id": CAROL, "rank_change": 10, "trend_direction": "up", "season": 2026},
        ],
        form_rows=[
            {"fencer_id": ALICE_ALT, "form_score": 85, "trend_direction": "improving"},
            {"fencer_id": BOB, "form_score": 70, "trend_direction": "stable"},
            {"fencer_id": CAROL, "form_score": 75, "trend_direction": "improving"},
        ],
        social_rows=[
            {
                "fencer_id": BOB,
                "mention_count": 500,
                "mention_rank": 1,
                "is_stale": False,
                "platform": "instagram",
                "normalized_handle": "bob_fencer",
            }
        ],
        identity_indexes=identity_indexes,
        week_start=WEEK_START,
        updated_at=NOW,
    )

    by_fencer = {row["fencer_id"]: row for row in rows}

    assert summary["recent_results_used"] == 3
    assert summary["skipped_missing_fencer"] == 1
    assert summary["skipped_outside_week"] == 1
    assert list(by_fencer) == [ALICE, BOB, CAROL]

    alice = by_fencer[ALICE]
    assert alice["week_start"] == WEEK_START
    assert alice["rank_delta"] == 8
    assert alice["recent_results_score"] == 100.0
    assert alice["social_score"] == 0.0
    assert alice["score"] == 110.0
    assert any("gold medal" in reason for reason in alice["reasons"])
    assert any("seed upset +11" in reason for reason in alice["reasons"])
    assert any("rank jump +8" in reason for reason in alice["reasons"])
    assert any("social data unavailable" in reason for reason in alice["reasons"])

    bob = by_fencer[BOB]
    assert bob["rank_delta"] == -2
    assert bob["recent_results_score"] == 78.5
    assert bob["social_score"] == 5.0
    assert bob["score"] == 83.5
    assert any("silver medal" in reason for reason in bob["reasons"])
    assert any("social mentions 500" in reason for reason in bob["reasons"])

    carol = by_fencer[CAROL]
    assert carol["rank_delta"] == 10
    assert carol["score"] == 59.75

    assert rows[0]["fencer_id"] == ALICE
    assert rows[1]["fencer_id"] == BOB
    assert rows[2]["fencer_id"] == CAROL


def test_tie_breaking_is_deterministic_when_scores_match():
    from compute_trending_fencers import build_trending_rows

    rows, summary = build_trending_rows(
        results=[
            result(ERIN, "tie-event", 4),
            result(DANA, "tie-event", 4),
        ],
        tournaments=[tournament("tie-event", "2026-05-26")],
        rank_trends=[],
        form_rows=[],
        social_rows=[],
        week_start=WEEK_START,
        updated_at=NOW,
    )

    assert summary["recent_results_used"] == 2
    assert [row["fencer_id"] for row in rows] == [DANA, ERIN]
    assert rows[0]["score"] == rows[1]["score"]


def test_rows_are_skipped_when_weekly_evidence_is_insufficient():
    from compute_trending_fencers import build_trending_rows

    rows, summary = build_trending_rows(
        results=[
            result(ALICE, "no-date", 1, medal="Gold"),
            result(BOB, "missing-rank", None),
            result(CAROL, "outside", 1, medal="Gold"),
            result(None, "valid", 1, medal="Gold"),
            result(DANA, "valid", 3),
        ],
        tournaments=[
            tournament("no-date", None),
            tournament("missing-rank", "2026-05-26"),
            tournament("outside", "2026-05-18"),
            tournament("valid", "2026-05-26"),
        ],
        rank_trends=[{"fie_fencer_id": ALICE, "rank_change": 20, "season": 2026}],
        form_rows=[{"fencer_id": ALICE, "form_score": 100, "trend_direction": "improving"}],
        social_rows=[{"fencer_id": ALICE, "mention_count": 999, "mention_rank": 1}],
        week_start=WEEK_START,
        updated_at=NOW,
    )

    assert [row["fencer_id"] for row in rows] == [DANA]
    assert summary["skipped_missing_date"] == 1
    assert summary["skipped_insufficient_result"] == 1
    assert summary["skipped_outside_week"] == 1
    assert summary["skipped_missing_fencer"] == 1


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.columns = None
        self.range_start = 0
        self.range_end = None
        self.limit_count = None
        self.pending_rows = None
        self.pending_conflict = None

    def select(self, columns):
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def limit(self, count):
        self.limit_count = count
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
            return FakeResult([])
        if self.name not in self.client.tables:
            raise RuntimeError(f"missing table {self.name}")
        rows = list(self.client.tables[self.name])
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        else:
            end = self.range_end + 1 if self.range_end is not None else None
            rows = rows[self.range_start : end]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_trending_fencers_upserts_weekly_rows_idempotently():
    from compute_trending_fencers import compute_trending_fencers

    client = FakeSupabase(
        {
            "fs_trending_fencers": [],
            "fs_results": [
                result(ALICE_ALT, "paris", 1, medal="Gold", seed=9),
                result(BOB, "paris", 9),
            ],
            "fs_tournaments": [tournament("paris", "2026-05-27")],
            "fs_fencer_identities": [
                {
                    "canonical_id": ALICE,
                    "fs_fencer_row_ids": [ALICE, ALICE_ALT],
                    "fie_ids": ["1001"],
                }
            ],
            "fs_fencers": [{"id": ALICE, "fie_id": "1001"}, {"id": ALICE_ALT, "fie_id": "1001"}],
            "fs_rankings_trends": [{"fie_fencer_id": "1001", "rank_change": 5, "season": 2026}],
            "fs_fencer_form": [{"fencer_id": ALICE_ALT, "form_score": 90, "trend_direction": "improving"}],
            "fs_fencer_social_leaderboard": [],
        }
    )

    first = compute_trending_fencers(
        client=client,
        week_start=WEEK_START,
        now=NOW,
        page_size=2,
        log_run=False,
        update_state=False,
    )
    second = compute_trending_fencers(
        client=client,
        week_start=WEEK_START,
        now=NOW,
        page_size=2,
        log_run=False,
        update_state=False,
    )

    assert first == second
    assert first["leaderboard_rows"] == 2
    assert first["written"] == 2
    assert len(client.upserts) == 2
    assert client.upserts[0] == client.upserts[1]
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_trending_fencers"
    assert upsert["on_conflict"] == "fencer_id,week_start"
    assert upsert["rows"][0]["fencer_id"] == ALICE
    assert upsert["rows"][0]["week_start"] == WEEK_START
    assert ("fs_trending_fencers", "fencer_id") in client.selects
    assert ("fs_results", "id,tournament_id,fencer_id,rank,placement,medal,seed,entry_seed,expected_rank,world_rank,weapon,category,gender") in client.selects
    assert ("fs_fencer_social_leaderboard", "fencer_id,mention_count,mention_rank,is_stale,platform,normalized_handle,computed_at") in client.selects


def test_trending_fencers_migration_defines_weekly_table_and_constraints():
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "20260602_trending_fencers.sql"
    )

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_trending_fencers" in normalized
    assert "fencer_id uuid not null references public.fs_fencers(id)" in normalized
    assert "week_start date not null" in normalized
    assert "score numeric(8,2) not null default 0" in normalized
    assert "rank_delta integer" in normalized
    assert "recent_results_score numeric(8,2) not null default 0" in normalized
    assert "social_score numeric(8,2) not null default 0" in normalized
    assert "reasons jsonb not null default '[]'" in normalized
    assert "updated_at timestamptz not null default now()" in normalized
    assert "primary key (fencer_id, week_start)" in normalized
    assert "check (score >= 0)" in normalized
    assert "check (social_score >= 0 and social_score <= 5)" in normalized
    assert "jsonb_typeof(reasons) = 'array'" in normalized
    assert "fs_trending_fencers_week_score_idx" in normalized
    assert "alter table public.fs_trending_fencers enable row level security" in normalized

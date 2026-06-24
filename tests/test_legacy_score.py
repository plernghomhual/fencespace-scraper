import os
import sys
from pathlib import Path
from typing import Any, cast

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ALICE_IDENTITY = "10000000-0000-0000-0000-000000000001"
ALICE_FOIL = "20000000-0000-0000-0000-000000000001"
ALICE_EPEE = "20000000-0000-0000-0000-000000000002"
BOB_IDENTITY = "10000000-0000-0000-0000-000000000002"
BOB_FOIL = "20000000-0000-0000-0000-000000000003"
NOW = "2026-06-02T12:00:00+00:00"


def test_tier_weights_use_explicit_fields_and_ignore_tournament_names():
    from compute_legacy_score import event_kind, tier_from_tournament, tier_weight

    assert tier_from_tournament({"type": "WCH"}) == "Worlds"
    assert tier_weight({"type": "WCH"}) == pytest.approx(5.0)
    assert tier_from_tournament({"tier": "GP", "type": "individual"}) == "GP"
    assert tier_weight({"tier": "GP", "type": "individual"}) == pytest.approx(4.0)
    assert tier_from_tournament({"competition_type": "WC"}) == "WC"
    assert tier_weight({"competition_type": "WC"}) == pytest.approx(3.0)

    misleading_name = {"type": "NAT", "name": "World Championships Grand Prix"}
    assert tier_from_tournament(misleading_name) == "National"
    assert tier_weight(misleading_name) == pytest.approx(1.0)

    name_only = {"name": "Olympic Games"}
    assert tier_from_tournament(name_only) == "Unclassified"
    assert tier_weight(name_only) == pytest.approx(1.0)

    assert event_kind({"type": "team"}) == "team"
    assert event_kind({"type": "individual"}) == "individual"
    assert event_kind({"tier": "Worlds", "type": "team"}) == "team"


def test_build_legacy_score_rows_groups_identities_dedupes_and_explains_components():
    from compute_legacy_score import build_legacy_score_rows

    identities = [
        {
            "id": ALICE_IDENTITY,
            "canonical_name": "Alice Example",
            "country": "USA",
            "fs_fencer_row_ids": [ALICE_FOIL, ALICE_EPEE],
        },
        {
            "id": BOB_IDENTITY,
            "canonical_name": "Bob Example",
            "country": "USA",
            "fs_fencer_row_ids": [BOB_FOIL],
        },
    ]
    tournaments = {
        "world-individual": {
            "id": "world-individual",
            "tier": "Worlds",
            "type": "individual",
            "season": "2020",
            "start_date": "2020-07-01",
            "name": "World Championships",
        },
        "gp-team": {
            "id": "gp-team",
            "competition_type": "GP",
            "type": "team",
            "season": "2021",
            "start_date": "2021-03-01",
        },
        "national-name-trap": {
            "id": "national-name-trap",
            "type": "NAT",
            "season": "2022",
            "start_date": "2022-01-15",
            "name": "World Championships Grand Prix Invitational",
        },
    }
    results: list[dict[str, Any]] = [
        {
            "id": "r1",
            "tournament_id": "world-individual",
            "fencer_id": ALICE_FOIL,
            "rank": 1,
            "medal": "Gold",
        },
        {
            "id": "r1-duplicate-row",
            "tournament_id": "world-individual",
            "fencer_id": ALICE_EPEE,
            "rank": "1",
            "medal": "gold",
        },
        {
            "id": "r2",
            "tournament_id": "gp-team",
            "fencer_id": ALICE_FOIL,
            "rank": 1,
            "medal": "G",
            "team_id": "usa-team",
        },
        {
            "id": "r3",
            "tournament_id": "national-name-trap",
            "fencer_id": ALICE_EPEE,
            "rank": 6,
            "medal": None,
        },
        {
            "id": "r4",
            "tournament_id": "world-individual",
            "fencer_id": BOB_FOIL,
            "placement": 2,
            "medal": "Silver",
        },
        {
            "id": "orphan",
            "tournament_id": "world-individual",
            "fencer_id": "99999999-0000-0000-0000-000000000999",
            "rank": 3,
            "medal": "Bronze",
        },
    ]

    rows, skipped = build_legacy_score_rows(
        results,
        tournaments,
        identities,
        updated_at=NOW,
    )

    assert skipped == 1
    by_identity = {row["identity_id"]: row for row in rows}

    alice = by_identity[ALICE_IDENTITY]
    assert alice["canonical_name"] == "Alice Example"
    assert alice["country"] == "USA"
    assert alice["legacy_score"] == pytest.approx(104.6)
    assert alice["medal_points"] == pytest.approx(74.0)
    assert alice["result_points"] == pytest.approx(30.6)
    assert alice["competition_count"] == 3
    assert alice["result_count"] == 3
    assert alice["gold_medals"] == 2
    assert alice["silver_medals"] == 0
    assert alice["bronze_medals"] == 0
    assert alice["individual_medals"] == 1
    assert alice["team_medals"] == 1
    assert alice["first_season"] == 2020
    assert alice["last_season"] == 2022
    assert alice["active_span_years"] == 3
    assert alice["updated_at"] == NOW
    assert alice["tier_weights"] == {"GP": 4.0, "National": 1.0, "Worlds": 5.0}
    assert alice["medal_counts"] == {
        "gold": 2,
        "silver": 0,
        "bronze": 0,
        "individual": 1,
        "team": 1,
        "by_tier": {
            "GP": {"gold": 1, "silver": 0, "bronze": 0},
            "Worlds": {"gold": 1, "silver": 0, "bronze": 0},
        },
    }
    assert alice["score_components"]["medal_points"] == pytest.approx(74.0)
    assert alice["score_components"]["result_points"] == pytest.approx(30.6)
    assert alice["score_components"]["duplicate_results_skipped"] == 1
    assert [event["tier"] for event in alice["score_components"]["events"]] == [
        "Worlds",
        "GP",
        "National",
    ]

    bob = by_identity[BOB_IDENTITY]
    assert bob["legacy_score"] == pytest.approx(55.0)
    assert bob["medal_points"] == pytest.approx(40.0)
    assert bob["result_points"] == pytest.approx(15.0)
    assert bob["silver_medals"] == 1


def test_build_legacy_score_rows_returns_empty_rows_for_empty_inputs():
    from compute_legacy_score import build_legacy_score_rows

    rows, skipped = build_legacy_score_rows([], {}, [], updated_at=NOW)

    assert rows == []
    assert skipped == 0


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
            return FakeResult(self.rows)
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_legacy_scores_fetches_tier_fields_and_upserts_by_identity():
    from compute_legacy_score import compute_legacy_scores

    client = FakeSupabase(
        {
            "fs_results": [
                {
                    "id": "r1",
                    "tournament_id": "world-individual",
                    "fencer_id": ALICE_FOIL,
                    "rank": 1,
                    "medal": "Gold",
                }
            ],
            "fs_tournaments": [
                {
                    "id": "world-individual",
                    "tier": "Worlds",
                    "type": "individual",
                    "competition_type": None,
                    "season": "2020",
                    "start_date": "2020-07-01",
                }
            ],
            "fs_fencer_identities": [
                {
                    "id": ALICE_IDENTITY,
                    "canonical_name": "Alice Example",
                    "country": "USA",
                    "fs_fencer_row_ids": [ALICE_FOIL, ALICE_EPEE],
                }
            ],
        }
    )

    summary = compute_legacy_scores(
        client=client,
        page_size=2,
        updated_at=NOW,
        log_run=False,
        update_state=False,
    )

    assert summary == {
        "results_read": 1,
        "tournaments_read": 1,
        "identity_rows": 1,
        "legacy_rows": 1,
        "written": 1,
        "skipped": 0,
    }
    assert (
        "fs_tournaments",
        "id,tier,type,competition_type,competition_tier,season,start_date,end_date,weapon,gender,category",
    ) in client.selects
    assert client.upserts == [
        {
            "table": "fs_fencer_legacy_scores",
            "rows": [
                {
                    **client.upserts[0]["rows"][0],
                    "identity_id": ALICE_IDENTITY,
                    "legacy_score": pytest.approx(70.0),
                }
            ],
            "on_conflict": "identity_id",
        }
    ]


def test_legacy_score_migration_defines_identity_scoped_explainable_storage():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_legacy_score.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencer_legacy_scores" in normalized
    assert "identity_id uuid primary key references public.fs_fencer_identities(id)" in normalized
    assert "on delete cascade" in normalized
    assert "legacy_score numeric" in normalized
    assert "medal_points numeric" in normalized
    assert "result_points numeric" in normalized
    assert "competition_count integer not null default 0" in normalized
    assert "gold_medals integer not null default 0" in normalized
    assert "silver_medals integer not null default 0" in normalized
    assert "bronze_medals integer not null default 0" in normalized
    assert "individual_medals integer not null default 0" in normalized
    assert "team_medals integer not null default 0" in normalized
    assert "score_components jsonb not null default" in normalized
    assert "medal_counts jsonb not null default" in normalized
    assert "tier_weights jsonb not null default" in normalized
    assert "first_season integer" in normalized
    assert "last_season integer" in normalized
    assert "active_span_years integer" in normalized
    assert "updated_at timestamptz not null default" in normalized
    assert "enable row level security" in normalized
    assert "fs_fencer_legacy_scores_score_idx" in normalized

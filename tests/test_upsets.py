import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"
TOURNAMENT_ID = "10000000-0000-4000-8000-000000000001"

F1 = "00000000-0000-4000-8000-000000000001"
F2 = "00000000-0000-4000-8000-000000000002"
F3 = "00000000-0000-4000-8000-000000000003"
F4 = "00000000-0000-4000-8000-000000000004"
F5 = "00000000-0000-4000-8000-000000000005"
F6 = "00000000-0000-4000-8000-000000000006"
F7 = "00000000-0000-4000-8000-000000000007"
F8 = "00000000-0000-4000-8000-000000000008"


def tournament(**overrides):
    row = {
        "id": TOURNAMENT_ID,
        "name": "World Cup Foil",
        "season": 2026,
        "start_date": "2026-01-12",
        "end_date": "2026-01-14",
        "weapon": "Foil",
        "gender": "Men",
        "category": "Senior",
        "type": "World Cup",
        "metadata": {"source_url": "https://fie.org/competitions/2026/123"},
    }
    row.update(overrides)
    return row


def result(fencer_id, placement, **overrides):
    row = {
        "id": f"result-{fencer_id[-2:]}",
        "tournament_id": TOURNAMENT_ID,
        "event_key": "men-foil",
        "fencer_id": fencer_id,
        "fie_fencer_id": fencer_id[-1],
        "name": f"Fencer {fencer_id[-1]}",
        "country": "USA",
        "rank": placement,
        "placement": placement,
        "weapon": "Foil",
        "gender": "Men",
        "category": "Senior",
        "metadata": {"source": "fie-results"},
    }
    row.update(overrides)
    return row


def bracket(
    bracket_id,
    round_name,
    round_order,
    bout_order,
    fencer_a,
    fencer_b,
    score_a,
    score_b,
    winner_id,
    *,
    seed_a=None,
    seed_b=None,
    **overrides,
):
    row = {
        "id": bracket_id,
        "bracket_key": f"{TOURNAMENT_ID}:men-foil:{round_order}:{bout_order}",
        "tournament_id": TOURNAMENT_ID,
        "event_key": "men-foil",
        "weapon": "Foil",
        "gender": "Men",
        "category": "Senior",
        "round_name": round_name,
        "round_order": round_order,
        "bout_order": bout_order,
        "fencer_a_id": fencer_a,
        "fencer_a_name": f"Fencer {fencer_a[-1]}" if fencer_a else None,
        "fencer_a_country": "USA" if fencer_a else None,
        "fencer_b_id": fencer_b,
        "fencer_b_name": f"Fencer {fencer_b[-1]}" if fencer_b else None,
        "fencer_b_country": "USA" if fencer_b else None,
        "score_a": score_a,
        "score_b": score_b,
        "winner_id": winner_id,
        "seed_a": seed_a,
        "seed_b": seed_b,
        "source": "fixture-bracket",
        "metadata": {"source_bout_id": bracket_id},
    }
    row.update(overrides)
    return row


def seeded_brackets():
    return [
        bracket("qf-1", "Tableau of 8", 1, 1, F1, F8, 15, 6, F1, seed_a=1, seed_b=8),
        bracket("qf-2", "Tableau of 8", 1, 2, F4, F5, 15, 14, F4, seed_a=4, seed_b=5),
        bracket("qf-3", "Tableau of 8", 1, 3, F3, F6, 13, 15, F6, seed_a=3, seed_b=6),
        bracket("qf-4", "Tableau of 8", 1, 4, F2, F7, 15, 8, F2, seed_a=2, seed_b=7),
        bracket("sf-1", "Semifinal", 2, 1, F1, F4, 15, 12, F1),
        bracket("sf-2", "Semifinal", 2, 2, F6, F2, 9, 15, F2),
        bracket("final", "Final", 3, 1, F1, F2, 15, 13, F1),
    ]


def seeded_results():
    placements = {F1: 1, F2: 2, F6: 3, F4: 3, F3: 5, F5: 6, F7: 7, F8: 8}
    return [result(fencer_id, placement) for fencer_id, placement in placements.items()]


def test_build_upset_rows_detects_seed_upset_and_lowest_seed_to_medal():
    from compute_upsets import build_upset_rows

    rows, skipped = build_upset_rows(
        [tournament()],
        seeded_brackets(),
        seeded_results(),
        rankings=[],
        updated_at=NOW,
    )

    assert skipped == []
    by_type = {row["upset_type"]: row for row in rows}
    round_upset = by_type["round_upset"]
    assert round_upset["tournament_id"] == TOURNAMENT_ID
    assert round_upset["event_key"] == "men-foil"
    assert round_upset["fencer_id"] == F6
    assert round_upset["opponent_id"] == F3
    assert round_upset["fencer_seed"] == 6
    assert round_upset["opponent_seed"] == 3
    assert round_upset["round_name"] == "Tableau of 8"
    assert round_upset["expected_outcome"] == "higher_seed_expected_to_win"
    assert round_upset["actual_outcome"] == "lower_seed_won"
    assert round_upset["upset_score"] == 3
    assert round_upset["evidence"]["not_derived_from_final_rank"] is True

    medal = by_type["lowest_seed_to_medal"]
    assert medal["fencer_id"] == F6
    assert medal["fencer_seed"] == 6
    assert medal["opponent_id"] is None
    assert medal["actual_outcome"] == "lower_seed_medaled"
    assert medal["upset_score"] == 5
    assert medal["evidence"]["source_result_id"] == "result-06"


def test_build_upset_rows_uses_pre_event_rank_evidence_for_high_rank_defeat():
    from compute_upsets import build_upset_rows

    rows, skipped = build_upset_rows(
        [tournament()],
        [
            bracket(
                "rank-qf",
                "Tableau of 8",
                1,
                1,
                F6,
                F2,
                15,
                10,
                F6,
            )
        ],
        [result(F6, 1, fie_fencer_id="600"), result(F2, 8, fie_fencer_id="200")],
        rankings=[
            {
                "source": "fie",
                "season": 2026,
                "weapon": "Foil",
                "gender": "Men",
                "category": "Senior",
                "fencer_id": F6,
                "fie_fencer_id": "600",
                "rank": 41,
                "scraped_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "source": "fie",
                "season": 2026,
                "weapon": "Foil",
                "gender": "Men",
                "category": "Senior",
                "fencer_id": F2,
                "fie_fencer_id": "200",
                "rank": 4,
                "scraped_at": "2026-01-01T00:00:00+00:00",
            },
        ],
        updated_at=NOW,
    )

    assert skipped == []
    assert [row["upset_type"] for row in rows] == ["high_rank_defeated"]
    row = rows[0]
    assert row["fencer_id"] == F6
    assert row["opponent_id"] == F2
    assert row["fencer_rank"] == 41
    assert row["opponent_rank"] == 4
    assert row["expected_outcome"] == "higher_rank_expected_to_win"
    assert row["actual_outcome"] == "lower_rank_won"
    assert row["upset_score"] == 37
    assert row["evidence"]["fencer_evidence"]["source_table"] == "fs_rankings_history"


def test_build_upset_rows_skips_event_without_seed_or_rank_evidence():
    from compute_upsets import build_upset_rows

    rows, skipped = build_upset_rows(
        [tournament()],
        [
            bracket("qf-no-seed", "Tableau of 8", 1, 1, F6, F2, 15, 10, F6),
        ],
        [result(F6, 1), result(F2, 8)],
        rankings=[],
        updated_at=NOW,
    )

    assert rows == []
    assert skipped == [
        {
            "tournament_id": TOURNAMENT_ID,
            "event_key": "men-foil",
            "reason": "missing_seed_or_rank_evidence",
        }
    ]


def test_build_upset_rows_dedupes_duplicate_bouts():
    from compute_upsets import build_upset_rows

    duplicate = bracket(
        "qf-dup-complete",
        "Tableau of 8",
        1,
        1,
        F6,
        F2,
        15,
        10,
        F6,
        seed_a=6,
        seed_b=2,
    )
    incomplete = dict(duplicate, id="qf-dup-incomplete", score_a=None, score_b=None)

    rows, skipped = build_upset_rows(
        [tournament()],
        [incomplete, duplicate, duplicate],
        [result(F6, 1), result(F2, 8)],
        rankings=[],
        updated_at=NOW,
    )

    assert skipped == []
    round_rows = [row for row in rows if row["upset_type"] == "round_upset"]
    assert len(round_rows) == 1
    assert round_rows[0]["evidence"]["source_bracket_id"] == "qf-dup-complete"


def test_build_upset_rows_skips_team_events_even_when_seeded():
    from compute_upsets import build_upset_rows

    rows, skipped = build_upset_rows(
        [tournament(name="World Cup Team Foil", type="Team")],
        [
            bracket("team-qf", "Tableau of 8", 1, 1, F6, F2, 45, 40, F6, seed_a=6, seed_b=2),
        ],
        [result(F6, 1), result(F2, 8)],
        rankings=[],
        updated_at=NOW,
    )

    assert rows == []
    assert skipped == [
        {
            "tournament_id": TOURNAMENT_ID,
            "event_key": "men-foil",
            "reason": "team_event",
        }
    ]


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
        self.rows = None
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
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            if self.name not in self.client.tables:
                raise RuntimeError(f"missing table {self.name}")
            rows = list(self.client.tables[self.name])
            return FakeResult(rows[self.range_start : self.range_end + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {"table": self.name, "rows": self.rows, "on_conflict": self.on_conflict}
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


def test_compute_upsets_fetches_inputs_and_upserts_deterministically(monkeypatch):
    import compute_upsets

    client = FakeSupabase(
        {
            "fs_tournaments": [tournament()],
            "fs_tournament_brackets": seeded_brackets(),
            "fs_results": seeded_results(),
            "fs_rankings_history": [],
            "fs_national_fed_rankings": [],
        }
    )
    monkeypatch.setattr(compute_upsets, "set_state", lambda *args, **kwargs: None)

    summary = compute_upsets.compute_upsets(
        client=client,
        page_size=100,
        updated_at=NOW,
        log_run=False,
        update_state=True,
    )

    assert summary["written"] == 2
    assert summary["skipped"] == 0
    assert summary["failed"] == 0
    assert summary["no_credentials"] is False
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_upsets"
    assert upsert["on_conflict"] == "upset_key"
    assert [row["upset_key"] for row in upsert["rows"]] == sorted(
        row["upset_key"] for row in upsert["rows"]
    )
    assert all(row["id"] for row in upsert["rows"])


def test_upsets_migration_defines_table_shape_and_conflict_key():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_upsets.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_upsets" in normalized
    assert "upset_key text not null unique" in normalized
    assert "tournament_id uuid not null references public.fs_tournaments(id)" in normalized
    assert "event_key text not null" in normalized
    assert "fencer_id uuid references public.fs_fencers(id)" in normalized
    assert "opponent_id uuid references public.fs_fencers(id)" in normalized
    assert "fencer_seed integer" in normalized
    assert "opponent_seed integer" in normalized
    assert "fencer_rank integer" in normalized
    assert "opponent_rank integer" in normalized
    assert "round_name text" in normalized
    assert "expected_outcome text not null" in normalized
    assert "actual_outcome text not null" in normalized
    assert "upset_score numeric not null" in normalized
    assert "evidence jsonb not null default '{}'" in normalized
    assert "metadata jsonb not null default '{}'" in normalized

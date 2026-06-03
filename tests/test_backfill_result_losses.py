import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_result_losses.sql"

FENCER_A = "00000000-0000-0000-0000-0000000000a1"
FENCER_B = "00000000-0000-0000-0000-0000000000b2"
FENCER_C = "00000000-0000-0000-0000-0000000000c3"


def update_values_by_result_id(updates):
    return {update["filters"]["id"]: update["values"] for update in updates}


def individual_tournament(**overrides):
    row = {
        "id": "t-individual",
        "name": "Senior Men's Foil",
        "type": "world_cup",
        "weapon": "Foil",
        "metadata": {},
    }
    row.update(overrides)
    return row


def result_row(row_id, fencer_id, placement, **overrides):
    row = {
        "id": row_id,
        "tournament_id": "t-individual",
        "fencer_id": fencer_id,
        "name": row_id,
        "placement": placement,
        "metadata": {"existing": "kept"},
    }
    row.update(overrides)
    return row


class FakeUpdateQuery:
    def __init__(self, client, table_name, values):
        self.client = client
        self.table_name = table_name
        self.values = values
        self.filters = []

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        self.client.updates.append((self.table_name, self.values, tuple(self.filters)))


class FakeUpdateClient:
    def __init__(self):
        self.updates = []
        self.inserts = []
        self.upserts = []

    def table(self, table_name):
        self.table_name = table_name
        return self

    def update(self, values):
        return FakeUpdateQuery(self, self.table_name, values)

    def insert(self, row):
        self.inserts.append((self.table_name, row))
        return self

    def upsert(self, row, on_conflict=None):
        self.upserts.append((self.table_name, row, on_conflict))
        return self


def test_result_losses_migration_is_idempotent_and_safe():
    sql = MIGRATION.read_text(encoding="utf-8")
    normalized = " ".join(sql.lower().split())

    assert "alter table public.fs_results" in normalized
    assert "add column if not exists defeats integer" in normalized
    assert "add column if not exists elimination_loss_metadata jsonb" in normalized
    assert "defeats is null or defeats >= 0" in normalized
    assert "drop table" not in normalized
    assert "truncate" not in normalized
    assert "delete from public.fs_results" not in normalized
    assert "update public.fs_results" not in normalized


def test_build_result_loss_updates_counts_normal_elimination_loss():
    from scripts.backfill_result_losses import build_result_loss_updates

    updates, summary = build_result_loss_updates(
        results=[
            result_row("r-loser", FENCER_A, 2),
            result_row("r-winner", FENCER_B, 1),
        ],
        bouts=[
            {
                "id": "b-final",
                "tournament_id": "t-individual",
                "fencer_a": FENCER_A,
                "fencer_b": FENCER_B,
                "winner": FENCER_B,
                "score_a": 13,
                "score_b": 15,
                "round": "Final",
            }
        ],
        tournaments={"t-individual": individual_tournament()},
    )

    by_id = update_values_by_result_id(updates)
    loser = by_id["r-loser"]
    winner = by_id["r-winner"]

    assert loser["defeats"] == 1
    assert winner["defeats"] == 0
    assert loser["elimination_loss_metadata"]["elimination_loss"] == {
        "bout_id": "b-final",
        "round": "Final",
        "opponent_fencer_id": FENCER_B,
        "score_for": 13,
        "score_against": 15,
        "loss_reason": "score",
        "decision_source": "winner",
    }
    assert loser["elimination_loss_metadata"]["backfill_counters"]["loss_bouts"] == 1
    assert summary["rows_to_update"] == 2
    assert summary["rows_without_bout_evidence_skipped"] == 0


def test_build_result_loss_updates_ignores_byes_but_records_counter():
    from scripts.backfill_result_losses import build_result_loss_updates

    updates, summary = build_result_loss_updates(
        results=[result_row("r-bye-then-loss", FENCER_A, 2)],
        bouts=[
            {
                "id": "b-bye",
                "tournament_id": "t-individual",
                "fencer_a": FENCER_A,
                "fencer_b": None,
                "winner": FENCER_A,
                "round": "Table of 16",
                "metadata": {"is_bye": True},
            },
            {
                "id": "b-semifinal",
                "tournament_id": "t-individual",
                "fencer_a": FENCER_A,
                "fencer_b": FENCER_B,
                "winner": FENCER_B,
                "score_a": 9,
                "score_b": 15,
                "round": "Semi-Final",
            },
        ],
        tournaments={"t-individual": individual_tournament()},
    )

    row = update_values_by_result_id(updates)["r-bye-then-loss"]

    assert row["defeats"] == 1
    assert row["elimination_loss_metadata"]["backfill_counters"]["bye_bouts_skipped"] == 1
    assert row["elimination_loss_metadata"]["elimination_loss"]["bout_id"] == "b-semifinal"
    assert summary["bye_bouts_skipped"] == 1


def test_build_result_loss_updates_counts_dns_dq_with_explicit_winner():
    from scripts.backfill_result_losses import build_result_loss_updates

    updates, summary = build_result_loss_updates(
        results=[result_row("r-dq", FENCER_A, 8), result_row("r-opponent", FENCER_B, 4)],
        bouts=[
            {
                "id": "b-dq",
                "tournament_id": "t-individual",
                "fencer_a": FENCER_A,
                "fencer_b": FENCER_B,
                "winner_id": FENCER_B,
                "score_a": None,
                "score_b": None,
                "round": "Table of 8",
                "metadata": {"decision": "DQ"},
            }
        ],
        tournaments={"t-individual": individual_tournament()},
    )

    dq_row = update_values_by_result_id(updates)["r-dq"]

    assert dq_row["defeats"] == 1
    assert dq_row["elimination_loss_metadata"]["elimination_loss"]["loss_reason"] == "dq"
    assert dq_row["elimination_loss_metadata"]["backfill_counters"]["missing_score_bouts"] == 1
    assert dq_row["elimination_loss_metadata"]["backfill_counters"]["non_score_losses"] == 1
    assert summary["missing_score_bouts"] == 1
    assert summary["non_score_losses"] == 1


def test_build_result_loss_updates_counts_withdrawal_with_explicit_winner():
    from scripts.backfill_result_losses import build_result_loss_updates

    updates, summary = build_result_loss_updates(
        results=[result_row("r-withdrawal", FENCER_A, 16)],
        bouts=[
            {
                "id": "b-withdrawal",
                "tournament_id": "t-individual",
                "fencer_a": FENCER_A,
                "fencer_b": FENCER_B,
                "winner": FENCER_B,
                "score_a": None,
                "score_b": None,
                "round": "Table of 16",
                "metadata": {"status": "withdrawn"},
            }
        ],
        tournaments={"t-individual": individual_tournament()},
    )

    row = update_values_by_result_id(updates)["r-withdrawal"]

    assert row["defeats"] == 1
    assert row["elimination_loss_metadata"]["elimination_loss"]["loss_reason"] == "withdrawal"
    assert row["elimination_loss_metadata"]["backfill_counters"]["non_score_losses"] == 1
    assert summary["non_score_losses"] == 1


def test_build_result_loss_updates_skips_missing_scores_without_winner():
    from scripts.backfill_result_losses import build_result_loss_updates

    updates, summary = build_result_loss_updates(
        results=[result_row("r-a", FENCER_A, 2), result_row("r-b", FENCER_B, 1)],
        bouts=[
            {
                "id": "b-no-outcome",
                "tournament_id": "t-individual",
                "fencer_a": FENCER_A,
                "fencer_b": FENCER_B,
                "winner": None,
                "score_a": None,
                "score_b": None,
                "round": "Final",
            }
        ],
        tournaments={"t-individual": individual_tournament()},
    )

    assert updates == []
    assert summary["missing_outcome_bouts_skipped"] == 1
    assert summary["rows_without_bout_evidence_skipped"] == 2


def test_build_result_loss_updates_skips_team_events():
    from scripts.backfill_result_losses import build_result_loss_updates

    updates, summary = build_result_loss_updates(
        results=[
            result_row("r-team-a", FENCER_A, 2, tournament_id="t-team"),
            result_row("r-team-b", FENCER_B, 1, tournament_id="t-team"),
        ],
        bouts=[
            {
                "id": "b-team",
                "tournament_id": "t-team",
                "fencer_a": FENCER_A,
                "fencer_b": FENCER_B,
                "winner": FENCER_B,
                "score_a": 12,
                "score_b": 15,
                "round": "Relay 9",
            }
        ],
        tournaments={
            "t-team": {
                "id": "t-team",
                "name": "Senior Women's Epee Team",
                "event_type": "team",
                "metadata": {"is_team_event": True},
            }
        },
    )

    assert updates == []
    assert summary["team_tournaments_skipped"] == 1
    assert summary["team_result_rows_skipped"] == 2


def test_build_result_loss_updates_does_not_use_final_rank_alone():
    from scripts.backfill_result_losses import build_result_loss_updates

    updates, summary = build_result_loss_updates(
        results=[result_row("r-placement-only", FENCER_C, 3)],
        bouts=[],
        tournaments={"t-individual": individual_tournament()},
    )

    assert updates == []
    assert summary["rows_without_bout_evidence_skipped"] == 1


def test_apply_result_updates_updates_existing_rows_only():
    from scripts.backfill_result_losses import apply_result_updates

    client = FakeUpdateClient()
    written = apply_result_updates(
        client,
        [
            {
                "filters": {"id": "result-1"},
                "values": {"defeats": 1, "elimination_loss_metadata": {"source": "test"}},
            }
        ],
    )

    assert written == 1
    assert client.updates == [
        (
            "fs_results",
            {"defeats": 1, "elimination_loss_metadata": {"source": "test"}},
            (("id", "result-1"),),
        )
    ]
    assert client.inserts == []
    assert client.upserts == []

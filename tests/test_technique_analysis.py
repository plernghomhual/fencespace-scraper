import os
import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ALICE = "00000000-0000-0000-0000-000000000001"
ALICE_ALT = "00000000-0000-0000-0000-000000000002"
BOB = "00000000-0000-0000-0000-000000000003"
CAROL = "00000000-0000-0000-0000-000000000004"
DANA = "00000000-0000-0000-0000-000000000005"
EVA = "00000000-0000-0000-0000-000000000006"
NOW = "2026-06-02T12:00:00+00:00"


def positive_pattern_bouts():
    return [
        {
            "id": "pool-1",
            "tournament_id": "foil-1",
            "round": "Poule No 1",
            "fencer_a_id": ALICE,
            "fencer_b_id": BOB,
            "score_a": 5,
            "score_b": 1,
        },
        {
            "id": "pool-2",
            "tournament_id": "foil-1",
            "round": "Pool 2",
            "fencer_a_id": ALICE,
            "fencer_b_id": CAROL,
            "score_a": 5,
            "score_b": 3,
        },
        {
            "id": "pool-3",
            "tournament_id": "foil-1",
            "round": "Poule No 1",
            "fencer_a_id": ALICE,
            "fencer_b_id": DANA,
            "score_a": 3,
            "score_b": 5,
        },
        {
            "id": "de-1",
            "tournament_id": "foil-2",
            "round": "Tableau of 32",
            "fencer_a_id": ALICE,
            "fencer_b_id": BOB,
            "score_a": 15,
            "score_b": 14,
            "metadata": {"comeback_winner_id": ALICE},
        },
        {
            "id": "de-2",
            "tournament_id": "foil-2",
            "round": "Direct elimination 16",
            "fencer_a_id": ALICE,
            "fencer_b_id": CAROL,
            "score_a": 15,
            "score_b": 10,
        },
        {
            "id": "de-3",
            "tournament_id": "foil-2",
            "round": "Final",
            "fencer_a_id": DANA,
            "fencer_b_id": ALICE,
            "score_a": 14,
            "score_b": 15,
        },
    ]


def negative_pattern_bouts():
    return [
        {
            "id": "eva-pool-1",
            "tournament_id": "foil-1",
            "round": "Poule No 1",
            "fencer_a_id": EVA,
            "fencer_b_id": DANA,
            "score_a": 1,
            "score_b": 5,
        },
        {
            "id": "eva-pool-2",
            "tournament_id": "foil-1",
            "round": "Pool 3",
            "fencer_a_id": EVA,
            "fencer_b_id": BOB,
            "score_a": 2,
            "score_b": 5,
        },
        {
            "id": "eva-pool-3",
            "tournament_id": "foil-1",
            "round": "Poule No 1",
            "fencer_a_id": EVA,
            "fencer_b_id": CAROL,
            "score_a": 4,
            "score_b": 5,
        },
        {
            "id": "eva-de-1",
            "tournament_id": "foil-2",
            "round": "Tableau of 64",
            "fencer_a_id": EVA,
            "fencer_b_id": DANA,
            "score_a": 10,
            "score_b": 15,
        },
        {
            "id": "eva-de-2",
            "tournament_id": "foil-2",
            "round": "Direct elimination 32",
            "fencer_a_id": EVA,
            "fencer_b_id": BOB,
            "score_a": 14,
            "score_b": 15,
        },
        {
            "id": "eva-de-3",
            "tournament_id": "foil-2",
            "round": "Tableau of 16",
            "fencer_a_id": EVA,
            "fencer_b_id": CAROL,
            "score_a": 8,
            "score_b": 15,
        },
    ]


def base_tournaments():
    return {
        "foil-1": {"id": "foil-1", "weapon": "foil"},
        "foil-2": {"id": "foil-2", "weapon": "Foil"},
    }


def claim_ids(row, key):
    return {claim["id"] for claim in row[key]}


def test_build_technique_rows_generates_rule_based_data_pattern_insights():
    from compute_technique_analysis import build_technique_analysis_rows

    fencers = [
        {
            "id": ALICE,
            "weapon": "Foil",
            "bio_text": "Alice Example is a left-handed foil fencer.",
            "metadata": {},
        },
        {"id": EVA, "weapon": "Foil", "metadata": {"handedness": "right"}},
    ]
    rows, skipped = build_technique_analysis_rows(
        bouts=positive_pattern_bouts() + negative_pattern_bouts(),
        results=[],
        tournaments=base_tournaments(),
        fencers=fencers,
        identity_map=None,
        updated_at=NOW,
    )
    by_fencer = {row["fencer_id"]: row for row in rows}

    assert skipped == 0
    alice = by_fencer[ALICE]
    assert alice["weapon"] == "Foil"
    assert alice["confidence"] == "medium"
    assert alice["updated_at"] == NOW
    assert alice["pattern_summary"].startswith("Data-pattern insight")
    assert "left-handed" in alice["pattern_summary"]
    assert claim_ids(alice, "strengths") >= {
        "positive_touch_differential",
        "pool_positive_pattern",
        "de_positive_pattern",
        "close_bout_conversion",
    }
    assert alice["weaknesses"] == []
    assert alice["evidence_metrics"]["bouts_analyzed"] == 6
    assert alice["evidence_metrics"]["touch_differential"] == 11
    assert alice["evidence_metrics"]["pool"]["win_rate"] == 66.67
    assert alice["evidence_metrics"]["de"]["win_rate"] == 100.0
    assert alice["evidence_metrics"]["close_bout_rate"] == 33.33
    assert alice["evidence_metrics"]["comeback"]["sample_count"] == 1
    assert alice["evidence_metrics"]["handedness"]["value"] == "left"

    eva = by_fencer[EVA]
    assert eva["strengths"] == []
    assert claim_ids(eva, "weaknesses") >= {
        "negative_touch_differential",
        "pool_negative_pattern",
        "de_negative_pattern",
        "close_bout_conversion_risk",
    }
    assert eva["evidence_metrics"]["handedness"]["value"] == "right"


def test_generated_claims_always_include_evidence_metrics():
    from compute_technique_analysis import build_technique_analysis_rows

    rows, _skipped = build_technique_analysis_rows(
        bouts=positive_pattern_bouts() + negative_pattern_bouts(),
        results=[],
        tournaments=base_tournaments(),
        fencers=[{"id": ALICE, "weapon": "Foil"}, {"id": EVA, "weapon": "Foil"}],
        updated_at=NOW,
    )

    for row in rows:
        for claim in row["strengths"] + row["weaknesses"]:
            assert claim["claim"].startswith("Recorded ")
            assert claim["evidence"]
            assert isinstance(claim["evidence"], dict)
            assert claim["evidence"]["bouts_analyzed"] > 0
            assert claim["id"] in row["evidence_metrics"]["claims"]


def test_sparse_bout_data_emits_low_confidence_no_analysis_row():
    from compute_technique_analysis import build_technique_analysis_rows

    rows, skipped = build_technique_analysis_rows(
        bouts=[
            {
                "id": "only-bout",
                "tournament_id": "foil-1",
                "round": "Poule No 1",
                "fencer_a_id": ALICE,
                "fencer_b_id": BOB,
                "score_a": 5,
                "score_b": 4,
            }
        ],
        results=[],
        tournaments=base_tournaments(),
        fencers=[{"id": ALICE, "weapon": "Foil"}],
        updated_at=NOW,
    )

    assert skipped == 0
    assert rows == [
        {
            "fencer_id": ALICE,
            "weapon": "Foil",
            "pattern_summary": (
                "Low-confidence data-pattern insight: not enough recorded bouts "
                "or results for a conservative technique-style analysis."
            ),
            "strengths": [],
            "weaknesses": [],
            "evidence_metrics": {
                "bouts_analyzed": 1,
                "results_analyzed": 0,
                "reason": "insufficient_recorded_data",
                "minimum_bouts_for_claims": 5,
                "claims": {},
            },
            "confidence": "low",
            "updated_at": NOW,
        }
    ]


def test_technique_analysis_language_avoids_medical_psychological_and_definitive_claims():
    from compute_technique_analysis import build_technique_analysis_rows

    rows, _skipped = build_technique_analysis_rows(
        bouts=positive_pattern_bouts() + negative_pattern_bouts(),
        results=[],
        tournaments=base_tournaments(),
        fencers=[{"id": ALICE, "weapon": "Foil"}, {"id": EVA, "weapon": "Foil"}],
        updated_at=NOW,
    )
    text = repr(rows).lower()

    banned_terms = [
        "medical",
        "injury",
        "illness",
        "psychological",
        "mental",
        "anxiety",
        "choke",
        "diagnose",
        "proves",
        "always",
        "never",
    ]
    for term in banned_terms:
        assert term not in text


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
        if self.operation == "upsert":
            self.client.upserts.append(
                {"table": self.name, "rows": self.rows, "on_conflict": self.on_conflict}
            )
            return FakeResult([])
        rows = self.client.tables.get(self.name)
        if rows is None:
            raise RuntimeError(f"missing table {self.name}")
        return FakeResult(rows[self.range_start : cast(int, self.range_end) + 1])


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "fs_bouts": positive_pattern_bouts(),
            "fs_results": [
                {"tournament_id": "foil-1", "fencer_id": ALICE, "rank": 3},
                {"tournament_id": "foil-2", "fencer_id": ALICE_ALT, "rank": 8},
            ],
            "fs_tournaments": list(base_tournaments().values()),
            "fs_fencers": [
                {"id": ALICE, "weapon": "Foil", "bio_text": "Left-handed foil fencer."},
                {"id": ALICE_ALT, "weapon": "Foil", "metadata": {"hand": "left"}},
            ],
            "fs_fencer_identities": [
                {"id": ALICE, "fs_fencer_row_ids": [ALICE, ALICE_ALT]},
            ],
        }
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_technique_analysis_fetches_sources_and_upserts_canonical_rows():
    from compute_technique_analysis import compute_technique_analysis

    client = FakeSupabase()

    summary = compute_technique_analysis(
        client=client,
        page_size=10,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary == {
        "bouts_read": 6,
        "results_read": 2,
        "fencers_read": 2,
        "tournaments_read": 2,
        "analysis_rows": 1,
        "written": 1,
        "skipped": 0,
        "identity_rows": 1,
        "llm_summaries": 0,
    }
    assert ("fs_bouts", "id,tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,round") in client.selects
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_fencer_technique_analysis"
    assert upsert["on_conflict"] == "fencer_id,weapon"
    assert len(upsert["rows"]) == 1
    assert upsert["rows"][0]["fencer_id"] == ALICE
    assert upsert["rows"][0]["evidence_metrics"]["results_analyzed"] == 2


def test_technique_analysis_migration_defines_table_and_evidence_columns():
    sql = Path("supabase/migrations/20260602_technique_analysis.sql").read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencer_technique_analysis" in normalized
    for column in [
        "fencer_id uuid not null references public.fs_fencers(id)",
        "weapon text not null",
        "pattern_summary text not null",
        "strengths jsonb not null default '[]'::jsonb",
        "weaknesses jsonb not null default '[]'::jsonb",
        "evidence_metrics jsonb not null default '{}'::jsonb",
        "confidence text not null",
        "updated_at timestamptz not null default now()",
    ]:
        assert column in normalized
    assert "unique (fencer_id, weapon)" in normalized
    assert "check (confidence in ('high', 'medium', 'low'))" in normalized

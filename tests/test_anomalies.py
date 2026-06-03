import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"
TOURNAMENT = "10000000-0000-0000-0000-000000000001"
TOP = "00000000-0000-0000-0000-000000000001"
UNDERDOG = "00000000-0000-0000-0000-000000000002"
PEER_A = "00000000-0000-0000-0000-000000000003"
PEER_B = "00000000-0000-0000-0000-000000000004"
PEER_C = "00000000-0000-0000-0000-000000000005"
PEER_D = "00000000-0000-0000-0000-000000000006"


def bout(
    bout_id,
    fencer_a,
    fencer_b,
    winner_id,
    score_a,
    score_b,
    *,
    tournament_id=TOURNAMENT,
    metadata=None,
):
    return {
        "id": bout_id,
        "tournament_id": tournament_id,
        "fencer_a": fencer_a,
        "fencer_b": fencer_b,
        "winner_id": winner_id,
        "score_a": score_a,
        "score_b": score_b,
        "metadata": metadata or {},
    }


def normal_bouts(count=10):
    pairings = [
        (PEER_A, PEER_B, PEER_A, 15, 12),
        (PEER_B, PEER_C, PEER_B, 15, 13),
        (PEER_C, PEER_D, PEER_D, 14, 15),
        (PEER_D, PEER_A, PEER_D, 15, 11),
    ]
    rows = []
    for index in range(count):
        fencer_a, fencer_b, winner_id, score_a, score_b = pairings[index % len(pairings)]
        rows.append(
            bout(
                f"normal-{index}",
                fencer_a,
                fencer_b,
                winner_id,
                score_a,
                score_b,
            )
        )
    return rows


def ranked_fencers():
    return [
        {"id": TOP, "world_rank": 2},
        {"id": UNDERDOG, "world_rank": 185},
        {"id": PEER_A, "world_rank": 18},
        {"id": PEER_B, "world_rank": 21},
        {"id": PEER_C, "world_rank": 24},
        {"id": PEER_D, "world_rank": 27},
    ]


def tournaments():
    return [{"id": TOURNAMENT, "weapon": "Foil", "name": "Public Open"}]


def anomaly_types(rows):
    return {row["anomaly_type"] for row in rows}


def row_for(rows, anomaly_type):
    matches = [row for row in rows if row["anomaly_type"] == anomaly_type]
    assert len(matches) == 1
    return matches[0]


def assert_review_record_shape(row):
    assert row["bout_id"]
    assert row["tournament_id"] == TOURNAMENT
    assert row["fencer_id"]
    assert row["model_version"]
    assert row["created_at"] == NOW
    assert row["reviewed"] is False
    assert 0 <= row["score"] <= 100
    assert row["confidence_level"] in {"low", "medium", "high"}
    assert isinstance(row["evidence"], dict)
    assert row["evidence"]["confidence_level"] == row["confidence_level"]
    assert row["evidence"]["integrity_note"] == (
        "Statistical sports-integrity review signal; not proof of wrongdoing."
    )
    assert row["evidence"]["source_fields"]
    assert "match_fixing" not in json.dumps(row).lower()


def test_anomaly_migration_defines_review_table_shape():
    root = Path(__file__).resolve().parents[1]
    sql = (root / "supabase" / "migrations" / "20260602_anomalies.sql").read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_bout_anomalies" in normalized
    assert "bout_id uuid references public.fs_bouts(id)" in normalized
    assert "tournament_id uuid references public.fs_tournaments(id)" in normalized
    assert "fencer_id uuid references public.fs_fencers(id)" in normalized
    assert "anomaly_type text not null" in normalized
    assert "score numeric" in normalized
    assert "confidence_level text not null" in normalized
    assert "evidence jsonb not null" in normalized
    assert "model_version text not null" in normalized
    assert "reviewed boolean not null default false" in normalized
    assert "created_at timestamptz not null default now()" in normalized
    assert "unique (bout_id, anomaly_type, model_version)" in normalized
    assert "match_fixing" not in normalized


def test_normal_bouts_do_not_emit_review_signals():
    from compute_anomalies import build_anomaly_rows

    rows, skipped = build_anomaly_rows(
        normal_bouts(12),
        ranked_fencers(),
        tournaments(),
        created_at=NOW,
    )

    assert rows == []
    assert skipped == 0


def test_scoreline_and_ranking_outliers_include_clear_evidence():
    from compute_anomalies import build_anomaly_rows

    rows, skipped = build_anomaly_rows(
        [
            *normal_bouts(12),
            bout("outlier-1", UNDERDOG, TOP, UNDERDOG, 15, 0),
        ],
        ranked_fencers(),
        tournaments(),
        created_at=NOW,
    )

    assert skipped == 0
    assert {"scoreline_outlier", "ranking_result_delta"}.issubset(anomaly_types(rows))

    scoreline = row_for(rows, "scoreline_outlier")
    assert_review_record_shape(scoreline)
    assert scoreline["bout_id"] == "outlier-1"
    assert scoreline["fencer_id"] == UNDERDOG
    assert scoreline["evidence"]["features"]["winner_score"] == 15
    assert scoreline["evidence"]["features"]["loser_score"] == 0
    assert scoreline["evidence"]["features"]["margin"] == 15
    assert scoreline["evidence"]["sample_size"] >= 10

    ranking = row_for(rows, "ranking_result_delta")
    assert_review_record_shape(ranking)
    assert ranking["evidence"]["features"]["winner_world_rank"] == 185
    assert ranking["evidence"]["features"]["opponent_world_rank"] == 2
    assert ranking["evidence"]["features"]["rank_delta"] == 183
    assert ranking["confidence_level"] in {"medium", "high"}


def test_low_sample_size_suppresses_even_extreme_bouts():
    from compute_anomalies import build_anomaly_rows

    rows, skipped = build_anomaly_rows(
        [
            *normal_bouts(3),
            bout("too-small", UNDERDOG, TOP, UNDERDOG, 15, 0),
        ],
        ranked_fencers(),
        tournaments(),
        created_at=NOW,
    )

    assert rows == []
    assert skipped == 0


def test_missing_rankings_suppress_ranking_delta_without_blocking_scoreline_review():
    from compute_anomalies import build_anomaly_rows

    fencers = [
        {"id": TOP, "world_rank": None},
        {"id": UNDERDOG, "world_rank": None},
        *ranked_fencers()[2:],
    ]
    rows, skipped = build_anomaly_rows(
        [
            *normal_bouts(12),
            bout("score-only", UNDERDOG, TOP, UNDERDOG, 15, 0),
        ],
        fencers,
        tournaments(),
        created_at=NOW,
    )

    assert "scoreline_outlier" in anomaly_types(rows)
    assert "ranking_result_delta" not in anomaly_types(rows)
    assert skipped == 0


def test_duplicate_bouts_are_deduped_before_scoring_and_storage():
    from compute_anomalies import build_anomaly_rows

    duplicate = bout("dup-outlier", UNDERDOG, TOP, UNDERDOG, 15, 0)
    rows, skipped = build_anomaly_rows(
        [
            *normal_bouts(12),
            duplicate,
            dict(duplicate),
        ],
        ranked_fencers(),
        tournaments(),
        created_at=NOW,
    )

    assert skipped == 1
    assert [row["bout_id"] for row in rows].count("dup-outlier") == len(rows)
    assert len([row for row in rows if row["anomaly_type"] == "scoreline_outlier"]) == 1
    assert len([row for row in rows if row["anomaly_type"] == "ranking_result_delta"]) == 1


def test_public_betting_mismatch_requires_lawful_public_source_metadata():
    from compute_anomalies import build_anomaly_rows

    private_betting = bout(
        "private-market",
        UNDERDOG,
        TOP,
        UNDERDOG,
        15,
        8,
        metadata={
            "public_betting": {
                "lawful_public": False,
                "favorite_fencer_id": TOP,
                "favorite_implied_probability": 0.91,
            }
        },
    )
    public_betting = bout(
        "public-market",
        UNDERDOG,
        TOP,
        UNDERDOG,
        15,
        8,
        metadata={
            "public_betting": {
                "lawful_public": True,
                "source_url": "https://example.test/public-market",
                "favorite_fencer_id": TOP,
                "favorite_implied_probability": 0.91,
            }
        },
    )

    rows, skipped = build_anomaly_rows(
        [
            *normal_bouts(12),
            private_betting,
            public_betting,
        ],
        ranked_fencers(),
        tournaments(),
        created_at=NOW,
    )

    assert skipped == 0
    betting_rows = [
        row for row in rows if row["anomaly_type"] == "public_betting_data_mismatch"
    ]
    assert len(betting_rows) == 1
    assert betting_rows[0]["bout_id"] == "public-market"
    assert betting_rows[0]["evidence"]["features"]["source_url"] == (
        "https://example.test/public-market"
    )


def test_repeated_unusual_patterns_are_fencer_scoped_and_conservative():
    from compute_anomalies import build_anomaly_rows

    rows, skipped = build_anomaly_rows(
        [
            *normal_bouts(12),
            bout("upset-1", UNDERDOG, TOP, UNDERDOG, 15, 9),
            bout("upset-2", UNDERDOG, PEER_A, UNDERDOG, 15, 8),
            bout("upset-3", UNDERDOG, PEER_B, UNDERDOG, 15, 7),
            bout("normal-underdog", UNDERDOG, PEER_C, PEER_C, 10, 15),
        ],
        ranked_fencers(),
        tournaments(),
        created_at=NOW,
    )

    assert skipped == 0
    repeated = row_for(rows, "repeated_unusual_pattern")
    assert_review_record_shape(repeated)
    assert repeated["fencer_id"] == UNDERDOG
    assert repeated["evidence"]["features"]["unusual_bout_count"] == 3
    assert repeated["evidence"]["features"]["fencer_bout_count"] == 4
    assert repeated["evidence"]["features"]["bout_ids"] == [
        "upset-1",
        "upset-2",
        "upset-3",
    ]


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
                *normal_bouts(12),
                bout("outlier-1", UNDERDOG, TOP, UNDERDOG, 15, 0),
            ],
            "fs_fencers": ranked_fencers(),
            "fs_tournaments": tournaments(),
            "fs_bout_anomalies": [],
        }
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_compute_anomalies_fetches_inputs_and_upserts_review_rows():
    from compute_anomalies import compute_anomalies

    client = FakeSupabase()

    summary = compute_anomalies(
        client=client,
        page_size=10,
        log_run=False,
        update_state=False,
        created_at=NOW,
    )

    assert summary["bouts_read"] == 13
    assert summary["fencers_read"] == 6
    assert summary["tournaments_read"] == 1
    assert summary["anomalies_built"] >= 2
    assert summary["written"] == summary["anomalies_built"]
    assert summary["skipped"] == 0
    assert client.upserts
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_bout_anomalies"
    assert upsert["on_conflict"] == "bout_id,anomaly_type,model_version"
    assert all(row["reviewed"] is False for row in upsert["rows"])


def test_compute_anomalies_does_not_reset_existing_reviewed_signals():
    from compute_anomalies import MODEL_VERSION, compute_anomalies

    client = FakeSupabase()
    client.tables["fs_bout_anomalies"] = [
        {
            "bout_id": "outlier-1",
            "anomaly_type": "scoreline_outlier",
            "model_version": MODEL_VERSION,
            "reviewed": True,
        }
    ]

    summary = compute_anomalies(
        client=client,
        page_size=10,
        log_run=False,
        update_state=False,
        created_at=NOW,
    )

    assert summary["anomalies_built"] >= 2
    assert summary["reviewed_preserved"] == 1
    upserted_types = {
        row["anomaly_type"]
        for upsert in client.upserts
        for row in upsert["rows"]
    }
    assert "scoreline_outlier" not in upserted_types
    assert "ranking_result_delta" in upserted_types

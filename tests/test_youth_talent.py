import json
from pathlib import Path

NOW = "2026-06-02T12:00:00+00:00"
FENCER_STANDOUT = "11111111-1111-1111-1111-111111111111"
FENCER_ORDINARY = "22222222-2222-2222-2222-222222222222"
FENCER_SPARSE = "33333333-3333-3333-3333-333333333333"


def test_build_youth_talent_rows_scores_known_public_feature_patterns():
    from compute_youth_talent import build_youth_talent_rows

    results = [
        {"fencer_id": FENCER_STANDOUT, "tournament_id": "cadet-1", "rank": 1},
        {"fencer_id": FENCER_STANDOUT, "tournament_id": "cadet-2", "placement": 3},
        {"fencer_id": FENCER_STANDOUT, "tournament_id": "junior-1", "rank": 7},
        {"fencer_id": FENCER_ORDINARY, "tournament_id": "cadet-1", "rank": 28},
        {"fencer_id": FENCER_ORDINARY, "tournament_id": "cadet-2", "rank": 35},
    ]
    tournaments = [
        {"id": "cadet-1", "category": "Cadet", "weapon": "Foil"},
        {"id": "cadet-2", "category": "Cadet", "weapon": "Foil"},
        {"id": "junior-1", "category": "Junior", "weapon": "Foil"},
    ]
    rankings = [
        {"fencer_id": FENCER_STANDOUT, "category": "Cadet", "rank": 2, "points": 320.5},
        {"fencer_id": FENCER_STANDOUT, "category": "Junior", "rank": 4, "points": 285.0},
        {"fencer_id": FENCER_STANDOUT, "category": "Junior", "rank": 8, "points": 250.0},
        {"fencer_id": FENCER_ORDINARY, "category": "Cadet", "rank": 44, "points": 12.0},
    ]

    rows, skipped = build_youth_talent_rows(
        results,
        tournaments,
        rankings,
        [],
        updated_at=NOW,
    )

    assert skipped == 0
    by_fencer = {row["fencer_id"]: row for row in rows}
    standout = by_fencer[FENCER_STANDOUT]
    ordinary = by_fencer[FENCER_ORDINARY]

    assert standout["label"] == "early-career outlier"
    assert standout["outlier_score"] >= 70
    assert standout["confidence"] == "high"
    assert standout["age_band"] == "mixed-youth"
    assert standout["feature_summary"]["public_result_count"] == 3
    assert standout["feature_summary"]["public_ranking_count"] == 3
    assert standout["feature_summary"]["best_result_rank"] == 1
    assert standout["feature_summary"]["best_ranking_rank"] == 2

    assert ordinary["label"] != "early-career outlier"
    assert ordinary["outlier_score"] < standout["outlier_score"]
    assert ordinary["feature_summary"]["best_result_rank"] == 28


def test_sparse_unknown_category_rows_get_low_confidence_flags():
    from compute_youth_talent import build_youth_talent_rows

    rows, skipped = build_youth_talent_rows(
        [{"fencer_id": FENCER_SPARSE, "rank": 1, "weapon": "Epee"}],
        [],
        [],
        [],
        updated_at=NOW,
    )

    assert skipped == 0
    assert len(rows) == 1
    row = rows[0]
    assert row["fencer_id"] == FENCER_SPARSE
    assert row["age_band"] == "unknown"
    assert row["category"] == "Unknown"
    assert row["confidence"] == "low"
    assert row["label"] == "insufficient public evidence"
    assert row["outlier_score"] < 35
    assert row["low_confidence_flags"] == [
        "age_category_uncertain",
        "sparse_public_data",
    ]
    assert "low confidence" in row["explanation"].lower()


def test_youth_talent_output_excludes_sensitive_age_source_fields():
    from compute_youth_talent import build_youth_talent_rows

    rows, _ = build_youth_talent_rows(
        [
            {
                "fencer_id": FENCER_STANDOUT,
                "category": "Cadet",
                "rank": 1,
                "date_of_birth": "2009-04-03",
                "birth_date": "2009-04-03",
                "dob": "2009-04-03",
                "exact_age": 16,
            }
        ],
        [],
        [
            {
                "fencer_id": FENCER_STANDOUT,
                "category": "Cadet",
                "rank": 2,
                "date_of_birth": "2009-04-03",
                "birth_date": "2009-04-03",
                "dob": "2009-04-03",
                "exact_age": 16,
            }
        ],
        [],
        updated_at=NOW,
    )

    serialized = json.dumps(rows[0], sort_keys=True).lower()
    assert "2009-04-03" not in serialized
    assert "date_of_birth" not in serialized
    assert "birth_date" not in serialized
    assert "dob" not in serialized
    assert "exact_age" not in serialized


def test_explanation_is_conservative_and_interpretable():
    from compute_youth_talent import build_youth_talent_rows

    rows, _ = build_youth_talent_rows(
        [
            {"fencer_id": FENCER_STANDOUT, "category": "Junior", "rank": 1},
            {"fencer_id": FENCER_STANDOUT, "category": "Junior", "rank": 2},
            {"fencer_id": FENCER_STANDOUT, "category": "Junior", "rank": 6},
        ],
        [],
        [
            {"fencer_id": FENCER_STANDOUT, "category": "Junior", "rank": 3},
            {"fencer_id": FENCER_STANDOUT, "category": "Junior", "rank": 5},
        ],
        [],
        updated_at=NOW,
    )

    explanation = rows[0]["explanation"].lower()
    assert "early-career outlier" in explanation
    assert "public" in explanation
    assert "not a prediction" in explanation
    assert "future champion" not in explanation
    assert "will become" not in explanation


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.start = 0
        self.end = 999
        self.pending_upsert = None
        self.pending_conflict = None

    def select(self, columns):
        self.client.selects.append((self.table_name, columns))
        return self

    def order(self, column):
        self.client.orders.append((self.table_name, column))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def limit(self, _count):
        return self

    def upsert(self, rows, on_conflict):
        self.pending_upsert = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.pending_upsert is not None:
            self.client.upserts.append(
                {
                    "table": self.table_name,
                    "rows": self.pending_upsert,
                    "on_conflict": self.pending_conflict,
                }
            )
            return FakeResult([])
        rows = self.client.tables.get(self.table_name, [])
        return FakeResult(rows[self.start : self.end + 1])


class FakeClient:
    def __init__(self):
        self.tables = {
            "fs_results": [
                {"fencer_id": FENCER_STANDOUT, "tournament_id": "junior-1", "rank": 1},
                {"fencer_id": FENCER_STANDOUT, "tournament_id": "junior-2", "rank": 5},
            ],
            "fs_tournaments": [
                {"id": "junior-1", "category": "Junior", "weapon": "Sabre"},
                {"id": "junior-2", "category": "Junior", "weapon": "Sabre"},
            ],
            "fs_rankings_history": [
                {"fencer_id": FENCER_STANDOUT, "category": "Junior", "rank": 2, "points": 100.0},
            ],
            "fs_national_fed_rankings": [
                {"fencer_id": FENCER_STANDOUT, "category": "Junior", "rank": 3, "points": 95.0},
            ],
        }
        self.selects = []
        self.orders = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_compute_youth_talent_fetches_public_rows_and_upserts_analytics():
    from compute_youth_talent import compute_youth_talent

    client = FakeClient()

    summary = compute_youth_talent(
        client=client,
        page_size=10,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary == {
        "results_read": 2,
        "tournaments_read": 2,
        "ranking_rows_read": 2,
        "analytics_rows": 1,
        "written": 1,
        "failed": 0,
        "skipped": 0,
    }
    assert ("fs_results", "fencer_id,tournament_id,rank,placement,weapon,category,metadata") in client.selects
    assert ("fs_rankings_history", "fencer_id,fie_fencer_id,season,weapon,category,rank,points,metadata") in client.selects
    assert client.upserts[0]["table"] == "fs_youth_talent_analytics"
    assert client.upserts[0]["on_conflict"] == "fencer_id"
    assert client.upserts[0]["rows"][0]["explanation"]


def test_youth_talent_migration_defines_privacy_conscious_table():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_youth_talent.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_youth_talent_analytics" in normalized
    assert "fencer_id" in normalized
    assert "age_band" in normalized
    assert "category" in normalized
    assert "feature_summary jsonb" in normalized
    assert "outlier_score" in normalized
    assert "explanation" in normalized
    assert "updated_at" in normalized
    assert "early-career outlier" in normalized
    assert "not a prediction" in normalized
    assert "exact birthdates" in normalized
    assert "date_of_birth" not in normalized
    assert "birth_date" not in normalized
    assert "dob" not in normalized

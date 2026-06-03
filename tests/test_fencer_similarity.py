import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"
A = "00000000-0000-0000-0000-000000000001"
A_DUP = "00000000-0000-0000-0000-000000000011"
B = "00000000-0000-0000-0000-000000000002"
C = "00000000-0000-0000-0000-000000000003"
SPARSE = "00000000-0000-0000-0000-000000000004"
ID_A = "10000000-0000-0000-0000-000000000001"
ID_B = "10000000-0000-0000-0000-000000000002"
ID_C = "10000000-0000-0000-0000-000000000003"
ID_SPARSE = "10000000-0000-0000-0000-000000000004"


def fencer(
    row_id,
    name,
    country,
    fie_id,
    weapon,
    *,
    category="Men's Senior",
    hand=None,
    birth_date=None,
):
    return {
        "id": row_id,
        "fie_id": fie_id,
        "name": name,
        "country": country,
        "weapon": weapon,
        "category": category,
        "hand": hand,
        "birth_date": birth_date,
    }


def ranking(fie_id, weapon, season, rank, points, *, category="Men's Senior"):
    return {
        "fie_fencer_id": fie_id,
        "weapon": weapon,
        "category": category,
        "season": season,
        "rank": rank,
        "points": points,
    }


def result(fencer_id, tournament_id, rank, *, fie_fencer_id=None):
    return {
        "fencer_id": fencer_id,
        "fie_fencer_id": fie_fencer_id,
        "tournament_id": tournament_id,
        "rank": rank,
    }


def fixture_inputs():
    fencers = [
        fencer(A, "Alice Example", "USA", "1001", "Foil", hand="L", birth_date="2000-01-15"),
        fencer(A_DUP, "Alice Example", "United States", "1001", "Epee", hand="left", birth_date="2000-01-15"),
        fencer(B, "Alicia Sample", "United States", "1002", "foil", hand="Left", birth_date="2001-03-20"),
        fencer(C, "Carla Different", "Italy", "2001", "Sabre", hand="Right", birth_date="1988-09-10"),
        fencer(SPARSE, "Sparse Fencer", "USA", None, "Foil"),
    ]
    identities = [
        {"id": ID_A, "fs_fencer_row_ids": [A, A_DUP], "fie_ids": ["1001"]},
        {"id": ID_B, "fs_fencer_row_ids": [B], "fie_ids": ["1002"]},
        {"id": ID_C, "fs_fencer_row_ids": [C], "fie_ids": ["2001"]},
        {"id": ID_SPARSE, "fs_fencer_row_ids": [SPARSE], "fie_ids": []},
    ]
    rankings = [
        ranking("1001", "Foil", 2024, 10, 120.0),
        ranking("1001", "Foil", 2025, 8, 150.0),
        ranking("1002", "Foil", 2024, 12, 100.0),
        ranking("1002", "Foil", 2025, 9, 145.0),
        ranking("2001", "Sabre", 2024, 75, 12.0),
        ranking("2001", "Sabre", 2025, 81, 9.0),
    ]
    tournaments = [
        {"id": "foil-gp", "weapon": "Foil", "gender": "Men's", "category": "Senior", "season": 2025},
        {"id": "foil-wc", "weapon": "Foil", "gender": "Men's", "category": "Senior", "season": 2024},
        {"id": "sabre-sat", "weapon": "Sabre", "gender": "Men's", "category": "Senior", "season": 2025},
    ]
    results = [
        result(A, "foil-gp", 6),
        result(A_DUP, "foil-wc", 10),
        result(B, "foil-gp", 7),
        result(B, "foil-wc", 11),
        result(C, "sabre-sat", 47),
    ]
    return fencers, identities, rankings, results, tournaments


def build_fixture_features():
    from compute_fencer_similarity import build_feature_vectors

    fencers, identities, rankings, results, tournaments = fixture_inputs()
    features, skipped = build_feature_vectors(
        fencers=fencers,
        rankings_history=rankings,
        results=results,
        tournaments=tournaments,
        identity_rows=identities,
        computed_at=NOW,
    )
    return features, skipped


def test_build_feature_vectors_normalizes_public_sports_features_by_identity():
    features, skipped = build_fixture_features()

    assert skipped == 0
    assert set(features) == {A, B, C, SPARSE}
    alice = features[A]

    assert alice["identity_id"] == ID_A
    assert alice["fencer_id"] == A
    assert alice["primary_weapon"] == "Foil"
    assert alice["sample_size"] == 4
    assert alice["confidence"] > features[SPARSE]["confidence"]
    assert alice["attributes"]["hand"] == "left"
    assert alice["attributes"]["country"] == "United States"
    assert alice["attributes"]["career_stage"] == "senior"
    assert alice["attributes"]["age"] == pytest.approx(26.4, abs=0.1)

    vector = alice["vector"]
    assert vector["weapon:Foil"] > vector["weapon:Epee"]
    assert vector["hand:left"] == 1.0
    assert vector["ranking_score"] > 0.0
    assert vector["result_score"] > 0.0
    assert all(0.0 <= value <= 1.0 for value in vector.values())


def test_similarity_score_orders_nearby_fencers_above_different_profiles():
    from compute_fencer_similarity import build_similarity_rows

    features, _ = build_fixture_features()
    rows = build_similarity_rows(
        features,
        updated_at=NOW,
        max_recommendations_per_fencer=10,
    )
    by_pair = {(row["fencer_id"], row["similar_fencer_id"]): row for row in rows}

    near = by_pair[(A, B)]
    far = by_pair[(A, C)]

    assert near["score"] > far["score"]
    assert near["confidence"] > 0.7
    assert near["sample_size"] == 4
    assert near["model_version"] == "public_sports_similarity_v1"
    assert near["updated_at"] == NOW
    assert near["factor_breakdown"]["weapon"]["score"] == pytest.approx(1.0)
    assert near["factor_breakdown"]["country"]["score"] == pytest.approx(1.0)


def test_similarity_rows_are_symmetric_once_and_exclude_self_and_duplicate_identity_matches():
    from compute_fencer_similarity import build_similarity_rows

    features, _ = build_fixture_features()
    rows = build_similarity_rows(features, updated_at=NOW, max_recommendations_per_fencer=10)
    pairs = {(row["fencer_id"], row["similar_fencer_id"]) for row in rows}

    assert all(left < right for left, right in pairs)
    assert all(left != right for left, right in pairs)
    assert (A, A_DUP) not in pairs
    assert (A_DUP, B) not in pairs
    assert (A, B) in pairs
    assert (B, A) not in pairs


def test_sparse_features_keep_low_confidence_and_mark_missing_factors():
    from compute_fencer_similarity import build_similarity_rows

    features, _ = build_fixture_features()

    assert features[SPARSE]["sample_size"] == 0
    assert features[SPARSE]["confidence"] < 0.5

    rows = build_similarity_rows(features, updated_at=NOW, max_recommendations_per_fencer=10)
    sparse_pair = next(
        row for row in rows
        if {row["fencer_id"], row["similar_fencer_id"]} == {B, SPARSE}
    )

    assert 0.0 <= sparse_pair["score"] <= 1.0
    assert sparse_pair["confidence"] < 0.6
    assert sparse_pair["sample_size"] == 0
    assert "ranking" in sparse_pair["factor_breakdown"]["missing_factors"]
    assert "results" in sparse_pair["factor_breakdown"]["missing_factors"]


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

    def limit(self, count):
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
        return FakeResult(rows[self.start:end])


class FakeSupabase:
    def __init__(self):
        fencers, identities, rankings, results, tournaments = fixture_inputs()
        self.tables = {
            "fs_fencers": fencers,
            "fs_fencer_identities": identities,
            "fs_rankings_history": rankings,
            "fs_results": results,
            "fs_tournaments": tournaments,
        }
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_compute_fencer_similarity_fetches_public_inputs_and_upserts_pairs():
    from compute_fencer_similarity import compute_fencer_similarity

    client = FakeSupabase()

    summary = compute_fencer_similarity(
        client=client,
        page_size=2,
        batch_size=2,
        max_recommendations_per_fencer=10,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary["fencers_read"] == 5
    assert summary["identity_rows"] == 4
    assert summary["feature_rows"] == 4
    assert summary["written"] == len([row for call in client.upserts for row in call["rows"]])
    assert {call["table"] for call in client.upserts} == {"fs_fencer_similarity"}
    assert {call["on_conflict"] for call in client.upserts} == {"fencer_id,similar_fencer_id"}
    assert any(columns.startswith("id,fie_id,name,country,weapon,category") for table, columns in client.selects if table == "fs_fencers")
    assert any("fs_fencer_row_ids" in columns for table, columns in client.selects if table == "fs_fencer_identities")


def test_similarity_migration_defines_table_shape_and_unique_unordered_pairs():
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "20260602_similarity.sql"
    )
    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencer_similarity" in normalized
    assert "fencer_id uuid not null references public.fs_fencers(id)" in normalized
    assert "similar_fencer_id uuid not null references public.fs_fencers(id)" in normalized
    assert "score numeric" in normalized
    assert "confidence numeric" in normalized
    assert "sample_size integer" in normalized
    assert "factor_breakdown jsonb not null default '{}'::jsonb" in normalized
    assert "model_version text not null" in normalized
    assert "updated_at timestamptz not null" in normalized
    assert "primary key (fencer_id, similar_fencer_id)" in normalized
    assert "check (fencer_id <> similar_fencer_id)" in normalized
    assert "check (fencer_id < similar_fencer_id)" in normalized

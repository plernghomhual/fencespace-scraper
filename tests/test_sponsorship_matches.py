import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ROOT = Path(__file__).resolve().parents[1]
ADULT_FENCER_ID = "11111111-1111-1111-1111-111111111111"
MINOR_FENCER_ID = "22222222-2222-2222-2222-222222222222"


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.columns = None
        self.range_bounds = None
        self.limit_count = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        self.client.selects.append({"table": self.name, "columns": columns})
        return self

    def range(self, start, end):
        self.range_bounds = (start, end)
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def upsert(self, rows, on_conflict=None):
        self.operation = "upsert"
        self.client.upserts.append(
            {"table": self.name, "rows": rows, "on_conflict": on_conflict}
        )
        return self

    def execute(self):
        if self.operation == "upsert":
            return FakeResult([])
        rows = list(self.client.rows_by_table.get(self.name, []))
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        if self.range_bounds is not None:
            start, end = self.range_bounds
            rows = rows[start : end + 1]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.selects = []
        self.upserts = []
        self.touched_tables = []

    def table(self, name):
        self.touched_tables.append(name)
        return FakeTable(self, name)


def adult_fencer(**overrides):
    row = {
        "id": ADULT_FENCER_ID,
        "name": "Avery Foilist",
        "country": "United States",
        "nationality": "United States",
        "weapon": "Foil",
        "world_rank": 3,
        "date_of_birth": "1994-06-15",
        "metadata": {},
    }
    row.update(overrides)
    return row


def test_score_components_reward_performance_geography_weapon_affinity_and_social_reach():
    from compute_sponsorship_matches import build_sponsorship_match_rows

    rows, skipped = build_sponsorship_match_rows(
        fencers=[adult_fencer()],
        performance_rows=[
            {
                "fencer_id": ADULT_FENCER_ID,
                "weapon": "Foil",
                "competitions_count": 12,
                "avg_delta": 8.0,
                "overperformance_rate": 75.0,
                "clutch_score": 8.0,
            }
        ],
        career_rows=[
            {
                "fencer_id": ADULT_FENCER_ID,
                "total_competitions": 24,
                "gold_medals": 2,
                "silver_medals": 1,
                "bronze_medals": 1,
                "top8_count": 14,
                "best_rank": 1,
            }
        ],
        equipment_rows=[
            {
                "fencer_id": ADULT_FENCER_ID,
                "brand": "Absolute Fencing",
                "equipment_type": "weapon",
                "sponsor_name": "Absolute Fencing",
                "confidence": "high",
                "metadata": {"source": "fie_profile"},
            }
        ],
        social_rows=[
            {
                "fencer_id": ADULT_FENCER_ID,
                "platform": "instagram",
                "verified": True,
                "metadata": {"followers": 120000},
            },
            {
                "fencer_id": ADULT_FENCER_ID,
                "platform": "youtube",
                "verified": False,
                "metadata": {"subscriber_count": 30000},
            },
        ],
        review_rows=[
            {
                "brand": "Absolute Fencing",
                "category": "Foil weapon",
                "metadata": {"country": "United States", "weapons": ["Foil"]},
            }
        ],
        today=date(2026, 6, 2),
        updated_at="2026-06-02T12:00:00+00:00",
    )

    assert skipped == 0
    assert len(rows) == 1
    row = rows[0]
    assert row["brand"] == "Absolute Fencing"
    assert row["fencer_id"] == ADULT_FENCER_ID
    assert row["match_score"] >= 85
    assert row["confidence"] == "high"
    assert row["updated_at"] == "2026-06-02T12:00:00+00:00"

    components = row["score_components"]
    assert set(components) >= {
        "performance",
        "geography",
        "weapon",
        "brand_affinity",
        "social_reach",
        "weights",
        "data_quality",
    }
    assert components["performance"] > 0.75
    assert components["geography"] == 1.0
    assert components["weapon"] == 1.0
    assert components["brand_affinity"] == 1.0
    assert components["social_reach"] > 0.7
    assert "public social reach" in row["explanation"]
    assert "existing brand affinity" in row["explanation"]


def test_known_minors_are_excluded_from_candidate_rows():
    from compute_sponsorship_matches import build_sponsorship_match_rows

    fencers = [
        adult_fencer(id=ADULT_FENCER_ID, date_of_birth="1998-01-01"),
        adult_fencer(
            id=MINOR_FENCER_ID,
            name="Young Sabreur",
            country="United States",
            weapon="Sabre",
            world_rank=5,
            date_of_birth="2010-07-01",
        ),
    ]

    rows, skipped = build_sponsorship_match_rows(
        fencers=fencers,
        performance_rows=[
            {"fencer_id": ADULT_FENCER_ID, "weapon": "Foil", "clutch_score": 6},
            {"fencer_id": MINOR_FENCER_ID, "weapon": "Sabre", "clutch_score": 12},
        ],
        career_rows=[],
        equipment_rows=[],
        social_rows=[],
        review_rows=[
            {"brand": "Absolute Fencing", "metadata": {"country": "United States"}}
        ],
        today=date(2026, 6, 2),
    )

    assert skipped == 1
    assert {row["fencer_id"] for row in rows} == {ADULT_FENCER_ID}


def test_sparse_data_still_produces_lower_confidence_performance_geography_match():
    from compute_sponsorship_matches import build_sponsorship_match_rows

    rows, skipped = build_sponsorship_match_rows(
        fencers=[
            adult_fencer(
                country="France",
                nationality="France",
                weapon="Epee",
                world_rank=20,
                metadata={},
            )
        ],
        performance_rows=[],
        career_rows=[],
        equipment_rows=[],
        social_rows=[],
        review_rows=[{"brand": "Prieur", "metadata": {"country": "France"}}],
        today=date(2026, 6, 2),
    )

    assert skipped == 0
    assert len(rows) == 1
    row = rows[0]
    assert row["brand"] == "Prieur"
    assert row["match_score"] > 35
    assert row["confidence"] == "low"
    assert row["score_components"]["performance"] > 0.6
    assert row["score_components"]["geography"] == 1.0
    assert row["score_components"]["brand_affinity"] <= 0.2
    assert row["score_components"]["social_reach"] <= 0.2
    assert "sparse data" in row["explanation"]
    assert "missing public social reach" in row["explanation"]


def test_compute_upserts_matches_without_outreach_side_effects():
    from compute_sponsorship_matches import compute_sponsorship_matches

    client = FakeSupabase(
        {
            "fs_fencers": [adult_fencer()],
            "fs_fencer_performance_analysis": [
                {
                    "fencer_id": ADULT_FENCER_ID,
                    "weapon": "Foil",
                    "competitions_count": 8,
                    "overperformance_rate": 80,
                    "clutch_score": 10,
                }
            ],
            "fs_fencer_career_stats": [],
            "fs_fencer_equipment": [
                {
                    "fencer_id": ADULT_FENCER_ID,
                    "brand": "Absolute Fencing",
                    "equipment_type": "weapon",
                    "sponsor_name": None,
                    "confidence": "medium",
                    "metadata": {},
                }
            ],
            "fs_fencer_social_media": [
                {
                    "fencer_id": ADULT_FENCER_ID,
                    "platform": "instagram",
                    "verified": True,
                    "metadata": {"followers": 25000},
                }
            ],
            "fs_equipment_reviews": [
                {
                    "brand": "Absolute Fencing",
                    "category": "Foil weapon",
                    "metadata": {"country": "United States", "weapons": ["Foil"]},
                }
            ],
        }
    )

    summary = compute_sponsorship_matches(
        client,
        log_run=False,
        update_state=False,
        today=date(2026, 6, 2),
        updated_at="2026-06-02T12:00:00+00:00",
    )

    assert summary["matches_built"] == 1
    assert summary["written"] == 1
    assert len(client.upserts) == 1
    assert client.upserts[0]["table"] == "fs_sponsorship_matches"
    assert client.upserts[0]["on_conflict"] == "brand,fencer_id"
    assert client.upserts[0]["rows"][0]["explanation"]

    forbidden = ("outreach", "email", "message", "contact", "campaign")
    assert all(not any(term in table for term in forbidden) for table in client.touched_tables)


def test_sponsorship_match_migration_defines_explainable_recommendation_table():
    sql = (ROOT / "supabase" / "migrations" / "20260602_sponsorship_matches.sql").read_text().lower()
    compact = " ".join(sql.split())

    assert "create table if not exists public.fs_sponsorship_matches" in sql
    assert "brand text not null" in compact
    assert "fencer_id uuid not null references public.fs_fencers(id)" in compact
    assert "match_score numeric" in compact
    assert "score_components jsonb not null default '{}'" in compact
    assert "confidence text not null" in compact
    assert "explanation text not null" in compact
    assert "updated_at timestamptz not null default now()" in compact
    assert "primary key (brand, fencer_id)" in compact
    assert "check (match_score >= 0 and match_score <= 100)" in compact
    assert "enable row level security" in compact

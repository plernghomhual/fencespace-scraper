import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

ALICE = "00000000-0000-0000-0000-000000000001"
BOB = "00000000-0000-0000-0000-000000000002"
SPARSE = "00000000-0000-0000-0000-000000000003"
NOW = "2026-06-02T12:00:00+00:00"


def fixture_source_data():
    return {
        "fencers": [
            {
                "id": ALICE,
                "name": "Ari Park",
                "country": "USA",
                "weapon": "Foil",
                "world_rank": 4,
                "fie_fencer_id": "1001",
            },
            {
                "id": BOB,
                "name": "Bea Rossi",
                "country": "ITA",
                "weapon": "Foil",
                "world_rank": 7,
                "fie_fencer_id": "1002",
            },
        ],
        "career_stats": [
            {
                "fencer_id": ALICE,
                "total_competitions": 12,
                "gold_medals": 3,
                "silver_medals": 1,
                "bronze_medals": 2,
                "top8_count": 9,
                "best_rank": 1,
                "avg_rank": 4.25,
                "worst_rank": 18,
                "weapons_used": ["Foil"],
                "categories_competed": ["Women's Senior"],
                "first_season": "2022-2023",
                "last_season": "2025-2026",
            },
            {
                "fencer_id": BOB,
                "total_competitions": 10,
                "gold_medals": 1,
                "silver_medals": 2,
                "bronze_medals": 1,
                "top8_count": 7,
                "best_rank": 1,
                "avg_rank": 5.1,
                "worst_rank": 20,
                "weapons_used": ["Foil"],
                "categories_competed": ["Women's Senior"],
                "first_season": "2021-2022",
                "last_season": "2025-2026",
            },
        ],
        "performance": [
            {
                "fencer_id": ALICE,
                "weapon": "Foil",
                "competitions_count": 8,
                "avg_delta": 2.5,
                "overperformance_rate": 75.0,
                "clutch_score": 2.5,
            },
            {
                "fencer_id": BOB,
                "weapon": "Foil",
                "competitions_count": 6,
                "avg_delta": -1.25,
                "overperformance_rate": 33.33,
                "clutch_score": -1.25,
            },
        ],
        "ranking_trends": [
            {
                "fencer_id": "1001",
                "weapon": "Foil",
                "category": "Women's Senior",
                "season": 2025,
                "rank": 4,
                "previous_rank": 6,
                "rank_change": 2,
                "points": 170.0,
                "trend_direction": "up",
            },
            {
                "fencer_id": "1002",
                "weapon": "Foil",
                "category": "Women's Senior",
                "season": 2025,
                "rank": 7,
                "previous_rank": 5,
                "rank_change": -2,
                "points": 150.0,
                "trend_direction": "down",
            },
        ],
        "head_to_head": [
            {
                "fencer_a_id": ALICE,
                "fencer_b_id": BOB,
                "weapon": "Foil",
                "a_wins": 3,
                "b_wins": 2,
                "a_touches": 70,
                "b_touches": 64,
                "bouts_total": 5,
                "last_meeting_date": "2026-04-20",
                "last_winner_id": BOB,
            }
        ],
        "results": [
            {
                "id": "r1",
                "tournament_id": "t1",
                "fencer_id": ALICE,
                "rank": 1,
                "weapon": "Foil",
            },
            {
                "id": "r2",
                "tournament_id": "t2",
                "fencer_id": BOB,
                "rank": 5,
                "weapon": "Foil",
            },
        ],
        "tournaments": [
            {
                "id": "t1",
                "name": "Grand Prix Alpha",
                "weapon": "Foil",
                "end_date": "2026-05-01",
                "season": "2025-2026",
            },
            {
                "id": "t2",
                "name": "World Cup Beta",
                "weapon": "Foil",
                "end_date": "2026-04-12",
                "season": "2025-2026",
            },
        ],
    }


def assert_summary_is_grounded(row):
    sentences = row["evidence_json"]["sentences"]
    sentence_texts = [item["text"] for item in sentences]

    assert row["summary"] == " ".join(sentence_texts)
    assert sentence_texts
    for sentence in sentences:
        assert sentence["sources"]
        assert isinstance(sentence["values"], dict)

    unsupported_terms = (" will ", " projected ", " injury", " medical", " private")
    lower_summary = f" {row['summary'].lower()} "
    for term in unsupported_terms:
        assert term not in lower_summary


def test_ai_insights_migration_defines_evidence_backed_storage():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_ai_insights.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_ai_insights" in normalized
    assert "entity_type text not null" in normalized
    assert "entity_id text not null" in normalized
    assert "insight_type text not null" in normalized
    assert "summary text not null" in normalized
    assert "evidence_json jsonb not null" in normalized
    assert "confidence" in normalized
    assert "provider text" in normalized
    assert "model text" in normalized
    assert "rule_version text" in normalized
    assert "generated_at timestamptz not null" in normalized
    assert "metadata jsonb not null" in normalized
    assert "unique (entity_type, entity_id, insight_type)" in normalized
    assert "alter table public.fs_ai_insights enable row level security" in normalized
    assert "drop table" not in normalized
    assert "truncate" not in normalized


def test_template_performance_summary_is_deterministic_and_evidence_backed():
    from compute_ai_insights import build_ai_insight_rows

    rows, skipped = build_ai_insight_rows(fixture_source_data(), generated_at=NOW)
    summary = next(
        row
        for row in rows
        if row["entity_type"] == "fencer"
        and row["entity_id"] == ALICE
        and row["insight_type"] == "performance_summary"
    )

    assert skipped == {"performance_summaries": 0, "comparisons": 0}
    assert summary["provider"] == "rules"
    assert summary["model"] is None
    assert summary["rule_version"] == "ai_insights_rules_v1"
    assert summary["generated_at"] == NOW
    assert 0.0 <= summary["confidence"] <= 1.0
    assert "Ari Park has 12 recorded competitions, 3 gold medals, 1 silver medal, 2 bronze medals, and 9 top-eight finishes." in summary["summary"]
    assert "In Foil, recorded performance delta is +2.50 with a 75.00% overperformance rate across 8 competitions." in summary["summary"]
    assert "Latest ranking evidence for Foil Women's Senior is season 2025 rank 4, marked up from previous rank 6." in summary["summary"]
    assert "Most recent recorded result is rank 1 at Grand Prix Alpha on 2026-05-01." in summary["summary"]
    assert summary["evidence_json"]["source_tables"] == [
        "fs_fencers",
        "fs_fencer_career_stats",
        "fs_fencer_performance_analysis",
        "fs_rankings_trends",
        "fs_results",
        "fs_tournaments",
    ]
    assert_summary_is_grounded(summary)


def test_fencer_comparison_uses_h2h_stats_rankings_and_recent_results():
    from compute_ai_insights import build_ai_insight_rows

    rows, skipped = build_ai_insight_rows(fixture_source_data(), generated_at=NOW)
    comparison = next(
        row
        for row in rows
        if row["entity_type"] == "fencer_pair"
        and row["insight_type"] == "fencer_comparison"
    )

    assert skipped == {"performance_summaries": 0, "comparisons": 0}
    assert comparison["entity_id"] == f"{ALICE}:{BOB}:Foil"
    assert "Ari Park and Bea Rossi have 5 recorded Foil head-to-head bouts; Ari Park leads 3-2." in comparison["summary"]
    assert "Touch evidence in those bouts is 70-64 for Ari Park." in comparison["summary"]
    assert "Their last recorded meeting was on 2026-04-20, won by Bea Rossi." in comparison["summary"]
    assert "Career evidence lists Ari Park with 12 competitions and 9 top-eight finishes, while Bea Rossi has 10 competitions and 7 top-eight finishes." in comparison["summary"]
    assert "Latest ranking evidence puts Ari Park at Foil Women's Senior season 2025 rank 4 and Bea Rossi at Foil Women's Senior season 2025 rank 7." in comparison["summary"]
    assert "Most recent dated results are Ari Park rank 1 at Grand Prix Alpha on 2026-05-01 and Bea Rossi rank 5 at World Cup Beta on 2026-04-12." in comparison["summary"]
    assert "fs_head_to_head" in comparison["evidence_json"]["source_tables"]
    assert_summary_is_grounded(comparison)


def test_comparison_normalizes_mixed_weapon_labels_for_ranking_and_recent_results():
    from compute_ai_insights import build_ai_insight_rows

    data = fixture_source_data()
    data["ranking_trends"][0]["weapon"] = "foil"
    data["ranking_trends"][1]["weapon"] = "FOIL"
    data["results"][0]["weapon"] = "f"
    data["results"][1]["weapon"] = "foil"

    rows, skipped = build_ai_insight_rows(data, generated_at=NOW)
    comparison = next(
        row
        for row in rows
        if row["entity_type"] == "fencer_pair"
        and row["insight_type"] == "fencer_comparison"
    )

    assert skipped == {"performance_summaries": 0, "comparisons": 0}
    assert "Latest ranking evidence puts Ari Park at Foil Women's Senior season 2025 rank 4 and Bea Rossi at Foil Women's Senior season 2025 rank 7." in comparison["summary"]
    assert "Most recent dated results are Ari Park rank 1 at Grand Prix Alpha on 2026-05-01 and Bea Rossi rank 5 at World Cup Beta on 2026-04-12." in comparison["summary"]
    assert_summary_is_grounded(comparison)


def test_unsupported_data_skips_insights_without_unfounded_summary():
    from compute_ai_insights import build_ai_insight_rows

    rows, skipped = build_ai_insight_rows(
        {
            "fencers": [{"id": SPARSE, "name": "Sparse Fencer"}],
            "career_stats": [],
            "performance": [],
            "ranking_trends": [],
            "head_to_head": [
                {
                    "fencer_a_id": SPARSE,
                    "fencer_b_id": BOB,
                    "weapon": "Foil",
                    "a_wins": 0,
                    "b_wins": 0,
                    "a_touches": 0,
                    "b_touches": 0,
                    "bouts_total": 0,
                }
            ],
            "results": [],
            "tournaments": [],
        },
        generated_at=NOW,
    )

    assert rows == []
    assert skipped == {"performance_summaries": 1, "comparisons": 1}


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.start = 0
        self.end = None
        self.pending_upsert = None
        self.pending_conflict = None

    def select(self, columns):
        self.client.selects.append((self.table_name, columns))
        return self

    def order(self, column, desc=False):
        self.client.orders.append((self.table_name, column, desc))
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
            return FakeResult(self.pending_upsert)

        rows = list(self.client.tables.get(self.table_name, []))
        end = self.end + 1 if self.end is not None else None
        return FakeResult(rows[self.start:end])


class FakeSupabase:
    def __init__(self):
        data = fixture_source_data()
        self.tables = {
            "fs_fencers": data["fencers"],
            "fs_fencer_career_stats": data["career_stats"],
            "fs_fencer_performance_analysis": data["performance"],
            "fs_rankings_trends": data["ranking_trends"],
            "fs_head_to_head": data["head_to_head"],
            "fs_results": data["results"],
            "fs_tournaments": data["tournaments"],
        }
        self.selects = []
        self.orders = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


class FakeProvider:
    def __init__(self):
        self.calls = []

    def generate(self, rows):
        self.calls.append(rows)
        return rows


def test_compute_ai_insights_reads_existing_outputs_and_upserts_by_cache_key():
    from compute_ai_insights import INSIGHT_CONFLICT_COLUMNS, compute_ai_insights

    client = FakeSupabase()

    summary = compute_ai_insights(
        client=client,
        log_run=False,
        update_state=False,
        generated_at=NOW,
    )

    selected_tables = {table for table, _columns in client.selects}
    assert {
        "fs_fencers",
        "fs_fencer_career_stats",
        "fs_fencer_performance_analysis",
        "fs_rankings_trends",
        "fs_head_to_head",
        "fs_results",
        "fs_tournaments",
    }.issubset(selected_tables)
    assert summary["provider_used"] is False
    assert summary["insights_built"] == 3
    assert summary["written"] == 3
    assert len(client.upserts) == 1
    assert client.upserts[0]["table"] == "fs_ai_insights"
    assert client.upserts[0]["on_conflict"] == INSIGHT_CONFLICT_COLUMNS
    assert client.upserts[0]["on_conflict"] == "entity_type,entity_id,insight_type"


def test_provider_generation_is_dry_run_and_not_called_without_approval():
    from compute_ai_insights import compute_ai_insights

    client = FakeSupabase()
    provider = FakeProvider()

    summary = compute_ai_insights(
        client=client,
        provider=provider,
        provider_dry_run=True,
        log_run=False,
        update_state=False,
        generated_at=NOW,
    )

    assert provider.calls == []
    assert summary["provider_used"] is False
    assert summary["provider_dry_run"] is True
    assert client.upserts[0]["rows"][0]["metadata"]["generation_mode"] == "rules"

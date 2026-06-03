import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


ROOT = Path(__file__).resolve().parents[1]


def test_equipment_trends_migration_defines_evidence_and_aggregate_tables():
    sql_path = ROOT / "supabase" / "migrations" / "20260602_equipment_trends.sql"
    sql = " ".join(sql_path.read_text().lower().split())

    assert "create table if not exists public.fs_equipment_trend_evidence" in sql
    assert "create table if not exists public.fs_equipment_trends" in sql
    for column in (
        "brand text not null",
        "equipment_category text not null",
        "weapon text not null",
        "event_tier text",
        "fencer_id uuid references public.fs_fencers(id)",
        "result_id uuid",
        "source text not null",
        "confidence text not null",
        "updated_at timestamptz",
    ):
        assert column in sql
    assert "check (confidence in ('high', 'medium', 'low'))" in sql
    assert "on public.fs_equipment_trend_evidence (brand, weapon, event_tier)" in sql
    assert "on public.fs_equipment_trends (brand, equipment_category, weapon, event_tier)" in sql


def test_extracts_only_explicit_public_profile_equipment_evidence():
    from scrape_equipment_trends import build_brand_catalog, extract_profile_evidence

    text = """
    <html><body>
      <h1>Lee Kiefer</h1>
      <p>Lee Kiefer is sponsored by Absolute Fencing.</p>
      <p>She wears a Leon Paul mask and uses a PBT blade in competition.</p>
    </body></html>
    """

    mentions = extract_profile_evidence(
        text,
        fencer_name="Lee Kiefer",
        source="fie_profile",
        source_url="https://fie.org/athletes/123",
        brand_catalog=build_brand_catalog(product_rows=[]),
    )

    assert [(m.brand, m.equipment_category, m.confidence) for m in mentions] == [
        ("Absolute Fencing", "sponsor", "high"),
        ("Leon Paul", "mask", "medium"),
        ("PBT", "weapon", "medium"),
    ]
    assert all(m.source == "fie_profile" for m in mentions)


def test_profile_parser_rejects_ambiguous_brand_mentions_without_equipment_signal():
    from scrape_equipment_trends import build_brand_catalog, extract_profile_evidence

    text = (
        "Lee Kiefer attended the Allstar Challenge and said OK after warmups. "
        "Lee Kiefer later selected a PBT blade for the final."
    )

    mentions = extract_profile_evidence(
        text,
        fencer_name="Lee Kiefer",
        source="fie_profile",
        source_url="https://fie.org/athletes/123",
        brand_catalog=build_brand_catalog(product_rows=[]),
    )

    assert [(m.brand, m.equipment_category) for m in mentions] == [("PBT", "weapon")]


def test_brand_normalization_uses_sponsor_aliases_and_product_rows():
    from scrape_equipment_trends import build_brand_catalog, normalize_brand

    catalog = build_brand_catalog(
        product_rows=[
            {"brand": "Leon Paul"},
            {"brand": "Blue Gauntlet"},
            {"brand": "Allstar"},
        ]
    )

    assert normalize_brand("LP", catalog) == "Leon Paul"
    assert normalize_brand("leon paul usa", catalog) == "Leon Paul"
    assert normalize_brand("Allstar Uhlmann", catalog) == "Allstar"
    assert normalize_brand("Blaise Freres", catalog) == "Blaise Frères"
    assert normalize_brand("unknown maker", catalog) == "Unknown Maker"


def test_build_evidence_rows_joins_equipment_to_results_and_preserves_sources():
    from scrape_equipment_trends import build_brand_catalog, build_evidence_rows

    equipment_rows = [
        {
            "id": "eq-1",
            "fencer_id": "fencer-1",
            "brand": "LP",
            "equipment_type": "mask",
            "source": "fie_profile",
            "source_url": "https://fie.org/athletes/123",
            "confidence": "high",
            "metadata": {"context": "Lee Kiefer wears a Leon Paul mask."},
        },
        {
            "id": "eq-low",
            "fencer_id": "fencer-1",
            "brand": "Allstar",
            "equipment_type": None,
            "source": "fie_profile",
            "source_url": "https://fie.org/athletes/123",
            "confidence": "low",
            "metadata": {"context": "Allstar Challenge mention only."},
        },
    ]
    fencers = [
        {"id": "fencer-1", "name": "Lee Kiefer", "fie_id": "123", "country": "USA", "weapon": "foil"}
    ]
    results = [
        {
            "id": "result-1",
            "tournament_id": "tournament-1",
            "fencer_id": "fencer-1",
            "rank": 1,
            "name": "Lee Kiefer",
            "nationality": "USA",
        }
    ]
    tournaments = [
        {
            "id": "tournament-1",
            "name": "Cairo Foil World Cup",
            "weapon": "Foil",
            "type": "World Cup",
            "category": "Senior",
        }
    ]

    rows, skipped = build_evidence_rows(
        equipment_rows,
        fencers,
        results,
        tournaments,
        brand_catalog=build_brand_catalog(product_rows=[]),
        updated_at="2026-06-02T12:00:00+00:00",
    )

    assert skipped == 1
    assert len(rows) == 1
    row = rows[0]
    assert row["brand"] == "Leon Paul"
    assert row["equipment_category"] == "mask"
    assert row["weapon"] == "Foil"
    assert row["event_tier"] == "World Cup"
    assert row["fencer_id"] == "fencer-1"
    assert row["result_id"] == "result-1"
    assert row["result_rank"] == 1
    assert row["source"] == "fie_profile"
    assert row["confidence"] == "high"
    assert row["updated_at"] == "2026-06-02T12:00:00+00:00"
    assert row["metadata"]["equipment_evidence_id"] == "eq-1"


def test_build_evidence_rows_matches_by_fie_id_and_name_country_when_result_fencer_id_missing():
    from scrape_equipment_trends import build_brand_catalog, build_evidence_rows

    equipment_rows = [
        {
            "id": "eq-1",
            "fencer_id": "fencer-1",
            "brand": "PBT",
            "equipment_type": "weapon",
            "source": "federation_profile",
            "confidence": "medium",
            "metadata": {},
        }
    ]
    fencers = [{"id": "fencer-1", "name": "Lee Kiefer", "fie_id": "123", "country": "USA"}]
    results = [
        {
            "id": "result-1",
            "tournament_id": "tournament-1",
            "fie_fencer_id": 123,
            "name": "KIEFER Lee",
            "nationality": "USA",
            "rank": 2,
        },
        {
            "id": "result-2",
            "tournament_id": "tournament-1",
            "name": "Lee Kiefer",
            "country": "USA",
            "rank": 5,
        },
    ]
    tournaments = [{"id": "tournament-1", "weapon": "Foil", "type": "Grand Prix"}]

    rows, skipped = build_evidence_rows(
        equipment_rows,
        fencers,
        results,
        tournaments,
        brand_catalog=build_brand_catalog(product_rows=[]),
        updated_at="2026-06-02T12:00:00+00:00",
    )

    assert skipped == 0
    assert [row["result_id"] for row in rows] == ["result-1", "result-2"]
    assert all(row["brand"] == "PBT" for row in rows)
    assert all(row["weapon"] == "Foil" for row in rows)


def test_build_evidence_rows_accepts_rate_limited_profile_evidence_sources():
    from scrape_equipment_trends import (
        ProfileEquipmentEvidence,
        build_brand_catalog,
        build_evidence_rows,
        profile_evidence_to_source,
    )

    fencer = {"id": "fencer-1", "name": "Lee Kiefer", "country": "USA", "weapon": "Foil"}
    profile_source = profile_evidence_to_source(
        fencer,
        ProfileEquipmentEvidence(
            brand="Leon Paul",
            equipment_category="mask",
            source="fie_profile",
            source_url="https://fie.org/athletes/123",
            confidence="high",
            metadata={"context": "Lee Kiefer wears a Leon Paul mask."},
        ),
    )

    rows, skipped = build_evidence_rows(
        [profile_source],
        [fencer],
        [
            {
                "id": "result-1",
                "tournament_id": "tournament-1",
                "fencer_id": "fencer-1",
                "rank": 1,
                "name": "Lee Kiefer",
                "nationality": "USA",
            }
        ],
        [{"id": "tournament-1", "weapon": "Foil", "type": "World Cup"}],
        brand_catalog=build_brand_catalog(product_rows=[]),
        updated_at="2026-06-02T12:00:00+00:00",
    )

    assert skipped == 0
    assert len(rows) == 1
    assert rows[0]["equipment_category"] == "mask"
    assert rows[0]["metadata"]["equipment_evidence_id"] == profile_source["equipment_evidence_id"]


def test_aggregate_trends_counts_brand_wins_by_weapon_and_preserves_confidence():
    from scrape_equipment_trends import aggregate_trend_rows

    evidence_rows = [
        {
            "brand": "Leon Paul",
            "equipment_category": "mask",
            "weapon": "Foil",
            "event_tier": "World Cup",
            "result_id": "result-1",
            "result_rank": 1,
            "source": "fie_profile",
            "confidence": "high",
        },
        {
            "brand": "Leon Paul",
            "equipment_category": "mask",
            "weapon": "Foil",
            "event_tier": "World Cup",
            "result_id": "result-2",
            "result_rank": 5,
            "source": "federation_profile",
            "confidence": "medium",
        },
        {
            "brand": "PBT",
            "equipment_category": "weapon",
            "weapon": "Epee",
            "event_tier": "Grand Prix",
            "result_id": "result-3",
            "result_rank": 3,
            "source": "fie_profile",
            "confidence": "medium",
        },
    ]

    rows = aggregate_trend_rows(evidence_rows, updated_at="2026-06-02T12:00:00+00:00")
    by_brand_weapon = {(row["brand"], row["weapon"]): row for row in rows}

    leon = by_brand_weapon[("Leon Paul", "Foil")]
    assert leon["evidence_count"] == 2
    assert leon["result_count"] == 2
    assert leon["win_count"] == 1
    assert leon["podium_count"] == 1
    assert leon["top8_count"] == 2
    assert leon["confidence"] == "high"
    assert leon["sources"] == ["federation_profile", "fie_profile"]

    pbt = by_brand_weapon[("PBT", "Epee")]
    assert pbt["win_count"] == 0
    assert pbt["podium_count"] == 1
    assert pbt["confidence"] == "medium"


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.upsert_calls = []
        self.select_columns = []

    def select(self, columns):
        self.select_columns.append(columns)
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def upsert(self, payload, on_conflict=None):
        self.upsert_calls.append((payload, on_conflict))
        return self

    def execute(self):
        return FakeResult(self.rows)


class FakeClient:
    def __init__(self, tables):
        self.tables = {name: FakeTable(rows) for name, rows in tables.items()}

    def table(self, name):
        if name not in self.tables:
            self.tables[name] = FakeTable([])
        return self.tables[name]


def test_run_writes_evidence_and_aggregate_rows_or_no_public_data_stub(monkeypatch):
    from scrape_equipment_trends import run

    client = FakeClient(
        {
            "fs_fencer_equipment": [
                {
                    "id": "eq-1",
                    "fencer_id": "fencer-1",
                    "brand": "Leon Paul",
                    "equipment_type": "mask",
                    "source": "fie_profile",
                    "source_url": "https://fie.org/athletes/123",
                    "confidence": "high",
                    "metadata": {},
                }
            ],
            "fs_equipment_reviews": [{"brand": "Leon Paul", "category": "Masks"}],
            "fs_fencers": [{"id": "fencer-1", "name": "Lee Kiefer", "country": "USA", "weapon": "Foil"}],
            "fs_results": [
                {
                    "id": "result-1",
                    "tournament_id": "tournament-1",
                    "fencer_id": "fencer-1",
                    "rank": 1,
                    "name": "Lee Kiefer",
                    "nationality": "USA",
                }
            ],
            "fs_tournaments": [{"id": "tournament-1", "weapon": "Foil", "type": "World Cup"}],
        }
    )
    monkeypatch.setattr("scrape_equipment_trends.get_state", lambda *_args: None)
    states = []
    monkeypatch.setattr("scrape_equipment_trends.set_state", lambda *args: states.append(args))

    summary = run(client=client, log_run=False, updated_at="2026-06-02T12:00:00+00:00")

    assert summary["evidence_rows_found"] == 1
    assert summary["trend_rows_found"] == 1
    assert summary["written"] == 2
    assert client.tables["fs_equipment_trend_evidence"].upsert_calls[0][1] == "id"
    assert client.tables["fs_equipment_trends"].upsert_calls[0][1] == "id"
    assert states[-1][0:2] == ("scrape_equipment_trends", "last_run")

    empty_client = FakeClient(
        {
            "fs_fencer_equipment": [],
            "fs_equipment_reviews": [],
            "fs_fencers": [],
            "fs_results": [],
            "fs_tournaments": [],
        }
    )
    summary = run(client=empty_client, log_run=False, updated_at="2026-06-02T12:00:00+00:00")

    assert summary["status"] == "no_public_data"
    assert summary["written"] == 0
    assert empty_client.tables["fs_equipment_trend_evidence"].upsert_calls == []
    assert empty_client.tables["fs_equipment_trends"].upsert_calls == []

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-06-02T12:00:00+00:00"


def test_build_durability_rows_uses_dated_public_evidence_and_brand_change_estimate():
    from compute_equipment_durability import build_durability_rows

    equipment_rows = [
        {
            "id": "eq-1",
            "fencer_id": "fencer-1",
            "brand": "LP",
            "equipment_type": "mask",
            "source": "fie_profile",
            "source_url": "https://fie.org/athletes/123",
            "confidence": "high",
            "metadata": {
                "observed_date": "2023-01-01",
                "context": "Lee Kiefer wears a Leon Paul mask.",
            },
        },
        {
            "id": "eq-2",
            "fencer_id": "fencer-1",
            "brand": "Leon Paul",
            "equipment_type": "mask",
            "source": "federation_profile",
            "source_url": "https://www.usafencing.org/lee-kiefer",
            "confidence": "medium",
            "metadata": {"observed_at": "2023-07-01T09:00:00Z"},
        },
        {
            "id": "eq-3",
            "fencer_id": "fencer-1",
            "brand": "Allstar Uhlmann",
            "equipment_type": "mask",
            "source": "sponsor_release",
            "source_url": "https://example.test/allstar-announcement",
            "confidence": "high",
            "metadata": {"published_at": "2024-01-01"},
        },
    ]

    rows = build_durability_rows(equipment_rows, [], computed_at=NOW)
    by_key = {(row["brand"], row["equipment_type"], row["fencer_id"]): row for row in rows}

    leon = by_key[("Leon Paul", "mask", "fencer-1")]
    assert leon["observed_first_date"] == "2023-01-01"
    assert leon["observed_last_date"] == "2023-07-01"
    assert leon["replacement_interval_estimate"] == 365
    assert leon["evidence_count"] == 2
    assert leon["confidence"] == "high"
    assert leon["computed_at"] == NOW
    assert leon["metadata"]["estimate_basis"] == "public_brand_change"
    assert leon["metadata"]["next_observed_brand"] == "Allstar"
    assert leon["metadata"]["replacement_gap_days"] == 184
    assert leon["metadata"]["evidence_links"] == [
        "https://fie.org/athletes/123",
        "https://www.usafencing.org/lee-kiefer",
    ]
    assert "private replacement" not in repr(leon["metadata"]).lower()

    assert ("Allstar", "mask", "fencer-1") not in by_key
    allstar_aggregate = by_key[("Allstar", "mask", None)]
    assert allstar_aggregate["confidence"] == "low"
    assert allstar_aggregate["replacement_interval_estimate"] is None
    assert allstar_aggregate["metadata"]["estimate_basis"] == "aggregate_public_evidence_only"


def test_sparse_fencer_evidence_emits_aggregate_low_confidence_summary_only():
    from compute_equipment_durability import build_durability_rows

    equipment_rows = [
        {
            "id": "eq-1",
            "fencer_id": "fencer-2",
            "brand": "AF",
            "equipment_type": "lame",
            "source": "fie_profile",
            "source_url": "https://fie.org/athletes/456",
            "confidence": "medium",
            "metadata": {"observed_date": "2024-03-15"},
        }
    ]
    review_rows = [
        {
            "id": "review-1",
            "brand": "Absolute Fencing",
            "category": "Lames",
            "url": "https://www.absolutefencinggear.com/lame",
            "review_count": 12,
            "scraped_at": "2024-04-01T00:00:00+00:00",
        }
    ]

    rows = build_durability_rows(equipment_rows, review_rows, computed_at=NOW)

    assert [row for row in rows if row["fencer_id"] == "fencer-2"] == []
    aggregate = rows[0]
    assert aggregate["brand"] == "Absolute Fencing"
    assert aggregate["equipment_type"] == "jacket"
    assert aggregate["fencer_id"] is None
    assert aggregate["observed_first_date"] == "2024-03-15"
    assert aggregate["observed_last_date"] == "2024-04-01"
    assert aggregate["replacement_interval_estimate"] is None
    assert aggregate["evidence_count"] == 2
    assert aggregate["confidence"] == "low"
    assert aggregate["metadata"]["warning"] == "estimate_not_private_replacement_behavior"
    assert aggregate["metadata"]["evidence_links"] == [
        "https://fie.org/athletes/456",
        "https://www.absolutefencinggear.com/lame",
    ]


def test_undated_or_singleton_evidence_is_marked_insufficient_without_interval():
    from compute_equipment_durability import build_durability_rows

    rows = build_durability_rows(
        [
            {
                "id": "eq-undated",
                "fencer_id": "fencer-3",
                "brand": "PBT",
                "equipment_type": "weapon",
                "source": "profile",
                "source_url": "https://example.test/pbt",
                "confidence": "high",
                "metadata": {"context": "No date here."},
            },
            {
                "id": "eq-dated",
                "fencer_id": "fencer-4",
                "brand": "PBT",
                "equipment_type": "weapon",
                "source": "profile",
                "source_url": "https://example.test/pbt-dated",
                "confidence": "medium",
                "metadata": {"source_date": "2025-05-10"},
            },
        ],
        [],
        computed_at=NOW,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["brand"] == "PBT"
    assert row["equipment_type"] == "weapon"
    assert row["fencer_id"] is None
    assert row["observed_first_date"] == "2025-05-10"
    assert row["replacement_interval_estimate"] is None
    assert row["confidence"] == "insufficient"
    assert row["evidence_count"] == 1
    assert row["metadata"]["skipped_undated_evidence_count"] == 1


def test_brand_and_equipment_normalization_use_aliases_and_review_categories():
    from compute_equipment_durability import normalize_brand, normalize_equipment_type

    assert normalize_brand("LP") == "Leon Paul"
    assert normalize_brand("leon paul usa") == "Leon Paul"
    assert normalize_brand("Allstar Uhlmann") == "Allstar"
    assert normalize_brand("Blaise Freres") == "Blaise Frères"
    assert normalize_brand("unknown maker") == "Unknown Maker"

    assert normalize_equipment_type("lame") == "jacket"
    assert normalize_equipment_type("Electric Jackets") == "jacket"
    assert normalize_equipment_type("FIE foil blades") == "weapon"
    assert normalize_equipment_type("Masks") == "mask"
    assert normalize_equipment_type(None, sponsor_name="Absolute Fencing") == "sponsor"


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


def test_compute_equipment_durability_upserts_rows_and_updates_state(monkeypatch):
    from compute_equipment_durability import compute_equipment_durability

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
                    "metadata": {"observed_date": "2023-01-01"},
                },
                {
                    "id": "eq-2",
                    "fencer_id": "fencer-1",
                    "brand": "Allstar",
                    "equipment_type": "mask",
                    "source": "sponsor_release",
                    "source_url": "https://example.test/allstar",
                    "confidence": "high",
                    "metadata": {"observed_date": "2024-01-01"},
                },
            ],
            "fs_equipment_reviews": [],
        }
    )
    states = []
    monkeypatch.setattr("compute_equipment_durability.get_state", lambda *_args: None)
    monkeypatch.setattr("compute_equipment_durability.set_state", lambda *args: states.append(args))

    summary = compute_equipment_durability(client=client, log_run=False, computed_at=NOW)

    assert summary["equipment_rows_read"] == 2
    assert summary["review_rows_read"] == 0
    assert summary["durability_rows_found"] == 2
    assert summary["written"] == 2
    assert summary["failed"] == 0
    upsert_payload, conflict = client.tables["fs_equipment_durability"].upsert_calls[0]
    assert conflict == "id"
    assert {row["brand"] for row in upsert_payload} == {"Leon Paul", "Allstar"}
    assert states[-1][0:2] == ("compute_equipment_durability", "last_run")
    assert states[-1][2]["written"] == 2


def test_equipment_durability_migration_defines_estimate_table_and_constraints():
    migration = ROOT / "supabase" / "migrations" / "20260602_equipment_durability.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_equipment_durability" in normalized
    assert "brand text not null" in normalized
    assert "equipment_type text not null" in normalized
    assert "fencer_id uuid references public.fs_fencers(id)" in normalized
    assert "observed_first_date date" in normalized
    assert "observed_last_date date" in normalized
    assert "replacement_interval_estimate integer" in normalized
    assert "evidence_count integer not null default 0" in normalized
    assert "confidence text not null" in normalized
    assert "metadata jsonb default '{}'" in normalized
    assert "check (confidence in ('high', 'medium', 'low', 'insufficient'))" in normalized
    assert "enable row level security" in normalized
    assert "grant select, insert, update, delete on public.fs_equipment_durability to service_role" in normalized
    assert "on public.fs_equipment_durability (brand, equipment_type, fencer_id)" in normalized

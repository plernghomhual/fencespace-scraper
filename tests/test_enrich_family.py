import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


SIBLING_BINDING = {
    "athlete": {"value": "http://www.wikidata.org/entity/QATHLETE"},
    "athleteLabel": {"value": "Source Fencer"},
    "fie_id": {"value": "12345"},
    "relationship": {"value": "sibling"},
    "property": {"value": "P3373"},
    "related": {"value": "http://www.wikidata.org/entity/QSIBLING"},
    "relatedLabel": {"value": "Sibling Fencer"},
    "statement": {"value": "http://www.wikidata.org/entity/statement/QATHLETE-111"},
}

FATHER_BINDING = {
    "athlete": {"value": "https://www.wikidata.org/wiki/QATHLETE"},
    "athleteLabel": {"value": "Source Fencer"},
    "relationship": {"value": "parent"},
    "property": {"value": "P22"},
    "related": {"value": "http://www.wikidata.org/entity/QPARENT"},
    "relatedLabel": {"value": "Parent Person"},
    "statement": {"value": "http://www.wikidata.org/entity/statement/QATHLETE-222"},
}


def fencer(row_id, name, wikidata_id=None):
    metadata = {}
    if wikidata_id:
        metadata["wikidata_id"] = wikidata_id
    return {
        "id": row_id,
        "fie_id": None,
        "name": name,
        "metadata": metadata,
    }


def test_migration_creates_family_relationships_shape_and_unique_key():
    sql = Path("supabase/migrations/20260602_family.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS public.fs_fencer_family_relationships" in sql
    for column in (
        "fencer_id",
        "fencer_identity_id",
        "fencer_wikidata_id",
        "related_name",
        "relationship_type",
        "related_wikidata_id",
        "related_fencer_id",
        "source",
        "confidence",
        "metadata",
    ):
        assert column in sql
    assert "CHECK (relationship_type IN ('sibling', 'parent', 'spouse', 'child', 'relative'))" in sql
    assert "UNIQUE (fencer_id, relationship_type, source, relationship_key)" in sql
    assert "REFERENCES public.fs_fencers(id)" in sql


def test_build_family_claims_normalizes_public_wikidata_bindings_and_dedupes():
    from enrich_family import build_family_claims

    claims = build_family_claims([SIBLING_BINDING, dict(SIBLING_BINDING), FATHER_BINDING])

    assert claims == [
        {
            "fencer_wikidata_id": "QATHLETE",
            "fencer_name": "Source Fencer",
            "fie_id": "12345",
            "relationship_type": "sibling",
            "related_wikidata_id": "QSIBLING",
            "related_name": "Sibling Fencer",
            "wikidata_property": "P3373",
            "wikidata_statement": "QATHLETE-111",
        },
        {
            "fencer_wikidata_id": "QATHLETE",
            "fencer_name": "Source Fencer",
            "fie_id": None,
            "relationship_type": "parent",
            "related_wikidata_id": "QPARENT",
            "related_name": "Parent Person",
            "wikidata_property": "P22",
            "wikidata_statement": "QATHLETE-222",
        },
    ]


def test_build_relationship_rows_links_by_exact_wikidata_id_and_expands_identity():
    from enrich_family import build_family_claims, build_relationship_rows

    fencers = [
        fencer("00000000-0000-0000-0000-000000000001", "Source Fencer", "QATHLETE"),
        fencer("00000000-0000-0000-0000-000000000002", "Source Fencer", "QATHLETE"),
        fencer("00000000-0000-0000-0000-000000000003", "Sibling Fencer", "QSIBLING"),
    ]
    identities = [
        {
            "id": "10000000-0000-0000-0000-000000000001",
            "fs_fencer_row_ids": [
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
            ],
        }
    ]

    rows = build_relationship_rows(build_family_claims([SIBLING_BINDING]), fencers, identities)

    assert [row["fencer_id"] for row in rows] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ]
    assert {row["fencer_identity_id"] for row in rows} == {"10000000-0000-0000-0000-000000000001"}
    assert {row["related_fencer_id"] for row in rows} == {"00000000-0000-0000-0000-000000000003"}
    assert {row["related_wikidata_id"] for row in rows} == {"QSIBLING"}
    assert {row["relationship_type"] for row in rows} == {"sibling"}
    assert {row["confidence"] for row in rows} == {1.0}
    assert rows[0]["metadata"]["related_match_status"] == "matched"
    assert "birth_date" not in rows[0]["metadata"]


def test_build_relationship_rows_does_not_link_by_name_only():
    from enrich_family import build_family_claims, build_relationship_rows

    binding = dict(SIBLING_BINDING)
    binding["related"] = {"value": "http://www.wikidata.org/entity/QUNMATCHED"}
    fencers = [
        fencer("00000000-0000-0000-0000-000000000001", "Source Fencer", "QATHLETE"),
        fencer("00000000-0000-0000-0000-000000000004", "Sibling Fencer", None),
    ]

    rows = build_relationship_rows(build_family_claims([binding]), fencers, [])

    assert len(rows) == 1
    assert rows[0]["related_name"] == "Sibling Fencer"
    assert rows[0]["related_wikidata_id"] == "QUNMATCHED"
    assert rows[0]["related_fencer_id"] is None
    assert rows[0]["metadata"]["related_match_status"] == "unmatched"


def test_ambiguous_related_wikidata_match_is_left_unlinked():
    from enrich_family import build_family_claims, build_relationship_rows

    fencers = [
        fencer("00000000-0000-0000-0000-000000000001", "Source Fencer", "QATHLETE"),
        fencer("00000000-0000-0000-0000-000000000005", "Sibling Fencer A", "QSIBLING"),
        fencer("00000000-0000-0000-0000-000000000006", "Sibling Fencer B", "QSIBLING"),
    ]

    rows = build_relationship_rows(build_family_claims([SIBLING_BINDING]), fencers, [])

    assert len(rows) == 1
    assert rows[0]["related_fencer_id"] is None
    assert rows[0]["related_fencer_identity_id"] is None
    assert rows[0]["confidence"] == 0.95
    assert rows[0]["metadata"]["related_match_status"] == "ambiguous_wikidata_match"
    assert rows[0]["metadata"]["related_match_candidate_count"] == 2


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.range_bounds = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        return self

    def range(self, start, end):
        self.range_bounds = (start, end)
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.client.upserts.append(
            {
                "table": self.name,
                "rows": rows,
                "on_conflict": on_conflict,
            }
        )
        return self

    def execute(self):
        if self.operation == "upsert":
            return FakeResult([])
        if self.operation == "select":
            rows = self.client.tables.get(self.name, [])
            if self.range_bounds:
                start, end = self.range_bounds
                rows = rows[start : end + 1]
            return FakeResult(rows)
        raise AssertionError(f"unexpected operation {self.operation} for {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_enrich_family_upserts_idempotent_rows_with_conflict_key():
    from enrich_family import enrich_family_relationships

    client = FakeSupabase(
        {
            "fs_fencers": [
                fencer("00000000-0000-0000-0000-000000000001", "Source Fencer", "QATHLETE"),
                fencer("00000000-0000-0000-0000-000000000003", "Sibling Fencer", "QSIBLING"),
            ],
            "fs_fencer_identities": [],
        }
    )

    summary = enrich_family_relationships(
        client=client,
        bindings=[SIBLING_BINDING],
        log_run=False,
        update_state=False,
    )

    assert summary == {
        "claims_found": 1,
        "relationships_built": 1,
        "written": 1,
        "failed": 0,
        "skipped": 0,
    }
    assert len(client.upserts) == 1
    assert client.upserts[0]["table"] == "fs_fencer_family_relationships"
    assert client.upserts[0]["on_conflict"] == "fencer_id,relationship_type,source,relationship_key"
    assert client.upserts[0]["rows"][0]["related_fencer_id"] == "00000000-0000-0000-0000-000000000003"

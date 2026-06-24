import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

IDENTITY_ID = "00000000-0000-0000-0000-000000000101"
SECOND_IDENTITY_ID = "00000000-0000-0000-0000-000000000102"
FENCER_ROW_A = "00000000-0000-0000-0000-000000000201"
FENCER_ROW_B = "00000000-0000-0000-0000-000000000202"
FENCER_ROW_C = "00000000-0000-0000-0000-000000000203"


def test_detect_script_covers_supported_scripts_and_other():
    from compute_name_variants import detect_script

    assert detect_script("Lee Kiefer") == "Latin"
    assert detect_script("E\u0301lodie Clément") == "Latin"
    assert detect_script("윤지수") == "Hangul"
    assert detect_script("江村 美咲") == "CJK"
    assert detect_script("Софья Великая") == "Cyrillic"
    assert detect_script("علاء أبو القاسم") == "Arabic"
    assert detect_script("かな") == "Other"
    assert detect_script("12345 -") == "Other"


def test_build_name_variants_groups_multi_script_names_by_identity():
    from compute_name_variants import build_name_variants

    identities: list[dict[str, Any]] = [
        {
            "id": IDENTITY_ID,
            "country": "KOR",
            "fie_ids": ["123"],
            "fs_fencer_row_ids": [FENCER_ROW_A, FENCER_ROW_B],
        }
    ]
    fencers: list[dict[str, Any]] = [
        {"id": FENCER_ROW_A, "name": " Lee Kiefer ", "country": "USA"},
        {"id": FENCER_ROW_B, "name": "윤지수", "country": "KOR"},
        {"id": "00000000-0000-0000-0000-000000000999", "name": "Ignored", "country": "USA"},
    ]
    results: list[dict[str, Any]] = [
        {
            "id": "r1",
            "fencer_id": FENCER_ROW_A,
            "fie_fencer_id": "999",
            "name": "Lee Kiefer",
            "country": "USA",
            "nationality": "USA",
        },
        {
            "id": "r2",
            "fencer_id": None,
            "fie_fencer_id": "123",
            "name": "Софья Великая",
            "nationality": "AIN",
        },
        {"id": "r3", "fencer_id": None, "fie_fencer_id": "nope", "name": "No Identity"},
    ]
    rankings: list[dict[str, Any]] = [
        {
            "id": "n1",
            "fencer_id": FENCER_ROW_B,
            "fie_id": "123",
            "name": "江村 美咲",
            "country": "JPN",
        },
        {
            "id": "n2",
            "fencer_id": None,
            "fie_id": "123",
            "name": "علاء أبو القاسم",
            "country": "EGY",
        },
    ]

    rows = build_name_variants(identities, fencers, results, rankings)

    by_name = {row["name"]: row for row in rows}
    assert set(by_name) == {
        "Lee Kiefer",
        "윤지수",
        "Софья Великая",
        "江村 美咲",
        "علاء أبو القاسم",
    }
    assert {row["fencer_id"] for row in rows} == {IDENTITY_ID}
    assert by_name["Lee Kiefer"]["script"] == "Latin"
    assert by_name["Lee Kiefer"]["source"] == "fs_fencers"
    assert by_name["Lee Kiefer"]["country"] == "USA"
    assert by_name["Lee Kiefer"]["metadata"]["sources"] == ["fs_fencers", "fs_results"]
    assert by_name["윤지수"]["script"] == "Hangul"
    assert by_name["Софья Великая"]["script"] == "Cyrillic"
    assert by_name["江村 美咲"]["script"] == "CJK"
    assert by_name["علاء أبو القاسم"]["script"] == "Arabic"


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.columns = None
        self.range_start = 0
        self.range_end = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.client.upserts.append(
            {
                "table": self.name,
                "rows": list(rows),
                "on_conflict": on_conflict,
            }
        )
        return self

    def execute(self):
        if self.operation == "select":
            rows = self.client.tables[self.name]
            return FakeResult(rows[self.range_start : cast(int, self.range_end) + 1])
        if self.operation == "upsert":
            return FakeResult([])
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeClient:
    def __init__(self):
        self.tables = {
            "fs_fencer_identities": [
                {
                    "id": IDENTITY_ID,
                    "country": "USA",
                    "fie_ids": ["1001"],
                    "fs_fencer_row_ids": [FENCER_ROW_A, FENCER_ROW_B],
                },
                {
                    "id": SECOND_IDENTITY_ID,
                    "country": "KOR",
                    "fie_ids": [],
                    "fs_fencer_row_ids": [FENCER_ROW_C],
                },
            ],
            "fs_fencers": [
                {"id": FENCER_ROW_A, "name": "Lee Kiefer", "country": "USA"},
                {"id": FENCER_ROW_B, "name": "Lee Kiefer", "country": "USA"},
                {"id": FENCER_ROW_C, "name": "윤지수", "country": "KOR"},
            ],
            "fs_results": [
                {
                    "id": "r1",
                    "fencer_id": FENCER_ROW_A,
                    "fie_fencer_id": None,
                    "name": "Lee Kiefer",
                    "country": "USA",
                    "nationality": "USA",
                }
            ],
            "fs_national_fed_rankings": [
                {
                    "id": "n1",
                    "fencer_id": None,
                    "fie_id": "1001",
                    "name": "KIEFER Lee",
                    "country": "USA",
                }
            ],
        }
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_name_variants_fetches_sources_and_upserts_unique_rows():
    from compute_name_variants import compute_name_variants

    client = FakeClient()

    report = compute_name_variants(
        client=client,
        page_size=2,
        batch_size=2,
        log_run=False,
        update_state=False,
    )

    assert report == {
        "identities_loaded": 2,
        "source_names_seen": 5,
        "variants_found": 3,
        "variants_written": 3,
        "skipped_without_identity": 0,
    }
    assert {table for table, _ in client.selects} == {
        "fs_fencer_identities",
        "fs_fencers",
        "fs_results",
        "fs_national_fed_rankings",
    }
    assert {call["table"] for call in client.upserts} == {"fs_fencer_name_variants"}
    assert {call["on_conflict"] for call in client.upserts} == {"fencer_id,name,script"}

    upserted = [row for call in client.upserts for row in call["rows"]]
    by_name = {row["name"]: row for row in upserted}
    assert set(by_name) == {"Lee Kiefer", "KIEFER Lee", "윤지수"}
    assert by_name["Lee Kiefer"]["metadata"]["sources"] == ["fs_fencers", "fs_results"]
    assert by_name["KIEFER Lee"]["metadata"]["source_row_ids"] == ["n1"]


def test_name_variant_migration_defines_table_indexes_and_unique_key():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "20260601_name_variants.sql"
    )

    sql = " ".join(migration_path.read_text().split())

    assert "CREATE TABLE IF NOT EXISTS fs_fencer_name_variants" in sql
    assert "script text NOT NULL CHECK (script IN ('Latin', 'Hangul', 'Cyrillic', 'CJK', 'Arabic', 'Other'))" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_fencer_name_variants_fencer ON fs_fencer_name_variants(fencer_id)" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_fencer_name_variants_name ON fs_fencer_name_variants(name)" in sql
    assert "CREATE UNIQUE INDEX IF NOT EXISTS idx_fencer_name_variants_unique ON fs_fencer_name_variants(fencer_id, name, script)" in sql

import os
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FENCER_ALICE = "00000000-0000-0000-0000-000000000001"
FENCER_BOB = "00000000-0000-0000-0000-000000000002"
FENCER_CAROL = "00000000-0000-0000-0000-000000000003"
FENCER_DAN = "00000000-0000-0000-0000-000000000004"
NOW = "2026-06-01T12:00:00+00:00"


def test_build_medal_table_rows_aggregates_country_fencer_and_tier_counts():
    from compute_medal_tables import build_medal_table_rows

    tournaments: dict[str, dict[str, Any]] = {
        "olympics-foil": {
            "id": "olympics-foil",
            "type": "OG",
            "name": "Olympic Games",
            "category": "Senior",
        },
        "worlds-epee": {
            "id": "worlds-epee",
            "type": "WCH",
            "name": "World Championships",
            "category": "Senior",
        },
        "gp-sabre": {
            "id": "gp-sabre",
            "type": "GP",
            "name": "Grand Prix",
            "category": "Senior",
        },
        "unknown-local": {
            "id": "unknown-local",
            "type": "NAT",
            "name": "Local Open",
            "category": "Senior",
        },
    }
    results: list[dict[str, Any]] = [
        {
            "id": "r1",
            "tournament_id": "olympics-foil",
            "fencer_id": FENCER_ALICE,
            "country": "USA",
            "nationality": "United States",
            "medal": "Gold",
        },
        {
            "id": "r2",
            "tournament_id": "olympics-foil",
            "fencer_id": FENCER_BOB,
            "country": "USA",
            "medal": "silver",
        },
        {
            "id": "r3",
            "tournament_id": "olympics-foil",
            "fencer_id": None,
            "nationality": "USA",
            "medal": "Bronze",
        },
        {
            "id": "r4",
            "tournament_id": "worlds-epee",
            "fencer_id": FENCER_CAROL,
            "nationality": "Italy",
            "medal": "Bronze",
        },
        {
            "id": "r5",
            "tournament_id": "worlds-epee",
            "fencer_id": FENCER_CAROL,
            "country": "Italy",
            "medal": "bronze",
        },
        {
            "id": "r6",
            "tournament_id": "gp-sabre",
            "fencer_id": FENCER_DAN,
            "country": "France",
            "medal": "G",
        },
        {
            "id": "r7",
            "tournament_id": "unknown-local",
            "fencer_id": FENCER_ALICE,
            "country": "USA",
            "medal": "Silver",
        },
        {
            "id": "r8",
            "tournament_id": "gp-sabre",
            "fencer_id": FENCER_DAN,
            "country": "France",
            "medal": "No medal",
        },
    ]

    rows, skipped = build_medal_table_rows(results, tournaments, updated_at=NOW)

    assert skipped == 1
    by_id = {row["id"]: row for row in rows}

    assert by_id["country:usa"] == {
        "id": "country:usa",
        "scope": "country",
        "country": "USA",
        "fencer_id": None,
        "tier": None,
        "gold": 1,
        "silver": 2,
        "bronze": 1,
        "total": 4,
        "updated_at": NOW,
    }
    assert by_id["country:italy"]["bronze"] == 2
    assert by_id["country:france"]["gold"] == 1

    assert by_id[f"fencer:{FENCER_ALICE}"]["gold"] == 1
    assert by_id[f"fencer:{FENCER_ALICE}"]["silver"] == 1
    assert by_id[f"fencer:{FENCER_ALICE}"]["total"] == 2
    assert by_id[f"fencer:{FENCER_CAROL}"]["bronze"] == 2
    assert by_id[f"fencer:{FENCER_DAN}"]["gold"] == 1

    assert by_id["tier:olympics:usa"]["tier"] == "Olympics"
    assert by_id["tier:olympics:usa"]["gold"] == 1
    assert by_id["tier:olympics:usa"]["silver"] == 1
    assert by_id["tier:olympics:usa"]["bronze"] == 1
    assert by_id["tier:worlds:italy"]["bronze"] == 2
    assert by_id["tier:gp:france"]["gold"] == 1
    assert "tier:nat:usa" not in by_id


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
        self.not_null_columns = []

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.name, columns))
        return self

    @property
    def not_(self):
        return self

    def is_(self, column, value):
        assert value == "null"
        self.not_null_columns.append(column)
        self.client.not_null_filters.append((self.name, column))
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
        if self.operation == "select":
            rows = list(self.client.tables[self.name])
            for column in self.not_null_columns:
                rows = [row for row in rows if row.get(column) is not None]
            return FakeResult(rows[self.range_start : cast(int, self.range_end) + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult(self.rows)
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.not_null_filters = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_medal_tables_fetches_medaled_results_and_upserts_rows():
    from compute_medal_tables import compute_medal_tables

    client = FakeSupabase(
        {
            "fs_results": [
                {
                    "id": "r1",
                    "tournament_id": "olympics-foil",
                    "fencer_id": FENCER_ALICE,
                    "country": "USA",
                    "medal": "Gold",
                },
                {
                    "id": "ignored",
                    "tournament_id": "olympics-foil",
                    "fencer_id": FENCER_ALICE,
                    "country": "USA",
                    "medal": None,
                },
            ],
            "fs_tournaments": [
                {
                    "id": "olympics-foil",
                    "type": "OG",
                    "name": "Olympic Games",
                    "category": "Senior",
                }
            ],
        }
    )

    summary = compute_medal_tables(
        client=client,
        page_size=2,
        updated_at=NOW,
        log_run=False,
        update_state=False,
    )

    assert ("fs_results", "medal") in client.not_null_filters
    assert summary == {
        "results_read": 1,
        "tournaments_read": 1,
        "medal_rows": 3,
        "written": 3,
        "skipped": 0,
    }
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_medal_tables"
    assert upsert["on_conflict"] == "id"
    upserted = {row["id"]: row for row in upsert["rows"]}
    assert set(upserted) == {
        "country:usa",
        f"fencer:{FENCER_ALICE}",
        "tier:olympics:usa",
    }


class MissingCountryTable(FakeTable):
    def select(self, columns):
        if self.name == "fs_results" and "country" in columns.split(","):
            raise RuntimeError("missing country column")
        return super().select(columns)


class MissingCountrySupabase(FakeSupabase):
    def table(self, name):
        return MissingCountryTable(self, name)


def test_fetch_medal_results_falls_back_when_country_column_is_absent():
    from compute_medal_tables import fetch_medal_results

    client = MissingCountrySupabase(
        {
            "fs_results": [
                {
                    "id": "r1",
                    "tournament_id": "olympics-foil",
                    "fencer_id": FENCER_ALICE,
                    "nationality": "USA",
                    "medal": "Gold",
                }
            ],
        }
    )

    rows = fetch_medal_results(client, page_size=2)

    assert rows == [
        {
            "id": "r1",
            "tournament_id": "olympics-foil",
            "fencer_id": FENCER_ALICE,
            "nationality": "USA",
            "medal": "Gold",
        }
    ]


def test_medal_tables_migration_defines_single_table_for_all_scopes():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260601_medal_tables.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_medal_tables" in normalized
    assert "id text primary key" in normalized
    assert "scope text not null" in normalized
    assert "country text" in normalized
    assert "fencer_id uuid references public.fs_fencers(id)" in normalized
    assert "on delete cascade" in normalized
    assert "tier text" in normalized
    assert "gold integer not null default 0" in normalized
    assert "silver integer not null default 0" in normalized
    assert "bronze integer not null default 0" in normalized
    assert "total integer not null default 0" in normalized
    assert "gold + silver + bronze" in normalized
    assert "enable row level security" in normalized

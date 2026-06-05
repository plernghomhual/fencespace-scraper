from typing import Any, cast
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FENCER_ACTIVE = "00000000-0000-0000-0000-000000000001"
FENCER_RETIRED = "00000000-0000-0000-0000-000000000002"
FENCER_UNKNOWN = "00000000-0000-0000-0000-000000000003"
FENCER_SINGLE_SEASON = "00000000-0000-0000-0000-000000000004"
FENCER_BOUNDARY = "00000000-0000-0000-0000-000000000005"
NOW = "2026-06-01T12:00:00+00:00"
TODAY = date(2026, 6, 1)


def test_build_longevity_rows_computes_active_retired_unknown_and_single_season_cases():
    from compute_longevity import build_longevity_rows

    tournaments: dict[str, dict[str, Any]] = {
        "active-2025": {"id": "active-2025", "start_date": "2025-03-10", "season": "2024-2025"},
        "active-2026": {"id": "active-2026", "start_date": "2026-02-01T10:30:00+00:00", "season": 2026},
        "retired-2020": {"id": "retired-2020", "start_date": "2020-01-15", "season": 2020},
        "retired-2021": {"id": "retired-2021", "start_date": "2021-05-20", "season": "2021"},
        "retired-2023": {"id": "retired-2023", "start_date": "2023-01-15", "season": "2022/2023"},
        "single-2026": {"id": "single-2026", "start_date": "2026-01-08", "season": 2026},
    }
    results: list[dict[str, Any]] = [
        {"fencer_id": FENCER_ACTIVE, "tournament_id": "active-2025"},
        {"fencer_id": FENCER_ACTIVE, "tournament_id": "active-2026"},
        {"fencer_id": FENCER_RETIRED, "tournament_id": "retired-2020"},
        {"fencer_id": FENCER_RETIRED, "tournament_id": "retired-2021"},
        {"fencer_id": FENCER_RETIRED, "tournament_id": "retired-2023"},
        {"fencer_id": FENCER_SINGLE_SEASON, "tournament_id": "single-2026"},
        {"fencer_id": None, "tournament_id": "active-2026"},
        {"fencer_id": FENCER_ACTIVE, "tournament_id": "missing-tournament"},
    ]

    rows, skipped = build_longevity_rows(
        results,
        tournaments,
        fencer_ids=[FENCER_ACTIVE, FENCER_RETIRED, FENCER_UNKNOWN, FENCER_SINGLE_SEASON],
        today=TODAY,
        updated_at=NOW,
    )
    by_fencer = {row["fencer_id"]: row for row in rows}

    assert skipped == 2
    assert by_fencer[FENCER_ACTIVE] == {
        "fencer_id": FENCER_ACTIVE,
        "first_competition_date": "2025-03-10",
        "last_competition_date": "2026-02-01",
        "first_season": 2025,
        "last_season": 2026,
        "career_years": 1,
        "competitions_per_season": 2.0,
        "status": "active",
        "updated_at": NOW,
    }
    assert by_fencer[FENCER_RETIRED] == {
        "fencer_id": FENCER_RETIRED,
        "first_competition_date": "2020-01-15",
        "last_competition_date": "2023-01-15",
        "first_season": 2020,
        "last_season": 2023,
        "career_years": 3,
        "competitions_per_season": 1.0,
        "status": "likely_retired",
        "updated_at": NOW,
    }
    assert by_fencer[FENCER_SINGLE_SEASON]["first_season"] == 2026
    assert by_fencer[FENCER_SINGLE_SEASON]["last_season"] == 2026
    assert by_fencer[FENCER_SINGLE_SEASON]["career_years"] == 0
    assert by_fencer[FENCER_SINGLE_SEASON]["competitions_per_season"] == 1.0
    assert by_fencer[FENCER_SINGLE_SEASON]["status"] == "active"
    assert by_fencer[FENCER_UNKNOWN] == {
        "fencer_id": FENCER_UNKNOWN,
        "first_competition_date": None,
        "last_competition_date": None,
        "first_season": None,
        "last_season": None,
        "career_years": None,
        "competitions_per_season": None,
        "status": "unknown",
        "updated_at": NOW,
    }


def test_status_threshold_marks_exactly_two_years_as_active():
    from compute_longevity import build_longevity_rows

    rows, skipped = build_longevity_rows(
        [{"fencer_id": FENCER_BOUNDARY, "tournament_id": "boundary"}],
        {"boundary": {"id": "boundary", "start_date": "2024-06-01", "season": 2024}},
        fencer_ids=[FENCER_BOUNDARY],
        today=TODAY,
        updated_at=NOW,
    )

    assert skipped == 0
    assert rows[0]["status"] == "active"


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

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.name, columns))
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
            return FakeResult(self.client.tables[self.name][self.range_start : cast(int, self.range_end) + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult([])
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_longevity_fetches_source_tables_and_upserts_metrics():
    from compute_longevity import compute_longevity

    client = FakeSupabase(
        {
            "fs_fencers": [
                {"id": FENCER_ACTIVE},
                {"id": FENCER_RETIRED},
                {"id": FENCER_UNKNOWN},
            ],
            "fs_results": [
                {"fencer_id": FENCER_ACTIVE, "tournament_id": "active-2025"},
                {"fencer_id": FENCER_ACTIVE, "tournament_id": "active-2026"},
                {"fencer_id": FENCER_RETIRED, "tournament_id": "retired-2020"},
            ],
            "fs_tournaments": [
                {"id": "active-2025", "start_date": "2025-03-10", "season": 2025},
                {"id": "active-2026", "start_date": "2026-02-01", "season": 2026},
                {"id": "retired-2020", "start_date": "2020-01-15", "season": 2020},
            ],
        }
    )

    summary = compute_longevity(
        client=client,
        page_size=2,
        log_run=False,
        update_state=False,
        today=TODAY,
        now=NOW,
    )

    assert ("fs_fencers", "id") in client.selects
    assert ("fs_results", "fencer_id,tournament_id") in client.selects
    assert ("fs_tournaments", "id,start_date,season") in client.selects
    assert summary == {
        "fencers_read": 3,
        "results_read": 3,
        "tournaments_read": 3,
        "longevity_rows": 3,
        "written": 3,
        "skipped": 0,
    }
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_fencer_longevity"
    assert upsert["on_conflict"] == "fencer_id"
    upserted = {row["fencer_id"]: row for row in upsert["rows"]}
    assert upserted[FENCER_ACTIVE]["career_years"] == 1
    assert upserted[FENCER_ACTIVE]["competitions_per_season"] == 2.0
    assert upserted[FENCER_RETIRED]["status"] == "likely_retired"
    assert upserted[FENCER_UNKNOWN]["status"] == "unknown"


def test_longevity_migration_defines_table_status_and_conflict_key():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260601_longevity.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencer_longevity" in normalized
    assert "fencer_id uuid primary key references public.fs_fencers(id)" in normalized
    assert "first_competition_date date" in normalized
    assert "last_competition_date date" in normalized
    assert "first_season integer" in normalized
    assert "last_season integer" in normalized
    assert "career_years integer" in normalized
    assert "competitions_per_season numeric(8,2)" in normalized
    assert "status text not null" in normalized
    assert "check (status in ('active', 'likely_retired', 'unknown'))" in normalized

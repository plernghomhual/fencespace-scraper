import os
import re
import sys
from pathlib import Path
from typing import cast

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def fencer_row(
    row_id,
    country="USA",
    weapon="Foil",
    category="Senior",
    world_rank=None,
    club=None,
    fie_points=None,
):
    return {
        "id": row_id,
        "country": country,
        "weapon": weapon,
        "category": category,
        "world_rank": world_rank,
        "club": club,
        "fie_points": fie_points,
    }


def test_compute_country_depth_counts_rank_buckets_and_average():
    from compute_country_analytics import compute_country_depth

    rows = [
        fencer_row("1", world_rank=1),
        fencer_row("2", world_rank=16),
        fencer_row("3", world_rank=17),
        fencer_row("4", world_rank=32),
        fencer_row("5", world_rank=64),
        fencer_row("6", world_rank=65),
        fencer_row("7", world_rank=None),
        fencer_row("8", world_rank=0),
        fencer_row("9", country="ITA", weapon="Epee", category="Junior", world_rank="8"),
        fencer_row("10", country="", world_rank=3),
    ]

    result = compute_country_depth(rows, updated_at="2026-05-31T00:00:00+00:00")

    usa = next(row for row in result if row["country"] == "USA" and row["weapon"] == "Foil")
    assert usa == {
        "country": "USA",
        "weapon": "Foil",
        "category": "Senior",
        "fencers_in_top16": 2,
        "fencers_in_top32": 4,
        "fencers_in_top64": 5,
        "total_ranked": 6,
        "avg_world_rank": 32.5,
        "updated_at": "2026-05-31T00:00:00+00:00",
    }

    ita = next(row for row in result if row["country"] == "ITA")
    assert ita["weapon"] == "Epee"
    assert ita["category"] == "Junior"
    assert ita["fencers_in_top16"] == 1
    assert ita["avg_world_rank"] == 8.0


def test_compute_club_rankings_normalizes_variants_and_skips_unranked():
    from compute_country_analytics import compute_club_rankings, normalize_club_name

    assert normalize_club_name("  Fiamme Oro  ") == "fiamme oro"
    assert normalize_club_name("Fiamme-Oro") == "fiamme oro"
    assert normalize_club_name("A.S.D. Fiamme Oro") == "fiamme oro"

    rows = [
        fencer_row("1", country="ITA", weapon="Foil", world_rank=1, club=" Fiamme Oro ", fie_points=100),
        fencer_row("2", country="ITA", weapon="Foil", world_rank=9, club="A.S.D. Fiamme Oro", fie_points=None),
        fencer_row("3", country="ITA", weapon="Foil", world_rank=11, club="fiamme-oro", fie_points="50.5"),
        fencer_row("4", country="ITA", weapon="Foil", world_rank=None, club="Fiamme Oro", fie_points=999),
        fencer_row("5", country="ITA", weapon="Foil", world_rank=4, club=" ", fie_points=30),
        fencer_row("6", country="USA", weapon="Foil", world_rank=5, club="Fiamme Oro", fie_points=40),
        fencer_row("7", country="ITA", weapon="Epee", world_rank=2, club="Fiamme Oro", fie_points=80),
    ]

    result = compute_club_rankings(rows, updated_at="2026-05-31T00:00:00+00:00")

    ita_foil = next(row for row in result if row["country"] == "ITA" and row["weapon"] == "Foil")
    assert ita_foil == {
        "club": "fiamme oro",
        "country": "ITA",
        "weapon": "Foil",
        "total_fencers": 3,
        "avg_rank": 7.0,
        "total_points": 150.5,
        "updated_at": "2026-05-31T00:00:00+00:00",
    }

    assert any(row["country"] == "USA" and row["total_fencers"] == 1 for row in result)
    assert any(row["weapon"] == "Epee" and row["total_points"] == 80.0 for row in result)


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


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
        if self.operation == "select" and self.name == "fs_fencers":
            return FakeResult(self.client.fencers[self.range_start:cast(int, self.range_end) + 1])
        if self.operation == "upsert":
            self.client.upserts.append({
                "table": self.name,
                "rows": self.rows,
                "on_conflict": self.on_conflict,
            })
            return FakeResult([])
        raise AssertionError(f"unexpected operation {self.operation} on {self.name}")


class FakeSupabase:
    def __init__(self, fencers):
        self.fencers = fencers
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_country_analytics_fetches_and_upserts_aggregates():
    from compute_country_analytics import compute_country_analytics

    client = FakeSupabase([
        fencer_row("1", country="USA", weapon="Foil", world_rank=1, club="Massialas Foundation", fie_points=120),
        fencer_row("2", country="USA", weapon="Foil", world_rank=20, club="Massialas Foundation", fie_points=80),
        fencer_row("3", country="FRA", weapon="Epee", world_rank=10, club="Levallois SC", fie_points=90),
    ])

    summary = compute_country_analytics(
        client=client,
        page_size=2,
        batch_size=1,
        updated_at="2026-05-31T00:00:00+00:00",
        log_run=False,
        update_state=False,
    )

    assert summary == {
        "fencers_read": 3,
        "country_depth_rows": 2,
        "club_ranking_rows": 2,
        "written": 4,
        "failed": 0,
        "skipped": 0,
    }
    assert client.selects == [
        ("fs_fencers", "id,country,weapon,category,world_rank,club,fie_points"),
        ("fs_fencers", "id,country,weapon,category,world_rank,club,fie_points"),
    ]
    assert {call["table"] for call in client.upserts} == {"fs_country_depth", "fs_club_rankings"}
    assert {call["on_conflict"] for call in client.upserts if call["table"] == "fs_country_depth"} == {
        "country,weapon,category"
    }
    assert {call["on_conflict"] for call in client.upserts if call["table"] == "fs_club_rankings"} == {
        "club,country,weapon"
    }


def test_country_club_rankings_migration_defines_expected_tables():
    migrations = sorted(Path("supabase/migrations").glob("*_country_club_rankings.sql"))

    assert migrations, "country/club rankings migration is missing"
    sql = migrations[-1].read_text()

    assert "create table if not exists public.fs_country_depth" in sql.lower()
    assert "primary key (country, weapon, category)" in sql.lower()
    assert "fencers_in_top16" in sql
    assert "fencers_in_top32" in sql
    assert "fencers_in_top64" in sql
    assert "create table if not exists public.fs_club_rankings" in sql.lower()
    assert re.search(r"\bclub\s+text\s+not\s+null\b", sql, re.IGNORECASE)
    assert "unique (club, country, weapon)" in sql.lower()

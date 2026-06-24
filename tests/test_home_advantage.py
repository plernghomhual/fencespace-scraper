import os
import re
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"
ALICE = "00000000-0000-0000-0000-000000000001"
BOB = "00000000-0000-0000-0000-000000000002"
TRANSFER = "00000000-0000-0000-0000-000000000003"


def tournament(
    row_id,
    *,
    country="USA",
    start_date="2026-01-10",
    weapon="Foil",
    gender="Men",
    category="Senior",
    event_type="WC",
    metadata=None,
):
    return {
        "id": row_id,
        "name": f"{row_id} event",
        "country": country,
        "country_code": None,
        "location": None,
        "city": None,
        "start_date": start_date,
        "end_date": start_date,
        "weapon": weapon,
        "gender": gender,
        "category": category,
        "type": event_type,
        "metadata": metadata or {},
    }


def result(row_id, tournament_id, fencer_id, rank, *, country=None, medal=None):
    return {
        "id": row_id,
        "tournament_id": tournament_id,
        "fencer_id": fencer_id,
        "name": f"Fencer {fencer_id}",
        "country": country,
        "nationality": country,
        "rank": rank,
        "placement": None,
        "medal": medal,
        "weapon": None,
        "gender": None,
        "category": None,
    }


def fencer(row_id, *, country="USA", metadata=None):
    return {
        "id": row_id,
        "fie_id": row_id[-3:],
        "name": f"Fencer {row_id[-3:]}",
        "country": country,
        "metadata": metadata or {},
    }


def test_home_advantage_migration_defines_detail_and_aggregate_tables():
    migration = Path("supabase/migrations/20260602_home_advantage.sql")

    sql = migration.read_text(encoding="utf-8")
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_home_advantage_results" in normalized
    for column in (
        "id text primary key",
        "tournament_id uuid not null references public.fs_tournaments(id)",
        "fencer_id uuid references public.fs_fencers(id)",
        "country text not null",
        "fencer_country text",
        "tournament_country text",
        "home_status text not null",
        "expected_placement numeric",
        "actual_placement integer not null",
        "actual_medal text",
        "placement_delta numeric",
        "updated_at timestamptz not null",
    ):
        assert column in normalized
    assert "check (home_status in ('home', 'away', 'unknown'))" in normalized
    assert "unique (source_result_id)" in normalized

    assert "create table if not exists public.fs_home_advantage_aggregates" in normalized
    for column in (
        "country text not null",
        "weapon text",
        "gender text",
        "category text",
        "competition_tier text",
        "home_status text not null",
        "results_count integer not null default 0",
        "avg_expected_placement numeric",
        "avg_actual_placement numeric",
        "avg_placement_delta numeric",
        "medal_count integer not null default 0",
    ):
        assert column in normalized
    assert "alter table public.fs_home_advantage_results enable row level security" in normalized
    assert "alter table public.fs_home_advantage_aggregates enable row level security" in normalized
    assert re.search(r"create index .*fs_home_advantage_results.*home_status", normalized)


def test_classify_home_status_handles_home_away_neutral_multi_host_and_missing():
    from compute_home_advantage import classify_home_status

    assert classify_home_status(tournament("us", country="USA"), "United States") == {
        "home_status": "home",
        "classification_reason": "country_match",
        "tournament_country": "United States",
    }
    assert classify_home_status(tournament("fr", country="France"), "United States") == {
        "home_status": "away",
        "classification_reason": "country_mismatch",
        "tournament_country": "France",
    }
    assert classify_home_status(tournament("neutral", country="FIE"), "France") == {
        "home_status": "unknown",
        "classification_reason": "neutral_venue",
        "tournament_country": "FIE",
    }
    assert classify_home_status(tournament("multi", country="France / Germany"), "France") == {
        "home_status": "unknown",
        "classification_reason": "multi_national_host",
        "tournament_country": "France; Germany",
    }
    assert classify_home_status(tournament("missing-host", country=None), "France")[
        "classification_reason"
    ] == "missing_tournament_country"
    assert classify_home_status(tournament("missing-fencer", country="France"), None)[
        "classification_reason"
    ] == "missing_fencer_country"


def test_country_at_event_uses_history_range_before_current_fencer_country():
    from compute_home_advantage import resolve_fencer_country_at_event

    fencer_row = fencer(TRANSFER, country="France")
    history_rows: list[dict[str, Any]] = [
        {
            "fencer_id": TRANSFER,
            "country": "Italy",
            "country_code": "ITA",
            "start_date": "2008-01-01",
            "end_date": "2012-12-31",
            "source": "wikidata_citizenship",
        },
        {
            "fencer_id": TRANSFER,
            "country": "France",
            "country_code": "FRA",
            "start_date": "2013-01-01",
            "end_date": None,
            "source": "wikidata_country_for_sport",
        },
    ]

    resolved = resolve_fencer_country_at_event(
        fencer_row,
        history_rows,
        "2011-05-14",
        result_country="France",
    )

    assert resolved == {
        "country": "Italy",
        "source": "fs_fencer_nationality_history",
        "resolution_reason": "history_range_match",
    }


def test_build_home_advantage_rows_computes_transfer_aware_baselines_and_deltas():
    from compute_home_advantage import build_home_advantage_rows

    tournaments = [
        tournament("us-wc", country="USA", start_date="2026-01-10", event_type="WC"),
        tournament("fr-wc", country="France", start_date="2026-02-10", event_type="WC"),
        tournament("it-old", country="Italy", start_date="2011-05-14", event_type="GP"),
        tournament("multi", country="France / Germany", start_date="2026-03-01", event_type="WC"),
    ]
    results = [
        result("alice-away", "fr-wc", ALICE, 10, country="USA"),
        result("alice-home", "us-wc", ALICE, 6, country="USA", medal="Gold"),
        result("bob-away", "us-wc", BOB, 20, country="France"),
        result("bob-home", "fr-wc", BOB, 16, country="France", medal="Bronze"),
        result("transfer-old-home", "it-old", TRANSFER, 5, country="France"),
        result("unknown-multi", "multi", ALICE, 8, country="USA"),
        result("missing-rank", "us-wc", ALICE, None, country="USA"),
    ]
    fencers = [
        fencer(ALICE, country="USA"),
        fencer(BOB, country="France"),
        fencer(TRANSFER, country="France"),
    ]
    histories = [
        {
            "fencer_id": TRANSFER,
            "country": "Italy",
            "country_code": "ITA",
            "start_date": "2008-01-01",
            "end_date": "2012-12-31",
            "source": "wikidata_citizenship",
        },
        {
            "fencer_id": TRANSFER,
            "country": "France",
            "country_code": "FRA",
            "start_date": "2013-01-01",
            "source": "wikidata_country_for_sport",
        },
    ]

    rows, skipped = build_home_advantage_rows(
        results,
        fencers,
        tournaments,
        histories,
        updated_at=NOW,
    )
    by_source = {row["source_result_id"]: row for row in rows}

    assert skipped == 1
    assert by_source["alice-home"]["home_status"] == "home"
    assert by_source["alice-home"]["country"] == "United States"
    assert by_source["alice-home"]["expected_placement"] == 10.0
    assert by_source["alice-home"]["actual_placement"] == 6
    assert by_source["alice-home"]["placement_delta"] == 4.0
    assert by_source["alice-home"]["actual_medal"] == "gold"

    assert by_source["alice-away"]["home_status"] == "away"
    assert by_source["alice-away"]["expected_placement"] == 10.0
    assert by_source["alice-away"]["placement_delta"] == 0.0

    assert by_source["bob-home"]["expected_placement"] == 20.0
    assert by_source["bob-home"]["placement_delta"] == 4.0
    assert by_source["transfer-old-home"]["country"] == "Italy"
    assert by_source["transfer-old-home"]["home_status"] == "home"
    assert by_source["transfer-old-home"]["country_resolution_source"] == "fs_fencer_nationality_history"
    assert by_source["unknown-multi"]["home_status"] == "unknown"
    assert by_source["unknown-multi"]["classification_reason"] == "multi_national_host"


def test_build_home_advantage_aggregates_groups_by_country_weapon_category_tier_and_status():
    from compute_home_advantage import build_home_advantage_aggregate_rows, build_home_advantage_rows

    tournaments = [
        tournament("us-wc", country="USA", start_date="2026-01-10", event_type="WC"),
        tournament("fr-wc", country="France", start_date="2026-02-10", event_type="WC"),
    ]
    results = [
        result("alice-away", "fr-wc", ALICE, 10, country="USA"),
        result("alice-home", "us-wc", ALICE, 6, country="USA", medal="Gold"),
        result("bob-away", "us-wc", BOB, 20, country="France"),
        result("bob-home", "fr-wc", BOB, 16, country="France", medal="Bronze"),
    ]
    fencers = [fencer(ALICE, country="USA"), fencer(BOB, country="France")]

    detail_rows, skipped = build_home_advantage_rows(
        results,
        fencers,
        tournaments,
        [],
        updated_at=NOW,
    )
    aggregates = build_home_advantage_aggregate_rows(detail_rows, updated_at=NOW)
    by_key = {
        (
            row["country"],
            row["weapon"],
            row["gender"],
            row["category"],
            row["competition_tier"],
            row["home_status"],
        ): row
        for row in aggregates
    }

    assert skipped == 0
    usa_home = by_key[("United States", "Foil", "Men", "Senior", "WC", "home")]
    assert usa_home["results_count"] == 1
    assert usa_home["avg_expected_placement"] == 10.0
    assert usa_home["avg_actual_placement"] == 6.0
    assert usa_home["avg_placement_delta"] == 4.0
    assert usa_home["medal_count"] == 1
    assert usa_home["gold_count"] == 1

    usa_away = by_key[("United States", "Foil", "Men", "Senior", "WC", "away")]
    assert usa_away["avg_placement_delta"] == 0.0

    france_home = by_key[("France", "Foil", "Men", "Senior", "WC", "home")]
    assert france_home["avg_expected_placement"] == 20.0
    assert france_home["avg_actual_placement"] == 16.0
    assert france_home["bronze_count"] == 1


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.columns = None
        self.range_start = 0
        self.range_end = None
        self.rows = None
        self.on_conflict = None

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
        self.rows = list(rows)
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.name in self.client.fail_selects and self.operation == "select":
            raise RuntimeError(f"{self.name} unavailable")
        if self.operation == "select":
            rows = self.client.tables.get(self.name, [])
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
        raise AssertionError(f"unexpected operation {self.operation} on {self.name}")


class FakeSupabase:
    def __init__(self, tables, fail_selects=None):
        self.tables = tables
        self.fail_selects = set(fail_selects or [])
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_home_advantage_fetches_optional_history_and_upserts_detail_and_aggregates():
    from compute_home_advantage import compute_home_advantage

    client = FakeSupabase(
        {
            "fs_results": [
                result("alice-away", "fr-wc", ALICE, 10, country="USA"),
                result("alice-home", "us-wc", ALICE, 6, country="USA", medal="Gold"),
            ],
            "fs_fencers": [fencer(ALICE, country="USA")],
            "fs_tournaments": [
                tournament("us-wc", country="USA", start_date="2026-01-10", event_type="WC"),
                tournament("fr-wc", country="France", start_date="2026-02-10", event_type="WC"),
            ],
            "fs_fencer_nationality_history": [],
        }
    )

    summary = compute_home_advantage(
        client=client,
        page_size=1,
        batch_size=1,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary == {
        "results_read": 2,
        "fencers_read": 1,
        "tournaments_read": 2,
        "nationality_history_read": 0,
        "detail_rows": 2,
        "aggregate_rows": 2,
        "written": 4,
        "failed": 0,
        "skipped": 0,
    }
    assert ("fs_fencer_nationality_history", "fencer_id,country,country_code,start_date,end_date,point_in_time,source,confidence,metadata") in client.selects
    assert [call["table"] for call in client.upserts] == [
        "fs_home_advantage_results",
        "fs_home_advantage_results",
        "fs_home_advantage_aggregates",
        "fs_home_advantage_aggregates",
    ]
    assert {call["on_conflict"] for call in client.upserts} == {"id"}

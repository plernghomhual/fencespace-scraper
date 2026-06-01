import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.data_quality_check import run_check


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeRpc:
    def __init__(self, client, name):
        self.client = client
        self.name = name

    def execute(self):
        self.client.rpc_calls.append(self.name)
        if self.client.refresh_error:
            raise self.client.refresh_error
        return FakeResult([])


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name

    def select(self, columns):
        self.client.selects.append((self.name, columns))
        return self

    def execute(self):
        return FakeResult(self.client.views.get(self.name, []))


class FakeSupabase:
    def __init__(self, views, refresh_error=None):
        self.views = views
        self.refresh_error = refresh_error
        self.rpc_calls = []
        self.selects = []

    def rpc(self, name):
        return FakeRpc(self, name)

    def table(self, name):
        return FakeTable(self, name)


def base_views(orphan_count=10):
    return {
        "v_fencer_source_coverage": [
            {"source_name": "fs_fencers", "fencer_count": 1000},
            {"source_name": "fs_national_fed_rankings", "fencer_count": 250},
            {"source_name": "fs_results_linked", "fencer_count": 800},
        ],
        "v_scraper_health": [
            {
                "module": "scrape_fencers",
                "status": "completed",
                "started_at": "2026-06-01T00:00:00Z",
                "completed_at": "2026-06-01T00:03:00Z",
                "written": 1000,
                "failed": 0,
                "skipped": 0,
            },
            {
                "module": "scrape_olympics",
                "status": "completed",
                "started_at": "2026-06-01T01:00:00Z",
                "completed_at": "2026-06-01T01:03:00Z",
                "written": 40,
                "failed": 0,
                "skipped": 0,
            },
        ],
        "v_orphan_results": [
            {"tournament_type": "olympics", "orphan_count": orphan_count},
        ],
        "v_stale_sources": [],
    }


def run_with_state(client, previous_state):
    states = []

    def get_state(_source, _key):
        return previous_state

    def set_state(source, key, value):
        states.append((source, key, value))

    code = run_check(
        client=client,
        get_state_fn=get_state,
        set_state_fn=set_state,
        log_run=False,
    )
    return code, states


def test_healthy_views_return_exit_code_zero(capsys):
    client = FakeSupabase(base_views(orphan_count=10))

    code, states = run_with_state(
        client,
        {"total": 10, "by_tournament_type": {"olympics": 10}},
    )

    assert code == 0
    assert client.rpc_calls == ["refresh_data_quality_views"]
    assert ("v_fencer_source_coverage", "*") in client.selects
    assert states[-1][0:2] == ("data_quality_check", "orphan_counts")
    assert states[-1][2]["total"] == 10
    output = capsys.readouterr().out
    assert "v_fencer_source_coverage: 3 rows" in output
    assert "Status: healthy" in output


def test_all_stale_scrapers_return_critical_exit_code(capsys):
    views = base_views(orphan_count=10)
    views["v_stale_sources"] = [
        {"module": "scrape_fencers", "last_run": "2026-05-29T00:00:00Z"},
        {"module": "scrape_olympics", "last_run": "2026-05-29T01:00:00Z"},
    ]
    client = FakeSupabase(views)

    code, _states = run_with_state(
        client,
        {"total": 10, "by_tournament_type": {"olympics": 10}},
    )

    assert code == 2
    output = capsys.readouterr().out
    assert "CRITICAL" in output
    assert "All scraper modules are stale" in output


def test_orphan_count_increase_over_twenty_percent_returns_warning(capsys):
    client = FakeSupabase(base_views(orphan_count=121))

    code, states = run_with_state(
        client,
        {"total": 100, "by_tournament_type": {"olympics": 100}},
    )

    assert code == 1
    assert states[-1][2]["total"] == 121
    output = capsys.readouterr().out
    assert "WARNING" in output
    assert "Orphan results increased" in output
    assert "100 -> 121" in output


def test_materialized_view_refresh_failure_returns_critical_exit_code(capsys):
    client = FakeSupabase(
        base_views(orphan_count=10),
        refresh_error=RuntimeError("permission denied for materialized view"),
    )

    code, states = run_with_state(
        client,
        {"total": 10, "by_tournament_type": {"olympics": 10}},
    )

    assert code == 2
    assert states == []
    output = capsys.readouterr().out
    assert "CRITICAL" in output
    assert "Failed to refresh materialized views" in output
    assert "permission denied for materialized view" in output


def test_coverage_views_migration_defines_views_and_refresh_rpc():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "20260601_coverage_views.sql"
    )

    sql = " ".join(migration_path.read_text().split()).lower()

    for view_name in (
        "v_fencer_source_coverage",
        "v_scraper_health",
        "v_orphan_results",
        "v_stale_sources",
    ):
        assert f"create materialized view public.{view_name}" in sql
        assert f"refresh materialized view public.{view_name}" in sql

    assert "create or replace function public.refresh_data_quality_views()" in sql
    assert "grant execute on function public.refresh_data_quality_views() to service_role" in sql
    assert "security definer" not in sql

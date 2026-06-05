import importlib
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.sidebar_text_input_value = ""
        self.sidebar = types.SimpleNamespace(
            radio=lambda *args, **kwargs: "Status Dashboard",
            text_input=self._sidebar_text_input,
        )
        self.calls = []

    def _sidebar_text_input(self, *args, **kwargs):
        self.calls.append(("sidebar.text_input", args, kwargs))
        return self.sidebar_text_input_value

    def cache_data(self, *args, **kwargs):
        return lambda fn: fn

    def cache_resource(self, *args, **kwargs):
        return lambda fn: fn

    def __getattr__(self, name):
        def _method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name == "selectbox":
                return args[1][0]
            if name == "text_input":
                return ""
            if name == "stop":
                raise RuntimeError("streamlit stopped")
            return None

        return _method


class FakeResult:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)
        self.start = 0
        self.end = len(self.rows) - 1
        self.count_requested = False

    def select(self, _columns, count=None):
        self.count_requested = count == "exact"
        return self

    def order(self, column, desc=False):
        self.rows.sort(key=lambda row: row.get(column) or "", reverse=desc)
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def limit(self, _limit):
        self.start = 0
        self.end = -1
        return self

    def execute(self):
        end = self.end + 1 if self.end >= self.start else self.start
        page = self.rows[self.start:end]
        return FakeResult(page, count=len(self.rows) if self.count_requested else None)


class FakeClient:
    def __init__(self, tables):
        self.tables = tables

    def table(self, table_name):
        if table_name not in self.tables:
            raise RuntimeError(f"missing table: {table_name}")
        return FakeQuery(self.tables[table_name])


def import_dashboard_with_fake_streamlit(monkeypatch):
    fake_streamlit = FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    sys.modules.pop("dashboard.app", None)
    module = importlib.import_module("dashboard.app")
    return module, fake_streamlit


def test_dashboard_queries_include_required_reference_blocks():
    sql = (ROOT / "dashboard" / "queries.sql").read_text(encoding="utf-8").lower()

    required_blocks = [
        "scraper run status",
        "data counts",
        "stale sources",
        "error rate per module",
    ]

    for block in required_blocks:
        assert block in sql


def test_dashboard_queries_include_stale_source_and_orphan_checks():
    sql = (ROOT / "dashboard" / "queries.sql").read_text(encoding="utf-8").lower()

    assert "interval '48 hours'" in sql
    assert "last_success" in sql
    assert "fencer_id is null" in sql
    assert "orphan" in sql
    assert "fs_results" in sql
    assert "fs_tournaments" in sql


def test_dashboard_app_imports_with_streamlit_mock(monkeypatch):
    module, _fake_streamlit = import_dashboard_with_fake_streamlit(monkeypatch)

    assert module.REQUIRED_ENV_VARS == ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    assert callable(module.main)
    assert callable(module.fetch_status_rows)


def test_dashboard_auth_fails_closed_without_configured_token(monkeypatch):
    monkeypatch.delenv("FENCESPACE_DASHBOARD_TOKEN", raising=False)
    monkeypatch.delenv("DASHBOARD_AUTH_TOKEN", raising=False)
    module, fake_streamlit = import_dashboard_with_fake_streamlit(monkeypatch)

    try:
        module.require_dashboard_auth()
    except RuntimeError as exc:
        assert str(exc) == "streamlit stopped"
    else:
        raise AssertionError("dashboard auth must stop when no token is configured")

    assert ("error", ("Dashboard authentication is not configured.",), {}) in fake_streamlit.calls


def test_dashboard_auth_uses_password_input_and_session_state(monkeypatch):
    monkeypatch.setenv("FENCESPACE_DASHBOARD_TOKEN", "dashboard-secret")
    module, fake_streamlit = import_dashboard_with_fake_streamlit(monkeypatch)
    fake_streamlit.sidebar_text_input_value = "dashboard-secret"

    assert module.require_dashboard_auth() is True

    assert fake_streamlit.session_state["dashboard_authenticated"] is True
    assert fake_streamlit.calls[0][0] == "sidebar.text_input"
    assert fake_streamlit.calls[0][2]["type"] == "password"


def test_dashboard_fetchers_handle_status_counts_coverage_and_errors(monkeypatch):
    module, _fake_streamlit = import_dashboard_with_fake_streamlit(monkeypatch)
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=3)
    client = FakeClient(
        {
            "fs_scraper_runs": [
                {
                    "module": "scraper",
                    "started_at": old.isoformat(),
                    "completed_at": old.isoformat(),
                    "status": "completed",
                    "written": 10,
                    "failed": 0,
                    "skipped": 0,
                    "metadata": {},
                },
                {
                    "module": "scrape_results",
                    "started_at": now.isoformat(),
                    "completed_at": now.isoformat(),
                    "status": "completed_with_errors",
                    "written": 8,
                    "failed": 2,
                    "skipped": 1,
                    "metadata": {"error": "partial insert failure"},
                },
            ],
            "fs_tournaments": [
                {"id": "t1", "season": "2026", "type": "world_cup", "source_id": "fie:1"},
                {"id": "t2", "season": "2025", "type": "olympics", "source_id": "olympedia:1"},
            ],
            "fs_results": [
                {"id": "r1", "tournament_id": "t1", "fencer_id": "f1"},
                {"id": "r2", "tournament_id": "t1", "fencer_id": None},
                {"id": "r3", "tournament_id": "t2", "fencer_id": ""},
            ],
            "fs_fencers": [
                {"id": "f1", "country": "United States"},
                {"id": "f2", "country": "France"},
                {"id": "f3", "country": "France"},
            ],
            "fs_national_fed_rankings": [],
            "v_fencer_source_coverage": [],
            "v_orphan_results": [],
        }
    )

    status_rows = module.fetch_status_rows(client)
    by_module = {row["module"]: row for row in status_rows}
    assert by_module["scraper"]["health"] == "no recent run"
    assert by_module["scrape_results"]["health"] == "completed_with_errors"

    counts = module.fetch_data_counts(client)
    assert {"season": "2026", "tournaments": 1} in counts["tournaments_per_season"]
    assert {"competition_type": "world_cup", "results": 2} in counts["results_per_competition_type"]
    assert {"competition_type": "world_cup", "orphans": 1} in counts["orphan_counts"]

    coverage = module.fetch_coverage_rows(client)
    assert {"country": "France", "fencers": 2} in coverage

    errors = module.fetch_error_rows(client)
    assert errors[0]["module"] == "scrape_results"
    assert errors[0]["error_message"] == "partial insert failure"

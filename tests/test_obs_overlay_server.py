import importlib
import json
import os
import sys
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.in_filters = []
        self.limit_count = None
        self.order_by = None
        self.selected = None

    def select(self, columns):
        self.selected = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        self.client.filters.append((self.table_name, "eq", column, value))
        return self

    def lte(self, column, value):
        self.filters.append(("lte", column, value))
        self.client.filters.append((self.table_name, "lte", column, value))
        return self

    def gte(self, column, value):
        self.filters.append(("gte", column, value))
        self.client.filters.append((self.table_name, "gte", column, value))
        return self

    def in_(self, column, values):
        self.in_filters.append((column, set(values)))
        self.client.filters.append((self.table_name, "in", column, tuple(values)))
        return self

    @property
    def not_(self):
        return self

    def is_(self, column, value):
        self.filters.append(("not_is", column, value))
        self.client.filters.append((self.table_name, "not_is", column, value))
        return self

    def order(self, column, desc=False):
        self.order_by = (column, desc)
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def execute(self):
        if self.client.raise_on_table == self.table_name:
            raise RuntimeError("service-role-secret should not leak")

        rows = list(self.client.tables.get(self.table_name, []))
        for operator, column, value in self.filters:
            if operator == "eq":
                rows = [row for row in rows if str(row.get(column)) == str(value)]
            elif operator == "lte":
                rows = [row for row in rows if row.get(column) is not None and row.get(column) <= value]
            elif operator == "gte":
                rows = [row for row in rows if row.get(column) is not None and row.get(column) >= value]
            elif operator == "not_is" and value == "null":
                rows = [row for row in rows if row.get(column) is not None]

        for column, values in self.in_filters:
            rows = [row for row in rows if row.get(column) in values]

        if self.order_by:
            column, desc = self.order_by
            rows = sorted(rows, key=lambda row: row.get(column) or "", reverse=desc)
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self, tables=None, raise_on_table=None):
        self.tables = tables or {}
        self.raise_on_table = raise_on_table
        self.filters = []
        self.selects = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def live_tables():
    today = date.today()
    return {
        "fs_tournaments": [
            {
                "id": "t-1",
                "name": "June Foil Grand Prix",
                "season": 2026,
                "start_date": (today - timedelta(days=1)).isoformat(),
                "end_date": today.isoformat(),
                "competition_url_id": "9001",
                "weapon": "Foil",
                "gender": "Women",
                "category": "Senior",
                "country": "USA",
            }
        ],
        "fs_results": [
            {
                "id": "r-1",
                "tournament_id": "t-1",
                "fencer_id": "f-1",
                "fie_fencer_id": "100",
                "name": "Lee Kiefer",
                "country": "USA",
                "rank": 1,
            },
            {
                "id": "r-2",
                "tournament_id": "t-1",
                "fencer_id": "f-2",
                "fie_fencer_id": "200",
                "name": "Alice Volpi",
                "country": "ITA",
                "rank": 2,
            },
        ],
        "fs_bouts": [
            {
                "id": "b-1",
                "tournament_id": "t-1",
                "fencer_a_id": "f-1",
                "fencer_b_id": "f-2",
                "winner_id": "f-1",
                "score_a": 15,
                "score_b": 12,
                "round": "Final",
                "updated_at": "2026-06-02T15:00:00+00:00",
            }
        ],
        "fs_fencers": [
            {"id": "f-1", "name": "Lee Kiefer", "country": "USA"},
            {"id": "f-2", "name": "Alice Volpi", "country": "ITA"},
        ],
    }


@pytest.fixture
def overlay_module(monkeypatch):
    monkeypatch.setenv("OBS_OVERLAY_CACHE_SECONDS", "5")
    monkeypatch.setenv(
        "OBS_OVERLAY_TOKENS",
        json.dumps({"foil-finals": {"tournament_id": "t-1"}}),
    )
    sys.modules.pop("obs_overlay_server", None)
    module = importlib.import_module("obs_overlay_server")
    module.reset_overlay_state()
    yield module
    sys.modules.pop("obs_overlay_server", None)


def test_live_score_endpoint_returns_active_scores_and_cache_headers(overlay_module):
    fake = FakeSupabase(live_tables())
    overlay_module.app.state.supabase_client = fake
    client = TestClient(overlay_module.app)

    response = client.get("/overlay/live-score?tournament_id=t-1")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=5, stale-while-revalidate=15"
    assert response.headers["X-Overlay-Cache"] == "miss"
    assert response.headers["X-RateLimit-Limit"] == str(overlay_module.OVERLAY_RATE_LIMIT_PER_MINUTE)

    payload = response.json()
    assert payload["status"] == "active"
    assert payload["active"] is True
    assert payload["event"]["id"] == "t-1"
    assert payload["event"]["name"] == "June Foil Grand Prix"
    assert payload["event"]["event_id"] == "9001"
    assert payload["leaders"][0] == {"rank": 1, "name": "Lee Kiefer", "country": "USA", "fie_fencer_id": "100"}
    assert payload["bouts"][0]["round"] == "Final"
    assert payload["bouts"][0]["fencer_a"]["name"] == "Lee Kiefer"
    assert payload["bouts"][0]["fencer_b"]["name"] == "Alice Volpi"
    assert payload["bouts"][0]["score"] == {"a": 15, "b": 12}
    assert payload["bouts"][0]["status"] == "final"

    second = client.get("/overlay/live-score?tournament_id=t-1")
    assert second.status_code == 200
    assert second.headers["X-Overlay-Cache"] == "hit"


def test_live_score_endpoint_returns_no_active_state(overlay_module):
    overlay_module.app.state.supabase_client = FakeSupabase({"fs_tournaments": []})
    client = TestClient(overlay_module.app)

    response = client.get("/overlay/live-score")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "no_active_event"
    assert payload["active"] is False
    assert payload["event"] is None
    assert payload["leaders"] == []
    assert payload["bouts"] == []
    assert "No active tournament" in payload["message"]


def test_live_score_endpoint_returns_safe_error_state(overlay_module):
    overlay_module.app.state.supabase_client = FakeSupabase(raise_on_table="fs_tournaments")
    client = TestClient(overlay_module.app)

    response = client.get("/overlay/live-score")

    assert response.status_code == 502
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["active"] is False
    assert payload["message"] == "Live overlay data source is unavailable"
    assert "secret" not in response.text.lower()


def test_live_score_endpoint_validates_selection_params(overlay_module):
    overlay_module.app.state.supabase_client = FakeSupabase(live_tables())
    client = TestClient(overlay_module.app)

    invalid = client.get("/overlay/live-score?tournament_id=../../secret")
    conflicting = client.get("/overlay/live-score?tournament_id=t-1&event_id=9001")
    unknown_token = client.get("/overlay/live-score?token=missing")

    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "Invalid tournament_id"
    assert conflicting.status_code == 400
    assert conflicting.json()["detail"] == "Use only one of tournament_id, event_id, or token"
    assert unknown_token.status_code == 400
    assert unknown_token.json()["detail"] == "Unknown overlay token"


def test_live_score_endpoint_accepts_config_token_selection(overlay_module):
    fake = FakeSupabase(live_tables())
    overlay_module.app.state.supabase_client = fake
    client = TestClient(overlay_module.app)

    response = client.get("/overlay/live-score?token=foil-finals")

    assert response.status_code == 200
    assert response.json()["event"]["id"] == "t-1"
    assert ("fs_tournaments", "eq", "id", "t-1") in fake.filters


def test_live_score_endpoint_rate_limits_per_client(overlay_module, monkeypatch):
    monkeypatch.setattr(overlay_module, "OVERLAY_RATE_LIMIT_PER_MINUTE", 1)
    overlay_module.reset_overlay_state()
    overlay_module.app.state.supabase_client = FakeSupabase({"fs_tournaments": []})
    client = TestClient(overlay_module.app)

    assert client.get("/overlay/live-score").status_code == 200
    response = client.get("/overlay/live-score")

    assert response.status_code == 429
    assert response.json()["status"] == "rate_limited"
    assert response.headers["X-RateLimit-Limit"] == "1"
    assert "Retry-After" in response.headers

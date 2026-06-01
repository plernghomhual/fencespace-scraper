import importlib
import os
import sys

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
        self.ilike_filters = []
        self.gte_filters = []
        self.start = None
        self.end = None
        self.limit_count = None
        self.selected = None

    def select(self, columns):
        self.selected = columns
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def ilike(self, column, pattern):
        self.ilike_filters.append((column, pattern.replace("%", "").lower()))
        return self

    def gte(self, column, value):
        self.gte_filters.append((column, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.client.ranges.append((self.table_name, start, end))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def execute(self):
        rows = list(self.client.tables.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        for column, needle in self.ilike_filters:
            rows = [row for row in rows if needle in str(row.get(column, "")).lower()]
        for column, value in self.gte_filters:
            rows = [row for row in rows if row.get(column) is not None and row.get(column) >= value]
        if self.start is not None and self.end is not None:
            rows = rows[self.start : self.end + 1]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self):
        self.ranges = []
        self.tables = {
            "fs_fencers": [
                {"id": "f1", "name": "Alex Lee", "country": "KOR", "weapon": "Epee", "category": "Senior"},
                {"id": "f2", "name": "Mina Park", "country": "KOR", "weapon": "Foil", "category": "Senior"},
                {"id": "f3", "name": "Sam Stone", "country": "USA", "weapon": "Epee", "category": "Junior"},
            ],
            "fs_fencer_career_stats": [{"fencer_id": "f1", "total_competitions": 12, "gold_medals": 2}],
            "fs_fencer_social_media": [{"fencer_id": "f1", "platform": "instagram", "url": "https://example.test/alex"}],
            "fs_fencer_equipment": [{"fencer_id": "f1", "brand": "Allstar", "equipment_type": "weapon"}],
            "fs_tournaments": [
                {"id": "t1", "name": "Seoul GP", "season": 2026, "type": "GP", "country": "KOR"},
                {"id": "t2", "name": "Paris WC", "season": 2026, "type": "WC", "country": "FRA"},
            ],
            "fs_results": [
                {"id": "r1", "tournament_id": "t1", "rank": 1, "name": "Alex Lee", "nationality": "KOR"},
                {"id": "r2", "tournament_id": "t1", "rank": 2, "name": "Mina Park", "nationality": "KOR"},
            ],
            "fs_rankings_history": [
                {
                    "season": 2026,
                    "weapon": "Epee",
                    "gender": "Men",
                    "category": "Senior",
                    "rank": 1,
                    "name": "Alex Lee",
                }
            ],
            "fs_head_to_head": [
                {
                    "fencer_a_id": "f1",
                    "fencer_b_id": "f2",
                    "weapon": "Epee",
                    "a_wins": 3,
                    "b_wins": 1,
                    "bouts_total": 4,
                }
            ],
            "fs_country_depth": [
                {"country": "KOR", "weapon": "Epee", "category": "Senior", "fencers_in_top16": 3, "total_ranked": 25}
            ],
            "fs_api_keys": [{"key": "db-secret", "active": True, "revoked": False}],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


@pytest.fixture
def api_module(monkeypatch):
    monkeypatch.setenv("FENCESPACE_API_KEY", "secret")
    sys.modules.pop("api", None)
    module = importlib.import_module("api")
    module.app.state.supabase_client = FakeSupabase()
    module.reset_rate_limits()
    yield module
    sys.modules.pop("api", None)


@pytest.fixture
def client(api_module):
    return TestClient(api_module.app)


def auth_headers():
    return {"X-API-Key": "secret"}


def test_api_rejects_missing_api_key(client):
    response = client.get("/fencer/f1")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_api_accepts_api_key_from_database(monkeypatch):
    monkeypatch.delenv("FENCESPACE_API_KEY", raising=False)
    monkeypatch.delenv("FS_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    sys.modules.pop("api", None)
    module = importlib.import_module("api")
    module.app.state.supabase_client = FakeSupabase()
    module.reset_rate_limits()

    response = TestClient(module.app).get("/fencer/f1", headers={"X-API-Key": "db-secret"})

    assert response.status_code == 200
    assert response.json()["profile"]["id"] == "f1"
    sys.modules.pop("api", None)


def test_api_rejects_write_methods(client):
    response = client.post("/fencer/search", headers=auth_headers())

    assert response.status_code == 405
    assert response.json()["detail"] == "Method not allowed"


def test_api_rate_limits_per_key(client, api_module, monkeypatch):
    monkeypatch.setattr(api_module, "RATE_LIMIT_PER_MINUTE", 2)
    api_module.reset_rate_limits()

    assert client.get("/fencer/f1", headers=auth_headers()).status_code == 200
    assert client.get("/fencer/f1", headers=auth_headers()).status_code == 200
    response = client.get("/fencer/f1", headers=auth_headers())

    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit exceeded"


def test_fencer_search_uses_pagination(client, api_module):
    response = client.get("/fencer/search?limit=1&offset=1", headers=auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"] == {"limit": 1, "offset": 1, "count": 1}
    assert payload["data"][0]["id"] == "f2"
    assert ("fs_fencers", 1, 1) in api_module.app.state.supabase_client.ranges


def test_get_fencer_returns_profile_career_social_and_equipment(client):
    response = client.get("/fencer/f1", headers=auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["name"] == "Alex Lee"
    assert payload["career_stats"]["total_competitions"] == 12
    assert payload["social"][0]["platform"] == "instagram"
    assert payload["equipment"][0]["brand"] == "Allstar"


def test_search_fencers_filters_by_name_country_and_weapon(client):
    response = client.get("/fencer/search?name=alex&country=KOR&weapon=Epee", headers=auth_headers())

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == ["f1"]


def test_list_tournaments_filters_and_paginates(client):
    response = client.get("/tournaments?season=2026&type=GP&country=KOR&limit=50&offset=0", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["data"] == [{"id": "t1", "name": "Seoul GP", "season": 2026, "type": "GP", "country": "KOR"}]


def test_tournament_results_happy_path(client):
    response = client.get("/tournaments/t1/results", headers=auth_headers())

    assert response.status_code == 200
    assert [row["rank"] for row in response.json()["data"]] == [1, 2]


def test_rankings_happy_path(client):
    response = client.get("/rankings?season=2026&weapon=Epee&gender=Men&category=Senior", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["data"][0]["name"] == "Alex Lee"


def test_head_to_head_happy_path(client):
    response = client.get("/h2h/f2/f1", headers=auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["fencer_a"] == "f2"
    assert payload["fencer_b"] == "f1"
    assert payload["data"][0]["bouts_total"] == 4


def test_country_depth_happy_path(client):
    response = client.get("/countries/KOR/depth", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["data"][0]["fencers_in_top16"] == 3

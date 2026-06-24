import hashlib
import importlib
import os
import re
import sys
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_syndication_keys.sql"


def key_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.ilike_filters = []
        self.start = None
        self.end = None
        self.limit_count = None
        self.selected = None
        self.order_args = None
        self.pending_insert = None
        self.pending_update = None

    def select(self, columns):
        self.selected = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def ilike(self, column, pattern):
        self.ilike_filters.append((column, pattern.replace("%", "").lower()))
        return self

    def order(self, *args, **kwargs):
        self.order_args = (args, kwargs)
        self.client.orders.append((self.table_name, args, kwargs))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.client.ranges.append((self.table_name, start, end))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def insert(self, row):
        self.pending_insert = deepcopy(row)
        return self

    def update(self, values):
        self.pending_update = deepcopy(values)
        return self

    def execute(self):
        if self.pending_insert is not None:
            self.client.inserts.setdefault(self.table_name, []).append(deepcopy(self.pending_insert))
            return FakeResponse([self.pending_insert])

        if self.pending_update is not None:
            self.client.updates.append((self.table_name, deepcopy(self.pending_update), list(self.filters)))
            rows = self.client.tables.get(self.table_name, [])
            for row in rows:
                if all(str(row.get(column)) == str(value) for column, value in self.filters):
                    row.update(self.pending_update)
            return FakeResponse([])

        rows = [deepcopy(row) for row in self.client.tables.get(self.table_name, [])]
        for column, value in self.filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        for column, needle in self.ilike_filters:
            rows = [row for row in rows if needle in str(row.get(column, "")).lower()]
        if self.start is not None and self.end is not None:
            rows = rows[self.start : self.end + 1]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self):
        self.ranges = []
        self.selects = []
        self.orders = []
        self.inserts = {}
        self.updates = []
        self.tables = {
            "fs_syndication_keys": [
                {
                    "id": "key_valid",
                    "key_hash": key_hash("valid-secret"),
                    "partner_name": "Fence Wire",
                    "scopes": [
                        "fencers:read",
                        "tournaments:read",
                        "rankings:read",
                        "results:read",
                        "medals:read",
                    ],
                    "rate_limit_per_minute": 100,
                    "disabled": False,
                },
                {
                    "id": "key_fencers_only",
                    "key_hash": key_hash("fencers-only"),
                    "partner_name": "Fencer Directory",
                    "scopes": ["fencers:read"],
                    "rate_limit_per_minute": 100,
                    "disabled": False,
                },
                {
                    "id": "key_limited",
                    "key_hash": key_hash("limited-secret"),
                    "partner_name": "Tiny Partner",
                    "scopes": ["fencers:read"],
                    "rate_limit_per_minute": 2,
                    "disabled": False,
                },
                {
                    "id": "key_disabled",
                    "key_hash": key_hash("disabled-secret"),
                    "partner_name": "Disabled Partner",
                    "scopes": ["fencers:read"],
                    "rate_limit_per_minute": 100,
                    "disabled": True,
                },
            ],
            "v_fencer_public": [
                {
                    "id": "f1",
                    "name": "Alex Lee",
                    "country": "KOR",
                    "weapon": "Epee",
                    "category": "Senior",
                    "world_rank": 3,
                    "fie_points": 195.5,
                    "image_url": "https://cdn.example/alex.jpg",
                    "bio_text": "private biography",
                    "metadata": {"source": "internal"},
                    "date_of_birth": "1999-01-01",
                },
                {
                    "id": "f2",
                    "name": "Ari Kim",
                    "country": "KOR",
                    "weapon": "Epee",
                    "category": "Junior",
                    "world_rank": 14,
                    "fie_points": 88.0,
                    "image_url": None,
                    "private_notes": "do not expose",
                },
                {
                    "id": "f3",
                    "name": "Mina Park",
                    "country": "KOR",
                    "weapon": "Epee",
                    "category": "Senior",
                    "world_rank": 15,
                    "fie_points": 87.0,
                    "image_url": None,
                },
            ],
            "v_tournament_public": [
                {
                    "id": "t1",
                    "name": "Seoul GP",
                    "season": 2026,
                    "start_date": "2026-03-01",
                    "end_date": "2026-03-03",
                    "country": "KOR",
                    "weapon": "Epee",
                    "category": "Senior",
                    "type": "GP",
                    "metadata": {"internal": True},
                }
            ],
            "fs_rankings_history": [
                {
                    "id": "rk1",
                    "season": 2026,
                    "weapon": "Epee",
                    "gender": "Men",
                    "category": "Senior",
                    "rank": 1,
                    "fencer_id": "f1",
                    "name": "Alex Lee",
                    "country": "KOR",
                    "points": 195.5,
                    "metadata": {"internal": True},
                }
            ],
            "fs_results": [
                {
                    "id": "r1",
                    "tournament_id": "t1",
                    "fencer_id": "f1",
                    "rank": 1,
                    "name": "Alex Lee",
                    "nationality": "KOR",
                    "country": "KOR",
                    "club": "Seoul FC",
                    "metadata": {"raw": "hidden"},
                    "raw_payload": {"secret": "hidden"},
                }
            ],
            "fs_medal_tables": [
                {
                    "id": "m1",
                    "scope": "country",
                    "country": "KOR",
                    "fencer_id": None,
                    "tier": None,
                    "gold": 2,
                    "silver": 1,
                    "bronze": 3,
                    "total": 6,
                    "updated_at": "2026-06-02T00:00:00Z",
                    "metadata": {"internal": True},
                }
            ],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


def auth_headers(secret="valid-secret"):
    return {"X-API-Key": secret}


def bearer_headers(secret="valid-secret"):
    return {"Authorization": f"Bearer {secret}"}


def make_client(monkeypatch):
    sys.modules.pop("api_syndication", None)
    module = importlib.import_module("api_syndication")
    module.app.state.supabase_client = FakeSupabase()
    module.reset_rate_limits()
    return module, TestClient(module.app)


def test_syndication_rejects_missing_invalid_and_disabled_keys(monkeypatch):
    _module, client = make_client(monkeypatch)

    missing = client.get("/syndication/v1/fencers")
    invalid = client.get("/syndication/v1/fencers", headers=auth_headers("wrong"))
    disabled = client.get("/syndication/v1/fencers", headers=auth_headers("disabled-secret"))

    assert missing.status_code == 401
    assert missing.json()["detail"] == "Missing API key"
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid API key"
    assert disabled.status_code == 401
    assert disabled.json()["detail"] == "Invalid API key"


def test_syndication_enforces_endpoint_scopes(monkeypatch):
    _module, client = make_client(monkeypatch)

    allowed = client.get("/syndication/v1/fencers", headers=auth_headers("fencers-only"))
    forbidden = client.get("/syndication/v1/tournaments", headers=auth_headers("fencers-only"))

    assert allowed.status_code == 200
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "API key lacks scope tournaments:read"


def test_syndication_accepts_bearer_token_auth(monkeypatch):
    _module, client = make_client(monkeypatch)

    response = client.get("/syndication/v1/fencers", headers=bearer_headers())

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "f1"


def test_fencer_endpoint_filters_paginates_and_uses_public_projection(monkeypatch):
    module, client = make_client(monkeypatch)

    response = client.get(
        "/syndication/v1/fencers?country=KOR&weapon=Epee&limit=1&offset=1",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"] == {"limit": 1, "offset": 1, "count": 1}
    assert payload["data"][0]["id"] == "f2"
    assert ("v_fencer_public", 1, 1) in module.app.state.supabase_client.ranges
    selected = dict(module.app.state.supabase_client.selects)["v_fencer_public"]
    assert selected != "*"
    assert "metadata" not in selected
    assert "date_of_birth" not in selected


def test_private_fields_are_redacted_from_all_partner_resources(monkeypatch):
    _module, client = make_client(monkeypatch)

    endpoints = [
        "/syndication/v1/fencers",
        "/syndication/v1/tournaments",
        "/syndication/v1/rankings",
        "/syndication/v1/results",
        "/syndication/v1/medal-tables",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint, headers=auth_headers())
        assert response.status_code == 200
        first = response.json()["data"][0]
        assert "bio_text" not in first
        assert "date_of_birth" not in first
        assert "metadata" not in first
        assert "private_notes" not in first
        assert "raw_payload" not in first


def test_rate_limit_uses_partner_key_limit(monkeypatch):
    module, client = make_client(monkeypatch)

    assert client.get("/syndication/v1/fencers", headers=auth_headers("limited-secret")).status_code == 200
    assert client.get("/syndication/v1/fencers", headers=auth_headers("limited-secret")).status_code == 200
    response = client.get("/syndication/v1/fencers", headers=auth_headers("limited-secret"))

    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit exceeded"
    assert "Retry-After" in response.headers
    assert module.app.state.supabase_client.inserts["fs_syndication_request_logs"][-1]["status_code"] == 429


def test_request_logging_redacts_secrets_and_updates_last_used(monkeypatch):
    module, client = make_client(monkeypatch)

    response = client.get(
        "/syndication/v1/fencers?country=KOR&api_key=leaked-query-secret",
        headers=auth_headers("valid-secret"),
    )

    assert response.status_code == 200
    logs = module.app.state.supabase_client.inserts["fs_syndication_request_logs"]
    log = logs[-1]
    assert log["partner_name"] == "Fence Wire"
    assert log["key_id"] == "key_valid"
    assert log["path"] == "/syndication/v1/fencers"
    assert log["method"] == "GET"
    assert log["status_code"] == 200
    assert log["query_params"] == {"country": "KOR", "api_key": "[redacted]"}
    assert "valid-secret" not in repr(log)
    assert "leaked-query-secret" not in repr(log)
    assert ("fs_syndication_keys", {"last_used_at": log["created_at"]}, [("id", "key_valid")]) in (
        module.app.state.supabase_client.updates
    )


def test_syndication_migration_defines_partner_keys_and_secret_safe_logs():
    sql = MIGRATION.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_syndication_keys" in normalized
    assert "partner_name text not null" in normalized
    assert "key_hash text not null unique" in normalized
    assert "scopes text[] not null" in normalized
    assert "rate_limit_per_minute integer not null" in normalized
    assert "disabled boolean not null default false" in normalized
    assert "last_used_at timestamptz" in normalized

    assert "create table if not exists public.fs_syndication_request_logs" in normalized
    assert "key_id uuid references public.fs_syndication_keys(id)" in normalized
    assert "query_params jsonb not null default '{}'::jsonb" in normalized
    assert "ip_hash text" in normalized
    assert "user_agent text" in normalized
    assert "request_headers" not in normalized
    assert not re.search(r"\bkey\s+text\b", normalized)


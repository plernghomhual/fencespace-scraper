import hashlib
import importlib
import os
import sys
import time
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.limit_count = None
        self.selected = None

    def select(self, columns):
        self.selected = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.client.filters.append((self.table_name, column, value))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        rows = list(self.client.tables.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return FakeResponse([dict(row) for row in rows])

    def insert(self, *_args, **_kwargs):
        self.client.write_operations.append(("insert", self.table_name))
        raise AssertionError("ws_server must be read-only")

    def update(self, *_args, **_kwargs):
        self.client.write_operations.append(("update", self.table_name))
        raise AssertionError("ws_server must be read-only")

    def upsert(self, *_args, **_kwargs):
        self.client.write_operations.append(("upsert", self.table_name))
        raise AssertionError("ws_server must be read-only")

    def delete(self):
        self.client.write_operations.append(("delete", self.table_name))
        raise AssertionError("ws_server must be read-only")


class FakeSupabase:
    def __init__(self, *, tournaments=None, results=None, bouts=None, api_keys=None):
        self.tables = {
            "fs_tournaments": tournaments or [],
            "fs_results": results or [],
            "fs_bouts": bouts or [],
            "fs_api_keys": api_keys or [],
        }
        self.filters = []
        self.selects = []
        self.write_operations = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


@pytest.fixture
def ws_module(monkeypatch):
    monkeypatch.setenv("FENCESPACE_API_KEY", "secret")
    sys.modules.pop("ws_server", None)
    module = cast(Any, importlib.import_module("ws_server"))
    module.POLL_INTERVAL_SECONDS = 0.02
    module.HEARTBEAT_INTERVAL_SECONDS = 0.03
    module.SEND_TIMEOUT_SECONDS = 1.0
    module.reset_connection_manager()
    yield module
    module.reset_connection_manager()
    sys.modules.pop("ws_server", None)


def make_client(module, fake_supabase):
    module.app.state.supabase_client = fake_supabase
    return TestClient(module.app)


def connect(client, tournament_id="t-1", *, include=None, headers=None):
    suffix = f"?include={include}" if include else ""
    return client.websocket_connect(
        f"/ws/live-results/{tournament_id}{suffix}",
        headers=headers or {"X-API-Key": "secret"},
    )


def receive_until(websocket, predicate, *, max_messages=20):
    messages = []
    for _ in range(max_messages):
        message = websocket.receive_json()
        if predicate(message):
            return message
        messages.append(message)
    raise AssertionError(f"expected message not received; saw {messages}")


def test_websocket_validates_api_key_and_tournament_before_subscribing(ws_module):
    fake = FakeSupabase(tournaments=[{"id": "t-1", "name": "Live Grand Prix"}])
    client = make_client(ws_module, fake)

    with pytest.raises(WebSocketDisconnect) as missing_key:
        with client.websocket_connect("/ws/live-results/t-1"):
            pass
    assert missing_key.value.code == 1008

    with pytest.raises(WebSocketDisconnect) as missing_tournament:
        with connect(client, "missing-tournament"):
            pass
    assert missing_tournament.value.code == 1008

    with connect(client) as websocket:
        assert websocket.receive_json() == {
            "type": "subscribed",
            "tournament_id": "t-1",
            "include": ["results", "bouts"],
        }


def test_websocket_rejects_api_keys_in_query_string(ws_module):
    fake = FakeSupabase(tournaments=[{"id": "t-1", "name": "Live Grand Prix"}])
    client = make_client(ws_module, fake)

    with pytest.raises(WebSocketDisconnect) as rejected:
        with client.websocket_connect("/ws/live-results/t-1?api_key=secret"):
            pass

    assert rejected.value.code == 1008


@pytest.mark.anyio
async def test_websocket_accepts_hashed_and_legacy_database_api_keys(ws_module):
    fake = FakeSupabase(
        api_keys=[
            {
                "key_hash": hashlib.sha256(b"ws-hashed-secret").hexdigest(),
                "active": True,
                "revoked": False,
            },
            {"key": "ws-legacy-secret", "active": True, "revoked": False},
        ]
    )
    ws_module.app.state.supabase_client = fake
    ws_module.ENV_API_KEYS.clear()

    assert await ws_module.is_authorized_api_key("ws-hashed-secret", "t-1") is True
    assert await ws_module.is_authorized_api_key("ws-legacy-secret", "t-1") is True

    assert fake.write_operations == []


def test_subscription_streams_only_requested_tournament_events_and_changes(ws_module):
    fake = FakeSupabase(
        tournaments=[{"id": "t-1"}, {"id": "t-2"}],
        results=[
            {"id": "result-1", "tournament_id": "t-1", "rank": 1, "name": "Alex Lee"},
            {"id": "result-2", "tournament_id": "t-2", "rank": 1, "name": "Mina Park"},
        ],
        bouts=[
            {"id": "bout-1", "tournament_id": "t-1", "score_a": 15, "score_b": 12},
            {"id": "bout-2", "tournament_id": "t-2", "score_a": 15, "score_b": 11},
        ],
    )
    client = make_client(ws_module, fake)

    with connect(client, "t-1", include="results") as websocket:
        assert websocket.receive_json()["type"] == "subscribed"
        event = websocket.receive_json()
        fake.tables["fs_results"][0]["rank"] = 2
        changed = receive_until(
            websocket,
            lambda message: message.get("type") == "result"
            and message.get("row", {}).get("id") == "result-1"
            and message.get("row", {}).get("rank") == 2,
        )

    assert event["type"] == "result"
    assert event["tournament_id"] == "t-1"
    assert event["row"]["id"] == "result-1"
    assert event["row"]["tournament_id"] == "t-1"
    assert changed["tournament_id"] == "t-1"
    assert ("fs_results", "tournament_id", "t-1") in fake.filters
    assert ("fs_bouts", "tournament_id", "t-1") not in fake.filters
    assert fake.write_operations == []


def test_disconnect_cleans_up_connection(ws_module):
    fake = FakeSupabase(tournaments=[{"id": "t-1"}])
    client = make_client(ws_module, fake)

    with connect(client) as websocket:
        assert websocket.receive_json()["type"] == "subscribed"
        assert ws_module.connection_manager.active_count() == 1

    deadline = time.time() + 1.0
    while time.time() < deadline and ws_module.connection_manager.active_count() != 0:
        time.sleep(0.01)

    assert ws_module.connection_manager.active_count() == 0


def test_no_event_subscription_sends_heartbeat(ws_module):
    fake = FakeSupabase(tournaments=[{"id": "t-1"}])
    client = make_client(ws_module, fake)

    with connect(client) as websocket:
        assert websocket.receive_json()["type"] == "subscribed"
        heartbeat = websocket.receive_json()

    assert heartbeat["type"] == "heartbeat"
    assert heartbeat["tournament_id"] == "t-1"
    assert "timestamp" in heartbeat
    assert fake.write_operations == []

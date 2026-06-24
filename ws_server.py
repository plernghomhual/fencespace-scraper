"""Read-only FastAPI WebSocket server for live fencing results.

Local run:
    FENCESPACE_API_KEY=dev SUPABASE_URL=... SUPABASE_SERVICE_KEY=... \
        .venv/bin/python -m uvicorn ws_server:app --host 127.0.0.1 --port 8001

Connect to:
    ws://127.0.0.1:8001/ws/live-results/<tournament_id>

Pass the API key with the `X-API-Key` header, `Authorization: Bearer ...`, or
the WebSocket client equivalent. This server only reads from Supabase;
`watch_live_results.py` is responsible for scraping and writing `fs_results` /
`fs_bouts`.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
ENV_API_KEYS = [
    key.strip()
    for source in (
        os.environ.get("FENCESPACE_API_KEY", ""),
        os.environ.get("FS_API_KEY", ""),
        os.environ.get("API_KEY", ""),
    )
    for key in source.split(",")
    if key.strip()
]

POLL_INTERVAL_SECONDS = float(os.environ.get("FENCESPACE_WS_POLL_INTERVAL_SECONDS", "3"))
HEARTBEAT_INTERVAL_SECONDS = float(os.environ.get("FENCESPACE_WS_HEARTBEAT_SECONDS", "15"))
SEND_TIMEOUT_SECONDS = float(os.environ.get("FENCESPACE_WS_SEND_TIMEOUT_SECONDS", "5"))
CLIENT_QUEUE_MAXSIZE = int(os.environ.get("FENCESPACE_WS_CLIENT_QUEUE_MAXSIZE", "50"))

DEFAULT_INCLUDE = ("results", "bouts")
INCLUDE_TO_TABLE = {"results": "fs_results", "bouts": "fs_bouts"}
INCLUDE_TO_EVENT = {"results": "result", "bouts": "bout"}
TOURNAMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
POLICY_VIOLATION = 1008
TRY_AGAIN_LATER = 1013

app = FastAPI(title="FenceSpace Live Results WebSocket", version="1.0.0")
_supabase_client = None


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_supabase_client():
    if hasattr(app.state, "supabase_client"):
        return app.state.supabase_client

    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("Supabase credentials are not configured")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def _row_allows_key(row: dict[str, Any]) -> bool:
    if row.get("revoked") is True:
        return False
    if row.get("active") is False:
        return False
    return True


def _coerce_id_set(value: Any) -> set[str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return {item.strip() for item in value.split(",") if item.strip()}
    if isinstance(value, list | tuple | set):
        return {str(item) for item in value if str(item).strip()}
    return None


def _row_allows_tournament(row: dict[str, Any], tournament_id: str) -> bool:
    allowed = _coerce_id_set(row.get("allowed_tournament_ids"))
    if allowed is None:
        allowed = _coerce_id_set(row.get("tournament_ids"))

    metadata = row.get("metadata")
    if allowed is None and isinstance(metadata, dict):
        allowed = _coerce_id_set(metadata.get("allowed_tournament_ids"))
    if allowed is None and isinstance(metadata, dict):
        allowed = _coerce_id_set(metadata.get("tournament_ids"))

    return allowed is None or tournament_id in allowed


def _lookup_api_key_row(api_key: str) -> dict[str, Any] | None:
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    rows = (
        get_supabase_client()
        .table("fs_api_keys")
        .select("*")
        .eq("key_hash", key_hash)
        .limit(1)
        .execute()
        .data
        or []
    )
    if rows:
        return rows[0]

    # Primary API key rotation cutover:
    # keep this plaintext compatibility window until production API consumers
    # have rotated and all stored keys are backfilled to key_hash.
    legacy_rows = (
        get_supabase_client()
        .table("fs_api_keys")
        .select("*")
        .eq("key", api_key)
        .limit(1)
        .execute()
        .data
        or []
    )
    return legacy_rows[0] if legacy_rows else None


async def is_authorized_api_key(api_key: str | None, tournament_id: str) -> bool:
    if not api_key:
        return False
    if api_key in ENV_API_KEYS:
        return True
    try:
        row = await asyncio.to_thread(_lookup_api_key_row, api_key)
    except Exception:
        return False
    return bool(row and _row_allows_key(row) and _row_allows_tournament(row, tournament_id))


def api_key_from_websocket(websocket: WebSocket) -> str | None:
    api_key = websocket.headers.get("x-api-key")
    if api_key:
        return api_key

    authorization = websocket.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token

    return None


def is_valid_tournament_id(tournament_id: str) -> bool:
    return bool(tournament_id and TOURNAMENT_ID_RE.fullmatch(tournament_id))


def _tournament_exists_sync(tournament_id: str) -> bool:
    rows = (
        get_supabase_client()
        .table("fs_tournaments")
        .select("id")
        .eq("id", tournament_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)


async def tournament_exists(tournament_id: str) -> bool:
    try:
        return await asyncio.to_thread(_tournament_exists_sync, tournament_id)
    except Exception:
        return False


def parse_include_filter(raw: str | None) -> tuple[str, ...] | None:
    if not raw:
        return DEFAULT_INCLUDE

    aliases = {"result": "results", "results": "results", "bout": "bouts", "bouts": "bouts"}
    requested = {aliases.get(item.strip().lower()) for item in raw.split(",") if item.strip()}
    if not requested or None in requested:
        return None
    return tuple(item for item in DEFAULT_INCLUDE if item in requested)


def stable_row_hash(row: dict[str, Any]) -> str:
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def row_identity(stream: str, row: dict[str, Any]) -> str:
    if row.get("id") is not None:
        return str(row["id"])
    if stream == "results":
        fencer_key = row.get("fie_fencer_id") or row.get("fencer_id") or row.get("name")
        return f"{row.get('tournament_id')}:{fencer_key}:{row.get('rank')}"
    if stream == "bouts":
        parts = (
            row.get("tournament_id"),
            row.get("round"),
            row.get("fie_fencer_id_a") or row.get("fencer_a"),
            row.get("fie_fencer_id_b") or row.get("fencer_b"),
            row.get("score_a"),
            row.get("score_b"),
        )
        return ":".join(str(part) for part in parts)
    return stable_row_hash(row)


class LiveResultsPoller:
    def __init__(self, client_factory: Callable[[], Any] = get_supabase_client):
        self.client_factory = client_factory

    def _fetch_rows_sync(self, table_name: str, tournament_id: str) -> list[dict[str, Any]]:
        rows = (
            self.client_factory()
            .table(table_name)
            .select("*")
            .eq("tournament_id", tournament_id)
            .order("id")
            .execute()
            .data
            or []
        )
        return [dict(row) for row in rows]

    async def fetch_rows(self, table_name: str, tournament_id: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._fetch_rows_sync, table_name, tournament_id)

    async def fetch_events(
        self,
        tournament_id: str,
        include: tuple[str, ...],
        snapshots: dict[str, dict[str, str]],
    ) -> list[dict[str, Any]]:
        fetches = [
            (stream, self.fetch_rows(INCLUDE_TO_TABLE[stream], tournament_id))
            for stream in include
        ]
        results = await asyncio.gather(*(fetch for _stream, fetch in fetches))
        events: list[dict[str, Any]] = []

        for (stream, _fetch), rows in zip(fetches, results, strict=False):
            previous = snapshots.setdefault(stream, {})
            next_snapshot: dict[str, str] = {}
            for row in rows:
                identity = row_identity(stream, row)
                row_hash = stable_row_hash(row)
                next_snapshot[identity] = row_hash
                if previous.get(identity) != row_hash:
                    events.append(
                        {
                            "type": INCLUDE_TO_EVENT[stream],
                            "action": "upsert",
                            "tournament_id": tournament_id,
                            "row": row,
                        }
                    )
            snapshots[stream] = next_snapshot

        return events


@dataclass(eq=False)
class LiveClient:
    websocket: WebSocket
    tournament_id: str
    include: tuple[str, ...]
    queue: asyncio.Queue = field(
        default_factory=lambda: asyncio.Queue(maxsize=CLIENT_QUEUE_MAXSIZE)
    )

    def enqueue(self, event: dict[str, Any]) -> bool:
        try:
            self.queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            return False


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[LiveClient] = set()

    async def add(self, client: LiveClient) -> None:
        self._clients.add(client)

    async def remove(self, client: LiveClient) -> None:
        self._clients.discard(client)

    def active_count(self) -> int:
        return len(self._clients)


connection_manager = ConnectionManager()
app.state.connection_manager = connection_manager


def reset_connection_manager() -> None:
    global connection_manager
    connection_manager = ConnectionManager()
    app.state.connection_manager = connection_manager


class ClientBackpressureError(Exception):
    pass


def enqueue_or_backpressure(client: LiveClient, event: dict[str, Any]) -> None:
    if not client.enqueue(event):
        raise ClientBackpressureError("client queue full")


async def send_loop(client: LiveClient) -> None:
    while True:
        event = await client.queue.get()
        await asyncio.wait_for(
            client.websocket.send_json(event),
            timeout=SEND_TIMEOUT_SECONDS,
        )


async def receive_loop(client: LiveClient) -> None:
    while True:
        message = await client.websocket.receive()
        if message.get("type") == "websocket.disconnect":
            raise WebSocketDisconnect(code=message.get("code", 1000))


async def close_before_accept(websocket: WebSocket, reason: str) -> None:
    await websocket.close(code=POLICY_VIOLATION, reason=reason)


@app.websocket("/ws/live-results/{tournament_id}")
async def live_results_socket(websocket: WebSocket, tournament_id: str):
    include = parse_include_filter(websocket.query_params.get("include"))
    api_key = api_key_from_websocket(websocket)

    if include is None:
        await close_before_accept(websocket, "Invalid include filter")
        return
    if not is_valid_tournament_id(tournament_id):
        await close_before_accept(websocket, "Invalid tournament id")
        return
    if not await is_authorized_api_key(api_key, tournament_id):
        await close_before_accept(websocket, "Invalid API key")
        return
    if not await tournament_exists(tournament_id):
        await close_before_accept(websocket, "Tournament not found")
        return

    await websocket.accept()

    client = LiveClient(websocket=websocket, tournament_id=tournament_id, include=include)
    await connection_manager.add(client)
    sender = asyncio.create_task(send_loop(client))
    receiver = asyncio.create_task(receive_loop(client))
    poller = LiveResultsPoller()
    snapshots: dict[str, dict[str, str]] = {}
    last_heartbeat = 0.0

    try:
        enqueue_or_backpressure(
            client,
            {
                "type": "subscribed",
                "tournament_id": tournament_id,
                "include": list(include),
            },
        )

        while True:
            if sender.done() or receiver.done():
                break

            try:
                for event in await poller.fetch_events(tournament_id, include, snapshots):
                    enqueue_or_backpressure(client, event)
            except Exception:
                enqueue_or_backpressure(
                    client,
                    {
                        "type": "error",
                        "tournament_id": tournament_id,
                        "detail": "Live result polling failed; retrying",
                    },
                )

            now = asyncio.get_running_loop().time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
                enqueue_or_backpressure(
                    client,
                    {
                        "type": "heartbeat",
                        "tournament_id": tournament_id,
                        "timestamp": utc_now_iso(),
                    },
                )
                last_heartbeat = now

            await asyncio.sleep(min(POLL_INTERVAL_SECONDS, HEARTBEAT_INTERVAL_SECONDS))
    except (WebSocketDisconnect, ClientBackpressureError):
        with contextlib.suppress(Exception):
            await websocket.close(code=TRY_AGAIN_LATER, reason="Connection closed")
    finally:
        for task in (sender, receiver):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        await connection_manager.remove(client)

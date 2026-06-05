import json
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, timedelta, timezone, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

ACTIVE_QUERY_LOOKBACK_DAYS = 2
TOURNAMENT_SELECT = (
    "id,name,season,start_date,end_date,competition_url_id,weapon,gender,category,type,country"
)
RESULT_SELECT = (
    "id,tournament_id,fencer_id,fie_fencer_id,name,country,nationality,rank,placement,"
    "victory,matches,td,tr,diff,updated_at"
)
BOUT_SELECT = (
    "id,tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,round,updated_at,created_at"
)
FENCER_SELECT = "id,name,country,nationality"


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except Exception:
        return default


OVERLAY_CACHE_SECONDS = _env_int("OBS_OVERLAY_CACHE_SECONDS", 5)
OVERLAY_RATE_LIMIT_PER_MINUTE = _env_int("OBS_OVERLAY_RATE_LIMIT_PER_MINUTE", 120, minimum=1)
RATE_WINDOW_SECONDS = 60

_supabase_client = None
_cache_lock = Lock()
_payload_cache: dict[tuple[str | None, str | None], tuple[float, dict[str, Any]]] = {}
_rate_limit_lock = Lock()
_rate_limits: dict[str, deque[float]] = defaultdict(deque)

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


app = FastAPI(title="FenceSpace OBS Overlay", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["Content-Type", "X-Overlay-Token"],
)

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend" / "obs-overlay"
if FRONTEND_DIR.exists():
    app.mount("/obs-overlay", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="obs-overlay")


@dataclass(frozen=True)
class OverlaySelection:
    tournament_id: str | None = None
    event_id: str | None = None

    @property
    def cache_key(self) -> tuple[str | None, str | None]:
        return self.tournament_id, self.event_id


def reset_overlay_state() -> None:
    with _cache_lock:
        _payload_cache.clear()
    with _rate_limit_lock:
        _rate_limits.clear()


def get_supabase_client():
    if hasattr(app.state, "supabase_client"):
        return app.state.supabase_client

    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("Supabase credentials are not configured")
        from supabase import create_client

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def _validate_identifier(name: str, value: str | None, pattern: re.Pattern[str]) -> str | None:
    if value is None or value == "":
        return None
    if not pattern.fullmatch(value):
        raise HTTPException(status_code=400, detail=f"Invalid {name}")
    return value


def _overlay_tokens() -> dict[str, Any]:
    raw = os.environ.get("OBS_OVERLAY_TOKENS") or os.environ.get("FENCESPACE_OBS_OVERLAY_TOKENS")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Overlay token config is invalid") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=500, detail="Overlay token config is invalid")
    return parsed


def resolve_selection(
    tournament_id: str | None,
    event_id: str | None,
    token: str | None,
) -> OverlaySelection:
    provided = [value for value in (tournament_id, event_id, token) if value]
    if len(provided) > 1:
        raise HTTPException(status_code=400, detail="Use only one of tournament_id, event_id, or token")

    if token:
        token = _validate_identifier("token", token, _TOKEN_RE)
        tokens = _overlay_tokens()
        if token not in tokens:
            raise HTTPException(status_code=400, detail="Unknown overlay token")

        configured = tokens[token]
        if isinstance(configured, str):
            tournament_id = configured
            event_id = None
        elif isinstance(configured, dict):
            tournament_id = configured.get("tournament_id")
            event_id = configured.get("event_id")
        else:
            raise HTTPException(status_code=500, detail="Overlay token config is invalid")

        if bool(tournament_id) == bool(event_id):
            raise HTTPException(status_code=500, detail="Overlay token config is invalid")

    tournament_id = _validate_identifier("tournament_id", tournament_id, _ID_RE)
    event_id = _validate_identifier("event_id", event_id, _ID_RE)
    return OverlaySelection(tournament_id=tournament_id, event_id=event_id)


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return None


def _execute_rows(query, table_name: str) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except Exception as exc:
        raise RuntimeError(f"{table_name} query failed") from exc


def _active_tournament_rows(client, selection: OverlaySelection) -> list[dict[str, Any]]:
    query = client.table("fs_tournaments").select(TOURNAMENT_SELECT)
    if selection.tournament_id:
        query = query.eq("id", selection.tournament_id)
    elif selection.event_id:
        query = query.eq("competition_url_id", selection.event_id)
    today = date.today()
    oldest_end = (today - timedelta(days=ACTIVE_QUERY_LOOKBACK_DAYS)).isoformat()
    query = (
        query.lte("start_date", today.isoformat())
        .gte("end_date", oldest_end)
        .not_.is_("competition_url_id", "null")
        .order("start_date", desc=True)
    )
    return _execute_rows(query.limit(1), "fs_tournaments")


def _fetch_results(client, tournament_id: str) -> list[dict[str, Any]]:
    return _execute_rows(
        client.table("fs_results")
        .select(RESULT_SELECT)
        .eq("tournament_id", tournament_id)
        .order("rank")
        .limit(8),
        "fs_results",
    )


def _fetch_bouts(client, tournament_id: str) -> list[dict[str, Any]]:
    return _execute_rows(
        client.table("fs_bouts")
        .select(BOUT_SELECT)
        .eq("tournament_id", tournament_id)
        .order("updated_at", desc=True)
        .limit(8),
        "fs_bouts",
    )


def _fetch_fencers(client, bouts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    fencer_ids = sorted(
        {
            str(value)
            for row in bouts
            for value in (row.get("fencer_a_id"), row.get("fencer_b_id"), row.get("winner_id"))
            if value
        }
    )
    if not fencer_ids:
        return {}
    rows = _execute_rows(
        client.table("fs_fencers").select(FENCER_SELECT).in_("id", fencer_ids),
        "fs_fencers",
    )
    return {str(row.get("id")): row for row in rows if row.get("id")}


def _leader_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    leaders = []
    for row in rows:
        rank = _safe_int(row.get("rank") or row.get("placement"))
        leaders.append(
            {
                "rank": rank,
                "name": row.get("name") or "Unknown",
                "country": row.get("country") or row.get("nationality"),
                "fie_fencer_id": str(row.get("fie_fencer_id")) if row.get("fie_fencer_id") is not None else None,
            }
        )
    return leaders


def _result_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup = {}
    for row in rows:
        fencer_id = row.get("fencer_id")
        if fencer_id and str(fencer_id) not in lookup:
            lookup[str(fencer_id)] = row
    return lookup


def _fencer_payload(
    fencer_id: Any,
    fencers: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    key = str(fencer_id) if fencer_id is not None else None
    fencer = fencers.get(key or "") or results.get(key or "") or {}
    return {
        "id": key,
        "name": fencer.get("name") or key or "TBD",
        "country": fencer.get("country") or fencer.get("nationality"),
    }


def _bout_status(row: dict[str, Any]) -> str:
    if row.get("winner_id"):
        return "final"
    score_a = _safe_int(row.get("score_a"))
    score_b = _safe_int(row.get("score_b"))
    if score_a is None and score_b is None:
        return "pending"
    return "live"


def _bout_payload(
    rows: list[dict[str, Any]],
    fencers: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    bouts = []
    for row in rows:
        bouts.append(
            {
                "id": row.get("id"),
                "round": row.get("round") or "Bout",
                "fencer_a": _fencer_payload(row.get("fencer_a_id"), fencers, results),
                "fencer_b": _fencer_payload(row.get("fencer_b_id"), fencers, results),
                "score": {"a": _safe_int(row.get("score_a")), "b": _safe_int(row.get("score_b"))},
                "winner_id": str(row.get("winner_id")) if row.get("winner_id") else None,
                "status": _bout_status(row),
                "updated_at": row.get("updated_at") or row.get("created_at"),
            }
        )
    return bouts


def _event_payload(tournament: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(tournament.get("id")),
        "name": tournament.get("name") or "Live Tournament",
        "event_id": (
            str(tournament.get("competition_url_id"))
            if tournament.get("competition_url_id") is not None
            else None
        ),
        "season": tournament.get("season"),
        "start_date": tournament.get("start_date"),
        "end_date": tournament.get("end_date"),
        "weapon": tournament.get("weapon"),
        "gender": tournament.get("gender"),
        "category": tournament.get("category"),
        "type": tournament.get("type"),
        "country": tournament.get("country"),
    }


def _no_active_payload(selection: OverlaySelection) -> dict[str, Any]:
    message = "No active tournament is currently available for the OBS overlay"
    if selection.tournament_id or selection.event_id:
        message = "No active tournament matched the overlay selection"
    return {
        "status": "no_active_event",
        "active": False,
        "message": message,
        "event": None,
        "leaders": [],
        "bouts": [],
        "updated_at": _now_timestamp(),
    }


def build_live_score_payload(selection: OverlaySelection) -> dict[str, Any]:
    client = get_supabase_client()
    tournaments = _active_tournament_rows(client, selection)
    if not tournaments:
        return _no_active_payload(selection)

    tournament = tournaments[0]
    tournament_id = str(tournament.get("id"))
    results = _fetch_results(client, tournament_id)
    bouts = _fetch_bouts(client, tournament_id)
    fencers = _fetch_fencers(client, bouts)
    results_by_fencer = _result_lookup(results)

    return {
        "status": "active",
        "active": True,
        "message": "Live tournament data available",
        "event": _event_payload(tournament),
        "leaders": _leader_payload(results),
        "bouts": _bout_payload(bouts, fencers, results_by_fencer),
        "updated_at": _now_timestamp(),
    }


def _cache_headers(cache_state: str) -> dict[str, str]:
    stale_seconds = max(OVERLAY_CACHE_SECONDS * 3, OVERLAY_CACHE_SECONDS)
    return {
        "Cache-Control": f"public, max-age={OVERLAY_CACHE_SECONDS}, stale-while-revalidate={stale_seconds}",
        "X-Overlay-Cache": cache_state,
        "X-RateLimit-Limit": str(OVERLAY_RATE_LIMIT_PER_MINUTE),
    }


def _overlay_response(payload: dict[str, Any], *, status_code: int = 200, cache_state: str = "miss"):
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers=_cache_headers(cache_state),
    )


def _cached_payload(selection: OverlaySelection, now: float) -> dict[str, Any] | None:
    if OVERLAY_CACHE_SECONDS <= 0:
        return None
    with _cache_lock:
        cached = _payload_cache.get(selection.cache_key)
        if not cached:
            return None
        expires_at, payload = cached
        if expires_at < now:
            _payload_cache.pop(selection.cache_key, None)
            return None
        return payload


def _store_payload(selection: OverlaySelection, payload: dict[str, Any], now: float) -> None:
    if OVERLAY_CACHE_SECONDS <= 0:
        return
    with _cache_lock:
        _payload_cache[selection.cache_key] = (now + OVERLAY_CACHE_SECONDS, payload)


def _rate_identifier(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_rate_limit(identifier: str, now: float | None = None) -> tuple[bool, int]:
    now = now if now is not None else time.time()
    window_start = now - RATE_WINDOW_SECONDS
    with _rate_limit_lock:
        requests = _rate_limits[identifier]
        while requests and requests[0] <= window_start:
            requests.popleft()
        if len(requests) >= OVERLAY_RATE_LIMIT_PER_MINUTE:
            retry_after = max(1, int(RATE_WINDOW_SECONDS - (now - requests[0])))
            return False, retry_after
        requests.append(now)
    return True, 0


@app.middleware("http")
async def overlay_rate_limit(request: Request, call_next):
    if request.url.path != "/overlay/live-score":
        return await call_next(request)

    allowed, retry_after = _check_rate_limit(_rate_identifier(request))
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"status": "rate_limited", "active": False, "message": "Overlay rate limit exceeded"},
            headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(OVERLAY_RATE_LIMIT_PER_MINUTE)},
        )
    return await call_next(request)


@app.get("/overlay/live-score")
def live_score_overlay(
    tournament_id: str | None = None,
    event_id: str | None = None,
    token: str | None = None,
    overlay_token: str | None = Header(default=None, alias="X-Overlay-Token"),
):
    selection = resolve_selection(tournament_id, event_id, overlay_token or token)
    now = time.time()
    cached = _cached_payload(selection, now)
    if cached is not None:
        return _overlay_response(cached, cache_state="hit")

    try:
        payload = build_live_score_payload(selection)
    except Exception:
        return _overlay_response(
            {
                "status": "error",
                "active": False,
                "message": "Live overlay data source is unavailable",
                "event": None,
                "leaders": [],
                "bouts": [],
                "updated_at": _now_timestamp(),
            },
            status_code=502,
            cache_state="bypass",
        )

    _store_payload(selection, payload, now)
    return _overlay_response(payload, cache_state="miss")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("OBS_OVERLAY_PORT", "8000")))


if __name__ == "__main__":
    main()

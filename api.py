import hashlib
import importlib.util
import os
import pathlib
import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


def _load_v1_router(name: str):
    path = pathlib.Path(__file__).parent / "api" / "v1" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_api_v1_{name}", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


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

DEFAULT_LIMIT = 50
MAX_LIMIT = 500
RATE_LIMIT_PER_MINUTE = int(os.environ.get("FENCESPACE_RATE_LIMIT_PER_MINUTE", "100"))
RATE_WINDOW_SECONDS = 60
TABLE_SELECT_COLUMNS = {
    "fs_fencers": "id,fie_id,name,country,weapon,category,gender,world_rank,fie_points",
    "fs_fencer_career_stats": "fencer_id,total_competitions,gold_medals,silver_medals,bronze_medals",
    "fs_fencer_social_media": "fencer_id,platform,url,handle",
    "fs_fencer_equipment": "fencer_id,brand,equipment_type,sponsor_name,source,source_url,confidence",
    "fs_tournaments": "id,fie_id,season,name,country,type,start_date,end_date",
    "fs_results": "id,tournament_id,fencer_id,rank,name,nationality,points",
    "fs_rankings_history": "id,season,weapon,gender,category,rank,name,country,points",
    "fs_head_to_head": (
        "id,fencer_a_id,fencer_b_id,weapon,a_wins,b_wins,a_touches,b_touches,"
        "bouts_total,last_meeting_date,last_winner_id"
    ),
    "fs_country_depth": (
        "country,weapon,category,fencers_in_top16,fencers_in_top32,"
        "fencers_in_top64,total_ranked,avg_world_rank"
    ),
}

_supabase_client = None
_rate_limit_lock = Lock()
_rate_limits: dict[str, deque[float]] = defaultdict(deque)


app = FastAPI(title="FenceSpace Export API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
)


def reset_rate_limits() -> None:
    with _rate_limit_lock:
        _rate_limits.clear()


def get_supabase_client():
    if hasattr(app.state, "supabase_client"):
        return app.state.supabase_client

    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise HTTPException(status_code=500, detail="Supabase credentials are not configured")
        from supabase import create_client

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def _row_allows_key(row: dict[str, Any]) -> bool:
    if row.get("revoked") is True:
        return False
    if row.get("active") is False:
        return False
    return True


def hash_primary_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _lookup_api_key_row(client: Any, api_key: str) -> dict[str, Any] | None:
    key_hash = hash_primary_api_key(api_key)
    rows = (
        client.table("fs_api_keys")
        .select("key_hash,key,active,revoked")
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
        client.table("fs_api_keys")
        .select("key_hash,key,active,revoked")
        .eq("key", api_key)
        .limit(1)
        .execute()
        .data
        or []
    )
    return legacy_rows[0] if legacy_rows else None


def is_valid_api_key_for_client(client: Any, api_key: str) -> bool:
    if api_key in ENV_API_KEYS:
        return True

    try:
        row = _lookup_api_key_row(client, api_key)
    except Exception:
        return False

    return bool(row and _row_allows_key(row))


def is_valid_api_key(api_key: str) -> bool:
    return is_valid_api_key_for_client(get_supabase_client(), api_key)


def check_rate_limit(api_key: str, now: float | None = None) -> tuple[bool, int]:
    now = now if now is not None else time.time()
    window_start = now - RATE_WINDOW_SECONDS
    with _rate_limit_lock:
        requests = _rate_limits[api_key]
        while requests and requests[0] <= window_start:
            requests.popleft()
        if len(requests) >= RATE_LIMIT_PER_MINUTE:
            retry_after = max(1, int(RATE_WINDOW_SECONDS - (now - requests[0])))
            return False, retry_after
        requests.append(now)
    return True, 0


@app.middleware("http")
async def api_auth_and_readonly_guard(request: Request, call_next):
    path = request.url.path
    if path in {"/docs", "/openapi.json", "/redoc"} or path.startswith("/docs/"):
        return await call_next(request)

    if request.method == "OPTIONS":
        return await call_next(request)
    if request.method not in {"GET", "HEAD"}:
        return JSONResponse(status_code=405, content={"detail": "Method not allowed"})

    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return JSONResponse(status_code=401, content={"detail": "Missing API key"})
    if not is_valid_api_key(api_key):
        return JSONResponse(status_code=401, content={"detail": "Invalid API key"})

    allowed, retry_after = check_rate_limit(api_key)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry_after)},
        )

    return await call_next(request)


def execute_rows(query, table_name: str) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase query failed for {table_name}") from exc


def execute_optional_rows(query) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except Exception:
        return []


def select_columns(table_name: str) -> str:
    columns = TABLE_SELECT_COLUMNS.get(table_name)
    if not columns:
        raise HTTPException(status_code=500, detail=f"No public column allowlist configured for {table_name}")
    return columns


def first_row(table_name: str, column: str, value: Any, *, optional: bool = False) -> dict[str, Any] | None:
    query = get_supabase_client().table(table_name).select(select_columns(table_name)).eq(column, value).limit(1)
    rows = execute_optional_rows(query) if optional else execute_rows(query, table_name)
    return rows[0] if rows else None


def list_rows(
    table_name: str,
    configure: Callable[[Any], Any] | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> list[dict[str, Any]]:
    query = get_supabase_client().table(table_name).select(select_columns(table_name))
    if configure:
        query = configure(query)
    return execute_rows(query.range(offset, offset + limit - 1), table_name)


def paginated_payload(rows: list[dict[str, Any]], limit: int, offset: int) -> dict[str, Any]:
    return {"data": rows, "pagination": {"limit": limit, "offset": offset, "count": len(rows)}}


def _apply_eq(query, column: str, value: Any):
    if value is None or value == "":
        return query
    return query.eq(column, value)


def _apply_ilike(query, column: str, value: str | None):
    if not value:
        return query
    return query.ilike(column, f"%{value}%")


@app.get("/fencer/search")
def search_fencers(
    name: str | None = None,
    country: str | None = None,
    weapon: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    def configure(query):
        query = _apply_ilike(query, "name", name)
        query = _apply_eq(query, "country", country)
        return _apply_eq(query, "weapon", weapon)

    return paginated_payload(list_rows("fs_fencers", configure, limit=limit, offset=offset), limit, offset)


@app.get("/fencer/{fencer_id}")
def get_fencer(fencer_id: str):
    profile = first_row("fs_fencers", "id", fencer_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Fencer not found")

    career_stats = first_row("fs_fencer_career_stats", "fencer_id", fencer_id, optional=True)
    social = execute_optional_rows(
        get_supabase_client()
        .table("fs_fencer_social_media")
        .select(select_columns("fs_fencer_social_media"))
        .eq("fencer_id", fencer_id)
    )
    equipment = execute_optional_rows(
        get_supabase_client()
        .table("fs_fencer_equipment")
        .select(select_columns("fs_fencer_equipment"))
        .eq("fencer_id", fencer_id)
    )

    return {
        "profile": profile,
        "career_stats": career_stats,
        "social": social,
        "equipment": equipment,
    }


@app.get("/tournaments")
def list_tournaments(
    season: int | None = None,
    type: str | None = None,
    country: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    def configure(query):
        query = _apply_eq(query, "season", season)
        query = _apply_eq(query, "type", type)
        return _apply_eq(query, "country", country)

    return paginated_payload(list_rows("fs_tournaments", configure, limit=limit, offset=offset), limit, offset)


@app.get("/tournaments/{tournament_id}/results")
def tournament_results(
    tournament_id: str,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    rows = list_rows(
        "fs_results",
        lambda query: query.eq("tournament_id", tournament_id),
        limit=limit,
        offset=offset,
    )
    return paginated_payload(rows, limit, offset)


@app.get("/rankings")
def rankings(
    season: int | None = None,
    weapon: str | None = None,
    gender: str | None = None,
    category: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    def configure(query):
        query = _apply_eq(query, "season", season)
        query = _apply_eq(query, "weapon", weapon)
        query = _apply_eq(query, "gender", gender)
        return _apply_eq(query, "category", category)

    return paginated_payload(list_rows("fs_rankings_history", configure, limit=limit, offset=offset), limit, offset)


@app.get("/h2h/{fencer_a}/{fencer_b}")
def head_to_head(fencer_a: str, fencer_b: str):
    left, right = sorted([fencer_a, fencer_b])
    rows = execute_rows(
        get_supabase_client()
        .table("fs_head_to_head")
        .select(select_columns("fs_head_to_head"))
        .eq("fencer_a_id", left)
        .eq("fencer_b_id", right),
        "fs_head_to_head",
    )
    return {"fencer_a": fencer_a, "fencer_b": fencer_b, "data": rows}


@app.get("/countries/{code}/depth")
def country_depth(
    code: str,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    rows = list_rows(
        "fs_country_depth",
        lambda query: query.eq("country", code.upper()),
        limit=limit,
        offset=offset,
    )
    return paginated_payload(rows, limit, offset)


for _v1_name in (
    "fencer_h2h",
    "fencer_milestones",
    "fencer_ranking_trajectory",
    "fencer_stats",
    "tournament_brackets",
    "tournament_details",
):
    app.include_router(_load_v1_router(_v1_name).router)

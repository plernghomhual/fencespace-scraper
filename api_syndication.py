import hashlib
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Coroutine

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

API_PREFIX = "/syndication/v1"
DEFAULT_LIMIT = 50
MAX_LIMIT = 500
DEFAULT_RATE_LIMIT_PER_MINUTE = int(os.environ.get("FENCESPACE_SYNDICATION_RATE_LIMIT_PER_MINUTE", "100"))
RATE_WINDOW_SECONDS = 60

KEY_TABLE = "fs_syndication_keys"
LOG_TABLE = "fs_syndication_request_logs"

SENSITIVE_QUERY_KEYS = {
    "api_key",
    "apikey",
    "key",
    "token",
    "access_token",
    "secret",
    "authorization",
    "password",
}

FENCER_COLUMNS = ("id", "name", "country", "weapon", "category", "world_rank", "fie_points", "image_url")
TOURNAMENT_COLUMNS = ("id", "name", "season", "start_date", "end_date", "country", "weapon", "category", "type")
RANKING_COLUMNS = ("id", "season", "weapon", "gender", "category", "rank", "fencer_id", "name", "country", "points")
RESULT_COLUMNS = ("id", "tournament_id", "fencer_id", "rank", "name", "nationality", "country")
MEDAL_TABLE_COLUMNS = ("id", "scope", "country", "fencer_id", "tier", "gold", "silver", "bronze", "total", "updated_at")


_supabase_client: Any = None
_rate_limit_lock = Lock()
_rate_limits: dict[str, deque[float]] = defaultdict(deque)


class Pagination(BaseModel):
    limit: int
    offset: int
    count: int


class FencerSchema(BaseModel):
    id: str | None = None
    name: str | None = None
    country: str | None = None
    weapon: str | None = None
    category: str | None = None
    world_rank: int | None = None
    fie_points: float | None = None
    image_url: str | None = None


class TournamentSchema(BaseModel):
    id: str | None = None
    name: str | None = None
    season: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    country: str | None = None
    weapon: str | None = None
    category: str | None = None
    type: str | None = None


class RankingSchema(BaseModel):
    id: str | None = None
    season: int | str | None = None
    weapon: str | None = None
    gender: str | None = None
    category: str | None = None
    rank: int | None = None
    fencer_id: str | None = None
    name: str | None = None
    country: str | None = None
    points: float | None = None


class ResultSchema(BaseModel):
    id: str | None = None
    tournament_id: str | None = None
    fencer_id: str | None = None
    rank: int | None = None
    name: str | None = None
    nationality: str | None = None
    country: str | None = None


class MedalTableSchema(BaseModel):
    id: str | None = None
    scope: str | None = None
    country: str | None = None
    fencer_id: str | None = None
    tier: str | None = None
    gold: int | None = None
    silver: int | None = None
    bronze: int | None = None
    total: int | None = None
    updated_at: str | None = None


class FencerListResponse(BaseModel):
    data: list[FencerSchema]
    pagination: Pagination


class TournamentListResponse(BaseModel):
    data: list[TournamentSchema]
    pagination: Pagination


class RankingListResponse(BaseModel):
    data: list[RankingSchema]
    pagination: Pagination


class ResultListResponse(BaseModel):
    data: list[ResultSchema]
    pagination: Pagination


class MedalTableListResponse(BaseModel):
    data: list[MedalTableSchema]
    pagination: Pagination


@dataclass(frozen=True)
class PartnerKey:
    id: str
    partner_name: str
    scopes: frozenset[str]
    rate_limit_per_minute: int


router = APIRouter(prefix=API_PREFIX, tags=["syndication"])


def reset_rate_limits() -> None:
    with _rate_limit_lock:
        _rate_limits.clear()


def get_supabase_client(request: Request | None = None):
    if request is not None and hasattr(request.app.state, "supabase_client"):
        return request.app.state.supabase_client

    if hasattr(app.state, "supabase_client"):
        return app.state.supabase_client

    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise HTTPException(status_code=500, detail="Supabase credentials are not configured")
        from supabase import create_client

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _extract_api_key(request: Request) -> str | None:
    header_key = request.headers.get("X-API-Key")
    if header_key and header_key.strip():
        return header_key.strip()

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()

    return None


def _load_partner(api_key: str, request: Request) -> PartnerKey | None:
    try:
        rows = (
            get_supabase_client(request)
            .table(KEY_TABLE)
            .select("id,partner_name,scopes,rate_limit_per_minute,disabled")
            .eq("key_hash", _hash_api_key(api_key))
            .limit(1)
            .execute()
            .data
            or []
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Syndication auth lookup failed") from exc

    if not rows:
        return None

    row = rows[0]
    if row.get("disabled") is True:
        return None

    scopes = row.get("scopes") or []
    if not isinstance(scopes, list):
        scopes = []

    try:
        rate_limit = int(row.get("rate_limit_per_minute") or DEFAULT_RATE_LIMIT_PER_MINUTE)
    except (TypeError, ValueError):
        rate_limit = DEFAULT_RATE_LIMIT_PER_MINUTE

    return PartnerKey(
        id=str(row.get("id")),
        partner_name=str(row.get("partner_name") or "unknown"),
        scopes=frozenset(str(scope) for scope in scopes),
        rate_limit_per_minute=max(1, rate_limit),
    )


def _check_rate_limit(partner: PartnerKey, now: float | None = None) -> tuple[bool, int]:
    now = now if now is not None else time.time()
    window_start = now - RATE_WINDOW_SECONDS
    with _rate_limit_lock:
        requests = _rate_limits[partner.id]
        while requests and requests[0] <= window_start:
            requests.popleft()
        if len(requests) >= partner.rate_limit_per_minute:
            retry_after = max(1, int(RATE_WINDOW_SECONDS - (now - requests[0])))
            return False, retry_after
        requests.append(now)
    return True, 0


def _mark_last_used(partner: PartnerKey, used_at: str, request: Request) -> None:
    try:
        get_supabase_client(request).table(KEY_TABLE).update({"last_used_at": used_at}).eq("id", partner.id).execute()
    except Exception:
        return


def require_scope(scope: str) -> Callable[[Request], Coroutine[Any, Any, PartnerKey]]:
    async def dependency(request: Request) -> PartnerKey:
        api_key = _extract_api_key(request)
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing API key")

        partner = _load_partner(api_key, request)
        if partner is None:
            raise HTTPException(status_code=401, detail="Invalid API key")

        request.state.syndication_partner = partner
        request.state.syndication_scope = scope
        used_at = getattr(request.state, "syndication_created_at", _utc_now_iso())
        _mark_last_used(partner, used_at, request)

        if "*" not in partner.scopes and scope not in partner.scopes:
            raise HTTPException(status_code=403, detail=f"API key lacks scope {scope}")

        allowed, retry_after = _check_rate_limit(partner)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

        return partner

    return dependency


def _apply_eq(query, column: str, value: Any):
    if value is None or value == "":
        return query
    return query.eq(column, value)


def _apply_ilike(query, column: str, value: str | None):
    if not value:
        return query
    return query.ilike(column, f"%{value}%")


def _project_rows(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> list[dict[str, Any]]:
    allowed = set(columns)
    return [{column: row.get(column) for column in columns if column in row and column in allowed} for row in rows]


def _execute_rows(query, table_name: str) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase query failed for {table_name}") from exc


def _list_resource(
    request: Request,
    table_name: str,
    columns: tuple[str, ...],
    configure: Callable[[Any], Any] | None,
    *,
    limit: int,
    offset: int,
    order_by: str | None = None,
) -> dict[str, Any]:
    query = get_supabase_client(request).table(table_name).select(",".join(columns))
    if configure:
        query = configure(query)
    if order_by:
        query = query.order(order_by)
    rows = _execute_rows(query.range(offset, offset + limit - 1), table_name)
    projected = _project_rows(rows, columns)
    return {"data": projected, "pagination": {"limit": limit, "offset": offset, "count": len(projected)}}


def _sanitize_query_params(request: Request) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        if key.lower() in SENSITIVE_QUERY_KEYS:
            sanitized[key] = "[redacted]"
        else:
            sanitized[key] = value
    return sanitized


def _hash_remote_addr(request: Request) -> str | None:
    if request.client is None or not request.client.host:
        return None
    return hashlib.sha256(request.client.host.encode("utf-8")).hexdigest()


def _log_request(request: Request, status_code: int, created_at: str) -> None:
    partner = getattr(request.state, "syndication_partner", None)
    if partner is None:
        return

    row = {
        "key_id": partner.id,
        "partner_name": partner.partner_name,
        "scope": getattr(request.state, "syndication_scope", None),
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "query_params": _sanitize_query_params(request),
        "ip_hash": _hash_remote_addr(request),
        "user_agent": request.headers.get("User-Agent"),
        "created_at": created_at,
    }
    try:
        get_supabase_client(request).table(LOG_TABLE).insert(row).execute()
    except Exception:
        return


@router.get("/fencers", response_model=FencerListResponse)
def list_fencers(
    request: Request,
    _partner: PartnerKey = Depends(require_scope("fencers:read")),
    name: str | None = None,
    country: str | None = None,
    weapon: str | None = None,
    category: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    def configure(query):
        query = _apply_ilike(query, "name", name)
        query = _apply_eq(query, "country", country)
        query = _apply_eq(query, "weapon", weapon)
        return _apply_eq(query, "category", category)

    return _list_resource(
        request,
        "v_fencer_public",
        FENCER_COLUMNS,
        configure,
        limit=limit,
        offset=offset,
        order_by="name",
    )


@router.get("/tournaments", response_model=TournamentListResponse)
def list_tournaments(
    request: Request,
    _partner: PartnerKey = Depends(require_scope("tournaments:read")),
    season: int | None = None,
    type: str | None = None,
    country: str | None = None,
    weapon: str | None = None,
    category: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    def configure(query):
        query = _apply_eq(query, "season", season)
        query = _apply_eq(query, "type", type)
        query = _apply_eq(query, "country", country)
        query = _apply_eq(query, "weapon", weapon)
        return _apply_eq(query, "category", category)

    return _list_resource(
        request,
        "v_tournament_public",
        TOURNAMENT_COLUMNS,
        configure,
        limit=limit,
        offset=offset,
        order_by="start_date",
    )


@router.get("/rankings", response_model=RankingListResponse)
def list_rankings(
    request: Request,
    _partner: PartnerKey = Depends(require_scope("rankings:read")),
    season: int | None = None,
    weapon: str | None = None,
    gender: str | None = None,
    category: str | None = None,
    country: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    def configure(query):
        query = _apply_eq(query, "season", season)
        query = _apply_eq(query, "weapon", weapon)
        query = _apply_eq(query, "gender", gender)
        query = _apply_eq(query, "category", category)
        return _apply_eq(query, "country", country)

    return _list_resource(
        request,
        "fs_rankings_history",
        RANKING_COLUMNS,
        configure,
        limit=limit,
        offset=offset,
        order_by="rank",
    )


@router.get("/results", response_model=ResultListResponse)
def list_results(
    request: Request,
    _partner: PartnerKey = Depends(require_scope("results:read")),
    tournament_id: str | None = None,
    fencer_id: str | None = None,
    country: str | None = None,
    nationality: str | None = None,
    name: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    def configure(query):
        query = _apply_eq(query, "tournament_id", tournament_id)
        query = _apply_eq(query, "fencer_id", fencer_id)
        query = _apply_eq(query, "country", country)
        query = _apply_eq(query, "nationality", nationality)
        return _apply_ilike(query, "name", name)

    return _list_resource(request, "fs_results", RESULT_COLUMNS, configure, limit=limit, offset=offset, order_by="rank")


@router.get("/medal-tables", response_model=MedalTableListResponse)
def list_medal_tables(
    request: Request,
    _partner: PartnerKey = Depends(require_scope("medals:read")),
    scope: str | None = None,
    country: str | None = None,
    fencer_id: str | None = None,
    tier: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    def configure(query):
        query = _apply_eq(query, "scope", scope)
        query = _apply_eq(query, "country", country)
        query = _apply_eq(query, "fencer_id", fencer_id)
        return _apply_eq(query, "tier", tier)

    return _list_resource(
        request,
        "fs_medal_tables",
        MEDAL_TABLE_COLUMNS,
        configure,
        limit=limit,
        offset=offset,
        order_by="total",
    )


app = FastAPI(title="FenceSpace Syndication API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["X-API-Key", "Authorization", "Content-Type"],
)


@app.middleware("http")
async def read_only_and_logging_middleware(request: Request, call_next):
    path = request.url.path
    if path in {"/docs", "/openapi.json", "/redoc"} or path.startswith("/docs/"):
        return await call_next(request)

    if request.method == "OPTIONS":
        return await call_next(request)

    created_at = _utc_now_iso()
    request.state.syndication_created_at = created_at

    if path.startswith(API_PREFIX) and request.method not in {"GET", "HEAD"}:
        response = JSONResponse(status_code=405, content={"detail": "Method not allowed"})
        _log_request(request, 405, created_at)
        return response

    try:
        response = await call_next(request)
    except Exception:
        if path.startswith(API_PREFIX):
            _log_request(request, 500, created_at)
        raise

    if path.startswith(API_PREFIX):
        _log_request(request, response.status_code, created_at)
    return response


app.include_router(router)

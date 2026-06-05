import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import UTC, date, datetime
from typing import Any, Callable
from urllib.parse import urlparse

import requests
from fastapi import Body, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
STRIPE_API_BASE = "https://api.stripe.com/v1"
STRIPE_API_VERSION = "2026-02-25.clover"
WEBHOOK_TOLERANCE_SECONDS = int(os.environ.get("STRIPE_WEBHOOK_TOLERANCE_SECONDS", "300"))
ALLOWED_SUBSCRIPTION_STATUSES = {"active", "trialing"}
DEFAULT_LIMIT = 50
MAX_LIMIT = 500
DEFAULT_MARKETPLACE_REDIRECT_HOSTS = {"app.fencespace.com", "www.fencespace.com", "localhost", "127.0.0.1", "::1"}

logger = logging.getLogger(__name__)
_supabase_client = None

app = FastAPI(title="FenceSpace Marketplace API", version="1.0.0")


class StripeConfigurationError(RuntimeError):
    """Raised before any unsafe or incomplete Stripe API request is made."""


class StripeSignatureError(ValueError):
    """Raised when a Stripe webhook signature cannot be verified."""


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


def hash_api_key(raw_key: str, *, pepper: str | None = None) -> str:
    if not raw_key:
        raise ValueError("API key is required")
    pepper = pepper if pepper is not None else os.environ.get("FENCESPACE_MARKETPLACE_KEY_PEPPER", "")
    return hashlib.sha256(f"{pepper}:{raw_key}".encode("utf-8")).hexdigest()


def generate_api_key(prefix: str = "fs_market_test") -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def parse_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        parsed = datetime.fromisoformat(normalized)
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise ValueError(f"unsupported timestamp: {value!r}")


def _execute_rows(query, table_name: str) -> list[dict[str, Any]]:
    try:
        return query.execute().data or []
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase query failed for {table_name}") from exc


def _select_one(supabase, table_name: str, column: str, value: Any) -> dict[str, Any] | None:
    rows = _execute_rows(
        supabase.table(table_name).select("*").eq(column, value).limit(1),
        table_name,
    )
    return rows[0] if rows else None


def _allowed_redirect_hosts() -> set[str]:
    configured = os.environ.get("FENCESPACE_MARKETPLACE_ALLOWED_REDIRECT_HOSTS", "")
    hosts = {host.strip().lower() for host in configured.split(",") if host.strip()}
    return hosts or DEFAULT_MARKETPLACE_REDIRECT_HOSTS


def _is_local_redirect_host(hostname: str) -> bool:
    return hostname in {"localhost", "127.0.0.1", "::1"}


def _validate_marketplace_redirect_url(value: str, *, field_name: str) -> str:
    parsed = urlparse(value or "")
    hostname = (parsed.hostname or "").lower()
    if not parsed.scheme or not parsed.netloc or not hostname:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    if hostname not in _allowed_redirect_hosts():
        raise HTTPException(status_code=400, detail=f"Untrusted {field_name}")
    if parsed.scheme != "https" and not (_is_local_redirect_host(hostname) and parsed.scheme == "http"):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    return value


def _load_marketplace_key_for_billing(supabase, raw_api_key: str | None) -> dict[str, Any]:
    if not raw_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    try:
        key_hash = hash_api_key(raw_api_key)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Missing API key") from exc
    key_row = _select_one(supabase, "fs_marketplace_api_keys", "key_hash", key_hash)
    if not key_row or key_row.get("active") is False or key_row.get("revoked_at"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    expires_at = key_row.get("expires_at")
    if expires_at and parse_timestamp(expires_at) <= datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Expired API key")
    return key_row


def _require_owned_marketplace_key(supabase, raw_api_key: str | None, api_key_id: str) -> dict[str, Any]:
    key_row = _load_marketplace_key_for_billing(supabase, raw_api_key)
    if str(key_row.get("id")) != str(api_key_id):
        raise HTTPException(status_code=403, detail="API key does not own this billing object")
    return key_row


def _subscriptions_for_marketplace_key(supabase, key_row: dict[str, Any]) -> list[dict[str, Any]]:
    subscriptions: list[dict[str, Any]] = []
    loaded = _load_subscription(supabase, key_row)
    if loaded:
        subscriptions.append(loaded)
    key_id = key_row.get("id")
    if key_id:
        rows = _execute_rows(
            supabase.table("fs_marketplace_subscriptions").select("*").eq("api_key_id", key_id).limit(10),
            "fs_marketplace_subscriptions",
        )
        seen = {str(row.get("id") or row.get("stripe_subscription_id")) for row in subscriptions}
        for row in rows:
            identity = str(row.get("id") or row.get("stripe_subscription_id"))
            if identity not in seen:
                subscriptions.append(row)
                seen.add(identity)
    return subscriptions


def _require_owned_stripe_customer(supabase, raw_api_key: str | None, stripe_customer_id: str) -> dict[str, Any]:
    key_row = _load_marketplace_key_for_billing(supabase, raw_api_key)
    if key_row.get("stripe_customer_id") == stripe_customer_id:
        return key_row
    for subscription in _subscriptions_for_marketplace_key(supabase, key_row):
        if subscription.get("stripe_customer_id") == stripe_customer_id:
            return key_row
    raise HTTPException(status_code=403, detail="API key does not own this billing object")


def _upsert(supabase, table_name: str, row: dict[str, Any], on_conflict: str) -> list[dict[str, Any]]:
    return _execute_rows(supabase.table(table_name).upsert(row, on_conflict=on_conflict), table_name)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, tuple | set):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _period_for(now: datetime) -> tuple[date, date]:
    start = date(now.year, now.month, 1)
    if now.month == 12:
        end = date(now.year + 1, 1, 1)
    else:
        end = date(now.year, now.month + 1, 1)
    return start, end


def _parse_stripe_signature_header(signature_header: str) -> tuple[int, list[str]]:
    parts: dict[str, list[str]] = {}
    for item in signature_header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts.setdefault(key, []).append(value)
    timestamps = parts.get("t") or []
    signatures = parts.get("v1") or []
    if not timestamps or not signatures:
        raise StripeSignatureError("missing timestamp or v1 signature")
    try:
        timestamp = int(timestamps[0])
    except ValueError as exc:
        raise StripeSignatureError("invalid timestamp") from exc
    return timestamp, signatures


def verify_stripe_signature(
    payload: bytes,
    signature_header: str | None,
    endpoint_secret: str,
    *,
    tolerance_seconds: int = WEBHOOK_TOLERANCE_SECONDS,
    now: float | None = None,
) -> None:
    if not endpoint_secret:
        raise StripeConfigurationError("STRIPE_WEBHOOK_SECRET is not configured")
    if not signature_header:
        raise StripeSignatureError("missing Stripe-Signature header")

    timestamp, signatures = _parse_stripe_signature_header(signature_header)
    now = time.time() if now is None else now
    if tolerance_seconds and abs(now - timestamp) > tolerance_seconds:
        raise StripeSignatureError("timestamp outside tolerance")

    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(endpoint_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise StripeSignatureError("signature mismatch")


def _live_stripe_allowed(allow_live: bool | None = None) -> bool:
    if allow_live is not None:
        return allow_live
    return os.environ.get("FENCESPACE_ALLOW_LIVE_STRIPE", "").strip().lower() in {"1", "true", "yes"}


def assert_test_mode_stripe_key(stripe_secret_key: str, *, allow_live: bool | None = None) -> None:
    if not stripe_secret_key:
        raise StripeConfigurationError("STRIPE_SECRET_KEY is not configured")
    if stripe_secret_key.startswith(("sk_live_", "rk_live_")) and not _live_stripe_allowed(allow_live):
        raise StripeConfigurationError("Live Stripe keys are disabled without explicit approval")
    if not stripe_secret_key.startswith(("sk_test_", "rk_test_")) and not _live_stripe_allowed(allow_live):
        raise StripeConfigurationError("Stripe key must be test-mode unless live mode is explicitly enabled")


def _stripe_headers(stripe_secret_key: str) -> dict[str, str]:
    return {"Stripe-Version": STRIPE_API_VERSION}


def _stripe_post(
    endpoint: str,
    data: dict[str, Any],
    *,
    stripe_secret_key: str,
    http_post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    response = http_post(
        f"{STRIPE_API_BASE}/{endpoint.lstrip('/')}",
        auth=(stripe_secret_key, ""),
        data=data,
        headers=_stripe_headers(stripe_secret_key),
        timeout=20,
    )
    status_code = getattr(response, "status_code", 200)
    if status_code >= 400:
        raise HTTPException(status_code=502, detail="Stripe API request failed")
    try:
        return response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Stripe API returned invalid JSON") from exc


def create_checkout_session(
    *,
    plan_id: str,
    customer_email: str,
    api_key_id: str,
    success_url: str,
    cancel_url: str,
    stripe_secret_key: str | None = None,
    price_id: str | None = None,
    allow_live: bool | None = None,
    http_post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    key: str = stripe_secret_key or os.environ.get("STRIPE_SECRET_KEY", "")
    assert_test_mode_stripe_key(key, allow_live=allow_live)
    price_id = price_id or os.environ.get(f"STRIPE_PRICE_ID_{plan_id.upper()}", "")
    if not price_id:
        raise StripeConfigurationError(f"Missing Stripe price ID for plan {plan_id}")

    return _stripe_post(
        "checkout/sessions",
        {
            "mode": "subscription",
            "customer_email": customer_email,
            "client_reference_id": api_key_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "metadata[plan_id]": plan_id,
            "metadata[api_key_id]": api_key_id,
            "subscription_data[metadata][plan_id]": plan_id,
            "subscription_data[metadata][api_key_id]": api_key_id,
        },
        stripe_secret_key=key,
        http_post=http_post,
    )


def create_customer_portal_session(
    *,
    stripe_customer_id: str,
    return_url: str,
    stripe_secret_key: str | None = None,
    allow_live: bool | None = None,
    http_post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    key: str = stripe_secret_key or os.environ.get("STRIPE_SECRET_KEY", "")
    assert_test_mode_stripe_key(key, allow_live=allow_live)
    return _stripe_post(
        "billing_portal/sessions",
        {"customer": stripe_customer_id, "return_url": return_url},
        stripe_secret_key=key,
        http_post=http_post,
    )


def _timestamp_to_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return parse_timestamp(value).isoformat()


def _record_webhook_event(
    supabase,
    event: dict[str, Any],
    *,
    processed: bool,
    error: str | None = None,
) -> None:
    event_id = event.get("id")
    row = {
        "id": event_id,
        "type": event.get("type"),
        "livemode": bool(event.get("livemode")),
        "processed": processed,
        "processed_at": datetime.now(UTC).isoformat() if processed else None,
        "payload": event,
        "error": error,
    }
    _upsert(supabase, "fs_stripe_webhook_events", row, "id")


def _upsert_customer_from_stripe(supabase, stripe_customer_id: str | None, email: str | None, metadata: dict[str, Any]) -> None:
    if not stripe_customer_id:
        return
    _upsert(
        supabase,
        "fs_marketplace_customers",
        {
            "stripe_customer_id": stripe_customer_id,
            "email": email,
            "metadata": metadata or {},
        },
        "stripe_customer_id",
    )


def _upsert_subscription_from_stripe(supabase, event_type: str, obj: dict[str, Any]) -> None:
    stripe_subscription_id = obj.get("id")
    if not stripe_subscription_id:
        return
    metadata = obj.get("metadata") or {}
    status = "canceled" if event_type == "customer.subscription.deleted" else obj.get("status")
    row = {
        "stripe_subscription_id": stripe_subscription_id,
        "stripe_customer_id": obj.get("customer"),
        "api_key_id": metadata.get("api_key_id") or None,
        "plan_id": metadata.get("plan_id") or None,
        "status": status,
        "current_period_start": _timestamp_to_iso(obj.get("current_period_start")),
        "current_period_end": _timestamp_to_iso(obj.get("current_period_end")),
        "cancel_at_period_end": bool(obj.get("cancel_at_period_end")),
        "metadata": metadata,
    }
    _upsert(supabase, "fs_marketplace_subscriptions", row, "stripe_subscription_id")


def _handle_checkout_completed(supabase, obj: dict[str, Any]) -> None:
    metadata = obj.get("metadata") or {}
    _upsert_customer_from_stripe(supabase, obj.get("customer"), obj.get("customer_email"), metadata)
    subscription = obj.get("subscription")
    if isinstance(subscription, str):
        _upsert(
            supabase,
            "fs_marketplace_subscriptions",
            {
                "stripe_subscription_id": subscription,
                "stripe_customer_id": obj.get("customer"),
                "api_key_id": metadata.get("api_key_id") or None,
                "plan_id": metadata.get("plan_id") or None,
                "status": obj.get("subscription_status") or "incomplete",
                "metadata": metadata,
            },
            "stripe_subscription_id",
        )


def process_stripe_event(supabase, event: dict[str, Any]) -> None:
    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    if event_type == "checkout.session.completed":
        _handle_checkout_completed(supabase, obj)
    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "customer.subscription.paused",
        "customer.subscription.resumed",
    }:
        _upsert_subscription_from_stripe(supabase, event_type, obj)
    elif event_type in {"invoice.paid", "invoice.payment_failed"}:
        subscription_id = obj.get("subscription")
        if subscription_id:
            existing = _select_one(supabase, "fs_marketplace_subscriptions", "stripe_subscription_id", subscription_id)
            if existing:
                existing["last_invoice_status"] = "paid" if event_type == "invoice.paid" else "payment_failed"
                _upsert(supabase, "fs_marketplace_subscriptions", existing, "stripe_subscription_id")


def handle_stripe_webhook(
    supabase,
    payload: bytes,
    signature_header: str | None,
    endpoint_secret: str,
    *,
    allow_live: bool | None = None,
    now: float | None = None,
) -> dict[str, str]:
    try:
        verify_stripe_signature(payload, signature_header, endpoint_secret, now=now)
        event = json.loads(payload.decode("utf-8"))
    except StripeConfigurationError:
        raise
    except (StripeSignatureError, json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Stripe webhook rejected: signature or payload validation failed")
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook")

    event_id = event.get("id")
    if not event_id:
        logger.warning("Stripe webhook rejected: missing event id")
        raise HTTPException(status_code=400, detail="Stripe event id is required")
    if event.get("livemode") and not _live_stripe_allowed(allow_live):
        logger.warning("Stripe webhook rejected: live mode is disabled")
        raise HTTPException(status_code=400, detail="Live Stripe events are disabled")

    existing = _select_one(supabase, "fs_stripe_webhook_events", "id", event_id)
    if existing and existing.get("processed") is True:
        return {"status": "duplicate", "event_id": event_id}

    _record_webhook_event(supabase, event, processed=False)
    try:
        process_stripe_event(supabase, event)
    except Exception as exc:
        _record_webhook_event(supabase, event, processed=False, error=type(exc).__name__)
        logger.exception("Stripe webhook processing failed for event %s", event_id)
        raise HTTPException(status_code=500, detail="Stripe webhook processing failed") from exc
    _record_webhook_event(supabase, event, processed=True)
    return {"status": "processed", "event_id": event_id}


def _load_plan(supabase, plan_id: str | None) -> dict[str, Any] | None:
    if not plan_id:
        return None
    return _select_one(supabase, "fs_marketplace_plans", "plan_id", plan_id)


def _load_subscription(supabase, key_row: dict[str, Any]) -> dict[str, Any] | None:
    subscription_id = key_row.get("subscription_id")
    if subscription_id:
        row = _select_one(supabase, "fs_marketplace_subscriptions", "id", subscription_id)
        if row:
            return row
    stripe_subscription_id = key_row.get("stripe_subscription_id")
    if stripe_subscription_id:
        return _select_one(supabase, "fs_marketplace_subscriptions", "stripe_subscription_id", stripe_subscription_id)
    return None


def _effective_scopes(key_row: dict[str, Any], plan_row: dict[str, Any] | None) -> set[str]:
    key_scopes = set(_as_list(key_row.get("scopes")))
    plan_scopes = set(_as_list((plan_row or {}).get("scopes")))
    if key_scopes and plan_scopes:
        return key_scopes.intersection(plan_scopes)
    return key_scopes or plan_scopes


def _subscription_is_current(subscription: dict[str, Any], now: datetime) -> bool:
    if subscription.get("status") not in ALLOWED_SUBSCRIPTION_STATUSES:
        return False
    current_period_end = subscription.get("current_period_end")
    if current_period_end:
        return parse_timestamp(current_period_end) > now
    return True


def _increment_usage_counter(
    supabase,
    *,
    api_key_id: str,
    scope: str,
    monthly_request_limit: int | None,
    now: datetime,
) -> int:
    period_start, period_end = _period_for(now)
    if hasattr(supabase, "rpc") and callable(getattr(supabase, "rpc")):
        try:
            response = supabase.rpc(
                "fs_marketplace_increment_usage",
                {
                    "p_api_key_id": api_key_id,
                    "p_scope": scope,
                    "p_period_start": period_start.isoformat(),
                    "p_period_end": period_end.isoformat(),
                    "p_limit": monthly_request_limit,
                },
            ).execute()
            data = response.data
            if isinstance(data, int):
                return data
            if isinstance(data, list) and data:
                value = data[0]
                if isinstance(value, dict):
                    return int(value.get("fs_marketplace_increment_usage") or value.get("request_count") or 0)
                return int(value)
        except Exception as exc:
            if "usage limit exceeded" in str(exc).lower():
                raise HTTPException(status_code=429, detail="Usage limit exceeded") from exc
            raise HTTPException(status_code=502, detail="Usage counter update failed") from exc

    existing = _execute_rows(
        supabase.table("fs_marketplace_usage_counters")
        .select("*")
        .eq("api_key_id", api_key_id)
        .eq("scope", scope)
        .eq("period_start", period_start.isoformat())
        .limit(1),
        "fs_marketplace_usage_counters",
    )
    current_count = int(existing[0].get("request_count", 0)) if existing else 0
    if monthly_request_limit is not None and current_count >= monthly_request_limit:
        raise HTTPException(status_code=429, detail="Usage limit exceeded")
    next_count = current_count + 1
    _upsert(
        supabase,
        "fs_marketplace_usage_counters",
        {
            "api_key_id": api_key_id,
            "scope": scope,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "request_count": next_count,
            "last_request_at": now.isoformat(),
        },
        "api_key_id,scope,period_start",
    )
    return next_count


def authorize_api_access(
    supabase,
    raw_api_key: str,
    required_scope: str,
    *,
    now: datetime | None = None,
    increment_usage: bool = True,
) -> dict[str, Any]:
    now = parse_timestamp(now)
    if not raw_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    try:
        key_hash = hash_api_key(raw_api_key)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Missing API key") from exc

    key_row = _select_one(supabase, "fs_marketplace_api_keys", "key_hash", key_hash)
    if not key_row or key_row.get("active") is False or key_row.get("revoked_at"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    expires_at = key_row.get("expires_at")
    if expires_at and parse_timestamp(expires_at) <= now:
        raise HTTPException(status_code=401, detail="Expired API key")

    subscription = _load_subscription(supabase, key_row)
    plan_id = (subscription or {}).get("plan_id") or key_row.get("plan_id")
    plan = _load_plan(supabase, plan_id)
    if not plan or plan.get("active") is False:
        raise HTTPException(status_code=403, detail="Plan is not active")
    if plan.get("requires_subscription", True) is not False:
        if not subscription or not _subscription_is_current(subscription, now):
            raise HTTPException(status_code=402, detail="Subscription is not active")

    if required_scope not in _effective_scopes(key_row, plan):
        raise HTTPException(status_code=403, detail="API key is not entitled to this scope")

    usage_count = None
    monthly_request_limit = plan.get("monthly_request_limit")
    if monthly_request_limit is not None:
        monthly_request_limit = int(monthly_request_limit)
    if increment_usage:
        usage_count = _increment_usage_counter(
            supabase,
            api_key_id=key_row["id"],
            scope=required_scope,
            monthly_request_limit=monthly_request_limit,
            now=now,
        )

    return {
        "api_key_id": key_row["id"],
        "plan_id": plan["plan_id"],
        "scope": required_scope,
        "usage_count": usage_count,
        "monthly_request_limit": monthly_request_limit,
    }


def _apply_eq(query, column: str, value: Any):
    if value in (None, ""):
        return query
    return query.eq(column, value)


def _apply_ilike_if_available(query, column: str, value: str | None):
    if not value:
        return query
    if hasattr(query, "ilike"):
        return query.ilike(column, f"%{value}%")
    return query.eq(column, value)


def _public_rows(
    supabase,
    table_name: str,
    configure: Callable[[Any], Any] | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    query = supabase.table(table_name).select("*")
    if configure:
        query = configure(query)
    if hasattr(query, "range"):
        query = query.range(offset, offset + limit - 1)
    rows = _execute_rows(query, table_name)
    return {"data": rows[:limit], "pagination": {"limit": limit, "offset": offset, "count": len(rows[:limit])}}


@app.exception_handler(StripeConfigurationError)
async def stripe_configuration_exception_handler(_request: Request, exc: StripeConfigurationError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/plans")
def list_marketplace_plans():
    rows = _execute_rows(
        get_supabase_client().table("fs_marketplace_plans").select("plan_id,name,description,monthly_request_limit,scopes,active"),
        "fs_marketplace_plans",
    )
    return {"data": [row for row in rows if row.get("active") is not False]}


@app.post("/checkout/session")
def checkout_session(
    payload: dict[str, Any] = Body(...),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    supabase = get_supabase_client()
    _require_owned_marketplace_key(supabase, x_api_key, payload["api_key_id"])
    success_url = _validate_marketplace_redirect_url(payload["success_url"], field_name="success_url")
    cancel_url = _validate_marketplace_redirect_url(payload["cancel_url"], field_name="cancel_url")
    session = create_checkout_session(
        plan_id=payload["plan_id"],
        customer_email=payload["customer_email"],
        api_key_id=payload["api_key_id"],
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return {"url": session.get("url"), "id": session.get("id")}


@app.post("/billing/portal")
def billing_portal(
    payload: dict[str, Any] = Body(...),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    supabase = get_supabase_client()
    _require_owned_stripe_customer(supabase, x_api_key, payload["stripe_customer_id"])
    return_url = _validate_marketplace_redirect_url(payload["return_url"], field_name="return_url")
    session = create_customer_portal_session(
        stripe_customer_id=payload["stripe_customer_id"],
        return_url=return_url,
    )
    return {"url": session.get("url"), "id": session.get("id")}


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None, alias="Stripe-Signature")):
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    payload = await request.body()
    return handle_stripe_webhook(get_supabase_client(), payload, stripe_signature, endpoint_secret)


@app.get("/data/fencers/search")
def marketplace_search_fencers(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    name: str | None = None,
    country: str | None = None,
    weapon: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    supabase = get_supabase_client()
    authorize_api_access(supabase, x_api_key or "", "data:fencers:read")

    def configure(query):
        query = _apply_ilike_if_available(query, "name", name)
        query = _apply_eq(query, "country", country)
        return _apply_eq(query, "weapon", weapon)

    return _public_rows(supabase, "v_fencer_public", configure, limit=limit, offset=offset)


@app.get("/data/tournaments")
def marketplace_tournaments(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    season: int | None = None,
    country: str | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    supabase = get_supabase_client()
    authorize_api_access(supabase, x_api_key or "", "data:tournaments:read")

    def configure(query):
        query = _apply_eq(query, "season", season)
        return _apply_eq(query, "country", country)

    return _public_rows(supabase, "v_tournament_public", configure, limit=limit, offset=offset)

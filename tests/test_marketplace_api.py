from typing import Any, cast
import hashlib
import hmac
import importlib
import json
import logging
import os
import sys
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_marketplace.sql"


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.limit_count = None
        self.operation = "select"
        self.payload = None
        self.on_conflict = None

    def select(self, _columns):
        self.operation = "select"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def upsert(self, row, on_conflict=None):
        self.operation = "upsert"
        self.payload = dict(row)
        self.on_conflict = on_conflict
        return self

    def insert(self, row):
        self.operation = "insert"
        self.payload = dict(row)
        return self

    def execute(self):
        if self.operation == "select":
            rows = list(self.client.tables.get(self.table_name, []))
            for column, value in self.filters:
                rows = [row for row in rows if str(row.get(column)) == str(value)]
            if self.limit_count is not None:
                rows = rows[: self.limit_count]
            return FakeResponse(rows)
        if self.operation == "insert":
            self.client.inserts.append({"table": self.table_name, "row": dict(cast(dict[str, Any], self.payload))})
            self.client.tables.setdefault(self.table_name, []).append(dict(cast(dict[str, Any], self.payload)))
            return FakeResponse([dict(cast(dict[str, Any], self.payload))])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.table_name,
                    "row": dict(cast(dict[str, Any], self.payload)),
                    "on_conflict": self.on_conflict,
                }
            )
            rows = self.client.tables.setdefault(self.table_name, [])
            conflict_columns = [part.strip() for part in (self.on_conflict or "").split(",") if part.strip()]
            match = None
            payload = cast(dict[str, Any], self.payload)
            if conflict_columns:
                for row in rows:
                    if all(str(row.get(column)) == str(payload.get(column)) for column in conflict_columns):
                        match = row
                        break
            if match is None:
                rows.append(dict(cast(dict[str, Any], self.payload)))
            else:
                match.update(dict(cast(dict[str, Any], self.payload)))
            return FakeResponse([dict(cast(dict[str, Any], self.payload))])
        raise AssertionError(f"unexpected operation {self.operation}")


class FakeSupabase:
    def __init__(self):
        self.inserts = []
        self.upserts = []
        self.tables = {
            "fs_marketplace_plans": [
                {
                    "plan_id": "starter",
                    "name": "Starter",
                    "monthly_request_limit": 2,
                    "scopes": ["data:fencers:read"],
                    "active": True,
                }
            ],
            "fs_marketplace_customers": [],
            "fs_marketplace_api_keys": [],
            "fs_marketplace_subscriptions": [],
            "fs_marketplace_usage_counters": [],
            "fs_stripe_webhook_events": [],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


def load_module():
    sys.modules.pop("marketplace_api", None)
    return importlib.import_module("marketplace_api")


def signed_header(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    timestamp = timestamp or int(time.time())
    signature = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def provision_active_key(module, fake, raw_key="mk_test_secret"):
    key_hash = module.hash_api_key(raw_key)
    fake.tables["fs_marketplace_api_keys"].append(
        {
            "id": "key-1",
            "key_hash": key_hash,
            "label": "CI key",
            "plan_id": "starter",
            "subscription_id": "sub-row-1",
            "scopes": ["data:fencers:read"],
            "revoked_at": None,
            "expires_at": None,
        }
    )
    fake.tables["fs_marketplace_subscriptions"].append(
        {
            "id": "sub-row-1",
            "plan_id": "starter",
            "status": "active",
            "stripe_subscription_id": "sub_test_123",
        }
    )
    return raw_key


def test_stripe_webhook_signature_and_idempotency_process_subscription_once():
    module = load_module()
    fake = FakeSupabase()
    secret = "whsec_test_secret"
    event = {
        "id": "evt_123",
        "type": "customer.subscription.updated",
        "livemode": False,
        "data": {
            "object": {
                "id": "sub_test_123",
                "customer": "cus_test_123",
                "status": "active",
                "current_period_start": 1780272000,
                "current_period_end": 1782864000,
                "cancel_at_period_end": False,
                "metadata": {"plan_id": "starter", "api_key_id": "key-1"},
            }
        },
    }
    payload = json.dumps(event, separators=(",", ":")).encode()
    header = signed_header(payload, secret)

    first = module.handle_stripe_webhook(fake, payload, header, secret)
    second = module.handle_stripe_webhook(fake, payload, header, secret)

    subscription_upserts = [item for item in fake.upserts if item["table"] == "fs_marketplace_subscriptions"]
    assert first == {"status": "processed", "event_id": "evt_123"}
    assert second == {"status": "duplicate", "event_id": "evt_123"}
    assert len(subscription_upserts) == 1
    assert subscription_upserts[0]["row"]["status"] == "active"
    assert fake.tables["fs_stripe_webhook_events"][0]["processed"] is True


def test_stripe_webhook_rejects_bad_signature_without_logging_secrets(caplog):
    module = load_module()
    fake = FakeSupabase()
    secret = "whsec_hidden_value"
    payload = b'{"id":"evt_bad","metadata":{"api_key":"sk_test_hidden_value"}}'
    caplog.set_level(logging.WARNING, logger="marketplace_api")

    with pytest.raises(HTTPException) as exc:
        module.handle_stripe_webhook(fake, payload, "t=1780272000,v1=bad", secret)

    assert exc.value.status_code == 400
    assert "whsec_hidden_value" not in caplog.text
    assert "sk_test_hidden_value" not in caplog.text
    assert payload.decode() not in caplog.text


def test_authorize_api_access_checks_subscription_scope_and_increments_usage():
    module = load_module()
    fake = FakeSupabase()
    api_key = provision_active_key(module, fake)
    now = module.parse_timestamp("2026-06-02T12:00:00Z")

    entitlement = module.authorize_api_access(fake, api_key, "data:fencers:read", now=now)

    assert entitlement["api_key_id"] == "key-1"
    assert entitlement["plan_id"] == "starter"
    assert fake.tables["fs_marketplace_usage_counters"][0]["request_count"] == 1
    assert fake.tables["fs_marketplace_usage_counters"][0]["scope"] == "data:fencers:read"


def test_authorize_api_access_rejects_inactive_subscription():
    module = load_module()
    fake = FakeSupabase()
    api_key = provision_active_key(module, fake)
    fake.tables["fs_marketplace_subscriptions"][0]["status"] = "canceled"

    with pytest.raises(HTTPException) as exc:
        module.authorize_api_access(fake, api_key, "data:fencers:read")

    assert exc.value.status_code == 402


def test_authorize_api_access_rejects_missing_scope():
    module = load_module()
    fake = FakeSupabase()
    api_key = provision_active_key(module, fake)

    with pytest.raises(HTTPException) as exc:
        module.authorize_api_access(fake, api_key, "data:tournaments:read")

    assert exc.value.status_code == 403


def test_usage_counter_blocks_requests_over_plan_limit():
    module = load_module()
    fake = FakeSupabase()
    api_key = provision_active_key(module, fake)
    now = module.parse_timestamp("2026-06-02T12:00:00Z")

    module.authorize_api_access(fake, api_key, "data:fencers:read", now=now)
    module.authorize_api_access(fake, api_key, "data:fencers:read", now=now)
    with pytest.raises(HTTPException) as exc:
        module.authorize_api_access(fake, api_key, "data:fencers:read", now=now)

    assert exc.value.status_code == 429
    assert fake.tables["fs_marketplace_usage_counters"][0]["request_count"] == 2


def test_live_stripe_checkout_is_blocked_before_http_call():
    module = load_module()
    calls = []

    with pytest.raises(module.StripeConfigurationError):
        module.create_checkout_session(
            plan_id="starter",
            customer_email="buyer@example.test",
            api_key_id="key-1",
            success_url="https://app.example.test/success",
            cancel_url="https://app.example.test/cancel",
            stripe_secret_key="sk_live_blocked",
            price_id="price_live_123",
            http_post=lambda *args, **kwargs: calls.append((args, kwargs)),
        )

    assert calls == []


def test_checkout_session_requires_api_key_before_stripe_call(monkeypatch):
    module = load_module()
    fake = FakeSupabase()
    module.app.state.supabase_client = fake
    calls = []
    monkeypatch.setattr(module, "create_checkout_session", lambda **kwargs: calls.append(kwargs))

    response = TestClient(module.app).post(
        "/checkout/session",
        json={
            "plan_id": "starter",
            "customer_email": "buyer@example.test",
            "api_key_id": "key-1",
            "success_url": "https://app.fencespace.com/success",
            "cancel_url": "https://app.fencespace.com/cancel",
        },
    )

    assert response.status_code == 401
    assert calls == []


def test_checkout_session_rejects_api_key_id_not_owned_by_header_key(monkeypatch):
    module = load_module()
    fake = FakeSupabase()
    api_key = provision_active_key(module, fake)
    module.app.state.supabase_client = fake
    calls = []
    monkeypatch.setattr(module, "create_checkout_session", lambda **kwargs: calls.append(kwargs))

    response = TestClient(module.app).post(
        "/checkout/session",
        headers={"X-API-Key": api_key},
        json={
            "plan_id": "starter",
            "customer_email": "buyer@example.test",
            "api_key_id": "key-2",
            "success_url": "https://app.fencespace.com/success",
            "cancel_url": "https://app.fencespace.com/cancel",
        },
    )

    assert response.status_code == 403
    assert calls == []


def test_checkout_session_rejects_untrusted_redirect_before_stripe_call(monkeypatch):
    module = load_module()
    fake = FakeSupabase()
    api_key = provision_active_key(module, fake)
    module.app.state.supabase_client = fake
    calls = []
    monkeypatch.setattr(module, "create_checkout_session", lambda **kwargs: calls.append(kwargs))

    response = TestClient(module.app).post(
        "/checkout/session",
        headers={"X-API-Key": api_key},
        json={
            "plan_id": "starter",
            "customer_email": "buyer@example.test",
            "api_key_id": "key-1",
            "success_url": "https://evil.example/success",
            "cancel_url": "https://app.fencespace.com/cancel",
        },
    )

    assert response.status_code == 400
    assert calls == []


def test_checkout_session_allows_owned_api_key_and_safe_redirect(monkeypatch):
    module = load_module()
    fake = FakeSupabase()
    api_key = provision_active_key(module, fake)
    module.app.state.supabase_client = fake
    calls = []

    def fake_checkout(**kwargs):
        calls.append(kwargs)
        return {"url": "https://checkout.stripe.test/session", "id": "cs_test_123"}

    monkeypatch.setattr(module, "create_checkout_session", fake_checkout)

    response = TestClient(module.app).post(
        "/checkout/session",
        headers={"X-API-Key": api_key},
        json={
            "plan_id": "starter",
            "customer_email": "buyer@example.test",
            "api_key_id": "key-1",
            "success_url": "https://app.fencespace.com/success",
            "cancel_url": "https://app.fencespace.com/cancel",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"url": "https://checkout.stripe.test/session", "id": "cs_test_123"}
    assert calls[0]["api_key_id"] == "key-1"


def test_billing_portal_requires_owned_stripe_customer_id(monkeypatch):
    module = load_module()
    fake = FakeSupabase()
    api_key = provision_active_key(module, fake)
    fake.tables["fs_marketplace_subscriptions"][0]["stripe_customer_id"] = "cus_owned"
    module.app.state.supabase_client = fake
    calls = []
    monkeypatch.setattr(module, "create_customer_portal_session", lambda **kwargs: calls.append(kwargs))

    response = TestClient(module.app).post(
        "/billing/portal",
        headers={"X-API-Key": api_key},
        json={"stripe_customer_id": "cus_other", "return_url": "https://app.fencespace.com/billing"},
    )

    assert response.status_code == 403
    assert calls == []


def test_marketplace_migration_defines_private_billing_and_usage_tables():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for table in [
        "fs_marketplace_plans",
        "fs_marketplace_customers",
        "fs_marketplace_api_keys",
        "fs_marketplace_subscriptions",
        "fs_marketplace_usage_counters",
        "fs_stripe_webhook_events",
    ]:
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on public.{table} from anon, authenticated" in sql
    assert "key_hash" in sql
    assert "stripe_event_id" in sql or "fs_stripe_webhook_events" in sql
    assert "fs_marketplace_increment_usage" in sql

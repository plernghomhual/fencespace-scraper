from typing import Any, cast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260602_push_notifications.sql"
)


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.payload = None
        self.filters = []
        self.on_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.name, columns))
        return self

    def upsert(self, row, on_conflict=None):
        self.operation = "upsert"
        self.payload = row
        self.on_conflict = on_conflict
        self.client.upserts.append(
            {"table": self.name, "row": row, "on_conflict": on_conflict}
        )
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        self.client.filters.append((self.name, "eq", column, value))
        return self

    def order(self, column, desc=False):
        self.client.orders.append((self.name, column, desc))
        return self

    def limit(self, count):
        self.client.limits.append((self.name, count))
        return self

    def execute(self):
        if self.operation == "select":
            if self.name == "fs_results":
                return FakeResult(self.client.results)
            if self.name == "fs_push_subscriptions":
                return FakeResult(self.client.subscriptions)
            if self.name == "fs_push_delivery_log":
                return FakeResult(self.client.delivery_logs)
        if self.operation == "upsert":
            return FakeResult([])
        raise AssertionError(f"unexpected {self.operation} on {self.name}")


class FakeSupabase:
    def __init__(self, results=None, subscriptions=None, delivery_logs=None):
        self.results = results or []
        self.subscriptions = subscriptions or []
        self.delivery_logs = delivery_logs or []
        self.selects = []
        self.filters = []
        self.orders = []
        self.limits = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


class FakeClock:
    def __init__(self):
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)


class FailingProvider:
    provider_name = "dry-run"
    dry_run = True

    def __init__(self, failures_before_success):
        self.failures_before_success = failures_before_success
        self.calls = []

    def send(self, subscription, payload):
        import push_notifications

        self.calls.append((subscription, payload))
        if len(self.calls) <= self.failures_before_success:
            return push_notifications.DeliveryResult(
                success=False,
                status="failed",
                error="temporary provider failure",
                dry_run=True,
            )
        return push_notifications.DeliveryResult(
            success=True,
            status="sent",
            provider_message_id=f"msg-{len(self.calls)}",
            dry_run=True,
        )


def live_result_row(**overrides):
    row = {
        "id": "result-1",
        "tournament_id": "tournament-1",
        "name": "Lee Kiefer",
        "country": "United States",
        "nationality": "United States",
        "rank": 1,
        "placement": 1,
        "fie_fencer_id": "100",
        "updated_at": "2026-01-28T12:00:00+00:00",
        "metadata": {"internal_score": 999},
        "fs_tournaments": {
            "id": "tournament-1",
            "name": "Live Grand Prix",
            "season": 2026,
        },
    }
    row.update(overrides)
    return row


def subscription_row(**overrides):
    row = {
        "id": "sub-1",
        "user_id": "user-1",
        "device_id": "device-1",
        "notification_type": "live_result",
        "provider": "dry-run",
        "provider_token": "private-device-token",
        "opt_in": True,
        "disabled": False,
        "tournament_id": None,
        "device": {
            "id": "device-1",
            "user_id": "user-1",
            "platform": "ios",
            "opt_in": True,
            "disabled": False,
        },
    }
    row.update(overrides)
    return row


def migration_sql():
    return MIGRATION.read_text(encoding="utf-8")


def compact_sql():
    return re.sub(r"\s+", " ", migration_sql().lower())


def test_migration_creates_opt_in_devices_subscriptions_and_delivery_log():
    sql = compact_sql()

    assert "create table if not exists public.fs_push_devices" in sql
    assert "create table if not exists public.fs_push_subscriptions" in sql
    assert "create table if not exists public.fs_push_delivery_log" in sql
    assert "opt_in boolean not null default false" in sql
    assert "disabled boolean not null default false" in sql
    assert "provider_token text not null" in sql
    assert "event_fingerprint text not null" in sql
    assert "unique (subscription_id, event_fingerprint)" in sql
    assert "on delete cascade" in sql


def test_migration_enforces_ownership_and_service_safe_delivery_logs():
    sql = compact_sql()

    for table in (
        "fs_push_devices",
        "fs_push_subscriptions",
        "fs_push_delivery_log",
    ):
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on public.{table} from anon" in sql

    assert "auth.uid() = user_id" in sql
    assert "with check (auth.uid() = user_id" in sql
    assert "no anon/authenticated insert policy" in sql


def test_dry_run_provider_is_default_and_records_no_external_secret():
    import push_notifications

    provider = push_notifications.provider_from_env({})
    result = provider.send(
        subscription_row(),
        {
            "title": "Live result",
            "body": "Lee Kiefer #1",
            "data": {"event_type": "live_result", "fingerprint": "abc"},
        },
    )

    assert isinstance(provider, push_notifications.DryRunPushProvider)
    assert result.success is True
    assert result.dry_run is True
    assert result.status == "dry_run"
    assert provider.deliveries[0]["subscription_id"] == "sub-1"
    assert "private-device-token" not in json.dumps(provider.deliveries)


def test_duplicate_suppression_is_per_subscription(monkeypatch):
    import push_notifications

    state: dict[Any, Any] = {}
    client = FakeSupabase(
        results=[live_result_row()],
        subscriptions=[subscription_row()],
    )
    provider = push_notifications.DryRunPushProvider()

    monkeypatch.setattr(
        push_notifications,
        "get_state",
        lambda source, key: state.get((source, key)),
    )
    monkeypatch.setattr(
        push_notifications,
        "set_state",
        lambda source, key, value: state.__setitem__((source, key), value),
    )

    first = push_notifications.run_push_notifications(
        client=client,
        provider=cast(Any, provider),
        now=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
        log_run=False,
    )
    second = push_notifications.run_push_notifications(
        client=client,
        provider=cast(Any, provider),
        now=datetime(2026, 1, 28, 12, 5, tzinfo=timezone.utc),
        log_run=False,
    )

    delivery_logs = [
        call for call in client.upserts if call["table"] == "fs_push_delivery_log"
    ]
    assert first["sent"] == 1
    assert first["duplicates"] == 0
    assert second["sent"] == 0
    assert second["duplicates"] == 1
    assert len(provider.deliveries) == 1
    assert len(delivery_logs) == 1
    assert delivery_logs[0]["on_conflict"] == "subscription_id,event_fingerprint"
    assert len(state[("push_notifications", "sent_live_result_sub-1")]) == 1


def test_payload_privacy_excludes_private_result_and_subscription_fields():
    import push_notifications

    row = live_result_row(
        user_id="private-user",
        email="athlete@example.com",
        date_of_birth="1994-06-15",
        provider_token="raw-token",
        raw_result={"pool": "private"},
    )
    event = push_notifications.live_result_event(row)
    payload = push_notifications.build_push_payload(event)
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["title"] == "Live result"
    assert payload["body"] == "Live Grand Prix: Lee Kiefer #1"
    assert payload["data"]["event_type"] == "live_result"
    assert payload["data"]["tournament_id"] == "tournament-1"
    assert payload["data"]["rank"] == "1"
    for private_value in (
        "private-user",
        "athlete@example.com",
        "1994-06-15",
        "raw-token",
        "private",
        "private-device-token",
        "metadata",
        "fie_fencer_id",
    ):
        assert private_value not in encoded


def test_subscription_ownership_and_opt_in_are_validated(monkeypatch):
    import push_notifications

    state: dict[Any, Any] = {}
    client = FakeSupabase(
        results=[live_result_row()],
        subscriptions=[
            subscription_row(id="valid-sub"),
            subscription_row(
                id="wrong-owner",
                user_id="user-2",
                device={"id": "device-1", "user_id": "user-1", "opt_in": True},
            ),
            subscription_row(id="disabled-sub", disabled=True),
            subscription_row(id="no-opt-in", opt_in=False),
            subscription_row(
                id="disabled-device",
                device={"id": "device-1", "user_id": "user-1", "disabled": True},
            ),
        ],
    )
    provider = push_notifications.DryRunPushProvider()

    monkeypatch.setattr(
        push_notifications,
        "get_state",
        lambda source, key: state.get((source, key)),
    )
    monkeypatch.setattr(
        push_notifications,
        "set_state",
        lambda source, key, value: state.__setitem__((source, key), value),
    )

    summary = push_notifications.run_push_notifications(
        client=client,
        provider=provider,
        now=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
        log_run=False,
    )

    assert summary["subscriptions"] == 1
    assert summary["skipped_subscriptions"] == 4
    assert summary["sent"] == 1
    assert [delivery["subscription_id"] for delivery in provider.deliveries] == [
        "valid-sub"
    ]


def test_provider_failures_retry_with_backoff_and_log_success(monkeypatch):
    import push_notifications

    state: dict[Any, Any] = {}
    clock = FakeClock()
    client = FakeSupabase(
        results=[live_result_row()],
        subscriptions=[subscription_row()],
    )
    provider = FailingProvider(failures_before_success=2)

    monkeypatch.setattr(
        push_notifications,
        "get_state",
        lambda source, key: state.get((source, key)),
    )
    monkeypatch.setattr(
        push_notifications,
        "set_state",
        lambda source, key, value: state.__setitem__((source, key), value),
    )

    summary = push_notifications.run_push_notifications(
        client=client,
        provider=cast(Any, provider),
        now=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
        log_run=False,
        retry_policy=push_notifications.RetryPolicy(max_attempts=3, base_delay=2.0),
        sleep=clock.sleep,
    )

    delivery_log = [
        call for call in client.upserts if call["table"] == "fs_push_delivery_log"
    ][0]["row"]
    assert summary["sent"] == 1
    assert summary["failed"] == 0
    assert len(provider.calls) == 3
    assert clock.sleeps == [2.0, 4.0]
    assert delivery_log["status"] == "sent"
    assert delivery_log["attempt_count"] == 3
    assert delivery_log["error"] is None


def test_provider_failure_errors_are_redacted_before_delivery_log(monkeypatch):
    import push_notifications

    class SecretFailingProvider:
        provider_name = "fcm"
        dry_run = False

        def send(self, subscription, payload):
            return push_notifications.DeliveryResult(
                success=False,
                status="failed",
                error=(
                    "Authorization: Bearer raw-access-token "
                    "provider_token=private-device-token FCM_SERVER_KEY=raw-server-key"
                ),
                dry_run=False,
            )

    state: dict[Any, Any] = {}
    client = FakeSupabase(
        results=[live_result_row()],
        subscriptions=[subscription_row(provider="fcm")],
    )
    monkeypatch.setattr(
        push_notifications,
        "get_state",
        lambda source, key: state.get((source, key)),
    )
    monkeypatch.setattr(
        push_notifications,
        "set_state",
        lambda source, key, value: state.__setitem__((source, key), value),
    )

    summary = push_notifications.run_push_notifications(
        client=client,
        provider=cast(Any, SecretFailingProvider()),
        now=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
        log_run=False,
        retry_policy=push_notifications.RetryPolicy(max_attempts=1),
    )

    delivery_log = [
        call for call in client.upserts if call["table"] == "fs_push_delivery_log"
    ][0]["row"]
    assert summary["failed"] == 1
    assert "[REDACTED]" in delivery_log["error"]
    assert "raw-access-token" not in delivery_log["error"]
    assert "private-device-token" not in delivery_log["error"]
    assert "raw-server-key" not in delivery_log["error"]

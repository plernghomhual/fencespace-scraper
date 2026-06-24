from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_ranking_alerts.sql"
NOW = "2026-06-02T12:00:00+00:00"


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = None
        self.selected = None
        self.filters = []
        self.in_filter = None
        self.start = 0
        self.end = None
        self.pending_rows = None
        self.pending_conflict = None
        self.pending_update = None

    def select(self, columns):
        self.operation = "select"
        self.selected = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def order(self, column):
        self.client.orders.append((self.table_name, column))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def limit(self, _limit):
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.in_filter = (column, set(values))
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.pending_rows = rows
        self.pending_conflict = on_conflict
        return self

    def update(self, payload):
        self.operation = "update"
        self.pending_update = payload
        return self

    def execute(self):
        if self.operation == "select":
            rows = list(self.client.tables.get(self.table_name, []))
            for kind, column, value in self.filters:
                if kind == "eq":
                    rows = [row for row in rows if row.get(column) == value]
            if self.in_filter:
                column, values = self.in_filter
                rows = [row for row in rows if row.get(column) in values]
            end = self.end + 1 if self.end is not None else None
            return FakeResult(rows[self.start:end])

        if self.operation == "upsert":
            rows = self.pending_rows if isinstance(self.pending_rows, list) else [self.pending_rows]
            self.client.upserts.append(
                {
                    "table": self.table_name,
                    "rows": [dict(row) for row in rows],
                    "on_conflict": self.pending_conflict,
                }
            )
            if self.table_name == "fs_ranking_alert_deliveries":
                by_key = {
                    row["idempotency_key"]: dict(row)
                    for row in self.client.tables.setdefault(self.table_name, [])
                }
                for row in rows:
                    by_key[row["idempotency_key"]] = dict(row)
                self.client.tables[self.table_name] = list(by_key.values())
            return FakeResult(rows)

        if self.operation == "update":
            rows = self.client.tables.get(self.table_name, [])
            updated = []
            for row in rows:
                if all(row.get(column) == value for _, column, value in self.filters):
                    row.update(self.pending_update)
                    updated.append(dict(row))
            self.client.updates.append(
                {
                    "table": self.table_name,
                    "payload": dict(cast(dict[str, Any], self.pending_update)),
                    "filters": list(self.filters),
                }
            )
            return FakeResult(updated)

        raise AssertionError(f"unexpected operation {self.operation} on {self.table_name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = {name: list(rows) for name, rows in tables.items()}
        self.selects = []
        self.orders = []
        self.upserts = []
        self.updates = []

    def table(self, table_name):
        return FakeTable(self, table_name)


class RecordingProvider:
    provider_name = "recording"

    def __init__(self, status="sent"):
        self.status = status
        self.sent = []

    def send(self, event):
        self.sent.append(event)
        from ranking_alerts import ProviderResult

        return ProviderResult(
            status=self.status,
            provider=self.provider_name,
            message_id=f"{self.status}-{len(self.sent)}",
            metadata={"safe": True},
        )


def rank_change(**overrides):
    row = {
        "fencer_id": "1001",
        "weapon": "Epee",
        "category": "Men's Senior",
        "season": 2026,
        "rank": 7,
        "previous_rank": 10,
        "rank_change": 3,
        "trend_direction": "up",
        "computed_at": NOW,
    }
    row.update(overrides)
    return row


def subscription(**overrides):
    row = {
        "id": "sub-1",
        "fencer_id": "1001",
        "weapon": None,
        "category": None,
        "email": "fan@example.com",
        "phone_e164": None,
        "email_opt_in": True,
        "sms_opt_in": False,
        "active": True,
        "unsubscribed_at": None,
        "unsubscribe_token_hash": "token-hash",
        "min_rank_change": 1,
    }
    row.update(overrides)
    return row


def test_ranking_alerts_migration_defines_subscription_and_delivery_tables():
    sql = MIGRATION.read_text()
    normalized = " ".join(sql.lower().split())

    assert "drop " not in normalized
    assert "truncate " not in normalized
    assert "delete from" not in normalized
    assert "create table if not exists public.fs_ranking_alert_subscriptions" in normalized
    assert "create table if not exists public.fs_ranking_alert_deliveries" in normalized
    assert "email_opt_in boolean not null default false" in normalized
    assert "sms_opt_in boolean not null default false" in normalized
    assert "unsubscribe_token_hash text not null" in normalized
    assert "unsubscribe_token text" not in normalized
    assert "idempotency_key text not null" in normalized
    assert "unique (idempotency_key)" in normalized
    assert "check (channel in ('email', 'sms'))" in normalized
    assert "check (status in ('dry_run', 'sent', 'failed', 'rate_limited', 'skipped'))" in normalized
    assert "alter table public.fs_ranking_alert_subscriptions enable row level security" in normalized
    assert "alter table public.fs_ranking_alert_deliveries enable row level security" in normalized


def test_build_alert_events_detects_rank_changes_and_suppresses_duplicates():
    from ranking_alerts import build_alert_events

    changes = [
        rank_change(),
        rank_change(fencer_id="1002"),
        rank_change(rank=10, previous_rank=10, rank_change=0, trend_direction="stable"),
        rank_change(rank=9, previous_rank=10, rank_change=1),
    ]
    subscriptions = [
        subscription(min_rank_change=2),
    ]

    events, stats = build_alert_events(changes, subscriptions, now=NOW)

    assert stats["rank_changes"] == 3
    assert stats["events"] == 1
    assert events[0].subscription_id == "sub-1"
    assert events[0].channel == "email"
    assert events[0].rank == 7
    assert events[0].previous_rank == 10
    assert events[0].rank_change == 3
    assert "fan@example.com" not in events[0].idempotency_key

    duplicate_events, duplicate_stats = build_alert_events(
        changes,
        subscriptions,
        existing_delivery_statuses={events[0].idempotency_key: "dry_run"},
        now=NOW,
    )

    assert duplicate_events == []
    assert duplicate_stats["duplicates"] == 1


def test_dry_run_provider_and_delivery_log_do_not_expose_contact_or_secrets(capsys):
    from ranking_alerts import DryRunProvider, build_alert_events, build_delivery_log_row

    events, _ = build_alert_events([rank_change()], [subscription()], now=NOW)
    provider = DryRunProvider()

    result = provider.send(events[0])
    captured = capsys.readouterr().out
    log_row = build_delivery_log_row(events[0], result, now=NOW)

    assert result.status == "dry_run"
    assert result.provider == "dry_run"
    assert "fan@example.com" not in captured
    assert log_row["contact_hash"]
    assert "fan@example.com" not in str(log_row)
    assert log_row["status"] == "dry_run"


def test_invalid_contact_and_unsubscribe_suppress_alerts():
    from ranking_alerts import build_alert_events

    changes = [rank_change()]
    subscriptions = [
        subscription(id="invalid-email", email="not-an-email"),
        subscription(id="unsubscribed", unsubscribed_at=NOW),
        subscription(id="inactive", active=False),
        subscription(id="missing-token", unsubscribe_token_hash=""),
        subscription(id="valid-sms", email_opt_in=False, sms_opt_in=True, phone_e164="+14155550199"),
    ]

    events, stats = build_alert_events(changes, subscriptions, now=NOW)

    assert [(event.subscription_id, event.channel) for event in events] == [("valid-sms", "sms")]
    assert stats["invalid_contacts"] == 1
    assert stats["unsubscribed"] == 1
    assert stats["inactive"] == 1
    assert stats["missing_unsubscribe_hash"] == 1


def test_unsubscribe_by_token_hashes_token_before_update():
    from ranking_alerts import hash_unsubscribe_token, unsubscribe_by_token

    token = "raw-secret-token"
    token_hash = hash_unsubscribe_token(token)
    client = FakeSupabase(
        {
            "fs_ranking_alert_subscriptions": [
                subscription(id="sub-token", unsubscribe_token_hash=token_hash)
            ]
        }
    )

    updated = unsubscribe_by_token(client, token, now=NOW)

    assert updated == 1
    assert client.updates == [
        {
            "table": "fs_ranking_alert_subscriptions",
            "payload": {"active": False, "unsubscribed_at": NOW},
            "filters": [("eq", "unsubscribe_token_hash", token_hash)],
        }
    ]
    assert "raw-secret-token" not in str(client.updates)


def test_deliver_ranking_alerts_uses_idempotency_and_rate_limits():
    from ranking_alerts import DeliveryRateLimiter, build_idempotency_key, deliver_ranking_alerts

    first_key = build_idempotency_key(
        subscription_id="sub-duplicate",
        channel="email",
        fencer_id="1001",
        weapon="Epee",
        category="Men's Senior",
        season=2026,
        rank=7,
        previous_rank=10,
        rank_change=3,
    )
    client = FakeSupabase(
        {
            "fs_rankings_trends": [
                rank_change(),
            ],
            "fs_ranking_alert_subscriptions": [
                subscription(id="sub-duplicate"),
                subscription(id="sub-rate-limited", email="second@example.com"),
                subscription(id="sub-rate-limited-2", email="third@example.com"),
            ],
            "fs_ranking_alert_deliveries": [
                {"idempotency_key": first_key, "status": "sent"}
            ],
        }
    )
    provider = RecordingProvider()
    limiter = DeliveryRateLimiter(max_per_channel={"email": 1})

    summary = deliver_ranking_alerts(
        client=client,
        providers={"email": provider},
        limiter=limiter,
        now=NOW,
        log_run=False,
    )

    assert summary["duplicates"] == 1
    assert summary["delivered"] == 1
    assert summary["rate_limited"] == 1
    assert len(provider.sent) == 1
    assert provider.sent[0].subscription_id == "sub-rate-limited"
    delivery_calls = [call for call in client.upserts if call["table"] == "fs_ranking_alert_deliveries"]
    assert delivery_calls
    assert {row["status"] for call in delivery_calls for row in call["rows"]} == {"sent", "rate_limited"}
    assert {call["on_conflict"] for call in delivery_calls} == {"idempotency_key"}

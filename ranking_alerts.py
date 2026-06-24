import hashlib
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
DELIVERY_CONFLICT_COLUMNS = "idempotency_key"
DELIVERED_STATUSES = {"sent", "dry_run"}
VALID_CHANNELS = {"email", "sms"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


@dataclass(frozen=True)
class AlertEvent:
    subscription_id: str
    fencer_id: str
    weapon: str
    category: str
    season: int
    rank: int
    previous_rank: int
    rank_change: int
    trend_direction: str
    channel: str
    contact: str
    contact_hash: str
    idempotency_key: str
    computed_at: str | None = None


@dataclass(frozen=True)
class ProviderResult:
    status: str
    provider: str
    message_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DryRunProvider:
    provider_name = "dry_run"

    def send(self, event: AlertEvent) -> ProviderResult:
        print(
            "[ranking_alerts] dry-run "
            f"{event.channel} alert idempotency_key={event.idempotency_key[:16]} "
            f"contact_hash={event.contact_hash[:16]}"
        )
        return ProviderResult(
            status="dry_run",
            provider=self.provider_name,
            metadata={"dry_run": True},
        )


class WebhookProvider:
    def __init__(self, *, channel: str, url: str, token: str | None = None):
        if channel not in VALID_CHANNELS:
            raise ValueError(f"Unsupported alert channel: {channel}")
        self.channel = channel
        self.url = url
        self.token = token
        self.provider_name = f"{channel}_webhook"

    def send(self, event: AlertEvent) -> ProviderResult:
        import requests

        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = {
            "channel": event.channel,
            "to": event.contact,
            "subject": build_alert_subject(event),
            "body": build_alert_body(event),
            "idempotency_key": event.idempotency_key,
            "metadata": safe_event_metadata(event),
        }
        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            message_id = response.headers.get("X-Message-Id")
            return ProviderResult(
                status="sent",
                provider=self.provider_name,
                message_id=message_id,
                metadata={"http_status": response.status_code},
            )
        except Exception as exc:
            return ProviderResult(
                status="failed",
                provider=self.provider_name,
                error=sanitize_for_log(str(exc)),
            )


class DeliveryRateLimiter:
    def __init__(
        self,
        *,
        max_per_channel: dict[str, int] | None = None,
        max_per_subscription_channel: int | None = None,
    ):
        self.max_per_channel = max_per_channel or {
            "email": _env_int("RANKING_ALERT_EMAIL_MAX_PER_RUN", 100),
            "sms": _env_int("RANKING_ALERT_SMS_MAX_PER_RUN", 50),
        }
        self.max_per_subscription_channel = (
            max_per_subscription_channel
            if max_per_subscription_channel is not None
            else _env_int("RANKING_ALERT_SUBSCRIPTION_CHANNEL_MAX_PER_RUN", 10)
        )
        self.channel_counts: dict[str, int] = {}
        self.subscription_channel_counts: dict[tuple[str, str], int] = {}

    def allow(self, event: AlertEvent) -> tuple[bool, str | None]:
        channel_count = self.channel_counts.get(event.channel, 0)
        channel_limit = self.max_per_channel.get(event.channel)
        if channel_limit is not None and channel_count >= channel_limit:
            return False, f"{event.channel} channel run limit reached"

        sub_key = (event.subscription_id, event.channel)
        sub_count = self.subscription_channel_counts.get(sub_key, 0)
        if self.max_per_subscription_channel is not None and sub_count >= self.max_per_subscription_channel:
            return False, "subscription channel run limit reached"

        self.channel_counts[event.channel] = channel_count + 1
        self.subscription_channel_counts[sub_key] = sub_count + 1
        return True, None


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
        return value if value >= 0 else default
    except ValueError:
        return default


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_email(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    email = text.lower()
    return email if EMAIL_RE.match(email) else None


def normalize_phone_e164(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    phone = re.sub(r"[\s().-]+", "", text)
    return phone if E164_RE.match(phone) else None


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def contact_hash(channel: str, contact: str) -> str:
    return hash_value(f"{channel}:{contact}")


def hash_unsubscribe_token(token: str, *, pepper: str | None = None) -> str:
    pepper = pepper if pepper is not None else os.environ.get("RANKING_ALERT_TOKEN_PEPPER", "")
    return hash_value(f"{pepper}\0{token}")


def generate_unsubscribe_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_unsubscribe_token(token)


def build_idempotency_key(
    *,
    subscription_id: str,
    channel: str,
    fencer_id: str,
    weapon: str,
    category: str,
    season: int,
    rank: int,
    previous_rank: int | None,
    rank_change: int,
) -> str:
    raw = "|".join(
        [
            subscription_id,
            channel,
            fencer_id,
            weapon,
            category,
            str(season),
            str(rank),
            str(previous_rank),
            str(rank_change),
        ]
    )
    return hash_value(raw)


def normalize_rank_change(row: dict[str, Any]) -> dict[str, Any] | None:
    fencer_id = clean_text(row.get("fencer_id"))
    weapon = clean_text(row.get("weapon"))
    category = clean_text(row.get("category"))
    season = coerce_int(row.get("season"))
    rank = coerce_int(row.get("rank"))
    previous_rank = coerce_int(row.get("previous_rank"))
    rank_change = coerce_int(row.get("rank_change"))
    if (
        not fencer_id
        or not weapon
        or not category
        or season is None
        or rank is None
        or previous_rank is None
        or rank_change is None
        or rank_change == 0
    ):
        return None
    return {
        "fencer_id": fencer_id,
        "weapon": weapon,
        "category": category,
        "season": season,
        "rank": rank,
        "previous_rank": previous_rank,
        "rank_change": rank_change,
        "trend_direction": clean_text(row.get("trend_direction")) or ("up" if rank_change > 0 else "down"),
        "computed_at": clean_text(row.get("computed_at")),
    }


def subscription_matches_change(subscription: dict[str, Any], change: dict[str, Any]) -> bool:
    if clean_text(subscription.get("fencer_id")) != change["fencer_id"]:
        return False
    weapon = clean_text(subscription.get("weapon"))
    category = clean_text(subscription.get("category"))
    if weapon and weapon != change["weapon"]:
        return False
    if category and category != change["category"]:
        return False
    min_rank_change = coerce_int(subscription.get("min_rank_change")) or 1
    return abs(change["rank_change"]) >= min_rank_change


def channels_for_subscription(subscription: dict[str, Any], stats: dict[str, int]) -> list[tuple[str, str]]:
    channels: list[tuple[str, str]] = []
    if bool(subscription.get("email_opt_in")):
        email = normalize_email(subscription.get("email"))
        if email:
            channels.append(("email", email))
        else:
            stats["invalid_contacts"] += 1
    if bool(subscription.get("sms_opt_in")):
        phone = normalize_phone_e164(subscription.get("phone_e164"))
        if phone:
            channels.append(("sms", phone))
        else:
            stats["invalid_contacts"] += 1
    return channels


def build_alert_events(
    rank_changes: list[dict[str, Any]],
    subscriptions: list[dict[str, Any]],
    *,
    existing_delivery_statuses: dict[str, str] | None = None,
    now: str | None = None,
) -> tuple[list[AlertEvent], dict[str, int]]:
    existing_delivery_statuses = existing_delivery_statuses or {}
    stats = {
        "changes_read": len(rank_changes),
        "subscriptions": len(subscriptions),
        "rank_changes": 0,
        "events": 0,
        "duplicates": 0,
        "inactive": 0,
        "unsubscribed": 0,
        "missing_unsubscribe_hash": 0,
        "invalid_contacts": 0,
        "threshold_skips": 0,
        "unmatched": 0,
    }

    normalized_changes = []
    for row in rank_changes:
        change = normalize_rank_change(row)
        if change:
            stats["rank_changes"] += 1
            normalized_changes.append(change)

    events: list[AlertEvent] = []
    for change in normalized_changes:
        matched_any_subscription = False
        for subscription in subscriptions:
            if clean_text(subscription.get("fencer_id")) != change["fencer_id"]:
                continue
            matched_any_subscription = True
            if subscription.get("active") is False:
                stats["inactive"] += 1
                continue
            if subscription.get("unsubscribed_at"):
                stats["unsubscribed"] += 1
                continue
            if not clean_text(subscription.get("unsubscribe_token_hash")):
                stats["missing_unsubscribe_hash"] += 1
                continue
            if not subscription_matches_change(subscription, change):
                stats["threshold_skips"] += 1
                continue

            for channel, contact in channels_for_subscription(subscription, stats):
                subscription_id = str(subscription["id"])
                idempotency_key = build_idempotency_key(
                    subscription_id=subscription_id,
                    channel=channel,
                    fencer_id=change["fencer_id"],
                    weapon=change["weapon"],
                    category=change["category"],
                    season=change["season"],
                    rank=change["rank"],
                    previous_rank=change["previous_rank"],
                    rank_change=change["rank_change"],
                )
                if existing_delivery_statuses.get(idempotency_key) in DELIVERED_STATUSES:
                    stats["duplicates"] += 1
                    continue
                events.append(
                    AlertEvent(
                        subscription_id=subscription_id,
                        fencer_id=change["fencer_id"],
                        weapon=change["weapon"],
                        category=change["category"],
                        season=change["season"],
                        rank=change["rank"],
                        previous_rank=change["previous_rank"],
                        rank_change=change["rank_change"],
                        trend_direction=change["trend_direction"],
                        channel=channel,
                        contact=contact,
                        contact_hash=contact_hash(channel, contact),
                        idempotency_key=idempotency_key,
                        computed_at=change.get("computed_at") or now,
                    )
                )
        if not matched_any_subscription:
            stats["unmatched"] += 1

    stats["events"] = len(events)
    return events, stats


def build_alert_subject(event: AlertEvent) -> str:
    direction = "up" if event.rank_change > 0 else "down"
    return f"Fencer {event.fencer_id} rank moved {direction}"


def build_alert_body(event: AlertEvent) -> str:
    direction = "up" if event.rank_change > 0 else "down"
    return (
        f"Fencer {event.fencer_id} moved {direction} from rank "
        f"{event.previous_rank} to {event.rank} in {event.weapon} "
        f"{event.category} for season {event.season}."
    )


def safe_event_metadata(event: AlertEvent) -> dict[str, Any]:
    return {
        "fencer_id": event.fencer_id,
        "weapon": event.weapon,
        "category": event.category,
        "season": event.season,
        "rank": event.rank,
        "previous_rank": event.previous_rank,
        "rank_change": event.rank_change,
        "trend_direction": event.trend_direction,
        "computed_at": event.computed_at,
    }


def sanitize_for_log(value: str | None) -> str | None:
    if value is None:
        return None
    sanitized = str(value)
    for name, secret in os.environ.items():
        upper = name.upper()
        if secret and any(token in upper for token in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            sanitized = sanitized.replace(secret, "***")
    sanitized = re.sub(r"(?i)(token|key|secret|password)=([^&\s]+)", r"\1=***", sanitized)
    return sanitized[:1000]


def build_delivery_log_row(event: AlertEvent, result: ProviderResult, *, now: str | None = None) -> dict[str, Any]:
    now = now or utc_now()
    status = result.status if result.status in {"dry_run", "sent", "failed", "rate_limited", "skipped"} else "failed"
    return {
        "subscription_id": event.subscription_id,
        "idempotency_key": event.idempotency_key,
        "fencer_id": event.fencer_id,
        "weapon": event.weapon,
        "category": event.category,
        "season": event.season,
        "rank": event.rank,
        "previous_rank": event.previous_rank,
        "rank_change": event.rank_change,
        "channel": event.channel,
        "provider": result.provider,
        "status": status,
        "contact_hash": event.contact_hash,
        "provider_message_id": result.message_id,
        "error": sanitize_for_log(result.error),
        "metadata": {
            **safe_event_metadata(event),
            **{key: value for key, value in result.metadata.items() if key not in {"contact", "to"}},
        },
        "created_at": now,
        "sent_at": now if status in DELIVERED_STATUSES else None,
    }


def fetch_paginated(client, table_name: str, columns: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table(table_name)
            .select(columns)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def fetch_rank_changes(client) -> list[dict[str, Any]]:
    return fetch_paginated(
        client,
        "fs_rankings_trends",
        "fencer_id,weapon,category,season,rank,previous_rank,rank_change,trend_direction,computed_at",
    )


def fetch_subscriptions(client) -> list[dict[str, Any]]:
    return fetch_paginated(
        client,
        "fs_ranking_alert_subscriptions",
        (
            "id,fencer_id,weapon,category,email,phone_e164,email_opt_in,sms_opt_in,"
            "active,unsubscribed_at,unsubscribe_token_hash,min_rank_change"
        ),
    )


def fetch_existing_delivery_statuses(client, idempotency_keys: list[str]) -> dict[str, str]:
    if not idempotency_keys:
        return {}
    statuses: dict[str, str] = {}
    keys = sorted(set(idempotency_keys))
    for index in range(0, len(keys), 100):
        batch = keys[index : index + 100]
        rows = (
            client.table("fs_ranking_alert_deliveries")
            .select("idempotency_key,status")
            .in_("idempotency_key", batch)
            .execute()
            .data
            or []
        )
        for row in rows:
            key = clean_text(row.get("idempotency_key"))
            status = clean_text(row.get("status"))
            if key and status:
                statuses[key] = status
    return statuses


def upsert_delivery_log(client, row: dict[str, Any]) -> None:
    client.table("fs_ranking_alert_deliveries").upsert(
        row,
        on_conflict=DELIVERY_CONFLICT_COLUMNS,
    ).execute()


def build_default_providers() -> dict[str, Any]:
    token = os.environ.get("RANKING_ALERT_WEBHOOK_TOKEN")
    email_url = os.environ.get("RANKING_ALERT_EMAIL_WEBHOOK_URL")
    sms_url = os.environ.get("RANKING_ALERT_SMS_WEBHOOK_URL")
    return {
        "email": WebhookProvider(channel="email", url=email_url, token=token) if email_url else DryRunProvider(),
        "sms": WebhookProvider(channel="sms", url=sms_url, token=token) if sms_url else DryRunProvider(),
    }


def deliver_ranking_alerts(
    *,
    client=None,
    providers: dict[str, Any] | None = None,
    limiter: DeliveryRateLimiter | None = None,
    now: str | None = None,
    log_run: bool = True,
) -> dict[str, int]:
    client = client or get_supabase_client()
    providers = providers or build_default_providers()
    limiter = limiter or DeliveryRateLimiter()
    now = now or utc_now()
    run_log = ScraperRunLogger("ranking_alerts").start() if log_run else None

    try:
        rank_changes = fetch_rank_changes(client)
        subscriptions = fetch_subscriptions(client)
        candidate_events, _ = build_alert_events(rank_changes, subscriptions, now=now)
        existing = fetch_existing_delivery_statuses(
            client,
            [event.idempotency_key for event in candidate_events],
        )
        events, stats = build_alert_events(
            rank_changes,
            subscriptions,
            existing_delivery_statuses=existing,
            now=now,
        )

        summary = {
            "changes_read": len(rank_changes),
            "subscriptions": len(subscriptions),
            "events": len(events),
            "duplicates": stats["duplicates"],
            "delivered": 0,
            "dry_run": 0,
            "failed": 0,
            "rate_limited": 0,
            "skipped": (
                stats["inactive"]
                + stats["unsubscribed"]
                + stats["missing_unsubscribe_hash"]
                + stats["invalid_contacts"]
                + stats["threshold_skips"]
            ),
        }

        for event in events:
            allowed, reason = limiter.allow(event)
            if not allowed:
                result = ProviderResult(
                    status="rate_limited",
                    provider="rate_limiter",
                    error=reason,
                    metadata={"rate_limited": True},
                )
                summary["rate_limited"] += 1
            else:
                provider = providers.get(event.channel) or DryRunProvider()
                result = provider.send(event)
                if result.status == "sent":
                    summary["delivered"] += 1
                elif result.status == "dry_run":
                    summary["delivered"] += 1
                    summary["dry_run"] += 1
                else:
                    summary["failed"] += 1

            upsert_delivery_log(client, build_delivery_log_row(event, result, now=now))

        set_state("ranking_alerts", "last_run", {**summary, "updated_at": now})
        if run_log:
            run_log.complete(
                written=summary["delivered"],
                failed=summary["failed"],
                skipped=summary["skipped"] + summary["duplicates"] + summary["rate_limited"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def unsubscribe_by_token(client, token: str, *, now: str | None = None) -> int:
    token_hash = hash_unsubscribe_token(token)
    now = now or utc_now()
    result = (
        client.table("fs_ranking_alert_subscriptions")
        .update({"active": False, "unsubscribed_at": now})
        .eq("unsubscribe_token_hash", token_hash)
        .execute()
    )
    return len(result.data or [])


def main() -> None:
    print(f"Ranking alerts starting - {utc_now()}")
    summary = deliver_ranking_alerts()
    print(
        "Ranking alerts complete - "
        f"events={summary['events']}, delivered={summary['delivered']}, "
        f"dry_run={summary['dry_run']}, failed={summary['failed']}, "
        f"duplicates={summary['duplicates']}, rate_limited={summary['rate_limited']}"
    )


if __name__ == "__main__":
    main()

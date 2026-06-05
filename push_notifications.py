"""Mobile push notifications for live result changes.

Provider setup:
- Default mode is dry-run and never calls APNs/FCM.
- Set PUSH_PROVIDER=apns plus APNS_TEAM_ID, APNS_KEY_ID, APNS_BUNDLE_ID,
  and APNS_PRIVATE_KEY to configure APNs.
- Set PUSH_PROVIDER=fcm plus FCM_PROJECT_ID and either FCM_SERVER_KEY or
  GOOGLE_APPLICATION_CREDENTIALS to configure FCM.

Real APNs/FCM delivery is intentionally transport-injected. Without an injected
transport callable, APNs/FCM providers remain dry-run safe.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from supabase import Client, create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SOURCE = "push_notifications"
NOTIFICATION_TYPE = "live_result"
MAX_SENT_FINGERPRINTS = 5000
DEFAULT_RESULT_LIMIT = 100

LIVE_RESULT_SELECT = (
    "id,tournament_id,name,country,nationality,rank,placement,updated_at,"
    "fs_tournaments(id,name,season,start_date,end_date)"
)
SUBSCRIPTION_SELECT = (
    "id,user_id,device_id,notification_type,provider,provider_token,opt_in,"
    "disabled,tournament_id,device:fs_push_devices(id,user_id,platform,opt_in,disabled)"
)
PRIVATE_PAYLOAD_KEYS = {
    "provider_token",
    "token",
    "endpoint",
    "metadata",
    "raw_result",
    "email",
    "phone",
    "date_of_birth",
    "birth_date",
    "user_id",
    "device_id",
    "fie_fencer_id",
}
SENSITIVE_ERROR_PATTERNS = [
    re.compile(r"(authorization\s*:\s*bearer\s+)[^\s,;]+", re.IGNORECASE),
    re.compile(r"((?:provider_)?token\s*=\s*)[^\s,;]+", re.IGNORECASE),
    re.compile(r"((?:api[_-]?key|server[_-]?key|secret|private[_-]?key)\s*=\s*)[^\s,;]+", re.IGNORECASE),
    re.compile(r"\b(sk|rk|pk)_(live|test)_[A-Za-z0-9_]+\b"),
]


@dataclass
class DeliveryResult:
    success: bool
    status: str
    provider_message_id: str | None = None
    error: str | None = None
    dry_run: bool = True
    attempts: int = 1
    next_attempt_at: str | None = None


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0

    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0:
            raise ValueError("base_delay must be greater than or equal to 0")
        if self.max_delay < 0:
            raise ValueError("max_delay must be greater than or equal to 0")

    def delay_for_attempt(self, attempt: int) -> float:
        return min(self.max_delay, self.base_delay * (2 ** max(0, attempt - 1)))


def redact_provider_error(message: Any, *, max_length: int = 1000) -> str | None:
    if message in (None, ""):
        return None
    redacted = str(message)
    for pattern in SENSITIVE_ERROR_PATTERNS:
        if pattern.groups >= 2 and pattern.pattern.startswith("\\b("):
            redacted = pattern.sub("[REDACTED]", redacted)
        else:
            redacted = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
    return redacted[:max_length]


class SimpleRateLimiter:
    def __init__(
        self,
        min_interval: float = 0.0,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ):
        if min_interval < 0:
            raise ValueError("min_interval must be greater than or equal to 0")
        self.min_interval = min_interval
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self._last_seen: dict[str, float] = {}

    def wait(self, key: str):
        if not self.min_interval:
            return
        now = self.clock()
        last_seen = self._last_seen.get(key)
        if last_seen is not None:
            remaining = self.min_interval - (now - last_seen)
            if remaining > 0:
                self.sleep(remaining)
                now = self.clock()
        self._last_seen[key] = now


class PushProvider:
    provider_name = "unknown"
    dry_run = True

    def send(self, subscription: dict[str, Any], payload: dict[str, Any]) -> DeliveryResult:
        raise NotImplementedError


class DryRunPushProvider(PushProvider):
    provider_name = "dry-run"
    dry_run = True

    def __init__(self):
        self.deliveries: list[dict[str, Any]] = []

    def send(self, subscription: dict[str, Any], payload: dict[str, Any]) -> DeliveryResult:
        fingerprint = payload.get("data", {}).get("fingerprint", "")
        subscription_id = str(subscription.get("id") or "")
        self.deliveries.append(
            {
                "subscription_id": subscription_id,
                "user_id": subscription.get("user_id"),
                "provider": subscription.get("provider") or self.provider_name,
                "payload": payload,
            }
        )
        return DeliveryResult(
            success=True,
            status="dry_run",
            provider_message_id=f"dry-run:{subscription_id}:{fingerprint}",
            dry_run=True,
        )


class TransportPushProvider(PushProvider):
    def __init__(
        self,
        provider_name: str,
        credentials: dict[str, str],
        required_keys: list[str],
        transport: Callable[[dict[str, Any], dict[str, Any], dict[str, str]], Any]
        | None = None,
        dry_run: bool = True,
    ):
        self.provider_name = provider_name
        self.credentials = credentials
        self.required_keys = required_keys
        self.transport = transport
        self.dry_run = dry_run or not self.has_credentials or transport is None
        self.deliveries: list[dict[str, Any]] = []

    @property
    def has_credentials(self) -> bool:
        return all(self.credentials.get(key) for key in self.required_keys)

    @property
    def setup_required(self) -> list[str]:
        return [key for key in self.required_keys if not self.credentials.get(key)]

    def send(self, subscription: dict[str, Any], payload: dict[str, Any]) -> DeliveryResult:
        if self.dry_run:
            self.deliveries.append(
                {
                    "subscription_id": subscription.get("id"),
                    "provider": self.provider_name,
                    "payload": payload,
                    "setup_required": self.setup_required,
                }
            )
            status = "dry_run_missing_credentials" if self.setup_required else "dry_run"
            return DeliveryResult(success=True, status=status, dry_run=True)
        try:
            if self.transport is None:
                raise RuntimeError("transport is not configured")
            response = self.transport(subscription, payload, self.credentials)
            message_id = None
            if isinstance(response, dict):
                message_id = response.get("message_id") or response.get("id")
            return DeliveryResult(
                success=True,
                status="sent",
                provider_message_id=message_id,
                dry_run=False,
            )
        except Exception as exc:
            return DeliveryResult(
                success=False,
                status="failed",
                error=redact_provider_error(exc),
                dry_run=False,
            )


class ApnsPushProvider(TransportPushProvider):
    def __init__(
        self,
        credentials: dict[str, str],
        transport: Callable[[dict[str, Any], dict[str, Any], dict[str, str]], Any]
        | None = None,
        dry_run: bool = True,
    ):
        super().__init__(
            "apns",
            credentials,
            ["APNS_TEAM_ID", "APNS_KEY_ID", "APNS_BUNDLE_ID", "APNS_PRIVATE_KEY"],
            transport=transport,
            dry_run=dry_run,
        )


class FcmPushProvider(TransportPushProvider):
    def __init__(
        self,
        credentials: dict[str, str],
        transport: Callable[[dict[str, Any], dict[str, Any], dict[str, str]], Any]
        | None = None,
        dry_run: bool = True,
    ):
        super().__init__(
            "fcm",
            credentials,
            ["FCM_PROJECT_ID"],
            transport=transport,
            dry_run=dry_run or not (
                credentials.get("FCM_SERVER_KEY")
                or credentials.get("GOOGLE_APPLICATION_CREDENTIALS")
            ),
        )


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def provider_from_env(
    env: dict[str, str] | None = None,
    transport: Callable[[dict[str, Any], dict[str, Any], dict[str, str]], Any]
    | None = None,
) -> PushProvider:
    values = env if env is not None else os.environ
    mode = (values.get("PUSH_PROVIDER") or values.get("PUSH_PROVIDER_MODE") or "dry-run").lower()
    force_dry_run = str(values.get("PUSH_DRY_RUN", "")).lower() in {"1", "true", "yes"}
    if mode in {"apns", "apple"}:
        credentials = {
            key: values.get(key, "")
            for key in ("APNS_TEAM_ID", "APNS_KEY_ID", "APNS_BUNDLE_ID", "APNS_PRIVATE_KEY")
        }
        return ApnsPushProvider(credentials, transport=transport, dry_run=force_dry_run)
    if mode in {"fcm", "firebase"}:
        credentials = {
            key: values.get(key, "")
            for key in ("FCM_PROJECT_ID", "FCM_SERVER_KEY", "GOOGLE_APPLICATION_CREDENTIALS")
        }
        return FcmPushProvider(credentials, transport=transport, dry_run=force_dry_run)
    return DryRunPushProvider()


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _short_text(value: str | None, max_len: int = 120) -> str:
    text = _clean_text(value) or ""
    return text if len(text) <= max_len else text[: max_len - 3].rstrip() + "..."


def _first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def fetch_recent_live_results(client: Any, limit: int = DEFAULT_RESULT_LIMIT) -> list[dict[str, Any]]:
    result = (
        client.table("fs_results")
        .select(LIVE_RESULT_SELECT)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def fetch_live_result_subscriptions(client: Any) -> list[dict[str, Any]]:
    result = (
        client.table("fs_push_subscriptions")
        .select(SUBSCRIPTION_SELECT)
        .eq("notification_type", NOTIFICATION_TYPE)
        .eq("opt_in", True)
        .eq("disabled", False)
        .execute()
    )
    return result.data or []


def _fingerprint(parts: dict[str, Any]) -> str:
    encoded = json.dumps(parts, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def live_result_event(row: dict[str, Any]) -> dict[str, Any]:
    tournament = _first_dict(row.get("fs_tournaments") or row.get("tournament"))
    rank = row.get("rank") if row.get("rank") is not None else row.get("placement")
    tournament_id = str(row.get("tournament_id") or tournament.get("id") or "")
    event = {
        "event_type": NOTIFICATION_TYPE,
        "result_id": str(row.get("id") or ""),
        "tournament_id": tournament_id,
        "tournament_name": _short_text(tournament.get("name") or "Tournament"),
        "season": tournament.get("season"),
        "name": _short_text(row.get("name") or "Result update", max_len=80),
        "country": _short_text(row.get("country") or row.get("nationality"), max_len=40),
        "rank": str(rank) if rank is not None else "",
        "updated_at": str(row.get("updated_at") or ""),
    }
    event["fingerprint"] = _fingerprint(
        {
            "event_type": event["event_type"],
            "result_id": event["result_id"],
            "tournament_id": event["tournament_id"],
            "name": event["name"],
            "rank": event["rank"],
            "updated_at": event["updated_at"],
        }
    )
    return event


def build_push_payload(event: dict[str, Any]) -> dict[str, Any]:
    tournament_name = _short_text(event.get("tournament_name") or "Tournament", max_len=64)
    name = _short_text(event.get("name") or "Result update", max_len=60)
    rank = str(event.get("rank") or "")
    body = f"{tournament_name}: {name}"
    if rank:
        body = f"{body} #{rank}"
    data = {
        "event_type": NOTIFICATION_TYPE,
        "fingerprint": str(event.get("fingerprint") or ""),
        "tournament_id": str(event.get("tournament_id") or ""),
        "rank": rank,
    }
    if event.get("country"):
        data["country"] = str(event["country"])
    return {
        "title": "Live result",
        "body": _short_text(body, max_len=120),
        "data": {key: value for key, value in data.items() if key not in PRIVATE_PAYLOAD_KEYS},
    }


def _subscription_device(subscription: dict[str, Any]) -> dict[str, Any]:
    return _first_dict(subscription.get("device") or subscription.get("fs_push_devices"))


def validate_subscription(subscription: dict[str, Any]) -> tuple[bool, str | None]:
    user_id = subscription.get("user_id")
    if not subscription.get("id") or not user_id:
        return False, "missing_identity"
    if (subscription.get("notification_type") or NOTIFICATION_TYPE) != NOTIFICATION_TYPE:
        return False, "wrong_notification_type"
    if not _truthy(subscription.get("opt_in")):
        return False, "subscription_opted_out"
    if _truthy(subscription.get("disabled")):
        return False, "subscription_disabled"
    if not _clean_text(subscription.get("provider_token")):
        return False, "missing_provider_token"

    device = _subscription_device(subscription)
    device_user_id = device.get("user_id") or subscription.get("device_user_id")
    if device_user_id and str(device_user_id) != str(user_id):
        return False, "ownership_mismatch"
    if device and not _truthy(device.get("opt_in"), default=True):
        return False, "device_opted_out"
    if _truthy(device.get("disabled")):
        return False, "device_disabled"
    return True, None


def subscription_matches_event(subscription: dict[str, Any], event: dict[str, Any]) -> bool:
    tournament_id = subscription.get("tournament_id")
    if tournament_id and str(tournament_id) != str(event.get("tournament_id")):
        return False
    return True


def _state_list(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(item) for item in value}
    if isinstance(value, dict):
        values = value.get("fingerprints") or value.get("hashes")
        if isinstance(values, list):
            return {str(item) for item in values}
        return {str(item) for item in value.keys()}
    return set()


def fetch_logged_success_fingerprints(client: Any, subscription_id: Any) -> set[str]:
    result = (
        client.table("fs_push_delivery_log")
        .select("subscription_id,event_fingerprint,status")
        .eq("subscription_id", subscription_id)
        .execute()
    )
    sent_statuses = {"sent", "dry_run", "dry_run_missing_credentials"}
    return {
        str(row.get("event_fingerprint"))
        for row in (result.data or [])
        if str(row.get("subscription_id") or subscription_id) == str(subscription_id)
        and row.get("status") in sent_statuses
        and row.get("event_fingerprint")
    }


def sent_state_key(subscription_id: Any) -> str:
    return f"sent_live_result_{subscription_id}"


def _store_sent_state(subscription_id: Any, fingerprints: set[str]):
    ordered = sorted(fingerprints)[-MAX_SENT_FINGERPRINTS:]
    set_state(SOURCE, sent_state_key(subscription_id), ordered)


def send_with_retries(
    provider: PushProvider,
    subscription: dict[str, Any],
    payload: dict[str, Any],
    retry_policy: RetryPolicy | None = None,
    rate_limiter: SimpleRateLimiter | None = None,
    sleep: Callable[[float], None] | None = None,
    now: datetime | None = None,
) -> DeliveryResult:
    policy = retry_policy or RetryPolicy()
    sleeper = sleep or time.sleep
    limiter = rate_limiter or SimpleRateLimiter()
    last_result: DeliveryResult | None = None
    now_value = now or datetime.now(timezone.utc)

    for attempt in range(1, policy.max_attempts + 1):
        limiter.wait(provider.provider_name)
        try:
            result = provider.send(subscription, payload)
        except Exception as exc:
            result = DeliveryResult(
                success=False,
                status="failed",
                error=redact_provider_error(exc),
                dry_run=getattr(provider, "dry_run", True),
            )
        result.attempts = attempt
        if result.success:
            result.error = None
            return result
        last_result = result
        if attempt < policy.max_attempts:
            sleeper(policy.delay_for_attempt(attempt))

    assert last_result is not None
    last_result.attempts = policy.max_attempts
    last_result.next_attempt_at = (
        now_value + timedelta(seconds=policy.delay_for_attempt(policy.max_attempts))
    ).astimezone(timezone.utc).isoformat()
    return last_result


def _write_delivery_log(
    client: Any,
    subscription: dict[str, Any],
    event: dict[str, Any],
    payload: dict[str, Any],
    result: DeliveryResult,
    provider_name: str,
    now: datetime,
):
    row = {
        "subscription_id": subscription.get("id"),
        "user_id": subscription.get("user_id"),
        "event_fingerprint": event["fingerprint"],
        "event_type": NOTIFICATION_TYPE,
        "provider": subscription.get("provider") or provider_name,
        "status": result.status,
        "attempt_count": result.attempts,
        "payload": payload,
        "provider_message_id": result.provider_message_id,
        "error": redact_provider_error(result.error),
        "dry_run": result.dry_run,
        "delivered_at": now.astimezone(timezone.utc).isoformat() if result.success else None,
        "next_attempt_at": result.next_attempt_at,
    }
    client.table("fs_push_delivery_log").upsert(
        row,
        on_conflict="subscription_id,event_fingerprint",
    ).execute()


def run_push_notifications(
    client: Any | None = None,
    provider: PushProvider | None = None,
    now: datetime | None = None,
    log_run: bool = True,
    result_limit: int = DEFAULT_RESULT_LIMIT,
    retry_policy: RetryPolicy | None = None,
    rate_limiter: SimpleRateLimiter | None = None,
    sleep: Callable[[float], None] | None = None,
) -> dict[str, int]:
    now_value = now or datetime.now(timezone.utc)
    if now_value.tzinfo is None:
        now_value = now_value.replace(tzinfo=timezone.utc)
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    summary = {
        "results": 0,
        "events": 0,
        "subscriptions": 0,
        "skipped_subscriptions": 0,
        "sent": 0,
        "failed": 0,
        "duplicates": 0,
        "dry_run": 0,
        "skipped_events": 0,
    }

    try:
        client = client or get_supabase_client()
        provider = provider or provider_from_env()
        results = fetch_recent_live_results(client, limit=result_limit)
        summary["results"] = len(results)
        events = [
            live_result_event(row)
            for row in results
            if row.get("tournament_id") or _first_dict(row.get("fs_tournaments")).get("id")
        ]
        summary["events"] = len(events)
        subscriptions = fetch_live_result_subscriptions(client)
        valid_subscriptions = []
        for subscription in subscriptions:
            is_valid, _reason = validate_subscription(subscription)
            if is_valid:
                valid_subscriptions.append(subscription)
            else:
                summary["skipped_subscriptions"] += 1
        summary["subscriptions"] = len(valid_subscriptions)

        for subscription in valid_subscriptions:
            subscription_id = subscription["id"]
            sent_fingerprints = _state_list(
                get_state(SOURCE, sent_state_key(subscription_id))
            )
            sent_fingerprints.update(
                fetch_logged_success_fingerprints(client, subscription_id)
            )
            changed = False
            for event in events:
                if not subscription_matches_event(subscription, event):
                    summary["skipped_events"] += 1
                    continue
                fingerprint = event["fingerprint"]
                if fingerprint in sent_fingerprints:
                    summary["duplicates"] += 1
                    continue
                payload = build_push_payload(event)
                result = send_with_retries(
                    provider,
                    subscription,
                    payload,
                    retry_policy=retry_policy,
                    rate_limiter=rate_limiter,
                    sleep=sleep,
                    now=now_value,
                )
                _write_delivery_log(
                    client,
                    subscription,
                    event,
                    payload,
                    result,
                    provider.provider_name,
                    now_value,
                )
                if result.success:
                    sent_fingerprints.add(fingerprint)
                    changed = True
                    summary["sent"] += 1
                    if result.dry_run:
                        summary["dry_run"] += 1
                else:
                    summary["failed"] += 1
            if changed:
                _store_sent_state(subscription_id, sent_fingerprints)

        if run_log:
            run_log.complete(
                written=summary["sent"],
                failed=summary["failed"],
                skipped=summary["duplicates"] + summary["skipped_subscriptions"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main():
    summary = run_push_notifications()
    print(
        "Push notifications: "
        f"events={summary['events']}; subscriptions={summary['subscriptions']}; "
        f"sent={summary['sent']}; failed={summary['failed']}; "
        f"duplicates={summary['duplicates']}; dry_run={summary['dry_run']}"
    )


if __name__ == "__main__":
    main()

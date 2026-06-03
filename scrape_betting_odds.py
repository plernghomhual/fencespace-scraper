"""
Compliance-gated betting odds aggregator for upcoming fencing competitions.

Probe/compliance status (2026-06-02):
  - No live odds source is enabled by default because source legality and
    regional availability need compliance review.
  - Sources marked login_required, geo_restricted, robots_disallowed, or
    legal_unclear are skipped without probing.
  - Stored rows are informational market data only. This module does not
    produce selections, picks, forecasts, staking guidance, or betting advice.

To enable a live source, provide BETTING_ODDS_SOURCES_JSON as either a JSON
array or a path to a JSON file with OddsSource-compatible dictionaries. Each
source must have access_policy="public_permitted" and terms_confirmed=true.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

getcontext().prec = 28

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "scrape_betting_odds"
BATCH_SIZE = int(os.environ.get("BETTING_ODDS_UPSERT_BATCH_SIZE", "100"))
DEFAULT_STALE_AFTER_MINUTES = int(os.environ.get("BETTING_ODDS_STALE_AFTER_MINUTES", "60"))

HEADERS = {
    "User-Agent": "FenceSpace/1.0 (+https://fencespace.app; informational odds index)",
    "Accept": "application/json,text/plain,*/*",
}

PUBLIC_ACCESS_POLICY = "public_permitted"
BLOCKING_ACCESS_POLICIES = {
    "login_required",
    "geo_restricted",
    "robots_disallowed",
    "legal_unclear",
    "unknown",
}
OPEN_MARKET_STATUSES = {"", "open", "active", "available", "trading"}
WITHDRAWN_MARKET_STATUSES = {"withdrawn", "void", "cancelled", "canceled"}
LOGIN_MARKERS = (
    "login required",
    "sign in",
    "sign-in",
    "account required",
    "access denied",
    "geo restricted",
    "not available in your region",
)

_supabase = None


@dataclass(frozen=True)
class OddsSource:
    name: str
    source_url: str
    region: str
    access_policy: str
    terms_confirmed: bool = False
    source_disclaimer: str = ""
    region_disclaimer: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProbeResult:
    allowed: bool
    reason: str
    source: OddsSource
    response_text: str | None = None
    status_code: int | None = None


@dataclass(frozen=True)
class OddsParseResult:
    rows: list[dict[str, Any]]
    skipped: list[dict[str, Any]]


DEFAULT_SOURCES = [
    OddsSource(
        name="documented_stub",
        source_url="",
        region="global",
        access_policy="legal_unclear",
        terms_confirmed=False,
        source_disclaimer="No legally reviewed public odds source is configured.",
        region_disclaimer="Odds availability and legality vary by region.",
    )
]


def get_supabase_client():
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        from supabase import create_client

        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def _decimal(value: Decimal | int | float | str) -> Decimal:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"Invalid odds value: {value!r}") from exc


def parse_decimal_odds(value: Decimal | int | float | str) -> float:
    text = str(value).strip()
    if not text:
        raise ValueError("Missing odds value")

    lowered = text.lower()
    if lowered in {"evs", "even", "even money"}:
        return 2.0

    fraction = re.fullmatch(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)", text)
    if fraction:
        numerator = _decimal(fraction.group(1))
        denominator = _decimal(fraction.group(2))
        if denominator <= 0:
            raise ValueError(f"Invalid fractional odds denominator: {value!r}")
        decimal_odds = Decimal("1") + numerator / denominator
    elif re.fullmatch(r"[+-]\d+(?:\.\d+)?", text):
        american = _decimal(text)
        if american >= 100:
            decimal_odds = Decimal("1") + american / Decimal("100")
        elif american <= -100:
            decimal_odds = Decimal("1") + Decimal("100") / abs(american)
        else:
            raise ValueError(f"Invalid American odds value: {value!r}")
    else:
        decimal_odds = _decimal(text)

    if decimal_odds <= Decimal("1"):
        raise ValueError(f"Decimal odds must be greater than 1: {value!r}")
    return float(decimal_odds.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def decimal_to_implied_probability(decimal_odds: Decimal | int | float | str) -> float:
    odds = _decimal(decimal_odds)
    if odds <= Decimal("1"):
        raise ValueError(f"Decimal odds must be greater than 1: {decimal_odds!r}")
    probability = Decimal("1") / odds
    return float(probability.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _as_utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _market_type(market: dict[str, Any]) -> str:
    return str(
        market.get("market_type")
        or market.get("key")
        or market.get("type")
        or market.get("name")
        or ""
    ).strip()


def _participant(outcome: dict[str, Any]) -> str:
    return str(
        outcome.get("participant")
        or outcome.get("name")
        or outcome.get("runner")
        or outcome.get("selection")
        or ""
    ).strip()


def _price(outcome: dict[str, Any]) -> Any:
    for key in ("odds_decimal", "decimal", "price", "odds"):
        if outcome.get(key) not in (None, ""):
            return outcome[key]
    return None


def _source_metadata(source: OddsSource) -> dict[str, Any]:
    metadata = {
        "informational_only": True,
        "no_betting_advice": True,
        "source_disclaimer": source.source_disclaimer,
        "region_disclaimer": source.region_disclaimer,
        "access_policy": source.access_policy,
        "terms_confirmed": source.terms_confirmed,
    }
    metadata.update(source.metadata or {})
    return metadata


def _iter_events(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("events", "competitions", "tournaments", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def _skip(source: OddsSource, reason: str, **metadata: Any) -> dict[str, Any]:
    item = {
        "source": source.name,
        "region": source.region,
        "reason": reason,
        "informational_only": True,
        "no_betting_advice": True,
    }
    item.update(metadata)
    return item


def parse_odds_payload(
    payload: Any,
    source: OddsSource,
    *,
    scraped_at: datetime | None = None,
    stale_after_minutes: int = DEFAULT_STALE_AFTER_MINUTES,
) -> OddsParseResult:
    scraped_at = (scraped_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    base_metadata = _source_metadata(source)

    events = _iter_events(payload)
    if not events:
        return OddsParseResult(rows=[], skipped=[_skip(source, "missing_events")])

    for event in events:
        tournament_id = str(event.get("tournament_id") or event.get("id") or "").strip()
        markets = event.get("markets") or event.get("odds") or []
        if not tournament_id:
            skipped.append(_skip(source, "missing_tournament_id", event=event.get("name")))
            continue
        if not isinstance(markets, list) or not markets:
            skipped.append(_skip(source, "missing_markets", tournament_id=tournament_id))
            continue

        for market in [item for item in markets if isinstance(item, dict)]:
            market_type = _market_type(market)
            status = str(market.get("status") or "").strip().lower()
            if not market_type:
                skipped.append(_skip(source, "missing_market_type", tournament_id=tournament_id))
                continue
            if status in WITHDRAWN_MARKET_STATUSES:
                skipped.append(
                    _skip(
                        source,
                        "market_withdrawn",
                        tournament_id=tournament_id,
                        market_type=market_type,
                        market_status=status,
                    )
                )
                continue
            if status not in OPEN_MARKET_STATUSES:
                skipped.append(
                    _skip(
                        source,
                        f"market_{status or 'unavailable'}",
                        tournament_id=tournament_id,
                        market_type=market_type,
                        market_status=status,
                    )
                )
                continue

            outcomes = market.get("outcomes") or market.get("participants") or []
            if not isinstance(outcomes, list) or not outcomes:
                skipped.append(
                    _skip(source, "missing_outcomes", tournament_id=tournament_id, market_type=market_type)
                )
                continue

            last_update = _as_utc(
                market.get("last_update")
                or market.get("last_updated")
                or market.get("updated_at")
                or event.get("last_update")
                or event.get("last_updated")
            )
            stale = False
            stale_reason = None
            if last_update:
                age_seconds = (scraped_at - last_update).total_seconds()
                stale = age_seconds > stale_after_minutes * 60
                if stale:
                    stale_reason = f"last_update_older_than_{stale_after_minutes}_minutes"

            for outcome in [item for item in outcomes if isinstance(item, dict)]:
                participant = _participant(outcome)
                if not participant:
                    skipped.append(
                        _skip(source, "missing_participant", tournament_id=tournament_id, market_type=market_type)
                    )
                    continue
                try:
                    odds_decimal = parse_decimal_odds(_price(outcome))
                    implied_probability = decimal_to_implied_probability(odds_decimal)
                except ValueError as exc:
                    skipped.append(
                        _skip(
                            source,
                            "invalid_odds",
                            tournament_id=tournament_id,
                            market_type=market_type,
                            participant=participant,
                            detail=str(exc),
                        )
                    )
                    continue

                metadata = {
                    **base_metadata,
                    "market_status": status or "open",
                    "stale": stale,
                    "last_update": _iso(last_update) if last_update else None,
                }
                if stale_reason:
                    metadata["stale_reason"] = stale_reason
                if event.get("name"):
                    metadata["event_name"] = event.get("name")

                rows.append(
                    {
                        "source": source.name,
                        "tournament_id": tournament_id,
                        "market_type": market_type,
                        "participant": participant,
                        "odds_decimal": odds_decimal,
                        "implied_probability": implied_probability,
                        "region": source.region,
                        "source_url": source.source_url,
                        "scraped_at": _iso(scraped_at),
                        "metadata": metadata,
                    }
                )

    return OddsParseResult(rows=rows, skipped=skipped)


def probe_source_access(source: OddsSource, *, session=None, timeout: int = 20) -> ProbeResult:
    if source.access_policy != PUBLIC_ACCESS_POLICY or source.access_policy in BLOCKING_ACCESS_POLICIES:
        return ProbeResult(False, "source_not_public_permitted", source)
    if not source.terms_confirmed:
        return ProbeResult(False, "source_terms_not_confirmed", source)
    if not source.source_url:
        return ProbeResult(False, "missing_source_url", source)

    parsed = urlparse(source.source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ProbeResult(False, "invalid_source_url", source)

    session = session or requests.Session()
    try:
        response = session.get(source.source_url, headers=HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        return ProbeResult(False, "source_request_failed", source, status_code=None, response_text=str(exc))

    text = getattr(response, "text", "") or ""
    status_code = getattr(response, "status_code", None)
    lowered = text[:4000].lower()
    if status_code in {401, 403} or any(marker in lowered for marker in LOGIN_MARKERS):
        return ProbeResult(False, "blocked_or_login_required", source, text, status_code)
    if status_code is not None and status_code >= 400:
        return ProbeResult(False, "source_unavailable", source, text, status_code)
    return ProbeResult(True, "public_source_reachable", source, text, status_code)


def fetch_source_payload(source: OddsSource, *, session=None) -> tuple[Any | None, ProbeResult]:
    probe = probe_source_access(source, session=session)
    if not probe.allowed:
        return None, probe
    try:
        return json.loads(probe.response_text or "{}"), probe
    except json.JSONDecodeError:
        return None, ProbeResult(False, "invalid_json_payload", source, probe.response_text, probe.status_code)


def upsert_odds_rows(
    client,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = BATCH_SIZE,
) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table("fs_betting_odds").upsert(
                batch,
                on_conflict="source,tournament_id,market_type,participant,region",
            ).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"[scrape_betting_odds] upsert batch {index // batch_size} failed: {exc}")
    return written, failed


def build_informational_summary(*, written: int, failed: int, skipped: int) -> str:
    return (
        f"Stored {written} public odds rows as informational data only; "
        f"failed={failed}; skipped={skipped}; no advice generated."
    )


def load_sources_from_env() -> list[OddsSource]:
    raw = os.environ.get("BETTING_ODDS_SOURCES_JSON")
    if not raw:
        return DEFAULT_SOURCES

    raw = raw.strip()
    try:
        if raw.startswith("["):
            items = json.loads(raw)
        else:
            items = json.loads(Path(raw).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[scrape_betting_odds] Could not load BETTING_ODDS_SOURCES_JSON: {exc}")
        return DEFAULT_SOURCES

    sources = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sources.append(OddsSource(**item))
    return sources or DEFAULT_SOURCES


def scrape_betting_odds(
    *,
    client=None,
    sources: list[OddsSource] | None = None,
    session=None,
    log_run: bool = True,
    update_state: bool = True,
    stale_after_minutes: int = DEFAULT_STALE_AFTER_MINUTES,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        sources = sources if sources is not None else load_sources_from_env()
        previous_state = get_state(SOURCE, "last_run") if update_state else None
        all_rows: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        probes: list[dict[str, Any]] = []
        scraped_at = datetime.now(timezone.utc)

        for source in sources:
            payload, probe = fetch_source_payload(source, session=session)
            probes.append(
                {
                    "source": source.name,
                    "region": source.region,
                    "allowed": probe.allowed,
                    "reason": probe.reason,
                    "status_code": probe.status_code,
                }
            )
            if not probe.allowed:
                skipped.append(
                    _skip(
                        source,
                        probe.reason,
                        source_url=source.source_url,
                        status_code=probe.status_code,
                    )
                )
                continue
            parsed = parse_odds_payload(
                payload,
                source,
                scraped_at=scraped_at,
                stale_after_minutes=stale_after_minutes,
            )
            all_rows.extend(parsed.rows)
            skipped.extend(parsed.skipped)

        if all_rows:
            client = client or get_supabase_client()
            written, failed = upsert_odds_rows(client, all_rows)
        else:
            written, failed = 0, 0
        summary = {
            "sources": len(sources),
            "rows_parsed": len(all_rows),
            "written": written,
            "failed": failed,
            "skipped": len(skipped),
            "probes": probes,
            "skipped_details": skipped[:50],
            "previous_run": previous_state,
            "updated_at": _iso(datetime.now(timezone.utc)),
            "informational_only": True,
            "no_betting_advice": True,
        }
        if update_state:
            set_state(SOURCE, "last_run", summary)
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=len(skipped), metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    summary = scrape_betting_odds()
    print(
        build_informational_summary(
            written=int(summary.get("written", 0)),
            failed=int(summary.get("failed", 0)),
            skipped=int(summary.get("skipped", 0)),
        )
    )


if __name__ == "__main__":
    main()

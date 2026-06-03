import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SOURCE = "result_tweets"
MAX_X_CHARS = 280
X_URL_LENGTH = 23
DEFAULT_LIMIT = int(os.environ.get("RESULT_TWEETS_LIMIT", "10"))
FENCESPACE_BASE_URL = os.environ.get("FENCESPACE_BASE_URL", "https://fencespace.app").rstrip("/")
DEFAULT_HASHTAGS = ("#FenceSpace", "#Fencing")
TWEET_ENDPOINT = "https://api.twitter.com/2/tweets"

TOURNAMENT_COLUMNS = (
    "id,source_id,name,season,start_date,end_date,type,weapon,gender,category,"
    "city,country,competition_url_id,metadata,has_results"
)
RESULT_COLUMNS = "rank,placement,name,nationality,country,medal,metadata"

HTTP_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
ANY_URL_RE = re.compile(r"\b(?:[a-z][a-z0-9+.-]*://|www\.)[^\s]+", re.IGNORECASE)
HASHTAG_RE = re.compile(r"^#[A-Za-z][A-Za-z0-9_]{0,29}$")


@dataclass(frozen=True)
class ResultSummary:
    key: str
    tournament_id: str
    title: str
    event: str | None
    location: str | None
    result_url: str
    podium: list[dict[str, Any]]


class XBearerProvider:
    """Minimal X API v2 provider. Requires a user-context bearer token."""

    def __init__(self, token: str | None = None, session: requests.Session | None = None, timeout: int = 20):
        self.token = token or os.environ.get("X_API_BEARER_TOKEN")
        self.session = session or requests.Session()
        self.timeout = timeout
        if not self.token:
            raise RuntimeError("X_API_BEARER_TOKEN must be set for live posting.")

    def post(self, message: str) -> dict[str, Any]:
        response = self.session.post(
            TWEET_ENDPOINT,
            json={"text": message},
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            return {"id": data.get("id"), "text": data.get("text")}
        return {"raw": payload}


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(url, key)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def parse_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def to_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except Exception:
        return None


def effective_x_length(message: str) -> int:
    total = 0
    cursor = 0
    for match in HTTP_URL_RE.finditer(message):
        total += len(message[cursor : match.start()])
        total += X_URL_LENGTH
        cursor = match.end()
    total += len(message[cursor:])
    return total


def validate_post_text(message: str) -> list[str]:
    issues: list[str] = []
    if not clean_text(message):
        return ["message is empty"]
    if effective_x_length(message) > MAX_X_CHARS:
        issues.append(f"message exceeds {MAX_X_CHARS} X characters")

    links = [match.group(0).rstrip(".,)") for match in ANY_URL_RE.finditer(message)]
    if not links:
        issues.append("message must include at least one link")
    for link in links:
        parsed = urlparse(link)
        if parsed.scheme not in {"http", "https"}:
            issues.append(f"unsupported link: {link}")
        elif not parsed.netloc:
            issues.append(f"invalid link: {link}")

    hashtags = [part.rstrip(".,)") for part in message.split() if part.startswith("#")]
    if not hashtags:
        issues.append("message must include at least one hashtag")
    seen_hashtags = set()
    for tag in hashtags:
        if not HASHTAG_RE.match(tag):
            issues.append(f"invalid hashtag: {tag}")
        lowered = tag.lower()
        if lowered in seen_hashtags:
            issues.append(f"duplicate hashtag: {tag}")
        seen_hashtags.add(lowered)
    return issues


def result_key(tournament: dict[str, Any]) -> str:
    return str(tournament.get("source_id") or tournament.get("id") or "")


def event_label(tournament: dict[str, Any]) -> str | None:
    parts = [
        clean_text(tournament.get("category")),
        clean_text(tournament.get("gender")),
        clean_text(tournament.get("weapon")),
    ]
    return " ".join(part for part in parts if part) or None


def location_label(tournament: dict[str, Any]) -> str | None:
    parts = [clean_text(tournament.get("city")), clean_text(tournament.get("country"))]
    return ", ".join(part for part in parts if part) or None


def result_url(tournament: dict[str, Any]) -> str:
    metadata = parse_metadata(tournament.get("metadata"))
    for key in ("result_url", "source_url", "event_url", "competition_url"):
        value = clean_text(metadata.get(key) or tournament.get(key))
        if value and value.startswith(("http://", "https://")):
            return value

    season = tournament.get("season")
    competition_id = tournament.get("competition_url_id")
    if season and competition_id:
        return f"https://fie.org/competitions/{season}/{competition_id}"
    return f"{FENCESPACE_BASE_URL}/tournaments/{tournament.get('id')}/results"


def podium_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    podium: list[dict[str, Any]] = []
    medal_ranks = {"gold": 1, "silver": 2, "bronze": 3}
    for row in rows:
        rank = to_int(row.get("rank") if row.get("rank") is not None else row.get("placement"))
        if rank is None:
            medal = clean_text(row.get("medal"))
            rank = medal_ranks.get(medal.lower()) if medal else None
        name = clean_text(row.get("name"))
        if rank is None or rank > 3 or not name:
            continue
        country = clean_text(row.get("nationality") or row.get("country"))
        podium.append({"rank": rank, "name": name, "country": country})

    podium.sort(key=lambda row: (row["rank"], row["name"]))
    return podium[:4]


def build_result_summary(tournament: dict[str, Any], rows: list[dict[str, Any]]) -> ResultSummary | None:
    key = result_key(tournament)
    title = clean_text(tournament.get("name"))
    tournament_id = clean_text(tournament.get("id"))
    podium = podium_rows(rows)
    if not key or not title or not tournament_id or not podium:
        return None
    return ResultSummary(
        key=key,
        tournament_id=tournament_id,
        title=title,
        event=event_label(tournament),
        location=location_label(tournament),
        result_url=result_url(tournament),
        podium=podium,
    )


def format_result_post(summary: ResultSummary, hashtags: tuple[str, ...] = DEFAULT_HASHTAGS) -> str:
    lines = [f"Result: {summary.title}"]
    if summary.event:
        lines.append(summary.event)
    if summary.location:
        lines.append(summary.location)
    for row in summary.podium:
        suffix = f" ({row['country']})" if row.get("country") else ""
        lines.append(f"{row['rank']}. {row['name']}{suffix}")
    lines.append(summary.result_url)
    lines.append(" ".join(hashtags))
    return "\n".join(lines)


def fetch_recent_completed_tournaments(client, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    result = (
        client.table("fs_tournaments")
        .select(TOURNAMENT_COLUMNS)
        .eq("has_results", True)
        .order("end_date", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def fetch_result_rows(client, tournament_id: str, limit: int = 8) -> list[dict[str, Any]]:
    result = (
        client.table("fs_results")
        .select(RESULT_COLUMNS)
        .eq("tournament_id", tournament_id)
        .order("rank")
        .limit(limit)
        .execute()
    )
    return result.data or []


def gather_result_summaries(client, limit: int = DEFAULT_LIMIT) -> list[ResultSummary]:
    summaries = []
    for tournament in fetch_recent_completed_tournaments(client, limit=limit):
        tournament_id = clean_text(tournament.get("id"))
        if not tournament_id:
            continue
        result_rows = fetch_result_rows(client, tournament_id)
        summary = build_result_summary(tournament, result_rows)
        if summary:
            summaries.append(summary)
    return summaries


def load_posted_keys() -> set[str]:
    value = get_state(SOURCE, "posted_result_keys")
    if isinstance(value, list):
        return {str(item) for item in value}
    if isinstance(value, dict):
        keys = value.get("keys")
        if isinstance(keys, list):
            return {str(item) for item in keys}
        return {str(item) for item in value.keys()}
    return set()


def load_delivery_log() -> dict[str, Any]:
    value = get_state(SOURCE, "delivery_log")
    return dict(value) if isinstance(value, dict) else {}


def iso_timestamp(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def mark_posted(summary: ResultSummary, provider_result: dict[str, Any], now: datetime | None = None) -> None:
    posted_keys = load_posted_keys()
    posted_keys.add(summary.key)
    delivery_log = load_delivery_log()
    delivery_log[summary.key] = {
        "tournament_id": summary.tournament_id,
        "provider_post_id": provider_result.get("id"),
        "posted_at": iso_timestamp(now),
    }
    set_state(SOURCE, "posted_result_keys", sorted(posted_keys))
    set_state(SOURCE, "delivery_log", delivery_log)


def require_live_config() -> None:
    if os.environ.get("RESULT_TWEETS_LIVE") != "1":
        raise RuntimeError("RESULT_TWEETS_LIVE=1 must be set for live posting.")
    if not os.environ.get("X_API_BEARER_TOKEN"):
        raise RuntimeError("X_API_BEARER_TOKEN must be set for live posting.")


def post_result_tweets(
    *,
    client=None,
    provider=None,
    live: bool = False,
    limit: int = DEFAULT_LIMIT,
    now: datetime | None = None,
    log_run: bool = True,
) -> dict[str, Any]:
    if live:
        require_live_config()

    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    summary: dict[str, Any] = {
        "dry_run": not live,
        "generated": 0,
        "posted": 0,
        "skipped_duplicates": 0,
        "skipped_invalid": 0,
        "failed": 0,
        "posts": [],
    }

    try:
        client = client or get_supabase_client()
        provider = provider or (XBearerProvider() if live else None)
        posted_keys = load_posted_keys()

        for result_summary in gather_result_summaries(client, limit=limit):
            if result_summary.key in posted_keys:
                summary["skipped_duplicates"] += 1
                continue

            message = format_result_post(result_summary)
            issues = validate_post_text(message)
            post_record: dict[str, Any] = {
                "key": result_summary.key,
                "tournament_id": result_summary.tournament_id,
                "message": message,
                "validation_issues": issues,
            }
            if issues:
                summary["skipped_invalid"] += 1
                summary["posts"].append(post_record)
                continue

            summary["generated"] += 1
            if live:
                try:
                    provider_result = provider.post(message)
                    mark_posted(result_summary, provider_result, now=now)
                    posted_keys.add(result_summary.key)
                    summary["posted"] += 1
                    post_record["provider_post_id"] = provider_result.get("id")
                except Exception as exc:
                    summary["failed"] += 1
                    post_record["error"] = str(exc)
            summary["posts"].append(post_record)

        set_state(
            SOURCE,
            "last_run",
            {
                "updated_at": iso_timestamp(now),
                "dry_run": summary["dry_run"],
                "generated": summary["generated"],
                "posted": summary["posted"],
                "skipped_duplicates": summary["skipped_duplicates"],
                "skipped_invalid": summary["skipped_invalid"],
                "failed": summary["failed"],
            },
        )
        if run_log:
            run_log.complete(
                written=summary["posted"],
                failed=summary["failed"],
                skipped=summary["skipped_duplicates"] + summary["skipped_invalid"],
                metadata={key: value for key, value in summary.items() if key != "posts"},
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate or post tournament result tweets.")
    parser.add_argument("--live", action="store_true", help="post to X/Twitter; requires RESULT_TWEETS_LIVE=1")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="maximum tournaments to inspect")
    args = parser.parse_args(argv)

    summary = post_result_tweets(live=args.live, limit=args.limit)
    mode = "LIVE" if args.live else "DRY RUN"
    print(f"Result tweets {mode}: generated={summary['generated']} posted={summary['posted']}")
    for post in summary["posts"]:
        print(f"\n[{post['key']}]")
        print(post["message"])
        if post.get("validation_issues"):
            print(f"Validation issues: {post['validation_issues']}")
        if post.get("error"):
            print(f"Post error: {post['error']}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

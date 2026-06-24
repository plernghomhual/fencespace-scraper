"""
Discover FIE competition URL IDs for tournaments that already exist in Supabase.

This fills fs_tournaments.competition_url_id so result and bout scrapers can
fetch https://fie.org/competitions/{season}/{competition_url_id}.
"""

from __future__ import annotations

import calendar
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FIE_BASE = "https://fie.org"
SOURCE = "discover_competition_urls"
REQUEST_INTERVAL_SECONDS = float(os.environ.get("FIE_DISCOVERY_REQUEST_INTERVAL", "1.0"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0; +https://fencespace.app)",
}
SEARCH_HEADERS = {
    **HEADERS,
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{FIE_BASE}/competitions",
}


@dataclass(frozen=True)
class DiscoveryResult:
    written: int = 0
    failed: int = 0
    skipped: int = 0


class RateLimiter:
    def __init__(
        self,
        min_interval: float = REQUEST_INTERVAL_SECONDS,
        time_func=time.monotonic,
        sleep_func=time.sleep,
    ):
        self.min_interval = min_interval
        self.time_func = time_func
        self.sleep_func = sleep_func
        self._last_request_at: float | None = None

    def wait(self) -> None:
        now = self.time_func()
        if self._last_request_at is not None:
            delay = self.min_interval - (now - self._last_request_at)
            if delay > 0:
                self.sleep_func(delay)
                now += delay
        self._last_request_at = now


class NoopRateLimiter:
    def wait(self) -> None:
        return None


def to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def extract_competition_url_id(url: str | None) -> str | None:
    if not url:
        return None
    segments = [part for part in urlparse(url).path.split("/") if part]
    if "competitions" not in segments or not segments:
        return None
    tail = segments[-1]
    if re.fullmatch(r"\d+", tail):
        return tail
    return None


def normalize_fie_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        day, month, year = str(date_str).split("-")
        if len(year) != 4:
            return None
        return f"{year}-{month}-{day}"
    except ValueError:
        return None


def _strip_accents(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    )


def _normalized_text(value: Any) -> str:
    text = _strip_accents(str(value or "")).lower().strip()
    return re.sub(r"\s+", " ", text)


def names_match(left: Any, right: Any) -> bool:
    a = _normalized_text(left)
    b = _normalized_text(right)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    tokens_a = set(re.split(r"\W+", a)) - {""}
    tokens_b = set(re.split(r"\W+", b)) - {""}
    if not tokens_a or not tokens_b:
        return False
    shorter = tokens_a if len(tokens_a) <= len(tokens_b) else tokens_b
    longer = tokens_b if shorter is tokens_a else tokens_a
    return len(shorter & longer) / len(shorter) >= 0.5


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _get_client():
    if supabase is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return supabase


def fetch_pending_tournaments(client, page_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table("fs_tournaments")
            .select("id,fie_id,name,season,weapon,gender,start_date")
            .is_("competition_url_id", "null")
            .not_.is_("fie_id", "null")
            .eq("has_results", True)
            .range(offset, offset + page_size - 1)
            .execute()
        ).data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def _request_get(session, url: str, rate_limiter) -> requests.Response:
    rate_limiter.wait()
    return session.get(url, allow_redirects=True, timeout=20)


def _request_post(session, url: str, payload: dict[str, Any], rate_limiter) -> requests.Response:
    rate_limiter.wait()
    return session.post(url, headers=SEARCH_HEADERS, json=payload, timeout=20)


def fetch_detail_url_id(session, season: int, candidate_id: Any, rate_limiter) -> str | None:
    candidate = str(candidate_id or "").strip()
    if not candidate:
        return None
    url = f"{FIE_BASE}/competitions/{season}/{candidate}"
    try:
        response = _request_get(session, url, rate_limiter)
    except requests.RequestException as exc:
        print(f"    Detail request failed for {url}: {exc}")
        return None
    if response.status_code != 200:
        return None
    return extract_competition_url_id(response.url)


def _month_window(start_date: str | None, season: int) -> tuple[str, str]:
    if start_date:
        try:
            year, month, _ = [int(part) for part in start_date.split("-")]
            last_day = calendar.monthrange(year, month)[1]
            return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"
        except (TypeError, ValueError):
            pass
    return f"{season}-01-01", f"{season}-12-31"


def search_competition_items(session, tournament: dict[str, Any], rate_limiter) -> list[dict[str, Any]]:
    season = to_int(tournament.get("season"))
    if season is None:
        return []
    from_date, to_date = _month_window(tournament.get("start_date"), season)
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = {
            "name": "",
            "status": "passed",
            "gender": [],
            "weapon": [],
            "type": [],
            "season": season,
            "level": "",
            "competitionCategory": "",
            "fromDate": from_date,
            "toDate": to_date,
            "fetchPage": page,
        }
        try:
            response = _request_post(session, f"{FIE_BASE}/competitions/search", payload, rate_limiter)
            if response.status_code != 200:
                break
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"    Search request failed for season={season} page={page}: {exc}")
            break

        page_items = data.get("items") or []
        if not page_items:
            break
        items.extend(page_items)

        raw_page_size = data.get("pageSize")
        page_size = max(to_int(raw_page_size) or len(page_items), 1)
        if len(page_items) < page_size or page >= 20:
            break
        page += 1
    return items


def item_matches_tournament(item: dict[str, Any], tournament: dict[str, Any]) -> bool:
    item_id = str(item.get("competitionId") or "").strip()
    tournament_fie_id = str(tournament.get("fie_id") or "").strip()
    if item_id and tournament_fie_id and item_id == tournament_fie_id:
        return True

    start_date = tournament.get("start_date")
    if start_date and normalize_fie_date(item.get("startDate")) != start_date:
        return False

    weapon = _normalized_text(tournament.get("weapon"))
    if weapon and _normalized_text(item.get("weapon")) != weapon:
        return False

    gender = _normalized_text(tournament.get("gender"))
    if gender and _normalized_text(item.get("gender")) != gender:
        return False

    name = tournament.get("name")
    if name and not names_match(item.get("name"), name):
        return False

    return bool(start_date or name or weapon or gender)


def search_candidate_ids(session, tournament: dict[str, Any], rate_limiter) -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []
    for item in search_competition_items(session, tournament, rate_limiter):
        if not item_matches_tournament(item, tournament):
            continue
        candidate = str(item.get("competitionId") or "").strip()
        if candidate and candidate not in seen:
            candidates.append(candidate)
            seen.add(candidate)
    return candidates


def discover_url_id_for_tournament(session, tournament: dict[str, Any], rate_limiter) -> str | None:
    season = to_int(tournament.get("season"))
    if season is None:
        return None

    tried: set[str] = set()
    fie_id = str(tournament.get("fie_id") or "").strip()
    if fie_id:
        tried.add(fie_id)
        direct_url_id = fetch_detail_url_id(session, season, fie_id, rate_limiter)
        if direct_url_id:
            return direct_url_id

    for candidate in search_candidate_ids(session, tournament, rate_limiter):
        if candidate in tried:
            continue
        tried.add(candidate)
        url_id = fetch_detail_url_id(session, season, candidate, rate_limiter)
        if url_id:
            return url_id
    return None


def update_tournament_url_id(client, tournament_id: Any, url_id: str) -> None:
    client.table("fs_tournaments").update({"competition_url_id": str(url_id)}).eq("id", tournament_id).execute()


def process_tournaments(client, session, tournaments: list[dict[str, Any]], rate_limiter=None) -> DiscoveryResult:
    limiter = rate_limiter or RateLimiter()
    written = failed = skipped = 0
    for tournament in tournaments:
        try:
            tournament_id = tournament.get("id")
            if not tournament_id:
                skipped += 1
                continue
            url_id = discover_url_id_for_tournament(session, tournament, limiter)
            if not url_id:
                skipped += 1
                print(f"    No URL ID found for {tournament.get('name') or tournament_id}")
                continue
            update_tournament_url_id(client, tournament_id, url_id)
            written += 1
            print(f"    Mapped {tournament.get('name') or tournament_id} -> competition_url_id={url_id}")
        except Exception as exc:
            failed += 1
            print(f"    Discovery failed for {tournament.get('id')}: {exc}")
    return DiscoveryResult(written=written, failed=failed, skipped=skipped)


def _write_state(result: DiscoveryResult) -> None:
    previous = get_state(SOURCE, "summary") or {}
    now = datetime.now(UTC).isoformat()
    set_state(
        SOURCE,
        "summary",
        {
            "completed_at": now,
            "last_completed_at": now,
            "previous_completed_at": previous.get("completed_at") or previous.get("last_completed_at"),
            "written": result.written,
            "failed": result.failed,
            "skipped": result.skipped,
        },
    )


def main(client=None, session=None, logger_factory=ScraperRunLogger, rate_limiter=None) -> DiscoveryResult:
    run_log = logger_factory(SOURCE).start()
    try:
        db = client or _get_client()
        http = session or make_session()
        limiter = rate_limiter or RateLimiter()

        tournaments = fetch_pending_tournaments(db)
        print(f"Found {len(tournaments)} tournaments missing competition_url_id")
        result = process_tournaments(db, http, tournaments, rate_limiter=limiter)
        _write_state(result)
        run_log.complete(written=result.written, failed=result.failed, skipped=result.skipped)
        print(f"Done - written={result.written}, failed={result.failed}, skipped={result.skipped}")
        return result
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

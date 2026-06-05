import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests
from supabase import Client, create_client

from run_logger import ScraperRunLogger
from scrape_bouts import (
    HEADERS,
    attach_fencer_ids,
    batch_upsert_bouts,
    extract_bouts,
    extract_window_json,
    load_fencer_map,
    parse_date,
)
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SOURCE = "live_watcher"
BATCH_SIZE = 100
ACTIVE_QUERY_LOOKBACK_DAYS = 2
ACTIVE_PROCESS_BUFFER_DAYS = 1
RESULT_CONFLICT = "tournament_id,fie_fencer_id"


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def title_case(value):
    text = clean_text(value)
    return text.title() if text else None


def normalize_country(value):
    text = clean_text(value)
    if not text:
        return None
    key = text.upper().replace(".", "")
    key = re.sub(r"\s+", " ", key)
    country_map = {
        "_AIN": "Russia",
        "AIN_": "Russia",
        "AIN": "Russia",
        "INDIVIDUAL NEUTRAL ATHLETES": "Russia",
        "FIE": "FIE",
        "USA": "United States",
        "US": "United States",
        "UNITED STATES": "United States",
        "UNITED STATES OF AMERICA": "United States",
        "GBR": "Great Britain",
        "GREAT BRITAIN": "Great Britain",
        "ITA": "Italy",
        "BRA": "Brazil",
        "KOREA": "South Korea",
        "KOR": "South Korea",
        "HONG KONG, CHINA": "Hong Kong",
        "HONG KONG CHINA": "Hong Kong",
        "MACAO, CHINA": "Macau",
        "MACAO CHINA": "Macau",
        "TURKIYE": "Turkey",
        "T\u00dcRKIYE": "Turkey",
        "T\u00dcRK\u0130YE": "Turkey",
        "COTE D'IVOIRE": "C\u00f4te d'Ivoire",
        "COTE DIVOIRE": "C\u00f4te d'Ivoire",
    }
    return country_map.get(key, title_case(text))


def normalize_person_name(value):
    text = clean_text(value)
    if not text:
        return None
    parts = text.split()
    leading = 0
    while (
        leading < len(parts)
        and any(ch.isalpha() for ch in parts[leading])
        and parts[leading].upper() == parts[leading]
    ):
        leading += 1
    if 0 < leading < len(parts):
        last = title_case(" ".join(parts[:leading]))
        first = title_case(" ".join(parts[leading:]))
        return first if first.lower() == last.lower() else f"{first} {last}"
    trailing = 0
    while (
        trailing < len(parts)
        and any(ch.isalpha() for ch in parts[-1 - trailing])
        and parts[-1 - trailing].upper() == parts[-1 - trailing]
    ):
        trailing += 1
    if 0 < trailing < len(parts):
        first = title_case(" ".join(parts[:-trailing]))
        last = title_case(" ".join(parts[-trailing:]))
        return first if first.lower() == last.lower() else f"{first} {last}"
    return title_case(text)


def to_int(value):
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except Exception:
        return None


def stable_hash(kind: str, row: dict[str, Any]) -> str:
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(f"{kind}:{encoded}".encode("utf-8")).hexdigest()


def load_hash_state(key: str) -> set[str]:
    value = get_state(SOURCE, key)
    if isinstance(value, list):
        return {str(item) for item in value}
    if isinstance(value, dict):
        hashes = value.get("hashes")
        if isinstance(hashes, list):
            return {str(item) for item in hashes}
        return {str(item) for item in value.keys()}
    return set()


def select_new_rows(rows: list[dict[str, Any]], known_hashes: set[str], kind: str):
    new_rows = []
    all_hashes = set(known_hashes)
    for row in rows:
        row_hash = stable_hash(kind, row)
        all_hashes.add(row_hash)
        if row_hash not in known_hashes:
            new_rows.append(row)
    return new_rows, all_hashes


def dedupe_result_rows(rows):
    seen = {}
    for row in rows:
        fencer_key = row.get("fie_fencer_id") or row.get("name")
        key = (row.get("tournament_id"), fencer_key, row.get("rank"))
        if key not in seen:
            seen[key] = row
    return list(seen.values())


def candidate_result_rows(window_data: dict[str, Any]) -> list[dict[str, Any]]:
    best_rows = []
    best_score = 0
    for value in window_data.values():
        if not isinstance(value, dict):
            continue
        rows = value.get("rows")
        if not isinstance(rows, list):
            continue
        score = sum(1 for row in rows if isinstance(row, dict) and row.get("name") and row.get("rank"))
        if score > best_score:
            best_rows = rows
            best_score = score
    return best_rows


def build_result_rows(tournament_id, window_data):
    result_rows = []
    for row in candidate_result_rows(window_data):
        if not isinstance(row, dict) or not row.get("name") or not row.get("rank"):
            continue
        result_rows.append(
            {
                "tournament_id": tournament_id,
                "fie_fencer_id": str(row.get("fencerId")) if row.get("fencerId") is not None else None,
                "name": normalize_person_name(row.get("name")),
                "nationality": normalize_country(row.get("nationality")),
                "country": normalize_country(row.get("country") or row.get("nationality")),
                "rank": to_int(row.get("rank")),
                "placement": to_int(row.get("rank")),
                "victory": to_int(row.get("victory")),
                "matches": to_int(row.get("matches")),
                "td": to_int(row.get("td")),
                "tr": to_int(row.get("tr")),
                "diff": to_int(row.get("diff")),
            }
        )
    return dedupe_result_rows(result_rows)


def fetch_active_tournaments(client, today_value: date):
    today_str = today_value.isoformat()
    oldest_end = (today_value - timedelta(days=ACTIVE_QUERY_LOOKBACK_DAYS)).isoformat()
    return (
        client.table("fs_tournaments")
        .select("id,name,season,start_date,end_date,competition_url_id")
        .lte("start_date", today_str)
        .gte("end_date", oldest_end)
        .not_.is_("competition_url_id", "null")
        .execute()
        .data
        or []
    )


def within_active_process_window(tournament, today_value: date) -> bool:
    start = parse_date(tournament.get("start_date"))
    end = parse_date(tournament.get("end_date"))
    if start and start > today_value:
        return False
    if end and end < today_value - timedelta(days=ACTIVE_PROCESS_BUFFER_DAYS):
        return False
    return bool(tournament.get("competition_url_id"))


def fetch_competition_page(session, season, competition_url_id):
    url = f"https://fie.org/competitions/{season}/{competition_url_id}"
    response = session.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return url, response.text


def batch_upsert_results(client, rows):
    for i in range(0, len(rows), BATCH_SIZE):
        client.table("fs_results").upsert(
            rows[i : i + BATCH_SIZE], on_conflict=RESULT_CONFLICT
        ).execute()


def upsert_new_bouts(client, bout_rows):
    if not bout_rows:
        return
    fencer_map = load_fencer_map(client, bout_rows)
    final_rows = attach_fencer_ids([row.copy() for row in bout_rows], fencer_map)
    batch_upsert_bouts(client, final_rows)


def iso_timestamp(now_value: datetime) -> str:
    if now_value.tzinfo is None:
        now_value = now_value.replace(tzinfo=timezone.utc)
    return now_value.astimezone(timezone.utc).isoformat()


def process_tournament(client, session, tournament, now_value: datetime):
    tournament_id = tournament["id"]
    last_checked_key = f"last_checked_{tournament_id}"
    result_hash_key = f"result_hashes_{tournament_id}"
    bout_hash_key = f"bout_hashes_{tournament_id}"
    last_checked = get_state(SOURCE, last_checked_key)
    season = int(tournament.get("season") or now_value.year)
    url_id = tournament.get("competition_url_id")

    url, html = fetch_competition_page(session, season, url_id)
    window_data = extract_window_json(html)
    result_rows = build_result_rows(tournament_id, window_data)
    bout_rows = extract_bouts(tournament_id, window_data)

    new_results, result_hashes = select_new_rows(
        result_rows, load_hash_state(result_hash_key), "result"
    )
    new_bouts, bout_hashes = select_new_rows(
        bout_rows, load_hash_state(bout_hash_key), "bout"
    )

    if new_results:
        batch_upsert_results(client, new_results)
        (
            client.table("fs_tournaments")
            .update({"has_results": True})
            .eq("id", tournament_id)
            .execute()
        )
    if new_bouts:
        upsert_new_bouts(client, new_bouts)

    set_state(SOURCE, result_hash_key, sorted(result_hashes))
    set_state(SOURCE, bout_hash_key, sorted(bout_hashes))
    set_state(SOURCE, last_checked_key, iso_timestamp(now_value))

    print(
        f"  Checked {tournament.get('name') or tournament_id} ({season}/{url_id}); "
        f"last_checked={last_checked or 'never'}; url={url}; "
        f"new_results={len(new_results)}; new_bouts={len(new_bouts)}"
    )
    return {
        "tournament_id": tournament_id,
        "new_results": len(new_results),
        "new_bouts": len(new_bouts),
        "skipped": 0 if result_rows or bout_rows else 1,
    }


def watch_live_results(
    client=None,
    session=None,
    today: date | None = None,
    now: datetime | None = None,
    log_run: bool = True,
    sleep_seconds: float = 0.0,
):
    now_value = now or datetime.now(timezone.utc)
    today_value = today or now_value.date()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    summary: dict[str, Any] = {
        "tournaments_checked": 0,
        "new_results": 0,
        "new_bouts": 0,
        "tournament_ids": [],
        "failed": 0,
        "skipped": 0,
    }

    try:
        client = client or get_supabase_client()
        session = session or requests.Session()
        active_tournaments = [
            tournament
            for tournament in fetch_active_tournaments(client, today_value)
            if within_active_process_window(tournament, today_value)
        ]

        if not active_tournaments:
            print("Live results watcher: no active tournaments")
            if run_log:
                run_log.complete(written=0, failed=0, skipped=0, metadata=summary)
            return summary

        for tournament in active_tournaments:
            try:
                result = process_tournament(client, session, tournament, now_value)
                summary["tournaments_checked"] += 1
                summary["new_results"] += result["new_results"]
                summary["new_bouts"] += result["new_bouts"]
                summary["skipped"] += result["skipped"]
                summary["tournament_ids"].append(result["tournament_id"])
            except Exception as exc:
                summary["failed"] += 1
                print(f"  Live watcher failed for tournament {tournament.get('id')}: {exc}")
            finally:
                if sleep_seconds:
                    time.sleep(sleep_seconds)

        print(
            "Live results watcher: "
            f"checked={summary['tournaments_checked']}; "
            f"new_results={summary['new_results']}; "
            f"new_bouts={summary['new_bouts']}; "
            f"tournament_ids={summary['tournament_ids']}"
        )
        if run_log:
            run_log.complete(
                written=summary["new_results"] + summary["new_bouts"],
                failed=summary["failed"],
                skipped=summary["skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main():
    watch_live_results()


if __name__ == "__main__":
    main()

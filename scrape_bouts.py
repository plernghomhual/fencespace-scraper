import json
import os
import re
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone

import requests
from supabase import Client, create_client

from run_logger import ScraperRunLogger


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BATCH_SIZE = 100
PAGE_SIZE = 1000
RECENT_DAYS = 14
RATE_LIMIT_SECONDS = 2


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def extract_js_value(source, start):
    i = start
    while i < len(source) and source[i].isspace():
        i += 1
    if i >= len(source):
        return ""

    opening = source[i]
    pairs = {"{": "}", "[": "]"}
    if opening in pairs:
        stack = []
        in_string = False
        quote = ""
        escaped = False
        for j in range(i, len(source)):
            ch = source[j]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == quote:
                    in_string = False
            else:
                if ch in ("'", '"'):
                    in_string = True
                    quote = ch
                elif ch in pairs:
                    stack.append(pairs[ch])
                elif stack and ch == stack[-1]:
                    stack.pop()
                    if not stack:
                        return source[i : j + 1]
        return source[i:]

    end = source.find(";", i)
    return source[i : end if end != -1 else len(source)]


def extract_window_json(html):
    blocks = {}
    for match in re.finditer(r"window\.([A-Za-z0-9_$]+)\s*=\s*", html):
        key = match.group(1)
        raw = extract_js_value(html, match.end())
        try:
            blocks[key] = json.loads(raw)
        except Exception:
            continue
    return blocks


def fetch_competition_page(session, season, competition_url_id):
    url = f"https://fie.org/competitions/{season}/{competition_url_id}"
    response = session.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return url, response.text


def to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except Exception:
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def normalize_fie_id(value):
    if value is None or value == "":
        return None
    try:
        return str(int(float(value)))
    except Exception:
        text = str(value).strip()
        return text or None


def parse_date(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        return None


def is_recent_tournament(tournament):
    end_date = parse_date(tournament.get("end_date"))
    if not end_date:
        return False
    today = datetime.now(timezone.utc).date()
    return end_date >= today - timedelta(days=RECENT_DAYS)


def make_bout_id(tournament_id, source_key):
    seed = f"fencespace:fie-bout:{tournament_id}:{source_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def make_tableau_round_lookup(competition):
    lookup = {}
    for item in (competition or {}).get("tableauList") or []:
        suite_id = item.get("suiteTableId") or ""
        table_id = item.get("tableId") or ""
        name = item.get("name") or table_id
        if table_id:
            lookup[(suite_id, table_id)] = name
            lookup[("", table_id)] = name
    return lookup


def tableau_round_name(round_lookup, suite_id, round_key):
    name = round_lookup.get((suite_id or "", round_key)) or round_lookup.get(
        ("", round_key)
    )
    if not name:
        return round_key
    return f"{name} ({round_key})" if round_key not in name else name


def build_bout_row(
    tournament_id,
    source_key,
    round_name,
    fencer_a,
    fencer_b,
    score_a,
    score_b,
    winner_id,
):
    fie_id_a = normalize_fie_id(fencer_a)
    fie_id_b = normalize_fie_id(fencer_b)
    if not fie_id_a or not fie_id_b:
        return None

    score_a = to_int(score_a)
    score_b = to_int(score_b)
    if score_a is None and score_b is None:
        return None

    winner = normalize_fie_id(winner_id)
    if not winner and score_a is not None and score_b is not None and score_a != score_b:
        winner = fie_id_a if score_a > score_b else fie_id_b

    return {
        "id": make_bout_id(tournament_id, source_key),
        "tournament_id": tournament_id,
        "fie_fencer_id_a": fie_id_a,
        "fie_fencer_id_b": fie_id_b,
        "score_a": score_a,
        "score_b": score_b,
        "round": round_name,
        "_winner_fie_id": winner,
    }


def extract_tableau_bouts(tournament_id, window_data):
    tableau = window_data.get("_tableau") or window_data.get("_matches") or []
    if not isinstance(tableau, list):
        return []

    round_lookup = make_tableau_round_lookup(window_data.get("_competition"))
    rows = []
    for table_index, table in enumerate(tableau):
        if not isinstance(table, dict):
            continue
        suite_id = table.get("suiteTableId") or f"table_{table_index}"
        rounds = table.get("rounds") or {}
        if not isinstance(rounds, dict):
            continue

        for round_key, bouts in rounds.items():
            if not isinstance(bouts, list):
                continue
            round_name = tableau_round_name(round_lookup, suite_id, str(round_key))
            for bout_index, bout in enumerate(bouts):
                if not isinstance(bout, dict) or bout.get("isBye"):
                    continue

                fencer_a = bout.get("fencer1") or bout.get("fencerA") or {}
                fencer_b = bout.get("fencer2") or bout.get("fencerB") or {}
                if not isinstance(fencer_a, dict) or not isinstance(fencer_b, dict):
                    continue

                id_a = normalize_fie_id(fencer_a.get("id") or fencer_a.get("fencerId"))
                id_b = normalize_fie_id(fencer_b.get("id") or fencer_b.get("fencerId"))
                winner_id = None
                if fencer_a.get("isWinner") is True:
                    winner_id = id_a
                elif fencer_b.get("isWinner") is True:
                    winner_id = id_b

                source_key = f"tableau:{suite_id}:{round_key}:{bout_index}:{id_a}:{id_b}"
                row = build_bout_row(
                    tournament_id,
                    source_key,
                    round_name,
                    id_a,
                    id_b,
                    fencer_a.get("score"),
                    fencer_b.get("score"),
                    winner_id,
                )
                if row:
                    rows.append(row)
    return rows


def extract_pool_bouts(tournament_id, window_data):
    pool_data = window_data.get("_pools") or window_data.get("_poules") or {}
    pools = pool_data.get("pools") if isinstance(pool_data, dict) else pool_data
    if not isinstance(pools, list):
        return []

    rows = []
    for pool_index, pool in enumerate(pools):
        if not isinstance(pool, dict):
            continue
        pool_id = pool.get("poolId") or pool.get("id") or pool_index + 1
        fencers = pool.get("rows") or []
        if not isinstance(fencers, list):
            continue

        round_name = f"Pool {pool_id}"
        for i, fencer_a in enumerate(fencers):
            if not isinstance(fencer_a, dict):
                continue
            matches_a = fencer_a.get("matches") or []
            if not isinstance(matches_a, list):
                continue

            for j in range(i + 1, len(fencers)):
                fencer_b = fencers[j]
                if not isinstance(fencer_b, dict):
                    continue
                matches_b = fencer_b.get("matches") or []
                match_a = matches_a[j] if j < len(matches_a) else None
                match_b = matches_b[i] if isinstance(matches_b, list) and i < len(matches_b) else None
                if not isinstance(match_a, dict) or not isinstance(match_b, dict):
                    continue

                id_a = normalize_fie_id(fencer_a.get("fencerId") or fencer_a.get("id"))
                id_b = normalize_fie_id(fencer_b.get("fencerId") or fencer_b.get("id"))
                winner_id = None
                if match_a.get("v") is True:
                    winner_id = id_a
                elif match_b.get("v") is True:
                    winner_id = id_b

                source_key = f"pool:{pool_id}:{i}:{j}:{id_a}:{id_b}"
                row = build_bout_row(
                    tournament_id,
                    source_key,
                    round_name,
                    id_a,
                    id_b,
                    match_a.get("score"),
                    match_b.get("score"),
                    winner_id,
                )
                if row:
                    rows.append(row)
    return rows


def extract_bouts(tournament_id, window_data):
    bouts = extract_pool_bouts(tournament_id, window_data)
    bouts.extend(extract_tableau_bouts(tournament_id, window_data))

    deduped = {}
    for row in bouts:
        deduped[row["id"]] = row
    return list(deduped.values())


def fetch_all_tournaments(supabase):
    tournaments = []
    offset = 0
    while True:
        page = (
            supabase.table("fs_tournaments")
            .select("id,name,season,competition_url_id,end_date")
            .not_.is_("competition_url_id", "null")
            .eq("has_results", True)
            .order("end_date", desc=True)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        tournaments.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return tournaments


def fetch_existing_bout_tournament_ids(supabase):
    tournament_ids = set()
    offset = 0
    while True:
        page = (
            supabase.table("fs_bouts")
            .select("tournament_id")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        for row in page:
            if row.get("tournament_id"):
                tournament_ids.add(row["tournament_id"])
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return tournament_ids


def load_fencer_map(supabase, bout_rows):
    fie_ids = sorted(
        {
            value
            for row in bout_rows
            for value in (row.get("fie_fencer_id_a"), row.get("fie_fencer_id_b"))
            if value
        }
    )
    fencer_map = {}
    for i in range(0, len(fie_ids), BATCH_SIZE):
        batch = fie_ids[i : i + BATCH_SIZE]
        data = (
            supabase.table("fs_fencers")
            .select("id,fie_id")
            .in_("fie_id", batch)
            .execute()
            .data
            or []
        )
        for fencer in data:
            fie_id = normalize_fie_id(fencer.get("fie_id"))
            if fie_id and fie_id not in fencer_map:
                fencer_map[fie_id] = fencer.get("id")
    return fencer_map


def attach_fencer_ids(bout_rows, fencer_map):
    for row in bout_rows:
        winner_fie_id = row.pop("_winner_fie_id", None)
        row["fencer_a"] = fencer_map.get(row.pop("fie_fencer_id_a", None))
        row["fencer_b"] = fencer_map.get(row.pop("fie_fencer_id_b", None))
        row["winner"] = fencer_map.get(winner_fie_id) if winner_fie_id else None
    return bout_rows


def strip_generated_ids(rows):
    return [{key: value for key, value in row.items() if key != "id"} for row in rows]


def batch_upsert_bouts(supabase, rows):
    try:
        for i in range(0, len(rows), BATCH_SIZE):
            supabase.table("fs_bouts").upsert(
                rows[i : i + BATCH_SIZE], on_conflict="id"
            ).execute()
    except Exception as exc:
        message = str(exc).lower()
        if "id" not in message or (
            "invalid input syntax" not in message
            and "type integer" not in message
            and "type bigint" not in message
        ):
            raise

        print("  fs_bouts.id rejected generated UUIDs; retrying with database IDs")
        fallback_rows = strip_generated_ids(rows)
        for i in range(0, len(fallback_rows), BATCH_SIZE):
            supabase.table("fs_bouts").upsert(
                fallback_rows[i : i + BATCH_SIZE]
            ).execute()


def scrape_bouts():
    print(f"Bout scraper starting - {datetime.now(timezone.utc).isoformat()}")
    run_log = ScraperRunLogger("scrape_bouts").start()
    supabase = get_supabase_client()
    session = requests.Session()
    session.headers.update(HEADERS)

    tournaments = fetch_all_tournaments(supabase)
    existing_bout_ids = fetch_existing_bout_tournament_ids(supabase)
    print(f"Found {len(tournaments)} tournaments with results and FIE URL IDs")
    print(f"Found existing bouts for {len(existing_bout_ids)} tournaments")

    scraped = 0
    skipped = 0
    no_bouts = 0
    failed = 0

    for index, tournament in enumerate(tournaments, start=1):
        tournament_id = tournament["id"]
        name = tournament.get("name") or tournament_id
        season = tournament.get("season") or datetime.now(timezone.utc).year
        url_id = tournament.get("competition_url_id")
        recent = is_recent_tournament(tournament)

        if tournament_id in existing_bout_ids and not recent:
            print(f"[{index}/{len(tournaments)}] Skipping {name} - bouts already exist")
            skipped += 1
            continue

        print(f"[{index}/{len(tournaments)}] Scraping {name} ({season}/{url_id})")
        try:
            url, html = fetch_competition_page(session, season, url_id)
            window_data = extract_window_json(html)
            print(f"  Fetched {url}; window keys: {', '.join(window_data.keys()) or 'none'}")

            bout_rows = extract_bouts(tournament_id, window_data)
            if not bout_rows:
                print("  No bout data found")
                no_bouts += 1
                continue

            if tournament_id in existing_bout_ids and recent:
                print("  Recent tournament: deleting existing bouts before reload")
                supabase.table("fs_bouts").delete().eq("tournament_id", tournament_id).execute()

            fencer_map = load_fencer_map(supabase, bout_rows)
            unmatched = sorted(
                {
                    value
                    for row in bout_rows
                    for value in (row["fie_fencer_id_a"], row["fie_fencer_id_b"])
                    if value and value not in fencer_map
                }
            )
            final_rows = attach_fencer_ids(bout_rows, fencer_map)
            batch_upsert_bouts(supabase, final_rows)

            print(
                f"  Upserted {len(final_rows)} bouts; "
                f"matched {len(fencer_map)} FIE IDs; unmatched {len(unmatched)}"
            )
            scraped += 1
            existing_bout_ids.add(tournament_id)
        except Exception as exc:
            print(f"  Error scraping tournament {tournament_id}: {exc}")
            traceback.print_exc()
            failed += 1
        finally:
            time.sleep(RATE_LIMIT_SECONDS)

    run_log.complete(written=scraped, failed=failed, skipped=skipped + no_bouts)
    print(
        "\nDone - "
        f"{scraped} tournaments scraped, {skipped} skipped, "
        f"{no_bouts} with no bouts, {failed} failed"
    )


if __name__ == "__main__":
    scrape_bouts()

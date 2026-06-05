"""
Import FIE individual pool bouts into fs_bouts.

The current FIE result pages expose pool data as inline window._pools/window._poules
payloads on https://fie.org/competitions/{season}/{competition_url_id}. This
scraper parses only pool bouts and deliberately ignores tableau payloads so it
does not duplicate elimination bouts.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from supabase import Client, create_client

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

try:
    from scripts.rate_limiter import RateLimiter as _RateLimiter

    _fie_limiter = _RateLimiter(default_rps=0.5, jitter=0.2, backoff=5.0)
except ImportError:  # pragma: no cover - local tests run without this branch
    _fie_limiter = None


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "scrape_fie_pools"
FIE_BASE = "https://fie.org"
BATCH_SIZE = 100
PAGE_SIZE = 1000
RATE_LIMIT_SECONDS = 2.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FenceSpace/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

WITHDRAWAL_MARKERS = {
    "A",
    "AB",
    "ABS",
    "ABSENT",
    "DNS",
    "DSQ",
    "EXC",
    "EXCL",
    "F",
    "FOR",
    "FORF",
    "FORFEIT",
    "WD",
    "W/D",
    "WO",
    "W/O",
}

FS_BOUT_COLUMNS = {
    "id",
    "tournament_id",
    "fencer_a_id",
    "fencer_b_id",
    "score_a",
    "score_b",
    "round",
    "winner_id",
}


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_fie_id(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        return str(int(float(value)))
    except Exception:
        text = clean_text(value)
        return text


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return text.upper() if len(text) <= 4 else text


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(float(value))
    except Exception:
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def parse_score(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    if text.upper() in WITHDRAWAL_MARKERS:
        return None
    return to_int(text)


def boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "v", "victory", "win", "winner"}:
        return True
    if text in {"0", "false", "no", "n", "d", "defeat", "loss"}:
        return False
    return None


def make_bout_id(tournament_id: Any, source_key: str) -> str:
    seed = f"fencespace:fie-bout:{tournament_id}:{source_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def extract_js_value(source: str, start: int) -> str:
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


def extract_window_json(html: str) -> dict[str, Any]:
    blocks: dict[str, Any] = {}
    for match in re.finditer(r"window\.([A-Za-z0-9_$]+)\s*=\s*", html or ""):
        key = match.group(1)
        raw = extract_js_value(html, match.end())
        try:
            blocks[key] = json.loads(raw)
        except Exception:
            continue
    return blocks


def is_team_competition(window_data: dict[str, Any], tournament: dict[str, Any] | None = None) -> bool:
    tournament = tournament or {}
    if tournament.get("is_team") is True:
        return True
    competition = window_data.get("_competition") or {}
    values = [
        tournament.get("name"),
        tournament.get("type"),
        competition.get("name") if isinstance(competition, dict) else None,
        competition.get("type") if isinstance(competition, dict) else None,
        competition.get("competitionType") if isinstance(competition, dict) else None,
    ]
    text = " ".join(clean_text(value) or "" for value in values).lower()
    return bool(re.search(r"\b(team|teams|equipe|équipes|equipes|par equipes)\b", text))


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def iter_pool_rounds(window_data: dict[str, Any]) -> list[dict[str, Any]]:
    pool_data = window_data.get("_pools") or window_data.get("_poules") or {}
    rounds: list[dict[str, Any]] = []

    def add_round(round_obj: Any, fallback_name: str = "Pools", fallback_key: str = "") -> None:
        if isinstance(round_obj, dict):
            pools = round_obj.get("pools") or round_obj.get("poules") or round_obj.get("items")
            if pools is None and isinstance(round_obj.get("rows"), list):
                pools = [round_obj]
            if isinstance(pools, dict):
                pools = list(pools.values())
            if isinstance(pools, list):
                rounds.append(
                    {
                        "name": clean_text(round_obj.get("name") or round_obj.get("label")) or fallback_name,
                        "key": clean_text(
                            round_obj.get("roundId")
                            or round_obj.get("round")
                            or round_obj.get("id")
                            or fallback_key
                        )
                        or "",
                        "pools": pools,
                    }
                )
        elif isinstance(round_obj, list):
            rounds.append({"name": fallback_name, "key": fallback_key, "pools": round_obj})

    if isinstance(pool_data, dict):
        nested_rounds = pool_data.get("rounds") or pool_data.get("tourList") or pool_data.get("stages")
        if nested_rounds:
            for index, item in enumerate(_as_list(nested_rounds), start=1):
                add_round(item, fallback_name=f"Pools Round {index}", fallback_key=str(index))
        else:
            add_round(pool_data)
    elif isinstance(pool_data, list):
        if any(isinstance(item, dict) and ("pools" in item or "poules" in item) for item in pool_data):
            for index, item in enumerate(pool_data, start=1):
                add_round(item, fallback_name=f"Pools Round {index}", fallback_key=str(index))
        else:
            add_round(pool_data)

    return [round_item for round_item in rounds if isinstance(round_item.get("pools"), list)]


def fencer_info(row: dict[str, Any]) -> dict[str, str | None]:
    nested = row.get("fencer") if isinstance(row.get("fencer"), dict) else {}
    nested = nested or {}
    merged = {**nested, **row}

    first = clean_text(merged.get("firstName") or merged.get("firstname") or merged.get("first_name"))
    last = clean_text(merged.get("lastName") or merged.get("lastname") or merged.get("last_name"))
    name = clean_text(
        merged.get("name")
        or merged.get("fullName")
        or merged.get("displayName")
        or merged.get("athleteName")
    )
    if not name and (first or last):
        name = " ".join(part for part in (last, first) if part)

    return {
        "fie_id": normalize_fie_id(
            merged.get("fencerId")
            or merged.get("fieId")
            or merged.get("fie_id")
            or merged.get("id")
            or merged.get("athleteId")
        ),
        "name": name,
        "country": normalize_country(
            merged.get("country")
            or merged.get("countryCode")
            or merged.get("nationality")
            or merged.get("nation")
            or merged.get("federation")
        ),
    }


def match_cell(row: dict[str, Any], opponent_index: int) -> dict[str, Any] | None:
    matches = row.get("matches") or row.get("bouts") or row.get("matchs") or []
    if isinstance(matches, dict):
        for key in (str(opponent_index), str(opponent_index + 1), opponent_index):
            value = matches.get(key)
            if isinstance(value, dict):
                return value
        return None
    if isinstance(matches, list) and opponent_index < len(matches):
        value = matches[opponent_index]
        return value if isinstance(value, dict) else None
    return None


def cell_score(cell: dict[str, Any] | None) -> int | None:
    if not isinstance(cell, dict):
        return None
    return parse_score(
        cell.get("score")
        if "score" in cell
        else cell.get("touches")
        if "touches" in cell
        else cell.get("result")
        if "result" in cell
        else cell.get("value")
    )


def cell_victory(cell: dict[str, Any] | None) -> bool | None:
    if not isinstance(cell, dict):
        return None
    for key in ("v", "victory", "isVictory", "winner", "win"):
        marker = boolish(cell.get(key))
        if marker is not None:
            return marker
    score_text = clean_text(cell.get("score") or cell.get("result") or cell.get("value"))
    if score_text and re.match(r"^V(?:\d+)?$", score_text.strip(), flags=re.I):
        return True
    return None


def cell_priority(cell: dict[str, Any] | None) -> bool:
    if not isinstance(cell, dict):
        return False
    for key in ("priority", "priorityWinner", "hasPriority", "p"):
        if boolish(cell.get(key)) is True:
            return True
    text = clean_text(cell.get("score") or cell.get("result") or cell.get("value")) or ""
    return bool(re.search(r"\bP\b", text, flags=re.I))


def cell_withdrawal(cell: dict[str, Any] | None) -> bool:
    if not isinstance(cell, dict):
        return False
    for key in ("withdrawn", "withdrawal", "abandoned", "abandon", "forfeit", "forfeited", "excluded"):
        if boolish(cell.get(key)) is True:
            return True
    text = clean_text(cell.get("score") or cell.get("result") or cell.get("value")) or ""
    return text.upper() in WITHDRAWAL_MARKERS


def cell_bout_order(cell_a: dict[str, Any] | None, cell_b: dict[str, Any] | None) -> int | None:
    for cell in (cell_a, cell_b):
        if not isinstance(cell, dict):
            continue
        for key in ("boutOrder", "bout_order", "order", "matchOrder", "matchNo", "boutNumber", "number"):
            order = to_int(cell.get(key))
            if order is not None:
                return order
    return None


def source_key_for_pool_bout(
    round_key: str,
    pool_id: Any,
    row_a_index: int,
    row_b_index: int,
    fencer_a_fie_id: str | None,
    fencer_b_fie_id: str | None,
) -> str:
    base = f"pool:{pool_id}:{row_a_index}:{row_b_index}:{fencer_a_fie_id}:{fencer_b_fie_id}"
    normalized_round = (round_key or "").strip().lower()
    if normalized_round in {"", "pool", "pools", "poule", "poules"}:
        return base
    return f"pool:{round_key}:{pool_id}:{row_a_index}:{row_b_index}:{fencer_a_fie_id}:{fencer_b_fie_id}"


def pool_id_for(pool: dict[str, Any], fallback: int) -> str:
    return str(
        clean_text(
            pool.get("poolId")
            or pool.get("pouleId")
            or pool.get("number")
            or pool.get("poolNumber")
            or pool.get("id")
            or fallback
        )
    )


def parse_pool_bouts(
    tournament_id: Any,
    window_data: dict[str, Any],
    source_url: str,
    tournament: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if is_team_competition(window_data, tournament):
        return []

    parsed: dict[str, dict[str, Any]] = {}
    for round_item in iter_pool_rounds(window_data):
        round_name = clean_text(round_item.get("name")) or "Pools"
        round_key = clean_text(round_item.get("key")) or ""
        for pool_index, pool in enumerate(round_item["pools"], start=1):
            if not isinstance(pool, dict):
                continue
            fencer_rows = pool.get("rows") or pool.get("fencers") or pool.get("athletes") or []
            if not isinstance(fencer_rows, list) or len(fencer_rows) < 2:
                continue

            poule_number = pool_id_for(pool, pool_index)
            display_round = f"{round_name} - Pool {poule_number}" if round_name else f"Pool {poule_number}"
            for i, row_a in enumerate(fencer_rows):
                if not isinstance(row_a, dict):
                    continue
                info_a = fencer_info(row_a)
                for j in range(i + 1, len(fencer_rows)):
                    row_b = fencer_rows[j]
                    if not isinstance(row_b, dict):
                        continue
                    info_b = fencer_info(row_b)
                    if not info_a["fie_id"] or not info_b["fie_id"]:
                        continue

                    match_a = match_cell(row_a, j)
                    match_b = match_cell(row_b, i)
                    score_a = cell_score(match_a)
                    score_b = cell_score(match_b)
                    victory_a = cell_victory(match_a)
                    victory_b = cell_victory(match_b)
                    withdrawal_a = cell_withdrawal(match_a)
                    withdrawal_b = cell_withdrawal(match_b)

                    winner_fie_id = None
                    if victory_a is True:
                        winner_fie_id = info_a["fie_id"]
                    elif victory_b is True:
                        winner_fie_id = info_b["fie_id"]
                    elif score_a is not None and score_b is not None and score_a != score_b:
                        winner_fie_id = info_a["fie_id"] if score_a > score_b else info_b["fie_id"]

                    if (
                        score_a is None
                        and score_b is None
                        and not winner_fie_id
                        and not withdrawal_a
                        and not withdrawal_b
                    ):
                        continue

                    source_key = source_key_for_pool_bout(
                        round_key,
                        poule_number,
                        i,
                        j,
                        info_a["fie_id"],
                        info_b["fie_id"],
                    )
                    parsed[source_key] = {
                        "id": make_bout_id(tournament_id, source_key),
                        "source_key": source_key,
                        "source_url": source_url,
                        "tournament_id": tournament_id,
                        "pool_round": round_name,
                        "poule_number": poule_number,
                        "bout_order": cell_bout_order(match_a, match_b),
                        "round": display_round,
                        "fencer_a_fie_id": info_a["fie_id"],
                        "fencer_a_name": info_a["name"],
                        "country_a": info_a["country"],
                        "fencer_b_fie_id": info_b["fie_id"],
                        "fencer_b_name": info_b["name"],
                        "country_b": info_b["country"],
                        "score_a": score_a,
                        "score_b": score_b,
                        "victory_a": victory_a is True,
                        "victory_b": victory_b is True,
                        "winner_fie_id": winner_fie_id,
                        "priority_a": cell_priority(match_a),
                        "priority_b": cell_priority(match_b),
                        "withdrawal_a": withdrawal_a,
                        "withdrawal_b": withdrawal_b,
                    }

    return sorted(
        parsed.values(),
        key=lambda row: (
            row.get("pool_round") or "",
            row.get("poule_number") or "",
            row.get("bout_order") is None,
            row.get("bout_order") or 0,
            row.get("source_key") or "",
        ),
    )


def parse_pool_bouts_from_html(tournament_id: Any, html: str, source_url: str) -> list[dict[str, Any]]:
    return parse_pool_bouts(tournament_id, extract_window_json(html), source_url)


def fetch_competition_page(session: requests.Session, tournament: dict[str, Any]) -> tuple[str, str]:
    season = tournament.get("season") or datetime.now(timezone.utc).year
    competition_url_id = tournament.get("competition_url_id") or tournament.get("fie_id")
    url = f"{FIE_BASE}/competitions/{season}/{competition_url_id}"
    response = session.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return url, response.text


def fetch_pool_tournaments(client: Client, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table("fs_tournaments")
            .select("id,fie_id,name,season,competition_url_id,end_date,has_results,type")
            .not_.is_("competition_url_id", "null")
            .eq("has_results", True)
            .order("end_date", desc=True)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if limit and len(rows) >= limit:
            return rows[:limit]
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def should_skip_tournament(tournament: dict[str, Any]) -> bool:
    if not tournament.get("competition_url_id") and not tournament.get("fie_id"):
        return True
    if tournament.get("has_results") is False:
        return True
    return is_team_competition({}, tournament)


def load_fie_id_map(client: Client, parsed_bouts: list[dict[str, Any]]) -> dict[str, str]:
    fie_ids = sorted(
        {
            fie_id
            for bout in parsed_bouts
            for fie_id in (bout.get("fencer_a_fie_id"), bout.get("fencer_b_fie_id"))
            if fie_id
        }
    )
    fencer_map: dict[str, str] = {}
    for i in range(0, len(fie_ids), BATCH_SIZE):
        batch = fie_ids[i : i + BATCH_SIZE]
        data = (
            client.table("fs_fencers")
            .select("id,fie_id,name,country")
            .in_("fie_id", batch)
            .execute()
            .data
            or []
        )
        for row in data:
            fie_id = normalize_fie_id(row.get("fie_id"))
            if fie_id and row.get("id") and fie_id not in fencer_map:
                fencer_map[fie_id] = row["id"]
    return fencer_map


def find_fencer_by_name_country(
    client: Client,
    name: str | None,
    country: str | None,
    cache: dict[tuple[str, str], str | None],
) -> str | None:
    if not name or not country:
        return None
    key = (name, country)
    if key in cache:
        return cache[key]
    data = (
        client.table("fs_fencers")
        .select("id,fie_id,name,country")
        .ilike("name", name)
        .eq("country", country)
        .limit(1)
        .execute()
        .data
        or []
    )
    cache[key] = data[0].get("id") if data else None
    return cache[key]


def format_unmatched(name: str | None, country: str | None, fie_id: str | None) -> str:
    display_name = name or "Unknown"
    bits = []
    if country:
        bits.append(country)
    if fie_id:
        bits.append(f"FIE {fie_id}")
    return f"{display_name} ({', '.join(bits)})" if bits else display_name


def resolve_fencer_id(
    client: Client,
    fie_id_map: dict[str, str],
    name_cache: dict[tuple[str, str], str | None],
    fie_id: str | None,
    name: str | None,
    country: str | None,
) -> str | None:
    if fie_id and fie_id in fie_id_map:
        return fie_id_map[fie_id]
    return find_fencer_by_name_country(client, name, country, name_cache)


def db_rows_for_pool_bouts(
    client: Client,
    parsed_bouts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    fie_id_map = load_fie_id_map(client, parsed_bouts)
    name_cache: dict[tuple[str, str], str | None] = {}
    rows: list[dict[str, Any]] = []
    unmatched: set[str] = set()

    for bout in parsed_bouts:
        fencer_a_id = resolve_fencer_id(
            client,
            fie_id_map,
            name_cache,
            bout.get("fencer_a_fie_id"),
            bout.get("fencer_a_name"),
            bout.get("country_a"),
        )
        fencer_b_id = resolve_fencer_id(
            client,
            fie_id_map,
            name_cache,
            bout.get("fencer_b_fie_id"),
            bout.get("fencer_b_name"),
            bout.get("country_b"),
        )
        if not fencer_a_id:
            unmatched.add(
                format_unmatched(bout.get("fencer_a_name"), bout.get("country_a"), bout.get("fencer_a_fie_id"))
            )
        if not fencer_b_id:
            unmatched.add(
                format_unmatched(bout.get("fencer_b_name"), bout.get("country_b"), bout.get("fencer_b_fie_id"))
            )

        winner_id = None
        if bout.get("winner_fie_id") == bout.get("fencer_a_fie_id"):
            winner_id = fencer_a_id
        elif bout.get("winner_fie_id") == bout.get("fencer_b_fie_id"):
            winner_id = fencer_b_id

        row = {
            "id": bout["id"],
            "tournament_id": bout["tournament_id"],
            "fencer_a_id": fencer_a_id,
            "fencer_b_id": fencer_b_id,
            "score_a": bout.get("score_a"),
            "score_b": bout.get("score_b"),
            "round": bout.get("round"),
            "winner_id": winner_id,
        }
        rows.append({key: value for key, value in row.items() if key in FS_BOUT_COLUMNS})

    deduped = {row["id"]: row for row in rows}
    return list(deduped.values()), sorted(unmatched)


def strip_generated_ids(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if key != "id"} for row in rows]


def batch_upsert_bouts(client: Client, rows: list[dict[str, Any]]) -> None:
    try:
        for i in range(0, len(rows), BATCH_SIZE):
            client.table("fs_bouts").upsert(rows[i : i + BATCH_SIZE], on_conflict="id").execute()
    except Exception as exc:
        message = str(exc).lower()
        if "id" not in message or (
            "invalid input syntax" not in message
            and "type integer" not in message
            and "type bigint" not in message
        ):
            raise
        fallback_rows = strip_generated_ids(rows)
        for i in range(0, len(fallback_rows), BATCH_SIZE):
            client.table("fs_bouts").upsert(fallback_rows[i : i + BATCH_SIZE]).execute()


def write_pool_bouts(client: Client, parsed_bouts: list[dict[str, Any]]) -> tuple[int, list[str]]:
    if not parsed_bouts:
        return 0, []
    rows, unmatched = db_rows_for_pool_bouts(client, parsed_bouts)
    if unmatched:
        print(f"Unmatched FIE pool fencers: {', '.join(unmatched[:20])}")
    if rows:
        batch_upsert_bouts(client, rows)
    return len(rows), unmatched


def scrape_fie_pools(limit: int | None = None) -> dict[str, Any]:
    run_log = ScraperRunLogger(SOURCE).start()
    client = get_supabase_client()
    session = requests.Session()
    session.headers.update(HEADERS)

    previous_state = get_state(SOURCE, "last_run") or {}
    print(f"FIE pool scraper starting - {datetime.now(timezone.utc).isoformat()}")
    if previous_state:
        print(f"Previous state: {previous_state}")

    written = 0
    failed = 0
    skipped = 0
    parsed_tournaments = 0
    try:
        tournaments = fetch_pool_tournaments(client, limit=limit)
        for tournament in tournaments:
            name = tournament.get("name") or tournament.get("id")
            if should_skip_tournament(tournament):
                skipped += 1
                continue
            try:
                if _fie_limiter:
                    _fie_limiter.wait("fie.org")
                else:
                    time.sleep(RATE_LIMIT_SECONDS)
                source_url, html = fetch_competition_page(session, tournament)
                window_data = extract_window_json(html)
                parsed = parse_pool_bouts(tournament["id"], window_data, source_url, tournament=tournament)
                if not parsed:
                    skipped += 1
                    print(f"  [{name}] No individual pool bouts found")
                    continue
                count, _unmatched = write_pool_bouts(client, parsed)
                written += count
                parsed_tournaments += 1
                print(f"  [{name}] Upserted {count} pool bouts from {source_url}")
                if _fie_limiter:
                    _fie_limiter.record_success("fie.org")
            except Exception as exc:
                failed += 1
                print(f"  [{name}] Failed: {exc}")
                if _fie_limiter:
                    _fie_limiter.record_failure("fie.org")

        state = {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "parsed_tournaments": parsed_tournaments,
        }
        set_state(SOURCE, "last_run", state)
        run_log.complete(written=written, failed=failed, skipped=skipped)
        return state
    except Exception as exc:
        run_log.error(str(exc))
        raise


def main() -> None:
    limit = to_int(os.environ.get("FIE_POOLS_LIMIT"))
    scrape_fie_pools(limit=limit)


if __name__ == "__main__":
    main()

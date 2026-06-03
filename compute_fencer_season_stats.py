from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from season_utils import normalize_season, season_from_string


MODULE_NAME = "compute_fencer_season_stats"
PAGE_SIZE = 1000
BATCH_SIZE = 100
SEASON_STATS_TABLE = "fs_fencer_season_stats"
SEASON_STATS_CONFLICT_COLUMNS = "fencer_id,season,weapon,gender,category,source_confidence"

RESULT_SELECTS = [
    "id,tournament_id,fencer_id,fie_fencer_id,season,weapon,gender,category,rank,placement,medal,source_confidence,confidence,metadata,date",
    "id,tournament_id,fencer_id,fie_fencer_id,season,weapon,gender,category,rank,placement,medal,date",
    "id,tournament_id,fencer_id,rank,placement,medal",
]
TOURNAMENT_SELECTS = [
    "id,season,weapon,gender,category,start_date,end_date,date,source_confidence,confidence,metadata",
    "id,season,weapon,gender,category,start_date,end_date,date",
    "id,season,weapon,gender,category",
]
BOUT_SELECTS = [
    "id,tournament_id,fencer_a,fencer_b,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,season,weapon,gender,category,source_confidence,confidence,metadata,bout_date,meeting_date,date,played_at,completed_at",
    "id,tournament_id,fencer_a,fencer_b,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,weapon,category,gender",
    "id,tournament_id,fencer_a,fencer_b,score_a,score_b",
]
IDENTITY_SELECTS = [
    "id,canonical_id,fs_fencer_row_ids,fencer_ids,fie_ids",
    "id,canonical_id,fs_fencer_row_ids,fie_ids",
    "id,fs_fencer_row_ids,fie_ids",
    "canonical_id,fencer_ids",
]


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(url, key)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    ).casefold()


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def positive_int(value: Any) -> int | None:
    number = to_int(value)
    return number if number is not None and number > 0 else None


def round_float(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    quant = Decimal("1").scaleb(-digits)
    rounded = Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP)
    return float(rounded)


def normalize_stat_season(raw: Any) -> str:
    if isinstance(raw, bool):
        raise TypeError("season must be an integer year or string")
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    if isinstance(raw, str):
        text = clean_text(raw)
        if not text:
            raise ValueError("season is empty")
        slash_range = re.fullmatch(r"(\d{4})\s*/\s*(\d{4})", text)
        if slash_range:
            text = f"{slash_range.group(1)}-{slash_range.group(2)}"
        short_range = re.fullmatch(r"(\d{4})\s*[-/]\s*(\d{2})", text)
        if short_range:
            start = int(short_range.group(1))
            end_two = int(short_range.group(2))
            end = (start // 100) * 100 + end_two
            if end < start:
                end += 100
            text = f"{start}-{end}"
        return normalize_season(text)
    return normalize_season(raw)


def season_end_year(season: Any) -> int | None:
    try:
        return season_from_string(normalize_stat_season(season))
    except (TypeError, ValueError):
        return None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text)
    if key in {"e", "epee", "epée"}:
        return "Epee"
    if key in {"f", "foil", "fleuret"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return text.title()


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text).replace(".", "")
    if key in {"f", "female", "woman", "women", "womens", "women's"}:
        return "Women"
    if key in {"m", "male", "man", "men", "mens", "men's"}:
        return "Men"
    return text.title()


def infer_gender_from_category(value: Any) -> str | None:
    key = normalize_key(value).replace(".", "")
    if re.search(r"\b(women|woman|female|womens|women's)\b", key):
        return "Women"
    if re.search(r"\b(men|man|male|mens|men's)\b", key):
        return "Men"
    return None


def normalize_category(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(
        r"^(women'?s?|female|men'?s?|male)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    key = normalize_key(text)
    if key in {"senior", "seniors", "open"}:
        return "Senior"
    if key in {"junior", "juniors", "u20", "under 20"}:
        return "Junior"
    if key in {"cadet", "cadets", "u17", "under 17"}:
        return "Cadet"
    if key in {"veteran", "veterans", "vet"}:
        return "Veteran"
    return text if "'" in text else text.title()


def metadata_value(row: dict[str, Any], *keys: str) -> Any:
    metadata = row.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = None
    if not isinstance(metadata, dict):
        return None
    for key in keys:
        if metadata.get(key) not in (None, ""):
            return metadata[key]
    return None


def normalize_source_confidence(*rows: dict[str, Any] | None) -> str:
    for row in rows:
        if not row:
            continue
        value = (
            row.get("source_confidence")
            or row.get("confidence")
            or metadata_value(row, "source_confidence", "confidence")
        )
        text = clean_text(value)
        if text:
            key = normalize_key(text)
            return key if key in {"high", "medium", "low", "unknown"} else key
    return "unknown"


def tournament_lookup(tournaments: dict[Any, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        values = tournaments.values()
    else:
        values = tournaments
    return {str(row["id"]): row for row in values if row.get("id") is not None}


def row_tournament(row: dict[str, Any], tournaments_by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    tournament_id = clean_text(row.get("tournament_id") or row.get("competition_id"))
    return tournaments_by_id.get(tournament_id or "")


def row_dimensions(
    row: dict[str, Any],
    tournament: dict[str, Any] | None,
) -> tuple[tuple[str, str, str, str, str] | None, str | None]:
    try:
        season = normalize_stat_season(row.get("season") or (tournament or {}).get("season"))
    except (TypeError, ValueError):
        return None, "season"

    weapon = normalize_weapon(row.get("weapon") or (tournament or {}).get("weapon"))
    raw_category = row.get("category") or (tournament or {}).get("category")
    gender = normalize_gender(row.get("gender") or (tournament or {}).get("gender"))
    gender = gender or infer_gender_from_category(raw_category)
    category = normalize_category(raw_category)
    if not weapon:
        return None, "weapon"
    if not gender:
        return None, "gender"
    if not category:
        return None, "category"
    source_confidence = normalize_source_confidence(row, tournament)
    return (season, weapon, gender, category, source_confidence), None


def parse_identity_members(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if clean_text(item)})


def build_identity_maps(identity_rows: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str], int]:
    identity_map: dict[str, str] = {}
    fie_id_map: dict[str, str] = {}
    duplicate_members = 0

    for row in identity_rows:
        members = parse_identity_members(
            row.get("fs_fencer_row_ids")
            or row.get("fencer_ids")
            or row.get("source_fencer_ids")
        )
        if not members:
            continue
        canonical = clean_text(row.get("canonical_id")) or members[0]

        for member in members:
            existing = identity_map.get(member)
            if existing:
                duplicate_members += 1
                if existing != canonical:
                    chosen = min(existing, canonical)
                    for mapped_member, mapped_canonical in list(identity_map.items()):
                        if mapped_canonical in {existing, canonical}:
                            identity_map[mapped_member] = chosen
                    canonical = chosen
            identity_map[member] = canonical

        for fie_id in parse_identity_members(row.get("fie_ids")):
            existing = fie_id_map.get(fie_id)
            if existing and existing != canonical:
                canonical = min(existing, canonical)
            fie_id_map[fie_id] = canonical

    for canonical in set(identity_map.values()):
        identity_map.setdefault(canonical, canonical)
    return identity_map, fie_id_map, duplicate_members


def canonical_fencer_id(fencer_id: Any, identity_map: dict[str, str] | None) -> str | None:
    text = clean_text(fencer_id)
    if not text:
        return None
    return (identity_map or {}).get(text, text)


def result_fencer_id(
    result: dict[str, Any],
    identity_map: dict[str, str],
    fie_id_map: dict[str, str],
) -> str | None:
    fencer_id = canonical_fencer_id(result.get("fencer_id"), identity_map)
    if fencer_id:
        return fencer_id
    fie_id = clean_text(result.get("fie_fencer_id") or result.get("fie_id"))
    return fie_id_map.get(fie_id or "")


def bout_fencer_id(row: dict[str, Any], primary: str, fallback: str, identity_map: dict[str, str]) -> str | None:
    return canonical_fencer_id(row.get(primary) or row.get(fallback), identity_map)


def medal_kind(rank: int | None, medal: Any) -> str | None:
    key = normalize_key(medal)
    if key in {"gold", "g", "1"}:
        return "gold"
    if key in {"silver", "s", "2"}:
        return "silver"
    if key in {"bronze", "b", "3"}:
        return "bronze"
    if rank == 1:
        return "gold"
    if rank == 2:
        return "silver"
    if rank == 3:
        return "bronze"
    return None


def new_stat(fencer_id: str, dimensions: tuple[str, str, str, str, str], updated_at: str) -> dict[str, Any]:
    season, weapon, gender, category, source_confidence = dimensions
    return {
        "fencer_id": fencer_id,
        "season": season,
        "weapon": weapon,
        "gender": gender,
        "category": category,
        "source_confidence": source_confidence,
        "results_by_competition": {},
        "wins": 0,
        "losses": 0,
        "touches_scored": 0,
        "touches_received": 0,
        "updated_at": updated_at,
    }


def choose_better_result(current: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if current is None:
        return candidate
    current_rank = current.get("rank")
    candidate_rank = candidate.get("rank")
    if candidate_rank is not None and (current_rank is None or candidate_rank < current_rank):
        return candidate
    if current.get("medal") is None and candidate.get("medal") is not None:
        return candidate
    return current


def add_result_observation(
    stats: dict[tuple[str, str, str, str, str, str], dict[str, Any]],
    *,
    fencer_id: str,
    dimensions: tuple[str, str, str, str, str],
    result: dict[str, Any],
    result_index: int,
    updated_at: str,
) -> None:
    key = (fencer_id, *dimensions)
    stat = stats.setdefault(key, new_stat(fencer_id, dimensions, updated_at))
    competition_id = clean_text(result.get("tournament_id") or result.get("competition_id") or result.get("id"))
    competition_id = competition_id or f"result:{result_index}"
    rank = positive_int(result.get("rank") if result.get("rank") is not None else result.get("placement"))
    observation = {
        "rank": rank,
        "medal": medal_kind(rank, result.get("medal")),
    }
    existing = stat["results_by_competition"].get(competition_id)
    stat["results_by_competition"][competition_id] = choose_better_result(existing, observation)


def add_bout_observation(
    stats: dict[tuple[str, str, str, str, str, str], dict[str, Any]],
    *,
    fencer_id: str,
    dimensions: tuple[str, str, str, str, str],
    scored: int,
    received: int,
    won: bool,
    updated_at: str,
) -> None:
    key = (fencer_id, *dimensions)
    stat = stats.setdefault(key, new_stat(fencer_id, dimensions, updated_at))
    if won:
        stat["wins"] += 1
    else:
        stat["losses"] += 1
    stat["touches_scored"] += scored
    stat["touches_received"] += received


def initial_counters(results: list[dict[str, Any]], bouts: list[dict[str, Any]], identity_rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "results_read": len(results),
        "bouts_read": len(bouts),
        "identity_rows": len(identity_rows),
        "duplicate_identity_members": 0,
        "skipped_orphan_results": 0,
        "skipped_missing_dimension_results": 0,
        "skipped_missing_fencer_bouts": 0,
        "skipped_missing_dimension_bouts": 0,
        "skipped_missing_score_bouts": 0,
        "skipped_self_bouts": 0,
        "skipped_no_winner_bouts": 0,
    }


def skipped_total(counters: dict[str, int]) -> int:
    return sum(value for key, value in counters.items() if key.startswith("skipped_"))


def stat_to_row(stat: dict[str, Any]) -> dict[str, Any]:
    results = list(stat["results_by_competition"].values())
    ranks = [row["rank"] for row in results if row.get("rank") is not None]
    medal_counts = {
        "gold": sum(1 for row in results if row.get("medal") == "gold"),
        "silver": sum(1 for row in results if row.get("medal") == "silver"),
        "bronze": sum(1 for row in results if row.get("medal") == "bronze"),
    }
    wins = stat["wins"]
    losses = stat["losses"]
    bouts_total = wins + losses
    touches_scored = stat["touches_scored"]
    touches_received = stat["touches_received"]
    avg_finish = round_float(sum(ranks) / len(ranks), 2) if ranks else None

    return {
        "fencer_id": stat["fencer_id"],
        "season": stat["season"],
        "weapon": stat["weapon"],
        "gender": stat["gender"],
        "category": stat["category"],
        "source_confidence": stat["source_confidence"],
        "starts": len(stat["results_by_competition"]),
        "best_finish": min(ranks) if ranks else None,
        "avg_finish": avg_finish,
        "gold_medals": medal_counts["gold"],
        "silver_medals": medal_counts["silver"],
        "bronze_medals": medal_counts["bronze"],
        "medal_count": sum(medal_counts.values()),
        "top4_count": sum(1 for rank in ranks if rank <= 4),
        "top8_count": sum(1 for rank in ranks if rank <= 8),
        "top16_count": sum(1 for rank in ranks if rank <= 16),
        "top32_count": sum(1 for rank in ranks if rank <= 32),
        "wins": wins,
        "losses": losses,
        "bouts_total": bouts_total,
        "touches_scored": touches_scored,
        "touches_received": touches_received,
        "touch_differential": touches_scored - touches_received,
        "win_pct": round_float(wins / bouts_total, 4) if bouts_total else None,
        "previous_best_finish": None,
        "best_finish_delta": None,
        "previous_avg_finish": None,
        "avg_finish_delta": None,
        "updated_at": stat["updated_at"],
    }


def add_finish_deltas(rows: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                row["fencer_id"],
                row["weapon"],
                row["gender"],
                row["category"],
                row["source_confidence"],
            )
        ].append(row)

    for group_rows in grouped.values():
        group_rows.sort(key=lambda row: (season_end_year(row["season"]) or 0, row["season"]))
        previous: dict[str, Any] | None = None
        for row in group_rows:
            if previous:
                if previous.get("best_finish") is not None and row.get("best_finish") is not None:
                    row["previous_best_finish"] = previous["best_finish"]
                    row["best_finish_delta"] = row["best_finish"] - previous["best_finish"]
                if previous.get("avg_finish") is not None and row.get("avg_finish") is not None:
                    row["previous_avg_finish"] = previous["avg_finish"]
                    row["avg_finish_delta"] = round_float(row["avg_finish"] - previous["avg_finish"], 2)
            previous = row


def build_fencer_season_stat_rows(
    *,
    results: list[dict[str, Any]],
    tournaments: dict[Any, dict[str, Any]] | list[dict[str, Any]],
    bouts: list[dict[str, Any]],
    identity_rows: list[dict[str, Any]] | None = None,
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    timestamp = updated_at or datetime.now(timezone.utc).isoformat()
    identity_rows = identity_rows or []
    identity_map, fie_id_map, duplicate_members = build_identity_maps(identity_rows)
    counters = initial_counters(results, bouts, identity_rows)
    counters["duplicate_identity_members"] = duplicate_members
    tournaments_by_id = tournament_lookup(tournaments)
    stats: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}

    for index, raw_result in enumerate(results):
        fencer_id = result_fencer_id(raw_result, identity_map, fie_id_map)
        if not fencer_id:
            counters["skipped_orphan_results"] += 1
            continue
        tournament = row_tournament(raw_result, tournaments_by_id)
        dimensions, _reason = row_dimensions(raw_result, tournament)
        if not dimensions:
            counters["skipped_missing_dimension_results"] += 1
            continue
        add_result_observation(
            stats,
            fencer_id=fencer_id,
            dimensions=dimensions,
            result=raw_result,
            result_index=index,
            updated_at=timestamp,
        )

    for raw_bout in bouts:
        tournament = row_tournament(raw_bout, tournaments_by_id)
        dimensions, _reason = row_dimensions(raw_bout, tournament)
        if not dimensions:
            counters["skipped_missing_dimension_bouts"] += 1
            continue
        fencer_a = bout_fencer_id(raw_bout, "fencer_a", "fencer_a_id", identity_map)
        fencer_b = bout_fencer_id(raw_bout, "fencer_b", "fencer_b_id", identity_map)
        if not fencer_a or not fencer_b:
            counters["skipped_missing_fencer_bouts"] += 1
            continue
        if fencer_a == fencer_b:
            counters["skipped_self_bouts"] += 1
            continue
        score_a = to_int(raw_bout.get("score_a"))
        score_b = to_int(raw_bout.get("score_b"))
        if score_a is None or score_b is None:
            counters["skipped_missing_score_bouts"] += 1
            continue
        winner = canonical_fencer_id(raw_bout.get("winner_id"), identity_map)
        if winner not in {fencer_a, fencer_b} and score_a != score_b:
            winner = fencer_a if score_a > score_b else fencer_b
        if winner not in {fencer_a, fencer_b}:
            counters["skipped_no_winner_bouts"] += 1
            continue
        add_bout_observation(
            stats,
            fencer_id=fencer_a,
            dimensions=dimensions,
            scored=score_a,
            received=score_b,
            won=winner == fencer_a,
            updated_at=timestamp,
        )
        add_bout_observation(
            stats,
            fencer_id=fencer_b,
            dimensions=dimensions,
            scored=score_b,
            received=score_a,
            won=winner == fencer_b,
            updated_at=timestamp,
        )

    rows = [stat_to_row(stats[key]) for key in sorted(stats)]
    add_finish_deltas(rows)
    counters["season_stat_rows"] = len(rows)
    return rows, counters


def fetch_all(client, table: str, columns: str, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table(table)
            .select(columns)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def fetch_with_fallbacks(client, table: str, select_options: list[str], *, page_size: int) -> list[dict[str, Any]]:
    last_exc: Exception | None = None
    for columns in select_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_exc = exc
            print(f"  Select fallback for {table}: {exc}")
    if last_exc:
        raise last_exc
    return []


def load_identity_rows(client, *, page_size: int) -> list[dict[str, Any]]:
    for columns in IDENTITY_SELECTS:
        try:
            return fetch_all(client, "fs_fencer_identities", columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
            print(f"  Select fallback for fs_fencer_identities: {exc}")
    print(f"Identity table unavailable; using raw fencer IDs: {last_error}")
    return []


def batch_upsert(
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
            client.table(SEASON_STATS_TABLE).upsert(
                batch,
                on_conflict=SEASON_STATS_CONFLICT_COLUMNS,
            ).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  {SEASON_STATS_TABLE} upsert batch {index // batch_size} failed: {exc}")
    return written, failed


def compute_fencer_season_stats(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    updated_at: str | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(MODULE_NAME).start() if log_run else None
    previous_summary = get_state(MODULE_NAME, "last_summary") if update_state else None

    try:
        client = client or get_supabase_client()
        timestamp = updated_at or datetime.now(timezone.utc).isoformat()
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        bouts = fetch_with_fallbacks(client, "fs_bouts", BOUT_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
        identity_rows = load_identity_rows(client, page_size=page_size)

        rows, counters = build_fencer_season_stat_rows(
            results=results,
            tournaments=tournaments,
            bouts=bouts,
            identity_rows=identity_rows,
            updated_at=timestamp,
        )
        written, failed = batch_upsert(client, rows, batch_size=batch_size) if rows else (0, 0)
        skipped = skipped_total(counters)
        summary: dict[str, Any] = {
            "results_read": len(results),
            "bouts_read": len(bouts),
            "tournaments_read": len(tournaments),
            "identity_rows": len(identity_rows),
            "season_stat_rows": len(rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "duplicate_identity_members": counters["duplicate_identity_members"],
        }
        for key, value in counters.items():
            if key.startswith("skipped_"):
                summary[key] = value
        if isinstance(previous_summary, dict) and previous_summary.get("updated_at"):
            summary["previous_updated_at"] = previous_summary["updated_at"]

        if update_state:
            set_state(MODULE_NAME, "last_summary", {**summary, "updated_at": timestamp})
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Fencer season stats computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_fencer_season_stats()
    print(
        "Fencer season stats computation complete - "
        f"{summary['season_stat_rows']} rows built, "
        f"{summary['written']} written, {summary['failed']} failed, "
        f"{summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()

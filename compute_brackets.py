import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state


SOURCE = "compute_brackets"
PAGE_SIZE = 1000
BATCH_SIZE = 100
BRACKET_CONFLICT = "tournament_id,event_key,round_order,bout_order"

BOUT_SELECTS = (
    (
        "id,tournament_id,fencer_a_id,fencer_b_id,score_a,score_b,round,winner_id,"
        "metadata,event_key,event_id,weapon,gender,category,bout_order,piste,"
        "seed_a,seed_b,source,is_bye"
    ),
    "id,tournament_id,fencer_a_id,fencer_b_id,score_a,score_b,round,winner_id",
)
RESULT_SELECTS = (
    (
        "id,tournament_id,fencer_id,name,nationality,country,rank,placement,"
        "metadata,event_key,event_id,weapon,gender,category,source"
    ),
    "id,tournament_id,fencer_id,name,nationality,country,rank,placement,metadata",
    "id,tournament_id,fencer_id,name,nationality,country,rank,placement",
)
TOURNAMENT_SELECTS = (
    "id,name,weapon,gender,category,type,metadata,event_key,event_id,source",
    "id,name,weapon,gender,category,type,metadata",
    "id,name,weapon,gender,category,type",
)

ORDER_KEYS = (
    "bout_order",
    "order",
    "match_order",
    "table_order",
    "position",
    "bout_index",
    "match_index",
)
PISTE_KEYS = ("piste", "strip", "pod", "table", "planche")
SEED_A_KEYS = ("seed_a", "fencer_a_seed", "seed1", "seed_1")
SEED_B_KEYS = ("seed_b", "fencer_b_seed", "seed2", "seed_2")


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return None
    from supabase import create_client

    return create_client(url, key)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (clean_text(value) or "").casefold()).strip("-")


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "bye"}


def metadata_for(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str) and metadata.strip():
        try:
            parsed = json.loads(metadata)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def first_value(row: dict[str, Any] | None, keys: tuple[str, ...] | list[str]) -> Any:
    if not row:
        return None
    metadata = metadata_for(row)
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
        value = metadata.get(key)
        if value is not None and value != "":
            return value
    return None


def event_key_from_parts(
    event_key: Any,
    event_id: Any,
    weapon: Any,
    gender: Any,
    category: Any,
) -> str:
    explicit = clean_text(event_key) or clean_text(event_id)
    if explicit:
        return compact_key(explicit)
    parts = [compact_key(part) for part in (gender, weapon, category) if clean_text(part)]
    return "-".join(parts) if parts else "main"


def event_info_from_row(
    row: dict[str, Any] | None,
    tournament: dict[str, Any] | None,
) -> dict[str, Any]:
    event_id = first_value(row, ("event_id",)) or first_value(tournament, ("event_id",))
    weapon = first_value(row, ("weapon",)) or first_value(tournament, ("weapon",))
    gender = first_value(row, ("gender",)) or first_value(tournament, ("gender",))
    category = first_value(row, ("category",)) or first_value(tournament, ("category",))
    event_key = first_value(row, ("event_key",))
    source = (
        first_value(row, ("source", "result_source", "source_name"))
        or first_value(tournament, ("source", "result_source", "source_name"))
        or "fs_bouts"
    )
    return {
        "event_key": event_key_from_parts(event_key, event_id, weapon, gender, category),
        "event_id": clean_text(event_id),
        "weapon": clean_text(weapon),
        "gender": clean_text(gender),
        "category": clean_text(category),
        "source": clean_text(source),
    }


def merge_event_info(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if not merged.get(key) and value:
            merged[key] = value
    return merged


def collect_event_context(
    tournament: dict[str, Any],
    results: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    event_infos: dict[str, dict[str, Any]] = {}
    fencer_events: dict[str, set[str]] = defaultdict(set)

    for result in results:
        if result.get("tournament_id") != tournament.get("id"):
            continue
        info = event_info_from_row(result, tournament)
        key = info["event_key"]
        event_infos[key] = merge_event_info(event_infos.get(key, {}), info)
        fencer_id = result.get("fencer_id")
        if fencer_id:
            fencer_events[str(fencer_id)].add(key)

    if not event_infos:
        info = event_info_from_row(None, tournament)
        event_infos[info["event_key"]] = info

    return event_infos, fencer_events


def explicit_event_info(
    bout: dict[str, Any],
    tournament: dict[str, Any],
) -> dict[str, Any] | None:
    if first_value(bout, ("event_key", "event_id", "weapon", "gender", "category")):
        return event_info_from_row(bout, tournament)
    return None


def infer_event_info(
    bout: dict[str, Any],
    tournament: dict[str, Any],
    event_infos: dict[str, dict[str, Any]],
    fencer_events: dict[str, set[str]],
) -> dict[str, Any] | None:
    explicit = explicit_event_info(bout, tournament)
    if explicit:
        key = explicit["event_key"]
        return merge_event_info(event_infos.get(key, {}), explicit)

    candidates = []
    for fencer_id in (bout.get("fencer_a_id"), bout.get("fencer_b_id"), bout.get("winner_id")):
        if fencer_id and str(fencer_id) in fencer_events:
            candidates.append(set(fencer_events[str(fencer_id)]))

    if candidates:
        common = set.intersection(*candidates)
        if len(common) == 1:
            return event_infos[next(iter(common))]

    if len(event_infos) == 1:
        return next(iter(event_infos.values()))
    return None


def parse_round_info(value: Any) -> dict[str, Any] | None:
    original = clean_text(value)
    if not original:
        return None

    text = original.casefold()
    if re.search(r"\b(pool|poule|poules)\b", text):
        return None
    if re.search(r"\b(classification|placing|place|bronze|third)\b", text):
        return None

    number_match = re.search(
        r"\b(?:tableau|table|round|top|t)\s*(?:of|de|des)?\s*(\d{1,3})\b",
        text,
    )
    if number_match:
        size = to_int(number_match.group(1))
        if size and size >= 2:
            return {"round_name": original, "round_size": size}

    if re.search(r"\bquarter(?:\s*-?\s*final|final)?s?\b", text):
        return {"round_name": original, "round_size": 8}
    if re.search(r"\bsemi(?:\s*-?\s*final|final)?s?\b", text):
        return {"round_name": original, "round_size": 4}
    if re.search(r"\bfinals?\b", text):
        return {"round_name": original, "round_size": 2}

    return None


def extract_order(bout: dict[str, Any]) -> int | None:
    value = first_value(bout, ORDER_KEYS)
    order = to_int(value)
    return order if order and order > 0 else None


def extract_first_clean(bout: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    value = first_value(bout, keys)
    return clean_text(value)


def extract_seed(bout: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    return to_int(first_value(bout, keys))


def is_explicit_bye(bout: dict[str, Any]) -> bool:
    return to_bool(first_value(bout, ("is_bye", "bye")))


def fencer_complete_enough(bout: dict[str, Any], is_bye: bool) -> bool:
    fencer_a = bout.get("fencer_a_id")
    fencer_b = bout.get("fencer_b_id")
    if is_bye:
        return bool(fencer_a or fencer_b)
    return bool(fencer_a and fencer_b)


def derive_winner(bout: dict[str, Any]) -> Any:
    winner = bout.get("winner_id")
    if winner:
        return winner
    score_a = to_int(bout.get("score_a"))
    score_b = to_int(bout.get("score_b"))
    if score_a is None or score_b is None or score_a == score_b:
        return None
    return bout.get("fencer_a_id") if score_a > score_b else bout.get("fencer_b_id")


def row_completeness(row: dict[str, Any]) -> tuple[int, str]:
    score = 0
    for key in (
        "fencer_a_id",
        "fencer_b_id",
        "winner_id",
        "score_a",
        "score_b",
        "seed_a",
        "seed_b",
        "piste",
    ):
        if row.get(key) is not None:
            score += 1
    if row.get("is_bye"):
        score += 1
    return score, str(row.get("metadata", {}).get("source_bout_id") or "")


def tournament_source_metadata(tournament: dict[str, Any]) -> dict[str, Any]:
    metadata = metadata_for(tournament)
    return {
        key: metadata.get(key)
        for key in ("source_url", "result_url", "competition_url", "source_file")
        if metadata.get(key)
    }


def make_bracket_id(bracket_key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fencespace:bracket:{bracket_key}"))


def build_tournament_bracket_rows(
    tournament: dict[str, Any],
    bouts: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    updated_at = updated_at or utc_now_iso()
    tournament_id = tournament.get("id")
    if not tournament_id:
        return [], "missing_tournament_id"

    event_infos, fencer_events = collect_event_context(tournament, results)
    source_metadata = tournament_source_metadata(tournament)
    candidates_by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    saw_elimination = False
    saw_missing_order = False
    saw_ambiguous_event = False

    for bout in bouts:
        if bout.get("tournament_id") != tournament_id:
            continue
        round_info = parse_round_info(bout.get("round"))
        if not round_info:
            continue
        saw_elimination = True

        bout_order = extract_order(bout)
        if bout_order is None:
            saw_missing_order = True
            continue

        event_info = infer_event_info(bout, tournament, event_infos, fencer_events)
        if not event_info:
            saw_ambiguous_event = True
            continue

        is_bye = is_explicit_bye(bout)
        if not fencer_complete_enough(bout, is_bye):
            continue

        winner_id = derive_winner(bout)
        metadata = {
            **source_metadata,
            "source_bout_id": bout.get("id"),
            "source_round": clean_text(bout.get("round")),
        }
        bout_metadata = metadata_for(bout)
        if bout_metadata:
            metadata["bout_metadata"] = bout_metadata

        row = {
            "tournament_id": tournament_id,
            "event_id": event_info.get("event_id"),
            "event_key": event_info["event_key"],
            "weapon": event_info.get("weapon"),
            "gender": event_info.get("gender"),
            "category": event_info.get("category"),
            "round_name": round_info["round_name"],
            "round_size": round_info["round_size"],
            "bout_order": bout_order,
            "fencer_a_id": bout.get("fencer_a_id"),
            "fencer_b_id": bout.get("fencer_b_id"),
            "score_a": to_int(bout.get("score_a")),
            "score_b": to_int(bout.get("score_b")),
            "winner_id": winner_id,
            "seed_a": extract_seed(bout, SEED_A_KEYS),
            "seed_b": extract_seed(bout, SEED_B_KEYS),
            "piste": extract_first_clean(bout, PISTE_KEYS),
            "source": clean_text(first_value(bout, ("source", "source_name"))) or event_info.get("source") or "fs_bouts",
            "is_bye": is_bye,
            "metadata": metadata,
            "updated_at": updated_at,
        }
        candidates_by_event[event_info["event_key"]].append(row)

    rows: list[dict[str, Any]] = []
    for event_key, candidates in sorted(candidates_by_event.items()):
        if not candidates:
            continue
        round_sizes = sorted({row["round_size"] for row in candidates}, reverse=True)
        round_orders = {round_size: index + 1 for index, round_size in enumerate(round_sizes)}

        deduped: dict[tuple[int, int], dict[str, Any]] = {}
        for row in candidates:
            row["round_order"] = round_orders[row["round_size"]]
            key = (row["round_order"], row["bout_order"])
            existing = deduped.get(key)
            if not existing or row_completeness(row) > row_completeness(existing):
                deduped[key] = row

        for row in sorted(deduped.values(), key=lambda item: (item["round_order"], item["bout_order"])):
            bracket_key = f"{tournament_id}:{event_key}:{row['round_order']}:{row['bout_order']}"
            row["bracket_key"] = bracket_key
            row["id"] = make_bracket_id(bracket_key)
            rows.append(row)

    if rows:
        return rows, None
    if saw_missing_order:
        return [], "missing_bout_order"
    if saw_ambiguous_event:
        return [], "ambiguous_event"
    if saw_elimination:
        return [], "insufficient_bout_evidence"
    return [], "no_elimination_bouts"


def fetch_all(
    client,
    table: str,
    columns: str,
    *,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
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
            break
        offset += page_size
    return rows


def fetch_all_with_fallback(
    client,
    table: str,
    selects: tuple[str, ...],
    *,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    last_error = None
    for columns in selects:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Unable to fetch {table}") from last_error


def batch_upsert_brackets(
    client,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_tournament_brackets").upsert(
            batch,
            on_conflict=BRACKET_CONFLICT,
        ).execute()
        written += len(batch)
    return written


def compute_brackets(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    updated_at: str | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    if not client:
        return {
            "tournaments_read": 0,
            "bouts_read": 0,
            "results_read": 0,
            "bracket_rows": 0,
            "written": 0,
            "skipped": 0,
            "failed": 0,
            "skipped_tournaments": [],
            "failed_tournaments": [],
            "no_credentials": True,
        }

    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        tournaments = fetch_all_with_fallback(
            client,
            "fs_tournaments",
            TOURNAMENT_SELECTS,
            page_size=page_size,
        )
        bouts = fetch_all_with_fallback(
            client,
            "fs_bouts",
            BOUT_SELECTS,
            page_size=page_size,
        )
        results = fetch_all_with_fallback(
            client,
            "fs_results",
            RESULT_SELECTS,
            page_size=page_size,
        )

        tournaments_by_id = {row.get("id"): row for row in tournaments if row.get("id")}
        bouts_by_tournament: dict[str, list[dict[str, Any]]] = defaultdict(list)
        results_by_tournament: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for bout in bouts:
            if bout.get("tournament_id"):
                bouts_by_tournament[str(bout["tournament_id"])].append(bout)
        for result in results:
            if result.get("tournament_id"):
                results_by_tournament[str(result["tournament_id"])].append(result)

        rows: list[dict[str, Any]] = []
        skipped_tournaments: list[dict[str, str]] = []
        failed_tournaments: list[dict[str, str]] = []
        failed = 0
        for tournament_id in sorted(bouts_by_tournament):
            tournament = tournaments_by_id.get(tournament_id, {"id": tournament_id})
            try:
                tournament_rows, skip_reason = build_tournament_bracket_rows(
                    tournament,
                    bouts_by_tournament[tournament_id],
                    results_by_tournament.get(tournament_id, []),
                    updated_at=updated_at,
                )
            except Exception as exc:
                failed += 1
                failed_tournaments.append({"tournament_id": tournament_id, "reason": str(exc)})
                continue

            if tournament_rows:
                rows.extend(tournament_rows)
            else:
                skipped_tournaments.append(
                    {"tournament_id": tournament_id, "reason": skip_reason or "unknown"}
                )

        written = batch_upsert_brackets(client, rows) if rows else 0
        summary = {
            "tournaments_read": len(tournaments),
            "bouts_read": len(bouts),
            "results_read": len(results),
            "bracket_rows": len(rows),
            "written": written,
            "skipped": len(skipped_tournaments),
            "failed": failed,
            "skipped_tournaments": skipped_tournaments,
            "failed_tournaments": failed_tournaments,
            "no_credentials": False,
        }
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": utc_now_iso(), **summary})
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=len(skipped_tournaments),
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> dict[str, Any]:
    summary = compute_brackets()
    if summary.get("no_credentials"):
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY are not set; bracket computation skipped.")
    else:
        print(
            "brackets: "
            f"{summary['written']} written, {summary['failed']} failed, "
            f"{summary['skipped']} skipped"
        )
    return summary


if __name__ == "__main__":
    main()

import os
import re
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Callable

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
UPDATE_BATCH_SIZE = 100
SOURCE = "compute_head_to_head"

BOUT_SELECT = "id,tournament_id,fencer_a,fencer_b,winner,score_a,score_b"
TOURNAMENT_SELECT = "id,weapon,end_date"

WEAPON_MAP = {
    "s": "Sabre",
    "sabre": "Sabre",
    "saber": "Sabre",
    "e": "Epee",
    "epee": "Epee",
    "epée": "Epee",
    "f": "Foil",
    "foil": "Foil",
}


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return WEAPON_MAP.get(text.casefold(), text.title())


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_uuid(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return str(uuid.UUID(text))
    except (TypeError, ValueError):
        return None


def canonical_pair(fencer_a: Any, fencer_b: Any) -> tuple[str, str] | None:
    a_id = normalize_uuid(fencer_a)
    b_id = normalize_uuid(fencer_b)
    if not a_id or not b_id or a_id == b_id:
        return None
    a_uuid = uuid.UUID(a_id)
    b_uuid = uuid.UUID(b_id)
    return (a_id, b_id) if a_uuid.int < b_uuid.int else (b_id, a_id)


def normalize_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = clean_text(value)
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def fetch_all(
    supabase,
    table: str,
    select_columns: str,
    configure: Callable[[Any], Any] | None = None,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = supabase.table(table).select(select_columns)
        if configure:
            query = configure(query)
        page = query.range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def fetch_bouts(supabase) -> list[dict[str, Any]]:
    return fetch_all(
        supabase,
        "fs_bouts",
        BOUT_SELECT,
        configure=lambda query: query.not_.is_("fencer_a", "null").not_.is_(
            "fencer_b", "null"
        ),
    )


def fetch_tournaments(supabase) -> dict[str, dict[str, Any]]:
    rows = fetch_all(supabase, "fs_tournaments", TOURNAMENT_SELECT)
    return {str(row["id"]): row for row in rows if row.get("id") is not None}


def bout_weapon(bout: dict[str, Any], tournaments: dict[str, dict[str, Any]]) -> str | None:
    weapon = normalize_weapon(bout.get("weapon"))
    if weapon:
        return weapon
    tournament_id = bout.get("tournament_id")
    tournament = tournaments.get(str(tournament_id)) if tournament_id is not None else None
    return normalize_weapon(tournament.get("weapon")) if tournament else None


def meeting_date(bout: dict[str, Any], tournaments: dict[str, dict[str, Any]]) -> str | None:
    for key in ("bout_date", "meeting_date", "date", "played_at"):
        value = normalize_date(bout.get(key))
        if value:
            return value

    tournament_id = bout.get("tournament_id")
    tournament = tournaments.get(str(tournament_id)) if tournament_id is not None else None
    if not tournament:
        return None
    for key in ("end_date", "date", "start_date"):
        value = normalize_date(tournament.get(key))
        if value:
            return value
    return None


def build_head_to_head_rows(
    bouts: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]],
    now: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    updated_at = now or datetime.now(timezone.utc).isoformat()
    grouped: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "a_wins": 0,
            "b_wins": 0,
            "a_touches": 0,
            "b_touches": 0,
            "bouts_total": 0,
            "last_meeting_date": None,
            "last_winner_id": None,
        }
    )
    skipped = 0

    for bout in bouts:
        pair = canonical_pair(bout.get("fencer_a"), bout.get("fencer_b"))
        score_a = to_int(bout.get("score_a"))
        score_b = to_int(bout.get("score_b"))
        weapon = bout_weapon(bout, tournaments)
        if not pair or score_a is None or score_b is None or not weapon:
            skipped += 1
            continue

        canonical_a, canonical_b = pair
        bout_a = normalize_uuid(bout.get("fencer_a"))
        if bout_a == canonical_a:
            canonical_a_score = score_a
            canonical_b_score = score_b
        else:
            canonical_a_score = score_b
            canonical_b_score = score_a

        stats = grouped[(canonical_a, canonical_b, weapon)]
        stats["a_touches"] += canonical_a_score
        stats["b_touches"] += canonical_b_score
        stats["bouts_total"] += 1

        winner_id = None
        if canonical_a_score > canonical_b_score:
            stats["a_wins"] += 1
            winner_id = canonical_a
        elif canonical_b_score > canonical_a_score:
            stats["b_wins"] += 1
            winner_id = canonical_b

        current_date = meeting_date(bout, tournaments)
        if current_date and (
            stats["last_meeting_date"] is None
            or current_date >= stats["last_meeting_date"]
        ):
            stats["last_meeting_date"] = current_date
            stats["last_winner_id"] = winner_id

    rows = []
    for (fencer_a_id, fencer_b_id, weapon), stats in sorted(grouped.items()):
        rows.append(
            {
                "fencer_a_id": fencer_a_id,
                "fencer_b_id": fencer_b_id,
                "weapon": weapon,
                "a_wins": stats["a_wins"],
                "b_wins": stats["b_wins"],
                "a_touches": stats["a_touches"],
                "b_touches": stats["b_touches"],
                "bouts_total": stats["bouts_total"],
                "last_meeting_date": stats["last_meeting_date"],
                "last_winner_id": stats["last_winner_id"],
                "updated_at": updated_at,
            }
        )
    return rows, skipped


def batch_upsert_head_to_head(
    supabase, rows: list[dict[str, Any]], batch_size: int = UPDATE_BATCH_SIZE
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        supabase.table("fs_head_to_head").upsert(
            batch, on_conflict="fencer_a_id,fencer_b_id,weapon"
        ).execute()
        written += len(batch)
    return written


def compute_head_to_head(supabase, now: str | None = None) -> dict[str, int]:
    bouts = fetch_bouts(supabase)
    tournaments = fetch_tournaments(supabase)
    rows, skipped = build_head_to_head_rows(bouts, tournaments, now=now)
    written = batch_upsert_head_to_head(supabase, rows) if rows else 0
    return {"bouts_loaded": len(bouts), "rows_written": written, "skipped": skipped}


def main() -> None:
    run_log = ScraperRunLogger(SOURCE).start()
    try:
        previous_state = get_state(SOURCE, "last_run")
        if previous_state:
            print(f"Previous head-to-head state: {previous_state}")

        supabase = get_supabase_client()
        summary = compute_head_to_head(supabase)
        set_state(
            SOURCE,
            "last_run",
            {
                **summary,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        run_log.complete(
            written=summary["rows_written"],
            failed=0,
            skipped=summary["skipped"],
            metadata=summary,
        )
        print(
            "Head-to-head computation complete: "
            f"{summary['rows_written']} rows written, "
            f"{summary['skipped']} bouts skipped"
        )
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

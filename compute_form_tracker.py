import json
import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 200
SOURCE = "compute_form_tracker"
FORM_CONFLICT_COLUMNS = "fencer_id,weapon"
MAX_RECENT_COMPETITIONS = 5
RANK_SCORE_STEP = 4
TREND_RANK_THRESHOLD = 2.0

MEDAL_BONUS = {"gold": 8, "silver": 5, "bronze": 3}
MEDAL_MAP = {
    "gold": "gold",
    "g": "gold",
    "1": "gold",
    "1st": "gold",
    "silver": "silver",
    "s": "silver",
    "2": "silver",
    "2nd": "silver",
    "bronze": "bronze",
    "b": "bronze",
    "3": "bronze",
    "3rd": "bronze",
}

RESULT_SELECTS = (
    "id,tournament_id,fencer_id,rank,placement,weapon,category,gender,medal,is_team,team,event_type,type",
    "id,tournament_id,fencer_id,rank,placement,weapon,category,gender,medal",
    "id,tournament_id,fencer_id,rank,placement,weapon,medal",
    "id,tournament_id,fencer_id,rank,placement",
)
TOURNAMENT_SELECTS = (
    "id,weapon,category,gender,end_date,start_date,date,season,name,type,status,has_results,is_team,team,event_type",
    "id,weapon,category,gender,end_date,start_date,date,season,name,type,status,has_results",
    "id,weapon,category,end_date,start_date,date,season,name,type",
    "id,weapon,category,season",
)
IDENTITY_SELECTS = (
    "id,canonical_id,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
    "canonical_id,fs_fencer_row_ids",
    "canonical_id,fencer_ids",
)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", (clean_text(value) or "").casefold())


def coerce_rank(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        rank = int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(value))
        rank = int(match.group(0)) if match else None
    return rank if rank and rank > 0 else None


def round_decimal(value: float | Decimal, places: str = "0.01") -> float:
    decimal_value = Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)
    return float(decimal_value)


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold()
    if key in {"e", "epee", "épée"}:
        return "Epee"
    if key in {"f", "foil"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return text.title()


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold().replace(".", "")
    if key in {"f", "female", "women", "woman", "womens", "women's"}:
        return "Women's"
    if key in {"m", "male", "men", "man", "mens", "men's"}:
        return "Men's"
    return text.title()


def normalize_category(category: Any, gender: Any = None) -> str | None:
    category_text = clean_text(category)
    if not category_text:
        return None
    category_label = category_text if "'" in category_text else category_text.title()
    gender_label = normalize_gender(gender)
    if not gender_label:
        return category_label
    if category_label.casefold().startswith(gender_label.casefold()):
        return category_label
    return f"{gender_label} {category_label}"


def medal_bucket(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return MEDAL_MAP.get(compact_key(text))


def medal_from_rank(rank: int | None) -> str | None:
    if rank == 1:
        return "gold"
    if rank == 2:
        return "silver"
    if rank == 3:
        return "bronze"
    return None


def result_medal(result: dict[str, Any], rank: int | None) -> str | None:
    return medal_bucket(result.get("medal")) or medal_from_rank(rank)


def truthy(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    return compact_key(value) in {"1", "true", "yes", "y", "team"}


def contains_team_text(value: Any) -> bool:
    text = clean_text(value)
    if not text:
        return False
    return re.search(r"\bteam\b", text, flags=re.IGNORECASE) is not None


def is_team_event(result: dict[str, Any], tournament: dict[str, Any] | None) -> bool:
    sources = [result, tournament or {}]
    for source in sources:
        for field in ("team", "is_team", "team_event"):
            if truthy(source.get(field)):
                return True
        for field in ("category", "event_type", "type", "name"):
            if contains_team_text(source.get(field)):
                return True
    return False


def is_incomplete_event(result: dict[str, Any], tournament: dict[str, Any] | None) -> bool:
    source = tournament or result
    has_results = source.get("has_results")
    if has_results is False or compact_key(has_results) in {"false", "0", "no", "n"}:
        return True

    status = compact_key(source.get("status"))
    return status in {"scheduled", "upcoming", "pending", "postponed", "cancelled", "canceled"}


def parse_date_iso(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def season_sort_value(value: Any) -> int:
    text = clean_text(value) or ""
    years = [int(part) for part in re.findall(r"\d{4}", text)]
    if years:
        return max(years)
    number = coerce_rank(text)
    return number or 0


def competition_date(result: dict[str, Any], tournament: dict[str, Any] | None) -> str | None:
    for source in (result, tournament or {}):
        for field in ("end_date", "start_date", "date", "competition_date", "event_date"):
            parsed = parse_date_iso(source.get(field))
            if parsed:
                return parsed
    return None


def competition_sort_key(competition: dict[str, Any]) -> tuple[int, str, str]:
    date_text = competition.get("date")
    if date_text:
        sort_value = date.fromisoformat(date_text).toordinal()
    else:
        sort_value = season_sort_value(competition.get("season"))
    return (
        sort_value,
        clean_text(competition.get("tournament_id")) or "",
        clean_text(competition.get("result_id")) or "",
    )


def tournament_lookup(tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


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


def build_identity_maps(identity_rows: list[dict[str, Any]] | None) -> tuple[dict[str, str], dict[str, str]]:
    identity_map: dict[str, str] = {}
    identity_ids: dict[str, str] = {}
    for row in identity_rows or []:
        members = parse_identity_members(
            row.get("fs_fencer_row_ids")
            or row.get("fencer_ids")
            or row.get("source_fencer_ids")
        )
        canonical = clean_text(row.get("canonical_id"))
        if not canonical and members:
            canonical = members[0]
        if not canonical:
            continue

        identity_id = clean_text(row.get("id"))
        identity_map[canonical] = canonical
        if identity_id:
            identity_ids[canonical] = identity_id
        for member in members:
            identity_map[member] = canonical
            if identity_id:
                identity_ids[member] = identity_id
    return identity_map, identity_ids


def canonical_fencer_id(fencer_id: Any, identity_map: dict[str, str]) -> str | None:
    text = clean_text(fencer_id)
    if not text:
        return None
    return identity_map.get(text, text)


def choose_competition(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    existing_rank = existing.get("rank")
    candidate_rank = candidate.get("rank")
    if existing_rank is None and candidate_rank is not None:
        return candidate
    if existing_rank is not None and candidate_rank is not None and candidate_rank < existing_rank:
        return candidate
    return existing


def rank_score(rank: int) -> float:
    return float(max(0, 100 - ((rank - 1) * RANK_SCORE_STEP)))


def split_trend_direction(ranks: list[int]) -> str:
    if len(ranks) < 2:
        return "stable"
    half = len(ranks) // 2
    older = ranks[:half]
    newer = ranks[-half:]
    older_avg = sum(older) / len(older)
    newer_avg = sum(newer) / len(newer)
    delta = older_avg - newer_avg
    if delta >= TREND_RANK_THRESHOLD:
        return "improving"
    if delta <= -TREND_RANK_THRESHOLD:
        return "declining"
    return "stable"


def build_last_competitions(window: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "tournament_id": competition.get("tournament_id"),
            "date": competition.get("date"),
            "rank": competition.get("rank"),
            "category": competition.get("category"),
            "medal": competition.get("medal"),
        }
        for competition in window
    ]


def score_window(window: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
    weights = list(range(1, len(window) + 1))
    scored: list[dict[str, Any]] = []
    weighted_score = 0.0
    weight_total = 0

    for competition, weight in zip(window, weights):
        rank = competition.get("rank")
        medal = competition.get("medal")
        if rank is None:
            scored.append(
                {
                    "tournament_id": competition.get("tournament_id"),
                    "rank": None,
                    "weight": weight,
                    "rank_score": None,
                    "medal_bonus": 0,
                    "event_score": None,
                    "weighted_contribution": 0,
                }
            )
            continue

        base_score = rank_score(rank)
        bonus = MEDAL_BONUS.get(medal, 0)
        event_score = min(100.0, base_score + bonus)
        weighted_contribution = event_score * weight
        weighted_score += weighted_contribution
        weight_total += weight
        scored.append(
            {
                "tournament_id": competition.get("tournament_id"),
                "rank": rank,
                "weight": weight,
                "rank_score": round_decimal(base_score),
                "medal_bonus": bonus,
                "event_score": round_decimal(event_score),
                "weighted_contribution": round_decimal(weighted_contribution),
            }
        )

    if not weight_total:
        return 0.0, scored
    return round_decimal(weighted_score / weight_total), scored


def form_row(
    fencer_id: str,
    weapon: str,
    competitions: list[dict[str, Any]],
    *,
    identity_id: str | None,
    used_identity_grouping: bool,
    now: str,
) -> dict[str, Any]:
    ordered = sorted(competitions, key=competition_sort_key)
    window = ordered[-MAX_RECENT_COMPETITIONS:]
    ranks = [competition["rank"] for competition in window if competition.get("rank") is not None]
    form_score, competition_scores = score_window(window)
    last_competitions = build_last_competitions(window)
    category_counts = Counter(
        competition["category"] for competition in window if competition.get("category")
    )
    source_result_ids = [
        competition["result_id"]
        for competition in window
        if competition.get("result_id") is not None
    ]

    metadata = {
        "source": SOURCE,
        "identity_grouping": "fs_fencer_identities" if used_identity_grouping else "raw_fencer_id",
        "identity_id": identity_id,
        "max_competitions": MAX_RECENT_COMPETITIONS,
        "window_size": len(window),
        "ranked_competitions": len(ranks),
        "missing_rank_competitions": len(window) - len(ranks),
        "category_counts": dict(sorted(category_counts.items())),
        "source_result_ids": source_result_ids,
        "score_components": {
            "formula": "recency-weighted average of max(0, 100 - (rank - 1) * 4) plus medal bonus, capped at 100",
            "rank_score_step": RANK_SCORE_STEP,
            "medal_bonus": MEDAL_BONUS,
            "recency_weights": list(range(1, len(window) + 1)),
            "missing_ranks": "excluded from score denominator but retained in last_competitions",
            "trend_rank_threshold": TREND_RANK_THRESHOLD,
        },
        "competition_scores": competition_scores,
    }
    if not used_identity_grouping:
        metadata["grouping_limitation"] = "Identity table unavailable or fencer not present; grouped by raw fencer_id."

    avg_rank = round_decimal(sum(ranks) / len(ranks)) if ranks else None
    recent_medals = sum(
        1
        for competition in window
        if competition.get("medal") in MEDAL_BONUS
    )

    return {
        "fencer_id": fencer_id,
        "weapon": weapon,
        "last_competitions": last_competitions,
        "form_score": form_score,
        "trend_direction": split_trend_direction(ranks),
        "recent_medals": recent_medals,
        "recent_avg_rank": avg_rank,
        "metadata": metadata,
        "updated_at": now,
    }


def build_form_rows(
    results: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    identity_rows: list[dict[str, Any]] | None = None,
    now: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    now = now or datetime.now(timezone.utc).isoformat()
    tournaments_by_id = tournament_lookup(tournaments)
    identity_map, identity_ids = build_identity_maps(identity_rows)
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    summary = {
        "skipped_missing_fencer": 0,
        "skipped_missing_weapon": 0,
        "skipped_team_results": 0,
        "skipped_incomplete_events": 0,
        "skipped_duplicate_results": 0,
    }

    for index, result in enumerate(results):
        raw_fencer_id = clean_text(result.get("fencer_id"))
        if not raw_fencer_id:
            summary["skipped_missing_fencer"] += 1
            continue

        canonical_id = canonical_fencer_id(raw_fencer_id, identity_map)
        if not canonical_id:
            summary["skipped_missing_fencer"] += 1
            continue

        tournament_id = clean_text(result.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id) if tournament_id else None
        if is_incomplete_event(result, tournament):
            summary["skipped_incomplete_events"] += 1
            continue
        if is_team_event(result, tournament):
            summary["skipped_team_results"] += 1
            continue

        weapon = normalize_weapon(result.get("weapon")) or normalize_weapon(
            tournament.get("weapon") if tournament else None
        )
        if not weapon:
            summary["skipped_missing_weapon"] += 1
            continue

        rank = coerce_rank(result.get("rank") if result.get("rank") is not None else result.get("placement"))
        category = normalize_category(
            result.get("category") or (tournament.get("category") if tournament else None),
            result.get("gender") or (tournament.get("gender") if tournament else None),
        )
        result_id = clean_text(result.get("id")) or f"result:{index}"
        candidate = {
            "result_id": result_id,
            "tournament_id": tournament_id or result_id,
            "fencer_id": canonical_id,
            "raw_fencer_id": raw_fencer_id,
            "weapon": weapon,
            "category": category,
            "rank": rank,
            "medal": result_medal(result, rank),
            "date": competition_date(result, tournament),
            "season": result.get("season") or (tournament.get("season") if tournament else None),
        }
        dedupe_key = (canonical_id, weapon, candidate["tournament_id"])
        if dedupe_key in deduped:
            summary["skipped_duplicate_results"] += 1
            deduped[dedupe_key] = choose_competition(deduped[dedupe_key], candidate)
        else:
            deduped[dedupe_key] = candidate

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for competition in deduped.values():
        grouped[(competition["fencer_id"], competition["weapon"])].append(competition)

    rows = [
        form_row(
            fencer_id,
            weapon,
            competitions,
            identity_id=identity_ids.get(fencer_id),
            used_identity_grouping=fencer_id in identity_ids,
            now=now,
        )
        for (fencer_id, weapon), competitions in sorted(grouped.items())
    ]

    summary["results_used"] = len(deduped)
    summary["skipped"] = sum(value for key, value in summary.items() if key.startswith("skipped_"))
    return rows, summary


def fetch_all(client, table: str, columns: str, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
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


def fetch_with_fallbacks(client, table: str, select_options: tuple[str, ...], page_size: int) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in select_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
            print(f"  Select fallback for {table}: {exc}")
    if last_error:
        raise last_error
    return []


def load_identity_rows(client, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    for columns in IDENTITY_SELECTS:
        try:
            return fetch_all(client, "fs_fencer_identities", columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
            print(f"  Identity select fallback: {exc}")
    print(f"Identity table unavailable; using raw fs_results.fencer_id grouping: {last_error}")
    return []


def batch_upsert(
    client,
    table: str,
    rows: list[dict[str, Any]],
    on_conflict: str,
    batch_size: int = BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table(table).upsert(batch, on_conflict=on_conflict).execute()
        written += len(batch)
    return written


def compute_form_tracker(
    client=None,
    page_size: int = PAGE_SIZE,
    now: str | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size)
        identity_rows = load_identity_rows(client, page_size)
        rows, build_summary = build_form_rows(
            results,
            tournaments,
            identity_rows=identity_rows,
            now=now,
        )
        written = batch_upsert(client, "fs_fencer_form", rows, FORM_CONFLICT_COLUMNS) if rows else 0

        summary = {
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "identity_rows": len(identity_rows),
            "form_rows": len(rows),
            "written": written,
            **build_summary,
        }
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": datetime.now(timezone.utc).isoformat(), **summary})
        if run_log:
            run_log.complete(written=written, failed=0, skipped=summary["skipped"], metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Form tracker computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_form_tracker()
    print(
        "Form tracker computation complete - "
        f"{summary['form_rows']} rows built, {summary['written']} rows upserted, "
        f"{summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()

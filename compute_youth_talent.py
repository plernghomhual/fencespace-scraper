import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_youth_talent"
YOUTH_TALENT_CONFLICT = "fencer_id"

RESULT_SELECTS = (
    "fencer_id,tournament_id,rank,placement,weapon,category,metadata",
    "fencer_id,tournament_id,rank,placement,weapon,category",
    "fencer_id,tournament_id,rank,placement",
)
TOURNAMENT_SELECTS = (
    "id,category,weapon,season,name,type",
    "id,category,weapon,season,name",
    "id,category,weapon",
)
RANKING_SELECTS = (
    "fencer_id,fie_fencer_id,season,weapon,category,rank,points,metadata",
    "fencer_id,season,weapon,category,rank,points",
    "fie_fencer_id,season,weapon,category,rank,points",
)
NATIONAL_RANKING_SELECTS = (
    "fencer_id,fie_id,season,weapon,gender,category,rank,points,metadata",
    "fencer_id,season,weapon,category,rank,points",
)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


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
            break
        offset += page_size
    return rows


def fetch_with_fallbacks(
    client,
    table: str,
    column_options: tuple[str, ...],
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in column_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def fetch_optional_with_fallbacks(
    client,
    table: str,
    column_options: tuple[str, ...],
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    try:
        return fetch_with_fallbacks(client, table, column_options, page_size=page_size)
    except Exception:
        return []


def tournament_lookup(tournaments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in tournaments if row.get("id") is not None}


def metadata_value(row: dict[str, Any], *keys: str) -> Any:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return None
    for key in keys:
        if metadata.get(key) not in (None, ""):
            return metadata.get(key)
    return None


def row_category(row: dict[str, Any], tournament: dict[str, Any] | None = None) -> str | None:
    return clean_text(
        row.get("category")
        or metadata_value(row, "category", "age_category", "event_category")
        or (tournament or {}).get("category")
        or metadata_value(tournament or {}, "category", "age_category", "event_category")
    )


def infer_age_band(category: str | None) -> str | None:
    text = clean_text(category)
    if not text:
        return None
    key = text.lower()
    if any(token in key for token in ("y10", "y12", "y14", "youth", "benjamin", "minime")):
        return "youth"
    if any(token in key for token in ("cadet", "u17", "u16", "under 17", "under-17")):
        return "cadet"
    if any(token in key for token in ("junior", "u20", "u19", "under 20", "under-20")):
        return "junior"
    if any(token in key for token in ("u23", "u21", "under 23", "under-23")):
        return "u23"
    return None


def is_known_non_youth_category(category: str | None) -> bool:
    text = clean_text(category)
    if not text:
        return False
    key = text.lower()
    return any(token in key for token in ("senior", "veteran", "veterans", "master", "open"))


def public_fencer_id(row: dict[str, Any]) -> str | None:
    return clean_text(row.get("fencer_id") or row.get("fie_fencer_id") or row.get("fie_id"))


def placement_from_row(row: dict[str, Any]) -> int | None:
    return coerce_int(row.get("rank") if row.get("rank") is not None else row.get("placement"))


def score_best_result(best_rank: int | None) -> float:
    if best_rank is None:
        return 0.0
    if best_rank == 1:
        return 22.0
    if best_rank <= 3:
        return 18.0
    if best_rank <= 8:
        return 12.0
    if best_rank <= 16:
        return 6.0
    return 0.0


def score_best_ranking(best_rank: int | None) -> float:
    if best_rank is None:
        return 0.0
    if best_rank == 1:
        return 20.0
    if best_rank <= 3:
        return 16.0
    if best_rank <= 8:
        return 12.0
    if best_rank <= 16:
        return 7.0
    if best_rank <= 32:
        return 4.0
    return 0.0


def representative_category(categories: list[str]) -> str:
    if not categories:
        return "Unknown"
    counts = Counter(categories)
    ordered = sorted(counts, key=lambda value: (-counts[value], value))
    return ", ".join(ordered[:3])


def representative_age_band(age_bands: list[str]) -> str:
    unique = sorted(set(age_bands))
    if not unique:
        return "unknown"
    if len(unique) == 1:
        return unique[0]
    return "mixed-youth"


def confidence_for(evidence_count: int, has_category_uncertainty: bool) -> str:
    if has_category_uncertainty or evidence_count < 3:
        return "low"
    if evidence_count >= 5:
        return "high"
    return "medium"


def label_for(score: float, confidence: str) -> str:
    if score >= 70 and confidence != "low":
        return "early-career outlier"
    if score >= 35 and confidence != "low":
        return "monitor with more public results"
    return "insufficient public evidence"


def build_explanation(row: dict[str, Any]) -> str:
    summary = row["feature_summary"]
    flags = row["low_confidence_flags"]
    parts = [
        f"{row['label']}: score {row['outlier_score']} from "
        f"{summary['public_result_count']} public result rows and "
        f"{summary['public_ranking_count']} public ranking rows.",
    ]
    if summary.get("best_result_rank") is not None:
        parts.append(
            f"Best public competition placement was {summary['best_result_rank']} "
            f"with {summary['top8_result_count']} top-8 result(s)."
        )
    if summary.get("best_ranking_rank") is not None:
        parts.append(
            f"Best public youth/category ranking was {summary['best_ranking_rank']} "
            f"with {summary['top8_ranking_count']} top-8 ranking entry(s)."
        )
    if flags:
        parts.append(f"Low confidence flags: {', '.join(flags)}.")
    parts.append(
        "Uses public competition and ranking evidence only; precise age details are "
        "not used or stored, and this is not a prediction."
    )
    return " ".join(parts)


def add_signal(
    signals: dict[str, dict[str, Any]],
    fencer_id: str,
    *,
    source: str,
    category: str | None,
    rank: int,
    points: float | None = None,
) -> None:
    signal = signals[fencer_id]
    signal["entries"].append({"source": source, "category": category, "rank": rank, "points": points})
    if category:
        signal["categories"].append(category)
    age_band = infer_age_band(category)
    if age_band:
        signal["age_bands"].append(age_band)
    else:
        signal["category_uncertain"] = True
    if source == "result":
        signal["result_ranks"].append(rank)
    else:
        signal["ranking_ranks"].append(rank)
        if points is not None:
            signal["ranking_points"].append(points)


def build_youth_talent_rows(
    results: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    ranking_history: list[dict[str, Any]],
    national_rankings: list[dict[str, Any]],
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    tournaments_by_id = tournament_lookup(tournaments)
    signals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "entries": [],
            "categories": [],
            "age_bands": [],
            "result_ranks": [],
            "ranking_ranks": [],
            "ranking_points": [],
            "category_uncertain": False,
        }
    )
    skipped = 0

    for result in results:
        fencer_id = public_fencer_id(result)
        rank = placement_from_row(result)
        tournament = tournaments_by_id.get(str(result.get("tournament_id")))
        category = row_category(result, tournament)
        age_band = infer_age_band(category)

        if not fencer_id or rank is None:
            skipped += 1
            continue
        if category and not age_band and is_known_non_youth_category(category):
            skipped += 1
            continue
        add_signal(signals, fencer_id, source="result", category=category, rank=rank)

    for ranking in [*ranking_history, *national_rankings]:
        fencer_id = public_fencer_id(ranking)
        rank = coerce_int(ranking.get("rank"))
        category = row_category(ranking)
        age_band = infer_age_band(category)

        if not fencer_id or rank is None:
            skipped += 1
            continue
        if category and not age_band and is_known_non_youth_category(category):
            skipped += 1
            continue
        add_signal(
            signals,
            fencer_id,
            source="ranking",
            category=category,
            rank=rank,
            points=coerce_float(ranking.get("points")),
        )

    rows: list[dict[str, Any]] = []
    for fencer_id, signal in sorted(signals.items()):
        result_ranks = signal["result_ranks"]
        ranking_ranks = signal["ranking_ranks"]
        evidence_count = len(signal["entries"])
        podium_count = sum(1 for rank in result_ranks if rank <= 3)
        top8_result_count = sum(1 for rank in result_ranks if rank <= 8)
        top8_ranking_count = sum(1 for rank in ranking_ranks if rank <= 8)
        best_result_rank = min(result_ranks) if result_ranks else None
        best_ranking_rank = min(ranking_ranks) if ranking_ranks else None
        category_uncertain = bool(signal["category_uncertain"] or not signal["age_bands"])
        sparse_public_data = evidence_count < 3

        score = 0.0
        score += min(20.0, evidence_count * 3.0)
        score += score_best_result(best_result_rank)
        score += min(16.0, podium_count * 6.0)
        score += min(12.0, top8_result_count * 3.0)
        score += score_best_ranking(best_ranking_rank)
        score += min(10.0, top8_ranking_count * 3.0)
        if result_ranks and ranking_ranks:
            score += 8.0
        if category_uncertain:
            score *= 0.75
        if sparse_public_data:
            score *= 0.70

        low_confidence_flags: list[str] = []
        if category_uncertain:
            low_confidence_flags.append("age_category_uncertain")
        if sparse_public_data:
            low_confidence_flags.append("sparse_public_data")

        confidence = confidence_for(evidence_count, category_uncertain)
        rounded_score = round_score(score)
        row = {
            "fencer_id": fencer_id,
            "age_band": representative_age_band(signal["age_bands"]),
            "category": representative_category(signal["categories"]),
            "feature_summary": {
                "public_result_count": len(result_ranks),
                "public_ranking_count": len(ranking_ranks),
                "best_result_rank": best_result_rank,
                "best_ranking_rank": best_ranking_rank,
                "podium_result_count": podium_count,
                "top8_result_count": top8_result_count,
                "top8_ranking_count": top8_ranking_count,
                "best_ranking_points": max(signal["ranking_points"]) if signal["ranking_points"] else None,
                "categories": sorted(set(signal["categories"])),
                "age_bands": sorted(set(signal["age_bands"])),
                "interpretation_limits": [
                    "public_competition_and_ranking_rows_only",
                    "not_a_prediction",
                    "no_precise_age_details_used_or_stored",
                ],
            },
            "outlier_score": rounded_score,
            "label": label_for(rounded_score, confidence),
            "confidence": confidence,
            "low_confidence_flags": low_confidence_flags,
            "updated_at": updated_at,
        }
        row["explanation"] = build_explanation(row)
        rows.append(row)

    return rows, skipped


def upsert_youth_talent_rows(client, rows: list[dict[str, Any]]) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index : index + BATCH_SIZE]
        try:
            client.table("fs_youth_talent_analytics").upsert(
                batch,
                on_conflict=YOUTH_TALENT_CONFLICT,
            ).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_youth_talent_analytics upsert batch {index // BATCH_SIZE} failed: {exc}")
    return written, failed


def compute_youth_talent(
    client=None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    updated_at: str | None = None,
) -> dict[str, int]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    try:
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
        ranking_history = fetch_optional_with_fallbacks(
            client,
            "fs_rankings_history",
            RANKING_SELECTS,
            page_size=page_size,
        )
        national_rankings = fetch_optional_with_fallbacks(
            client,
            "fs_national_fed_rankings",
            NATIONAL_RANKING_SELECTS,
            page_size=page_size,
        )
        analytics_rows, skipped = build_youth_talent_rows(
            results,
            tournaments,
            ranking_history,
            national_rankings,
            updated_at=updated_at,
        )
        written, failed = upsert_youth_talent_rows(client, analytics_rows)

        summary = {
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "ranking_rows_read": len(ranking_history) + len(national_rankings),
            "analytics_rows": len(analytics_rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
        }
        if update_state:
            set_state(SOURCE, "last_summary", summary)
        if run_log:
            run_log.complete(written, failed, skipped)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


if __name__ == "__main__":
    print(compute_youth_talent())

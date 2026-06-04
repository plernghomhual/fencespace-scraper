import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_anomalies"
MODEL_VERSION = "sports_integrity_v1"

BOUT_SELECT = "id,tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b"
FENCER_SELECT = "id,world_rank"
TOURNAMENT_SELECT = "id,weapon,name,start_date,end_date"
ANOMALY_SELECT = "bout_id,anomaly_type,model_version,reviewed"
ANOMALY_CONFLICT = "bout_id,anomaly_type,model_version"

MIN_SAMPLE_SIZE = 10
MIN_RANKED_SAMPLE_SIZE = 10
SCORELINE_MARGIN_FLOOR = 8
SCORELINE_ROBUST_Z_FLOOR = 4.0
RANK_DELTA_FLOOR = 75
REPEATED_UNUSUAL_COUNT = 3
REPEATED_FENCER_BOUTS = 4
PUBLIC_BETTING_PROBABILITY_FLOOR = 0.80

INTEGRITY_NOTE = "Statistical sports-integrity review signal; not proof of wrongdoing."


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
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number


def coerce_rank(value: Any) -> int | None:
    number = coerce_int(value)
    return number if number and number > 0 else None


def coerce_probability(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    if probability > 1:
        probability = probability / 100
    if probability < 0 or probability > 1:
        return None
    return probability


def round_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def population_stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return variance ** 0.5


def robust_zscore(value: float, values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    center = median(values)
    deviations = [abs(item - center) for item in values]
    mad = median(deviations)
    if mad > 0:
        return 0.6745 * (value - center) / mad
    stddev = population_stddev(values)
    if stddev <= 0:
        return 0.0
    mean = sum(values) / len(values)
    return (value - mean) / stddev


def fencer_rank_lookup(fencers: list[dict[str, Any]]) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for row in fencers:
        fencer_id = clean_text(row.get("id"))
        rank = coerce_rank(row.get("world_rank"))
        if fencer_id and rank is not None:
            ranks[fencer_id] = rank
    return ranks


def tournament_lookup(tournaments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def dedupe_key(bout: dict[str, Any]) -> tuple[Any, ...]:
    bout_id = clean_text(bout.get("id"))
    if bout_id:
        return ("id", bout_id)

    fencer_a = clean_text(bout.get("fencer_a_id"))
    fencer_b = clean_text(bout.get("fencer_b_id"))
    pair = tuple(sorted([fencer_a or "", fencer_b or ""]))
    return (
        "signature",
        clean_text(bout.get("tournament_id")),
        pair,
        clean_text(bout.get("winner_id")),
        coerce_int(bout.get("score_a")),
        coerce_int(bout.get("score_b")),
    )


def normalize_valid_bout(bout: dict[str, Any]) -> dict[str, Any] | None:
    bout_id = clean_text(bout.get("id"))
    tournament_id = clean_text(bout.get("tournament_id"))
    fencer_a = clean_text(bout.get("fencer_a_id"))
    fencer_b = clean_text(bout.get("fencer_b_id"))
    winner_id = clean_text(bout.get("winner_id"))
    score_a = coerce_int(bout.get("score_a"))
    score_b = coerce_int(bout.get("score_b"))

    if (
        not bout_id
        or not tournament_id
        or not fencer_a
        or not fencer_b
        or fencer_a == fencer_b
        or winner_id not in {fencer_a, fencer_b}
        or score_a is None
        or score_b is None
        or score_a < 0
        or score_b < 0
        or score_a == score_b
        or max(score_a, score_b) > 45
    ):
        return None

    if winner_id == fencer_a:
        winner_score = score_a
        loser_score = score_b
        opponent_id = fencer_b
    else:
        winner_score = score_b
        loser_score = score_a
        opponent_id = fencer_a

    if winner_score <= loser_score:
        return None

    return {
        "id": bout_id,
        "tournament_id": tournament_id,
        "fencer_a": fencer_a,
        "fencer_b": fencer_b,
        "winner_id": winner_id,
        "opponent_id": opponent_id,
        "score_a": score_a,
        "score_b": score_b,
        "winner_score": winner_score,
        "loser_score": loser_score,
        "margin": winner_score - loser_score,
        "metadata": bout.get("metadata") if isinstance(bout.get("metadata"), dict) else {},
    }


def prepare_bouts(bouts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[tuple[Any, ...]] = set()
    valid: list[dict[str, Any]] = []
    skipped = 0

    for bout in bouts:
        key = dedupe_key(bout)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)

        normalized = normalize_valid_bout(bout)
        if normalized is None:
            skipped += 1
            continue
        valid.append(normalized)

    return valid, skipped


def make_evidence(
    *,
    indicator: str,
    confidence_level: str,
    sample_size: int,
    features: dict[str, Any],
    source_fields: list[str],
) -> dict[str, Any]:
    return {
        "indicator": indicator,
        "confidence_level": confidence_level,
        "integrity_note": INTEGRITY_NOTE,
        "sample_size": sample_size,
        "features": features,
        "source_fields": source_fields,
        "model_version": MODEL_VERSION,
    }


def make_row(
    bout: dict[str, Any],
    *,
    anomaly_type: str,
    score: float,
    confidence_level: str,
    evidence: dict[str, Any],
    fencer_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    return {
        "bout_id": bout["id"],
        "tournament_id": bout["tournament_id"],
        "fencer_id": fencer_id or bout["winner_id"],
        "anomaly_type": anomaly_type,
        "score": round_score(score),
        "confidence_level": confidence_level,
        "evidence": evidence,
        "model_version": MODEL_VERSION,
        "reviewed": False,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }


def scoreline_rows(
    bouts: list[dict[str, Any]],
    created_at: str | None,
) -> list[dict[str, Any]]:
    if len(bouts) < MIN_SAMPLE_SIZE:
        return []

    margins = [float(bout["margin"]) for bout in bouts]
    rows: list[dict[str, Any]] = []
    for bout in bouts:
        margin = float(bout["margin"])
        zscore = robust_zscore(margin, margins)
        if margin < SCORELINE_MARGIN_FLOOR or zscore < SCORELINE_ROBUST_Z_FLOOR:
            continue

        confidence = "high" if zscore >= 7 or margin >= 12 else "medium"
        evidence = make_evidence(
            indicator="scoreline_outlier",
            confidence_level=confidence,
            sample_size=len(bouts),
            features={
                "winner_score": bout["winner_score"],
                "loser_score": bout["loser_score"],
                "margin": bout["margin"],
                "margin_robust_z": round(zscore, 2),
            },
            source_fields=[
                "fs_bouts.score_a",
                "fs_bouts.score_b",
                "fs_bouts.winner_id",
            ],
        )
        rows.append(
            make_row(
                bout,
                anomaly_type="scoreline_outlier",
                score=55 + (zscore * 4) + margin,
                confidence_level=confidence,
                evidence=evidence,
                created_at=created_at,
            )
        )
    return rows


def ranking_rows(
    bouts: list[dict[str, Any]],
    fencer_ranks: dict[str, int],
    created_at: str | None,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    ranked_bouts = [
        bout
        for bout in bouts
        if bout["winner_id"] in fencer_ranks and bout["opponent_id"] in fencer_ranks
    ]
    if len(ranked_bouts) < MIN_RANKED_SAMPLE_SIZE:
        return [], {}

    rows: list[dict[str, Any]] = []
    unusual_by_fencer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bout in ranked_bouts:
        winner_rank = fencer_ranks[bout["winner_id"]]
        opponent_rank = fencer_ranks[bout["opponent_id"]]
        rank_delta = winner_rank - opponent_rank
        if rank_delta < RANK_DELTA_FLOOR:
            continue

        confidence = "high" if rank_delta >= 150 else "medium"
        evidence = make_evidence(
            indicator="ranking_result_delta",
            confidence_level=confidence,
            sample_size=len(ranked_bouts),
            features={
                "winner_world_rank": winner_rank,
                "opponent_world_rank": opponent_rank,
                "rank_delta": rank_delta,
                "winner_score": bout["winner_score"],
                "loser_score": bout["loser_score"],
                "margin": bout["margin"],
            },
            source_fields=[
                "fs_fencers.world_rank",
                "fs_bouts.winner_id",
                "fs_bouts.score_a",
                "fs_bouts.score_b",
            ],
        )
        rows.append(
            make_row(
                bout,
                anomaly_type="ranking_result_delta",
                score=50 + (rank_delta * 0.22) + bout["margin"],
                confidence_level=confidence,
                evidence=evidence,
                created_at=created_at,
            )
        )
        unusual_by_fencer[bout["winner_id"]].append(bout)

    return rows, unusual_by_fencer


def repeated_pattern_rows(
    bouts: list[dict[str, Any]],
    unusual_by_fencer: dict[str, list[dict[str, Any]]],
    created_at: str | None,
) -> list[dict[str, Any]]:
    if len(bouts) < MIN_SAMPLE_SIZE:
        return []

    bout_counts: dict[str, int] = defaultdict(int)
    for bout in bouts:
        bout_counts[bout["winner_id"]] += 1
        bout_counts[bout["opponent_id"]] += 1

    rows: list[dict[str, Any]] = []
    for fencer_id, unusual_bouts in sorted(unusual_by_fencer.items()):
        fencer_bout_count = bout_counts.get(fencer_id, 0)
        unusual_count = len(unusual_bouts)
        if unusual_count < REPEATED_UNUSUAL_COUNT or fencer_bout_count < REPEATED_FENCER_BOUTS:
            continue
        if unusual_count / fencer_bout_count < 0.5:
            continue

        representative = unusual_bouts[0]
        confidence = "high" if unusual_count >= 4 else "medium"
        evidence = make_evidence(
            indicator="repeated_unusual_pattern",
            confidence_level=confidence,
            sample_size=len(bouts),
            features={
                "fencer_bout_count": fencer_bout_count,
                "unusual_bout_count": unusual_count,
                "unusual_rate": round(unusual_count / fencer_bout_count, 2),
                "bout_ids": [bout["id"] for bout in unusual_bouts],
            },
            source_fields=[
                "fs_bouts.fencer_a_id",
                "fs_bouts.fencer_b_id",
                "fs_bouts.winner_id",
                "fs_fencers.world_rank",
            ],
        )
        rows.append(
            make_row(
                representative,
                anomaly_type="repeated_unusual_pattern",
                score=60 + (unusual_count * 8),
                confidence_level=confidence,
                evidence=evidence,
                fencer_id=fencer_id,
                created_at=created_at,
            )
        )
    return rows


def public_betting_payload(bout: dict[str, Any]) -> dict[str, Any] | None:
    metadata = bout.get("metadata")
    if not isinstance(metadata, dict):
        return None

    payload = metadata.get("public_betting")
    if not isinstance(payload, dict):
        payload = metadata.get("betting_market")
    if not isinstance(payload, dict):
        return None

    if payload.get("lawful_public") is not True:
        return None

    source_url = clean_text(payload.get("source_url"))
    favorite_id = clean_text(
        payload.get("favorite_fencer_id")
        or payload.get("favorite_id")
        or payload.get("pre_bout_favorite_id")
    )
    probability = coerce_probability(
        payload.get("favorite_implied_probability")
        if payload.get("favorite_implied_probability") is not None
        else payload.get("favorite_probability")
    )

    if not source_url or not favorite_id or probability is None:
        return None
    return {
        "source_url": source_url,
        "favorite_fencer_id": favorite_id,
        "favorite_implied_probability": probability,
    }


def betting_rows(
    bouts: list[dict[str, Any]],
    created_at: str | None,
) -> list[dict[str, Any]]:
    if len(bouts) < MIN_SAMPLE_SIZE:
        return []

    rows: list[dict[str, Any]] = []
    for bout in bouts:
        payload = public_betting_payload(bout)
        if not payload:
            continue
        if payload["favorite_fencer_id"] == bout["winner_id"]:
            continue
        if payload["favorite_implied_probability"] < PUBLIC_BETTING_PROBABILITY_FLOOR:
            continue

        probability = payload["favorite_implied_probability"]
        confidence = "medium" if probability >= 0.9 else "low"
        evidence = make_evidence(
            indicator="public_betting_data_mismatch",
            confidence_level=confidence,
            sample_size=len(bouts),
            features={
                "favorite_fencer_id": payload["favorite_fencer_id"],
                "winner_id": bout["winner_id"],
                "favorite_implied_probability": round(probability, 3),
                "source_url": payload["source_url"],
            },
            source_fields=[
                "fs_bouts.metadata.public_betting.lawful_public",
                "fs_bouts.metadata.public_betting.source_url",
                "fs_bouts.metadata.public_betting.favorite_fencer_id",
                "fs_bouts.metadata.public_betting.favorite_implied_probability",
            ],
        )
        rows.append(
            make_row(
                bout,
                anomaly_type="public_betting_data_mismatch",
                score=50 + (probability * 40),
                confidence_level=confidence,
                evidence=evidence,
                created_at=created_at,
            )
        )
    return rows


def build_anomaly_rows(
    bouts: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    created_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    valid_bouts, skipped = prepare_bouts(bouts)
    if len(valid_bouts) < MIN_SAMPLE_SIZE:
        return [], skipped

    fencer_ranks = fencer_rank_lookup(fencers)
    tournaments_by_id = tournament_lookup(tournaments)
    valid_bouts = [
        {**bout, "tournament": tournaments_by_id.get(bout["tournament_id"], {})}
        for bout in valid_bouts
    ]

    rows: list[dict[str, Any]] = []
    rows.extend(scoreline_rows(valid_bouts, created_at))
    ranked_rows, unusual_by_fencer = ranking_rows(valid_bouts, fencer_ranks, created_at)
    rows.extend(ranked_rows)
    rows.extend(repeated_pattern_rows(valid_bouts, unusual_by_fencer, created_at))
    # fs_bouts.metadata removed from schema; public_betting_data_mismatch disabled until restored
    # rows.extend(betting_rows(valid_bouts, created_at))

    rows.sort(key=lambda row: (row["bout_id"], row["anomaly_type"]))
    return rows, skipped


def fetch_all(
    client,
    table: str,
    columns: str,
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


def upsert_anomaly_rows(
    client,
    rows: list[dict[str, Any]],
    batch_size: int = BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_bout_anomalies").upsert(
            batch,
            on_conflict=ANOMALY_CONFLICT,
        ).execute()
        written += len(batch)
    return written


def anomaly_key(row: dict[str, Any]) -> tuple[str, str, str] | None:
    bout_id = clean_text(row.get("bout_id"))
    anomaly_type = clean_text(row.get("anomaly_type"))
    model_version = clean_text(row.get("model_version"))
    if not bout_id or not anomaly_type or not model_version:
        return None
    return (bout_id, anomaly_type, model_version)


def fetch_reviewed_anomaly_keys(
    client,
    page_size: int = PAGE_SIZE,
) -> set[tuple[str, str, str]]:
    rows = fetch_all(client, "fs_bout_anomalies", ANOMALY_SELECT, page_size=page_size)
    keys: set[tuple[str, str, str]] = set()
    for row in rows:
        key = anomaly_key(row)
        if key and row.get("reviewed") is True:
            keys.add(key)
    return keys


def filter_reviewed_anomalies(
    rows: list[dict[str, Any]],
    reviewed_keys: set[tuple[str, str, str]],
) -> tuple[list[dict[str, Any]], int]:
    writable: list[dict[str, Any]] = []
    preserved = 0
    for row in rows:
        key = anomaly_key(row)
        if key in reviewed_keys:
            preserved += 1
            continue
        writable.append(row)
    return writable, preserved


def compute_anomalies(
    client=None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    created_at: str | None = None,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        bouts = fetch_all(client, "fs_bouts", BOUT_SELECT, page_size=page_size)
        fencers = fetch_all(client, "fs_fencers", FENCER_SELECT, page_size=page_size)
        tournaments = fetch_all(client, "fs_tournaments", TOURNAMENT_SELECT, page_size=page_size)
        rows, skipped = build_anomaly_rows(
            bouts,
            fencers,
            tournaments,
            created_at=created_at,
        )
        reviewed_keys = (
            fetch_reviewed_anomaly_keys(client, page_size=page_size)
            if rows
            else set()
        )
        writable_rows, reviewed_preserved = filter_reviewed_anomalies(rows, reviewed_keys)
        written = upsert_anomaly_rows(client, writable_rows) if writable_rows else 0
        summary = {
            "bouts_read": len(bouts),
            "fencers_read": len(fencers),
            "tournaments_read": len(tournaments),
            "anomalies_built": len(rows),
            "written": written,
            "reviewed_preserved": reviewed_preserved,
            "skipped": skipped,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {"updated_at": datetime.now(timezone.utc).isoformat(), **summary},
            )
        if run_log:
            run_log.complete(written=written, failed=0, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous anomaly computation state: {previous_state}")

    print(f"Anomaly computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_anomalies()
    print(
        "Anomaly computation complete - "
        f"{summary['anomalies_built']} review signals built, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} bouts skipped"
    )


if __name__ == "__main__":
    main()

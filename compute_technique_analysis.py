import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_technique_analysis"
TECHNIQUE_CONFLICT = "fencer_id,weapon"
MINIMUM_BOUTS_FOR_CLAIMS = 5
HIGH_CONFIDENCE_BOUTS = 12
HIGH_CONFIDENCE_RESULTS = 3
USE_LLM_SUMMARIES = False

BOUT_SELECTS = (
    "id,tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,round",
    "id,tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b",
)
RESULT_SELECTS = (
    "tournament_id,fencer_id,rank,placement,weapon",
    "tournament_id,fencer_id,rank,placement",
    "tournament_id,fencer_id,rank",
)
TOURNAMENT_SELECTS = (
    "id,weapon",
)
FENCER_SELECTS = (
    "id,weapon,bio_text,metadata,handedness,dominant_hand,hand",
    "id,weapon,bio_text,metadata",
    "id,weapon,metadata",
    "id,weapon",
)
IDENTITY_SELECTS = (
    "canonical_id,fs_fencer_row_ids",
    "id,canonical_id,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
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


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def normalize_uuid(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return str(uuid.UUID(text))
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def round_metric(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def pct(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round_metric(part / total * 100)


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


def parse_identity_members(value: Any) -> list[str]:
    value = parse_jsonish(value)
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return sorted({member for item in value if (member := normalize_uuid(item))})


def build_identity_map(identity_rows: list[dict[str, Any]]) -> dict[str, str]:
    identity_map: dict[str, str] = {}
    for row in identity_rows:
        members = parse_identity_members(
            row.get("fs_fencer_row_ids")
            or row.get("fencer_ids")
            or row.get("source_fencer_ids")
        )
        canonical = normalize_uuid(row.get("canonical_id"))
        row_id = normalize_uuid(row.get("id"))
        if not canonical and row_id and row_id in members:
            canonical = row_id
        if not canonical and members:
            canonical = members[0]
        if not canonical:
            continue

        identity_map[canonical] = canonical
        for member in members:
            identity_map[member] = canonical
    return identity_map


def load_identity_map(client, page_size: int = PAGE_SIZE) -> tuple[dict[str, str], int]:
    last_error: Exception | None = None
    for columns in IDENTITY_SELECTS:
        try:
            rows = fetch_all(client, "fs_fencer_identities", columns, page_size=page_size)
            return build_identity_map(rows), len(rows)
        except Exception as exc:
            last_error = exc
    print(f"Identity table unavailable; using raw fencer ids: {last_error}")
    return {}, 0


def canonical_fencer_id(value: Any, identity_map: dict[str, str] | None) -> str | None:
    fencer_id = normalize_uuid(value)
    if not fencer_id:
        return None
    if identity_map:
        return identity_map.get(fencer_id, fencer_id)
    return fencer_id


def tournament_lookup(tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def fencer_lookup(
    fencers: list[dict[str, Any]], identity_map: dict[str, str] | None
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in fencers:
        fencer_id = canonical_fencer_id(row.get("id"), identity_map)
        raw_id = normalize_uuid(row.get("id"))
        if not fencer_id:
            continue
        rows.setdefault(fencer_id, row)
        if raw_id:
            rows.setdefault(raw_id, row)
    return rows


def metadata_dict(row: dict[str, Any]) -> dict[str, Any]:
    metadata = parse_jsonish(row.get("metadata"))
    return metadata if isinstance(metadata, dict) else {}


def handedness_from_text(text: Any) -> str | None:
    cleaned = clean_text(text)
    if not cleaned:
        return None
    lowered = cleaned.casefold()
    if re.search(r"\bleft[- ]?handed\b", lowered) or re.search(r"\bleft hand\b", lowered):
        return "left"
    if re.search(r"\bright[- ]?handed\b", lowered) or re.search(r"\bright hand\b", lowered):
        return "right"
    if lowered in {"left", "l"}:
        return "left"
    if lowered in {"right", "r"}:
        return "right"
    return None


def extract_handedness(row: dict[str, Any]) -> dict[str, Any] | None:
    sources: list[str] = []
    values: list[str] = []

    for key in ("handedness", "dominant_hand", "hand"):
        value = handedness_from_text(row.get(key))
        if value:
            values.append(value)
            sources.append(key)

    metadata = metadata_dict(row)
    for key in ("handedness", "dominant_hand", "hand"):
        value = handedness_from_text(metadata.get(key))
        if value:
            values.append(value)
            sources.append(f"metadata.{key}")

    bio_value = handedness_from_text(row.get("bio_text"))
    if bio_value:
        values.append(bio_value)
        sources.append("bio_text")

    if not values:
        return None

    unique_values = sorted(set(values))
    if len(unique_values) > 1:
        return {"value": "conflicting", "source_fields": sorted(set(sources))}
    return {"value": unique_values[0], "source_fields": sorted(set(sources))}


def merge_profile(existing: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    if not merged.get("weapon"):
        merged["weapon"] = normalize_weapon(row.get("weapon"))
    if not merged.get("handedness"):
        merged["handedness"] = extract_handedness(row)
    return merged


def build_profiles(
    fencers: list[dict[str, Any]], identity_map: dict[str, str] | None
) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for row in fencers:
        fencer_id = canonical_fencer_id(row.get("id"), identity_map)
        if not fencer_id:
            continue
        current = profiles.get(fencer_id, {})
        profiles[fencer_id] = merge_profile(current, row)
    return profiles


def classify_round(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold()
    if any(token in key for token in ("poule", "pool")):
        return "pool"
    if any(
        token in key
        for token in (
            "tableau",
            "table of",
            "direct elimination",
            "elimination",
            "final",
            "semifinal",
            "quarterfinal",
            "round of",
        )
    ):
        return "de"
    if re.search(r"\ba(128|64|32|16|8|4|2)\b", key):
        return "de"
    return None


def result_weapon(
    result: dict[str, Any],
    tournaments_by_id: dict[str, dict[str, Any]],
    fencers_by_id: dict[str, dict[str, Any]],
    identity_map: dict[str, str] | None,
) -> str | None:
    weapon = normalize_weapon(result.get("weapon"))
    if weapon:
        return weapon

    tournament_id = result.get("tournament_id")
    tournament = tournaments_by_id.get(str(tournament_id)) if tournament_id is not None else None
    weapon = normalize_weapon(tournament.get("weapon")) if tournament else None
    if weapon:
        return weapon

    fencer_id = canonical_fencer_id(result.get("fencer_id"), identity_map)
    fencer = fencers_by_id.get(fencer_id) if fencer_id else None
    return normalize_weapon(fencer.get("weapon")) if fencer else None


def bout_weapon(
    bout: dict[str, Any],
    tournaments_by_id: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    fencer_ids: tuple[str | None, str | None],
) -> str | None:
    weapon = normalize_weapon(bout.get("weapon"))
    if weapon:
        return weapon

    tournament_id = bout.get("tournament_id")
    tournament = tournaments_by_id.get(str(tournament_id)) if tournament_id is not None else None
    weapon = normalize_weapon(tournament.get("weapon")) if tournament else None
    if weapon:
        return weapon

    profile_weapons = {
        profiles[fencer_id]["weapon"]
        for fencer_id in fencer_ids
        if fencer_id in profiles and profiles[fencer_id].get("weapon")
    }
    if len(profile_weapons) == 1:
        return profile_weapons.pop()
    return None


def empty_phase() -> dict[str, int]:
    return {"bouts": 0, "wins": 0, "touches_for": 0, "touches_against": 0}


def new_stats() -> dict[str, Any]:
    return {
        "bouts": 0,
        "wins": 0,
        "losses": 0,
        "touches_for": 0,
        "touches_against": 0,
        "close_bouts": 0,
        "close_wins": 0,
        "comeback_sample_count": 0,
        "comeback_wins": 0,
        "results_count": 0,
        "result_ranks": [],
        "pool": empty_phase(),
        "de": empty_phase(),
    }


def ensure_stats(
    grouped: dict[tuple[str, str], dict[str, Any]],
    fencer_id: str,
    weapon: str,
) -> dict[str, Any]:
    return grouped.setdefault((fencer_id, weapon), new_stats())


def comeback_winner_id(
    bout: dict[str, Any], identity_map: dict[str, str] | None
) -> str | None:
    metadata = metadata_dict(bout)
    sources = [bout, metadata]
    for source in sources:
        for key in ("comeback_winner_id", "comeback_fencer_id"):
            winner = canonical_fencer_id(source.get(key), identity_map)
            if winner:
                return winner

    for source in sources:
        if source.get("was_comeback") is True:
            return canonical_fencer_id(source.get("winner_id") or bout.get("winner_id"), identity_map) or ""
        if source.get("was_comeback") is False:
            return ""
    return None


def update_side_stats(
    stats: dict[str, Any],
    score_for: int,
    score_against: int,
    won: bool,
    lost: bool,
    phase: str | None,
    comeback_winner: str | None,
    fencer_id: str,
) -> None:
    stats["bouts"] += 1
    stats["touches_for"] += score_for
    stats["touches_against"] += score_against
    if won:
        stats["wins"] += 1
    if lost:
        stats["losses"] += 1

    if abs(score_for - score_against) <= 1:
        stats["close_bouts"] += 1
        if won:
            stats["close_wins"] += 1

    if phase in {"pool", "de"}:
        phase_stats = stats[phase]
        phase_stats["bouts"] += 1
        phase_stats["touches_for"] += score_for
        phase_stats["touches_against"] += score_against
        if won:
            phase_stats["wins"] += 1

    if comeback_winner is not None:
        stats["comeback_sample_count"] += 1
        if comeback_winner == fencer_id:
            stats["comeback_wins"] += 1


def phase_metrics(stats: dict[str, int]) -> dict[str, Any]:
    bouts = stats["bouts"]
    touches_for = stats["touches_for"]
    touches_against = stats["touches_against"]
    differential = touches_for - touches_against
    return {
        "bouts": bouts,
        "wins": stats["wins"],
        "win_rate": pct(stats["wins"], bouts),
        "touch_differential": differential,
        "touch_diff_per_bout": round_metric(differential / bouts) if bouts else None,
    }


def base_metrics(stats: dict[str, Any]) -> dict[str, Any]:
    bouts = stats["bouts"]
    differential = stats["touches_for"] - stats["touches_against"]
    ranks = stats["result_ranks"]
    metrics = {
        "bouts_analyzed": bouts,
        "results_analyzed": stats["results_count"],
        "wins": stats["wins"],
        "losses": stats["losses"],
        "win_rate": pct(stats["wins"], bouts),
        "touches_for": stats["touches_for"],
        "touches_against": stats["touches_against"],
        "touch_differential": differential,
        "touch_diff_per_bout": round_metric(differential / bouts) if bouts else None,
        "close_bouts": stats["close_bouts"],
        "close_bout_rate": pct(stats["close_bouts"], bouts),
        "close_win_rate": pct(stats["close_wins"], stats["close_bouts"]),
        "pool": phase_metrics(stats["pool"]),
        "de": phase_metrics(stats["de"]),
        "comeback": {
            "sample_count": stats["comeback_sample_count"],
            "wins": stats["comeback_wins"],
            "rate": pct(stats["comeback_wins"], stats["comeback_sample_count"]),
        },
        "claims": {},
    }
    if ranks:
        metrics["results"] = {
            "ranked_results": len(ranks),
            "best_rank": min(ranks),
            "avg_rank": round_metric(sum(ranks) / len(ranks)),
        }
    return metrics


def make_claim(claim_id: str, claim: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"id": claim_id, "claim": claim, "evidence": evidence}


def build_claims(metrics: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    strengths: list[dict[str, Any]] = []
    weaknesses: list[dict[str, Any]] = []
    bouts = metrics["bouts_analyzed"]
    if bouts < MINIMUM_BOUTS_FOR_CLAIMS:
        return strengths, weaknesses

    diff_per_bout = metrics["touch_diff_per_bout"] or 0.0
    if diff_per_bout >= 1.5:
        strengths.append(
            make_claim(
                "positive_touch_differential",
                "Recorded touch differential is positive across scored bouts.",
                {
                    "bouts_analyzed": bouts,
                    "touch_differential": metrics["touch_differential"],
                    "touch_diff_per_bout": diff_per_bout,
                },
            )
        )
    elif diff_per_bout <= -1.5:
        weaknesses.append(
            make_claim(
                "negative_touch_differential",
                "Recorded touch differential is negative across scored bouts.",
                {
                    "bouts_analyzed": bouts,
                    "touch_differential": metrics["touch_differential"],
                    "touch_diff_per_bout": diff_per_bout,
                },
            )
        )

    for phase_key, label in (("pool", "pool"), ("de", "direct-elimination")):
        phase = metrics[phase_key]
        phase_bouts = phase["bouts"]
        win_rate = phase["win_rate"]
        phase_diff = phase["touch_diff_per_bout"] or 0.0
        if phase_bouts < 3 or win_rate is None:
            continue
        evidence = {
            "bouts_analyzed": bouts,
            f"{phase_key}_bouts": phase_bouts,
            f"{phase_key}_win_rate": win_rate,
            f"{phase_key}_touch_diff_per_bout": phase_diff,
        }
        if win_rate >= 60.0 and phase_diff >= 1.0:
            strengths.append(
                make_claim(
                    f"{phase_key}_positive_pattern",
                    f"Recorded {label} bouts show a positive result pattern.",
                    evidence,
                )
            )
        elif win_rate <= 40.0 and phase_diff <= -1.0:
            weaknesses.append(
                make_claim(
                    f"{phase_key}_negative_pattern",
                    f"Recorded {label} bouts show a negative result pattern.",
                    evidence,
                )
            )

    close_bouts = metrics["close_bouts"]
    close_win_rate = metrics["close_win_rate"]
    if close_bouts >= 2 and close_win_rate is not None:
        evidence = {
            "bouts_analyzed": bouts,
            "close_bouts": close_bouts,
            "close_bout_rate": metrics["close_bout_rate"],
            "close_win_rate": close_win_rate,
        }
        if close_win_rate >= 60.0:
            strengths.append(
                make_claim(
                    "close_bout_conversion",
                    "Recorded close bouts show above-even conversion.",
                    evidence,
                )
            )
        elif close_win_rate <= 40.0:
            weaknesses.append(
                make_claim(
                    "close_bout_conversion_risk",
                    "Recorded close bouts show below-even conversion.",
                    evidence,
                )
            )

    comeback = metrics["comeback"]
    comeback_rate = comeback["rate"]
    if comeback["sample_count"] >= 3 and comeback_rate is not None:
        evidence = {
            "bouts_analyzed": bouts,
            "comeback_sample_count": comeback["sample_count"],
            "comeback_rate": comeback_rate,
        }
        if comeback_rate >= 50.0:
            strengths.append(
                make_claim(
                    "tagged_comeback_conversion",
                    "Recorded tagged comeback bouts show above-even conversion.",
                    evidence,
                )
            )
        elif comeback_rate <= 20.0:
            weaknesses.append(
                make_claim(
                    "tagged_comeback_conversion_risk",
                    "Recorded tagged comeback bouts show limited conversion.",
                    evidence,
                )
            )

    return strengths, weaknesses


def confidence_for(metrics: dict[str, Any]) -> str:
    bouts = metrics["bouts_analyzed"]
    results = metrics["results_analyzed"]
    if bouts < MINIMUM_BOUTS_FOR_CLAIMS:
        return "low"
    if bouts >= HIGH_CONFIDENCE_BOUTS and results >= HIGH_CONFIDENCE_RESULTS:
        return "high"
    return "medium"


def low_data_row(
    fencer_id: str,
    weapon: str,
    stats: dict[str, Any],
    profile: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    evidence_metrics: dict[str, Any] = {
        "bouts_analyzed": stats["bouts"],
        "results_analyzed": stats["results_count"],
        "reason": "insufficient_recorded_data",
        "minimum_bouts_for_claims": MINIMUM_BOUTS_FOR_CLAIMS,
        "claims": {},
    }
    if profile.get("handedness"):
        evidence_metrics["handedness"] = profile["handedness"]

    return {
        "fencer_id": fencer_id,
        "weapon": weapon,
        "pattern_summary": (
            "Low-confidence data-pattern insight: not enough recorded bouts "
            "or results for a conservative technique-style analysis."
        ),
        "strengths": [],
        "weaknesses": [],
        "evidence_metrics": evidence_metrics,
        "confidence": "low",
        "updated_at": updated_at,
    }


def pattern_summary(weapon: str, metrics: dict[str, Any]) -> str:
    parts = [
        f"Data-pattern insight for {weapon}: {metrics['bouts_analyzed']} recorded bouts analyzed.",
        (
            f"Touch differential {metrics['touch_differential']} "
            f"({metrics['touch_diff_per_bout']} per bout)."
        ),
    ]

    pool = metrics["pool"]
    if pool["bouts"]:
        parts.append(f"Pool win rate {pool['win_rate']}% over {pool['bouts']} recorded bouts.")

    de = metrics["de"]
    if de["bouts"]:
        parts.append(
            f"Direct-elimination win rate {de['win_rate']}% over {de['bouts']} recorded bouts."
        )

    if metrics["close_bouts"]:
        parts.append(
            f"Close-bout rate {metrics['close_bout_rate']}%; "
            f"close-bout win rate {metrics['close_win_rate']}%."
        )

    comeback = metrics["comeback"]
    if comeback["sample_count"]:
        parts.append(
            f"Tagged comeback rate {comeback['rate']}% across "
            f"{comeback['sample_count']} source-tagged bouts."
        )
    else:
        parts.append("Comeback rate unavailable because recorded rows lack comeback tags.")

    handedness = metrics.get("handedness")
    if handedness and handedness.get("value") in {"left", "right"}:
        parts.append(f"Recorded handedness: {handedness['value']}-handed.")

    parts.append("Claims are conservative summaries of public result patterns.")
    return " ".join(parts)


def build_technique_analysis_rows(
    bouts: list[dict[str, Any]],
    results: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    identity_map: dict[str, str] | None = None,
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    now = updated_at or datetime.now(timezone.utc).isoformat()
    tournaments_by_id = tournament_lookup(tournaments)
    fencers_by_id = fencer_lookup(fencers, identity_map)
    profiles = build_profiles(fencers, identity_map)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    subject_ids = set(profiles)
    skipped = 0

    for fencer_id, profile in profiles.items():
        weapon = normalize_weapon(profile.get("weapon"))
        if weapon:
            ensure_stats(grouped, fencer_id, weapon)

    for result in results:
        result_fencer_id = canonical_fencer_id(result.get("fencer_id"), identity_map)
        if not result_fencer_id:
            continue
        subject_ids.add(result_fencer_id)
        weapon = result_weapon(result, tournaments_by_id, fencers_by_id, identity_map)
        if not weapon:
            continue
        stats = ensure_stats(grouped, result_fencer_id, weapon)
        stats["results_count"] += 1
        rank = to_int(result.get("rank") if result.get("rank") is not None else result.get("placement"))
        if rank is not None and rank > 0:
            stats["result_ranks"].append(rank)

    for bout in bouts:
        fencer_a = canonical_fencer_id(bout.get("fencer_a_id"), identity_map)
        fencer_b = canonical_fencer_id(bout.get("fencer_b_id"), identity_map)
        score_a = to_int(bout.get("score_a"))
        score_b = to_int(bout.get("score_b"))
        weapon = bout_weapon(bout, tournaments_by_id, profiles, (fencer_a, fencer_b))
        if not fencer_a or not fencer_b or fencer_a == fencer_b or score_a is None or score_b is None or not weapon:
            skipped += 1
            continue

        phase = classify_round(bout.get("round"))
        comeback_winner = comeback_winner_id(bout, identity_map)
        winner = canonical_fencer_id(bout.get("winner_id"), identity_map)
        a_won = score_a > score_b or (score_a == score_b and winner == fencer_a)
        b_won = score_b > score_a or (score_a == score_b and winner == fencer_b)
        a_lost = score_a < score_b or (score_a == score_b and winner == fencer_b)
        b_lost = score_b < score_a or (score_a == score_b and winner == fencer_a)

        if fencer_a in subject_ids:
            stats = ensure_stats(grouped, fencer_a, weapon)
            update_side_stats(
                stats, score_a, score_b, a_won, a_lost, phase, comeback_winner, fencer_a
            )
        if fencer_b in subject_ids:
            stats = ensure_stats(grouped, fencer_b, weapon)
            update_side_stats(
                stats, score_b, score_a, b_won, b_lost, phase, comeback_winner, fencer_b
            )

    rows: list[dict[str, Any]] = []
    for (fencer_id, weapon), stats in sorted(grouped.items()):
        profile = profiles.get(fencer_id, {})
        if stats["bouts"] < MINIMUM_BOUTS_FOR_CLAIMS:
            rows.append(low_data_row(fencer_id, weapon, stats, profile, now))
            continue

        metrics = base_metrics(stats)
        if profile.get("handedness"):
            metrics["handedness"] = profile["handedness"]
        strengths, weaknesses = build_claims(metrics)
        metrics["claims"] = {
            claim["id"]: claim["evidence"]
            for claim in strengths + weaknesses
        }
        rows.append(
            {
                "fencer_id": fencer_id,
                "weapon": weapon,
                "pattern_summary": pattern_summary(weapon, metrics),
                "strengths": strengths,
                "weaknesses": weaknesses,
                "evidence_metrics": metrics,
                "confidence": confidence_for(metrics),
                "updated_at": now,
            }
        )
    return rows, skipped


def batch_upsert(
    client,
    rows: list[dict[str, Any]],
    batch_size: int = BATCH_SIZE,
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_fencer_technique_analysis").upsert(
            batch, on_conflict=TECHNIQUE_CONFLICT
        ).execute()
        written += len(batch)
    return written


def compute_technique_analysis(
    client=None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    updated_at: str | None = None,
) -> dict[str, int]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    try:
        bouts = fetch_with_fallbacks(client, "fs_bouts", BOUT_SELECTS, page_size=page_size)
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(
            client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size
        )
        fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
        identity_map, identity_rows = load_identity_map(client, page_size=page_size)
        rows, skipped = build_technique_analysis_rows(
            bouts=bouts,
            results=results,
            tournaments=tournaments,
            fencers=fencers,
            identity_map=identity_map,
            updated_at=updated_at,
        )
        written = batch_upsert(client, rows) if rows else 0
        summary = {
            "bouts_read": len(bouts),
            "results_read": len(results),
            "fencers_read": len(fencers),
            "tournaments_read": len(tournaments),
            "analysis_rows": len(rows),
            "written": written,
            "skipped": skipped,
            "identity_rows": identity_rows,
            "llm_summaries": 0,
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
    print(f"Technique analysis computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_technique_analysis()
    print(
        "Technique analysis computation complete - "
        f"{summary['analysis_rows']} rows built, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} source bouts skipped"
    )


if __name__ == "__main__":
    main()

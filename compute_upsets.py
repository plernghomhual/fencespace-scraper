from __future__ import annotations

import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state


SOURCE = "compute_upsets"
PAGE_SIZE = 1000
BATCH_SIZE = 100
UPSET_CONFLICT = "upset_key"
UPSET_NAMESPACE = uuid.UUID("4f33b845-ecca-4c78-981c-ac9a381972db")

TOURNAMENT_SELECTS = (
    "id,name,season,start_date,end_date,weapon,gender,category,type,metadata,event_key,event_id,source",
    "id,name,season,start_date,end_date,weapon,gender,category,type,metadata",
    "id,name,season,start_date,end_date,weapon,gender,category,type",
)
BRACKET_SELECTS = (
    (
        "id,bracket_key,tournament_id,event_id,event_key,weapon,gender,category,"
        "round_name,round_order,bout_order,fencer_a_id,fencer_a_name,fencer_a_country,"
        "fencer_a_seed,fencer_b_id,fencer_b_name,fencer_b_country,fencer_b_seed,"
        "score_a,score_b,winner_id,is_bye,seed_a,seed_b,source,metadata"
    ),
    (
        "id,bracket_key,tournament_id,event_id,event_key,weapon,gender,category,"
        "round_name,round_order,bout_order,fencer_a_id,fencer_b_id,score_a,score_b,"
        "winner_id,is_bye,seed_a,seed_b,source,metadata"
    ),
    "id,tournament_id,fencer_a_id,fencer_b_id,score_a,score_b,round,winner_id,metadata",
)
RESULT_SELECTS = (
    (
        "id,tournament_id,event_id,event_key,weapon,gender,category,fencer_id,"
        "fie_fencer_id,name,country,nationality,rank,placement,source,metadata"
    ),
    "id,tournament_id,fencer_id,fie_fencer_id,name,country,nationality,rank,placement,metadata",
    "id,tournament_id,fencer_id,name,country,nationality,rank,placement",
)
RANKING_HISTORY_SELECTS = (
    (
        "source,season,weapon,gender,category,fencer_id,fie_fencer_id,rank,points,"
        "name,country,scraped_at,metadata"
    ),
    "season,weapon,gender,category,fencer_id,fie_fencer_id,rank,points,name,country,scraped_at",
    "season,weapon,gender,category,fie_fencer_id,rank,points,name,country,scraped_at",
)
NATIONAL_RANKING_SELECTS = (
    (
        "source,season,weapon,gender,category,fencer_id,fie_id,rank,points,"
        "name,country,club,scraped_at,metadata"
    ),
    "source,season,weapon,gender,category,fencer_id,fie_id,rank,points,name,country,scraped_at",
)

SEED_A_KEYS = ("seed_a", "fencer_a_seed", "seed1", "seed_1")
SEED_B_KEYS = ("seed_b", "fencer_b_seed", "seed2", "seed_2")
RESULT_SEED_KEYS = ("pre_event_seed", "entry_seed", "initial_seed", "pool_seed", "seed")
RESULT_RANK_KEYS = (
    "pre_event_rank",
    "entry_rank",
    "initial_rank",
    "world_rank_at_entry",
    "ranking_at_entry",
)


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
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
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


def positive_int(value: Any) -> int | None:
    number = to_int(value)
    return number if number and number > 0 else None


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


def first_value(row: dict[str, Any] | None, keys: tuple[str, ...]) -> Any:
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


def event_key_from_parts(event_key: Any, event_id: Any, weapon: Any, gender: Any, category: Any) -> str:
    explicit = clean_text(event_key)
    if explicit:
        return compact_key(explicit)
    explicit_id = clean_text(event_id)
    if explicit_id:
        return compact_key(explicit_id)
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
    event_key = first_value(row, ("event_key",)) or first_value(tournament, ("event_key",))
    return {
        "event_id": clean_text(event_id),
        "event_key": event_key_from_parts(event_key, event_id, weapon, gender, category),
        "weapon": clean_text(weapon),
        "gender": clean_text(gender),
        "category": clean_text(category),
    }


def merge_event_info(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if not merged.get(key) and value:
            merged[key] = value
    return merged


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = re.sub(r"[^a-z]+", " ", text.casefold()).strip()
    if "women" in key or "female" in key:
        return "women"
    if "men" in key or "male" in key:
        return "men"
    return key or None


def normalize_category(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    tokens = [token for token in key.split() if token not in {"men", "mens", "women", "womens"}]
    return " ".join(tokens) or key


def compatible_value(left: Any, right: Any, *, kind: str) -> bool:
    left_text = clean_text(left)
    right_text = clean_text(right)
    if not left_text or not right_text:
        return True
    if kind == "gender":
        return normalize_gender(left_text) == normalize_gender(right_text)
    if kind == "category":
        left_key = normalize_category(left_text) or ""
        right_key = normalize_category(right_text) or ""
        return left_key == right_key or left_key in right_key or right_key in left_key
    return compact_key(left_text) == compact_key(right_text)


def season_to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = clean_text(value)
    if not text:
        return None
    years = re.findall(r"\d{4}", text)
    if years:
        return int(years[-1])
    return to_int(text)


def is_team_event(tournament: dict[str, Any], event_info: dict[str, Any]) -> bool:
    metadata = metadata_for(tournament)
    for key in ("is_team_event", "team_event"):
        if metadata.get(key) is True:
            return True
    values = [
        tournament.get("type"),
        tournament.get("name"),
        tournament.get("category"),
        event_info.get("event_key"),
        event_info.get("category"),
        metadata.get("event_type"),
        metadata.get("competition_type"),
    ]
    for value in values:
        text = clean_text(value)
        if text and re.search(r"\bteams?\b", text.casefold()):
            return True
    return False


def side_fencer_id(row: dict[str, Any], side: str) -> str | None:
    if side == "a":
        return clean_text(first_value(row, ("fencer_a_id", "fencer_a", "a_fencer_id")))
    return clean_text(first_value(row, ("fencer_b_id", "fencer_b", "b_fencer_id")))


def side_name(row: dict[str, Any], side: str) -> str | None:
    keys = ("fencer_a_name", "name_a", "a_name") if side == "a" else ("fencer_b_name", "name_b", "b_name")
    return clean_text(first_value(row, keys))


def side_country(row: dict[str, Any], side: str) -> str | None:
    keys = (
        ("fencer_a_country", "country_a", "a_country")
        if side == "a"
        else ("fencer_b_country", "country_b", "b_country")
    )
    return clean_text(first_value(row, keys))


def side_seed(row: dict[str, Any], side: str) -> int | None:
    return positive_int(first_value(row, SEED_A_KEYS if side == "a" else SEED_B_KEYS))


def derive_winner_id(row: dict[str, Any]) -> str | None:
    winner_id = clean_text(first_value(row, ("winner_id", "winner")))
    if winner_id:
        return winner_id
    score_a = to_int(row.get("score_a"))
    score_b = to_int(row.get("score_b"))
    if score_a is None or score_b is None or score_a == score_b:
        return None
    return side_fencer_id(row, "a") if score_a > score_b else side_fencer_id(row, "b")


def bout_completeness(row: dict[str, Any]) -> tuple[int, str]:
    score = 0
    for key in (
        "winner_id",
        "score_a",
        "score_b",
        "seed_a",
        "seed_b",
        "fencer_a_seed",
        "fencer_b_seed",
        "round_order",
        "bout_order",
    ):
        if first_value(row, (key,)) is not None:
            score += 1
    return score, clean_text(row.get("id")) or ""


def dedupe_bouts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = (
            clean_text(row.get("bracket_key"))
            or (
                row.get("tournament_id"),
                first_value(row, ("event_key", "event_id")),
                to_int(first_value(row, ("round_order",))),
                to_int(first_value(row, ("bout_order", "bout_index", "order"))),
                side_fencer_id(row, "a"),
                side_fencer_id(row, "b"),
            )
        )
        if not isinstance(key, tuple):
            key = (key,)
        existing = deduped.get(key)
        if not existing or bout_completeness(row) > bout_completeness(existing):
            deduped[key] = row
    return sorted(
        deduped.values(),
        key=lambda row: (
            str(row.get("tournament_id") or ""),
            event_info_from_row(row, None)["event_key"],
            to_int(first_value(row, ("round_order",))) or 9999,
            to_int(first_value(row, ("bout_order", "bout_index", "order"))) or 9999,
            clean_text(row.get("id")) or "",
        ),
    )


def result_placement(row: dict[str, Any]) -> int | None:
    return positive_int(row.get("placement")) or positive_int(row.get("rank"))


def result_fencer_id(row: dict[str, Any]) -> str | None:
    return clean_text(row.get("fencer_id"))


def result_fie_id(row: dict[str, Any]) -> str | None:
    return clean_text(row.get("fie_fencer_id") or row.get("fie_id"))


def fencer_context_from_results(results: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    context: dict[str, dict[str, Any]] = {}
    fencer_id_by_fie_id: dict[str, str] = {}
    for row in results:
        fencer_id = result_fencer_id(row)
        if not fencer_id:
            continue
        country = clean_text(row.get("country") or row.get("nationality"))
        context[fencer_id] = {
            "name": clean_text(row.get("name")),
            "country": country,
            "fie_fencer_id": result_fie_id(row),
            "result_id": clean_text(row.get("id")),
        }
        fie_id = result_fie_id(row)
        if fie_id:
            fencer_id_by_fie_id.setdefault(fie_id, fencer_id)
    return context, fencer_id_by_fie_id


def evidence_row(
    *,
    kind: str,
    value: int,
    source_table: str,
    source_field: str,
    source_id: Any = None,
    source: Any = None,
    row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = {
        "kind": kind,
        "value": value,
        "source_table": source_table,
        "source_field": source_field,
        "source_id": clean_text(source_id),
        "source": clean_text(source),
        "not_derived_from_final_rank": True,
    }
    if row:
        for key in ("season", "weapon", "gender", "category", "scraped_at"):
            value_from_row = clean_text(row.get(key))
            if value_from_row:
                evidence[key] = value_from_row
    return evidence


def add_seed_evidence(
    seed_evidence: dict[str, dict[str, Any]],
    fencer_id: str | None,
    seed: int | None,
    *,
    source_table: str,
    source_field: str,
    source_id: Any,
    source: Any = None,
    row: dict[str, Any] | None = None,
) -> None:
    if not fencer_id or seed is None:
        return
    if fencer_id in seed_evidence:
        return
    seed_evidence[fencer_id] = evidence_row(
        kind="seed",
        value=seed,
        source_table=source_table,
        source_field=source_field,
        source_id=source_id,
        source=source,
        row=row,
    )


def add_rank_evidence(
    rank_evidence: dict[str, dict[str, Any]],
    fencer_id: str | None,
    rank: int | None,
    *,
    source_table: str,
    source_field: str,
    source_id: Any = None,
    source: Any = None,
    row: dict[str, Any] | None = None,
) -> None:
    if not fencer_id or rank is None:
        return
    incoming = evidence_row(
        kind="rank",
        value=rank,
        source_table=source_table,
        source_field=source_field,
        source_id=source_id,
        source=source,
        row=row,
    )
    existing = rank_evidence.get(fencer_id)
    if not existing or (rank, source_table, clean_text(source)) < (
        existing["value"],
        existing["source_table"],
        existing.get("source") or "",
    ):
        rank_evidence[fencer_id] = incoming


def ranking_matches_event(
    row: dict[str, Any],
    *,
    tournament: dict[str, Any],
    event_info: dict[str, Any],
) -> bool:
    tournament_season = season_to_int(tournament.get("season"))
    ranking_season = season_to_int(row.get("season"))
    if tournament_season and ranking_season and tournament_season != ranking_season:
        return False
    return (
        compatible_value(row.get("weapon"), event_info.get("weapon"), kind="weapon")
        and compatible_value(row.get("gender"), event_info.get("gender"), kind="gender")
        and compatible_value(row.get("category"), event_info.get("category"), kind="category")
    )


def add_result_metadata_evidence(
    result: dict[str, Any],
    seed_evidence: dict[str, dict[str, Any]],
    rank_evidence: dict[str, dict[str, Any]],
) -> None:
    fencer_id = result_fencer_id(result)
    if not fencer_id:
        return
    seed = positive_int(first_value(result, RESULT_SEED_KEYS))
    add_seed_evidence(
        seed_evidence,
        fencer_id,
        seed,
        source_table="fs_results",
        source_field="metadata.seed",
        source_id=result.get("id"),
        source=first_value(result, ("source",)),
        row=result,
    )
    rank = positive_int(first_value(result, RESULT_RANK_KEYS))
    add_rank_evidence(
        rank_evidence,
        fencer_id,
        rank,
        source_table="fs_results",
        source_field="metadata.pre_event_rank",
        source_id=result.get("id"),
        source=first_value(result, ("source",)),
        row=result,
    )


def collect_event_evidence(
    *,
    tournament: dict[str, Any],
    event_info: dict[str, Any],
    brackets: list[dict[str, Any]],
    results: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    seed_evidence: dict[str, dict[str, Any]] = {}
    rank_evidence: dict[str, dict[str, Any]] = {}
    fencer_context, fencer_id_by_fie_id = fencer_context_from_results(results)

    for row in dedupe_bouts(brackets):
        fencer_a = side_fencer_id(row, "a")
        fencer_b = side_fencer_id(row, "b")
        add_seed_evidence(
            seed_evidence,
            fencer_a,
            side_seed(row, "a"),
            source_table="fs_tournament_brackets",
            source_field="seed_a",
            source_id=row.get("id"),
            source=first_value(row, ("source",)),
            row=row,
        )
        add_seed_evidence(
            seed_evidence,
            fencer_b,
            side_seed(row, "b"),
            source_table="fs_tournament_brackets",
            source_field="seed_b",
            source_id=row.get("id"),
            source=first_value(row, ("source",)),
            row=row,
        )
        for side, fencer_id in (("a", fencer_a), ("b", fencer_b)):
            if fencer_id and fencer_id not in fencer_context:
                fencer_context[fencer_id] = {
                    "name": side_name(row, side),
                    "country": side_country(row, side),
                    "fie_fencer_id": None,
                    "result_id": None,
                }

    for result in results:
        add_result_metadata_evidence(result, seed_evidence, rank_evidence)

    for row in rankings:
        if not ranking_matches_event(row, tournament=tournament, event_info=event_info):
            continue
        fencer_id = clean_text(row.get("fencer_id"))
        if not fencer_id:
            fie_id = clean_text(row.get("fie_fencer_id") or row.get("fie_id"))
            fencer_id = fencer_id_by_fie_id.get(fie_id or "")
        add_rank_evidence(
            rank_evidence,
            fencer_id,
            positive_int(row.get("rank")),
            source_table=clean_text(row.get("source_table")) or "fs_rankings_history",
            source_field="rank",
            source_id=row.get("id"),
            source=row.get("source"),
            row=row,
        )

    return seed_evidence, rank_evidence, fencer_context


def side_evidence(
    row: dict[str, Any],
    side: str,
    seed_evidence: dict[str, dict[str, Any]],
    rank_evidence: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    fencer_id = side_fencer_id(row, side)
    seed = side_seed(row, side)
    if fencer_id and seed is not None:
        return evidence_row(
            kind="seed",
            value=seed,
            source_table="fs_tournament_brackets",
            source_field=f"seed_{side}",
            source_id=row.get("id"),
            source=first_value(row, ("source",)),
            row=row,
        )
    if fencer_id and fencer_id in seed_evidence:
        return seed_evidence[fencer_id]
    if fencer_id and fencer_id in rank_evidence:
        return rank_evidence[fencer_id]
    return None


def score_from_evidence(fencer_evidence: dict[str, Any], opponent_evidence: dict[str, Any]) -> int | None:
    if fencer_evidence["kind"] != opponent_evidence["kind"]:
        return None
    gap = fencer_evidence["value"] - opponent_evidence["value"]
    return gap if gap > 0 else None


def upset_key_for(parts: list[Any]) -> str:
    return ":".join(clean_text(part) or "none" for part in parts)


def upset_id(upset_key: str) -> str:
    return str(uuid.uuid5(UPSET_NAMESPACE, upset_key))


def fencer_name(fencer_id: str | None, side: str, row: dict[str, Any], context: dict[str, dict[str, Any]]) -> str | None:
    if fencer_id and context.get(fencer_id, {}).get("name"):
        return context[fencer_id]["name"]
    return side_name(row, side)


def fencer_country(fencer_id: str | None, side: str, row: dict[str, Any], context: dict[str, dict[str, Any]]) -> str | None:
    if fencer_id and context.get(fencer_id, {}).get("country"):
        return context[fencer_id]["country"]
    return side_country(row, side)


def make_round_upset_row(
    *,
    tournament: dict[str, Any],
    event_info: dict[str, Any],
    bout: dict[str, Any],
    winner_side: str,
    loser_side: str,
    winner_evidence: dict[str, Any],
    loser_evidence: dict[str, Any],
    fencer_context: dict[str, dict[str, Any]],
    updated_at: str,
) -> dict[str, Any] | None:
    upset_score = score_from_evidence(winner_evidence, loser_evidence)
    if upset_score is None:
        return None

    fencer_id = side_fencer_id(bout, winner_side)
    opponent_id = side_fencer_id(bout, loser_side)
    round_order = to_int(first_value(bout, ("round_order",)))
    bout_order = to_int(first_value(bout, ("bout_order", "bout_index", "order")))
    evidence_kind = winner_evidence["kind"]
    upset_type = "round_upset" if evidence_kind == "seed" else "high_rank_defeated"
    expected = "higher_seed_expected_to_win" if evidence_kind == "seed" else "higher_rank_expected_to_win"
    actual = "lower_seed_won" if evidence_kind == "seed" else "lower_rank_won"
    upset_key = upset_key_for(
        [
            tournament.get("id"),
            event_info["event_key"],
            upset_type,
            round_order,
            bout_order,
            fencer_id,
            opponent_id,
        ]
    )
    return {
        "id": upset_id(upset_key),
        "upset_key": upset_key,
        "tournament_id": tournament.get("id"),
        "event_id": event_info.get("event_id"),
        "event_key": event_info["event_key"],
        "weapon": event_info.get("weapon"),
        "gender": event_info.get("gender"),
        "category": event_info.get("category"),
        "upset_type": upset_type,
        "fencer_id": fencer_id,
        "fencer_name": fencer_name(fencer_id, winner_side, bout, fencer_context),
        "fencer_country": fencer_country(fencer_id, winner_side, bout, fencer_context),
        "opponent_id": opponent_id,
        "opponent_name": fencer_name(opponent_id, loser_side, bout, fencer_context),
        "opponent_country": fencer_country(opponent_id, loser_side, bout, fencer_context),
        "fencer_seed": winner_evidence["value"] if evidence_kind == "seed" else None,
        "opponent_seed": loser_evidence["value"] if evidence_kind == "seed" else None,
        "fencer_rank": winner_evidence["value"] if evidence_kind == "rank" else None,
        "opponent_rank": loser_evidence["value"] if evidence_kind == "rank" else None,
        "seed_source": winner_evidence.get("source") if evidence_kind == "seed" else None,
        "rank_source": winner_evidence.get("source") if evidence_kind == "rank" else None,
        "round_name": clean_text(first_value(bout, ("round_name", "round"))),
        "round_order": round_order,
        "bout_order": bout_order,
        "expected_outcome": expected,
        "actual_outcome": actual,
        "upset_score": upset_score,
        "evidence": {
            "evidence_type": evidence_kind,
            "source_bracket_id": clean_text(bout.get("id")),
            "source_bracket_key": clean_text(bout.get("bracket_key")),
            "source_tables": sorted({winner_evidence["source_table"], loser_evidence["source_table"]}),
            "fencer_evidence": winner_evidence,
            "opponent_evidence": loser_evidence,
            "not_derived_from_final_rank": True,
        },
        "metadata": {
            "tournament_name": clean_text(tournament.get("name")),
            "score_a": to_int(bout.get("score_a")),
            "score_b": to_int(bout.get("score_b")),
            "source_url": metadata_for(tournament).get("source_url"),
        },
        "updated_at": updated_at,
    }


def make_medal_upset_row(
    *,
    tournament: dict[str, Any],
    event_info: dict[str, Any],
    medalists: list[dict[str, Any]],
    seed_evidence: dict[str, dict[str, Any]],
    fencer_context: dict[str, dict[str, Any]],
    updated_at: str,
) -> dict[str, Any] | None:
    seeded_medalists = []
    for result in medalists:
        fencer_id = result_fencer_id(result)
        evidence = seed_evidence.get(fencer_id or "")
        if fencer_id and evidence:
            seeded_medalists.append((result, evidence))
    if not seeded_medalists:
        return None

    result, evidence = max(
        seeded_medalists,
        key=lambda item: (
            item[1]["value"],
            -(result_placement(item[0]) or 9999),
            clean_text(item[0].get("name")) or "",
            result_fencer_id(item[0]) or "",
        ),
    )
    best_seed = min(item[1]["value"] for item in seeded_medalists)
    fencer_id = result_fencer_id(result)
    placement = result_placement(result)
    upset_score = max(0, evidence["value"] - best_seed)
    upset_key = upset_key_for(
        [
            tournament.get("id"),
            event_info["event_key"],
            "lowest_seed_to_medal",
            fencer_id,
        ]
    )
    context = fencer_context.get(fencer_id or "", {})
    return {
        "id": upset_id(upset_key),
        "upset_key": upset_key,
        "tournament_id": tournament.get("id"),
        "event_id": event_info.get("event_id"),
        "event_key": event_info["event_key"],
        "weapon": event_info.get("weapon"),
        "gender": event_info.get("gender"),
        "category": event_info.get("category"),
        "upset_type": "lowest_seed_to_medal",
        "fencer_id": fencer_id,
        "fencer_name": clean_text(result.get("name")) or context.get("name"),
        "fencer_country": clean_text(result.get("country") or result.get("nationality")) or context.get("country"),
        "opponent_id": None,
        "opponent_name": None,
        "opponent_country": None,
        "fencer_seed": evidence["value"],
        "opponent_seed": None,
        "fencer_rank": None,
        "opponent_rank": None,
        "seed_source": evidence.get("source"),
        "rank_source": None,
        "round_name": "Medal",
        "round_order": None,
        "bout_order": None,
        "expected_outcome": "higher_seed_expected_to_medal",
        "actual_outcome": "lower_seed_medaled",
        "upset_score": upset_score,
        "evidence": {
            "evidence_type": "seed",
            "source_result_id": clean_text(result.get("id")),
            "medal_placement": placement,
            "best_medalist_seed": best_seed,
            "fencer_evidence": evidence,
            "not_derived_from_final_rank": True,
        },
        "metadata": {
            "tournament_name": clean_text(tournament.get("name")),
            "source_url": metadata_for(tournament).get("source_url"),
        },
        "updated_at": updated_at,
    }


def build_event_upset_rows(
    *,
    tournament: dict[str, Any],
    event_info: dict[str, Any],
    brackets: list[dict[str, Any]],
    results: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    updated_at: str,
) -> tuple[list[dict[str, Any]], str | None]:
    if is_team_event(tournament, event_info):
        return [], "team_event"

    seed_evidence, rank_evidence, fencer_context = collect_event_evidence(
        tournament=tournament,
        event_info=event_info,
        brackets=brackets,
        results=results,
        rankings=rankings,
    )
    evidenced_fencers = set(seed_evidence) | set(rank_evidence)
    if len(evidenced_fencers) < 2:
        return [], "missing_seed_or_rank_evidence"

    rows: list[dict[str, Any]] = []
    for bout in dedupe_bouts(brackets):
        winner_id = derive_winner_id(bout)
        if not winner_id:
            continue
        side_a = side_fencer_id(bout, "a")
        side_b = side_fencer_id(bout, "b")
        if winner_id == side_a:
            winner_side, loser_side = "a", "b"
        elif winner_id == side_b:
            winner_side, loser_side = "b", "a"
        else:
            continue
        if not side_fencer_id(bout, loser_side):
            continue

        winner_evidence = side_evidence(bout, winner_side, seed_evidence, rank_evidence)
        loser_evidence = side_evidence(bout, loser_side, seed_evidence, rank_evidence)
        if not winner_evidence or not loser_evidence:
            continue
        row = make_round_upset_row(
            tournament=tournament,
            event_info=event_info,
            bout=bout,
            winner_side=winner_side,
            loser_side=loser_side,
            winner_evidence=winner_evidence,
            loser_evidence=loser_evidence,
            fencer_context=fencer_context,
            updated_at=updated_at,
        )
        if row:
            rows.append(row)

    medalists = [row for row in results if (result_placement(row) or 9999) <= 3]
    medal_row = make_medal_upset_row(
        tournament=tournament,
        event_info=event_info,
        medalists=medalists,
        seed_evidence=seed_evidence,
        fencer_context=fencer_context,
        updated_at=updated_at,
    )
    if medal_row:
        rows.append(medal_row)

    return sorted(rows, key=lambda row: row["upset_key"]), None


def build_upset_rows(
    tournaments: list[dict[str, Any]],
    brackets: list[dict[str, Any]],
    results: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    *,
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    updated_at = updated_at or utc_now_iso()
    tournaments_by_id = {clean_text(row.get("id")): row for row in tournaments if row.get("id")}
    event_keys: set[tuple[str, str]] = set()
    brackets_by_event: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    results_by_event: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    event_infos: dict[tuple[str, str], dict[str, Any]] = {}

    for row in brackets:
        tournament_id = clean_text(row.get("tournament_id"))
        if not tournament_id:
            continue
        tournament = tournaments_by_id.get(tournament_id, {"id": tournament_id})
        info = event_info_from_row(row, tournament)
        key = (tournament_id, info["event_key"])
        event_keys.add(key)
        event_infos[key] = merge_event_info(event_infos.get(key, {}), info)
        brackets_by_event[key].append(row)

    for row in results:
        tournament_id = clean_text(row.get("tournament_id"))
        if not tournament_id:
            continue
        tournament = tournaments_by_id.get(tournament_id, {"id": tournament_id})
        info = event_info_from_row(row, tournament)
        key = (tournament_id, info["event_key"])
        event_keys.add(key)
        event_infos[key] = merge_event_info(event_infos.get(key, {}), info)
        results_by_event[key].append(row)

    rows: list[dict[str, Any]] = []
    skipped_events: list[dict[str, str]] = []
    for tournament_id, event_key in sorted(event_keys):
        tournament = tournaments_by_id.get(tournament_id, {"id": tournament_id})
        event_info = event_infos[(tournament_id, event_key)]
        try:
            event_rows, skip_reason = build_event_upset_rows(
                tournament=tournament,
                event_info=event_info,
                brackets=brackets_by_event.get((tournament_id, event_key), []),
                results=results_by_event.get((tournament_id, event_key), []),
                rankings=rankings,
                updated_at=updated_at,
            )
        except Exception as exc:
            event_rows = []
            skip_reason = f"failed:{exc}"
        if event_rows:
            rows.extend(event_rows)
        elif skip_reason:
            skipped_events.append(
                {
                    "tournament_id": tournament_id,
                    "event_key": event_key,
                    "reason": skip_reason,
                }
            )

    return sorted(rows, key=lambda row: row["upset_key"]), skipped_events


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
            break
        offset += page_size
    return rows


def fetch_all_with_fallback(
    client,
    table: str,
    selects: tuple[str, ...],
    *,
    page_size: int = PAGE_SIZE,
    optional: bool = False,
) -> list[dict[str, Any]]:
    last_error = None
    for columns in selects:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    if optional:
        return []
    raise RuntimeError(f"Unable to fetch {table}") from last_error


def with_source_table(rows: list[dict[str, Any]], source_table: str) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        copy = dict(row)
        copy.setdefault("source_table", source_table)
        enriched.append(copy)
    return enriched


def batch_upsert_upsets(client, rows: list[dict[str, Any]], *, batch_size: int = BATCH_SIZE) -> int:
    written = 0
    rows = sorted(rows, key=lambda row: row["upset_key"])
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_upsets").upsert(batch, on_conflict=UPSET_CONFLICT).execute()
        written += len(batch)
    return written


def compute_upsets(
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
            "brackets_read": 0,
            "results_read": 0,
            "rankings_read": 0,
            "upset_rows": 0,
            "written": 0,
            "skipped": 0,
            "failed": 0,
            "skipped_events": [],
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
        brackets = fetch_all_with_fallback(
            client,
            "fs_tournament_brackets",
            BRACKET_SELECTS,
            page_size=page_size,
            optional=True,
        )
        results = fetch_all_with_fallback(
            client,
            "fs_results",
            RESULT_SELECTS,
            page_size=page_size,
        )
        ranking_history = with_source_table(
            fetch_all_with_fallback(
                client,
                "fs_rankings_history",
                RANKING_HISTORY_SELECTS,
                page_size=page_size,
                optional=True,
            ),
            "fs_rankings_history",
        )
        national_rankings = with_source_table(
            fetch_all_with_fallback(
                client,
                "fs_national_fed_rankings",
                NATIONAL_RANKING_SELECTS,
                page_size=page_size,
                optional=True,
            ),
            "fs_national_fed_rankings",
        )
        rankings = ranking_history + national_rankings
        rows, skipped_events = build_upset_rows(
            tournaments,
            brackets,
            results,
            rankings,
            updated_at=updated_at,
        )
        written = batch_upsert_upsets(client, rows) if rows else 0
        summary = {
            "tournaments_read": len(tournaments),
            "brackets_read": len(brackets),
            "results_read": len(results),
            "rankings_read": len(rankings),
            "upset_rows": len(rows),
            "written": written,
            "skipped": len(skipped_events),
            "failed": 0,
            "skipped_events": skipped_events,
            "no_credentials": False,
        }
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": utc_now_iso(), **summary})
        if run_log:
            run_log.complete(
                written=written,
                failed=0,
                skipped=len(skipped_events),
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> dict[str, Any]:
    summary = compute_upsets()
    if summary.get("no_credentials"):
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY are not set; upset computation skipped.")
    else:
        print(
            "upsets: "
            f"{summary['written']} written, {summary['failed']} failed, "
            f"{summary['skipped']} skipped"
        )
    return summary


if __name__ == "__main__":
    main()

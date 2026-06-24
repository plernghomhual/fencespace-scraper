from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timezone
from math import floor
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "compute_peak_age"
PAGE_SIZE = 1000
BATCH_SIZE = 100
OUTPUT_TABLE = "fs_peak_age_analysis"
OUTPUT_CONFLICT = "weapon,gender,category,country,competition_tier,source_type"

MIN_RELIABLE_AGE = 10.0
MAX_RELIABLE_AGE = 90.0
MIN_COHORT_SIZE = 5
PEAK_RESULT_RANK_CUTOFF = 8
PEAK_RANKING_CUTOFF = 16

RESULT_SELECTS = (
    "id,tournament_id,fencer_id,fie_fencer_id,rank,placement,weapon,gender,category,"
    "country,nationality,result_date,event_date,date,competition_tier,tier,level,grade",
    "id,tournament_id,fencer_id,rank,placement,weapon,gender,category,country,nationality",
    "tournament_id,fencer_id,rank,placement",
)
FENCER_SELECTS = (
    "id,fie_id,name,country,weapon,category,date_of_birth",
    "id,fie_id,name,country,weapon,category",
)
TOURNAMENT_SELECTS = (
    "id,name,season,weapon,gender,category,start_date,end_date,date,type,source,"
    "competition_tier,tier,level,grade",
    "id,name,season,weapon,gender,category,start_date,end_date,type,source",
    "id,weapon,gender,category,start_date,end_date",
)
RANKING_SELECTS = (
    "id,fencer_id,fie_fencer_id,season,weapon,gender,category,country,nationality,"
    "rank,points,ranking_date,as_of_date,date,competition_tier,tier,level,grade",
    "fie_fencer_id,season,weapon,gender,category,country,rank,points,ranking_date",
    "fie_fencer_id,season,weapon,category,rank,points",
)
IDENTITY_SELECTS = (
    "canonical_id,fs_fencer_row_ids",
    "id,canonical_id,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
    "canonical_id,fencer_ids",
)
COMPETITION_DETAIL_SELECTS = (
    "tournament_id,format_type,metadata",
    "tournament_id,metadata",
)

AGE_BUCKETS = (
    ("under_18", None, 18.0),
    ("18_21", 18.0, 22.0),
    ("22_25", 22.0, 26.0),
    ("26_29", 26.0, 30.0),
    ("30_34", 30.0, 35.0),
    ("35_plus", 35.0, None),
)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def threshold_note(min_cohort_size: int = MIN_COHORT_SIZE) -> str:
    return (
        f"ages {MIN_RELIABLE_AGE:.1f}-{MAX_RELIABLE_AGE:.1f} inclusive; "
        "exact YYYY-MM-DD birth/result dates only; "
        f"sparse cohorts need n>={min_cohort_size}"
    )


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def parse_reliable_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    if not text:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T\s].*)?$", text)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def age_at_event(birth_value: Any, event_value: Any) -> float | None:
    birth_date = parse_reliable_date(birth_value)
    event_date = parse_reliable_date(event_value)
    if not birth_date or not event_date or event_date < birth_date:
        return None
    return (event_date - birth_date).days / 365.2425


def is_reliable_age(age: float | None) -> bool:
    return age is not None and MIN_RELIABLE_AGE <= age <= MAX_RELIABLE_AGE


def round_metric(value: float | None) -> float | None:
    if value is None:
        return None
    rounded = round(float(value), 2)
    return 0.0 if rounded == -0.0 else rounded


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def first_present(*values: Any) -> Any:
    for value in values:
        if clean_text(value):
            return value
    return None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.lower().replace("epee", "epee").replace("épée", "epee")
    if "foil" in key:
        return "Foil"
    if "epee" in key:
        return "Epee"
    if "sabre" in key or "saber" in key:
        return "Sabre"
    return text.title()


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.lower()
    if key in {"f", "female", "women", "woman", "w"} or "women" in key:
        return "Women"
    if key in {"m", "male", "men", "man"} or re.search(r"\bmen'?s?\b", key):
        return "Men"
    return text.title()


def normalize_category(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = re.sub(r"\b(men|women|male|female|boys|girls)'?s?\b", "", text, flags=re.I)
    key = re.sub(r"\s+", " ", key).strip(" -_/")
    lower = key.lower()
    for category in ("senior", "junior", "cadet", "veteran", "youth"):
        if category in lower:
            return category.title()
    return key.title() if key else None


def normalize_country(value: Any) -> str:
    text = clean_text(value)
    return text.upper() if text and len(text) <= 3 else (text or "UNKNOWN")


def normalize_tier(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or None


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
    members: list[str] = []
    for item in value:
        text = clean_text(item)
        if text:
            members.append(text)
    return members


def build_identity_map(identity_rows: list[dict[str, Any]]) -> dict[str, str]:
    identity_map: dict[str, str] = {}
    for row in identity_rows:
        members = parse_identity_members(
            row.get("fs_fencer_row_ids")
            or row.get("fencer_ids")
            or row.get("source_fencer_ids")
        )
        canonical = clean_text(row.get("canonical_id"))
        row_id = clean_text(row.get("id"))
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


def canonical_fencer_id(fencer_id: Any, identity_map: dict[str, str]) -> str | None:
    text = clean_text(fencer_id)
    if not text:
        return None
    return identity_map.get(text, text)


def fencer_lookups(
    fencers: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_fie_id: dict[str, dict[str, Any]] = {}
    for row in fencers:
        row_id = clean_text(row.get("id"))
        fie_id = clean_text(row.get("fie_id") or row.get("fie_fencer_id"))
        if row_id:
            by_id.setdefault(row_id, row)
        if fie_id:
            by_fie_id.setdefault(fie_id, row)
    return by_id, by_fie_id


def tournament_lookup(tournaments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None and clean_text(row.get("id"))
    }


def parse_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def competition_detail_lookup(
    details: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in details or []:
        tournament_id = clean_text(row.get("tournament_id"))
        if not tournament_id:
            continue
        merged = dict(parse_metadata(row.get("metadata")))
        for key in ("format_type", "competition_tier", "tier", "level", "grade"):
            if row.get(key) is not None:
                merged[key] = row[key]
        lookup[tournament_id] = merged
    return lookup


def classify_tier(
    row: dict[str, Any],
    tournament: dict[str, Any] | None = None,
    detail: dict[str, Any] | None = None,
    source_type: str = "result",
) -> str:
    for source in (row, tournament or {}, detail or {}):
        for key in ("competition_tier", "tier", "competition_level", "level", "grade"):
            tier = normalize_tier(source.get(key))
            if tier:
                return tier

    if source_type == "ranking":
        return "ranking"

    text = " ".join(
        filter(
            None,
            [
                clean_text(row.get("name")),
                clean_text(row.get("competition")),
                clean_text((tournament or {}).get("name")),
                clean_text((tournament or {}).get("type")),
                clean_text((tournament or {}).get("source")),
                clean_text((detail or {}).get("format_type")),
            ],
        )
    ).lower()

    if "olympic" in text:
        return "olympic"
    if "grand prix" in text:
        return "grand_prix"
    if "world cup" in text:
        return "world_cup"
    if "world championship" in text:
        return "world_championship"
    if "championship" in text and "national" in text:
        return "national"
    if any(term in text for term in ("continental", "european", "asian", "pan american", "african")):
        return "continental"
    if any(term in text for term in ("national", "federation", "ncaa", "domestic")):
        return "national"
    return "unknown"


def result_event_date(
    result: dict[str, Any],
    tournament: dict[str, Any] | None,
) -> Any:
    return first_present(
        result.get("result_date"),
        result.get("event_date"),
        result.get("competition_date"),
        result.get("date"),
        (tournament or {}).get("start_date"),
        (tournament or {}).get("end_date"),
        (tournament or {}).get("date"),
        (tournament or {}).get("event_date"),
        (tournament or {}).get("competition_date"),
    )


def ranking_event_date(row: dict[str, Any]) -> Any:
    return first_present(
        row.get("ranking_date"),
        row.get("as_of_date"),
        row.get("event_date"),
        row.get("date"),
    )


def fencer_birth_value(fencer: dict[str, Any]) -> Any:
    return first_present(
        fencer.get("birth_date"),
        fencer.get("date_of_birth"),
        fencer.get("dob"),
    )


def resolve_result_fencer(
    row: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    by_fie_id: dict[str, dict[str, Any]],
) -> tuple[str | None, dict[str, Any] | None]:
    fencer_id = clean_text(row.get("fencer_id") or row.get("fs_fencer_id"))
    if fencer_id and fencer_id in by_id:
        return fencer_id, by_id[fencer_id]
    fie_id = clean_text(row.get("fie_fencer_id") or row.get("fie_id"))
    if fie_id and fie_id in by_fie_id:
        fencer = by_fie_id[fie_id]
        return clean_text(fencer.get("id")), fencer
    return fencer_id, None


def resolve_ranking_fencer(
    row: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    by_fie_id: dict[str, dict[str, Any]],
) -> tuple[str | None, dict[str, Any] | None]:
    fencer_id = clean_text(row.get("fencer_id") or row.get("fs_fencer_id"))
    if fencer_id and fencer_id in by_id:
        return fencer_id, by_id[fencer_id]
    fie_id = clean_text(row.get("fie_fencer_id") or row.get("fie_id"))
    if fie_id and fie_id in by_fie_id:
        fencer = by_fie_id[fie_id]
        return clean_text(fencer.get("id")), fencer
    return fencer_id or fie_id, None


def blank_summary(
    results: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    ranking_rows: list[dict[str, Any]],
    identity_rows: list[dict[str, Any]],
    competition_details: list[dict[str, Any]] | None,
) -> dict[str, int]:
    return {
        "results_read": len(results),
        "fencers_read": len(fencers),
        "tournaments_read": len(tournaments),
        "ranking_rows_read": len(ranking_rows),
        "identity_rows_read": len(identity_rows),
        "competition_details_read": len(competition_details or []),
        "observations_used": 0,
        "cohort_rows": 0,
        "sparse_cohort_rows": 0,
        "report_rows": 0,
        "skipped_total": 0,
        "skipped_non_peak_result": 0,
        "skipped_non_peak_ranking": 0,
        "skipped_missing_fencer": 0,
        "skipped_missing_birth_date": 0,
        "skipped_unreliable_birth_date": 0,
        "skipped_missing_result_date": 0,
        "skipped_implausible_age": 0,
        "skipped_missing_group": 0,
        "skipped_duplicate_identity_event": 0,
    }


def increment(summary: dict[str, int], key: str) -> None:
    summary[key] = summary.get(key, 0) + 1
    if key.startswith("skipped_"):
        summary["skipped_total"] = summary.get("skipped_total", 0) + 1


def build_observation(
    *,
    age: float,
    source_type: str,
    row: dict[str, Any],
    fencer: dict[str, Any],
    tournament: dict[str, Any] | None = None,
    detail: dict[str, Any] | None = None,
    include_country: bool,
) -> dict[str, Any] | None:
    weapon = normalize_weapon(first_present(row.get("weapon"), fencer.get("weapon"), (tournament or {}).get("weapon")))
    raw_gender = first_present(row.get("gender"), (tournament or {}).get("gender"), fencer.get("gender"))
    raw_category = first_present(row.get("category"), (tournament or {}).get("category"), fencer.get("category"))
    gender = normalize_gender(raw_gender) or normalize_gender(raw_category)
    category = normalize_category(raw_category)
    if not weapon or not gender or not category:
        return None

    country = "ALL"
    if include_country:
        country = normalize_country(
            first_present(
                row.get("country"),
                row.get("nationality"),
                fencer.get("country"),
                fencer.get("nationality"),
            )
        )

    return {
        "age": age,
        "weapon": weapon,
        "gender": gender,
        "category": category,
        "country": country,
        "competition_tier": classify_tier(row, tournament, detail, source_type),
        "source_type": source_type,
    }


def append_or_replace_observation(
    observations_by_key: dict[tuple[str, str, str, str, str, str, str], dict[str, Any]],
    key: tuple[str, str, str, str, str, str, str],
    observation: dict[str, Any],
    rank: int,
    summary: dict[str, int],
) -> None:
    existing = observations_by_key.get(key)
    if existing is not None:
        increment(summary, "skipped_duplicate_identity_event")
        if rank < existing["_rank"]:
            observation["_rank"] = rank
            observations_by_key[key] = observation
        return
    observation["_rank"] = rank
    observations_by_key[key] = observation


def collect_result_observations(
    *,
    results: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    by_fie_id: dict[str, dict[str, Any]],
    tournaments_by_id: dict[str, dict[str, Any]],
    details_by_tournament: dict[str, dict[str, Any]],
    identity_map: dict[str, str],
    include_country: bool,
    summary: dict[str, int],
) -> dict[tuple[str, str, str, str, str, str, str], dict[str, Any]]:
    observations_by_key: dict[tuple[str, str, str, str, str, str, str], dict[str, Any]] = {}

    for row in results:
        rank = coerce_int(row.get("rank") if row.get("rank") is not None else row.get("placement"))
        if rank is None or rank > PEAK_RESULT_RANK_CUTOFF:
            increment(summary, "skipped_non_peak_result")
            continue

        raw_fencer_id, fencer = resolve_result_fencer(row, by_id, by_fie_id)
        if not raw_fencer_id or not fencer:
            increment(summary, "skipped_missing_fencer")
            continue

        birth_value = fencer_birth_value(fencer)
        if not clean_text(birth_value):
            increment(summary, "skipped_missing_birth_date")
            continue
        if parse_reliable_date(birth_value) is None:
            increment(summary, "skipped_unreliable_birth_date")
            continue

        tournament_id = clean_text(row.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id or "")
        event_value = result_event_date(row, tournament)
        if parse_reliable_date(event_value) is None:
            increment(summary, "skipped_missing_result_date")
            continue

        age = age_at_event(birth_value, event_value)
        if not is_reliable_age(age):
            increment(summary, "skipped_implausible_age")
            continue

        detail = details_by_tournament.get(tournament_id or "")
        observation = build_observation(
            age=age or 0.0,
            source_type="result",
            row=row,
            fencer=fencer,
            tournament=tournament,
            detail=detail,
            include_country=include_country,
        )
        if not observation:
            increment(summary, "skipped_missing_group")
            continue

        canonical = canonical_fencer_id(raw_fencer_id, identity_map)
        key = (
            "result",
            canonical or raw_fencer_id,
            tournament_id or clean_text(row.get("id")) or "",
            observation["weapon"],
            observation["gender"],
            observation["category"],
            observation["competition_tier"],
        )
        append_or_replace_observation(observations_by_key, key, observation, rank, summary)

    return observations_by_key


def collect_ranking_observations(
    *,
    ranking_rows: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    by_fie_id: dict[str, dict[str, Any]],
    identity_map: dict[str, str],
    include_country: bool,
    summary: dict[str, int],
) -> dict[tuple[str, str, str, str, str, str, str], dict[str, Any]]:
    observations_by_key: dict[tuple[str, str, str, str, str, str, str], dict[str, Any]] = {}

    for row in ranking_rows:
        rank = coerce_int(row.get("rank"))
        if rank is None or rank > PEAK_RANKING_CUTOFF:
            increment(summary, "skipped_non_peak_ranking")
            continue

        raw_fencer_id, fencer = resolve_ranking_fencer(row, by_id, by_fie_id)
        if not raw_fencer_id or not fencer:
            increment(summary, "skipped_missing_fencer")
            continue

        birth_value = fencer_birth_value(fencer)
        if not clean_text(birth_value):
            increment(summary, "skipped_missing_birth_date")
            continue
        if parse_reliable_date(birth_value) is None:
            increment(summary, "skipped_unreliable_birth_date")
            continue

        event_value = ranking_event_date(row)
        if parse_reliable_date(event_value) is None:
            increment(summary, "skipped_missing_result_date")
            continue

        age = age_at_event(birth_value, event_value)
        if not is_reliable_age(age):
            increment(summary, "skipped_implausible_age")
            continue

        observation = build_observation(
            age=age or 0.0,
            source_type="ranking",
            row=row,
            fencer=fencer,
            include_country=include_country,
        )
        if not observation:
            increment(summary, "skipped_missing_group")
            continue

        canonical = canonical_fencer_id(clean_text(fencer.get("id")) or raw_fencer_id, identity_map)
        event_key = clean_text(event_value) or clean_text(row.get("id")) or clean_text(row.get("season")) or ""
        key = (
            "ranking",
            canonical or raw_fencer_id,
            event_key,
            observation["weapon"],
            observation["gender"],
            observation["category"],
            observation["competition_tier"],
        )
        append_or_replace_observation(observations_by_key, key, observation, rank, summary)

    return observations_by_key


def age_distribution(ages: list[float]) -> dict[str, int]:
    buckets = {name: 0 for name, _, _ in AGE_BUCKETS}
    for age in ages:
        for name, lower, upper in AGE_BUCKETS:
            if (lower is None or age >= lower) and (upper is None or age < upper):
                buckets[name] += 1
                break
    return buckets


def aggregate_group(
    key: tuple[str, str, str, str, str, str],
    observations: list[dict[str, Any]],
    min_cohort_size: int,
    computed_at: str,
) -> dict[str, Any]:
    weapon, gender, category, country, tier, source_type = key
    ages = sorted(float(item["age"]) for item in observations)
    sparse = len(ages) < min_cohort_size
    row = {
        "weapon": weapon,
        "gender": gender,
        "category": category,
        "country": country,
        "competition_tier": tier,
        "source_type": source_type,
        "sample_size": len(ages),
        "is_sparse": sparse,
        "min_age": None,
        "p25_age": None,
        "median_age": None,
        "mean_age": None,
        "p75_age": None,
        "max_age": None,
        "peak_age_range_start": None,
        "peak_age_range_end": None,
        "age_distribution": age_distribution(ages),
        "threshold_note": threshold_note(min_cohort_size),
        "computed_at": computed_at,
    }
    if sparse:
        return row

    p25 = percentile(ages, 0.25)
    p75 = percentile(ages, 0.75)
    row.update(
        {
            "min_age": round_metric(ages[0]),
            "p25_age": round_metric(p25),
            "median_age": round_metric(percentile(ages, 0.5)),
            "mean_age": round_metric(sum(ages) / len(ages)),
            "p75_age": round_metric(p75),
            "max_age": round_metric(ages[-1]),
            "peak_age_range_start": round_metric(p25),
            "peak_age_range_end": round_metric(p75),
        }
    )
    return row


def build_peak_age_rows(
    *,
    results: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    ranking_rows: list[dict[str, Any]],
    identity_rows: list[dict[str, Any]],
    competition_details: list[dict[str, Any]] | None = None,
    include_country: bool = False,
    min_cohort_size: int = MIN_COHORT_SIZE,
    computed_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    computed_at = computed_at or datetime.now(UTC).isoformat()
    by_id, by_fie_id = fencer_lookups(fencers)
    tournaments_by_id = tournament_lookup(tournaments)
    details_by_tournament = competition_detail_lookup(competition_details)
    identity_map = build_identity_map(identity_rows)
    summary = blank_summary(
        results,
        fencers,
        tournaments,
        ranking_rows,
        identity_rows,
        competition_details,
    )

    result_observations = collect_result_observations(
        results=results,
        by_id=by_id,
        by_fie_id=by_fie_id,
        tournaments_by_id=tournaments_by_id,
        details_by_tournament=details_by_tournament,
        identity_map=identity_map,
        include_country=include_country,
        summary=summary,
    )
    ranking_observations = collect_ranking_observations(
        ranking_rows=ranking_rows,
        by_id=by_id,
        by_fie_id=by_fie_id,
        identity_map=identity_map,
        include_country=include_country,
        summary=summary,
    )

    observations = list(result_observations.values()) + list(ranking_observations.values())
    for observation in observations:
        observation.pop("_rank", None)
    summary["observations_used"] = len(observations)

    grouped: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[
            (
                observation["weapon"],
                observation["gender"],
                observation["category"],
                observation["country"],
                observation["competition_tier"],
                observation["source_type"],
            )
        ].append(observation)

    rows = [
        aggregate_group(key, grouped[key], min_cohort_size, computed_at)
        for key in sorted(grouped)
    ]
    summary["cohort_rows"] = len(rows)
    summary["sparse_cohort_rows"] = sum(1 for row in rows if row["is_sparse"])
    summary["report_rows"] = len(rows)
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
            break
        offset += page_size
    return rows


def fetch_with_fallbacks(
    client,
    table: str,
    column_options: tuple[str, ...],
    page_size: int = PAGE_SIZE,
    optional: bool = False,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for columns in column_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    if optional:
        print(f"Skipping optional source table {table}: {last_error}")
        return []
    if last_error:
        raise last_error
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


def format_peak_age_report(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    note = threshold_note()
    if rows:
        note = rows[0].get("threshold_note") or note
    lines = [
        "Peak performance age analysis",
        f"Thresholds: {note}",
        (
            "Summary: "
            f"observations_used={summary.get('observations_used', 0)}, "
            f"report_rows={len(rows)}, "
            f"skipped_total={summary.get('skipped_total', 0)}"
        ),
        "weapon | gender | category | country | tier | source | n | peak_range | median | mean | status",
    ]
    for row in rows:
        if row.get("is_sparse"):
            peak_range = "insufficient sample"
            status = "sparse"
        else:
            peak_range = f"{row.get('peak_age_range_start')}-{row.get('peak_age_range_end')}"
            status = "ok"
        lines.append(
            " | ".join(
                [
                    str(row.get("weapon")),
                    str(row.get("gender")),
                    str(row.get("category")),
                    str(row.get("country")),
                    str(row.get("competition_tier")),
                    str(row.get("source_type")),
                    str(row.get("sample_size")),
                    peak_range,
                    str(row.get("median_age")),
                    str(row.get("mean_age")),
                    status,
                ]
            )
        )
    return "\n".join(lines)


def compute_peak_age(
    client=None,
    page_size: int = PAGE_SIZE,
    include_country: bool = False,
    min_cohort_size: int = MIN_COHORT_SIZE,
    write_table: bool = False,
    log_run: bool = True,
    update_state: bool = True,
    computed_at: str | None = None,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    try:
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
        ranking_rows = fetch_with_fallbacks(
            client,
            "fs_rankings_history",
            RANKING_SELECTS,
            page_size=page_size,
            optional=True,
        )
        identity_rows = fetch_with_fallbacks(
            client,
            "fs_fencer_identities",
            IDENTITY_SELECTS,
            page_size=page_size,
            optional=True,
        )
        competition_details = fetch_with_fallbacks(
            client,
            "fs_competition_details",
            COMPETITION_DETAIL_SELECTS,
            page_size=page_size,
            optional=True,
        )

        report_rows, summary = build_peak_age_rows(
            results=results,
            fencers=fencers,
            tournaments=tournaments,
            ranking_rows=ranking_rows,
            identity_rows=identity_rows,
            competition_details=competition_details,
            include_country=include_country,
            min_cohort_size=min_cohort_size,
            computed_at=computed_at,
        )

        written = (
            batch_upsert(client, OUTPUT_TABLE, report_rows, on_conflict=OUTPUT_CONFLICT)
            if write_table and report_rows
            else 0
        )
        summary["written"] = written

        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": datetime.now(UTC).isoformat(), **summary})
        if run_log:
            run_log.complete(
                written=written,
                failed=0,
                skipped=int(summary.get("skipped_total", 0)),
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute aggregate peak-performance age ranges.")
    parser.add_argument("--include-country", action="store_true", help="Group by country instead of ALL.")
    parser.add_argument("--write-table", action="store_true", help=f"Upsert aggregates into {OUTPUT_TABLE}.")
    parser.add_argument("--min-cohort-size", type=int, default=MIN_COHORT_SIZE)
    args = parser.parse_args()

    run_log = ScraperRunLogger(SOURCE).start()
    try:
        client = get_supabase_client()
        computed_at = datetime.now(UTC).isoformat()
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS)
        fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS)
        ranking_rows = fetch_with_fallbacks(client, "fs_rankings_history", RANKING_SELECTS, optional=True)
        identity_rows = fetch_with_fallbacks(client, "fs_fencer_identities", IDENTITY_SELECTS, optional=True)
        competition_details = fetch_with_fallbacks(
            client,
            "fs_competition_details",
            COMPETITION_DETAIL_SELECTS,
            optional=True,
        )
        report_rows, summary = build_peak_age_rows(
            results=results,
            fencers=fencers,
            tournaments=tournaments,
            ranking_rows=ranking_rows,
            identity_rows=identity_rows,
            competition_details=competition_details,
            include_country=args.include_country,
            min_cohort_size=args.min_cohort_size,
            computed_at=computed_at,
        )
        if args.write_table and report_rows:
            summary["written"] = batch_upsert(client, OUTPUT_TABLE, report_rows, on_conflict=OUTPUT_CONFLICT)
        else:
            summary["written"] = 0
        set_state(SOURCE, "last_run", {"updated_at": datetime.now(UTC).isoformat(), **summary})
        run_log.complete(
            written=int(summary["written"]),
            failed=0,
            skipped=int(summary.get("skipped_total", 0)),
            metadata=summary,
        )
        print(format_peak_age_report(report_rows, summary))
    except Exception as exc:
        run_log.error(str(exc))
        raise


if __name__ == "__main__":
    main()

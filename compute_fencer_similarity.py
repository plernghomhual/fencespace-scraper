from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any, Iterable

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "compute_fencer_similarity"
MODEL_VERSION = "public_sports_similarity_v1"
PAGE_SIZE = 1000
BATCH_SIZE = 100
SIMILARITY_CONFLICT = "fencer_id,similar_fencer_id"
SIMILARITY_TABLE = "fs_fencer_similarity"

FENCER_SELECTS = [
    "id,fie_id,name,country,weapon,category,hand,dominant_hand,handedness,date_of_birth,metadata,world_rank,fie_points",
    "id,fie_id,name,country,weapon,category,date_of_birth,metadata,world_rank,fie_points",
    "id,fie_id,name,country,weapon,category,world_rank,fie_points",
    "id,fie_id,name,country,weapon,category",
]
IDENTITY_SELECTS = [
    "id,canonical_id,fs_fencer_row_ids,fencer_ids,fie_ids,metadata",
    "id,fs_fencer_row_ids,fencer_ids,fie_ids,metadata",
    "id,fs_fencer_row_ids,fie_ids",
]
RANKING_SELECTS = [
    "fencer_id,fie_fencer_id,season,weapon,gender,category,rank,points",
    "fie_fencer_id,season,weapon,gender,category,rank,points",
]
RESULT_SELECTS = [
    "tournament_id,fencer_id,fie_fencer_id,name,country,nationality,weapon,gender,category,season,rank,placement,medal",
    "tournament_id,fencer_id,fie_fencer_id,name,country,weapon,category,season,rank,placement",
    "tournament_id,fencer_id,rank,placement",
]
TOURNAMENT_SELECTS = [
    "id,season,weapon,gender,category,type,start_date,end_date,date,name",
    "id,season,weapon,gender,category",
]

WEAPONS = ("Foil", "Epee", "Sabre")
HANDS = ("left", "right")
CAREER_STAGES = ("cadet", "junior", "senior", "veteran")
FACTOR_WEIGHTS = {
    "weapon": 0.24,
    "ranking": 0.22,
    "results": 0.20,
    "style": 0.10,
    "country": 0.08,
    "career_stage": 0.12,
    "hand": 0.04,
}


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    return text.casefold()


def country_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_key(value)).strip("_")


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text).replace(".", "")
    aliases = {
        "usa": "United States",
        "us": "United States",
        "united states": "United States",
        "united states of america": "United States",
        "gbr": "Great Britain",
        "great britain": "Great Britain",
        "kor": "South Korea",
        "korea": "South Korea",
        "hong kong china": "Hong Kong",
        "hong kong": "Hong Kong",
        "ain": "Russia",
        "_ain": "Russia",
        "ain_": "Russia",
    }
    return aliases.get(key, text.title())


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text)
    if key in {"f", "foil", "fleuret"}:
        return "Foil"
    if key in {"e", "epee", "épée"}:
        return "Epee"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    title = text.title()
    return title if title in WEAPONS else None


def normalize_hand(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text)
    if key in {"l", "left", "left hand", "left handed", "left-handed", "lh"}:
        return "left"
    if key in {"r", "right", "right hand", "right handed", "right-handed", "rh"}:
        return "right"
    return None


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text).replace(".", "")
    if key in {"f", "female", "woman", "women", "womens", "women's"}:
        return "Women's"
    if key in {"m", "male", "man", "men", "mens", "men's"}:
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


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    number: int | None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        number = int(match.group(0)) if match else None
    return number if number and number > 0 else None


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    if not text:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime(value: Any) -> datetime:
    text = clean_text(value)
    if not text:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def age_at(birth: date | None, at_time: datetime) -> float | None:
    if not birth:
        return None
    return round((at_time.date() - birth).days / 365.25, 1)


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


def parse_members(value: Any) -> list[str]:
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


def sorted_most_common(values: Iterable[str | None]) -> str | None:
    usable = [value for value in values if value]
    if not usable:
        return None
    counts = Counter(usable)
    return sorted(counts, key=lambda item: (-counts[item], item))[0]


def build_identity_maps(
    identity_rows: list[dict[str, Any]] | None,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    row_to_identity: dict[str, str] = {}
    identity_members: dict[str, list[str]] = {}
    for row in identity_rows or []:
        members = parse_members(
            row.get("fs_fencer_row_ids")
            or row.get("fencer_ids")
            or row.get("source_fencer_ids")
        )
        identity_id = clean_text(row.get("canonical_id")) or clean_text(row.get("id"))
        if not identity_id and members:
            identity_id = members[0]
        if not identity_id:
            continue
        _row_id = clean_text(row.get("id"))
        if not members and _row_id:
            members = [_row_id]
        identity_members[identity_id] = members
        for member in members:
            row_to_identity[member] = identity_id
    return row_to_identity, identity_members


def rank_score(rank: Any) -> float | None:
    number = to_int(rank)
    if number is None:
        return None
    return clamp(1 / math.sqrt(number))


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def population_stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def round_metric(value: float | None, digits: int = 5) -> float | None:
    return round(value, digits) if value is not None else None


def career_stage(category: Any, age: float | None) -> str | None:
    key = normalize_key(category)
    if "veteran" in key:
        return "veteran"
    if "cadet" in key:
        return "cadet"
    if "junior" in key or re.search(r"\bu20\b", key):
        return "junior"
    if "senior" in key:
        return "senior"
    if age is not None:
        if age < 17:
            return "cadet"
        if age < 21:
            return "junior"
        if age >= 40:
            return "veteran"
        return "senior"
    return None


def name_country_key(name: Any, country: Any) -> tuple[str, str] | None:
    name_key = normalize_key(name)
    country_value = normalize_country(country)
    country_norm = normalize_key(country_value)
    if not name_key or not country_norm:
        return None
    return name_key, country_norm


def tournament_lookup(tournaments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in tournaments if row.get("id") is not None}


def best_rank_observation(
    current: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    if current is None:
        return candidate
    current_rank = to_int(current.get("rank"))
    candidate_rank = to_int(candidate.get("rank"))
    if candidate_rank is not None and (current_rank is None or candidate_rank < current_rank):
        return candidate
    if candidate_rank == current_rank and str(candidate.get("competition_id") or "") < str(current.get("competition_id") or ""):
        return candidate
    return current


def _fencer_hand(row: dict[str, Any]) -> str | None:
    for key in ("hand", "dominant_hand", "handedness"):
        hand = normalize_hand(row.get(key))
        if hand:
            return hand
    metadata = parse_metadata(row.get("metadata"))
    for key in ("hand", "dominant_hand", "handedness"):
        hand = normalize_hand(metadata.get(key))
        if hand:
            return hand
    return None


def _fencer_birth(row: dict[str, Any]) -> date | None:
    for key in ("date_of_birth", "birth_date", "dob"):
        parsed = parse_date(row.get(key))
        if parsed:
            return parsed
    metadata = parse_metadata(row.get("metadata"))
    for key in ("date_of_birth", "birth_date", "dob"):
        parsed = parse_date(metadata.get(key))
        if parsed:
            return parsed
    return None


def _prepare_identity_groups(
    fencers: list[dict[str, Any]],
    identity_rows: list[dict[str, Any]] | None,
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, str],
    dict[str, str],
    dict[str, str],
    dict[tuple[str, str], str],
]:
    row_to_identity, _ = build_identity_maps(identity_rows)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    row_to_canonical: dict[str, str] = {}
    identity_to_canonical: dict[str, str] = {}
    fie_to_canonical: dict[str, str] = {}
    name_country_to_canonical: dict[tuple[str, str], str] = {}

    for row in fencers:
        row_id = clean_text(row.get("id"))
        if not row_id:
            continue
        identity_id = row_to_identity.get(row_id, row_id)
        grouped[identity_id].append(row)

    for identity_id in sorted(grouped):
        rows = grouped[identity_id]
        _ids: list[str] = [_id for row in rows if (_id := clean_text(row.get("id")))]
        canonical: str = sorted(_ids)[0] if _ids else identity_id
        identity_to_canonical[identity_id] = canonical
        for row in rows:
            row_id = clean_text(row.get("id"))
            if row_id:
                row_to_canonical[row_id] = canonical
            fie_id = clean_text(row.get("fie_id"))
            if fie_id:
                fie_to_canonical.setdefault(fie_id, canonical)
            key = name_country_key(row.get("name"), row.get("country"))
            if key:
                name_country_to_canonical.setdefault(key, canonical)

    return grouped, row_to_canonical, identity_to_canonical, fie_to_canonical, name_country_to_canonical


def _canonical_from_source_row(
    row: dict[str, Any],
    row_to_canonical: dict[str, str],
    fie_to_canonical: dict[str, str],
    name_country_to_canonical: dict[tuple[str, str], str],
) -> str | None:
    row_id = clean_text(row.get("fencer_id"))
    if row_id and row_id in row_to_canonical:
        return row_to_canonical[row_id]

    fie_id = clean_text(row.get("fie_fencer_id") or row.get("fie_id"))
    if fie_id and fie_id in fie_to_canonical:
        return fie_to_canonical[fie_id]

    key = name_country_key(row.get("name"), row.get("country") or row.get("nationality"))
    if key:
        return name_country_to_canonical.get(key)
    return None


def _result_weapon(
    row: dict[str, Any],
    tournament: dict[str, Any] | None,
) -> str | None:
    return (
        normalize_weapon(row.get("weapon"))
        or normalize_weapon((tournament or {}).get("weapon"))
    )


def _result_category(
    row: dict[str, Any],
    tournament: dict[str, Any] | None,
) -> str | None:
    return normalize_category(
        row.get("category") or (tournament or {}).get("category"),
        row.get("gender") or (tournament or {}).get("gender"),
    )


def _ranking_observations(
    rankings_history: list[dict[str, Any]],
    row_to_canonical: dict[str, str],
    fie_to_canonical: dict[str, str],
    name_country_to_canonical: dict[tuple[str, str], str],
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    by_fencer: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = defaultdict(dict)
    skipped = 0
    for row in rankings_history:
        canonical = _canonical_from_source_row(row, row_to_canonical, fie_to_canonical, name_country_to_canonical)
        weapon = normalize_weapon(row.get("weapon"))
        rank = to_int(row.get("rank"))
        if not canonical or not weapon or rank is None:
            skipped += 1
            continue
        category = normalize_category(row.get("category"), row.get("gender"))
        season = clean_text(row.get("season"))
        key = (season or "", weapon, category or "")
        candidate = {
            "fencer_id": canonical,
            "season": season,
            "weapon": weapon,
            "category": category,
            "rank": rank,
            "points": to_float(row.get("points")),
        }
        by_fencer[canonical][key] = best_rank_observation(by_fencer[canonical].get(key), candidate)
    return {fencer_id: list(rows.values()) for fencer_id, rows in by_fencer.items()}, skipped


def _result_observations(
    results: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    row_to_canonical: dict[str, str],
    fie_to_canonical: dict[str, str],
    name_country_to_canonical: dict[tuple[str, str], str],
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    tournaments_by_id = tournament_lookup(tournaments)
    deduped: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    skipped = 0
    for index, row in enumerate(results):
        canonical = _canonical_from_source_row(row, row_to_canonical, fie_to_canonical, name_country_to_canonical)
        tournament_id = clean_text(row.get("tournament_id") or row.get("competition_id"))
        tournament = tournaments_by_id.get(tournament_id or "")
        weapon = _result_weapon(row, tournament)
        rank = to_int(row.get("rank") if row.get("rank") is not None else row.get("placement"))
        if not canonical or not weapon or rank is None:
            skipped += 1
            continue
        competition_id = tournament_id or f"result:{index}"
        category = _result_category(row, tournament)
        season = clean_text(row.get("season") or (tournament or {}).get("season"))
        observation = {
            "fencer_id": canonical,
            "competition_id": competition_id,
            "weapon": weapon,
            "category": category,
            "season": season,
            "rank": rank,
            "is_medal": rank <= 3 or normalize_key(row.get("medal")) in {"gold", "silver", "bronze", "g", "s", "b"},
        }
        deduped[canonical][(competition_id, weapon)] = best_rank_observation(
            deduped[canonical].get((competition_id, weapon)),
            observation,
        )
    return {fencer_id: list(rows.values()) for fencer_id, rows in deduped.items()}, skipped


def _current_rank_observations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations = []
    for row in rows:
        rank = to_int(row.get("world_rank"))
        weapon = normalize_weapon(row.get("weapon"))
        if rank is None or not weapon:
            continue
        observations.append(
            {
                "season": "current",
                "weapon": weapon,
                "category": normalize_category(row.get("category")),
                "rank": rank,
                "points": to_float(row.get("fie_points")),
            }
        )
    return observations


def _feature_confidence(
    *,
    has_weapon: bool,
    has_country: bool,
    has_hand: bool,
    has_career_stage: bool,
    ranking_count: int,
    result_count: int,
) -> float:
    score = 0.0
    if has_weapon:
        score += 0.20
    if has_country:
        score += 0.10
    if has_hand:
        score += 0.08
    if has_career_stage:
        score += 0.12
    score += min(0.25, ranking_count * 0.125)
    score += min(0.25, result_count * 0.125)
    return round(clamp(score), 5)


def _build_vector(
    *,
    weapon_counts: Counter[str],
    hand: str | None,
    country: str | None,
    stage: str | None,
    age: float | None,
    ranking_observations: list[dict[str, Any]],
    result_observations: list[dict[str, Any]],
) -> dict[str, float]:
    vector: dict[str, float] = {}
    total_weapon_evidence = sum(weapon_counts.values())
    for weapon in WEAPONS:
        vector[f"weapon:{weapon}"] = (
            weapon_counts.get(weapon, 0) / total_weapon_evidence
            if total_weapon_evidence
            else 0.0
        )
    for option in HANDS:
        vector[f"hand:{option}"] = 1.0 if hand == option else 0.0
    if country:
        vector[f"country:{country_key(country)}"] = 1.0
    for option in CAREER_STAGES:
        vector[f"career_stage:{option}"] = 1.0 if stage == option else 0.0
    vector["age_norm"] = clamp((age or 0.0) / 60.0) if age is not None else 0.0

    ranking_scores = [score for obs in ranking_observations if (score := rank_score(obs.get("rank"))) is not None]
    ranking_points: list[float] = [v for obs in ranking_observations if (v := to_float(obs.get("points"))) is not None]
    sorted_rankings = sorted(
        ranking_observations,
        key=lambda obs: str(obs.get("season") or ""),
    )
    if len(sorted_rankings) >= 2:
        first_rank = to_int(sorted_rankings[0].get("rank"))
        latest_rank = to_int(sorted_rankings[-1].get("rank"))
        if first_rank and latest_rank:
            raw_trend = (first_rank - latest_rank) / max(first_rank, latest_rank)
            vector["ranking_trend"] = clamp(0.5 + raw_trend / 2)
        else:
            vector["ranking_trend"] = 0.0
    else:
        vector["ranking_trend"] = 0.0
    vector["ranking_score"] = average(ranking_scores) or 0.0
    vector["points_score"] = clamp(1 - math.exp(-(average(ranking_points) or 0.0) / 200.0))

    result_scores = [score for obs in result_observations if (score := rank_score(obs.get("rank"))) is not None]
    result_ranks: list[int] = [r for obs in result_observations if (r := to_int(obs.get("rank"))) is not None]
    result_count = len(result_ranks)
    vector["result_score"] = average(result_scores) or 0.0
    vector["top8_rate"] = (
        sum(1 for rank in result_ranks if rank <= 8) / result_count
        if result_count
        else 0.0
    )
    vector["medal_rate"] = (
        sum(1 for obs in result_observations if obs.get("is_medal")) / result_count
        if result_count
        else 0.0
    )
    vector["result_volume"] = clamp(math.log1p(result_count) / math.log1p(20))
    vector["rank_consistency"] = (
        clamp(1 / (1 + population_stddev([float(rank) for rank in result_ranks]) / 10))
        if result_ranks
        else 0.0
    )
    return {key: round(value, 5) for key, value in sorted(vector.items())}


def build_feature_vectors(
    *,
    fencers: list[dict[str, Any]],
    rankings_history: list[dict[str, Any]] | None = None,
    results: list[dict[str, Any]] | None = None,
    tournaments: list[dict[str, Any]] | None = None,
    identity_rows: list[dict[str, Any]] | None = None,
    computed_at: str | None = None,
) -> tuple[dict[str, dict[str, Any]], int]:
    computed_time = parse_datetime(computed_at) if computed_at else datetime.now(timezone.utc)
    (
        grouped,
        row_to_canonical,
        identity_to_canonical,
        fie_to_canonical,
        name_country_to_canonical,
    ) = _prepare_identity_groups(fencers, identity_rows)

    rankings_by_fencer, skipped_rankings = _ranking_observations(
        rankings_history or [],
        row_to_canonical,
        fie_to_canonical,
        name_country_to_canonical,
    )
    results_by_fencer, skipped_results = _result_observations(
        results or [],
        tournaments or [],
        row_to_canonical,
        fie_to_canonical,
        name_country_to_canonical,
    )

    identity_for_canonical = {
        canonical: identity_id
        for identity_id, canonical in identity_to_canonical.items()
    }
    features: dict[str, dict[str, Any]] = {}

    for identity_id in sorted(grouped):
        rows = grouped[identity_id]
        canonical = identity_to_canonical[identity_id]
        ranking_observations = list(rankings_by_fencer.get(canonical, []))
        ranking_observations.extend(_current_rank_observations(rows))
        result_observations = list(results_by_fencer.get(canonical, []))

        weapon_counts: Counter[str] = Counter()
        for row in rows:
            weapon = normalize_weapon(row.get("weapon"))
            if weapon:
                weapon_counts[weapon] += 1
        for obs in ranking_observations + result_observations:
            weapon = normalize_weapon(obs.get("weapon"))
            if weapon:
                weapon_counts[weapon] += 1

        countries = [normalize_country(row.get("country")) for row in rows]
        hands = [_fencer_hand(row) for row in rows]
        births = [_fencer_birth(row) for row in rows]
        birth = sorted([item for item in births if item])[0] if any(births) else None
        age = age_at(birth, computed_time)
        categories = [normalize_category(row.get("category")) for row in rows]
        categories.extend(obs.get("category") for obs in ranking_observations + result_observations)
        stage = sorted_most_common(career_stage(category, age) for category in categories)
        country = sorted_most_common(countries)
        hand = sorted_most_common(hands)
        primary_weapon = (
            sorted(weapon_counts, key=lambda weapon: (-weapon_counts[weapon], weapon))[0]
            if weapon_counts
            else None
        )

        vector = _build_vector(
            weapon_counts=weapon_counts,
            hand=hand,
            country=country,
            stage=stage,
            age=age,
            ranking_observations=ranking_observations,
            result_observations=result_observations,
        )
        ranking_count = len(ranking_observations)
        result_count = len(result_observations)
        sample_size = ranking_count + result_count
        confidence = _feature_confidence(
            has_weapon=bool(weapon_counts),
            has_country=country is not None,
            has_hand=hand is not None,
            has_career_stage=stage is not None,
            ranking_count=ranking_count,
            result_count=result_count,
        )
        features[canonical] = {
            "fencer_id": canonical,
            "identity_id": identity_for_canonical.get(canonical, identity_id),
            "primary_weapon": primary_weapon,
            "sample_size": sample_size,
            "confidence": confidence,
            "vector": vector,
            "attributes": {
                "country": country,
                "country_key": country_key(country) if country else None,
                "hand": hand,
                "career_stage": stage,
                "age": age,
                "weapons": sorted(weapon_counts),
                "ranking_count": ranking_count,
                "result_count": result_count,
            },
        }

    return features, skipped_rankings + skipped_results


def numeric_similarity(
    feature_a: dict[str, Any],
    feature_b: dict[str, Any],
    keys: list[str],
) -> float:
    diffs = [
        abs(float(feature_a["vector"].get(key, 0.0)) - float(feature_b["vector"].get(key, 0.0)))
        for key in keys
    ]
    return clamp(1 - (sum(diffs) / len(diffs)))


def _factor_scores(
    feature_a: dict[str, Any],
    feature_b: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str], float]:
    factors: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    weighted_score = 0.0
    used_weight = 0.0

    def add(name: str, score: float | None, sample_size: int = 0) -> None:
        nonlocal weighted_score, used_weight
        weight = FACTOR_WEIGHTS[name]
        if score is None:
            missing.append(name)
            return
        score = round_metric(clamp(score)) or 0.0
        factors[name] = {
            "score": score,
            "weight": weight,
            "sample_size": sample_size,
        }
        weighted_score += score * weight
        used_weight += weight

    attr_a = feature_a["attributes"]
    attr_b = feature_b["attributes"]

    add(
        "weapon",
        1.0 if feature_a.get("primary_weapon") and feature_a.get("primary_weapon") == feature_b.get("primary_weapon")
        else numeric_similarity(feature_a, feature_b, [f"weapon:{weapon}" for weapon in WEAPONS])
        if feature_a.get("primary_weapon") and feature_b.get("primary_weapon")
        else None,
        sample_size=min(feature_a["sample_size"], feature_b["sample_size"]),
    )

    add(
        "ranking",
        numeric_similarity(feature_a, feature_b, ["ranking_score", "ranking_trend", "points_score"])
        if attr_a["ranking_count"] and attr_b["ranking_count"]
        else None,
        sample_size=min(attr_a["ranking_count"], attr_b["ranking_count"]),
    )
    add(
        "results",
        numeric_similarity(feature_a, feature_b, ["result_score", "top8_rate", "medal_rate", "result_volume"])
        if attr_a["result_count"] and attr_b["result_count"]
        else None,
        sample_size=min(attr_a["result_count"], attr_b["result_count"]),
    )
    add(
        "style",
        numeric_similarity(feature_a, feature_b, ["rank_consistency", "top8_rate", "medal_rate"])
        if attr_a["result_count"] and attr_b["result_count"]
        else None,
        sample_size=min(attr_a["result_count"], attr_b["result_count"]),
    )
    add(
        "country",
        1.0 if attr_a.get("country_key") == attr_b.get("country_key") else 0.0
        if attr_a.get("country_key") and attr_b.get("country_key")
        else None,
    )

    career_score = None
    if attr_a.get("career_stage") and attr_b.get("career_stage"):
        stage_score = 1.0 if attr_a["career_stage"] == attr_b["career_stage"] else 0.25
        if attr_a.get("age") is not None and attr_b.get("age") is not None:
            age_score = 1 - min(abs(attr_a["age"] - attr_b["age"]) / 20, 1)
            career_score = (stage_score + age_score) / 2
        else:
            career_score = stage_score
    add("career_stage", career_score)

    hand_score = None
    if attr_a.get("hand") and attr_b.get("hand"):
        hand_score = 1.0 if attr_a["hand"] == attr_b["hand"] else 0.0
    add("hand", hand_score)

    return factors, missing, used_weight


def score_feature_pair(
    feature_a: dict[str, Any],
    feature_b: dict[str, Any],
    *,
    model_version: str = MODEL_VERSION,
) -> dict[str, Any] | None:
    if feature_a["identity_id"] == feature_b["identity_id"]:
        return None
    factors, missing, used_weight = _factor_scores(feature_a, feature_b)
    if used_weight <= 0:
        return None

    score = sum(item["score"] * item["weight"] for item in factors.values()) / used_weight
    coverage = used_weight / sum(FACTOR_WEIGHTS.values())
    confidence = math.sqrt(feature_a["confidence"] * feature_b["confidence"]) * coverage
    return {
        "score": round_metric(score),
        "confidence": round_metric(confidence),
        "sample_size": min(feature_a["sample_size"], feature_b["sample_size"]),
        "factor_breakdown": {
            **factors,
            "missing_factors": sorted(missing),
            "model_version": model_version,
            "feature_confidence": {
                feature_a["fencer_id"]: feature_a["confidence"],
                feature_b["fencer_id"]: feature_b["confidence"],
            },
            "used_weight": round_metric(used_weight),
        },
    }


def _pair_key(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def _pairs_from_group(ids: list[str], *, window: int | None = None) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    sorted_ids = sorted(set(ids))
    for index, left in enumerate(sorted_ids):
        candidates = sorted_ids[index + 1 :] if window is None else sorted_ids[index + 1 : index + 1 + window]
        for right in candidates:
            pairs.add(_pair_key(left, right))
    return pairs


def candidate_pairs(
    features: dict[str, dict[str, Any]],
    *,
    exhaustive_limit: int = 500,
    neighbor_window: int = 50,
) -> set[tuple[str, str]]:
    ids = sorted(features)
    if len(ids) <= exhaustive_limit:
        return _pairs_from_group(ids)

    pairs: set[tuple[str, str]] = set()
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for fencer_id, feature in features.items():
        attrs = feature["attributes"]
        primary_weapon = feature.get("primary_weapon") or "unknown"
        grouped[("weapon", primary_weapon)].append(fencer_id)
        if attrs.get("country_key"):
            grouped[("country_weapon", f"{attrs['country_key']}:{primary_weapon}")].append(fencer_id)
        if attrs.get("career_stage"):
            grouped[("stage_weapon", f"{attrs['career_stage']}:{primary_weapon}")].append(fencer_id)

    for group_ids in grouped.values():
        ranked_ids = sorted(
            set(group_ids),
            key=lambda fencer_id: (
                features[fencer_id]["vector"].get("ranking_score", 0.0),
                features[fencer_id]["vector"].get("result_score", 0.0),
                fencer_id,
            ),
        )
        pairs.update(_pairs_from_group(ranked_ids, window=neighbor_window))
    return pairs


def build_similarity_rows(
    features: dict[str, dict[str, Any]],
    *,
    model_version: str = MODEL_VERSION,
    updated_at: str | None = None,
    max_recommendations_per_fencer: int | None = 10,
) -> list[dict[str, Any]]:
    updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for left, right in sorted(candidate_pairs(features)):
        if left == right:
            continue
        score = score_feature_pair(features[left], features[right], model_version=model_version)
        if not score:
            continue
        fencer_id, similar_fencer_id = _pair_key(left, right)
        rows.append(
            {
                "fencer_id": fencer_id,
                "similar_fencer_id": similar_fencer_id,
                "score": score["score"],
                "confidence": score["confidence"],
                "sample_size": score["sample_size"],
                "factor_breakdown": score["factor_breakdown"],
                "model_version": model_version,
                "updated_at": updated_at,
            }
        )

    rows.sort(key=lambda row: (row["fencer_id"], row["similar_fencer_id"]))
    if max_recommendations_per_fencer is None:
        return rows

    per_fencer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        per_fencer[row["fencer_id"]].append(row)
        per_fencer[row["similar_fencer_id"]].append(row)

    keep: set[tuple[str, str]] = set()
    for fencer_id, fencer_rows in per_fencer.items():
        ranked = sorted(
            fencer_rows,
            key=lambda row: (
                -row["score"],
                -row["confidence"],
                row["similar_fencer_id"] if row["fencer_id"] == fencer_id else row["fencer_id"],
            ),
        )
        for row in ranked[:max_recommendations_per_fencer]:
            keep.add((row["fencer_id"], row["similar_fencer_id"]))

    return [row for row in rows if (row["fencer_id"], row["similar_fencer_id"]) in keep]


def fetch_all(client, table: str, columns: str, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        page = (
            client.table(table)
            .select(columns)
            .range(start, start + page_size - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < page_size:
            return rows
        start += page_size


def fetch_with_fallbacks(
    client,
    table: str,
    select_options: list[str],
    *,
    page_size: int,
) -> tuple[list[dict[str, Any]], str]:
    last_error: Exception | None = None
    for columns in select_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size), columns
        except Exception as exc:
            last_error = exc
            print(f"  Select fallback for {table}: {exc}")
    if last_error:
        raise last_error
    return [], select_options[-1]


def upsert_similarity_rows(
    client,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = BATCH_SIZE,
) -> tuple[int, int]:
    written = 0
    failed = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        try:
            client.table(SIMILARITY_TABLE).upsert(batch, on_conflict=SIMILARITY_CONFLICT).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  fs_fencer_similarity upsert batch {start // batch_size} failed: {exc}")
    return written, failed


def compute_fencer_similarity(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    max_recommendations_per_fencer: int | None = 10,
    log_run: bool = True,
    update_state: bool = True,
    updated_at: str | None = None,
) -> dict[str, int]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        fencers, _ = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
        identity_rows, _ = fetch_with_fallbacks(client, "fs_fencer_identities", IDENTITY_SELECTS, page_size=page_size)
        rankings, _ = fetch_with_fallbacks(client, "fs_rankings_history", RANKING_SELECTS, page_size=page_size)
        results, _ = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        tournaments, _ = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)

        features, skipped = build_feature_vectors(
            fencers=fencers,
            rankings_history=rankings,
            results=results,
            tournaments=tournaments,
            identity_rows=identity_rows,
            computed_at=updated_at,
        )
        rows = build_similarity_rows(
            features,
            updated_at=updated_at,
            max_recommendations_per_fencer=max_recommendations_per_fencer,
        )
        written, failed = upsert_similarity_rows(client, rows, batch_size=batch_size) if rows else (0, 0)
        summary = {
            "fencers_read": len(fencers),
            "identity_rows": len(identity_rows),
            "rankings_read": len(rankings),
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "feature_rows": len(features),
            "similarity_rows": len(rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
        }
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": datetime.now(timezone.utc).isoformat(), **summary})
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Fencer similarity computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_fencer_similarity()
    print(
        "Fencer similarity computation complete - "
        f"{summary['feature_rows']} identities analyzed, "
        f"{summary['written']} similarity rows written, "
        f"{summary['failed']} failed, {summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()

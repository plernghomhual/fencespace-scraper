from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

SOURCE = "compute_sponsorship_matches"
PAGE_SIZE = 1000
BATCH_SIZE = 100
MIN_MATCH_SCORE = 35.0
MAX_MATCHES_PER_BRAND = 50

MATCH_WEIGHTS = {
    "performance": 0.35,
    "geography": 0.15,
    "weapon": 0.15,
    "brand_affinity": 0.20,
    "social_reach": 0.15,
}

FENCER_SELECTS = (
    "id,name,country,nationality,weapon,world_rank,date_of_birth,birth_date,dob,category,metadata",
    "id,name,country,nationality,weapon,world_rank,date_of_birth,category,metadata",
    "id,name,country,weapon,world_rank,date_of_birth,metadata",
    "id,name,country,weapon,world_rank,metadata",
)
PERFORMANCE_SELECT = (
    "fencer_id,weapon,competitions_count,avg_delta,overperformance_rate,clutch_score"
)
CAREER_SELECT = (
    "fencer_id,total_competitions,gold_medals,silver_medals,bronze_medals,top8_count,best_rank"
)
EQUIPMENT_SELECT = "fencer_id,brand,equipment_type,sponsor_name,confidence,metadata"
SOCIAL_SELECT = "fencer_id,platform,verified,metadata"
REVIEW_SELECT = "brand,category,rating,review_count,metadata"

COUNTRY_ALIASES = {
    "united states": "united states",
    "united states of america": "united states",
    "usa": "united states",
    "us": "united states",
    "u.s.": "united states",
    "u.s.a.": "united states",
    "great britain": "united kingdom",
    "uk": "united kingdom",
    "u.k.": "united kingdom",
    "england": "united kingdom",
}

WEAPON_ALIASES = {
    "e": "Epee",
    "epee": "Epee",
    "epée": "Epee",
    "foil": "Foil",
    "f": "Foil",
    "sabre": "Sabre",
    "saber": "Sabre",
    "s": "Sabre",
}

FOLLOWER_KEYS = {
    "followers",
    "follower_count",
    "followers_count",
    "subscriber_count",
    "subscribers",
    "public_followers",
}


@dataclass
class BrandProfile:
    brand: str
    countries: set[str] = field(default_factory=set)
    weapons: set[str] = field(default_factory=set)
    equipment_types: set[str] = field(default_factory=set)
    categories: set[str] = field(default_factory=set)
    known_fencer_ids: set[str] = field(default_factory=set)
    used_by_countries: set[str] = field(default_factory=set)
    used_by_weapons: set[str] = field(default_factory=set)
    review_count: int = 0


@dataclass(frozen=True)
class ScorePart:
    value: float
    has_data: bool
    note: str
    missing_label: str | None = None


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def metadata_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def normalize_lookup(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = text.casefold()
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip() or None


def normalize_country(value: Any) -> str | None:
    key = normalize_lookup(value)
    if not key:
        return None
    return COUNTRY_ALIASES.get(key, key)


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold().strip()
    return WEAPON_ALIASES.get(key, text.title())


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        return float(match.group(0)) if match else None


def coerce_positive_int(value: Any) -> int | None:
    number = coerce_float(value)
    if number is None:
        return None
    integer = int(number)
    return integer if integer > 0 else None


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def component(value: float) -> float:
    return round(clamp(value), 4)


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    if text.startswith("+"):
        text = text[1:]
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def age_on(birth_date: date, today: date) -> int:
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def minor_policy_allowed(fencer: dict[str, Any]) -> bool:
    metadata = metadata_dict(fencer.get("metadata"))
    return any(
        metadata.get(key) is True
        for key in (
            "allow_minor_sponsorship",
            "sponsorship_policy_allows_minors",
            "sponsorship_allowed_for_minors",
        )
    )


def ineligibility_reason(fencer: dict[str, Any], today: date) -> str | None:
    metadata = metadata_dict(fencer.get("metadata"))
    if metadata.get("sponsorship_ineligible") is True or metadata.get("ineligible") is True:
        return "marked sponsorship-ineligible"

    birth_date = (
        parse_date(fencer.get("date_of_birth"))
        or parse_date(fencer.get("birth_date"))
        or parse_date(fencer.get("dob"))
    )
    if birth_date and age_on(birth_date, today) < 18 and not minor_policy_allowed(fencer):
        return "known minor"

    category = normalize_lookup(fencer.get("category"))
    if category and re.search(r"\b(cadet|u17|u16|youth|minor)\b", category):
        if not minor_policy_allowed(fencer):
            return "youth category"
    return None


def age_status(fencer: dict[str, Any], today: date) -> str:
    birth_date = (
        parse_date(fencer.get("date_of_birth"))
        or parse_date(fencer.get("birth_date"))
        or parse_date(fencer.get("dob"))
    )
    if not birth_date:
        return "unknown"
    return "adult" if age_on(birth_date, today) >= 18 else "minor"


def metadata_values(metadata: dict[str, Any], keys: set[str]) -> list[Any]:
    values: list[Any] = []
    for key, value in metadata.items():
        normalized = normalize_lookup(key)
        if normalized and normalized.replace(" ", "_") in keys:
            values.append(value)
    return values


def flatten_string_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;/|]", value) if part.strip()]
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(flatten_string_values(item))
        return values
    return [str(value)]


def extract_metadata_countries(metadata: dict[str, Any]) -> set[str]:
    countries: set[str] = set()
    keys = {"country", "countries", "brand_country", "hq_country", "market", "markets"}
    for value in metadata_values(metadata, keys):
        for country in flatten_string_values(value):
            normalized = normalize_country(country)
            if normalized:
                countries.add(normalized)
    return countries


def extract_weapons_from_text(value: Any) -> set[str]:
    text = clean_text(value)
    if not text:
        return set()
    weapons = set()
    normalized = text.casefold()
    for key, weapon in WEAPON_ALIASES.items():
        if re.search(rf"\b{re.escape(key)}\b", normalized):
            weapons.add(weapon)
    return weapons


def extract_metadata_weapons(metadata: dict[str, Any]) -> set[str]:
    weapons: set[str] = set()
    for value in metadata_values(metadata, {"weapon", "weapons", "discipline", "disciplines"}):
        for item in flatten_string_values(value):
            weapon = normalize_weapon(item)
            if weapon:
                weapons.add(weapon)
    return weapons


def build_brand_profiles(
    equipment_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    fencers_by_id: dict[str, dict[str, Any]],
) -> dict[str, BrandProfile]:
    profiles: dict[str, BrandProfile] = {}

    def profile_for(brand_value: Any) -> BrandProfile | None:
        brand = clean_text(brand_value)
        if not brand:
            return None
        key = brand.casefold()
        if key not in profiles:
            profiles[key] = BrandProfile(brand=brand)
        return profiles[key]

    for row in review_rows:
        profile = profile_for(row.get("brand"))
        if not profile:
            continue
        metadata = metadata_dict(row.get("metadata"))
        category = clean_text(row.get("category"))
        if category:
            profile.categories.add(category)
            profile.weapons.update(extract_weapons_from_text(category))
            profile.equipment_types.add(category.casefold())
        profile.countries.update(extract_metadata_countries(metadata))
        profile.weapons.update(extract_metadata_weapons(metadata))
        profile.review_count += 1

    for row in equipment_rows:
        profile = profile_for(row.get("brand"))
        if not profile:
            continue
        fencer_id = clean_text(row.get("fencer_id"))
        if fencer_id:
            profile.known_fencer_ids.add(fencer_id)
            fencer = fencers_by_id.get(fencer_id)
            if fencer:
                country = normalize_country(fencer.get("country") or fencer.get("nationality"))
                weapon = normalize_weapon(fencer.get("weapon"))
                if country:
                    profile.used_by_countries.add(country)
                if weapon:
                    profile.used_by_weapons.add(weapon)

        equipment_type = clean_text(row.get("equipment_type"))
        if equipment_type:
            profile.equipment_types.add(equipment_type.casefold())
            profile.weapons.update(extract_weapons_from_text(equipment_type))
        metadata = metadata_dict(row.get("metadata"))
        profile.countries.update(extract_metadata_countries(metadata))
        profile.weapons.update(extract_metadata_weapons(metadata))

    return profiles


def score_performance(
    fencer: dict[str, Any],
    performance_rows: list[dict[str, Any]],
    career_row: dict[str, Any] | None,
) -> ScorePart:
    signals: list[float] = []
    fencer_weapon = normalize_weapon(fencer.get("weapon"))

    rows = performance_rows
    if fencer_weapon:
        matching = [row for row in rows if normalize_weapon(row.get("weapon")) == fencer_weapon]
        if matching:
            rows = matching

    for row in rows[:3]:
        clutch = coerce_float(row.get("clutch_score") if row.get("clutch_score") is not None else row.get("avg_delta"))
        if clutch is not None:
            signals.append(clamp((clutch + 20.0) / 40.0))
        overperformance = coerce_float(row.get("overperformance_rate"))
        if overperformance is not None:
            signals.append(clamp(overperformance / 100.0))
        competitions = coerce_positive_int(row.get("competitions_count"))
        if competitions is not None:
            signals.append(clamp(competitions / 12.0))

    if career_row:
        total = coerce_positive_int(career_row.get("total_competitions")) or 0
        if total:
            top8 = coerce_positive_int(career_row.get("top8_count")) or 0
            signals.append(clamp(top8 / total))
        medals = sum(
            coerce_positive_int(career_row.get(key)) or 0
            for key in ("gold_medals", "silver_medals", "bronze_medals")
        )
        if medals:
            signals.append(clamp(medals / 5.0))
        best_rank = coerce_positive_int(career_row.get("best_rank"))
        if best_rank:
            signals.append(clamp((65.0 - min(best_rank, 64)) / 64.0))

    world_rank = coerce_positive_int(fencer.get("world_rank"))
    if world_rank:
        signals.append(clamp((201.0 - min(world_rank, 200)) / 200.0))

    if not signals:
        return ScorePart(0.2, False, "no public performance signal", "public performance")

    value = sum(signals) / len(signals)
    return ScorePart(component(value), True, "public performance signal")


def score_geography(fencer: dict[str, Any], profile: BrandProfile) -> ScorePart:
    fencer_country = normalize_country(fencer.get("country") or fencer.get("nationality"))
    brand_countries = profile.countries | profile.used_by_countries
    if fencer_country and fencer_country in brand_countries:
        return ScorePart(1.0, True, f"geography matches {fencer_country.title()}")
    if fencer_country and brand_countries:
        return ScorePart(0.25, True, "geography does not match known brand markets")
    if fencer_country:
        return ScorePart(0.35, False, "brand geography unknown", "brand geography")
    return ScorePart(0.2, False, "fencer geography unknown", "geography")


def score_weapon(fencer: dict[str, Any], profile: BrandProfile) -> ScorePart:
    fencer_weapon = normalize_weapon(fencer.get("weapon"))
    brand_weapons = profile.weapons | profile.used_by_weapons
    if fencer_weapon and fencer_weapon in brand_weapons:
        return ScorePart(1.0, True, f"weapon aligns with {fencer_weapon}")
    if fencer_weapon and brand_weapons:
        return ScorePart(0.25, True, "weapon differs from known brand focus")
    if fencer_weapon and profile.equipment_types:
        return ScorePart(0.65, True, "brand has generic fencing equipment affinity")
    if fencer_weapon:
        return ScorePart(0.35, False, "brand weapon focus unknown", "brand weapon focus")
    return ScorePart(0.2, False, "fencer weapon unknown", "weapon")


def brand_matches(value: Any, brand: str) -> bool:
    left = clean_text(value)
    return bool(left and left.casefold() == brand.casefold())


def score_brand_affinity(
    fencer: dict[str, Any],
    profile: BrandProfile,
    equipment_rows: list[dict[str, Any]],
) -> ScorePart:
    for row in equipment_rows:
        if not brand_matches(row.get("brand"), profile.brand):
            continue
        sponsor = clean_text(row.get("sponsor_name"))
        confidence = (clean_text(row.get("confidence")) or "").casefold()
        if sponsor and sponsor.casefold() == profile.brand.casefold():
            return ScorePart(1.0, True, "existing brand affinity from sponsorship/equipment")
        if confidence == "high":
            return ScorePart(0.95, True, "existing brand affinity from high-confidence equipment")
        if confidence == "medium":
            return ScorePart(0.85, True, "existing brand affinity from equipment")
        return ScorePart(0.75, True, "existing brand affinity from low-confidence equipment")

    fencer_country = normalize_country(fencer.get("country") or fencer.get("nationality"))
    fencer_weapon = normalize_weapon(fencer.get("weapon"))
    if fencer_country and fencer_country in profile.used_by_countries:
        return ScorePart(0.45, True, "brand used by fencers from same geography")
    if fencer_weapon and fencer_weapon in profile.used_by_weapons:
        return ScorePart(0.4, True, "brand used by fencers in same weapon")
    return ScorePart(0.2, False, "no equipment or brand affinity signal", "equipment/brand affinity")


def find_numeric_metadata(value: Any) -> float | None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = normalize_lookup(key)
            if normalized and normalized.replace(" ", "_") in FOLLOWER_KEYS:
                number = coerce_float(item)
                if number is not None:
                    return number
            nested = find_numeric_metadata(item)
            if nested is not None:
                return nested
    elif isinstance(value, (list, tuple)):
        for item in value:
            nested = find_numeric_metadata(item)
            if nested is not None:
                return nested
    return None


def score_social_reach(social_rows: list[dict[str, Any]]) -> ScorePart:
    if not social_rows:
        return ScorePart(0.15, False, "missing public social reach", "public social reach")

    follower_counts = [
        count
        for count in (find_numeric_metadata(metadata_dict(row.get("metadata"))) for row in social_rows)
        if count is not None and count >= 0
    ]
    verified_count = sum(1 for row in social_rows if row.get("verified") is True)
    platform_count = len({clean_text(row.get("platform")) for row in social_rows if clean_text(row.get("platform"))})

    if follower_counts:
        best_count = max(follower_counts)
        value = clamp(math.log10(best_count + 1.0) / 6.0)
        value = clamp(value + min(verified_count * 0.05, 0.1) + min(platform_count * 0.03, 0.09))
        return ScorePart(component(value), True, "public social reach with follower counts")

    value = clamp(0.2 + min(platform_count * 0.12, 0.36) + min(verified_count * 0.08, 0.16))
    return ScorePart(component(value), True, "public social accounts without follower counts")


def confidence_label(parts: dict[str, ScorePart], fencer: dict[str, Any], today: date) -> str:
    coverage = sum(1 for part in parts.values() if part.has_data) / len(parts)
    penalty = 0.0
    if not parts["social_reach"].has_data:
        penalty += 0.15
    if not parts["brand_affinity"].has_data:
        penalty += 0.10
    if not parts["weapon"].has_data:
        penalty += 0.05
    if age_status(fencer, today) == "unknown":
        penalty += 0.15
    score = coverage - penalty
    if score >= 0.72:
        return "high"
    if score >= 0.42:
        return "medium"
    return "low"


def explain_match(
    brand: str,
    fencer: dict[str, Any],
    parts: dict[str, ScorePart],
    confidence: str,
) -> str:
    fencer_name = clean_text(fencer.get("name")) or clean_text(fencer.get("id")) or "fencer"
    notes = [part.note for part in parts.values()]
    missing = [part.missing_label for part in parts.values() if part.missing_label]
    if missing:
        notes.append("sparse data: missing " + ", ".join(dict.fromkeys(missing)))
    return (
        f"{brand} candidate for {fencer_name}: "
        + "; ".join(notes)
        + f". Confidence {confidence}."
    )


def build_score_components(parts: dict[str, ScorePart]) -> dict[str, Any]:
    components: dict[str, Any] = {name: part.value for name, part in parts.items()}
    components["weights"] = dict(MATCH_WEIGHTS)
    components["data_quality"] = {
        "available": sorted(name for name, part in parts.items() if part.has_data),
        "missing": sorted(
            dict.fromkeys(part.missing_label for part in parts.values() if part.missing_label)
        ),
    }
    return components


def score_match(
    fencer: dict[str, Any],
    profile: BrandProfile,
    performance_rows: list[dict[str, Any]],
    career_row: dict[str, Any] | None,
    equipment_rows: list[dict[str, Any]],
    social_rows: list[dict[str, Any]],
    today: date,
) -> tuple[float, dict[str, ScorePart], str, str]:
    parts = {
        "performance": score_performance(fencer, performance_rows, career_row),
        "geography": score_geography(fencer, profile),
        "weapon": score_weapon(fencer, profile),
        "brand_affinity": score_brand_affinity(fencer, profile, equipment_rows),
        "social_reach": score_social_reach(social_rows),
    }
    score = round(
        sum(parts[name].value * weight for name, weight in MATCH_WEIGHTS.items()) * 100.0,
        2,
    )
    confidence = confidence_label(parts, fencer, today)
    explanation = explain_match(profile.brand, fencer, parts, confidence)
    return score, parts, confidence, explanation


def group_by_fencer(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        fencer_id = clean_text(row.get("fencer_id"))
        if fencer_id:
            grouped[fencer_id].append(row)
    return grouped


def career_by_fencer(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["fencer_id"]): row
        for row in rows
        if row.get("fencer_id") is not None
    }


def build_sponsorship_match_rows(
    *,
    fencers: list[dict[str, Any]],
    performance_rows: list[dict[str, Any]],
    career_rows: list[dict[str, Any]],
    equipment_rows: list[dict[str, Any]],
    social_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    today: date | None = None,
    updated_at: str | None = None,
    min_score: float = MIN_MATCH_SCORE,
    max_matches_per_brand: int = MAX_MATCHES_PER_BRAND,
) -> tuple[list[dict[str, Any]], int]:
    today = today or date.today()
    now = updated_at or datetime.now(timezone.utc).isoformat()
    fencers_by_id = {
        str(row["id"]): row
        for row in fencers
        if row.get("id") is not None
    }
    profiles = build_brand_profiles(equipment_rows, review_rows, fencers_by_id)
    performance_by_id = group_by_fencer(performance_rows)
    equipment_by_id = group_by_fencer(equipment_rows)
    social_by_id = group_by_fencer(social_rows)
    career_index = career_by_fencer(career_rows)

    candidates_by_brand: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped = 0

    for fencer in fencers:
        fencer_id = clean_text(fencer.get("id"))
        if not fencer_id:
            skipped += 1
            continue
        if ineligibility_reason(fencer, today):
            skipped += 1
            continue

        for profile in profiles.values():
            score, parts, confidence, explanation = score_match(
                fencer,
                profile,
                performance_by_id.get(fencer_id, []),
                career_index.get(fencer_id),
                equipment_by_id.get(fencer_id, []),
                social_by_id.get(fencer_id, []),
                today,
            )
            if score < min_score:
                continue
            candidates_by_brand[profile.brand].append(
                {
                    "brand": profile.brand,
                    "fencer_id": fencer_id,
                    "match_score": score,
                    "score_components": build_score_components(parts),
                    "confidence": confidence,
                    "explanation": explanation,
                    "updated_at": now,
                }
            )

    rows: list[dict[str, Any]] = []
    for brand in sorted(candidates_by_brand):
        brand_rows = sorted(
            candidates_by_brand[brand],
            key=lambda row: (-row["match_score"], row["fencer_id"]),
        )
        rows.extend(brand_rows[:max_matches_per_brand])
    return rows, skipped


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


def fetch_optional(client, table: str, columns: str, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    try:
        return fetch_all(client, table, columns, page_size=page_size)
    except Exception as exc:
        print(f"Skipping optional sponsorship input {table}: {exc}")
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


def compute_sponsorship_matches(
    client=None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    today: date | None = None,
    updated_at: str | None = None,
) -> dict[str, int]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
        performance_rows = fetch_optional(
            client,
            "fs_fencer_performance_analysis",
            PERFORMANCE_SELECT,
            page_size=page_size,
        )
        career_rows = fetch_optional(
            client,
            "fs_fencer_career_stats",
            CAREER_SELECT,
            page_size=page_size,
        )
        equipment_rows = fetch_optional(
            client,
            "fs_fencer_equipment",
            EQUIPMENT_SELECT,
            page_size=page_size,
        )
        social_rows = fetch_optional(
            client,
            "fs_fencer_social_media",
            SOCIAL_SELECT,
            page_size=page_size,
        )
        review_rows = fetch_optional(
            client,
            "fs_equipment_reviews",
            REVIEW_SELECT,
            page_size=page_size,
        )

        match_rows, skipped = build_sponsorship_match_rows(
            fencers=fencers,
            performance_rows=performance_rows,
            career_rows=career_rows,
            equipment_rows=equipment_rows,
            social_rows=social_rows,
            review_rows=review_rows,
            today=today,
            updated_at=updated_at,
        )
        written = (
            batch_upsert(
                client,
                "fs_sponsorship_matches",
                match_rows,
                on_conflict="brand,fencer_id",
            )
            if match_rows
            else 0
        )
        summary = {
            "fencers_read": len(fencers),
            "performance_rows_read": len(performance_rows),
            "career_rows_read": len(career_rows),
            "equipment_rows_read": len(equipment_rows),
            "social_rows_read": len(social_rows),
            "review_rows_read": len(review_rows),
            "matches_built": len(match_rows),
            "written": written,
            "skipped": skipped,
        }
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": datetime.now(timezone.utc).isoformat(), **summary})
        if run_log:
            run_log.complete(written=written, failed=0, skipped=skipped, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Sponsorship match computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_sponsorship_matches()
    print(
        "Sponsorship match computation complete - "
        f"{summary['matches_built']} rows built, {summary['written']} rows upserted"
    )


if __name__ == "__main__":
    main()

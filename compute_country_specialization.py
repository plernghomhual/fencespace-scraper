from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

try:
    from supabase import create_client
except Exception:  # pragma: no cover - dependency errors surface when a client is required.
    create_client = None


SOURCE = "compute_country_specialization"
PAGE_SIZE = 1000
BATCH_SIZE = 200
SPECIALIZATION_TABLE = "fs_country_specialization"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

COUNTRY_CODE_SELECTS = (
    "alpha3,alpha2,name,olympic_code,fie_code,aliases",
    "country_code,alpha2,name,olympic_code,fie_code,aliases",
    "code,name,aliases",
)
COUNTRY_DEPTH_SELECTS = (
    "country,weapon,category,fencers_in_top16,fencers_in_top32,fencers_in_top64,total_ranked,avg_world_rank",
)
RANKING_SELECTS = (
    "country,weapon,gender,category,season,rank,points",
    "country,weapon,category,season,rank,points",
)
RESULT_SELECTS = (
    "tournament_id,country,nationality,weapon,gender,category,season,rank,placement,medal",
    "tournament_id,country,nationality,rank,placement,medal",
    "tournament_id,nationality,rank,placement,medal",
)
TOURNAMENT_SELECTS = (
    "id,season,weapon,gender,category,type,name,tier,competition_type,start_date,end_date,date",
    "id,season,weapon,gender,category,type,name",
    "id,season,weapon,category,type,name",
)
MEDAL_SELECTS = (
    "scope,country,tier,gold,silver,bronze,total",
)

WEAPON_MAP = {
    "e": "Epee",
    "epee": "Epee",
    "epée": "Epee",
    "f": "Foil",
    "foil": "Foil",
    "fleuret": "Foil",
    "s": "Sabre",
    "sabre": "Sabre",
    "saber": "Sabre",
}
CATEGORY_MAP = {
    "senior": "Senior",
    "junior": "Junior",
    "u20": "Junior",
    "cadet": "Cadet",
    "u17": "Cadet",
    "veteran": "Veteran",
}
TYPE_TIERS = {
    "OG": "Olympics",
    "OLYMPICS": "Olympics",
    "OLYMPICGAMES": "Olympics",
    "WCH": "Worlds",
    "CHM": "Worlds",
    "WORLDCHAMPIONSHIP": "Worlds",
    "WORLDCHAMPIONSHIPS": "Worlds",
    "WORLDS": "Worlds",
    "GP": "GP",
    "GRANDPRIX": "GP",
    "WC": "WC",
    "WORLDCUP": "WC",
    "CC": "Continental",
    "ZCH": "Continental",
    "CONTINENTALCHAMPIONSHIP": "Continental",
    "CONTINENTALCHAMPIONSHIPS": "Continental",
    "ZONALCHAMPIONSHIP": "Continental",
    "ZONALCHAMPIONSHIPS": "Continental",
}
TIER_TEXT_PATTERNS = (
    ("Olympics", ("olympic games", "olympics")),
    ("GP", ("grand prix",)),
    ("WC", ("world cup",)),
    (
        "Continental",
        (
            "continental championship",
            "continental championships",
            "zonal championship",
            "zonal championships",
            "european championship",
            "european championships",
            "asian championship",
            "asian championships",
            "pan american championship",
            "pan american championships",
            "african championship",
            "african championships",
        ),
    ),
    ("Worlds", ("world championship", "world championships", "worlds")),
)
MEDAL_BUCKETS = {
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
MEDAL_WEIGHTS = {"gold": 5.0, "silver": 3.0, "bronze": 2.0}
SKIPPED_SOURCE_KEYS = ("country_depth", "rankings", "results", "medals")


class CountryCodeIndex:
    def __init__(self, alias_to_code: dict[str, str]):
        self.alias_to_code = alias_to_code

    def lookup(self, value: Any) -> str | None:
        return self.alias_to_code.get(alias_key(value))


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    if create_client is None:
        raise RuntimeError("supabase package is required.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def without_diacritics(value: Any) -> str:
    text = clean_text(value) or ""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )


def normalized_key(value: Any) -> str:
    return without_diacritics(value).casefold()


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalized_key(value))


def alias_key(value: Any) -> str:
    return compact_key(value)


def parse_aliases(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if clean_text(item)]
    if isinstance(value, tuple):
        return [str(item) for item in value if clean_text(item)]
    if isinstance(value, str):
        text = clean_text(value)
        if not text:
            return []
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            return [part.strip() for part in re.split(r"[;,]", text) if part.strip()]
        return parse_aliases(loaded)
    return []


def build_country_code_index(country_codes: list[dict[str, Any]]) -> CountryCodeIndex:
    alias_to_code: dict[str, str] = {}
    for row in country_codes:
        code = clean_text(row.get("alpha3") or row.get("country_code") or row.get("code"))
        if not code:
            continue
        code = code.upper()
        if not re.fullmatch(r"[A-Z]{3}", code):
            continue

        aliases: list[Any] = [
            code,
            row.get("alpha2"),
            row.get("name"),
            row.get("display_name"),
            row.get("official_name"),
            row.get("olympic_code"),
            row.get("fie_code"),
            row.get("ioc_code"),
            row.get("noc"),
        ]
        aliases.extend(parse_aliases(row.get("aliases")))
        for alias in aliases:
            key = alias_key(alias)
            if key:
                alias_to_code.setdefault(key, code)
    return CountryCodeIndex(alias_to_code)


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    result: int | None
    try:
        result = int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        result = int(match.group(0)) if match else None
    return result


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def positive_int(value: Any) -> int | None:
    number = to_int(value)
    return number if number is not None and number > 0 else None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return WEAPON_MAP.get(normalized_key(text), text.title())


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalized_key(text).replace(".", "")
    if key in {"f", "female", "woman", "women", "womens", "women's"}:
        return "Women's"
    if key in {"m", "male", "man", "men", "mens", "men's"}:
        return "Men's"
    return text.title()


def category_base(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalized_key(text)
    for needle, label in CATEGORY_MAP.items():
        if needle in key:
            return label
    return text if "'" in text else text.title()


def gender_from_category(value: Any) -> str | None:
    key = normalized_key(value)
    if any(token in key for token in ("women", "female")):
        return "Women's"
    if any(token in key for token in ("men", "male")):
        return "Men's"
    return None


def normalize_category(category: Any, gender: Any = None) -> str | None:
    base = category_base(category)
    if not base:
        return None
    gender_label = normalize_gender(gender) or gender_from_category(category)
    if gender_label:
        return f"{gender_label} {base}"
    return base


def season_to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = clean_text(value)
    if not text:
        return None
    years = re.findall(r"\d{4}", text)
    if years:
        return int(years[-1])
    short = re.match(r"^(\d{4})\s*[-/]\s*(\d{2})$", text)
    if short:
        start = int(short.group(1))
        end_two = int(short.group(2))
        century = start // 100 * 100
        end = century + end_two
        return end + 100 if end < start else end
    return to_int(text)


def normalize_tier(tournament: dict[str, Any] | None = None, value: Any = None) -> str | None:
    values: list[Any] = [value]
    if tournament:
        values.extend(tournament.get(field) for field in ("tier", "type", "competition_type"))
    for raw in values:
        text = clean_text(raw)
        if not text:
            continue
        tier = TYPE_TIERS.get(compact_key(text).upper())
        if tier:
            return tier
        if text in {"Olympics", "Worlds", "GP", "WC", "Continental", "Ranking", "Depth"}:
            return text

    haystack = " ".join(
        clean_text((tournament or {}).get(field)) or ""
        for field in ("tier", "type", "competition_type", "name", "category")
    ).casefold()
    haystack = f"{haystack} {(clean_text(value) or '').casefold()}"
    for tier, patterns in TIER_TEXT_PATTERNS:
        if any(pattern in haystack for pattern in patterns):
            return tier
    return None


def medal_bucket(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return MEDAL_BUCKETS.get(compact_key(text))


def rank_quality(value: Any) -> float:
    rank = positive_int(value)
    if rank is None:
        return 0.0
    if rank <= 256:
        return max(0.01, (257.0 - rank) / 256.0)
    return max(0.001, 1.0 / rank)


def stable_id(country_code: str, weapon: str, category: str, tier: str, season: int | None) -> str:
    parts = [
        country_code.lower(),
        compact_key(weapon) or "all",
        compact_key(category) or "all",
        compact_key(tier) or "unknown",
        str(season) if season is not None else "all",
    ]
    return ":".join(parts)


def tournament_lookup(tournaments: list[dict[str, Any]] | dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def record_skip(skipped: dict[str, int], source: str, reason: str) -> None:
    skipped[source] += 1
    skipped[reason] += 1


def add_observation(
    observations: dict[tuple[str, str, str, str, int | None], dict[str, Any]],
    *,
    skipped: dict[str, int],
    source: str,
    country_code: str | None,
    weapon: str | None,
    category: str | None,
    tier: str | None,
    season: int | None,
    score: float,
    sample_count: int,
    medal: str | None = None,
) -> None:
    if not country_code:
        record_skip(skipped, source, "unknown_country")
        return
    if not weapon or not category or not tier:
        record_skip(skipped, source, "missing_group")
        return
    if score <= 0:
        record_skip(skipped, source, "zero_score")
        return

    key = (country_code, weapon, category, tier, season)
    entry = observations.setdefault(
        key,
        {
            "score": 0.0,
            "sample_count": 0,
            "source_counts": Counter(),
            "gold": 0,
            "silver": 0,
            "bronze": 0,
        },
    )
    entry["score"] += score
    entry["sample_count"] += max(0, sample_count)
    entry["source_counts"][source] += max(1, sample_count)
    if medal:
        entry[medal] += 1


def add_depth_observations(
    observations: dict[tuple[str, str, str, str, int | None], dict[str, Any]],
    rows: list[dict[str, Any]],
    country_index: CountryCodeIndex,
    skipped: dict[str, int],
) -> None:
    for row in rows:
        country_code = country_index.lookup(row.get("country"))
        total_ranked = positive_int(row.get("total_ranked")) or 0
        top16 = positive_int(row.get("fencers_in_top16")) or 0
        top32 = positive_int(row.get("fencers_in_top32")) or 0
        top64 = positive_int(row.get("fencers_in_top64")) or 0
        score = total_ranked + top64 * 0.5 + top32 + top16 * 2.0
        add_observation(
            observations,
            skipped=skipped,
            source="country_depth",
            country_code=country_code,
            weapon=normalize_weapon(row.get("weapon")),
            category=normalize_category(row.get("category")),
            tier="Depth",
            season=None,
            score=score,
            sample_count=total_ranked,
        )


def add_ranking_observations(
    observations: dict[tuple[str, str, str, str, int | None], dict[str, Any]],
    rows: list[dict[str, Any]],
    country_index: CountryCodeIndex,
    skipped: dict[str, int],
) -> None:
    for row in rows:
        country_code = country_index.lookup(row.get("country"))
        points = max(0.0, to_float(row.get("points")) or 0.0)
        score = rank_quality(row.get("rank")) + min(points, 1000.0) / 1000.0
        add_observation(
            observations,
            skipped=skipped,
            source="rankings",
            country_code=country_code,
            weapon=normalize_weapon(row.get("weapon")),
            category=normalize_category(row.get("category"), row.get("gender")),
            tier="Ranking",
            season=season_to_int(row.get("season")),
            score=score,
            sample_count=1,
        )


def add_result_observations(
    observations: dict[tuple[str, str, str, str, int | None], dict[str, Any]],
    rows: list[dict[str, Any]],
    tournaments: list[dict[str, Any]] | dict[str, dict[str, Any]],
    country_index: CountryCodeIndex,
    skipped: dict[str, int],
) -> None:
    tournaments_by_id = tournament_lookup(tournaments)
    for row in rows:
        country_code = country_index.lookup(row.get("country") or row.get("nationality"))
        tournament_id = clean_text(row.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id) if tournament_id else None
        medal = medal_bucket(row.get("medal"))
        score = rank_quality(row.get("rank") or row.get("placement"))
        if medal:
            score += MEDAL_WEIGHTS[medal]
        add_observation(
            observations,
            skipped=skipped,
            source="results",
            country_code=country_code,
            weapon=normalize_weapon(row.get("weapon") or (tournament or {}).get("weapon")),
            category=normalize_category(
                row.get("category") or (tournament or {}).get("category"),
                row.get("gender") or (tournament or {}).get("gender"),
            ),
            tier=normalize_tier(tournament) or "Results",
            season=season_to_int(row.get("season") or (tournament or {}).get("season")),
            score=score,
            sample_count=1,
            medal=medal,
        )


def add_medal_observations(
    observations: dict[tuple[str, str, str, str, int | None], dict[str, Any]],
    rows: list[dict[str, Any]],
    country_index: CountryCodeIndex,
    skipped: dict[str, int],
) -> None:
    for row in rows:
        if clean_text(row.get("scope")) not in {"country", "tier_country"}:
            continue
        country_code = country_index.lookup(row.get("country"))
        gold = positive_int(row.get("gold")) or 0
        silver = positive_int(row.get("silver")) or 0
        bronze = positive_int(row.get("bronze")) or 0
        total = positive_int(row.get("total")) or gold + silver + bronze
        score = gold * MEDAL_WEIGHTS["gold"] + silver * MEDAL_WEIGHTS["silver"] + bronze * MEDAL_WEIGHTS["bronze"]
        tier = normalize_tier(value=row.get("tier")) or "Medals"
        for medal, count in (("gold", gold), ("silver", silver), ("bronze", bronze)):
            for _ in range(count):
                add_observation(
                    observations,
                    skipped=skipped,
                    source="medals",
                    country_code=country_code,
                    weapon="All",
                    category="All",
                    tier=tier,
                    season=None,
                    score=score / total if total else 0.0,
                    sample_count=1,
                    medal=medal,
                )
        if total == 0:
            add_observation(
                observations,
                skipped=skipped,
                source="medals",
                country_code=country_code,
                weapon="All",
                category="All",
                tier=tier,
                season=None,
                score=0.0,
                sample_count=0,
            )


def confidence_for(sample_count: int, distinct_sources: int) -> float:
    sample_component = sample_count / (sample_count + 6.0) if sample_count > 0 else 0.0
    source_component = min(0.2, max(0, distinct_sources - 1) * 0.05)
    return round(min(1.0, sample_component + source_component), 4)


def confidence_label(confidence: float) -> str:
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.3:
        return "medium"
    return "low"


def build_rows_from_observations(
    observations: dict[tuple[str, str, str, str, int | None], dict[str, Any]],
    *,
    computed_at: str,
) -> list[dict[str, Any]]:
    total_score = sum(value["score"] for value in observations.values())
    if total_score <= 0:
        return []

    country_scores: dict[str, float] = defaultdict(float)
    segment_scores: dict[tuple[str, str, str, int | None], float] = defaultdict(float)
    for (country_code, weapon, category, tier, season), value in observations.items():
        country_scores[country_code] += value["score"]
        segment_scores[(weapon, category, tier, season)] += value["score"]

    rows: list[dict[str, Any]] = []
    segment_rows: dict[tuple[str, str, str, int | None], list[dict[str, Any]]] = defaultdict(list)
    for (country_code, weapon, category, tier, season), value in sorted(observations.items()):
        segment_key = (weapon, category, tier, season)
        country_share = value["score"] / segment_scores[segment_key] if segment_scores[segment_key] else 0.0
        baseline_share = country_scores[country_code] / total_score if total_score else 0.0
        specialization_index = country_share / baseline_share if baseline_share else 0.0
        sample_count = int(value["sample_count"])
        source_counts = dict(sorted(value["source_counts"].items()))
        confidence = confidence_for(sample_count, len(source_counts))
        row = {
            "id": stable_id(country_code, weapon, category, tier, season),
            "country_code": country_code,
            "weapon": weapon,
            "category": category,
            "tier": tier,
            "season": season,
            "raw_score": round(value["score"], 6),
            "sample_count": sample_count,
            "source_counts": source_counts,
            "country_share_in_segment": round(country_share, 6),
            "country_baseline_share": round(baseline_share, 6),
            "specialization_index": round(specialization_index, 6),
            "z_score": 0.0,
            "segment_rank": None,
            "confidence": confidence,
            "confidence_label": confidence_label(confidence),
            "is_sparse": sample_count < 3 or confidence < 0.3,
            "gold": int(value["gold"]),
            "silver": int(value["silver"]),
            "bronze": int(value["bronze"]),
            "medal_count": int(value["gold"] + value["silver"] + value["bronze"]),
            "computed_at": computed_at,
        }
        rows.append(row)
        segment_rows[segment_key].append(row)

    for segment in segment_rows.values():
        indexes = [row["specialization_index"] for row in segment]
        mean = sum(indexes) / len(indexes)
        variance = sum((value - mean) ** 2 for value in indexes) / len(indexes)
        stddev = math.sqrt(variance)
        for row in segment:
            row["z_score"] = round((row["specialization_index"] - mean) / stddev, 6) if stddev else 0.0

        sorted_segment = sorted(
            segment,
            key=lambda row: (-row["specialization_index"], -row["sample_count"], row["country_code"]),
        )
        previous_index: float | None = None
        previous_rank = 0
        for ordinal, row in enumerate(sorted_segment, start=1):
            if previous_index is not None and row["specialization_index"] == previous_index:
                row["segment_rank"] = previous_rank
            else:
                row["segment_rank"] = ordinal
                previous_rank = ordinal
                previous_index = row["specialization_index"]

    return sorted(rows, key=lambda row: (row["country_code"], row["weapon"], row["category"], row["tier"], row["season"] or 0))


def build_country_specialization_rows(
    *,
    country_codes: list[dict[str, Any]],
    country_depth_rows: list[dict[str, Any]],
    ranking_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
    tournament_rows: list[dict[str, Any]] | dict[str, dict[str, Any]],
    medal_rows: list[dict[str, Any]],
    computed_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    timestamp = computed_at or datetime.now(UTC).isoformat()
    country_index = build_country_code_index(country_codes)
    skipped = {
        "country_depth": 0,
        "rankings": 0,
        "results": 0,
        "medals": 0,
        "unknown_country": 0,
        "missing_group": 0,
        "zero_score": 0,
    }
    observations: dict[tuple[str, str, str, str, int | None], dict[str, Any]] = {}

    add_depth_observations(observations, country_depth_rows, country_index, skipped)
    add_ranking_observations(observations, ranking_rows, country_index, skipped)
    add_result_observations(observations, result_rows, tournament_rows, country_index, skipped)
    add_medal_observations(observations, medal_rows, country_index, skipped)

    return build_rows_from_observations(observations, computed_at=timestamp), skipped


def skipped_source_total(skipped: dict[str, int]) -> int:
    return sum(skipped.get(source, 0) for source in SKIPPED_SOURCE_KEYS)


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


def fetch_optional_with_fallbacks(
    client,
    table: str,
    select_options: tuple[str, ...],
    *,
    page_size: int,
    source_errors: list[str],
) -> list[dict[str, Any]]:
    last_exc: Exception | None = None
    for columns in select_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_exc = exc
            print(f"  Select fallback for {table}: {exc}")
    if last_exc:
        source_errors.append(f"{table}: {last_exc}")
    return []


def batch_upsert(client, rows: list[dict[str, Any]], *, batch_size: int) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table(SPECIALIZATION_TABLE).upsert(batch, on_conflict="id").execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  {SPECIALIZATION_TABLE} upsert batch {index // batch_size} failed: {exc}")
    return written, failed


def compute_country_specialization(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    computed_at: str | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    previous_summary = get_state(SOURCE, "last_summary") if update_state else None
    source_errors: list[str] = []

    try:
        client = client or get_supabase_client()
        timestamp = computed_at or datetime.now(UTC).isoformat()
        country_codes = fetch_optional_with_fallbacks(
            client,
            "fs_country_codes",
            COUNTRY_CODE_SELECTS,
            page_size=page_size,
            source_errors=source_errors,
        )
        country_depth_rows = fetch_optional_with_fallbacks(
            client,
            "fs_country_depth",
            COUNTRY_DEPTH_SELECTS,
            page_size=page_size,
            source_errors=source_errors,
        )
        ranking_rows = fetch_optional_with_fallbacks(
            client,
            "fs_rankings_history",
            RANKING_SELECTS,
            page_size=page_size,
            source_errors=source_errors,
        )
        result_rows = fetch_optional_with_fallbacks(
            client,
            "fs_results",
            RESULT_SELECTS,
            page_size=page_size,
            source_errors=source_errors,
        )
        tournament_rows = fetch_optional_with_fallbacks(
            client,
            "fs_tournaments",
            TOURNAMENT_SELECTS,
            page_size=page_size,
            source_errors=source_errors,
        )
        medal_rows = fetch_optional_with_fallbacks(
            client,
            "fs_medal_tables",
            MEDAL_SELECTS,
            page_size=page_size,
            source_errors=source_errors,
        )

        rows, skipped = build_country_specialization_rows(
            country_codes=country_codes,
            country_depth_rows=country_depth_rows,
            ranking_rows=ranking_rows,
            result_rows=result_rows,
            tournament_rows=tournament_rows,
            medal_rows=medal_rows,
            computed_at=timestamp,
        )
        written, failed = batch_upsert(client, rows, batch_size=batch_size) if rows else (0, 0)

        summary: dict[str, Any] = {
            "country_code_rows": len(country_codes),
            "country_depth_rows": len(country_depth_rows),
            "ranking_rows": len(ranking_rows),
            "result_rows": len(result_rows),
            "tournament_rows": len(tournament_rows),
            "medal_rows": len(medal_rows),
            "specialization_rows": len(rows),
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "skipped_total": skipped_source_total(skipped),
            "source_errors": source_errors,
            "rows": rows,
        }
        if isinstance(previous_summary, dict) and previous_summary.get("updated_at"):
            summary["previous_updated_at"] = previous_summary["updated_at"]

        state_summary = {key: value for key, value in summary.items() if key != "rows"}
        state_summary["updated_at"] = timestamp
        if update_state:
            set_state(SOURCE, "last_summary", state_summary)
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=summary["skipped_total"],
                metadata=state_summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Country specialization computation starting - {datetime.now(UTC).isoformat()}")
    summary = compute_country_specialization()
    print(
        "Country specialization computation complete - "
        f"{summary['specialization_rows']} rows, "
        f"{summary['written']} written, {summary['failed']} failed, "
        f"{summary['skipped_total']} skipped"
    )


if __name__ == "__main__":
    main()

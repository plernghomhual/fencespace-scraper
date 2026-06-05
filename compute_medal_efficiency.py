import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from season_utils import normalize_season


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_medal_efficiency"
OUTPUT_TABLE = "fs_medal_efficiency"
MIN_MEDAL_SAMPLE = 3
MIN_COMPETITION_SAMPLE = 3

MEDAL_TABLE_COLUMNS = "id,scope,country,fencer_id,tier,gold,silver,bronze,total"
COUNTRY_DEPTH_COLUMNS = "country,weapon,category,total_ranked,avg_world_rank,fencers_in_top16,fencers_in_top32,fencers_in_top64"
COUNTRY_CODE_COLUMNS = "country,country_code,iso3,ioc,noc,name,country_name"
POPULATION_COLUMNS = "country,country_code,iso3,iso_alpha3,ioc,noc,season,population"
FENCER_COUNT_COLUMNS = (
    "country,country_code,iso3,iso_alpha3,ioc,noc,season,active_fencers,active_fencer_count,"
    "fencer_count,total_active_fencers"
)
COMPETITION_COUNT_COLUMNS = (
    "country,country_code,iso3,iso_alpha3,ioc,noc,season,competition_count,competitions_count,"
    "tournament_count,tournament_id,competition_id,competition_tier,tier,competition_type,type"
)

MEDAL_POINTS = {"gold": 3.0, "silver": 2.0, "bronze": 1.0}
TIER_WEIGHTS = {
    "Olympics": 5.0,
    "Worlds": 4.0,
    "Continental": 2.5,
    "GP": 2.0,
    "WC": 1.5,
}

TIER_ALIASES = {
    "og": "Olympics",
    "olympics": "Olympics",
    "olympicgames": "Olympics",
    "wch": "Worlds",
    "chm": "Worlds",
    "worlds": "Worlds",
    "worldchampionship": "Worlds",
    "worldchampionships": "Worlds",
    "grandprix": "GP",
    "gp": "GP",
    "worldcup": "WC",
    "wc": "WC",
    "cc": "Continental",
    "zch": "Continental",
    "continentalchampionship": "Continental",
    "continentalchampionships": "Continental",
    "zonalchampionship": "Continental",
    "zonalchampionships": "Continental",
    "europeanchampionship": "Continental",
    "europeanchampionships": "Continental",
    "asianchampionship": "Continental",
    "asianchampionships": "Continental",
    "panamericanchampionship": "Continental",
    "panamericanchampionships": "Continental",
    "africanchampionship": "Continental",
    "africanchampionships": "Continental",
}

TYPE_ALIASES = {
    "individual": "Individual",
    "ind": "Individual",
    "team": "Team",
    "teams": "Team",
    "mixedteam": "Mixed Team",
    "mixed": "Mixed Team",
}


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


def normalize_country_code(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    code = re.sub(r"[^A-Za-z0-9]+", "", text).upper()
    return code if len(code) == 3 else None


def normalize_season_value(value: Any) -> str:
    if value is None or value == "":
        return "all"
    try:
        return normalize_season(value)
    except (TypeError, ValueError):
        return clean_text(value) or "all"


def positive_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def positive_int(value: Any) -> int | None:
    number = positive_float(value)
    if number is None:
        return None
    return int(number)


def medal_count(row: dict[str, Any], field: str) -> int:
    value = positive_int(row.get(field))
    return value or 0


def normalize_tier(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = compact_key(text)
    if key in TIER_ALIASES:
        return TIER_ALIASES[key]
    for pattern, tier in (
        ("olympic", "Olympics"),
        ("worldchampionship", "Worlds"),
        ("grandprix", "GP"),
        ("worldcup", "WC"),
        ("continental", "Continental"),
        ("zonal", "Continental"),
    ):
        if pattern in key:
            return tier
    return None


def row_tier(row: dict[str, Any]) -> str | None:
    for field in ("competition_tier", "tier", "event_tier", "type"):
        tier = normalize_tier(row.get(field))
        if tier:
            return tier
    return None


def normalize_competition_type(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = compact_key(text)
    return TYPE_ALIASES.get(key, text)


def row_competition_type(row: dict[str, Any]) -> str | None:
    for field in ("competition_type", "event_type"):
        comp_type = normalize_competition_type(row.get(field))
        if comp_type:
            return comp_type
    return None


def country_alias_maps(
    country_code_rows: list[dict[str, Any]] | None,
) -> tuple[dict[str, str], dict[str, str]]:
    aliases: dict[str, str] = {}
    names: dict[str, str] = {}

    for row in country_code_rows or []:
        code = (
            normalize_country_code(row.get("country_code"))
            or normalize_country_code(row.get("iso3"))
            or normalize_country_code(row.get("iso_alpha3"))
            or normalize_country_code(row.get("ioc"))
            or normalize_country_code(row.get("noc"))
            or normalize_country_code(row.get("code"))
        )
        if not code:
            continue

        display = (
            clean_text(row.get("name"))
            or clean_text(row.get("country_name"))
            or clean_text(row.get("country"))
            or code
        )
        names.setdefault(code, display)

        for field in (
            "country",
            "country_name",
            "name",
            "country_code",
            "iso3",
            "iso_alpha3",
            "ioc",
            "noc",
            "code",
        ):
            key = compact_key(row.get(field))
            if key:
                aliases[key] = code

    return aliases, names


def resolve_country(
    row: dict[str, Any],
    aliases: dict[str, str],
    names: dict[str, str],
) -> tuple[str | None, str | None]:
    code = (
        normalize_country_code(row.get("country_code"))
        or normalize_country_code(row.get("iso3"))
        or normalize_country_code(row.get("iso_alpha3"))
        or normalize_country_code(row.get("ioc"))
        or normalize_country_code(row.get("noc"))
    )

    country = (
        clean_text(row.get("country"))
        or clean_text(row.get("country_name"))
        or clean_text(row.get("name"))
        or clean_text(row.get("nationality"))
    )

    if not code and country:
        code = aliases.get(compact_key(country)) or normalize_country_code(country)
    if not code:
        return None, country
    return code, names.get(code) or country or code


def empty_counts() -> dict[str, int]:
    return {"gold": 0, "silver": 0, "bronze": 0}


def add_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for medal in ("gold", "silver", "bronze"):
        target[medal] += source[medal]


def row_counts(row: dict[str, Any]) -> dict[str, int]:
    return {
        "gold": medal_count(row, "gold"),
        "silver": medal_count(row, "silver"),
        "bronze": medal_count(row, "bronze"),
    }


def total_medals(counts: dict[str, int]) -> int:
    return counts["gold"] + counts["silver"] + counts["bronze"]


def medal_points(counts: dict[str, int]) -> float:
    return sum(counts[medal] * MEDAL_POINTS[medal] for medal in MEDAL_POINTS)


def weighted_medal_score(counts: dict[str, int], tier: str | None) -> float:
    return medal_points(counts) * TIER_WEIGHTS.get(tier or "", 1.0)


def sample_confidence(total: int, competition_count: int | None) -> str:
    if total < MIN_MEDAL_SAMPLE:
        return "low"
    if competition_count is not None and competition_count < MIN_COMPETITION_SAMPLE:
        return "low"
    if total >= 10 and (competition_count is None or competition_count >= 10):
        return "high"
    return "medium"


def first_value(row: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        if row.get(field) not in (None, ""):
            return row.get(field)
    return None


def build_denominator_index(
    rows: list[dict[str, Any]] | None,
    value_fields: tuple[str, ...],
    aliases: dict[str, str],
    names: dict[str, str],
) -> dict[tuple[str | None, str], dict[str, Any]]:
    index: dict[tuple[str | None, str], dict[str, Any]] = defaultdict(
        lambda: {"value": None, "sample_count": 0}
    )

    for row in rows or []:
        code, _name = resolve_country(row, aliases, names)
        if not code:
            continue
        value = positive_int(first_value(row, value_fields))
        if value is None:
            continue
        season = normalize_season_value(row.get("season")) if row.get("season") not in (None, "") else None
        key = (season, code)
        if index[key]["value"] is None:
            index[key]["value"] = value
        index[key]["sample_count"] += 1

    return dict(index)


def build_depth_index(
    rows: list[dict[str, Any]] | None,
    aliases: dict[str, str],
    names: dict[str, str],
) -> dict[tuple[str | None, str], dict[str, int]]:
    index: dict[tuple[str | None, str], dict[str, int]] = defaultdict(
        lambda: {"ranked_fencer_sample_count": 0, "country_depth_rows": 0}
    )

    for row in rows or []:
        code, _name = resolve_country(row, aliases, names)
        if not code:
            continue
        total_ranked = positive_int(row.get("total_ranked"))
        if total_ranked is None:
            continue
        season = normalize_season_value(row.get("season")) if row.get("season") not in (None, "") else None
        key = (season, code)
        index[key]["ranked_fencer_sample_count"] += total_ranked
        index[key]["country_depth_rows"] += 1

    return dict(index)


def build_competition_index(
    rows: list[dict[str, Any]] | None,
    aliases: dict[str, str],
    names: dict[str, str],
) -> dict[tuple[str | None, str], dict[str, Any]]:
    index: dict[tuple[str | None, str], dict[str, Any]] = defaultdict(
        lambda: {"competition_count": 0, "sample_count": 0, "tiers": set(), "types": set()}
    )

    for row in rows or []:
        code, _name = resolve_country(row, aliases, names)
        if not code:
            continue

        explicit_count = first_value(
            row,
            ("competition_count", "competitions_count", "tournament_count"),
        )
        count: int | None
        if explicit_count is None and (row.get("tournament_id") or row.get("competition_id")):
            count = 1
        else:
            count = positive_int(explicit_count)
        if count is None:
            continue

        season = normalize_season_value(row.get("season")) if row.get("season") not in (None, "") else None
        key = (season, code)
        index[key]["competition_count"] += count
        index[key]["sample_count"] += 1

        tier = row_tier(row)
        if tier:
            index[key]["tiers"].add(tier)
        comp_type = row_competition_type(row)
        if comp_type:
            index[key]["types"].add(comp_type)

    return dict(index)


def exact_or_aggregate(
    index: dict[tuple[str | None, str], dict[str, Any]],
    season: str,
    code: str,
    default: dict[str, Any],
) -> dict[str, Any]:
    return index.get((season, code)) or index.get((None, code)) or default


def build_medal_efficiency_rows(
    medal_rows: list[dict[str, Any]],
    *,
    country_depth_rows: list[dict[str, Any]] | None = None,
    country_code_rows: list[dict[str, Any]] | None = None,
    population_rows: list[dict[str, Any]] | None = None,
    fencer_count_rows: list[dict[str, Any]] | None = None,
    competition_rows: list[dict[str, Any]] | None = None,
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    aliases, names = country_alias_maps(country_code_rows)
    timestamp = updated_at or datetime.now(timezone.utc).isoformat()

    country_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(empty_counts)
    fallback_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(empty_counts)
    weighted_scores: dict[tuple[str, str], float] = defaultdict(float)
    country_names: dict[str, str] = {}
    skipped = 0

    for row in medal_rows:
        code, display_name = resolve_country(row, aliases, names)
        if not code:
            skipped += 1
            continue
        country_names.setdefault(code, display_name or code)
        season = normalize_season_value(row.get("season"))
        key = (season, code)
        counts = row_counts(row)
        if total_medals(counts) == 0:
            skipped += 1
            continue

        tier = row_tier(row)
        scope = compact_key(row.get("scope"))
        if scope == "country" and not tier:
            add_counts(country_counts[key], counts)
        else:
            add_counts(fallback_counts[key], counts)
            weighted_scores[key] += weighted_medal_score(counts, tier)

    population_index = build_denominator_index(
        population_rows,
        ("population",),
        aliases,
        names,
    )
    active_fencer_index = build_denominator_index(
        fencer_count_rows,
        ("active_fencers", "active_fencer_count", "fencer_count", "total_active_fencers"),
        aliases,
        names,
    )
    depth_index = build_depth_index(country_depth_rows, aliases, names)
    competition_index = build_competition_index(competition_rows, aliases, names)

    keys = sorted(set(country_counts) | set(fallback_counts))
    rows: list[dict[str, Any]] = []
    for season, code in keys:
        season_counts: dict[str, int] | None = country_counts.get((season, code))
        if season_counts is None or total_medals(season_counts) == 0:
            season_counts = fallback_counts[(season, code)]

        total = total_medals(season_counts)
        score = weighted_scores.get((season, code))
        if score is None or score == 0:
            score = weighted_medal_score(season_counts, None)

        population_sample = exact_or_aggregate(
            population_index,
            season,
            code,
            {"value": None, "sample_count": 0},
        )
        fencer_sample = exact_or_aggregate(
            active_fencer_index,
            season,
            code,
            {"value": None, "sample_count": 0},
        )
        competition_sample = exact_or_aggregate(
            competition_index,
            season,
            code,
            {"competition_count": 0, "sample_count": 0, "tiers": set(), "types": set()},
        )
        depth_sample = exact_or_aggregate(
            depth_index,
            season,
            code,
            {"ranked_fencer_sample_count": 0, "country_depth_rows": 0},
        )

        population = population_sample["value"]
        active_fencers = fencer_sample["value"]
        competition_count = competition_sample["competition_count"] or None

        missing_denominators = []
        if active_fencers is None:
            missing_denominators.append("active_fencers")
        if competition_count is None:
            missing_denominators.append("competition_count")
        if population is None:
            missing_denominators.append("population")

        confidence = sample_confidence(total, competition_count)
        is_small_sample = confidence == "low"

        rows.append(
            {
                "id": f"{season}:{code}",
                "country_code": code,
                "country": country_names.get(code) or names.get(code) or code,
                "season": season,
                "gold": season_counts["gold"],
                "silver": season_counts["silver"],
                "bronze": season_counts["bronze"],
                "total_medals": total,
                "population": population,
                "active_fencers": active_fencers,
                "competition_count": competition_count,
                "ranked_fencer_sample_count": depth_sample["ranked_fencer_sample_count"],
                "country_depth_rows": depth_sample["country_depth_rows"],
                "medals_per_capita": (total / population) if population else None,
                "medals_per_million": (total / population * 1_000_000) if population else None,
                "medals_per_active_fencer": (total / active_fencers) if active_fencers else None,
                "medals_per_competition": (total / competition_count) if competition_count else None,
                "tier_weighted_medal_score": score,
                "tier_weighted_efficiency": (score / competition_count) if competition_count else None,
                "competition_tiers": sorted(competition_sample["tiers"]),
                "competition_types": sorted(competition_sample["types"]),
                "population_sample_count": population_sample["sample_count"],
                "active_fencer_sample_count": fencer_sample["sample_count"],
                "competition_sample_count": competition_sample["sample_count"],
                "medal_sample_count": total,
                "minimum_medal_sample": MIN_MEDAL_SAMPLE,
                "minimum_competition_sample": MIN_COMPETITION_SAMPLE,
                "is_small_sample": is_small_sample,
                "is_rankable": not is_small_sample,
                "sample_confidence": confidence,
                "missing_denominators": sorted(missing_denominators),
                "updated_at": timestamp,
            }
        )

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


def fetch_optional(
    client,
    table: str,
    columns: str,
    *,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    try:
        return fetch_all(client, table, columns, page_size=page_size)
    except Exception as exc:
        print(f"Skipping optional medal efficiency source {table}: {exc}")
        return []


def fetch_optional_many(
    client,
    tables: tuple[str, ...],
    columns: str,
    *,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in tables:
        rows.extend(fetch_optional(client, table, columns, page_size=page_size))
    return rows


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


def is_missing_backing_table_error(exc: Exception) -> bool:
    message = str(exc).casefold()
    return any(
        marker in message
        for marker in (
            "does not exist",
            "not found",
            "schema cache",
            "could not find the table",
        )
    )


def compute_medal_efficiency(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    updated_at: str | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        medal_rows = fetch_all(client, "fs_medal_tables", MEDAL_TABLE_COLUMNS, page_size=page_size)
        country_depth_rows = fetch_optional(
            client,
            "fs_country_depth",
            COUNTRY_DEPTH_COLUMNS,
            page_size=page_size,
        )
        country_code_rows = fetch_optional(
            client,
            "fs_country_codes",
            COUNTRY_CODE_COLUMNS,
            page_size=page_size,
        )
        population_rows = fetch_optional_many(
            client,
            ("fs_country_population", "fs_country_populations"),
            POPULATION_COLUMNS,
            page_size=page_size,
        )
        fencer_count_rows = fetch_optional_many(
            client,
            ("fs_country_fencer_counts", "fs_fencer_counts"),
            FENCER_COUNT_COLUMNS,
            page_size=page_size,
        )
        competition_rows = fetch_optional_many(
            client,
            ("fs_country_competition_counts", "fs_country_competitions"),
            COMPETITION_COUNT_COLUMNS,
            page_size=page_size,
        )

        rows, skipped = build_medal_efficiency_rows(
            medal_rows,
            country_depth_rows=country_depth_rows,
            country_code_rows=country_code_rows,
            population_rows=population_rows,
            fencer_count_rows=fencer_count_rows,
            competition_rows=competition_rows,
            updated_at=updated_at,
        )

        try:
            written = (
                batch_upsert(
                    client,
                    OUTPUT_TABLE,
                    rows,
                    on_conflict="id",
                    batch_size=batch_size,
                )
                if rows
                else 0
            )
        except Exception as exc:
            if not is_missing_backing_table_error(exc):
                raise
            print(
                f"Computed {len(rows)} medal efficiency rows but did not write them: "
                f"{OUTPUT_TABLE} backing table is unavailable."
            )
            written = 0

        summary = {
            "medal_rows_read": len(medal_rows),
            "country_depth_rows_read": len(country_depth_rows),
            "country_code_rows_read": len(country_code_rows),
            "population_rows_read": len(population_rows),
            "fencer_count_rows_read": len(fencer_count_rows),
            "competition_rows_read": len(competition_rows),
            "efficiency_rows": len(rows),
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
    print(f"Medal efficiency computation starting - {datetime.now(timezone.utc).isoformat()}")
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous medal efficiency state: {previous_state}")
    summary = compute_medal_efficiency()
    print(
        "Medal efficiency computation complete - "
        f"{summary['efficiency_rows']} rows built, "
        f"{summary['written']} rows written, "
        f"{summary['skipped']} rows skipped"
    )


if __name__ == "__main__":
    main()

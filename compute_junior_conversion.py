from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from season_utils import season_from_string

try:
    from supabase import create_client
except Exception:  # pragma: no cover - import errors surface when a client is required.
    create_client = None


SOURCE = "compute_junior_conversion"
PAGE_SIZE = 1000
BATCH_SIZE = 200
DEFAULT_WINDOWS = (1, 2, 4)
SPARSE_COHORT_THRESHOLD = 3
RATE_TABLE = "fs_junior_conversion_rates"
RATE_CONFLICT_COLUMNS = "country,weapon,gender,category,cohort_season,window_years"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

RANKING_SELECTS = [
    "fencer_id,fie_fencer_id,season,country,weapon,gender,category,rank,points,name,scraped_at",
    "fie_fencer_id,season,country,weapon,gender,category,rank,points,name,scraped_at",
]
RESULT_SELECTS = [
    "fencer_id,fie_fencer_id,tournament_id,country,nationality,weapon,gender,category,season,rank,placement,medal,name,date",
    "fencer_id,fie_fencer_id,tournament_id,country,nationality,rank,placement,medal,name",
    "fencer_id,tournament_id,rank,placement,medal",
]
TOURNAMENT_SELECTS = [
    "id,season,weapon,gender,category,start_date,end_date,date,country,name",
    "id,season,weapon,gender,category,start_date,end_date,date,name",
    "id,season,weapon,gender,category",
]
FENCER_SELECTS = [
    "id,fie_id,country,date_of_birth",
    "id,fie_id,country",
    "id,fie_id",
]
IDENTITY_SELECTS = [
    "id,canonical_id,fs_fencer_row_ids,fencer_ids,fie_ids,country",
    "id,fs_fencer_row_ids,fie_ids,country",
    "canonical_id,fs_fencer_row_ids,fencer_ids,fie_ids,country",
    "id,fs_fencer_row_ids",
]
SKIP_KEYS = (
    "without_identity",
    "without_country",
    "without_weapon",
    "without_category",
    "without_season",
    "non_junior_or_senior",
)

COUNTRY_ALIASES = {
    "_AIN": "Russia",
    "AIN_": "Russia",
    "AIN": "Russia",
    "INDIVIDUAL NEUTRAL ATHLETES": "Russia",
    "FIE": "FIE",
    "US": "United States",
    "USA": "United States",
    "UNITED STATES": "United States",
    "UNITED STATES OF AMERICA": "United States",
    "CAN": "Canada",
    "GB": "Great Britain",
    "GBR": "Great Britain",
    "GREAT BRITAIN": "Great Britain",
    "KOR": "South Korea",
    "KOREA": "South Korea",
    "HONG KONG, CHINA": "Hong Kong",
    "HONG KONG CHINA": "Hong Kong",
    "TURKIYE": "Turkey",
}


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    if create_client is None:
        raise RuntimeError("supabase package is required.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    ).casefold()


def coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def season_to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = clean_text(value)
    if not text:
        return None
    try:
        return season_from_string(text)
    except (TypeError, ValueError):
        pass
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
    return coerce_int(text)


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text).upper().replace(".", "")
    key = re.sub(r"\s+", " ", key)
    return COUNTRY_ALIASES.get(key, text.title())


def country_key(value: Any) -> str:
    return normalize_key(normalize_country(value))


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text)
    if key in {"e", "epee"}:
        return "Epee"
    if key in {"f", "foil", "fleuret"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return text.title()


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = normalize_key(text).replace(".", "").replace("'", "")
    if key in {"f", "female", "women", "woman", "womens"}:
        return "Women's"
    if key in {"m", "male", "men", "man", "mens"}:
        return "Men's"
    return None


def infer_gender(explicit: Any, category: Any) -> str | None:
    gender = normalize_gender(explicit)
    if gender:
        return gender
    key = normalize_key(category).replace("'", "")
    if "women" in key or "female" in key:
        return "Women's"
    if "men" in key or "male" in key:
        return "Men's"
    return None


def normalize_category(category: Any, gender: Any = None) -> str | None:
    category_text = clean_text(category)
    if not category_text:
        return None
    category_label = category_text if "'" in category_text else category_text.title()
    gender_label = normalize_gender(gender) or clean_text(gender)
    if not gender_label or gender_label == "Unknown":
        return category_label
    if category_label.casefold().startswith(gender_label.casefold()):
        return category_label
    return f"{gender_label} {category_label}"


def category_level(category: Any) -> str | None:
    key = normalize_key(category)
    if not key:
        return None
    if "junior" in key or re.search(r"\bu20\b", key):
        return "Junior"
    if "senior" in key:
        return "Senior"
    return None


def rank_value(row: dict[str, Any]) -> int | None:
    return coerce_int(row.get("rank") if row.get("rank") is not None else row.get("placement"))


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if clean_text(value) is not None:
            return value
    return None


def medal_from_result(rank: int | None, medal: Any) -> bool:
    if rank is not None and 1 <= rank <= 3:
        return True
    key = normalize_key(medal)
    return key in {"gold", "silver", "bronze", "g", "s", "b"}


def parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list | tuple | set):
        return []
    return sorted({str(item) for item in value if clean_text(item)})


def build_identity_index(
    fencers: list[dict[str, Any]] | None,
    identities: list[dict[str, Any]] | None,
) -> dict[str, dict[str, str]]:
    by_row_id: dict[str, str] = {}
    by_fie_id: dict[str, str] = {}
    country_by_identity: dict[str, str] = {}

    for row in identities or []:
        identity_id = clean_text(row.get("id"))
        canonical_id = identity_id or clean_text(row.get("canonical_id"))
        members = parse_list(row.get("fs_fencer_row_ids") or row.get("fencer_ids"))
        if not canonical_id and members:
            canonical_id = members[0]
        if not canonical_id:
            continue

        by_row_id[canonical_id] = canonical_id
        for member in members:
            by_row_id[member] = canonical_id
        for fie_id in parse_list(row.get("fie_ids")):
            by_fie_id[fie_id] = canonical_id
        country = normalize_country(row.get("country"))
        if country:
            country_by_identity.setdefault(canonical_id, country)

    for row in fencers or []:
        row_id = clean_text(row.get("id"))
        if not row_id:
            continue
        canonical_id = by_row_id.get(row_id, row_id)
        by_row_id.setdefault(row_id, canonical_id)
        by_row_id.setdefault(canonical_id, canonical_id)
        fie_id_fencer: str | None = clean_text(row.get("fie_id"))
        if fie_id_fencer:
            by_fie_id.setdefault(fie_id_fencer, canonical_id)
        country = normalize_country(row.get("country"))
        if country:
            country_by_identity.setdefault(canonical_id, country)

    return {
        "by_row_id": by_row_id,
        "by_fie_id": by_fie_id,
        "country_by_identity": country_by_identity,
    }


def canonical_fencer_id(row: dict[str, Any], identity_index: dict[str, dict[str, str]]) -> str | None:
    row_id = clean_text(row.get("fencer_id"))
    fie_id = clean_text(row.get("fie_fencer_id") or row.get("fie_id"))
    if row_id and row_id in identity_index["by_row_id"]:
        return identity_index["by_row_id"][row_id]
    if fie_id and fie_id in identity_index["by_fie_id"]:
        return identity_index["by_fie_id"][fie_id]
    return row_id


def tournament_lookup(tournaments: dict[Any, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    values: list[dict[str, Any]]
    if isinstance(tournaments, dict):
        values = list(tournaments.values())
    else:
        values = tournaments or []
    return {str(row["id"]): row for row in values if row.get("id") is not None}


def observation_from_row(
    row: dict[str, Any],
    *,
    source: str,
    tournaments_by_id: dict[str, dict[str, Any]],
    identity_index: dict[str, dict[str, str]],
) -> tuple[dict[str, Any] | None, str | None]:
    tournament_id = clean_text(row.get("tournament_id") or row.get("competition_id"))
    tournament = tournaments_by_id.get(tournament_id or "")

    fencer_id = canonical_fencer_id(row, identity_index)
    if not fencer_id:
        return None, "without_identity"

    country = normalize_country(
        first_non_empty(
            row.get("country"),
            row.get("nationality"),
            (tournament or {}).get("country"),
            identity_index["country_by_identity"].get(fencer_id),
        )
    )
    if not country:
        return None, "without_country"

    weapon = normalize_weapon(first_non_empty(row.get("weapon"), (tournament or {}).get("weapon")))
    if not weapon:
        return None, "without_weapon"

    raw_category = first_non_empty(row.get("category"), (tournament or {}).get("category"))
    if not clean_text(raw_category):
        return None, "without_category"

    raw_gender = first_non_empty(row.get("gender"), (tournament or {}).get("gender"))
    gender = infer_gender(raw_gender, raw_category) or "Unknown"
    category = normalize_category(raw_category, gender)
    level = category_level(category or raw_category)
    if not level:
        return None, "non_junior_or_senior"

    season = season_to_int(first_non_empty(row.get("season"), (tournament or {}).get("season")))
    if season is None:
        return None, "without_season"

    rank = rank_value(row)
    return (
        {
            "fencer_id": fencer_id,
            "source": source,
            "country": country,
            "country_key": country_key(country),
            "weapon": weapon,
            "gender": gender,
            "category": category,
            "category_level": level,
            "season": season,
            "rank": rank,
            "is_medal": medal_from_result(rank, row.get("medal")) if source == "result" else False,
        },
        None,
    )


def valid_windows(windows: tuple[int, ...] | list[int]) -> tuple[int, ...]:
    normalized = tuple(sorted({int(window) for window in windows}))
    if any(window <= 0 for window in normalized):
        raise ValueError("conversion windows must be positive season counts")
    return normalized


def rate(count: int, sample_count: int) -> float | None:
    if sample_count <= 0:
        return None
    return round(count / sample_count * 100, 2)


def build_junior_conversion_report(
    *,
    results: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    tournaments: dict[Any, dict[str, Any]] | list[dict[str, Any]],
    fencers: list[dict[str, Any]] | None = None,
    identities: list[dict[str, Any]] | None = None,
    windows: tuple[int, ...] | list[int] = DEFAULT_WINDOWS,
    computed_at: str | None = None,
) -> dict[str, Any]:
    computed_at = computed_at or datetime.now(timezone.utc).isoformat()
    windows = valid_windows(windows)
    identity_index = build_identity_index(fencers, identities)
    tournaments_by_id = tournament_lookup(tournaments)
    skipped = Counter({key: 0 for key in SKIP_KEYS})

    junior_members: dict[tuple[str, str, str, str, int], dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    senior_by_fencer: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for raw_row in rankings:
        observation, skip_key = observation_from_row(
            raw_row,
            source="ranking",
            tournaments_by_id=tournaments_by_id,
            identity_index=identity_index,
        )
        if skip_key:
            skipped[skip_key] += 1
            continue
        assert observation is not None
        if observation["category_level"] == "Junior":
            cohort_key = (
                observation["country"],
                observation["weapon"],
                observation["gender"],
                observation["category"],
                observation["season"],
            )
            junior_members[cohort_key][observation["fencer_id"]].add("ranking")
        else:
            senior_by_fencer[observation["fencer_id"]].append(observation)

    for raw_row in results:
        observation, skip_key = observation_from_row(
            raw_row,
            source="result",
            tournaments_by_id=tournaments_by_id,
            identity_index=identity_index,
        )
        if skip_key:
            skipped[skip_key] += 1
            continue
        assert observation is not None
        if observation["category_level"] == "Junior":
            cohort_key = (
                observation["country"],
                observation["weapon"],
                observation["gender"],
                observation["category"],
                observation["season"],
            )
            junior_members[cohort_key][observation["fencer_id"]].add("result")
        else:
            senior_by_fencer[observation["fencer_id"]].append(observation)

    rows: list[dict[str, Any]] = []
    for cohort_key, members in sorted(junior_members.items()):
        country, weapon, gender, category, cohort_season = cohort_key
        sample_count = len(members)
        country_norm_key = country_key(country)

        for window in windows:
            window_start = cohort_season + 1
            window_end = cohort_season + window
            senior_appearance = 0
            senior_ranking = 0
            senior_medal = 0
            senior_top8 = 0
            senior_top16 = 0
            country_transfer = 0

            for fencer_id in members:
                evidence = [
                    observation
                    for observation in senior_by_fencer.get(fencer_id, [])
                    if window_start <= observation["season"] <= window_end
                ]
                if not evidence:
                    continue
                senior_appearance += 1
                if any(observation["source"] == "ranking" for observation in evidence):
                    senior_ranking += 1
                if any(observation.get("is_medal") for observation in evidence):
                    senior_medal += 1
                if any(observation.get("rank") is not None and observation["rank"] <= 8 for observation in evidence):
                    senior_top8 += 1
                if any(observation.get("rank") is not None and observation["rank"] <= 16 for observation in evidence):
                    senior_top16 += 1
                if any(observation["country_key"] and observation["country_key"] != country_norm_key for observation in evidence):
                    country_transfer += 1

            junior_result_count = sum(1 for sources in members.values() if "result" in sources)
            junior_ranking_count = sum(1 for sources in members.values() if "ranking" in sources)
            rows.append(
                {
                    "country": country,
                    "weapon": weapon,
                    "gender": gender,
                    "category": category,
                    "cohort_season": cohort_season,
                    "window_years": window,
                    "sample_count": sample_count,
                    "junior_result_count": junior_result_count,
                    "junior_ranking_count": junior_ranking_count,
                    "senior_appearance_count": senior_appearance,
                    "senior_appearance_rate": rate(senior_appearance, sample_count),
                    "senior_ranking_count": senior_ranking,
                    "senior_ranking_rate": rate(senior_ranking, sample_count),
                    "senior_medal_count": senior_medal,
                    "senior_medal_rate": rate(senior_medal, sample_count),
                    "senior_top8_count": senior_top8,
                    "senior_top8_rate": rate(senior_top8, sample_count),
                    "senior_top16_count": senior_top16,
                    "senior_top16_rate": rate(senior_top16, sample_count),
                    "country_transfer_count": country_transfer,
                    "country_transfer_rate": rate(country_transfer, sample_count),
                    "computed_at": computed_at,
                    "metadata": {
                        "cohort_fencer_ids": sorted(members),
                        "window_start_season": window_start,
                        "window_end_season": window_end,
                        "sparse_cohort": sample_count < SPARSE_COHORT_THRESHOLD,
                    },
                }
            )

    return {
        "computed_at": computed_at,
        "rows": rows,
        "skipped": {key: skipped[key] for key in SKIP_KEYS},
    }


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
            return rows
        offset += page_size


def fetch_with_fallbacks(client, table: str, select_options: list[str], *, page_size: int) -> list[dict[str, Any]]:
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


def load_inputs(client, *, page_size: int) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    rankings = fetch_with_fallbacks(client, "fs_rankings_history", RANKING_SELECTS, page_size=page_size)
    results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
    tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
    fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
    identities = fetch_with_fallbacks(client, "fs_fencer_identities", IDENTITY_SELECTS, page_size=page_size)
    return rankings, results, tournaments, fencers, identities


def probe_rate_table(client) -> None:
    client.table(RATE_TABLE).select("country").limit(0).execute()


def upsert_conversion_rows(client, rows: list[dict[str, Any]], *, batch_size: int = BATCH_SIZE) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table(RATE_TABLE).upsert(batch, on_conflict=RATE_CONFLICT_COLUMNS).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  {RATE_TABLE} upsert batch {index // batch_size} failed: {exc}")
            failed += len(batch)
    return written, failed


def compute_junior_conversion(
    *,
    client=None,
    windows: tuple[int, ...] | list[int] = DEFAULT_WINDOWS,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    computed_at: str | None = None,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    get_state(SOURCE, "last_run") if update_state else None

    try:
        probe_rate_table(client)
        rankings, results, tournaments, fencers, identities = load_inputs(client, page_size=page_size)
        report = build_junior_conversion_report(
            rankings=rankings,
            results=results,
            tournaments=tournaments,
            fencers=fencers,
            identities=identities,
            windows=windows,
            computed_at=computed_at,
        )
        written, failed = upsert_conversion_rows(client, report["rows"], batch_size=batch_size)
        skipped_total = sum(report["skipped"].values())
        summary = {
            "rankings_read": len(rankings),
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "fencers_read": len(fencers),
            "identity_rows": len(identities),
            "rows_generated": len(report["rows"]),
            "rows_written": written,
            "failed": failed,
            "skipped": skipped_total,
            **{f"skipped_{key}": value for key, value in report["skipped"].items()},
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        if run_log:
            run_log.complete(written=written, failed=failed, skipped=skipped_total, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Junior conversion computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_junior_conversion()
    print(
        "Junior conversion computation complete - "
        f"rankings={summary['rankings_read']}, results={summary['results_read']}, "
        f"rows_written={summary['rows_written']}, failed={summary['failed']}, "
        f"skipped={summary['skipped']}"
    )


if __name__ == "__main__":
    main()

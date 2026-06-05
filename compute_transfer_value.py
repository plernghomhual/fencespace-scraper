import json
import os
import re
from datetime import date, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_transfer_value"
TRANSFER_VALUE_TABLE = "fs_transfer_values"
TRANSFER_VALUE_CONFLICT = "fencer_id,season"

SIGNAL_WEIGHTS = {
    "ranking": 0.30,
    "performance": 0.25,
    "form": 0.20,
    "age": 0.15,
    "category": 0.10,
}

ETHICAL_PRODUCT_LIMITATIONS = [
    "Non-monetary decision-support score from public sport data only.",
    "Excludes private, medical, financial, contract, academic, and consent-sensitive context.",
    "Do not use as a sole recruiting, selection, eligibility, or compensation decision input.",
]

FENCER_SELECTS = (
    (
        "id,fie_id,world_rank,national_rank,national_rank_points,national_rank_season,"
        "weapon,category,gender,date_of_birth,birth_date,birth_year,dob"
    ),
    (
        "id,fie_id,world_rank,national_rank,national_rank_points,national_rank_season,"
        "weapon,category,gender,date_of_birth,birth_date,birth_year"
    ),
    "id,fie_id,world_rank,national_rank,national_rank_points,national_rank_season,weapon,category,gender",
    "id,fie_id,world_rank,weapon,category,gender",
    "id,fie_id,world_rank",
    "id,fie_id",
    "id",
)
RANKING_SELECTS = (
    "fie_fencer_id,season,weapon,category,rank,points",
    "fencer_id,season,weapon,category,rank,points",
)
RESULT_SELECTS = (
    "tournament_id,fencer_id,rank,placement,season,weapon,category,gender",
    "tournament_id,fencer_id,rank,placement,season",
    "tournament_id,fencer_id,rank,placement",
    "tournament_id,fencer_id,rank",
)
TOURNAMENT_SELECTS = (
    "id,season,weapon,gender,category",
    "id,season,weapon,category",
    "id,season,weapon",
    "id,season",
)
IDENTITY_SELECTS = (
    "id,fs_fencer_row_ids,fie_ids",
    "canonical_id,fs_fencer_row_ids,fie_ids",
    "id,canonical_id,fs_fencer_row_ids,fie_ids",
    "id,fs_fencer_row_ids",
    "canonical_id,fs_fencer_row_ids",
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
    number: int | None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        number = int(match.group(0)) if match else None
    return number


def coerce_positive_int(value: Any) -> int | None:
    number = coerce_int(value)
    return number if number and number > 0 else None


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_metric(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def normalize_season(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    text = clean_text(value)
    if not text:
        return None
    years = [int(part) for part in re.findall(r"\d{4}", text)]
    if years:
        return years[-1]
    number = coerce_int(text)
    return number if number and number > 0 else None


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold()
    if key in {"e", "epee", "\u00e9p\u00e9e"}:
        return "Epee"
    if key in {"f", "foil"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return text.title()


def normalize_category(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.casefold()
    if "senior" in key:
        return "Senior"
    if "junior" in key or "u20" in key or "under 20" in key:
        return "Junior"
    if "cadet" in key or "u17" in key or "under 17" in key:
        return "Cadet"
    if "veteran" in key or "master" in key:
        return "Veteran"
    return text if "'" in text else text.title()


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


def build_identity_maps(identity_rows: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    row_identity: dict[str, str] = {}
    fie_identity: dict[str, str] = {}
    for row in identity_rows:
        members = parse_identity_members(row.get("fs_fencer_row_ids") or row.get("fencer_ids"))
        canonical = clean_text(row.get("canonical_id"))
        row_id = clean_text(row.get("id"))
        if not canonical and row_id and row_id in members:
            canonical = row_id
        if not canonical and members:
            canonical = members[0]
        if not canonical:
            continue

        row_identity[canonical] = canonical
        for member in members:
            row_identity[member] = canonical
        for fie_id in parse_identity_members(row.get("fie_ids")):
            fie_identity[fie_id] = canonical
    return row_identity, fie_identity


def load_identity_maps(client, page_size: int = PAGE_SIZE) -> tuple[dict[str, str], dict[str, str], int]:
    last_error: Exception | None = None
    for columns in IDENTITY_SELECTS:
        try:
            rows = fetch_all(client, "fs_fencer_identities", columns, page_size=page_size)
            row_identity, fie_identity = build_identity_maps(rows)
            return row_identity, fie_identity, len(rows)
        except Exception as exc:
            last_error = exc
    if last_error:
        print(f"Identity table unavailable; transfer scores use raw fs_fencers rows: {last_error}")
    return {}, {}, 0


def canonical_fencer_id(fencer_id: Any, row_identity: dict[str, str] | None = None) -> str | None:
    text = clean_text(fencer_id)
    if not text:
        return None
    return (row_identity or {}).get(text, text)


def merge_fencer_profiles(
    fencers: list[dict[str, Any]],
    row_identity: dict[str, str] | None = None,
    fie_identity: dict[str, str] | None = None,
) -> tuple[dict[str, dict[str, Any]], int]:
    profiles: dict[str, dict[str, Any]] = {}
    skipped = 0
    for fencer in fencers:
        raw_id = clean_text(fencer.get("id"))
        if not raw_id:
            skipped += 1
            continue
        canonical_id: str = canonical_fencer_id(raw_id, row_identity) or raw_id
        fie_id = clean_text(fencer.get("fie_id"))
        if fie_id and fie_identity and fie_id in fie_identity:
            canonical_id = fie_identity[fie_id]

        profile = profiles.setdefault(
            canonical_id,
            {
                "fencer_id": canonical_id,
                "source_row_ids": set(),
                "fie_ids": set(),
            },
        )
        profile["source_row_ids"].add(raw_id)
        if fie_id:
            profile["fie_ids"].add(fie_id)
        for key, value in fencer.items():
            if key in {"id", "fie_id"}:
                continue
            if profile.get(key) in {None, ""} and clean_text(value):
                profile[key] = value

    return profiles, skipped


def rank_score(rank: int) -> float:
    if rank <= 1:
        return 100.0
    if rank <= 3:
        return 95.0
    if rank <= 8:
        return 90.0
    if rank <= 16:
        return 80.0
    if rank <= 32:
        return 70.0
    if rank <= 64:
        return 55.0
    if rank <= 128:
        return 40.0
    return 25.0


def finish_rank_score(rank: int) -> float:
    if rank <= 1:
        return 100.0
    if rank <= 3:
        return 92.0
    if rank <= 8:
        return 82.0
    if rank <= 16:
        return 68.0
    if rank <= 32:
        return 52.0
    if rank <= 64:
        return 38.0
    return 25.0


def category_score(category: str) -> float:
    key = category.casefold()
    if "senior" in key:
        return 85.0
    if "junior" in key or "u20" in key:
        return 70.0
    if "cadet" in key or "u17" in key:
        return 55.0
    if "veteran" in key or "master" in key:
        return 35.0
    return 50.0


def age_score(age: int, category: str | None) -> float:
    key = (category or "").casefold()
    peak = 27
    floor = 20.0
    if "junior" in key or "u20" in key:
        peak = 19
        floor = 25.0
    elif "cadet" in key or "u17" in key:
        peak = 16
        floor = 25.0
    elif "veteran" in key or "master" in key:
        peak = 45
        floor = 20.0
    return max(floor, 100.0 - abs(age - peak) * 5.0)


def rank_form_score(rank_change: int) -> float:
    return max(15.0, min(100.0, 55.0 + rank_change * 4.0))


def parse_birth_year(value: Any) -> int | None:
    number = coerce_int(value)
    if number and 1900 <= number <= 2100:
        return number
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    return int(match.group(1)) if match else None


def parse_birth_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    text = text.removeprefix("+")
    text = text.split("T", 1)[0]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def age_at_season(profile: dict[str, Any], season: int) -> tuple[int | None, str | None, float | None]:
    for field in ("date_of_birth", "birth_date", "dob"):
        birth_date = parse_birth_date(profile.get(field))
        if birth_date:
            as_of = date(season, 12, 31)
            age = as_of.year - birth_date.year
            if (as_of.month, as_of.day) < (birth_date.month, birth_date.day):
                age -= 1
            return age, field, 0.85

    birth_year = parse_birth_year(profile.get("birth_year"))
    if birth_year:
        return season - birth_year, "birth_year", 0.60

    return None, None, None


def ranking_fencer_id(row: dict[str, Any]) -> str | None:
    return clean_text(row.get("fie_fencer_id") or row.get("fencer_id"))


def normalized_ranking_rows(
    ranking_history: list[dict[str, Any]],
    profile: dict[str, Any],
    season: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fie_ids = {str(item) for item in profile.get("fie_ids", set())}
    if not fie_ids and clean_text(profile.get("fie_id")):
        fie_ids.add(str(profile["fie_id"]))
    candidate_ids = set(fie_ids)
    candidate_ids.add(str(profile["fencer_id"]))
    candidate_ids.update(str(item) for item in profile.get("source_row_ids", set()))

    current: list[dict[str, Any]] = []
    previous: list[dict[str, Any]] = []
    for row in ranking_history:
        external_id = ranking_fencer_id(row)
        if not external_id or external_id not in candidate_ids:
            continue
        row_season = normalize_season(row.get("season"))
        rank = coerce_positive_int(row.get("rank"))
        if row_season is None or rank is None:
            continue
        normalized = {
            **row,
            "season": row_season,
            "rank": rank,
            "points": coerce_float(row.get("points")),
            "weapon": normalize_weapon(row.get("weapon")) or clean_text(row.get("weapon")),
            "category": clean_text(row.get("category")),
        }
        if row_season == season:
            current.append(normalized)
        elif row_season < season:
            previous.append(normalized)
    return current, previous


def choose_best_ranking(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(rows, key=lambda row: (row["rank"], -(coerce_float(row.get("points")) or 0.0)))[0]


def ranking_component(
    profile: dict[str, Any],
    ranking_history: list[dict[str, Any]],
    season: int,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    current_rows, previous_rows = normalized_ranking_rows(ranking_history, profile, season)
    current = choose_best_ranking(current_rows)
    if current:
        return (
            {
                "status": "scored",
                "score": rank_score(current["rank"]),
                "confidence": 1.0,
                "source": "fs_rankings_history",
                "rank": current["rank"],
                "points": current.get("points"),
                "weapon": current.get("weapon"),
                "category": current.get("category"),
            },
            current,
            choose_best_ranking(previous_rows),
        )

    current_rank = coerce_positive_int(profile.get("world_rank"))
    if current_rank is not None:
        return (
            {
                "status": "scored",
                "score": rank_score(current_rank),
                "confidence": 0.8,
                "source": "fs_fencers.world_rank",
                "rank": current_rank,
            },
            {"rank": current_rank, "source": "fs_fencers.world_rank"},
            None,
        )

    national_rank = coerce_positive_int(profile.get("national_rank"))
    if national_rank is not None:
        return (
            {
                "status": "scored",
                "score": rank_score(national_rank),
                "confidence": 0.65,
                "source": "fs_fencers.national_rank",
                "rank": national_rank,
                "points": coerce_float(profile.get("national_rank_points")),
                "season": clean_text(profile.get("national_rank_season")),
            },
            {"rank": national_rank, "source": "fs_fencers.national_rank"},
            None,
        )

    return {"status": "missing", "reason": "no public ranking signal"}, None, None


def tournament_lookup(tournaments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in tournaments if row.get("id") is not None}


def performance_component(
    profile: dict[str, Any],
    results: list[dict[str, Any]],
    tournaments_by_id: dict[str, dict[str, Any]],
    row_identity: dict[str, str] | None,
    season: int,
) -> tuple[dict[str, Any], str | None]:
    fencer_id = profile["fencer_id"]
    ranks: list[int] = []
    categories: list[str] = []
    for result in results:
        result_fencer = canonical_fencer_id(result.get("fencer_id"), row_identity)
        if result_fencer != fencer_id:
            continue

        tournament_id = clean_text(result.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id) if tournament_id else None
        result_season = normalize_season((tournament or result).get("season"))
        if result_season != season:
            continue

        rank = coerce_positive_int(result.get("rank") if result.get("rank") is not None else result.get("placement"))
        if rank is None:
            continue
        ranks.append(rank)

        category = normalize_category((tournament or result).get("category"))
        if category:
            categories.append(category)

    if not ranks:
        return {"status": "missing", "reason": "no public result signal for season"}, None

    scores = [finish_rank_score(rank) for rank in ranks]
    return (
        {
            "status": "scored",
            "score": round_metric(sum(scores) / len(scores)),
            "confidence": round_metric(min(1.0, len(ranks) / 4.0)),
            "source": "fs_results",
            "competitions": len(ranks),
            "avg_rank": round_metric(sum(ranks) / len(ranks)),
            "best_rank": min(ranks),
            "top8_count": sum(1 for rank in ranks if rank <= 8),
        },
        categories[0] if categories else None,
    )


def form_component(current_ranking: dict[str, Any] | None, previous_ranking: dict[str, Any] | None) -> dict[str, Any]:
    if not current_ranking or not previous_ranking:
        return {"status": "missing", "reason": "no comparable public form signal"}
    current_rank = coerce_positive_int(current_ranking.get("rank"))
    previous_rank = coerce_positive_int(previous_ranking.get("rank"))
    if current_rank is None or previous_rank is None:
        return {"status": "missing", "reason": "no comparable public form signal"}

    rank_change = previous_rank - current_rank
    return {
        "status": "scored",
        "score": rank_form_score(rank_change),
        "confidence": 0.9,
        "source": "fs_rankings_history",
        "previous_rank": previous_rank,
        "current_rank": current_rank,
        "rank_change": rank_change,
    }


def age_component(profile: dict[str, Any], season: int, category: str | None) -> dict[str, Any]:
    age, source, confidence = age_at_season(profile, season)
    if age is None or source is None or confidence is None:
        return {"status": "missing", "reason": "no public birth date or birth year"}
    return {
        "status": "scored",
        "score": round_metric(age_score(age, category)),
        "confidence": confidence,
        "source": source,
        "age": age,
    }


def category_component(category: str | None) -> dict[str, Any]:
    if not category:
        return {"status": "missing", "reason": "no public category signal"}
    return {
        "status": "scored",
        "score": category_score(category),
        "confidence": 0.75,
        "source": "public category field",
        "category": category,
    }


def build_score_components(
    profile: dict[str, Any],
    ranking_history: list[dict[str, Any]],
    results: list[dict[str, Any]],
    tournaments_by_id: dict[str, dict[str, Any]],
    row_identity: dict[str, str] | None,
    season: int,
) -> dict[str, Any]:
    ranking, current_ranking, previous_ranking = ranking_component(profile, ranking_history, season)
    performance, performance_category = performance_component(
        profile,
        results,
        tournaments_by_id,
        row_identity,
        season,
    )
    form = form_component(current_ranking, previous_ranking)

    category = (
        normalize_category(profile.get("category"))
        or normalize_category((current_ranking or {}).get("category"))
        or performance_category
    )
    age = age_component(profile, season, category)
    category_info = category_component(category)

    components: dict[str, Any] = {
        "score_label": "transfer impact score",
        "ranking": ranking,
        "performance": performance,
        "form": form,
        "age": age,
        "category": category_info,
    }
    components["missing_signals"] = [
        name
        for name in SIGNAL_WEIGHTS
        if components[name].get("status") != "scored"
    ]
    components["limitations"] = ETHICAL_PRODUCT_LIMITATIONS
    return components


def combined_value_score(components: dict[str, Any]) -> float | None:
    has_primary_signal = any(
        components[name].get("status") == "scored"
        for name in ("ranking", "performance", "form")
    )
    if not has_primary_signal:
        return None

    weighted_sum = 0.0
    available_weight = 0.0
    for name, weight in SIGNAL_WEIGHTS.items():
        component = components[name]
        if component.get("status") == "scored":
            weighted_sum += weight * float(component["score"])
            available_weight += weight
    if available_weight <= 0:
        return None
    return round_metric(weighted_sum / available_weight)


def combined_confidence(components: dict[str, Any]) -> float:
    confidence = 0.0
    for name, weight in SIGNAL_WEIGHTS.items():
        component = components[name]
        if component.get("status") == "scored":
            confidence += weight * float(component.get("confidence", 0.0))
    return round_metric(confidence) or 0.0


def build_transfer_value_rows(
    fencers: list[dict[str, Any]],
    ranking_history: list[dict[str, Any]],
    results: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    season: int,
    updated_at: str | None = None,
    row_identity: dict[str, str] | None = None,
    fie_identity: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    profiles, skipped = merge_fencer_profiles(fencers, row_identity, fie_identity)
    tournaments_by_id = tournament_lookup(tournaments)
    now = updated_at or datetime.now(timezone.utc).isoformat()

    rows: list[dict[str, Any]] = []
    for fencer_id in sorted(profiles):
        profile = profiles[fencer_id]
        components = build_score_components(
            profile,
            ranking_history,
            results,
            tournaments_by_id,
            row_identity,
            season,
        )
        rows.append(
            {
                "fencer_id": fencer_id,
                "season": season,
                "value_score": combined_value_score(components),
                "score_components": components,
                "confidence": combined_confidence(components),
                "updated_at": now,
            }
        )
    return rows, skipped


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


def current_fie_season(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month < 7 else today.year + 1


def compute_transfer_values(
    client=None,
    season: int | None = None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    updated_at: str | None = None,
) -> dict[str, int]:
    season = season or current_fie_season()
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    try:
        fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
        ranking_history = fetch_with_fallbacks(client, "fs_rankings_history", RANKING_SELECTS, page_size=page_size)
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
        row_identity, fie_identity, identity_rows = load_identity_maps(client, page_size=page_size)

        rows, skipped = build_transfer_value_rows(
            fencers,
            ranking_history,
            results,
            tournaments,
            season=season,
            updated_at=updated_at,
            row_identity=row_identity,
            fie_identity=fie_identity,
        )
        written = (
            batch_upsert(
                client,
                TRANSFER_VALUE_TABLE,
                rows,
                on_conflict=TRANSFER_VALUE_CONFLICT,
            )
            if rows
            else 0
        )
        no_score_rows = sum(1 for row in rows if row["value_score"] is None)
        summary = {
            "fencers_read": len(fencers),
            "rankings_read": len(ranking_history),
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "identity_rows": identity_rows,
            "value_rows": len(rows),
            "no_score_rows": no_score_rows,
            "written": written,
            "skipped": skipped,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {"updated_at": datetime.now(timezone.utc).isoformat(), "season": season, **summary},
            )
        if run_log:
            run_log.complete(written=written, failed=0, skipped=skipped)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Transfer impact score computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_transfer_values()
    print(
        "Transfer impact score computation complete - "
        f"{summary['value_rows']} rows built, "
        f"{summary['written']} rows upserted, "
        f"{summary['no_score_rows']} no-score rows"
    )


if __name__ == "__main__":
    main()

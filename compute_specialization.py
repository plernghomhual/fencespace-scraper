from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state

try:
    from supabase import create_client
except Exception:  # pragma: no cover - import errors surface when a client is required.
    create_client = None


SOURCE = "compute_specialization"
PAGE_SIZE = 1000

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

RESULT_SELECTS = [
    "tournament_id,fencer_id,fie_fencer_id,weapon,category,season,rank,placement,medal,date",
    "tournament_id,fencer_id,weapon,category,season,rank,placement,medal,date",
    "tournament_id,fencer_id,rank,placement,medal",
]
TOURNAMENT_SELECTS = [
    "id,season,weapon,gender,category,start_date,end_date,date,name",
    "id,season,weapon,gender,category,start_date,end_date",
    "id,season,weapon,gender,category",
]
FENCER_SELECTS = [
    "id,fie_id,date_of_birth,birth_date,dob",
    "id,fie_id,date_of_birth",
    "id,fie_id",
]
IDENTITY_SELECTS = [
    "canonical_id,fs_fencer_row_ids",
    "id,canonical_id,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
    "canonical_id,fencer_ids",
]


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    if create_client is None:
        raise RuntimeError("supabase package is required.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    ).casefold()


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


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
    key = normalize_key(text).replace(".", "")
    if key in {"f", "female", "women", "woman", "womens", "women's"}:
        return "Women's"
    if key in {"m", "male", "men", "man", "mens", "men's"}:
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


def category_level(category: Any) -> str | None:
    key = normalize_key(category)
    if not key:
        return None
    if "junior" in key or re.search(r"\bu20\b", key):
        return "Junior"
    if "senior" in key:
        return "Senior"
    return None


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


def season_label(value: Any) -> str | None:
    text = clean_text(value)
    if text:
        return text
    number = season_to_int(value)
    return str(number) if number is not None else None


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


def date_from_season(value: Any) -> date | None:
    season = season_to_int(value)
    if season is None:
        return None
    return date(season, 7, 1)


def event_date(result: dict[str, Any], tournament: dict[str, Any] | None) -> date | None:
    for key in ("date", "event_date", "start_date", "end_date"):
        parsed = parse_date(result.get(key))
        if parsed:
            return parsed
    if tournament:
        for key in ("start_date", "end_date", "date"):
            parsed = parse_date(tournament.get(key))
            if parsed:
                return parsed
    return date_from_season(result.get("season") or (tournament or {}).get("season"))


def event_sort_value(observation: dict[str, Any]) -> int:
    event_dt = observation.get("event_date")
    if isinstance(event_dt, date):
        return event_dt.toordinal()
    season = season_to_int(observation.get("season"))
    return season * 400 if season is not None else 0


def age_at(birth_date: date | None, event_dt: date | None) -> float | None:
    if not birth_date or not event_dt:
        return None
    return round((event_dt - birth_date).days / 365.25, 1)


def medal_from_result(rank: int | None, medal: Any) -> bool:
    if rank is not None and 1 <= rank <= 3:
        return True
    text = normalize_key(medal)
    return text in {"gold", "silver", "bronze", "g", "s", "b"}


def round_float(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None


def average(values: list[int | float]) -> float | None:
    return sum(values) / len(values) if values else None


def tournament_lookup(tournaments: dict[Any, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    values: list[dict[str, Any]]
    if isinstance(tournaments, dict):
        values = list(tournaments.values())
    else:
        values = tournaments
    return {str(row["id"]): row for row in values if row.get("id") is not None}


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


def build_identity_map(identity_rows: list[dict[str, Any]]) -> dict[str, str]:
    identity_map: dict[str, str] = {}
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
        identity_map[canonical] = canonical
        for member in members:
            identity_map[member] = canonical
    return identity_map


def canonical_fencer_id(fencer_id: Any, identity_map: dict[str, str] | None) -> str | None:
    text = clean_text(fencer_id)
    if not text:
        return None
    return (identity_map or {}).get(text, text)


def build_fencer_maps(
    fencers: list[dict[str, Any]] | None,
    identity_map: dict[str, str] | None,
) -> tuple[dict[str, str], dict[str, date]]:
    fencer_id_by_fie_id: dict[str, str] = {}
    birth_dates: dict[str, date] = {}
    for row in fencers or []:
        row_id = clean_text(row.get("id"))
        canonical_id = canonical_fencer_id(row_id, identity_map)
        if not canonical_id:
            continue
        fie_id = clean_text(row.get("fie_id"))
        if fie_id:
            fencer_id_by_fie_id.setdefault(fie_id, canonical_id)
        birth = (
            parse_date(row.get("date_of_birth"))
            or parse_date(row.get("birth_date"))
            or parse_date(row.get("dob"))
        )
        if birth and canonical_id not in birth_dates:
            birth_dates[canonical_id] = birth
    return fencer_id_by_fie_id, birth_dates


def result_fencer_id(
    result: dict[str, Any],
    fencer_id_by_fie_id: dict[str, str],
    identity_map: dict[str, str] | None,
) -> str | None:
    fencer_id = clean_text(result.get("fencer_id"))
    if not fencer_id:
        fie_id = clean_text(result.get("fie_fencer_id") or result.get("fie_id"))
        fencer_id = fencer_id_by_fie_id.get(fie_id or "")
    return canonical_fencer_id(fencer_id, identity_map)


def choose_better_observation(
    current: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    if current is None:
        return candidate
    current_rank = current.get("rank")
    candidate_rank = candidate.get("rank")
    if candidate_rank is not None and (current_rank is None or candidate_rank < current_rank):
        return candidate
    if candidate_rank == current_rank and event_sort_value(candidate) > event_sort_value(current):
        return candidate
    return current


def build_observations(
    results: list[dict[str, Any]],
    tournaments: dict[Any, dict[str, Any]] | list[dict[str, Any]],
    fencers: list[dict[str, Any]] | None,
    identity_map: dict[str, str] | None,
) -> tuple[dict[str, list[dict[str, Any]]], int, dict[str, date]]:
    tournaments_by_id = tournament_lookup(tournaments)
    fencer_id_by_fie_id, birth_dates = build_fencer_maps(fencers, identity_map)
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped = 0

    for index, result in enumerate(results):
        fencer_id = result_fencer_id(result, fencer_id_by_fie_id, identity_map)
        tournament_id = clean_text(result.get("tournament_id") or result.get("competition_id"))
        tournament = tournaments_by_id.get(str(tournament_id)) if tournament_id else None
        weapon = normalize_weapon(result.get("weapon") or (tournament or {}).get("weapon"))
        if not fencer_id or not weapon:
            skipped += 1
            continue

        category = normalize_category(
            result.get("category") or (tournament or {}).get("category"),
            result.get("gender") or (tournament or {}).get("gender"),
        )
        season = season_label(result.get("season") or (tournament or {}).get("season"))
        rank = to_int(result.get("rank") if result.get("rank") is not None else result.get("placement"))
        competition_id = tournament_id or f"result:{index}"
        observed_at = event_date(result, tournament)
        observation = {
            "fencer_id": fencer_id,
            "competition_id": competition_id,
            "weapon": weapon,
            "category": category,
            "category_level": category_level(category),
            "season": season,
            "season_sort": season_to_int(season),
            "rank": rank,
            "is_medal": medal_from_result(rank, result.get("medal")),
            "event_date": observed_at,
            "event_date_iso": observed_at.isoformat() if observed_at else None,
        }
        key = (fencer_id, competition_id, weapon)
        deduped[key] = choose_better_observation(deduped.get(key), observation)

    by_fencer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in deduped.values():
        by_fencer[str(observation["fencer_id"])].append(observation)

    for fencer_id in by_fencer:
        by_fencer[fencer_id].sort(
            key=lambda item: (
                event_sort_value(item),
                item.get("competition_id") or "",
                item.get("weapon") or "",
            )
        )
    return dict(by_fencer), skipped, birth_dates


def metric_summary(observations: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = [obs["rank"] for obs in observations if obs.get("rank") is not None]
    competitions = {
        (obs["fencer_id"], obs["competition_id"])
        for obs in observations
        if obs.get("competition_id")
    }
    competition_count = len(competitions) or len(observations)
    medal_count = sum(1 for obs in observations if obs.get("is_medal"))
    return {
        "results": len(observations),
        "competitions": competition_count,
        "ranked_results": len(ranks),
        "avg_rank": round_float(average(ranks)),
        "best_rank": min(ranks) if ranks else None,
        "worst_rank": max(ranks) if ranks else None,
        "medal_count": medal_count,
        "medals_per_competition": round_float(medal_count / competition_count) if competition_count else None,
    }


def primary_weapon(observations: list[dict[str, Any]]) -> str | None:
    if not observations:
        return None
    weapons = sorted({obs["weapon"] for obs in observations})

    def key(weapon: str) -> tuple[int, int, float, str]:
        weapon_obs = [obs for obs in observations if obs["weapon"] == weapon]
        ranks = [obs["rank"] for obs in weapon_obs if obs.get("rank") is not None]
        avg_rank = average(ranks)
        latest = max(event_sort_value(obs) for obs in weapon_obs)
        return (-len(weapon_obs), -latest, avg_rank if avg_rank is not None else float("inf"), weapon)

    return sorted(weapons, key=key)[0]


def season_primary_rows(observations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_season: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obs in observations:
        if obs.get("season"):
            by_season[obs["season"]].append(obs)

    rows: dict[str, dict[str, Any]] = {}
    for season, season_obs in by_season.items():
        weapon = primary_weapon(season_obs)
        weapon_obs = [obs for obs in season_obs if obs["weapon"] == weapon]
        rows[season] = {
            "season": season,
            "season_sort": season_to_int(season),
            "primary_weapon": weapon,
            "avg_rank": metric_summary(weapon_obs)["avg_rank"],
        }
    return rows


def fencer_switches(fencer_id: str, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    season_rows = [
        row
        for row in season_primary_rows(observations).values()
        if row["season_sort"] is not None
    ]
    season_rows.sort(key=lambda row: (row["season_sort"], row["season"]))
    switches = []
    for previous, current in zip(season_rows, season_rows[1:]):
        if previous["primary_weapon"] == current["primary_weapon"]:
            continue
        before = previous["avg_rank"]
        after = current["avg_rank"]
        switches.append(
            {
                "fencer_id": fencer_id,
                "from_season": previous["season"],
                "to_season": current["season"],
                "from_weapon": previous["primary_weapon"],
                "to_weapon": current["primary_weapon"],
                "before_avg_rank": before,
                "after_avg_rank": after,
                "rank_delta": round_float(after - before) if before is not None and after is not None else None,
            }
        )
    return switches


def fencer_report_row(fencer_id: str, observations: list[dict[str, Any]]) -> dict[str, Any]:
    weapons = sorted({obs["weapon"] for obs in observations})
    metrics = metric_summary(observations)
    per_weapon = {
        weapon: metric_summary([obs for obs in observations if obs["weapon"] == weapon])
        for weapon in weapons
    }
    switches = fencer_switches(fencer_id, observations)
    row = {
        "fencer_id": fencer_id,
        "classification": "single_weapon" if len(weapons) == 1 else "multi_weapon",
        "primary_weapon": primary_weapon(observations),
        "weapons": weapons,
        "total_results": metrics["results"],
        "total_competitions": metrics["competitions"],
        "ranked_results": metrics["ranked_results"],
        "avg_rank": metrics["avg_rank"],
        "best_rank": metrics["best_rank"],
        "worst_rank": metrics["worst_rank"],
        "medal_count": metrics["medal_count"],
        "medals_per_competition": metrics["medals_per_competition"],
        "per_weapon": per_weapon,
        "season_primary_weapons": {
            season: row["primary_weapon"]
            for season, row in sorted(
                season_primary_rows(observations).items(),
                key=lambda item: (item[1]["season_sort"] or 0, item[0]),
            )
        },
        "changed_primary_weapon": bool(switches),
        "weapon_switches": switches,
        "categories": sorted({obs["category"] for obs in observations if obs.get("category")}),
    }
    return row


def aggregate_group(observations: list[dict[str, Any]], fencer_ids: set[str]) -> dict[str, Any]:
    group_observations = [obs for obs in observations if obs["fencer_id"] in fencer_ids]
    metrics = metric_summary(group_observations)
    by_weapon = {}
    for weapon in sorted({obs["weapon"] for obs in group_observations}):
        by_weapon[weapon] = metric_summary(
            [obs for obs in group_observations if obs["weapon"] == weapon]
        )["avg_rank"]
    return {
        "fencers": len(fencer_ids),
        "results": metrics["results"],
        "competitions": metrics["competitions"],
        "avg_rank": metrics["avg_rank"],
        "medal_count": metrics["medal_count"],
        "medals_per_competition": metrics["medals_per_competition"],
        "avg_rank_by_weapon": by_weapon,
    }


def compare_specialists_and_generalists(specialists: dict[str, Any], generalists: dict[str, Any]) -> dict[str, Any]:
    specialist_rank = specialists.get("avg_rank")
    generalist_rank = generalists.get("avg_rank")
    specialist_medals = specialists.get("medals_per_competition")
    generalist_medals = generalists.get("medals_per_competition")
    rank_delta = (
        round_float(specialist_rank - generalist_rank)
        if specialist_rank is not None and generalist_rank is not None
        else None
    )
    medal_delta = (
        round_float(specialist_medals - generalist_medals)
        if specialist_medals is not None and generalist_medals is not None
        else None
    )

    if rank_delta is None and medal_delta is None:
        verdict = "insufficient_data"
    elif (rank_delta is None or rank_delta < 0) and (medal_delta is None or medal_delta >= 0):
        verdict = "specialists_outperform"
    elif (rank_delta is None or rank_delta > 0) and (medal_delta is None or medal_delta <= 0):
        verdict = "generalists_outperform"
    else:
        verdict = "mixed"

    return {
        "avg_rank_delta": rank_delta,
        "medals_per_competition_delta": medal_delta,
        "verdict": verdict,
    }


def aggregate_report(
    fencer_rows: list[dict[str, Any]],
    observations_by_fencer: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    observations = [obs for rows in observations_by_fencer.values() for obs in rows]
    specialist_ids = {row["fencer_id"] for row in fencer_rows if row["classification"] == "single_weapon"}
    generalist_ids = {row["fencer_id"] for row in fencer_rows if row["classification"] == "multi_weapon"}
    specialists = aggregate_group(observations, specialist_ids)
    generalists = aggregate_group(observations, generalist_ids)
    return {
        "specialists": specialists,
        "generalists": generalists,
        "specialist_vs_generalist": compare_specialists_and_generalists(specialists, generalists),
    }


def transition_report(
    observations_by_fencer: dict[str, list[dict[str, Any]]],
    birth_dates: dict[str, date],
) -> dict[str, Any]:
    junior_fencers = 0
    transitions = []

    for fencer_id, observations in sorted(observations_by_fencer.items()):
        juniors = [obs for obs in observations if obs.get("category_level") == "Junior"]
        if not juniors:
            continue
        junior_fencers += 1
        first_junior = min(juniors, key=event_sort_value)
        senior_candidates = [
            obs
            for obs in observations
            if obs.get("category_level") == "Senior" and event_sort_value(obs) >= event_sort_value(first_junior)
        ]
        if not senior_candidates:
            continue
        first_senior = min(senior_candidates, key=event_sort_value)
        junior_date = first_junior.get("event_date")
        senior_date = first_senior.get("event_date")
        years_between = None
        if isinstance(junior_date, date) and isinstance(senior_date, date):
            years_between = round_float((senior_date - junior_date).days / 365.25, 1)
        transitions.append(
            {
                "fencer_id": fencer_id,
                "first_junior_competition": first_junior.get("competition_id"),
                "first_senior_competition": first_senior.get("competition_id"),
                "first_junior_date": first_junior.get("event_date_iso"),
                "first_senior_date": first_senior.get("event_date_iso"),
                "transition_age": age_at(birth_dates.get(fencer_id), senior_date if isinstance(senior_date, date) else None),
                "years_between": years_between,
            }
        )

    ages: list[float] = [float(row["transition_age"]) for row in transitions if row["transition_age"] is not None]
    gaps: list[float] = [float(row["years_between"]) for row in transitions if row["years_between"] is not None]
    return {
        "junior_fencers": junior_fencers,
        "senior_transitioners": len(transitions),
        "junior_to_senior_pct": round_float(len(transitions) / junior_fencers * 100, 2) if junior_fencers else None,
        "avg_transition_age": round_float(average(ages), 1),
        "avg_years_between_first_junior_and_senior": round_float(average(gaps), 1),
        "transitions": transitions,
    }


def weapon_switching_report(observations_by_fencer: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    switches = []
    fencers_with_multiple_seasons = 0
    switching_fencers = set()

    for fencer_id, observations in sorted(observations_by_fencer.items()):
        season_count = sum(
            1
            for row in season_primary_rows(observations).values()
            if row.get("season_sort") is not None
        )
        if season_count < 2:
            continue
        fencers_with_multiple_seasons += 1
        fencer_switch_rows = fencer_switches(fencer_id, observations)
        if fencer_switch_rows:
            switching_fencers.add(fencer_id)
            switches.extend(fencer_switch_rows)

    deltas = [row["rank_delta"] for row in switches if row["rank_delta"] is not None]
    improved = [delta for delta in deltas if delta < 0]
    return {
        "fencers_with_multiple_seasons": fencers_with_multiple_seasons,
        "switching_fencers": len(switching_fencers),
        "switching_pct": (
            round_float(len(switching_fencers) / fencers_with_multiple_seasons * 100, 2)
            if fencers_with_multiple_seasons
            else None
        ),
        "switches": switches,
        "avg_rank_delta_after_switch": round_float(average(deltas)),
        "improved_after_switch_pct": round_float(len(improved) / len(deltas) * 100, 2) if deltas else None,
    }


def build_specialization_report(
    *,
    results: list[dict[str, Any]],
    tournaments: dict[Any, dict[str, Any]] | list[dict[str, Any]],
    fencers: list[dict[str, Any]] | None = None,
    identity_map: dict[str, str] | None = None,
    computed_at: str | None = None,
) -> dict[str, Any]:
    generated_at = computed_at or datetime.now(timezone.utc).isoformat()
    observations_by_fencer, skipped, birth_dates = build_observations(
        results,
        tournaments,
        fencers,
        identity_map,
    )
    fencer_rows = [
        fencer_report_row(fencer_id, observations_by_fencer[fencer_id])
        for fencer_id in sorted(observations_by_fencer)
    ]

    return {
        "computed_at": generated_at,
        "fencers": fencer_rows,
        "aggregate": aggregate_report(fencer_rows, observations_by_fencer),
        "category_transition": transition_report(observations_by_fencer, birth_dates),
        "weapon_switching": weapon_switching_report(observations_by_fencer),
        "skipped_results": skipped,
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
    last_exc: Exception | None = None
    for columns in select_options:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_exc = exc
            print(f"  Select fallback for {table}: {exc}")
    if last_exc:
        raise last_exc
    return []


def load_identity_map(client, *, page_size: int) -> tuple[dict[str, str], int]:
    for columns in IDENTITY_SELECTS:
        try:
            rows = fetch_all(client, "fs_fencer_identities", columns, page_size=page_size)
            return build_identity_map(rows), len(rows)
        except Exception as exc:
            last_error = exc
    print(f"Identity table unavailable; using raw fs_results.fencer_id grouping: {last_error}")
    return {}, 0


def compact_summary(
    report: dict[str, Any],
    *,
    results_read: int,
    tournaments_read: int,
    fencers_read: int,
    identity_rows: int,
) -> dict[str, Any]:
    aggregate = report["aggregate"]
    transition = report["category_transition"]
    switching = report["weapon_switching"]
    return {
        "results_read": results_read,
        "tournaments_read": tournaments_read,
        "fencers_read": fencers_read,
        "identity_rows": identity_rows,
        "fencers_analyzed": len(report["fencers"]),
        "single_weapon_fencers": aggregate["specialists"]["fencers"],
        "multi_weapon_fencers": aggregate["generalists"]["fencers"],
        "skipped_results": report["skipped_results"],
        "junior_fencers": transition["junior_fencers"],
        "senior_transitioners": transition["senior_transitioners"],
        "junior_to_senior_pct": transition["junior_to_senior_pct"],
        "weapon_switching_fencers": switching["switching_fencers"],
        "weapon_switching_pct": switching["switching_pct"],
        "specialist_vs_generalist": aggregate["specialist_vs_generalist"]["verdict"],
    }


_SPECIALIZE_TABLE = "fs_fencer_specialization"
_BATCH_SIZE = 200


def _persist_specialization_rows(
    client,
    fencer_rows: list[dict[str, Any]],
    computed_at: str,
) -> int:
    written = 0
    for i in range(0, len(fencer_rows), _BATCH_SIZE):
        batch = []
        for row in fencer_rows[i : i + _BATCH_SIZE]:
            batch.append({
                "fencer_id": row["fencer_id"],
                "classification": row["classification"],
                "primary_weapon": row.get("primary_weapon"),
                "weapons": row.get("weapons", []),
                "total_results": row.get("total_results", 0),
                "total_competitions": row.get("total_competitions", 0),
                "ranked_results": row.get("ranked_results", 0),
                "avg_rank": row.get("avg_rank"),
                "best_rank": row.get("best_rank"),
                "worst_rank": row.get("worst_rank"),
                "medal_count": row.get("medal_count", 0),
                "medals_per_competition": row.get("medals_per_competition"),
                "per_weapon": row.get("per_weapon", {}),
                "season_primary_weapons": row.get("season_primary_weapons", {}),
                "changed_primary_weapon": row.get("changed_primary_weapon", False),
                "weapon_switches": row.get("weapon_switches", []),
                "categories": row.get("categories", []),
                "computed_at": computed_at,
            })
        (
            client.table(_SPECIALIZE_TABLE)
            .upsert(batch, on_conflict="fencer_id")
            .execute()
        )
        written += len(batch)
    return written


def compute_specialization(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    computed_at: str | None = None,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None

    try:
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
        fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
        identity_map, identity_rows = load_identity_map(client, page_size=page_size)
        report = build_specialization_report(
            results=results,
            tournaments=tournaments,
            fencers=fencers,
            identity_map=identity_map,
            computed_at=computed_at,
        )
        summary = compact_summary(
            report,
            results_read=len(results),
            tournaments_read=len(tournaments),
            fencers_read=len(fencers),
            identity_rows=identity_rows,
        )
        summary["report"] = report

        written = _persist_specialization_rows(client, report["fencers"], report["computed_at"])

        state_summary = {key: value for key, value in summary.items() if key != "report"}
        state_summary["computed_at"] = report["computed_at"]
        state_summary["rows_written"] = written
        if update_state:
            set_state(SOURCE, "last_run", state_summary)
        if run_log:
            run_log.complete(
                written=written,
                failed=0,
                skipped=summary["skipped_results"],
                metadata=state_summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Weapon specialization computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_specialization()
    print(
        "Weapon specialization computation complete - "
        f"{summary['fencers_analyzed']} fencers analyzed, "
        f"{summary['single_weapon_fencers']} specialists, "
        f"{summary['multi_weapon_fencers']} generalists"
    )
    print(
        "Specialists vs generalists: "
        f"{summary['specialist_vs_generalist']}; "
        f"Junior-to-Senior transition: {summary['junior_to_senior_pct']}%; "
        f"weapon switching: {summary['weapon_switching_pct']}%"
    )


if __name__ == "__main__":
    main()

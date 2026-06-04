from __future__ import annotations

import os
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SOURCE = "compute_home_advantage"
PAGE_SIZE = 1000
BATCH_SIZE = 100
UNKNOWN_COUNTRY = "Unknown"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

RESULT_SELECTS = (
    "id,tournament_id,fencer_id,name,country,nationality,rank,placement,medal,weapon,gender,category",
    "id,tournament_id,fencer_id,name,nationality,rank,placement,medal,weapon,gender,category",
    "id,tournament_id,fencer_id,name,country,rank,placement,medal,weapon,gender,category",
    "tournament_id,fencer_id,name,country,nationality,rank,placement,medal",
)
FENCER_SELECTS = (
    "id,fie_id,name,country,metadata",
    "id,fie_id,name,country",
    "id,name,country,metadata",
)
TOURNAMENT_SELECTS = (
    "id,name,country,country_code,location,city,start_date,end_date,weapon,gender,category,type,metadata",
    "id,name,country,country_code,start_date,end_date,weapon,gender,category,type,metadata",
    "id,name,country,start_date,end_date,weapon,gender,category,type",
    "id,name,start_date,end_date,weapon,gender,category,type",
)
HISTORY_SELECT = (
    "fencer_id,country,country_code,start_date,end_date,point_in_time,source,confidence,metadata"
)

COUNTRY_ALIASES = {
    "_AIN": "Russia",
    "AIN_": "Russia",
    "AIN": "Russia",
    "INDIVIDUAL NEUTRAL ATHLETES": "Russia",
    "FIE": "FIE",
    "NEUTRAL": "Neutral",
    "UNKNOWN": UNKNOWN_COUNTRY,
    "US": "United States",
    "USA": "United States",
    "UNITED STATES": "United States",
    "UNITED STATES OF AMERICA": "United States",
    "GB": "Great Britain",
    "GBR": "Great Britain",
    "GREAT BRITAIN": "Great Britain",
    "UK": "Great Britain",
    "ITA": "Italy",
    "ITALIA": "Italy",
    "FRA": "France",
    "FRANCE": "France",
    "GER": "Germany",
    "DEU": "Germany",
    "GERMANY": "Germany",
    "CAN": "Canada",
    "CANADA": "Canada",
    "CHN": "China",
    "CHINA": "China",
    "JPN": "Japan",
    "JAPAN": "Japan",
    "KOR": "South Korea",
    "KOREA": "South Korea",
    "SOUTH KOREA": "South Korea",
    "HKG": "Hong Kong",
    "HONG KONG, CHINA": "Hong Kong",
    "HONG KONG CHINA": "Hong Kong",
    "MACAO, CHINA": "Macau",
    "MACAO CHINA": "Macau",
    "TURKIYE": "Turkey",
    "TÜRKIYE": "Turkey",
    "TÜRKİYE": "Turkey",
    "COTE D'IVOIRE": "Cote D'Ivoire",
    "COTE DIVOIRE": "Cote D'Ivoire",
}

NEUTRAL_COUNTRY_KEYS = {"fie", "neutral", "unknown", "tbd"}

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

MEDAL_MAP = {
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


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def ascii_fold(value: Any) -> str:
    text = clean_text(value) or ""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", ascii_fold(value).casefold())


def country_alias_key(value: Any) -> str:
    text = ascii_fold(value).upper().replace(".", "")
    return re.sub(r"\s+", " ", text).strip()


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = country_alias_key(text)
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]
    if len(key) == 3 and key.isalpha():
        return key
    return text.title()


def country_key(value: Any) -> str:
    return compact_key(normalize_country(value))


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = compact_key(text)
    if key in {"e", "epee", "eepee"}:
        return "Epee"
    if key in {"f", "foil"}:
        return "Foil"
    if key in {"s", "sabre", "saber"}:
        return "Sabre"
    return text.title()


def normalize_gender(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = compact_key(text)
    if key in {"m", "men", "mens", "male"}:
        return "Men"
    if key in {"w", "women", "womens", "female"}:
        return "Women"
    if key in {"mixed", "team"}:
        return text.title()
    return text.title()


def normalize_category(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = compact_key(text)
    if key in {"senior", "seniors"}:
        return "Senior"
    if key in {"junior", "juniors", "u20"}:
        return "Junior"
    if key in {"cadet", "cadets", "u17"}:
        return "Cadet"
    if key in {"veteran", "veterans"}:
        return "Veteran"
    return text.title()


def normalize_tier(tournament: dict[str, Any] | None) -> str | None:
    if not tournament:
        return None
    for field in ("tier", "type", "competition_type"):
        tier = TYPE_TIERS.get(country_alias_key(tournament.get(field)))
        if tier:
            return tier
    haystack = " ".join(
        clean_text(tournament.get(field)) or ""
        for field in ("tier", "type", "name", "category")
    )
    key = compact_key(haystack)
    for raw, tier in TYPE_TIERS.items():
        if raw.casefold() in key or compact_key(raw) in key:
            return tier
    return clean_text(tournament.get("type"))


def coerce_positive_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(value))
        number = int(match.group(0)) if match else None
    return number if number and number > 0 else None


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    text = text.lstrip("+")
    if "T" in text:
        text = text.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y"):
        try:
            parsed = datetime.strptime(text[:10] if fmt != "%Y" else text[:4], fmt)
            return parsed.date()
        except ValueError:
            continue
    return None


def metadata_dict(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def split_country_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            parts.extend(split_country_values(item))
        return parts
    text = clean_text(value)
    if not text:
        return []
    if country_alias_key(text) in COUNTRY_ALIASES:
        return [text]
    pieces = re.split(r"\s*(?:/|;|\||&|\band\b)\s*", text, flags=re.IGNORECASE)
    return [piece for piece in pieces if clean_text(piece)]


def tournament_host_countries(tournament: dict[str, Any] | None) -> dict[str, Any]:
    metadata = metadata_dict(tournament)
    if metadata.get("neutral") or metadata.get("neutral_venue") or metadata.get("is_neutral"):
        return {
            "countries": [],
            "display": clean_text(metadata.get("country")) or "Neutral",
            "neutral": True,
        }

    raw_values: list[Any] = []
    for field in ("host_countries", "host_country", "countries", "country", "country_code"):
        if metadata.get(field):
            raw_values.append(metadata.get(field))
    if tournament:
        for field in ("country", "country_code"):
            if tournament.get(field):
                raw_values.append(tournament.get(field))

    countries: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        for part in split_country_values(raw):
            country = normalize_country(part)
            if not country:
                continue
            key = country_key(country)
            if key not in seen:
                countries.append(country)
                seen.add(key)

    if any(country_key(country) in NEUTRAL_COUNTRY_KEYS for country in countries):
        return {
            "countries": countries,
            "display": "; ".join(countries) if countries else "Neutral",
            "neutral": True,
        }

    return {
        "countries": countries,
        "display": "; ".join(countries) if countries else None,
        "neutral": False,
    }


def classify_home_status(tournament: dict[str, Any] | None, fencer_country: Any) -> dict[str, str | None]:
    host = tournament_host_countries(tournament)
    display = host["display"]
    countries = host["countries"]
    fencer_country_norm = normalize_country(fencer_country)

    if not fencer_country_norm:
        return {
            "home_status": "unknown",
            "classification_reason": "missing_fencer_country",
            "tournament_country": display,
        }
    if host["neutral"]:
        return {
            "home_status": "unknown",
            "classification_reason": "neutral_venue",
            "tournament_country": display,
        }
    if not countries:
        return {
            "home_status": "unknown",
            "classification_reason": "missing_tournament_country",
            "tournament_country": display,
        }
    if len(countries) > 1:
        return {
            "home_status": "unknown",
            "classification_reason": "multi_national_host",
            "tournament_country": display,
        }
    if country_key(countries[0]) == country_key(fencer_country_norm):
        return {
            "home_status": "home",
            "classification_reason": "country_match",
            "tournament_country": countries[0],
        }
    return {
        "home_status": "away",
        "classification_reason": "country_mismatch",
        "tournament_country": countries[0],
    }


def history_item_country(item: dict[str, Any]) -> str | None:
    return normalize_country(
        item.get("country")
        or item.get("country_code")
        or item.get("nationality")
        or item.get("countryLabel")
        or item.get("nationalityLabel")
    )


def history_item_dates(item: dict[str, Any]) -> tuple[date | None, date | None, date | None]:
    return (
        parse_date(item.get("start_date") or item.get("start_time")),
        parse_date(item.get("end_date") or item.get("end_time")),
        parse_date(item.get("point_in_time") or item.get("date")),
    )


def choose_history_country(
    history_rows: list[dict[str, Any]],
    event_date: Any,
    *,
    source: str,
) -> dict[str, str | None] | None:
    if not history_rows:
        return None

    event = parse_date(event_date)
    active: list[str] = []
    point_matches: list[str] = []
    dated_before: list[tuple[date, str]] = []
    undated: list[str] = []

    for item in history_rows:
        country = history_item_country(item)
        if not country:
            continue
        start, end, point = history_item_dates(item)
        if event:
            if start and start <= event and (end is None or event <= end):
                active.append(country)
            elif point and point == event:
                point_matches.append(country)
            elif start and start <= event:
                dated_before.append((start, country))
            elif not start and not end and not point:
                undated.append(country)
        else:
            undated.append(country)

    for countries, reason in (
        (active, "history_range_match"),
        (point_matches, "history_point_match"),
    ):
        distinct = sorted({country_key(country): country for country in countries}.values())
        if len(distinct) == 1:
            return {"country": distinct[0], "source": source, "resolution_reason": reason}
        if len(distinct) > 1:
            return {"country": None, "source": source, "resolution_reason": "ambiguous_history"}

    if dated_before:
        latest_date = max(start for start, _ in dated_before)
        latest = [country for start, country in dated_before if start == latest_date]
        distinct = sorted({country_key(country): country for country in latest}.values())
        if len(distinct) == 1:
            return {"country": distinct[0], "source": source, "resolution_reason": "latest_history_before_event"}
        if len(distinct) > 1:
            return {"country": None, "source": source, "resolution_reason": "ambiguous_history"}

    distinct_undated = sorted({country_key(country): country for country in undated}.values())
    if len(distinct_undated) == 1:
        return {
            "country": distinct_undated[0],
            "source": source,
            "resolution_reason": "single_undated_history",
        }
    if len(distinct_undated) > 1:
        return {"country": None, "source": source, "resolution_reason": "ambiguous_history"}
    return None


def metadata_nationality_history(fencer: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw = metadata_dict(fencer).get("nationality_history")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def resolve_fencer_country_at_event(
    fencer: dict[str, Any] | None,
    history_rows: list[dict[str, Any]],
    event_date: Any,
    *,
    result_country: Any = None,
) -> dict[str, str | None]:
    explicit = choose_history_country(
        history_rows,
        event_date,
        source="fs_fencer_nationality_history",
    )
    if explicit:
        return explicit

    metadata_history = choose_history_country(
        metadata_nationality_history(fencer),
        event_date,
        source="fs_fencers.metadata.nationality_history",
    )
    if metadata_history:
        return metadata_history

    result_country_norm = normalize_country(result_country)
    if result_country_norm:
        return {
            "country": result_country_norm,
            "source": "fs_results",
            "resolution_reason": "result_country",
        }

    fencer_country = normalize_country((fencer or {}).get("country"))
    if fencer_country:
        return {
            "country": fencer_country,
            "source": "fs_fencers.country",
            "resolution_reason": "current_fencer_country_fallback",
        }

    return {"country": None, "source": None, "resolution_reason": "missing_country"}


def result_country(result: dict[str, Any]) -> str | None:
    return normalize_country(result.get("country") or result.get("nationality"))


def result_date(result: dict[str, Any], tournament: dict[str, Any] | None) -> str | None:
    return clean_text(
        result.get("date")
        or (tournament or {}).get("start_date")
        or (tournament or {}).get("end_date")
    )


def result_actual_placement(result: dict[str, Any]) -> int | None:
    return coerce_positive_int(
        result.get("placement") if result.get("placement") is not None else result.get("rank")
    )


def medal_bucket(value: Any, placement: int | None = None) -> str | None:
    text = clean_text(value)
    if text:
        medal = MEDAL_MAP.get(compact_key(text))
        if medal:
            return medal
    if placement == 1:
        return "gold"
    if placement == 2:
        return "silver"
    if placement == 3:
        return "bronze"
    return None


def lookup_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): row
        for row in rows
        if row.get("id") is not None
    }


def histories_by_fencer(history_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in history_rows:
        fencer_id = clean_text(row.get("fencer_id"))
        if fencer_id:
            grouped[fencer_id].append(row)
    return grouped


def row_key(*parts: Any) -> str:
    return ":".join(compact_key(part) or "unknown" for part in parts)


def detail_row_id(result: dict[str, Any]) -> str:
    source_id = clean_text(result.get("id"))
    if source_id:
        return f"result:{source_id}"
    return row_key(
        "result",
        result.get("tournament_id"),
        result.get("fencer_id") or result.get("name"),
        result.get("rank") or result.get("placement"),
    )


def observation_dimension(row: dict[str, Any], *, include_tier: bool = True) -> tuple[Any, ...]:
    values: tuple[Any, ...] = (
        row.get("fencer_id") or row.get("fencer_name") or row.get("id"),
        row.get("weapon"),
        row.get("gender"),
        row.get("category"),
    )
    if include_tier:
        return (*values, row.get("competition_tier"))
    return values


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def round_metric(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def baseline_maps(preliminary_rows: list[dict[str, Any]]) -> list[dict[tuple[Any, ...], list[float]]]:
    fencer_tier_away: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    fencer_no_tier_away: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    fencer_all_away: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    group_tier_away: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    group_tier_all: dict[tuple[Any, ...], list[float]] = defaultdict(list)

    for row in preliminary_rows:
        placement = float(row["actual_placement"])
        group_key = (
            row.get("weapon"),
            row.get("gender"),
            row.get("category"),
            row.get("competition_tier"),
        )
        group_tier_all[group_key].append(placement)
        if row["home_status"] == "away":
            fencer_tier_away[observation_dimension(row, include_tier=True)].append(placement)
            fencer_no_tier_away[observation_dimension(row, include_tier=False)].append(placement)
            fencer_all_away[(row.get("fencer_id") or row.get("fencer_name") or row.get("id"),)].append(placement)
            group_tier_away[group_key].append(placement)

    return [
        fencer_tier_away,
        fencer_no_tier_away,
        fencer_all_away,
        group_tier_away,
        group_tier_all,
    ]


def expected_baseline(row: dict[str, Any], maps: list[dict[tuple[Any, ...], list[float]]]) -> float | None:
    keys = [
        observation_dimension(row, include_tier=True),
        observation_dimension(row, include_tier=False),
        (row.get("fencer_id") or row.get("fencer_name") or row.get("id"),),
        (row.get("weapon"), row.get("gender"), row.get("category"), row.get("competition_tier")),
        (row.get("weapon"), row.get("gender"), row.get("category"), row.get("competition_tier")),
    ]
    for values_by_key, key in zip(maps, keys, strict=False):
        baseline = average(values_by_key.get(key, []))
        if baseline is not None:
            return baseline
    return None


def build_home_advantage_rows(
    results: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    nationality_histories: list[dict[str, Any]],
    *,
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    fencers_by_id = lookup_by_id(fencers)
    tournaments_by_id = lookup_by_id(tournaments)
    history_by_fencer = histories_by_fencer(nationality_histories)
    timestamp = updated_at or datetime.now(timezone.utc).isoformat()

    preliminary_rows: list[dict[str, Any]] = []
    skipped = 0
    for result in results:
        tournament_id = clean_text(result.get("tournament_id"))
        tournament = tournaments_by_id.get(str(tournament_id)) if tournament_id else None
        fencer_id = clean_text(result.get("fencer_id"))
        fencer = fencers_by_id.get(fencer_id) if fencer_id else None
        placement = result_actual_placement(result)
        if not tournament_id or placement is None:
            skipped += 1
            continue

        event_date = result_date(result, tournament)
        country_resolution = resolve_fencer_country_at_event(
            fencer,
            history_by_fencer.get(fencer_id or "", []),
            event_date,
            result_country=result_country(result),
        )
        fencer_country = normalize_country(country_resolution.get("country"))
        classification = classify_home_status(tournament, fencer_country)
        weapon = normalize_weapon(result.get("weapon") or (tournament or {}).get("weapon"))
        gender = normalize_gender(result.get("gender") or (tournament or {}).get("gender"))
        category = normalize_category(result.get("category") or (tournament or {}).get("category"))
        tier = normalize_tier(tournament)
        medal = medal_bucket(result.get("medal"), placement)

        row = {
            "id": detail_row_id(result),
            "source_result_id": clean_text(result.get("id")),
            "tournament_id": tournament_id,
            "fencer_id": fencer_id,
            "fencer_name": clean_text(result.get("name") or (fencer or {}).get("name")),
            "country": fencer_country or UNKNOWN_COUNTRY,
            "fencer_country": fencer_country,
            "tournament_country": classification["tournament_country"],
            "home_status": classification["home_status"],
            "classification_reason": classification["classification_reason"],
            "country_resolution_source": country_resolution.get("source"),
            "country_resolution_reason": country_resolution.get("resolution_reason"),
            "weapon": weapon,
            "gender": gender,
            "category": category,
            "competition_tier": tier,
            "expected_placement": None,
            "actual_placement": placement,
            "actual_medal": medal,
            "placement_delta": None,
            "metadata": {
                "event_date": event_date,
                "result_country": result_country(result),
                "baseline_source": "same_fencer_away_average",
            },
            "updated_at": timestamp,
        }
        preliminary_rows.append(row)

    maps = baseline_maps(preliminary_rows)
    rows: list[dict[str, Any]] = []
    for row in sorted(preliminary_rows, key=lambda item: item["id"]):
        baseline = expected_baseline(row, maps)
        delta = baseline - float(row["actual_placement"]) if baseline is not None else None
        row = dict(row)
        row["expected_placement"] = round_metric(baseline)
        row["placement_delta"] = round_metric(delta)
        rows.append(row)
    return rows, skipped


def non_null_average(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return round_metric(average(values))


def build_home_advantage_aggregate_rows(
    detail_rows: list[dict[str, Any]],
    *,
    updated_at: str | None = None,
) -> list[dict[str, Any]]:
    timestamp = updated_at or datetime.now(timezone.utc).isoformat()
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in detail_rows:
        grouped[
            (
                row.get("country") or UNKNOWN_COUNTRY,
                row.get("weapon"),
                row.get("gender"),
                row.get("category"),
                row.get("competition_tier"),
                row.get("home_status"),
            )
        ].append(row)

    aggregate_rows: list[dict[str, Any]] = []
    for (country, weapon, gender, category, tier, status), rows in sorted(
        grouped.items(), key=lambda item: tuple(v or "" for v in item[0])
    ):
        medals = [row.get("actual_medal") for row in rows]
        aggregate_rows.append(
            {
                "id": row_key("home_advantage", country, weapon, gender, category, tier, status),
                "country": country or UNKNOWN_COUNTRY,
                "weapon": weapon,
                "gender": gender,
                "category": category,
                "competition_tier": tier,
                "home_status": status,
                "results_count": len(rows),
                "avg_expected_placement": non_null_average(rows, "expected_placement"),
                "avg_actual_placement": non_null_average(rows, "actual_placement"),
                "avg_placement_delta": non_null_average(rows, "placement_delta"),
                "medal_count": sum(1 for medal in medals if medal),
                "gold_count": sum(1 for medal in medals if medal == "gold"),
                "silver_count": sum(1 for medal in medals if medal == "silver"),
                "bronze_count": sum(1 for medal in medals if medal == "bronze"),
                "unknown_count": sum(1 for row in rows if row.get("home_status") == "unknown"),
                "updated_at": timestamp,
            }
        )
    return aggregate_rows


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


def fetch_with_fallbacks(
    client,
    table: str,
    select_options: tuple[str, ...],
    *,
    page_size: int,
) -> list[dict[str, Any]]:
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


def fetch_optional(client, table: str, columns: str, *, page_size: int) -> list[dict[str, Any]]:
    try:
        return fetch_all(client, table, columns, page_size=page_size)
    except Exception as exc:
        print(f"  Optional table {table} unavailable: {exc}")
        return []


def load_inputs(client, *, page_size: int) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
    fencers = fetch_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
    tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
    history_rows = fetch_optional(
        client,
        "fs_fencer_nationality_history",
        HISTORY_SELECT,
        page_size=page_size,
    )
    return results, fencers, tournaments, history_rows


def batch_upsert(
    client,
    table: str,
    rows: list[dict[str, Any]],
    *,
    batch_size: int,
) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table(table).upsert(batch, on_conflict="id").execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  {table} upsert batch {index // batch_size} failed: {exc}")
    return written, failed


def compute_home_advantage(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    updated_at: str | None = None,
) -> dict[str, int]:
    client = client or get_supabase_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    get_state(SOURCE, "last_run") if update_state else None
    timestamp = updated_at or datetime.now(timezone.utc).isoformat()

    try:
        results, fencers, tournaments, history_rows = load_inputs(client, page_size=page_size)
        detail_rows, skipped = build_home_advantage_rows(
            results,
            fencers,
            tournaments,
            history_rows,
            updated_at=timestamp,
        )
        aggregate_rows = build_home_advantage_aggregate_rows(detail_rows, updated_at=timestamp)

        detail_written, detail_failed = batch_upsert(
            client,
            "fs_home_advantage_results",
            detail_rows,
            batch_size=batch_size,
        ) if detail_rows else (0, 0)
        aggregate_written, aggregate_failed = batch_upsert(
            client,
            "fs_home_advantage_aggregates",
            aggregate_rows,
            batch_size=batch_size,
        ) if aggregate_rows else (0, 0)

        summary = {
            "results_read": len(results),
            "fencers_read": len(fencers),
            "tournaments_read": len(tournaments),
            "nationality_history_read": len(history_rows),
            "detail_rows": len(detail_rows),
            "aggregate_rows": len(aggregate_rows),
            "written": detail_written + aggregate_written,
            "failed": detail_failed + aggregate_failed,
            "skipped": skipped,
        }
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": timestamp, **summary})
        if run_log:
            run_log.complete(
                written=summary["written"],
                failed=summary["failed"],
                skipped=summary["skipped"],
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Home advantage computation starting - {datetime.now(timezone.utc).isoformat()}")
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous home advantage state: {previous_state}")
    summary = compute_home_advantage()
    print(
        "Home advantage computation complete - "
        f"{summary['detail_rows']} detail rows, "
        f"{summary['aggregate_rows']} aggregate rows, "
        f"{summary['written']} written, {summary['failed']} failed, "
        f"{summary['skipped']} skipped"
    )


if __name__ == "__main__":
    main()

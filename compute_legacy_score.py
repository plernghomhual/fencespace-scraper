from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state

try:
    from supabase import create_client
except Exception:  # pragma: no cover - surfaced when a live client is requested.
    create_client = None


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_legacy_score"

RESULT_SELECTS = (
    "id,tournament_id,fencer_id,rank,placement,medal,event_type,event_kind,is_team,team_id,team_name,weapon,category,season,date",
    "id,tournament_id,fencer_id,rank,placement,medal,event_type,is_team,team_id,team_name",
    "id,tournament_id,fencer_id,rank,placement,medal",
)
TOURNAMENT_SELECTS = (
    "id,tier,type,competition_type,competition_tier,season,start_date,end_date,weapon,gender,category",
    "id,tier,type,competition_type,season,start_date,end_date,weapon,gender,category",
    "id,type,season,start_date,end_date,weapon,gender,category",
)
IDENTITY_SELECTS = (
    "id,canonical_name,country,fs_fencer_row_ids",
    "id,canonical_name,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
)

TIER_ALIASES = {
    "OG": "Olympics",
    "OLYMPICS": "Olympics",
    "OLYMPICGAMES": "Olympics",
    "WCH": "Worlds",
    "CHM": "Worlds",
    "WORLD": "Worlds",
    "WORLDS": "Worlds",
    "WORLDCHAMPIONSHIP": "Worlds",
    "WORLDCHAMPIONSHIPS": "Worlds",
    "GP": "GP",
    "GRANDPRIX": "GP",
    "WC": "WC",
    "WORLDCUP": "WC",
    "CC": "Continental",
    "ZCH": "Continental",
    "CONTINENTAL": "Continental",
    "CONTINENTALCHAMPIONSHIP": "Continental",
    "CONTINENTALCHAMPIONSHIPS": "Continental",
    "ZONAL": "Continental",
    "ZONALCHAMPIONSHIP": "Continental",
    "ZONALCHAMPIONSHIPS": "Continental",
    "SAT": "Satellite",
    "SATELLITE": "Satellite",
    "NAT": "National",
    "NATIONAL": "National",
    "NATIONALCHAMPIONSHIP": "National",
    "NATIONALCHAMPIONSHIPS": "National",
    "NCAA": "National",
    "NCAACHAMPIONSHIP": "National",
}
TIER_WEIGHTS = {
    "Olympics": 5.0,
    "Worlds": 5.0,
    "GP": 4.0,
    "WC": 3.0,
    "Continental": 2.5,
    "Satellite": 1.5,
    "National": 1.0,
    "Unclassified": 1.0,
}
MEDAL_POINTS = {"gold": 10.0, "silver": 8.0, "bronze": 5.0}
PLACEMENT_POINTS = {1: 4.0, 2: 3.0, 3: 2.0}
TEAM_MULTIPLIER = 0.6

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
TEAM_VALUES = {"team", "teams", "relay"}
INDIVIDUAL_VALUES = {"individual", "ind", "solo"}


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    if create_client is None:
        raise RuntimeError("supabase package is required.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def compact_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", (clean_text(value) or "").casefold()).upper()


def to_int(value: Any) -> int | None:
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
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = clean_text(value)
    if not text:
        return None

    short_range = re.match(r"^(\d{4})\s*[-/]\s*(\d{2})$", text)
    if short_range:
        start = int(short_range.group(1))
        end = (start // 100) * 100 + int(short_range.group(2))
        if end < start:
            end += 100
        return end

    years = [int(part) for part in re.findall(r"\d{4}", text)]
    if years:
        return years[-1]

    try:
        return int(float(text))
    except ValueError:
        return None


def medal_bucket(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return MEDAL_MAP.get(compact_key(text).lower())


def tier_from_tournament(tournament: dict[str, Any] | None) -> str:
    if not tournament:
        return "Unclassified"
    for field in ("tier", "competition_tier", "competition_type", "type"):
        tier = TIER_ALIASES.get(compact_key(tournament.get(field)))
        if tier:
            return tier
    return "Unclassified"


def tier_weight(tournament: dict[str, Any] | None) -> float:
    return TIER_WEIGHTS[tier_from_tournament(tournament)]


def event_kind(*sources: dict[str, Any] | None) -> str:
    for source in sources:
        if not source:
            continue
        if source.get("is_team") is True:
            return "team"
        if source.get("is_team") is False:
            return "individual"
        for field in ("event_type", "event_kind", "competition_format", "format", "type"):
            key = compact_key(source.get(field)).lower()
            if key in TEAM_VALUES:
                return "team"
            if key in INDIVIDUAL_VALUES:
                return "individual"
    return "individual"


def event_multiplier(kind: str) -> float:
    return TEAM_MULTIPLIER if kind == "team" else 1.0


def placement_base_points(rank: int | None) -> float:
    if rank is None:
        return 0.0
    if rank in PLACEMENT_POINTS:
        return PLACEMENT_POINTS[rank]
    if 4 <= rank <= 8:
        return 1.0
    return 0.0


def score_points(base_points: float, weight: float, multiplier: float) -> float:
    return round(base_points * weight * multiplier, 2)


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


def build_identity_index(identity_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in identity_rows:
        identity_id = clean_text(row.get("id"))
        if not identity_id:
            continue
        for member in parse_identity_members(row.get("fs_fencer_row_ids")):
            index[member] = row
    return index


def tournament_lookup(tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {str(row["id"]): row for row in tournaments if row.get("id") is not None}


def result_rank(result: dict[str, Any]) -> int | None:
    return to_int(result.get("rank") if result.get("rank") is not None else result.get("placement"))


def result_season(result: dict[str, Any], tournament: dict[str, Any] | None) -> int | None:
    for source in (tournament, result):
        if not source:
            continue
        season = season_to_int(source.get("season"))
        if season is not None:
            return season
    return None


def result_dedupe_key(
    identity_id: str,
    result: dict[str, Any],
    tournament: dict[str, Any] | None,
    index: int,
) -> tuple[Any, ...]:
    tournament_id = clean_text(result.get("tournament_id"))
    competition_id = tournament_id or clean_text(result.get("source_id")) or clean_text(result.get("id")) or f"result:{index}"
    kind = event_kind(result, tournament)
    team_key = None
    if kind == "team":
        team_key = clean_text(result.get("team_id")) or clean_text(result.get("team_name")) or clean_text(result.get("country"))
    weapon = clean_text(result.get("weapon")) or clean_text((tournament or {}).get("weapon"))
    category = clean_text(result.get("category")) or clean_text((tournament or {}).get("category"))
    return (
        identity_id,
        competition_id,
        kind,
        team_key,
        weapon,
        category,
        result_rank(result),
        medal_bucket(result.get("medal")),
    )


def empty_medal_counts() -> dict[str, Any]:
    return {
        "gold": 0,
        "silver": 0,
        "bronze": 0,
        "individual": 0,
        "team": 0,
        "by_tier": {},
    }


def ensure_tier_medal_counts(counts: dict[str, Any], tier: str) -> dict[str, int]:
    by_tier = counts["by_tier"]
    if tier not in by_tier:
        by_tier[tier] = {"gold": 0, "silver": 0, "bronze": 0}
    return by_tier[tier]


def new_stat(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "identity_id": clean_text(identity.get("id")),
        "canonical_name": clean_text(identity.get("canonical_name")),
        "country": clean_text(identity.get("country")),
        "medal_points": 0.0,
        "result_points": 0.0,
        "competition_keys": set(),
        "result_count": 0,
        "medal_counts": empty_medal_counts(),
        "tier_weights": {},
        "seasons": set(),
        "events": [],
        "duplicate_results_skipped": 0,
    }


def build_legacy_score_rows(
    results: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    identities: list[dict[str, Any]],
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    now = updated_at or datetime.now(timezone.utc).isoformat()
    tournaments_by_id = tournament_lookup(tournaments)
    identities_by_member = build_identity_index(identities)
    stats: dict[str, dict[str, Any]] = {}
    seen: set[tuple[Any, ...]] = set()
    skipped = 0

    for index, result in enumerate(results):
        fencer_id = clean_text(result.get("fencer_id"))
        identity = identities_by_member.get(fencer_id or "")
        if not identity:
            skipped += 1
            continue

        identity_id = clean_text(identity.get("id"))
        if not identity_id:
            skipped += 1
            continue

        tournament_id = clean_text(result.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id) if tournament_id else None
        stat = stats.setdefault(identity_id, new_stat(identity))
        dedupe_key = result_dedupe_key(identity_id, result, tournament, index)
        if dedupe_key in seen:
            stat["duplicate_results_skipped"] += 1
            continue
        seen.add(dedupe_key)

        tier = tier_from_tournament(tournament)
        weight = tier_weight(tournament)
        kind = event_kind(result, tournament)
        multiplier = event_multiplier(kind)
        rank = result_rank(result)
        medal = medal_bucket(result.get("medal"))
        medal_points = score_points(MEDAL_POINTS.get(medal, 0.0), weight, multiplier)
        result_points = score_points(placement_base_points(rank), weight, multiplier)
        total_points = round(medal_points + result_points, 2)
        if total_points <= 0:
            continue

        stat["medal_points"] = round(stat["medal_points"] + medal_points, 2)
        stat["result_points"] = round(stat["result_points"] + result_points, 2)
        stat["result_count"] += 1
        stat["tier_weights"][tier] = weight
        stat["competition_keys"].add(dedupe_key[1])

        season = result_season(result, tournament)
        if season is not None:
            stat["seasons"].add(season)

        if medal:
            medal_counts = stat["medal_counts"]
            medal_counts[medal] += 1
            medal_counts[kind] += 1
            ensure_tier_medal_counts(medal_counts, tier)[medal] += 1

        stat["events"].append(
            {
                "result_id": clean_text(result.get("id")),
                "tournament_id": tournament_id,
                "tier": tier,
                "tier_weight": weight,
                "event_kind": kind,
                "rank": rank,
                "medal": medal,
                "medal_points": medal_points,
                "result_points": result_points,
                "total_points": total_points,
            }
        )

    rows: list[dict[str, Any]] = []
    for identity_id in sorted(stats):
        stat = stats[identity_id]
        medal_counts = stat["medal_counts"]
        seasons = sorted(stat["seasons"])
        first_season = seasons[0] if seasons else None
        last_season = seasons[-1] if seasons else None
        active_span_years = (
            last_season - first_season + 1
            if first_season is not None and last_season is not None
            else None
        )
        medal_points = round(stat["medal_points"], 2)
        result_points = round(stat["result_points"], 2)
        legacy_score = round(medal_points + result_points, 2)
        tier_weights = dict(sorted(stat["tier_weights"].items()))
        score_components = {
            "medal_points": medal_points,
            "result_points": result_points,
            "legacy_score": legacy_score,
            "tier_weights": tier_weights,
            "team_multiplier": TEAM_MULTIPLIER,
            "duplicate_results_skipped": stat["duplicate_results_skipped"],
            "events": stat["events"],
        }
        rows.append(
            {
                "identity_id": identity_id,
                "canonical_name": stat["canonical_name"],
                "country": stat["country"],
                "legacy_score": legacy_score,
                "medal_points": medal_points,
                "result_points": result_points,
                "competition_count": len(stat["competition_keys"]),
                "result_count": stat["result_count"],
                "gold_medals": medal_counts["gold"],
                "silver_medals": medal_counts["silver"],
                "bronze_medals": medal_counts["bronze"],
                "individual_medals": medal_counts["individual"],
                "team_medals": medal_counts["team"],
                "score_components": score_components,
                "medal_counts": {
                    "gold": medal_counts["gold"],
                    "silver": medal_counts["silver"],
                    "bronze": medal_counts["bronze"],
                    "individual": medal_counts["individual"],
                    "team": medal_counts["team"],
                    "by_tier": {
                        tier: counts
                        for tier, counts in sorted(medal_counts["by_tier"].items())
                    },
                },
                "tier_weights": tier_weights,
                "first_season": first_season,
                "last_season": last_season,
                "active_span_years": active_span_years,
                "updated_at": now,
            }
        )
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
    selects: tuple[str, ...],
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    last_error = None
    for columns in selects:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Unable to fetch {table}") from last_error


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


def compute_legacy_scores(
    client=None,
    *,
    page_size: int = PAGE_SIZE,
    updated_at: str | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
        identities = fetch_with_fallbacks(client, "fs_fencer_identities", IDENTITY_SELECTS, page_size=page_size)
        rows, skipped = build_legacy_score_rows(
            results,
            tournaments,
            identities,
            updated_at=updated_at,
        )
        written = batch_upsert(
            client,
            "fs_fencer_legacy_scores",
            rows,
            on_conflict="identity_id",
        ) if rows else 0
        summary = {
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "identity_rows": len(identities),
            "legacy_rows": len(rows),
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
    print(f"Legacy score computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_legacy_scores()
    print(
        "Legacy score computation complete - "
        f"{summary['legacy_rows']} rows built, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} rows skipped"
    )


if __name__ == "__main__":
    main()

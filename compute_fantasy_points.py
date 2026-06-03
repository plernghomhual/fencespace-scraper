import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_fantasy_points"
FANTASY_CONFLICT_COLUMNS = "fencer_id,tournament_id,season,rules_version"

PLACEMENT_WEIGHTS = {
    "1": 32,
    "2": 24,
    "3": 21,
    "4": 16,
    "5-8": 8,
    "9-16": 6,
    "17-32": 3,
    "33-64": 1,
}

MEDAL_WEIGHTS = {"gold": 20, "silver": 14, "bronze": 10}
PENALTY_WEIGHTS = {"dns": -5, "dq": -10}
UPSET_RULE = {"base": 8, "min_rank_gap": 10}
TIER_MULTIPLIERS = {
    "olympics": 2.0,
    "worlds": 1.75,
    "gp": 1.35,
    "wc": 1.25,
    "continental": 1.2,
    "national": 1.0,
    "domestic": 1.0,
    "unknown": 1.0,
}

FANTASY_SCORING_RULES = {
    "rules_version": "2026.06.v1",
    "participation": 2,
    "placement": PLACEMENT_WEIGHTS,
    "medal": MEDAL_WEIGHTS,
    "upset": UPSET_RULE,
    "penalties": PENALTY_WEIGHTS,
    "tier_multipliers": TIER_MULTIPLIERS,
    "team_event_multiplier": 0.5,
    "documented_weights": {
        "participation": 2,
        "placement": PLACEMENT_WEIGHTS,
        "medal": MEDAL_WEIGHTS,
        "upset": UPSET_RULE,
        "penalties": PENALTY_WEIGHTS,
        "tier_multipliers": TIER_MULTIPLIERS,
        "team_event_multiplier": 0.5,
    },
}

RESULT_SELECTS = (
    "id,tournament_id,fencer_id,rank,placement,place,medal,status,result_status,dns,dq,is_team,team_event,season,metadata",
    "id,tournament_id,fencer_id,rank,medal,status,result_status,season,metadata",
    "id,tournament_id,fencer_id,rank,medal,metadata",
    "id,tournament_id,fencer_id,rank,medal",
)
BOUT_SELECTS = (
    "id,tournament_id,fencer_a,fencer_b,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,round,is_bye,bye,status,metadata",
    "id,tournament_id,fencer_a,fencer_b,winner_id,score_a,score_b,round",
    "id,tournament_id,fencer_a_id,fencer_b_id,winner_id,score_a,score_b,round",
)
TOURNAMENT_SELECTS = (
    "id,season,type,tier,competition_type,competition_tier,name,category,weapon,is_team,team_event,metadata",
    "id,season,type,tier,competition_type,competition_tier,name,category,is_team,team_event,metadata",
    "id,season,type,name,category,weapon,metadata",
    "id,season,type,name",
)
FENCER_SELECTS = ("id,world_rank", "id")
IDENTITY_SELECTS = (
    "canonical_id,fs_fencer_row_ids",
    "id,canonical_id,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
    "canonical_id,fencer_ids",
)

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
    "CONTINENTAL": "Continental",
    "ZONAL": "Continental",
    "NAT": "National",
    "NATIONAL": "National",
    "DOMESTIC": "Domestic",
}

TIER_TEXT_PATTERNS = (
    ("Olympics", ("olympic games", "olympics")),
    ("Worlds", ("world championship", "world championships", "worlds")),
    ("GP", ("grand prix",)),
    ("WC", ("world cup",)),
    (
        "Continental",
        (
            "continental championship",
            "continental championships",
            "zonal championship",
            "european championship",
            "asian championship",
            "panamerican championship",
            "african championship",
        ),
    ),
    ("National", ("national championship", "national championships")),
)

SKIP_KEYS = (
    "results_missing_required_fields",
    "duplicate_results",
    "bouts_missing_required_fields",
    "bouts_missing_scores",
    "bouts_byes",
    "bouts_missing_ranks",
    "bouts_non_upsets",
    "bouts_status_skipped",
    "bouts_duplicate",
)


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


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group(0)) if match else None


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = clean_text(value)
    return bool(text and text.casefold() in {"1", "true", "t", "yes", "y"})


def round_points(value: Any) -> float:
    decimal_value = Decimal(str(value or 0))
    return float(decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def normalize_medal(value: Any) -> str | None:
    key = compact_key(value)
    return {
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
    }.get(key)


def normalize_status(row: dict[str, Any]) -> str | None:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    if truthy(row.get("dq")) or truthy(metadata.get("dq")):
        return "dq"
    if truthy(row.get("dns")) or truthy(metadata.get("dns")):
        return "dns"

    values = [
        row.get("status"),
        row.get("result_status"),
        metadata.get("status"),
        metadata.get("result_status"),
        row.get("rank"),
        row.get("placement"),
        row.get("place"),
    ]
    for value in values:
        key = compact_key(value)
        if key in {"dq", "dsq", "disqualified", "disqualification"}:
            return "dq"
        if key in {"dns", "didnotstart"}:
            return "dns"
    return None


def normalize_season(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = clean_text(value)
    if not text:
        return None
    if re.match(r"^\d{4}$", text):
        return int(text)
    match = re.search(r"(20\d{2})", text)
    return int(match.group(1)) if match else None


def normalize_tier(tournament: dict[str, Any] | None) -> str:
    if not tournament:
        return "Unknown"
    for field in ("tier", "competition_tier", "type", "competition_type"):
        tier = TYPE_TIERS.get(compact_key(tournament.get(field)).upper())
        if tier:
            return tier
    text = " ".join(
        clean_text(tournament.get(field)) or ""
        for field in ("tier", "competition_tier", "type", "competition_type", "name", "category")
    ).casefold()
    for tier, patterns in TIER_TEXT_PATTERNS:
        if any(pattern in text for pattern in patterns):
            return tier
    return "Unknown"


def tier_multiplier(tier: str, rules: dict[str, Any]) -> float:
    return float(rules.get("tier_multipliers", {}).get(tier.casefold(), 1.0))


def is_team_event(result: dict[str, Any], tournament: dict[str, Any] | None) -> bool:
    values = [result.get("is_team"), result.get("team_event")]
    if tournament:
        values.extend([tournament.get("is_team"), tournament.get("team_event")])
        values.extend([tournament.get("name"), tournament.get("category")])
    for value in values:
        if truthy(value):
            return True
        text = clean_text(value)
        if text and "team" in text.casefold():
            return True
    return False


def placement_points(rank: int | None, rules: dict[str, Any]) -> int:
    if rank is None:
        return 0
    placement = rules.get("placement", {})
    for key, points in placement.items():
        if "-" in str(key):
            start_text, end_text = str(key).split("-", 1)
            start = to_int(start_text)
            end = to_int(end_text)
            if start is not None and end is not None and start <= rank <= end:
                return int(points)
        elif to_int(key) == rank:
            return int(points)
    return 0


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
        members = parse_identity_members(
            row.get("fs_fencer_row_ids") or row.get("fencer_ids") or row.get("source_fencer_ids")
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


def canonical_fencer_id(fencer_id: Any, identity_map: dict[str, str] | None) -> str | None:
    text = clean_text(fencer_id)
    if not text:
        return None
    return (identity_map or {}).get(text, text)


def result_fencer_id(result: dict[str, Any], identity_map: dict[str, str]) -> str | None:
    return canonical_fencer_id(
        result.get("fencer_id")
        or result.get("fencer")
        or result.get("fencer_uuid")
        or result.get("athlete_id"),
        identity_map,
    )


def result_rank(result: dict[str, Any]) -> int | None:
    if normalize_status(result):
        return None
    for field in ("rank", "placement", "place"):
        rank = to_int(result.get(field))
        if rank is not None and rank > 0:
            return rank
    return None


def result_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    status = item["status"]
    if status == "dq":
        return (3, 0, 0)
    if status == "dns":
        return (2, 0, 0)
    medal_score = {"gold": 3, "silver": 2, "bronze": 1}.get(item["medal_type"], 0)
    rank_score = -(item["rank"] or 999999)
    return (0, medal_score, rank_score)


def empty_skips() -> dict[str, int]:
    return {key: 0 for key in SKIP_KEYS}


def base_components(tier: str, tier_mult: float, team_mult: float, rank: int | None, medal_type: str | None, status: str | None) -> dict[str, Any]:
    return {
        "participation": 0.0,
        "placement": 0.0,
        "medal": 0.0,
        "upsets": 0.0,
        "penalties": 0.0,
        "tier": tier,
        "tier_multiplier": round_points(tier_mult),
        "team_event_multiplier": round_points(team_mult),
        "placement_rank": rank,
        "medal_type": medal_type,
        "status": status,
        "upset_count": 0,
    }


def total_from_components(components: dict[str, Any]) -> float:
    return round_points(
        components["participation"]
        + components["placement"]
        + components["medal"]
        + components["upsets"]
        + components["penalties"]
    )


def score_result_components(
    result: dict[str, Any],
    tournament: dict[str, Any] | None,
    rules: dict[str, Any],
) -> dict[str, Any]:
    tier = normalize_tier(tournament)
    tier_mult = tier_multiplier(tier, rules)
    team_mult = float(rules.get("team_event_multiplier", 1.0)) if is_team_event(result, tournament) else 1.0
    status = normalize_status(result)
    rank = result_rank(result)
    medal_type = normalize_medal(result.get("medal"))
    components = base_components(tier, tier_mult, team_mult, rank, medal_type, status)

    if status in PENALTY_WEIGHTS:
        components["penalties"] = round_points(rules.get("penalties", {}).get(status, 0))
        return components

    scale = Decimal(str(tier_mult)) * Decimal(str(team_mult))
    participation = Decimal(str(rules.get("participation", 0))) * scale
    placement = Decimal(str(placement_points(rank, rules))) * scale
    medal = Decimal(str(rules.get("medal", {}).get(medal_type, 0))) * scale

    components["participation"] = round_points(participation)
    components["placement"] = round_points(placement)
    components["medal"] = round_points(medal)
    return components


def make_fantasy_row(
    fencer_id: str,
    tournament_id: str,
    season: int,
    components: dict[str, Any],
    rules: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    return {
        "fencer_id": fencer_id,
        "tournament_id": tournament_id,
        "season": season,
        "components": components,
        "total_points": total_from_components(components),
        "rules_version": rules["rules_version"],
        "updated_at": updated_at,
    }


def build_fencer_rank_map(
    fencers: list[dict[str, Any]], identity_map: dict[str, str]
) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for fencer in fencers:
        row_id = clean_text(fencer.get("id"))
        rank = to_int(fencer.get("world_rank"))
        if not row_id or rank is None or rank <= 0:
            continue
        ranks[row_id] = rank
        canonical = canonical_fencer_id(row_id, identity_map)
        if canonical and (canonical not in ranks or rank < ranks[canonical]):
            ranks[canonical] = rank
    return ranks


def is_bye_bout(bout: dict[str, Any]) -> bool:
    if truthy(bout.get("is_bye")) or truthy(bout.get("bye")):
        return True
    metadata = bout.get("metadata") if isinstance(bout.get("metadata"), dict) else {}
    if truthy(metadata.get("is_bye")) or truthy(metadata.get("bye")):
        return True
    text = " ".join(clean_text(bout.get(field)) or "" for field in ("round", "status"))
    return "bye" in text.casefold()


def bout_fencer_ids(bout: dict[str, Any], identity_map: dict[str, str]) -> tuple[str | None, str | None, str | None, str | None]:
    raw_a = clean_text(bout.get("fencer_a_id") or bout.get("fencer_a"))
    raw_b = clean_text(bout.get("fencer_b_id") or bout.get("fencer_b"))
    return raw_a, raw_b, canonical_fencer_id(raw_a, identity_map), canonical_fencer_id(raw_b, identity_map)


def find_winner(
    bout: dict[str, Any],
    raw_a: str,
    raw_b: str,
    canon_a: str,
    canon_b: str,
    score_a: int,
    score_b: int,
    identity_map: dict[str, str],
) -> tuple[str | None, str | None]:
    winner_raw = clean_text(bout.get("winner_id") or bout.get("winner") or bout.get("winner_fencer_id"))
    winner = canonical_fencer_id(winner_raw, identity_map) if winner_raw else None
    if not winner and score_a != score_b:
        winner = canon_a if score_a > score_b else canon_b
    if winner == canon_a or winner_raw == raw_a:
        return canon_a, canon_b
    if winner == canon_b or winner_raw == raw_b:
        return canon_b, canon_a
    return None, None


def add_upset_points(
    rows_by_key: dict[tuple[str, str, int], dict[str, Any]],
    bouts: list[dict[str, Any]],
    tournaments_by_id: dict[str, dict[str, Any]],
    fencer_ranks: dict[str, int],
    identity_map: dict[str, str],
    result_statuses: dict[tuple[str, str, int], str | None],
    rules: dict[str, Any],
    updated_at: str,
    skips: dict[str, int],
) -> None:
    seen_bouts: set[tuple[Any, ...]] = set()
    for bout in bouts:
        tournament_id = clean_text(bout.get("tournament_id"))
        raw_a, raw_b, canon_a, canon_b = bout_fencer_ids(bout, identity_map)
        if not tournament_id or not raw_a or not raw_b or not canon_a or not canon_b or canon_a == canon_b:
            skips["bouts_missing_required_fields"] += 1
            continue

        bout_id = clean_text(bout.get("id"))
        if bout_id:
            bout_key = ("id", bout_id)
        else:
            pair = tuple(sorted((canon_a, canon_b)))
            if pair[0] == canon_a:
                ordered_scores = (clean_text(bout.get("score_a")), clean_text(bout.get("score_b")))
            else:
                ordered_scores = (clean_text(bout.get("score_b")), clean_text(bout.get("score_a")))
            bout_key = (
                "fallback",
                tournament_id,
                pair[0],
                pair[1],
                clean_text(bout.get("round")),
                ordered_scores[0],
                ordered_scores[1],
            )
        if bout_key in seen_bouts:
            skips["bouts_duplicate"] += 1
            continue
        seen_bouts.add(bout_key)

        if is_bye_bout(bout):
            skips["bouts_byes"] += 1
            continue

        score_a = to_int(bout.get("score_a"))
        score_b = to_int(bout.get("score_b"))
        if score_a is None or score_b is None:
            skips["bouts_missing_scores"] += 1
            continue

        tournament = tournaments_by_id.get(tournament_id)
        season = normalize_season((tournament or {}).get("season"))
        if season is None:
            skips["bouts_missing_required_fields"] += 1
            continue

        winner, loser = find_winner(bout, raw_a, raw_b, canon_a, canon_b, score_a, score_b, identity_map)
        if not winner or not loser:
            skips["bouts_non_upsets"] += 1
            continue

        if result_statuses.get((winner, tournament_id, season)) or result_statuses.get((loser, tournament_id, season)):
            skips["bouts_status_skipped"] += 1
            continue

        winner_rank = fencer_ranks.get(winner)
        loser_rank = fencer_ranks.get(loser)
        if winner_rank is None or loser_rank is None:
            skips["bouts_missing_ranks"] += 1
            continue
        if winner_rank - loser_rank < int(rules.get("upset", {}).get("min_rank_gap", 10)):
            skips["bouts_non_upsets"] += 1
            continue

        tier = normalize_tier(tournament)
        tier_mult = tier_multiplier(tier, rules)
        team_mult = float(rules.get("team_event_multiplier", 1.0)) if is_team_event({}, tournament) else 1.0
        points = round_points(Decimal(str(rules.get("upset", {}).get("base", 0))) * Decimal(str(tier_mult)) * Decimal(str(team_mult)))
        key = (winner, tournament_id, season)
        if key not in rows_by_key:
            components = base_components(tier, tier_mult, team_mult, None, None, None)
            rows_by_key[key] = make_fantasy_row(winner, tournament_id, season, components, rules, updated_at)
        components = rows_by_key[key]["components"]
        components["upsets"] = round_points(components["upsets"] + points)
        components["upset_count"] += 1
        rows_by_key[key]["total_points"] = total_from_components(components)


def tournament_lookup(tournaments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in tournaments if row.get("id") is not None}


def build_fantasy_rows(
    results: list[dict[str, Any]],
    bouts: list[dict[str, Any]],
    tournaments: list[dict[str, Any]],
    fencers: list[dict[str, Any]],
    identity_rows: list[dict[str, Any]],
    updated_at: str | None = None,
    rules: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rules = rules or FANTASY_SCORING_RULES
    updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    skips = empty_skips()
    identity_map = build_identity_map(identity_rows)
    tournaments_by_id = tournament_lookup(tournaments)
    result_items: dict[tuple[str, str, int], dict[str, Any]] = {}

    for result in results:
        tournament_id = clean_text(result.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id or "")
        season = normalize_season(result.get("season") or (tournament or {}).get("season"))
        fencer_id = result_fencer_id(result, identity_map)
        if not tournament_id or not fencer_id or season is None:
            skips["results_missing_required_fields"] += 1
            continue

        item = {
            "result": result,
            "tournament": tournament,
            "fencer_id": fencer_id,
            "tournament_id": tournament_id,
            "season": season,
            "rank": result_rank(result),
            "medal_type": normalize_medal(result.get("medal")),
            "status": normalize_status(result),
        }
        key = (fencer_id, tournament_id, season)
        if key in result_items:
            skips["duplicate_results"] += 1
            if result_sort_key(item) > result_sort_key(result_items[key]):
                result_items[key] = item
        else:
            result_items[key] = item

    rows_by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    result_statuses: dict[tuple[str, str, int], str | None] = {}
    for key, item in result_items.items():
        components = score_result_components(item["result"], item["tournament"], rules)
        row = make_fantasy_row(
            item["fencer_id"],
            item["tournament_id"],
            item["season"],
            components,
            rules,
            updated_at,
        )
        rows_by_key[key] = row
        result_statuses[key] = components["status"]

    fencer_ranks = build_fencer_rank_map(fencers, identity_map)
    add_upset_points(
        rows_by_key,
        bouts,
        tournaments_by_id,
        fencer_ranks,
        identity_map,
        result_statuses,
        rules,
        updated_at,
        skips,
    )
    rows = [rows_by_key[key] for key in sorted(rows_by_key)]
    return rows, skips


def fetch_all(
    client,
    table: str,
    columns: str,
    configure: Callable[[Any], Any] | None = None,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = client.table(table).select(columns)
        if configure:
            query = configure(query)
        page = query.range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def fetch_with_fallbacks(
    client, table: str, selects: tuple[str, ...], page_size: int = PAGE_SIZE
) -> list[dict[str, Any]]:
    last_error = None
    for columns in selects:
        try:
            return fetch_all(client, table, columns, page_size=page_size)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Unable to fetch {table}") from last_error


def fetch_optional_with_fallbacks(
    client, table: str, selects: tuple[str, ...], page_size: int = PAGE_SIZE
) -> list[dict[str, Any]]:
    try:
        return fetch_with_fallbacks(client, table, selects, page_size=page_size)
    except Exception:
        return []


def batch_upsert_fantasy_rows(
    client, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE
) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table("fs_fantasy_points").upsert(
            batch, on_conflict=FANTASY_CONFLICT_COLUMNS
        ).execute()
        written += len(batch)
    return written


def compute_fantasy_points(
    client=None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
    updated_at: str | None = None,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = rules or FANTASY_SCORING_RULES
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        results = fetch_with_fallbacks(client, "fs_results", RESULT_SELECTS, page_size=page_size)
        bouts = fetch_optional_with_fallbacks(client, "fs_bouts", BOUT_SELECTS, page_size=page_size)
        tournaments = fetch_with_fallbacks(client, "fs_tournaments", TOURNAMENT_SELECTS, page_size=page_size)
        fencers = fetch_optional_with_fallbacks(client, "fs_fencers", FENCER_SELECTS, page_size=page_size)
        identity_rows = fetch_optional_with_fallbacks(
            client, "fs_fencer_identities", IDENTITY_SELECTS, page_size=page_size
        )
        rows, skipped = build_fantasy_rows(
            results,
            bouts,
            tournaments,
            fencers,
            identity_rows,
            updated_at=updated_at,
            rules=rules,
        )
        written = batch_upsert_fantasy_rows(client, rows) if rows else 0
        summary = {
            "results_read": len(results),
            "bouts_read": len(bouts),
            "tournaments_read": len(tournaments),
            "fencers_read": len(fencers),
            "identity_rows": len(identity_rows),
            "fantasy_rows": len(rows),
            "written": written,
            "skipped": skipped,
            "rules_version": rules["rules_version"],
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {"updated_at": datetime.now(timezone.utc).isoformat(), **summary},
            )
        if run_log:
            run_log.complete(
                written=written,
                failed=0,
                skipped=sum(skipped.values()),
                metadata=summary,
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous fantasy scoring state: {previous_state}")
    print(f"Fantasy scoring computation starting - {datetime.now(timezone.utc).isoformat()}")
    summary = compute_fantasy_points()
    print(
        "Fantasy scoring computation complete - "
        f"{summary['fantasy_rows']} rows built, "
        f"{summary['written']} rows upserted, "
        f"{sum(summary['skipped'].values())} inputs skipped, "
        f"rules_version={summary['rules_version']}"
    )


if __name__ == "__main__":
    main()

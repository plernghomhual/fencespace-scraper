import argparse
import json
import math
import os
import random
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_ELO = 1500.0
PAGE_SIZE = 1000

CONFIDENCE_ORDER = {"low": 1, "medium": 2, "high": 3}
ROUND_SIZE_PATTERNS = (
    re.compile(r"(?:table|round)\s*(?:of)?\s*(\d+)", re.IGNORECASE),
    re.compile(r"\b(?:t|r)(\d+)\b", re.IGNORECASE),
)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def to_int(value: Any) -> int | None:
    number = to_float(value)
    return int(number) if number is not None else None


def lower_confidence(confidence: str, floor: str = "low") -> str:
    score = max(CONFIDENCE_ORDER[floor], CONFIDENCE_ORDER[confidence] - 1)
    for label, value in CONFIDENCE_ORDER.items():
        if value == score:
            return label
    return floor


def unique_warnings(warnings: list[str]) -> list[str]:
    seen = set()
    result = []
    for warning in warnings:
        if warning not in seen:
            seen.add(warning)
            result.append(warning)
    return result


def fencer_key(row: dict[str, Any], index: int | None = None) -> str:
    value = (
        row.get("fencer_id")
        or row.get("canonical_id")
        or row.get("id")
        or row.get("fie_fencer_id")
        or row.get("fencerId")
        or row.get("name")
    )
    text = clean_text(value)
    if text:
        return text
    if index is None:
        raise ValueError("Entrant is missing fencer_id/id/name")
    return f"entrant-{index + 1}"


def rating_lookup(elo_ratings: dict[str, Any] | list[dict[str, Any]] | None) -> dict[str, float]:
    if not elo_ratings:
        return {}
    if isinstance(elo_ratings, dict):
        rows = [{"fencer_id": key, "rating": value} for key, value in elo_ratings.items()]
    else:
        rows = elo_ratings

    lookup: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = clean_text(
            row.get("fencer_id")
            or row.get("canonical_id")
            or row.get("id")
            or row.get("fie_fencer_id")
        )
        rating = to_float(
            row.get("rating")
            if row.get("rating") is not None
            else row.get("elo")
            if row.get("elo") is not None
            else row.get("rating_after")
        )
        if key and rating is not None:
            lookup[key] = rating
    return lookup


def normalize_entrants(
    entrants: list[dict[str, Any]],
    elo_ratings: dict[str, Any] | list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not entrants:
        raise ValueError("At least one entrant is required for tournament simulation.")

    warnings: list[str] = []
    ratings = rating_lookup(elo_ratings)
    participants_by_id: dict[str, dict[str, Any]] = {}
    duplicate_count = 0

    for index, entrant in enumerate(entrants):
        if not isinstance(entrant, dict):
            warnings.append(f"Ignored non-object entrant at index {index}.")
            continue
        key = fencer_key(entrant, index)
        rating = ratings.get(key)
        if rating is None:
            rating = DEFAULT_ELO
        seed = to_int(
            entrant.get("seed")
            if entrant.get("seed") is not None
            else entrant.get("initial_seed")
            if entrant.get("initial_seed") is not None
            else entrant.get("entry_seed")
        )
        normalized = {
            "fencer_id": key,
            "name": clean_text(entrant.get("name")) or key,
            "rating": rating,
            "seed": seed,
        }
        current = participants_by_id.get(key)
        if current:
            duplicate_count += 1
            if current["seed"] is None or (seed is not None and seed < current["seed"]):
                current["seed"] = seed
            if current["rating"] == DEFAULT_ELO and rating != DEFAULT_ELO:
                current["rating"] = rating
            if current["name"] == key and normalized["name"] != key:
                current["name"] = normalized["name"]
        else:
            participants_by_id[key] = normalized

    if not participants_by_id:
        raise ValueError("No usable entrants were provided for tournament simulation.")

    missing_count = sum(1 for participant in participants_by_id.values() if participant["rating"] == DEFAULT_ELO)
    if missing_count:
        warnings.append(
            f"Missing Elo for {missing_count} entrant(s); using neutral {DEFAULT_ELO:g}."
        )
    if duplicate_count:
        warnings.append(f"Deduplicated {duplicate_count} repeated entrant row(s).")

    participants = sorted(
        participants_by_id.values(),
        key=lambda row: (
            row["seed"] is None,
            row["seed"] if row["seed"] is not None else 999999,
            row["name"],
            row["fencer_id"],
        ),
    )
    return participants, warnings


def elo_win_probability(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def simulated_winner(
    fencer_a: str | None,
    fencer_b: str | None,
    ratings: dict[str, float],
    rng: random.Random,
) -> tuple[str | None, str | None]:
    if fencer_a and not fencer_b:
        return fencer_a, None
    if fencer_b and not fencer_a:
        return fencer_b, None
    if not fencer_a and not fencer_b:
        return None, None

    assert fencer_a is not None and fencer_b is not None
    probability_a = elo_win_probability(ratings[fencer_a], ratings[fencer_b])
    if rng.random() < probability_a:
        return fencer_a, fencer_b
    return fencer_b, fencer_a


def round_size(round_name: Any) -> int:
    text = clean_text(round_name) or ""
    lowered = text.casefold()
    if "final" in lowered and "semi" not in lowered:
        return 2
    if "semi" in lowered:
        return 4
    if "quarter" in lowered:
        return 8
    for pattern in ROUND_SIZE_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return 0


def row_fencer_id(row: dict[str, Any], side: str) -> str | None:
    keys = (
        f"fencer_{side}_id",
        f"fencer_{side}",
        f"{side}_fencer_id",
        f"{side}_id",
        f"seed_{side}_fencer_id",
    )
    for key in keys:
        value = clean_text(row.get(key))
        if value:
            return value
    return None


def extract_initial_bracket_pairs(
    bracket_rows: list[dict[str, Any]] | None,
    participant_ids: set[str],
) -> tuple[list[tuple[str | None, str | None]], list[str]]:
    if not bracket_rows:
        return [], []

    warnings: list[str] = []
    candidate_rows = [row for row in bracket_rows if isinstance(row, dict)]
    if any(clean_text(row.get("winner_id") or row.get("winner")) for row in candidate_rows):
        warnings.append("Bracket historical winner fields ignored; only matchup slots are used.")

    rows_with_slots = [
        row
        for row in candidate_rows
        if row_fencer_id(row, "a") or row_fencer_id(row, "b")
    ]
    if not rows_with_slots:
        return [], warnings

    max_round_size = max(round_size(row.get("round_name") or row.get("round")) for row in rows_with_slots)
    if max_round_size > 0:
        initial_rows = [
            row
            for row in rows_with_slots
            if round_size(row.get("round_name") or row.get("round")) == max_round_size
        ]
    else:
        initial_rows = rows_with_slots

    initial_rows = sorted(
        initial_rows,
        key=lambda row: (
            to_int(row.get("bout_order") or row.get("order") or row.get("bout_number")) or 999999,
            clean_text(row.get("id")) or "",
        ),
    )

    pairs: list[tuple[str | None, str | None]] = []
    used_ids: set[str] = set()
    unknown_ids: set[str] = set()
    for row in initial_rows:
        left = row_fencer_id(row, "a")
        right = row_fencer_id(row, "b")
        if left and left not in participant_ids:
            unknown_ids.add(left)
            left = None
        if right and right not in participant_ids:
            unknown_ids.add(right)
            right = None
        if not left and not right:
            continue
        pairs.append((left, right))
        if left:
            used_ids.add(left)
        if right:
            used_ids.add(right)

    missing_from_initial_round = sorted(participant_ids - used_ids)
    for fencer_id in missing_from_initial_round:
        pairs.append((fencer_id, None))
    if missing_from_initial_round:
        warnings.append(
            f"Added {len(missing_from_initial_round)} entrant(s) as byes because the initial bracket round omitted them."
        )
    if unknown_ids:
        warnings.append(
            f"Ignored {len(unknown_ids)} bracket slot(s) not present in entrants."
        )
    return pairs, warnings


def seeded_pairs(participants: list[dict[str, Any]]) -> list[tuple[str | None, str | None]]:
    ordered = sorted(
        participants,
        key=lambda row: (
            row["seed"] is None,
            row["seed"] if row["seed"] is not None else 999999,
            -row["rating"],
            row["name"],
            row["fencer_id"],
        ),
    )
    slots = [row["fencer_id"] for row in ordered]
    pairs: list[tuple[str | None, str | None]] = []
    while slots:
        left = slots.pop(0)
        right = slots.pop(-1) if slots else None
        pairs.append((left, right))
    return pairs


def pair_next_round(winners: list[str]) -> list[tuple[str | None, str | None]]:
    pairs: list[tuple[str | None, str | None]] = []
    index = 0
    while index < len(winners):
        left = winners[index]
        right = winners[index + 1] if index + 1 < len(winners) else None
        pairs.append((left, right))
        index += 2
    return pairs


def simulate_direct_elimination_once(
    initial_pairs: list[tuple[str | None, str | None]],
    ratings: dict[str, float],
    rng: random.Random,
    participant_count: int,
) -> tuple[str, set[str], set[str]]:
    pairs = list(initial_pairs)
    top8: set[str] | None = None
    semifinal_losers: set[str] = set()
    runner_up: str | None = None

    while pairs:
        round_competitors = [
            fencer_id for pair in pairs for fencer_id in pair if fencer_id is not None
        ]
        if top8 is None and len(round_competitors) <= 8:
            top8 = set(round_competitors)

        winners = []
        losers = []
        for left, right in pairs:
            winner, loser = simulated_winner(left, right, ratings, rng)
            if winner:
                winners.append(winner)
            if loser:
                losers.append(loser)

        if 2 < len(round_competitors) <= 4:
            semifinal_losers.update(losers)
        if len(round_competitors) == 2:
            runner_up = losers[0] if losers else None
            winner = winners[0]
            medalists = {winner}
            if runner_up:
                medalists.add(runner_up)
            medalists.update(semifinal_losers)
            return winner, medalists, top8 or set(winners)

        pairs = pair_next_round(winners)

    only_fencer = next(fencer_id for pair in initial_pairs for fencer_id in pair if fencer_id)
    return only_fencer, {only_fencer}, {only_fencer} if participant_count <= 8 else set()


def simulate_standings_once(
    participant_ids: list[str],
    ratings: dict[str, float],
    rng: random.Random,
) -> list[str]:
    wins = {fencer_id: 0 for fencer_id in participant_ids}
    for index, left in enumerate(participant_ids):
        for right in participant_ids[index + 1 :]:
            winner, loser = simulated_winner(left, right, ratings, rng)
            if winner:
                wins[winner] += 1

    tie_breakers = {fencer_id: rng.random() for fencer_id in participant_ids}
    return sorted(
        participant_ids,
        key=lambda fencer_id: (-wins[fencer_id], tie_breakers[fencer_id], fencer_id),
    )


def probability_output(counts: dict[str, int], iterations: int) -> dict[str, float]:
    return {key: counts[key] / iterations for key in sorted(counts)}


def resolve_mode(
    format_hint: str | None,
    bracket_pairs: list[tuple[str | None, str | None]],
) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    format_text = (format_hint or "").casefold()
    format_tokens = set(re.findall(r"[a-z0-9]+", format_text))

    if bracket_pairs and any(left and right for left, right in bracket_pairs):
        return "direct_elimination", "high", warnings
    if (
        "de" in format_tokens
        or "direct" in format_text
        or "elimination" in format_text
        or "table" in format_text
    ):
        if bracket_pairs:
            return "direct_elimination", "medium", warnings
        warnings.append("No bracket rows were available; generated a seeded direct-elimination bracket.")
        return "direct_elimination", "medium", warnings
    if any(term in format_text for term in ("standing", "pool", "poule", "round robin", "rank")):
        return "simple_standings", "medium", warnings

    warnings.append("No bracket or recognized tournament format was available; used partial-data standings fallback.")
    return "partial_data_fallback", "low", warnings


def simulate_tournament(
    *,
    entrants: list[dict[str, Any]],
    elo_ratings: dict[str, Any] | list[dict[str, Any]] | None = None,
    format_hint: str | None = None,
    bracket_rows: list[dict[str, Any]] | None = None,
    seed: int = 1,
    iterations: int = 1000,
    tournament_id: str | None = None,
) -> dict[str, Any]:
    if iterations <= 0:
        raise ValueError("iterations must be greater than zero.")

    participants, warnings = normalize_entrants(entrants, elo_ratings)
    participant_ids = [row["fencer_id"] for row in participants]
    ratings = {row["fencer_id"]: row["rating"] for row in participants}
    bracket_pairs, bracket_warnings = extract_initial_bracket_pairs(
        bracket_rows, set(participant_ids)
    )
    warnings.extend(bracket_warnings)

    mode, confidence, mode_warnings = resolve_mode(format_hint, bracket_pairs)
    warnings.extend(mode_warnings)
    if mode == "direct_elimination" and not bracket_pairs:
        bracket_pairs = seeded_pairs(participants)
    if any(row["rating"] == DEFAULT_ELO for row in participants) and confidence != "low":
        confidence = lower_confidence(confidence)

    rng = random.Random(seed)
    winner_counts = {fencer_id: 0 for fencer_id in participant_ids}
    medal_counts = {fencer_id: 0 for fencer_id in participant_ids}
    top8_counts = {fencer_id: 0 for fencer_id in participant_ids}

    for _ in range(iterations):
        if mode == "direct_elimination":
            winner, medalists, top8 = simulate_direct_elimination_once(
                bracket_pairs, ratings, rng, len(participant_ids)
            )
            winner_counts[winner] += 1
            for fencer_id in medalists:
                medal_counts[fencer_id] += 1
            for fencer_id in top8:
                top8_counts[fencer_id] += 1
        else:
            standings = simulate_standings_once(participant_ids, ratings, rng)
            winner_counts[standings[0]] += 1
            for fencer_id in standings[: min(3, len(standings))]:
                medal_counts[fencer_id] += 1
            for fencer_id in standings[: min(8, len(standings))]:
                top8_counts[fencer_id] += 1

    return {
        "tournament_id": tournament_id,
        "mode": mode,
        "confidence": confidence,
        "seed": seed,
        "iterations": iterations,
        "participants": [
            {
                "fencer_id": row["fencer_id"],
                "name": row["name"],
                "rating": int(row["rating"]) if float(row["rating"]).is_integer() else row["rating"],
                "seed": row["seed"],
            }
            for row in participants
        ],
        "probabilities": {
            "winner": probability_output(winner_counts, iterations),
            "medal": probability_output(medal_counts, iterations),
            "top8": probability_output(top8_counts, iterations),
        },
        "warnings": unique_warnings(warnings),
    }


def infer_entrants_from_bracket(bracket_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entrants_by_id: dict[str, dict[str, Any]] = {}
    for row in bracket_rows:
        for side in ("a", "b"):
            fencer_id = row_fencer_id(row, side)
            if not fencer_id or fencer_id in entrants_by_id:
                continue
            name = clean_text(
                row.get(f"fencer_{side}_name")
                or row.get(f"{side}_name")
                or row.get(fencer_id)
            )
            entrants_by_id[fencer_id] = {"fencer_id": fencer_id, "name": name or fencer_id}
    return list(entrants_by_id.values())


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    from supabase import create_client

    return create_client(url, key)


def execute_select(query) -> list[dict[str, Any]]:
    result = query.execute()
    return result.data or []


def fetch_rows_for_tournament(client, table: str, columns: str, tournament_id: str) -> list[dict[str, Any]]:
    try:
        return execute_select(
            client.table(table).select(columns).eq("tournament_id", tournament_id)
        )
    except Exception as exc:
        print(f"Could not read {table}: {exc}", file=sys.stderr)
        return []


def fetch_tournament_payload(client, tournament_id: str) -> dict[str, Any]:
    tournament_rows = []
    try:
        tournament_rows = execute_select(
            client.table("fs_tournaments")
            .select("id,name,weapon,gender,category,format,season")
            .eq("id", tournament_id)
        )
    except Exception as exc:
        print(f"Could not read fs_tournaments: {exc}", file=sys.stderr)

    results = fetch_rows_for_tournament(
        client,
        "fs_results",
        "tournament_id,fencer_id,fie_fencer_id,name,rank,placement,seed",
        tournament_id,
    )
    bracket_rows = fetch_rows_for_tournament(
        client,
        "fs_tournament_brackets",
        "tournament_id,round_name,bout_order,fencer_a_id,fencer_b_id,winner_id,seed_a,seed_b",
        tournament_id,
    )

    entrants = [
        {
            "fencer_id": row.get("fencer_id") or row.get("fie_fencer_id"),
            "name": row.get("name") or row.get("fencer_id") or row.get("fie_fencer_id"),
            "seed": row.get("seed"),
        }
        for row in results
        if row.get("fencer_id") or row.get("fie_fencer_id") or row.get("name")
    ]
    if not entrants and bracket_rows:
        entrants = infer_entrants_from_bracket(bracket_rows)

    fencer_ids = [row["fencer_id"] for row in entrants if row.get("fencer_id")]
    elo_rows: list[dict[str, Any]] = []
    if fencer_ids:
        try:
            query = client.table("fs_fencer_elo").select("fencer_id,rating")
            if hasattr(query, "in_"):
                query = query.in_("fencer_id", fencer_ids)
            elo_rows = execute_select(query)
        except Exception as exc:
            print(f"Could not read fs_fencer_elo: {exc}", file=sys.stderr)

    tournament = tournament_rows[0] if tournament_rows else {}
    return {
        "tournament_id": tournament_id,
        "tournament": tournament,
        "format": tournament.get("format"),
        "entrants": entrants,
        "elo_ratings": elo_rows,
        "bracket_rows": bracket_rows,
    }


def load_payload(path: str | Path | None, tournament_id: str) -> dict[str, Any]:
    if path:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        payload.setdefault("tournament_id", tournament_id)
        return payload
    return fetch_tournament_payload(get_supabase_client(), tournament_id)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a seeded Monte Carlo re-simulation for a historical fencing tournament."
    )
    parser.add_argument("--tournament-id", required=True, help="Tournament id to simulate.")
    parser.add_argument("--seed", type=int, default=1, help="Deterministic random seed.")
    parser.add_argument("--iterations", type=int, default=1000, help="Monte Carlo iterations.")
    parser.add_argument("--output-json", help="Write simulation JSON to this path.")
    parser.add_argument(
        "--input-json",
        help="Optional offline fixture payload with entrants, elo_ratings, format, and bracket_rows.",
    )
    parser.add_argument(
        "--format",
        dest="format_hint",
        help="Override tournament format, for example direct_elimination or standings.",
    )
    parser.add_argument("--no-log", action="store_true", help="Disable fs_scraper_runs logging.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logger = None
    if not args.no_log:
        from run_logger import ScraperRunLogger

        logger = ScraperRunLogger("simulate_tournament").start()

    try:
        payload = load_payload(args.input_json, args.tournament_id)
        result = simulate_tournament(
            tournament_id=args.tournament_id,
            entrants=payload.get("entrants") or [],
            elo_ratings=payload.get("elo_ratings") or {},
            format_hint=args.format_hint or payload.get("format"),
            bracket_rows=payload.get("bracket_rows") or payload.get("brackets") or [],
            seed=args.seed,
            iterations=args.iterations,
        )
        encoded = json.dumps(result, indent=2, sort_keys=True)
        if args.output_json:
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(encoded + "\n", encoding="utf-8")
            written = 1
        else:
            print(encoded)
            written = 0
        if logger:
            logger.complete(written=written, failed=0, skipped=0)
        return 0
    except Exception as exc:
        if logger:
            logger.error(str(exc))
        print(f"simulate_tournament failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

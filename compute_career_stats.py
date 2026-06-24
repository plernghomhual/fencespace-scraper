import json
import os
import re
from datetime import UTC, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import set_state
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_career_stats"

IDENTITY_SELECTS = (
    "canonical_id,fs_fencer_row_ids",
    "id,canonical_id,fs_fencer_row_ids",
    "id,fs_fencer_row_ids",
    "canonical_id,fencer_ids",
)


def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


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
    key = text.casefold()
    if key in {"e", "epee", "épée"}:
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
    key = text.casefold().replace(".", "")
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


def season_sort_key(value: Any) -> tuple[int, str]:
    text = clean_text(value) or ""
    years = [int(part) for part in re.findall(r"\d{4}", text)]
    if years:
        return years[-1], text
    number = to_int(text)
    return (number if number is not None else 999999, text)


def avg_rank(ranks: list[int]) -> float | None:
    if not ranks:
        return None
    value = Decimal(sum(ranks)) / Decimal(len(ranks))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def canonical_fencer_id(fencer_id: Any, identity_map: dict[str, str] | None) -> str | None:
    text = clean_text(fencer_id)
    if not text:
        return None
    if identity_map:
        return identity_map.get(text, text)
    return text


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
            row.get("fs_fencer_row_ids")
            or row.get("fencer_ids")
            or row.get("source_fencer_ids")
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


def load_identity_map(client, page_size: int = PAGE_SIZE) -> tuple[dict[str, str], int]:
    for columns in IDENTITY_SELECTS:
        try:
            rows = fetch_all(client, "fs_fencer_identities", columns, page_size=page_size)
            return build_identity_map(rows), len(rows)
        except Exception as exc:
            last_error = exc
    print(f"Identity table unavailable; using raw fs_results.fencer_id grouping: {last_error}")
    return {}, 0


def tournament_lookup(tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def add_tournament_dimensions(stat: dict[str, Any], tournament: dict[str, Any] | None, result: dict[str, Any] | None = None) -> None:
    source = tournament or result or {}
    weapon = normalize_weapon(source.get("weapon"))
    category = normalize_category(source.get("category"), source.get("gender"))
    season = clean_text(source.get("season"))
    if weapon:
        stat["weapons"].add(weapon)
    if category:
        stat["categories"].add(category)
    if season:
        stat["seasons"].add(season)


def new_stat(fencer_id: str) -> dict[str, Any]:
    return {
        "fencer_id": fencer_id,
        "competition_ids": set(),
        "rank_by_competition": {},
        "weapons": set(),
        "categories": set(),
        "seasons": set(),
        "total_touches_scored": 0,
        "total_touches_received": 0,
    }


def aggregate_career_stats(
    results: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    bouts: list[dict[str, Any]],
    identity_map: dict[str, str] | None = None,
    updated_at: str | None = None,
) -> list[dict[str, Any]]:
    tournaments_by_id = tournament_lookup(tournaments)
    stats: dict[str, dict[str, Any]] = {}

    for index, result in enumerate(results):
        fencer_id = canonical_fencer_id(result.get("fencer_id"), identity_map)
        if not fencer_id:
            continue

        stat = stats.setdefault(fencer_id, new_stat(fencer_id))
        tournament_id = clean_text(result.get("tournament_id"))
        rank = to_int(result.get("rank") if result.get("rank") is not None else result.get("placement"))
        tournament = tournaments_by_id.get(tournament_id) if tournament_id else None

        if tournament_id:
            stat["competition_ids"].add(tournament_id)
            add_tournament_dimensions(stat, tournament, result)
            if rank is not None:
                current = stat["rank_by_competition"].get(tournament_id)
                if current is None or rank < current:
                    stat["rank_by_competition"][tournament_id] = rank
        elif rank is not None:
            stat["rank_by_competition"][f"result:{index}"] = rank
            add_tournament_dimensions(stat, tournament, result)

    for bout in bouts:
        fencer_a = canonical_fencer_id(bout.get("fencer_a_id"), identity_map)
        fencer_b = canonical_fencer_id(bout.get("fencer_b_id"), identity_map)
        if not fencer_a or not fencer_b or fencer_a == fencer_b:
            continue

        score_a = to_int(bout.get("score_a"))
        score_b = to_int(bout.get("score_b"))
        if score_a is None or score_b is None:
            continue

        if fencer_a in stats:
            stats[fencer_a]["total_touches_scored"] += score_a
            stats[fencer_a]["total_touches_received"] += score_b
        if fencer_b in stats:
            stats[fencer_b]["total_touches_scored"] += score_b
            stats[fencer_b]["total_touches_received"] += score_a

    now = updated_at or datetime.now(UTC).isoformat()
    rows: list[dict[str, Any]] = []
    for fencer_id in sorted(stats):
        stat = stats[fencer_id]
        ranks = list(stat["rank_by_competition"].values())
        seasons = sorted(stat["seasons"], key=season_sort_key)
        touches_scored = stat["total_touches_scored"]
        touches_received = stat["total_touches_received"]
        rows.append(
            {
                "fencer_id": fencer_id,
                "total_competitions": len(stat["competition_ids"]) or len(ranks),
                "gold_medals": sum(1 for rank in ranks if rank == 1),
                "silver_medals": sum(1 for rank in ranks if rank == 2),
                "bronze_medals": sum(1 for rank in ranks if rank == 3),
                "top8_count": sum(1 for rank in ranks if 1 <= rank <= 8),
                "best_rank": min(ranks) if ranks else None,
                "avg_rank": avg_rank(ranks),
                "worst_rank": max(ranks) if ranks else None,
                "weapons_used": sorted(stat["weapons"]),
                "categories_competed": sorted(stat["categories"]),
                "first_season": seasons[0] if seasons else None,
                "last_season": seasons[-1] if seasons else None,
                "total_touches_scored": touches_scored,
                "total_touches_received": touches_received,
                "touch_differential": touches_scored - touches_received,
                "updated_at": now,
            }
        )
    return rows


def batch_upsert(client, table: str, rows: list[dict[str, Any]], on_conflict: str, batch_size: int = BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        client.table(table).upsert(batch, on_conflict=on_conflict).execute()
        written += len(batch)
    return written


def compute_career_stats(
    client=None,
    page_size: int = PAGE_SIZE,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        results = fetch_all(
            client,
            "fs_results",
            "tournament_id,fencer_id,rank",
            page_size=page_size,
        )
        tournaments = fetch_all(
            client,
            "fs_tournaments",
            "id,season,weapon,gender,category",
            page_size=page_size,
        )
        bouts = fetch_all(
            client,
            "fs_bouts",
            "tournament_id,fencer_a_id,fencer_b_id,score_a,score_b",
            page_size=page_size,
        )
        identity_map, identity_rows = load_identity_map(client, page_size=page_size)
        rows = aggregate_career_stats(results, tournaments, bouts, identity_map)
        written = batch_upsert(client, "fs_fencer_career_stats", rows, on_conflict="fencer_id")

        summary = {
            "results_read": len(results),
            "bouts_read": len(bouts),
            "career_rows": len(rows),
            "written": written,
            "identity_rows": identity_rows,
        }
        if update_state:
            set_state(SOURCE, "last_run", {"updated_at": datetime.now(UTC).isoformat(), **summary})
        if run_log:
            run_log.complete(written=written, failed=0, skipped=0, metadata=summary)
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Career stats computation starting - {datetime.now(UTC).isoformat()}")
    summary = compute_career_stats()
    print(
        "Career stats computation complete - "
        f"{summary['career_rows']} rows built, {summary['written']} rows upserted"
    )


if __name__ == "__main__":
    main()

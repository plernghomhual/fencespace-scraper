import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

PAGE_SIZE = 1000
BATCH_SIZE = 100
SOURCE = "compute_medal_tables"

RESULT_SELECTS = (
    "id,tournament_id,fencer_id,country,nationality,medal",
    "id,tournament_id,fencer_id,nationality,medal",
    "id,tournament_id,fencer_id,country,medal",
)
TOURNAMENT_SELECTS = (
    "id,type,name,category",
    "id,type,name",
    "id,type",
)

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
    "EUROPEANCHAMPIONSHIP": "Continental",
    "EUROPEANCHAMPIONSHIPS": "Continental",
    "ASIANCHAMPIONSHIP": "Continental",
    "ASIANCHAMPIONSHIPS": "Continental",
    "PANAMERICANCHAMPIONSHIP": "Continental",
    "PANAMERICANCHAMPIONSHIPS": "Continental",
    "AFRICANCHAMPIONSHIP": "Continental",
    "AFRICANCHAMPIONSHIPS": "Continental",
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
    (
        "Worlds",
        (
            "world championship",
            "world championships",
            "championnats du monde",
            "worlds",
        ),
    ),
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


def row_key(*parts: Any) -> str:
    return ":".join((clean_text(part) or "").casefold() for part in parts)


def medal_bucket(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return MEDAL_MAP.get(compact_key(text))


def result_country(result: dict[str, Any]) -> str | None:
    return clean_text(result.get("country")) or clean_text(result.get("nationality"))


def normalize_tier(tournament: dict[str, Any] | None) -> str | None:
    if not tournament:
        return None

    for field in ("tier", "type", "competition_type"):
        tier = TYPE_TIERS.get(compact_key(tournament.get(field)).upper())
        if tier:
            return tier

    haystack = " ".join(
        clean_text(tournament.get(field)) or ""
        for field in ("tier", "type", "name", "category")
    ).casefold()
    for tier, patterns in TIER_TEXT_PATTERNS:
        if any(pattern in haystack for pattern in patterns):
            return tier
    return None


def empty_counts() -> dict[str, int]:
    return {"gold": 0, "silver": 0, "bronze": 0}


def add_medal(counter: dict[str, Any], medal: str) -> None:
    counter[medal] += 1


def medal_row(
    *,
    record_id: str,
    scope: str,
    counts: dict[str, int],
    updated_at: str,
    country: str | None = None,
    fencer_id: str | None = None,
    tier: str | None = None,
) -> dict[str, Any]:
    gold = counts["gold"]
    silver = counts["silver"]
    bronze = counts["bronze"]
    return {
        "id": record_id,
        "scope": scope,
        "country": country,
        "fencer_id": fencer_id,
        "tier": tier,
        "gold": gold,
        "silver": silver,
        "bronze": bronze,
        "total": gold + silver + bronze,
        "updated_at": updated_at,
    }


def tournament_lookup(tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(tournaments, dict):
        return {str(key): value for key, value in tournaments.items()}
    return {
        str(row["id"]): row
        for row in tournaments
        if row.get("id") is not None
    }


def build_medal_table_rows(
    results: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]] | list[dict[str, Any]],
    updated_at: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    tournaments_by_id = tournament_lookup(tournaments)
    now = updated_at or datetime.now(timezone.utc).isoformat()

    country_counts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"country": None, "counts": empty_counts()}
    )
    fencer_counts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"fencer_id": None, "counts": empty_counts()}
    )
    tier_counts: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"tier": None, "country": None, "counts": empty_counts()}
    )
    skipped = 0

    for result in results:
        medal = medal_bucket(result.get("medal"))
        if not medal:
            skipped += 1
            continue

        contributed = False
        country = result_country(result)
        if country:
            country_id = row_key("country", country)
            country_counts[country_id]["country"] = country_counts[country_id]["country"] or country
            add_medal(country_counts[country_id]["counts"], medal)
            contributed = True

        fencer_id = clean_text(result.get("fencer_id"))
        if fencer_id:
            fencer_id_key = row_key("fencer", fencer_id)
            fencer_counts[fencer_id_key]["fencer_id"] = fencer_counts[fencer_id_key]["fencer_id"] or fencer_id
            add_medal(fencer_counts[fencer_id_key]["counts"], medal)
            contributed = True

        tournament_id = clean_text(result.get("tournament_id"))
        tournament = tournaments_by_id.get(tournament_id) if tournament_id else None
        tier = normalize_tier(tournament)
        if tier and country:
            tier_id = row_key("tier", tier, country)
            tier_counts[(tier, tier_id)]["tier"] = tier
            tier_counts[(tier, tier_id)]["country"] = tier_counts[(tier, tier_id)]["country"] or country
            add_medal(tier_counts[(tier, tier_id)]["counts"], medal)
            contributed = True

        if not contributed:
            skipped += 1

    rows: list[dict[str, Any]] = []
    for record_id, data in sorted(country_counts.items()):
        rows.append(
            medal_row(
                record_id=record_id,
                scope="country",
                country=data["country"],
                counts=data["counts"],
                updated_at=now,
            )
        )
    for record_id, data in sorted(fencer_counts.items()):
        rows.append(
            medal_row(
                record_id=record_id,
                scope="fencer",
                fencer_id=data["fencer_id"],
                counts=data["counts"],
                updated_at=now,
            )
        )
    for (_, record_id), data in sorted(tier_counts.items()):
        rows.append(
            medal_row(
                record_id=record_id,
                scope="tier_country",
                country=data["country"],
                tier=data["tier"],
                counts=data["counts"],
                updated_at=now,
            )
        )
    return rows, skipped


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


def fetch_medal_results(client, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    last_error = None
    for columns in RESULT_SELECTS:
        try:
            return fetch_all(
                client,
                "fs_results",
                columns,
                configure=lambda query: query.not_.is_("medal", "null"),
                page_size=page_size,
            )
        except Exception as exc:
            last_error = exc
    raise RuntimeError("Unable to fetch medaled fs_results rows") from last_error


def fetch_tournaments(client, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    last_error = None
    for columns in TOURNAMENT_SELECTS:
        try:
            return fetch_all(
                client,
                "fs_tournaments",
                columns,
                page_size=page_size,
            )
        except Exception as exc:
            last_error = exc
    raise RuntimeError("Unable to fetch fs_tournaments tier rows") from last_error


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


def compute_medal_tables(
    client=None,
    page_size: int = PAGE_SIZE,
    updated_at: str | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    try:
        client = client or get_supabase_client()
        results = fetch_medal_results(client, page_size=page_size)
        tournaments = fetch_tournaments(client, page_size=page_size)
        rows, skipped = build_medal_table_rows(results, tournaments, updated_at=updated_at)
        written = batch_upsert(client, "fs_medal_tables", rows, on_conflict="id") if rows else 0

        summary = {
            "results_read": len(results),
            "tournaments_read": len(tournaments),
            "medal_rows": len(rows),
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
    print(f"Medal table computation starting - {datetime.now(timezone.utc).isoformat()}")
    previous_state = get_state(SOURCE, "last_run")
    if previous_state:
        print(f"Previous medal table state: {previous_state}")
    summary = compute_medal_tables()
    print(
        "Medal table computation complete - "
        f"{summary['medal_rows']} rows built, "
        f"{summary['written']} rows upserted, "
        f"{summary['skipped']} rows skipped"
    )


if __name__ == "__main__":
    main()

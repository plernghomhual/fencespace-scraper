from __future__ import annotations

import os
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state

try:
    from supabase import create_client
except Exception:  # pragma: no cover - import errors surface when a client is required.
    create_client = None


SOURCE = "compute_transfers"
PAGE_SIZE = 1000
BATCH_SIZE = 100
TRANSFER_NAMESPACE = uuid.UUID("4307fcae-0dd5-4b25-8d7d-fc3f62f2ce90")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = None


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
    "GB": "Great Britain",
    "GBR": "Great Britain",
    "GREAT BRITAIN": "Great Britain",
    "KOREA": "South Korea",
    "KOR": "South Korea",
    "HONG KONG, CHINA": "Hong Kong",
    "HONG KONG CHINA": "Hong Kong",
    "MACAO, CHINA": "Macau",
    "MACAO CHINA": "Macau",
    "TURKIYE": "Turkey",
    "COTE D'IVOIRE": "Cote D'Ivoire",
    "COTE DIVOIRE": "Cote D'Ivoire",
}


def get_client():
    global supabase
    if supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        if create_client is None:
            raise RuntimeError("supabase package is required.")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return text.casefold()


def normalize_country(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    key = key.upper().replace(".", "")
    key = re.sub(r"\s+", " ", key)
    return COUNTRY_ALIASES.get(key, text.title())


def country_key(value: Any) -> str:
    return normalize_key(normalize_country(value))


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
        if end < start:
            end += 100
        return end
    return None


def transfer_id(row: dict[str, Any]) -> str:
    parts = [
        clean_text(row.get("fencer_id")) or "",
        clean_text(row.get("from_country")) or "",
        clean_text(row.get("to_country")) or "",
        clean_text(row.get("season")) or "",
        clean_text(row.get("competition_id")) or "",
        clean_text(row.get("source")) or "",
    ]
    return str(uuid.uuid5(TRANSFER_NAMESPACE, "|".join(parts)))


def with_transfer_id(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    row["id"] = transfer_id(row)
    return row


def extract_fencer_id(row: dict[str, Any], fencer_id_by_fie_id: dict[str, str] | None = None) -> str | None:
    fencer_id = clean_text(row.get("fencer_id"))
    if fencer_id:
        return fencer_id
    fie_id = clean_text(row.get("fie_fencer_id") or row.get("fie_id"))
    if fie_id and fencer_id_by_fie_id:
        return fencer_id_by_fie_id.get(fie_id)
    return None


def extract_nationality_history(metadata: Any) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    raw_history = metadata.get("nationality_history")
    if not isinstance(raw_history, list):
        return []

    countries: list[str] = []
    for item in raw_history:
        if isinstance(item, dict):
            country = normalize_country(
                item.get("country")
                or item.get("nationality")
                or item.get("countryLabel")
                or item.get("nationalityLabel")
            )
        else:
            country = normalize_country(item)
        if country and country_key(country) not in {country_key(existing) for existing in countries}:
            countries.append(country)
    return countries


def add_nationality_cross_check(row: dict[str, Any], fencer_metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not fencer_metadata:
        return row
    history = extract_nationality_history(fencer_metadata.get(row["fencer_id"]))
    if not history:
        return row

    metadata = dict(row.get("metadata") or {})
    history_keys = {country_key(country) for country in history}
    from_key = country_key(row.get("from_country"))
    to_key = country_key(row.get("to_country"))
    metadata["wikidata_cross_check"] = "matched" if {from_key, to_key}.issubset(history_keys) else "not_matched"
    metadata["wikidata_nationality_history"] = history
    row = dict(row)
    row["metadata"] = metadata
    row["id"] = transfer_id(row)
    return row


def summarize_season_observations(observations: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(obs["country_key"] for obs in observations)
    best_key = max(counts, key=lambda key: counts[key])
    best_country = next(obs["country"] for obs in observations if obs["country_key"] == best_key)
    compact_observations = [
        {
            "country": obs["country"],
            "weapon": obs.get("weapon"),
            "gender": obs.get("gender"),
            "category": obs.get("category"),
            "rank": obs.get("rank"),
            "points": obs.get("points"),
            "fie_fencer_id": obs.get("fie_fencer_id"),
        }
        for obs in observations
    ]
    return {
        "country": best_country,
        "country_key": best_key,
        "country_counts": dict(sorted(counts.items())),
        "country_conflict": len(counts) > 1,
        "observations": compact_observations,
    }


def compute_confirmed_ranking_transfers(
    rankings: list[dict[str, Any]],
    *,
    fencer_id_by_fie_id: dict[str, str] | None = None,
    fencer_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    by_fencer_season: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))

    for row in rankings:
        fencer_id = extract_fencer_id(row, fencer_id_by_fie_id)
        season = season_to_int(row.get("season"))
        country = normalize_country(row.get("country"))
        if not fencer_id or season is None or not country:
            continue
        by_fencer_season[fencer_id][season].append(
            {
                "country": country,
                "country_key": country_key(country),
                "weapon": clean_text(row.get("weapon")),
                "gender": clean_text(row.get("gender")),
                "category": clean_text(row.get("category")),
                "rank": row.get("rank"),
                "points": row.get("points"),
                "fie_fencer_id": clean_text(row.get("fie_fencer_id") or row.get("fie_id")),
            }
        )

    transfers: list[dict[str, Any]] = []
    for fencer_id in sorted(by_fencer_season):
        by_season = by_fencer_season[fencer_id]
        seasons = sorted(by_season)
        summaries = {season: summarize_season_observations(by_season[season]) for season in seasons}

        for previous_season, current_season in zip(seasons, seasons[1:], strict=False):
            if current_season != previous_season + 1:
                continue
            previous = summaries[previous_season]
            current = summaries[current_season]
            if previous["country_key"] == current["country_key"]:
                continue

            row = with_transfer_id(
                {
                    "fencer_id": fencer_id,
                    "from_country": previous["country"],
                    "to_country": current["country"],
                    "season": str(current_season),
                    "competition_id": None,
                    "source": "rankings_history",
                    "confirmed": True,
                    "metadata": {
                        "previous_season": previous_season,
                        "current_season": current_season,
                        "previous_country_counts": previous["country_counts"],
                        "current_country_counts": current["country_counts"],
                        "previous_country_conflict": previous["country_conflict"],
                        "current_country_conflict": current["country_conflict"],
                        "previous_observations": previous["observations"],
                        "current_observations": current["observations"],
                    },
                }
            )
            transfers.append(add_nationality_cross_check(row, fencer_metadata))

    return sort_transfer_rows(dedupe_transfer_rows(transfers))


def tournament_map(tournaments: dict[Any, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    values: list[dict[str, Any]]
    if isinstance(tournaments, dict):
        values = list(tournaments.values())
    else:
        values = tournaments
    return {str(row["id"]): row for row in values if row.get("id") is not None}


def result_observation_sort_key(observation: dict[str, Any]) -> tuple[str, str]:
    return (
        clean_text(observation.get("date")) or "",
        clean_text(observation.get("competition_id")) or "",
    )


def compute_uncertain_result_transfers(
    results: list[dict[str, Any]],
    tournaments: dict[Any, dict[str, Any]] | list[dict[str, Any]],
    *,
    fencer_id_by_fie_id: dict[str, str] | None = None,
    fencer_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    tournaments_by_id = tournament_map(tournaments)
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)

    for row in results:
        fencer_id = extract_fencer_id(row, fencer_id_by_fie_id)
        tournament_id = clean_text(row.get("tournament_id") or row.get("competition_id"))
        tournament = tournaments_by_id.get(str(tournament_id)) if tournament_id else None
        season = season_to_int(row.get("season") or (tournament or {}).get("season"))
        country = normalize_country(row.get("country") or row.get("nationality"))
        if not fencer_id or season is None or not country or not tournament_id:
            continue
        grouped[(fencer_id, season)].append(
            {
                "country": country,
                "country_key": country_key(country),
                "competition_id": tournament_id,
                "date": (tournament or {}).get("start_date") or (tournament or {}).get("end_date") or row.get("date"),
                "rank": row.get("rank"),
                "name": row.get("name"),
                "tournament_name": (tournament or {}).get("name"),
            }
        )

    transfers: list[dict[str, Any]] = []
    for (fencer_id, season), observations in sorted(grouped.items()):
        ordered = sorted(observations, key=result_observation_sort_key)
        if len(ordered) < 2:
            continue
        previous = ordered[0]
        for current in ordered[1:]:
            if current["country_key"] == previous["country_key"]:
                previous = current
                continue
            row = with_transfer_id(
                {
                    "fencer_id": fencer_id,
                    "from_country": previous["country"],
                    "to_country": current["country"],
                    "season": str(season),
                    "competition_id": current["competition_id"],
                    "source": "results_same_season",
                    "confirmed": False,
                    "metadata": {
                        "from_competition_id": previous["competition_id"],
                        "to_competition_id": current["competition_id"],
                        "from_competition_date": previous.get("date"),
                        "to_competition_date": current.get("date"),
                        "from_tournament_name": previous.get("tournament_name"),
                        "to_tournament_name": current.get("tournament_name"),
                        "from_rank": previous.get("rank"),
                        "to_rank": current.get("rank"),
                    },
                }
            )
            transfers.append(add_nationality_cross_check(row, fencer_metadata))
            previous = current

    return sort_transfer_rows(dedupe_transfer_rows(transfers))


def dedupe_transfer_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {row["id"]: row for row in rows}
    return list(by_id.values())


def sort_transfer_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            clean_text(row.get("fencer_id")) or "",
            season_to_int(row.get("season")) or 0,
            clean_text(row.get("source")) or "",
            clean_text(row.get("from_country")) or "",
            clean_text(row.get("to_country")) or "",
            clean_text(row.get("competition_id")) or "",
        ),
    )


def build_fencer_maps(fencers: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, Any]]:
    fencer_id_by_fie_id: dict[str, str] = {}
    fencer_metadata: dict[str, Any] = {}
    for row in sorted(fencers, key=lambda item: clean_text(item.get("id")) or ""):
        fencer_id = clean_text(row.get("id"))
        if not fencer_id:
            continue
        fencer_metadata[fencer_id] = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        fie_id = clean_text(row.get("fie_id"))
        if fie_id:
            fencer_id_by_fie_id.setdefault(fie_id, fencer_id)
    return fencer_id_by_fie_id, fencer_metadata


def fetch_all(client, table: str, select_columns: str, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table(table)
            .select(select_columns)
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


def load_inputs(client, *, page_size: int) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    fencers = fetch_all(client, "fs_fencers", "id,fie_id,metadata", page_size=page_size)
    rankings = fetch_with_fallbacks(
        client,
        "fs_rankings_history",
        [
            "fencer_id,fie_fencer_id,season,country,weapon,gender,category,rank,points,name,scraped_at",
            "fie_fencer_id,season,country,weapon,gender,category,rank,points,name,scraped_at",
        ],
        page_size=page_size,
    )
    tournaments = fetch_all(client, "fs_tournaments", "id,season,start_date,end_date,name", page_size=page_size)
    results = fetch_with_fallbacks(
        client,
        "fs_results",
        [
            "fencer_id,fie_fencer_id,tournament_id,country,nationality,rank,name",
            "fencer_id,fie_fencer_id,tournament_id,nationality,rank,name",
            "fie_fencer_id,tournament_id,country,nationality,rank,name",
        ],
        page_size=page_size,
    )
    return fencers, rankings, tournaments, results


def upsert_transfer_rows(client, rows: list[dict[str, Any]], *, batch_size: int = BATCH_SIZE) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        try:
            client.table("fs_fencer_transfers").upsert(batch, on_conflict="id").execute()
            written += len(batch)
        except Exception as exc:
            print(f"  fs_fencer_transfers upsert batch {index // batch_size} failed: {exc}")
            failed += len(batch)
    return written, failed


def compute_transfer_rows(
    *,
    fencers: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    tournaments: list[dict[str, Any]] | dict[Any, dict[str, Any]],
    results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fencer_id_by_fie_id, fencer_metadata = build_fencer_maps(fencers)
    confirmed = compute_confirmed_ranking_transfers(
        rankings,
        fencer_id_by_fie_id=fencer_id_by_fie_id,
        fencer_metadata=fencer_metadata,
    )
    uncertain = compute_uncertain_result_transfers(
        results,
        tournaments,
        fencer_id_by_fie_id=fencer_id_by_fie_id,
        fencer_metadata=fencer_metadata,
    )
    return confirmed, uncertain


def compute_and_store_transfers(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, int]:
    client = client or get_client()
    run_log = ScraperRunLogger(SOURCE).start() if log_run else None
    get_state(SOURCE, "last_run") if update_state else None

    try:
        fencers, rankings, tournaments, results = load_inputs(client, page_size=page_size)
        confirmed, uncertain = compute_transfer_rows(
            fencers=fencers,
            rankings=rankings,
            tournaments=tournaments,
            results=results,
        )
        rows = sort_transfer_rows(dedupe_transfer_rows(confirmed + uncertain))
        written, failed = upsert_transfer_rows(client, rows, batch_size=batch_size)
        summary = {
            "confirmed_transfers": len(confirmed),
            "uncertain_transfers": len(uncertain),
            "written": written,
            "failed": failed,
            "skipped": 0,
        }
        if update_state:
            set_state(
                SOURCE,
                "last_run",
                {
                    **summary,
                    "completed_at": datetime.now(UTC).isoformat(),
                },
            )
        if run_log:
            run_log.complete(
                written=written,
                failed=failed,
                skipped=0,
                metadata={
                    "confirmed_transfers": len(confirmed),
                    "uncertain_transfers": len(uncertain),
                },
            )
        return summary
    except Exception as exc:
        if run_log:
            run_log.error(str(exc))
        raise


def main() -> None:
    print(f"Fencer transfer computation starting - {datetime.now(UTC).isoformat()}")
    summary = compute_and_store_transfers()
    print(f"Confirmed transfers found: {summary['confirmed_transfers']}")
    print(f"Uncertain transfers found: {summary['uncertain_transfers']}")
    print(f"Transfer rows written: {summary['written']}")
    print(f"Failed rows: {summary['failed']}")


if __name__ == "__main__":
    main()

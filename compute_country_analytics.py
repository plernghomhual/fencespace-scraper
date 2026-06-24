import os
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime, timezone
from typing import Any

from run_logger import ScraperRunLogger
from scraper_state import get_state, set_state
from supabase import create_client

MODULE_NAME = "compute_country_analytics"
PAGE_SIZE = 1000
BATCH_SIZE = 100
FENCER_COLUMNS = "id,country,weapon,category,world_rank,club,fie_points"

WEAPON_MAP = {
    "s": "Sabre",
    "sabre": "Sabre",
    "saber": "Sabre",
    "e": "Epee",
    "epee": "Epee",
    "epée": "Epee",
    "f": "Foil",
    "foil": "Foil",
}

CATEGORY_MAP = {
    "senior": "Senior",
    "junior": "Junior",
    "cadet": "Cadet",
    "veteran": "Veteran",
}

CLUB_PREFIX_TOKENS = (
    ("a", "s", "d"),
    ("a", "s"),
    ("s", "s", "d"),
)
CLUB_NOISE_TOKENS = {
    "asd",
    "ssd",
    "srl",
    "spa",
    "llc",
    "ltd",
    "inc",
    "association",
    "associazione",
    "sportiva",
    "dilettantistica",
}


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalized_text(value: Any) -> str:
    text = clean_text(value) or ""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    ).casefold()


def numeric(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            value = value.replace(",", "")
        return float(value)
    except (TypeError, ValueError):
        return None


def positive_rank(value: Any) -> float | None:
    rank = numeric(value)
    if rank is None or rank <= 0:
        return None
    return rank


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return WEAPON_MAP.get(normalized_text(text), text.title())


def normalize_category(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if "'" in text:
        return text
    return CATEGORY_MAP.get(normalized_text(text), text.title())


def normalize_club_name(value: Any) -> str | None:
    text = normalized_text(value)
    if not text:
        return None
    text = text.replace("&", " and ")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).replace("_", " ")
    tokens = [token for token in text.split() if token]

    for prefix in CLUB_PREFIX_TOKENS:
        if tuple(tokens[:len(prefix)]) == prefix:
            tokens = tokens[len(prefix):]
            break

    tokens = [token for token in tokens if token not in CLUB_NOISE_TOKENS]
    return " ".join(tokens) or None


def compute_country_depth(
    fencers: list[dict[str, Any]],
    *,
    updated_at: str | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)

    for fencer in fencers:
        country = clean_text(fencer.get("country"))
        weapon = normalize_weapon(fencer.get("weapon"))
        category = normalize_category(fencer.get("category"))
        rank = positive_rank(fencer.get("world_rank"))
        if not country or not weapon or not category or rank is None:
            continue
        grouped[(country, weapon, category)].append(rank)

    timestamp = updated_at or datetime.now(UTC).isoformat()
    rows: list[dict[str, Any]] = []
    for (country, weapon, category), ranks in sorted(grouped.items()):
        total_ranked = len(ranks)
        rows.append({
            "country": country,
            "weapon": weapon,
            "category": category,
            "fencers_in_top16": sum(1 for rank in ranks if rank <= 16),
            "fencers_in_top32": sum(1 for rank in ranks if rank <= 32),
            "fencers_in_top64": sum(1 for rank in ranks if rank <= 64),
            "total_ranked": total_ranked,
            "avg_world_rank": round(sum(ranks) / total_ranked, 4),
            "updated_at": timestamp,
        })
    return rows


def compute_club_rankings(
    fencers: list[dict[str, Any]],
    *,
    updated_at: str | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {"ranks": [], "total_points": 0.0}
    )

    for fencer in fencers:
        club = normalize_club_name(fencer.get("club"))
        country = clean_text(fencer.get("country"))
        weapon = normalize_weapon(fencer.get("weapon"))
        rank = positive_rank(fencer.get("world_rank"))
        if not club or not country or not weapon or rank is None:
            continue

        key = (club, country, weapon)
        grouped[key]["ranks"].append(rank)
        grouped[key]["total_points"] += numeric(fencer.get("fie_points")) or 0.0

    timestamp = updated_at or datetime.now(UTC).isoformat()
    rows: list[dict[str, Any]] = []
    for (club, country, weapon), values in sorted(grouped.items()):
        ranks = values["ranks"]
        rows.append({
            "club": club,
            "country": country,
            "weapon": weapon,
            "total_fencers": len(ranks),
            "avg_rank": round(sum(ranks) / len(ranks), 4),
            "total_points": round(values["total_points"], 4),
            "updated_at": timestamp,
        })
    return rows


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
    return create_client(url, key)


def fetch_all_fencers(client, *, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = (
            client.table("fs_fencers")
            .select(FENCER_COLUMNS)
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


def batch_upsert(client, table: str, rows: list[dict[str, Any]], *, on_conflict: str, batch_size: int) -> tuple[int, int]:
    written = 0
    failed = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index:index + batch_size]
        try:
            client.table(table).upsert(batch, on_conflict=on_conflict).execute()
            written += len(batch)
        except Exception as exc:
            failed += len(batch)
            print(f"  {table} upsert batch {index // batch_size} failed: {exc}")
    return written, failed


def compute_country_analytics(
    *,
    client=None,
    page_size: int = PAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    updated_at: str | None = None,
    log_run: bool = True,
    update_state: bool = True,
) -> dict[str, Any]:
    run_log = ScraperRunLogger(MODULE_NAME).start() if log_run else None
    previous_summary = get_state(MODULE_NAME, "last_summary") if update_state else None

    try:
        client = client or get_supabase_client()
        timestamp = updated_at or datetime.now(UTC).isoformat()
        fencers = fetch_all_fencers(client, page_size=page_size)

        country_rows = compute_country_depth(fencers, updated_at=timestamp)
        club_rows = compute_club_rankings(fencers, updated_at=timestamp)

        country_written, country_failed = batch_upsert(
            client,
            "fs_country_depth",
            country_rows,
            on_conflict="country,weapon,category",
            batch_size=batch_size,
        )
        club_written, club_failed = batch_upsert(
            client,
            "fs_club_rankings",
            club_rows,
            on_conflict="club,country,weapon",
            batch_size=batch_size,
        )

        summary = {
            "fencers_read": len(fencers),
            "country_depth_rows": len(country_rows),
            "club_ranking_rows": len(club_rows),
            "written": country_written + club_written,
            "failed": country_failed + club_failed,
            "skipped": 0,
        }
        if isinstance(previous_summary, dict) and previous_summary.get("updated_at"):
            summary["previous_updated_at"] = previous_summary["updated_at"]

        if update_state:
            set_state(MODULE_NAME, "last_summary", {**summary, "updated_at": timestamp})
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
    summary = compute_country_analytics()
    print(
        "Country analytics complete: "
        f"{summary['country_depth_rows']} country depth rows, "
        f"{summary['club_ranking_rows']} club ranking rows, "
        f"{summary['written']} written, {summary['failed']} failed"
    )


if __name__ == "__main__":
    main()

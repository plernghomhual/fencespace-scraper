import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from supabase import create_client

from run_logger import ScraperRunLogger

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

PAGE_SIZE = 1000
UPDATE_BATCH_SIZE = 100

WEAPON_MAP = {
    "s": "Sabre",
    "sabre": "Sabre",
    "saber": "Sabre",
    "e": "Epee",
    "epee": "Epee",
    "f": "Foil",
    "foil": "Foil",
}

GENDER_MAP = {
    "m": "Men's",
    "male": "Men's",
    "men": "Men's",
    "mens": "Men's",
    "men's": "Men's",
    "f": "Women's",
    "female": "Women's",
    "women": "Women's",
    "womens": "Women's",
    "women's": "Women's",
}

TYPE_WEIGHTS = {
    "WCH": 5.0,
    "CHM": 5.0,
    "WORLDCHAMPIONSHIP": 5.0,
    "WORLDCHAMPIONSHIPS": 5.0,
    "OG": 5.0,
    "OLYMPICS": 5.0,
    "OLYMPICGAMES": 5.0,
    "GP": 4.0,
    "GRANDPRIX": 4.0,
    "WC": 3.0,
    "WORLDCUP": 3.0,
    "CC": 2.5,
    "ZCH": 2.5,
    "CONTINENTALCHAMPIONSHIP": 2.5,
    "CONTINENTALCHAMPIONSHIPS": 2.5,
    "ZONALCHAMPIONSHIP": 2.5,
    "ZONALCHAMPIONSHIPS": 2.5,
    "SAT": 1.5,
    "SATELLITE": 1.5,
    "NAT": 1.0,
    "NATIONAL": 1.0,
    "NATIONALCHAMPIONSHIP": 1.0,
    "NCAACHAMPIONSHIP": 1.0,
    "NCAA": 1.0,
}

TEXT_LEVEL_WEIGHTS = (
    (("olympic games", "olympics", "world championship", "world championships", "championnats du monde", "championships world", "wch", "chm"), 5.0),
    (("grand prix", "gp"), 4.0),
    (("world cup", "wc"), 3.0),
    (("continental championship", "continental championships", "zonal championship", "zonal championships", "asian championship", "european championship", "pan american championship", "african championship", "cc"), 2.5),
    (("satellite", "sat"), 1.5),
    (("national", "nat", "ncaa"), 1.0),
)

SCHEMA_SQL = """
alter table public.fs_fencers add column if not exists domestic_rank integer;
alter table public.fs_fencers add column if not exists domestic_results_score double precision;
create table if not exists public.fs_country_rankings (
  country text not null,
  weapon text not null,
  category text not null,
  fencer_count integer not null default 0,
  top8_count integer not null default 0,
  updated_at timestamptz not null default timezone('utc'::text, now()),
  primary key (country, weapon, category)
);
create unique index if not exists idx_fs_country_rankings_unique
  on public.fs_country_rankings(country, weapon, category);
create index if not exists idx_fs_fencers_domestic_rank
  on public.fs_fencers(country, weapon, category, domestic_rank)
  where domestic_rank is not null;
create index if not exists idx_fs_fencers_domestic_results_score
  on public.fs_fencers(domestic_results_score)
  where domestic_results_score is not null;
"""


def clean_text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def normalized_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return text.casefold()


def numeric(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_weapon(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return WEAPON_MAP.get(normalized_key(text), text.title())


def normalize_category(category: Any, gender: Any = None) -> str | None:
    category_text = clean_text(category)
    if not category_text:
        return None

    if "'" in category_text:
        return category_text

    category_label = category_text.title()
    gender_label = GENDER_MAP.get(normalized_key(gender))
    return f"{gender_label} {category_label}" if gender_label else category_label


def label_group(country: str, weapon: str, category: str) -> str:
    parts = category.split()
    if len(parts) >= 2 and parts[0] in {"Men's", "Women's"}:
        return f"{country} {parts[0]} {weapon} {' '.join(parts[1:])}"
    return f"{country} {weapon} {category}"


def tournament_type_key(value: Any) -> str:
    text = normalized_key(value)
    return re.sub(r"[^a-z0-9]+", "", text).upper()


def haystack_contains(haystack: str, token: str) -> bool:
    if len(token) <= 3 and token.isalnum():
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack) is not None
    return token in haystack


def result_weight(tournament: dict[str, Any] | None) -> float:
    if not tournament:
        return 1.0
    type_key = tournament_type_key(tournament.get("type"))
    if type_key in TYPE_WEIGHTS:
        return TYPE_WEIGHTS[type_key]

    haystack = " ".join(
        clean_text(tournament.get(field)) or ""
        for field in ("name", "category")
    ).casefold()
    for tokens, weight in TEXT_LEVEL_WEIGHTS:
        if any(haystack_contains(haystack, token) for token in tokens):
            return weight
    return 1.0


def ensure_schema() -> None:
    print("Ensuring national rankings schema...")
    try:
        supabase.rpc("fs_ensure_national_rankings_schema").execute()
        print("  Schema RPC complete")
    except Exception as exc:
        print(f"  Schema RPC unavailable or failed: {exc}")
        applied = False
        for function_name in ("exec_sql", "execute_sql"):
            for payload in ({"sql": SCHEMA_SQL}, {"query": SCHEMA_SQL}):
                try:
                    supabase.rpc(function_name, payload).execute()
                    print(f"  Schema SQL applied via {function_name}")
                    applied = True
                    break
                except Exception:
                    continue
            if applied:
                break
        if not applied:
            print("  Continuing with schema verification; apply the national rankings migration if verification fails.")

    try:
        supabase.table("fs_fencers")\
            .select("id,domestic_rank,domestic_results_score")\
            .limit(1)\
            .execute()
        supabase.table("fs_country_rankings")\
            .select("country,weapon,category,fencer_count,top8_count,updated_at")\
            .limit(1)\
            .execute()
    except Exception as exc:
        raise RuntimeError(
            "National rankings schema is missing. Apply the migration that adds "
            "fs_fencers.domestic_results_score and fs_country_rankings, then rerun."
        ) from exc


def fetch_all(
    table: str,
    select_columns: str,
    configure: Callable[[Any], Any] | None = None,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = supabase.table(table).select(select_columns)
        if configure:
            query = configure(query)
        page = query.range(offset, offset + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def batch_upsert(table: str, rows: list[dict[str, Any]], on_conflict: str, batch_size: int = UPDATE_BATCH_SIZE) -> int:
    written = 0
    for index in range(0, len(rows), batch_size):
        batch = rows[index:index + batch_size]
        try:
            supabase.table(table).upsert(batch, on_conflict=on_conflict).execute()
            written += len(batch)
        except Exception as exc:
            print(f"  batch_upsert({table}) batch {index//batch_size} failed: {exc}")
    return written


def build_fencer_indexes(fencers: list[dict[str, Any]]) -> tuple[
    dict[Any, dict[str, Any]],
    dict[tuple[str, str, str], dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[tuple[str, str, str, str], dict[str, Any]],
]:
    by_id: dict[Any, dict[str, Any]] = {}
    by_fie_weapon_category: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_fie_id_only: dict[str, dict[str, Any]] = {}
    by_name_country_weapon_category: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for fencer in fencers:
        fencer_id = fencer.get("id")
        if fencer_id is not None:
            by_id[fencer_id] = fencer

        weapon = normalize_weapon(fencer.get("weapon"))
        category = normalize_category(fencer.get("category"))
        if not weapon or not category:
            continue

        fie_id = clean_text(fencer.get("fie_id"))
        if fie_id:
            by_fie_weapon_category[(fie_id, weapon, category)] = fencer
            by_fie_id_only.setdefault(fie_id, fencer)

        name_key = normalized_key(fencer.get("name"))
        country_key = normalized_key(fencer.get("country"))
        if name_key and country_key:
            by_name_country_weapon_category[(name_key, country_key, weapon, category)] = fencer

    return by_id, by_fie_weapon_category, by_fie_id_only, by_name_country_weapon_category


def compute_domestic_ranks(fencers: list[dict[str, Any]]) -> tuple[dict[Any, int], list[tuple[str, str, str, int]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for fencer in fencers:
        country = clean_text(fencer.get("country"))
        weapon = normalize_weapon(fencer.get("weapon"))
        category = normalize_category(fencer.get("category"))
        fencer_id = fencer.get("id")
        if not country or not weapon or not category or fencer_id is None or not (fencer.get("name") or "").strip():
            continue
        grouped[(country, weapon, category)].append(fencer)

    updates: dict[str, int] = {}
    summaries: list[tuple[str, str, str, int]] = []
    for (country, weapon, category), rows in sorted(grouped.items()):
        ranked = sorted(
            rows,
            key=lambda row: (
                -numeric(row.get("fie_points")),
                normalized_key(row.get("name")),
                str(row.get("id") or ""),
            ),
        )
        for rank, fencer in enumerate(ranked, start=1):
            fencer_id = fencer["id"]
            if fencer_id in updates:
                print(f"  Warning: fencer id={fencer_id} appears in multiple groups; overwriting rank {updates[fencer_id]} -> {rank}")
            updates[fencer_id] = rank
        summaries.append((country, weapon, category, len(ranked)))

    return updates, summaries


def load_tournaments() -> dict[str, dict[str, Any]]:
    tournaments = fetch_all("fs_tournaments", "id,name,weapon,gender,category,type")
    result: dict[str, dict[str, Any]] = {}
    for row in tournaments:
        if row.get("id") is not None:
            result[str(row["id"])] = row
    return result


def compute_results_scores(
    fencers: list[dict[str, Any]],
    tournaments: dict[str, dict[str, Any]],
) -> tuple[dict[Any, float], int]:
    by_id, by_fie_weapon_category, by_fie_id_only, by_name_country_weapon_category = build_fencer_indexes(fencers)
    result_rows = fetch_all(
        "fs_results",
        "tournament_id,fencer_id,fie_fencer_id,rank,name,country",
        configure=lambda query: query.lte("rank", 8).not_.is_("rank", "null"),
    )

    scores: dict[int, float] = defaultdict(float)
    unmatched = 0
    for result in result_rows:
        tournament_id = result.get("tournament_id")
        tournament = tournaments.get(str(tournament_id)) if tournament_id is not None else None
        weapon = normalize_weapon(tournament.get("weapon") if tournament else None)
        category = normalize_category(tournament.get("category") if tournament else None, tournament.get("gender") if tournament else None)
        if not weapon or not category:
            unmatched += 1
            continue

        fencer = None
        fencer_id = result.get("fencer_id")
        if fencer_id is not None:
            fencer = by_id.get(fencer_id)

        fie_id = clean_text(result.get("fie_fencer_id"))
        if not fencer and fie_id:
            fencer = by_fie_weapon_category.get((fie_id, weapon, category))
        if not fencer and fie_id:
            fencer = by_fie_id_only.get(fie_id)

        if not fencer:
            name_key = normalized_key(result.get("name"))
            country_key = normalized_key(result.get("country"))
            if name_key and country_key:
                fencer = by_name_country_weapon_category.get((name_key, country_key, weapon, category))

        if fencer and fencer.get("id") is not None:
            scores[fencer["id"]] += result_weight(tournament)
        else:
            unmatched += 1

    return dict(scores), unmatched


def compute_country_rankings(fencers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"fencer_count": 0, "top8_count": 0})
    for fencer in fencers:
        country = clean_text(fencer.get("country"))
        weapon = normalize_weapon(fencer.get("weapon"))
        category = normalize_category(fencer.get("category"))
        if not country or not weapon or not category:
            continue
        key = (country, weapon, category)
        grouped[key]["fencer_count"] += 1
        world_rank = numeric(fencer.get("world_rank"), default=999999)
        if 1 <= world_rank <= 8:
            grouped[key]["top8_count"] += 1

    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "country": country,
            "weapon": weapon,
            "category": category,
            "fencer_count": counts["fencer_count"],
            "top8_count": counts["top8_count"],
            "updated_at": now,
        }
        for (country, weapon, category), counts in sorted(grouped.items())
    ]


def main() -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"National rankings computation starting - {started_at}")
    run_log = ScraperRunLogger("compute_national_rankings").start()
    ensure_schema()

    fencers = fetch_all(
        "fs_fencers",
        "id,fie_id,name,country,weapon,category,world_rank,fie_points",
    )
    print(f"Loaded {len(fencers)} fencers")

    rank_updates, summaries = compute_domestic_ranks(fencers)
    tournaments = load_tournaments()
    print(f"Loaded {len(tournaments)} tournaments")

    result_scores, unmatched_results = compute_results_scores(fencers, tournaments)
    print(f"Computed results scores for {len(result_scores)} fencers ({unmatched_results} top-8 rows unmatched)")

    valid_fencer_ids = {f["id"] for f in fencers if (f.get("name") or "").strip()}
    now = datetime.now(timezone.utc).isoformat()
    fencer_updates = [
        {
            "id": fencer_id,
            "domestic_rank": domestic_rank,
            "domestic_results_score": result_scores.get(fencer_id, 0.0),
            "updated_at": now,
        }
        for fencer_id, domestic_rank in sorted(rank_updates.items())
        if fencer_id in valid_fencer_ids
    ]
    updated_fencers = batch_upsert("fs_fencers", fencer_updates, on_conflict="id") if fencer_updates else 0

    country_rows = compute_country_rankings(fencers)
    updated_countries = batch_upsert("fs_country_rankings", country_rows, on_conflict="country,weapon,category") if country_rows else 0

    for country, weapon, category, count in summaries:
        print(f"{label_group(country, weapon, category)}: {count} fencers ranked")

    print(f"Upserted {updated_fencers} fencer ranking rows")
    print(f"Upserted {updated_countries} country ranking rows")
    run_log.complete(
        written=updated_fencers + updated_countries,
        metadata={"fencer_rows": updated_fencers, "country_rows": updated_countries, "unmatched_results": unmatched_results},
    )
    print("National rankings computation complete")


if __name__ == "__main__":
    main()

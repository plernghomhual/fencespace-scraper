import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_country_medal_geo.sql"


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def normalized_sql() -> str:
    return " ".join(migration_sql().lower().split())


def test_country_medal_geo_migration_defines_materialized_view_shape():
    sql = migration_sql()
    normalized = normalized_sql()

    assert "alter table public.fs_results add column if not exists country text" in normalized
    assert "create materialized view if not exists public.fs_country_medal_geo as" in normalized
    assert "coalesce(nullif(upper(trim(r.country)), ''), nullif(upper(trim(r.nationality)), ''))" in normalized
    assert "left join public.fs_country_geo_codes" in normalized
    assert "on geo.country_code = medals.country_code" in normalized

    expected_columns = [
        "country_code",
        "country_name",
        "fie_code",
        "olympic_code",
        "weapon",
        "category",
        "competition_tier",
        "season",
        "year",
        "gold_count",
        "silver_count",
        "bronze_count",
        "total_medals",
        "top8_count",
        "top16_count",
        "latitude",
        "longitude",
        "centroid_latitude",
        "centroid_longitude",
        "refreshed_at",
    ]
    for column in expected_columns:
        assert re.search(rf"\b{column}\b", sql, re.IGNORECASE), column


def test_country_medal_geo_counts_medals_and_rank_buckets():
    normalized = normalized_sql()

    assert "count(*) filter (where medal_bucket = 'gold')::integer as gold_count" in normalized
    assert "count(*) filter (where medal_bucket = 'silver')::integer as silver_count" in normalized
    assert "count(*) filter (where medal_bucket = 'bronze')::integer as bronze_count" in normalized
    assert "count(*) filter (where medal_bucket in ('gold', 'silver', 'bronze'))::integer as total_medals" in normalized
    assert "count(*) filter (where rank_int between 1 and 8)::integer as top8_count" in normalized
    assert "count(*) filter (where rank_int between 1 and 16)::integer as top16_count" in normalized
    assert "r.rank::text ~ '^[0-9]+$'" in normalized


def test_country_medal_geo_groups_by_supported_dimensions_and_tier():
    normalized = normalized_sql()

    for expression in (
        "country_code",
        "coalesce(nullif(t.weapon, ''), 'unknown')",
        "coalesce(nullif(t.category, ''), 'unknown')",
        "competition_tier",
        "t.season::text",
        "extract(year from t.start_date)::integer",
    ):
        assert expression in normalized

    assert "case" in normalized
    assert "'olympics'" in normalized
    assert "'worlds'" in normalized
    assert "'grand prix'" in normalized
    assert "'world cup'" in normalized
    assert "'continental'" in normalized


def test_country_medal_geo_has_stable_code_mapping_and_unknown_geo_fallback():
    normalized = normalized_sql()

    assert "create table if not exists public.fs_country_geo_codes" in normalized
    assert "country_code text primary key" in normalized
    assert "fie_code text" in normalized
    assert "olympic_code text" in normalized
    assert "iso_alpha3 text" in normalized
    assert "latitude double precision" in normalized
    assert "longitude double precision" in normalized
    assert "left join public.fs_country_geo_codes" in normalized
    assert "geo.latitude" in normalized
    assert "geo.longitude" in normalized
    assert "geo.centroid_latitude" in normalized
    assert "geo.centroid_longitude" in normalized
    assert "where country_code is not null" in normalized
    assert "unrecognized country codes keep medal counts with null geo fields" in normalized


def test_country_medal_geo_indexes_and_refresh_function_are_defined():
    normalized = normalized_sql()

    assert "create unique index if not exists fs_country_medal_geo_unique_idx" in normalized
    assert "on public.fs_country_medal_geo" in normalized
    assert "country_code, weapon, category, competition_tier, season, year" in normalized
    assert "create index if not exists fs_country_medal_geo_heatmap_idx" in normalized
    assert "total_medals desc" in normalized
    assert "create or replace function public.refresh_country_medal_geo()" in normalized
    assert "refresh materialized view public.fs_country_medal_geo" in normalized
    assert "grant execute on function public.refresh_country_medal_geo() to service_role" in normalized


def test_country_medal_geo_migration_is_idempotent_and_non_destructive():
    sql = migration_sql()
    normalized = normalized_sql()

    assert "drop table" not in normalized
    assert "drop materialized view" not in normalized
    assert "drop view" not in normalized
    assert "truncate" not in normalized
    assert "delete from" not in normalized
    assert re.search(r"\binsert\s+into\s+public\.fs_country_geo_codes\b", sql, re.IGNORECASE)
    assert "on conflict (country_code) do update set" in normalized
    assert "create table if not exists public.fs_country_geo_codes" in normalized
    assert "create materialized view if not exists public.fs_country_medal_geo as" in normalized

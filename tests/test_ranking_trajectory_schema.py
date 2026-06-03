import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_ranking_trajectory.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _normalized(sql: str) -> str:
    return " ".join(sql.lower().split())


def _table_body(sql: str, table_name: str) -> str:
    match = re.search(
        rf"create\s+table\s+if\s+not\s+exists\s+(?:public\.)?{table_name}\s*\((.*?)\);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing CREATE TABLE IF NOT EXISTS for {table_name}"
    return match.group(1)


def _column_definition(table_body: str, column: str) -> str:
    match = re.search(
        rf"^\s*{column}\s+([^,\n]+)",
        table_body,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    assert match, f"missing column {column}"
    return match.group(1).lower()


def test_trajectory_migration_defines_required_columns():
    table_body = _table_body(_sql(), "fs_ranking_history_trajectory")

    required_columns = {
        "id",
        "fencer_identity_id",
        "fencer_id",
        "source",
        "season",
        "weapon",
        "gender",
        "category",
        "rank",
        "points",
        "rank_delta",
        "points_delta",
        "trend_window",
        "updated_at",
    }

    for column in required_columns:
        _column_definition(table_body, column)

    assert "uuid" in _column_definition(table_body, "fencer_identity_id")
    assert "references" in _column_definition(table_body, "fencer_identity_id")
    assert "fs_fencer_identities" in _column_definition(table_body, "fencer_identity_id")
    assert "uuid" in _column_definition(table_body, "fencer_id")
    assert "references" in _column_definition(table_body, "fencer_id")
    assert "fs_fencers" in _column_definition(table_body, "fencer_id")


def test_trajectory_points_are_nullable_for_rank_only_sources():
    table_body = _table_body(_sql(), "fs_ranking_history_trajectory")

    points_definition = _column_definition(table_body, "points")
    points_delta_definition = _column_definition(table_body, "points_delta")

    assert "numeric" in points_definition
    assert "not null" not in points_definition
    assert "numeric" in points_delta_definition
    assert "not null" not in points_delta_definition


def test_trajectory_uses_normalized_text_seasons():
    sql = _sql()
    table_body = _table_body(sql, "fs_ranking_history_trajectory")
    normalized = _normalized(sql)

    season_definition = _column_definition(table_body, "season")

    assert season_definition.startswith("text")
    assert "not null" in season_definition
    assert "fs_ranking_history_trajectory_season_format" in normalized
    assert "season ~ '^\\d{4}-\\d{4}$'" in normalized


def test_trajectory_unique_key_prevents_duplicate_source_season_rows_per_fencer():
    normalized = _normalized(_sql())

    assert "constraint fs_ranking_history_trajectory_unique unique" in normalized
    assert (
        "unique (fencer_identity_id, source, season, weapon, gender, category, trend_window)"
        in normalized
    )


def test_trajectory_indexes_support_fencer_detail_and_stable_ordering():
    normalized = _normalized(_sql())

    assert (
        "create index if not exists fs_ranking_history_trajectory_detail_idx "
        "on public.fs_ranking_history_trajectory "
        "(fencer_identity_id, source, weapon, gender, category, trend_window, season)"
    ) in normalized
    assert (
        "create index if not exists fs_ranking_history_trajectory_fencer_idx "
        "on public.fs_ranking_history_trajectory (fencer_id, season, source) "
        "where fencer_id is not null"
    ) in normalized
    assert (
        "create index if not exists fs_ranking_history_trajectory_projection_idx "
        "on public.fs_ranking_history_trajectory "
        "(source, weapon, gender, category, season, rank)"
    ) in normalized


def test_trajectory_migration_is_idempotent_and_non_destructive():
    normalized = _normalized(_sql())

    assert "create table if not exists public.fs_ranking_history_trajectory" in normalized
    assert "create index if not exists" in normalized
    assert "drop table" not in normalized
    assert "truncate" not in normalized
    assert "delete from" not in normalized
    assert "alter table public.fs_ranking_history_trajectory drop" not in normalized

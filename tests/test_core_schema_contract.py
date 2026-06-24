import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260604_core_schema_contract.sql"


def normalized_sql() -> str:
    return " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())


def test_core_schema_contract_creates_visible_base_tables():
    sql = normalized_sql()

    for table in (
        "fs_fencers",
        "fs_fencer_identities",
        "fs_tournaments",
        "fs_results",
        "fs_bouts",
        "fs_rankings_history",
        "fs_scraper_runs",
        "fs_scraper_state",
    ):
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql


def test_core_schema_contract_defines_importer_conflict_targets():
    sql = normalized_sql()

    expected_indexes = (
        "fs_tournaments_source_id_key on public.fs_tournaments (source_id)",
        "fs_tournaments_source_source_id_key on public.fs_tournaments (source, source_id)",
        "fs_results_tournament_name_key on public.fs_results (tournament_id, name)",
        "fs_results_tournament_fencer_key on public.fs_results (tournament_id, fencer_id)",
        "fs_results_source_id_key on public.fs_results (source_id)",
        "fs_bouts_id_key on public.fs_bouts (id)",
        "fs_scraper_state_source_key_key on public.fs_scraper_state (source, key)",
    )
    for index_fragment in expected_indexes:
        assert index_fragment in sql


def test_core_schema_contract_is_idempotent_and_non_destructive():
    sql = normalized_sql()

    assert "create extension if not exists pgcrypto" in sql
    assert "create table if not exists" in sql
    assert "create unique index if not exists" in sql
    destructive_patterns = (
        r"\bdrop\s+table\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
        r"\balter\s+table\b[^;]*\bdrop\b",
        r"\bdrop\s+index\b",
    )
    for pattern in destructive_patterns:
        assert not re.search(pattern, sql), f"destructive SQL found: {pattern}"

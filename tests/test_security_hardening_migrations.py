import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RLS_MIGRATION = ROOT / "supabase" / "migrations" / "20260604_rls_gap_closure.sql"
BULK_UPDATE_MIGRATION = ROOT / "supabase" / "migrations" / "20260604_bulk_update_rpcs.sql"
MARKETPLACE_MIGRATION = ROOT / "supabase" / "migrations" / "20260602_marketplace.sql"

RLS_GAP_TABLES = (
    "fs_betting_odds",
    "fs_coach_history",
    "fs_country_geo_codes",
    "fs_fencer_family_relationships",
    "fs_fantasy_points",
    "fs_h2h_graph",
    "fs_fencer_injury_absences",
    "fs_junior_conversion_rates",
    "fs_ranking_history_trajectory",
    "fs_social_feed",
    "fs_upsets",
    "fs_competition_weather",
)


def normalized_sql(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_rls_gap_closure_enables_rls_and_revokes_direct_client_access():
    sql = normalized_sql(RLS_MIGRATION)

    for table in RLS_GAP_TABLES:
        assert f"alter table if exists public.{table} enable row level security" in sql
        assert f"revoke all on public.{table} from anon, authenticated" in sql


def test_rls_gap_closure_is_idempotent_and_non_destructive():
    sql = normalized_sql(RLS_MIGRATION)

    assert "alter table if exists" in sql
    destructive_patterns = (
        r"\bdrop\s+table\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
        r"\balter\s+table\b[^;]*\bdrop\b",
        r"\bdrop\s+index\b",
    )
    for pattern in destructive_patterns:
        assert not re.search(pattern, sql), f"destructive SQL found: {pattern}"


def test_marketplace_usage_rpc_is_granted_to_service_role_only():
    sql = normalized_sql(MARKETPLACE_MIGRATION)

    signature = "public.fs_marketplace_increment_usage(uuid, text, date, date, integer)"
    assert f"revoke all on function {signature} from public" in sql
    assert f"grant execute on function {signature} to service_role" in sql


def test_bulk_update_rpcs_are_service_role_only_and_validate_targets():
    sql = normalized_sql(BULK_UPDATE_MIGRATION)

    for function_name in (
        "fs_bulk_update_fencer_matches",
        "fs_bulk_update_result_losses",
        "fs_bulk_update_tournament_metadata",
    ):
        assert f"create or replace function public.{function_name}" in sql
        assert f"revoke all on function public.{function_name}" in sql
        assert f"grant execute on function public.{function_name}" in sql

    assert "p_table_name not in ('fs_results', 'fs_national_fed_rankings')" in sql
    assert "jsonb_to_recordset(p_updates)" in sql

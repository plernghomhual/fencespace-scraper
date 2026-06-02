import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260601_rls_policies.sql"

SENSITIVE_BASE_TABLES = [
    "fs_fencers",
    "fs_tournaments",
    "fs_results",
    "fs_national_fed_rankings",
    "fs_head_to_head",
    "fs_rankings_history",
]

SUBSCRIBER_POLICIES = {
    "fs_fencers": "subscriber_fencers_read",
    "fs_tournaments": "subscriber_tournaments_read",
    "fs_results": "subscriber_results_read",
    "fs_national_fed_rankings": "subscriber_national_fed_rankings_read",
    "fs_head_to_head": "subscriber_head_to_head_read",
    "fs_rankings_history": "subscriber_rankings_history_read",
}

SENSITIVE_COLUMNS = {"bio_text", "metadata", "date_of_birth", "height", "club"}


def _sql() -> str:
    return MIGRATION.read_text()


def _normalized(sql: str) -> str:
    return " ".join(sql.lower().split())


def _view_select_columns(sql: str, view_name: str) -> set[str]:
    match = re.search(
        rf"create\s+or\s+replace\s+view\s+(?:public\.)?{view_name}\s+"
        rf"(?:with\s*\([^)]*\)\s+)?as\s+select\s+(.*?)\s+from\s+",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing public view {view_name}"
    return {part.strip().split()[-1].lower() for part in match.group(1).split(",")}


def test_rls_migration_does_not_use_invalid_security_policy_syntax():
    normalized = _normalized(_sql())

    assert "create security policy" not in normalized
    assert "create role" not in normalized
    assert "public_user" not in normalized


def test_rls_is_enabled_on_sensitive_base_tables():
    normalized = _normalized(_sql())

    for table in SENSITIVE_BASE_TABLES:
        assert (
            f"alter table public.{table} enable row level security" in normalized
            or f"alter table {table} enable row level security" in normalized
        ), f"missing RLS enablement for {table}"


def test_direct_anon_reads_are_revoked_from_sensitive_base_tables():
    normalized = _normalized(_sql())

    for table in SENSITIVE_BASE_TABLES:
        assert (
            f"revoke all on public.{table} from anon" in normalized
            or f"revoke all on {table} from anon" in normalized
        ), f"missing anon revoke for {table}"


def test_public_views_exclude_sensitive_columns():
    sql = _sql()
    normalized = _normalized(sql)

    assert _view_select_columns(sql, "v_fencer_public") == {
        "id",
        "name",
        "country",
        "weapon",
        "category",
        "world_rank",
        "fie_points",
        "image_url",
    }
    assert _view_select_columns(sql, "v_tournament_public") == {
        "id",
        "name",
        "season",
        "start_date",
        "end_date",
        "country",
        "weapon",
        "category",
        "type",
    }
    assert SENSITIVE_COLUMNS.isdisjoint(_view_select_columns(sql, "v_fencer_public"))
    assert SENSITIVE_COLUMNS.isdisjoint(_view_select_columns(sql, "v_tournament_public"))
    assert "grant select on public.v_fencer_public to anon" in normalized
    assert "grant select on public.v_tournament_public to anon" in normalized


def test_public_views_are_security_invoker():
    normalized = _normalized(_sql())

    assert "security_invoker = true" in normalized
    assert normalized.count("security_invoker = true") >= 2


def test_authenticated_subscriber_policies_check_jwt_app_metadata():
    normalized = _normalized(_sql())

    for table, policy in SUBSCRIBER_POLICIES.items():
        assert f"create policy {policy}" in normalized
        assert f"on public.{table}" in normalized
    assert normalized.count("for select to authenticated") == len(SUBSCRIBER_POLICIES)
    assert normalized.count("auth.jwt()") == len(SUBSCRIBER_POLICIES)
    assert normalized.count("app_metadata") >= len(SUBSCRIBER_POLICIES)
    assert "'role'" in normalized
    assert normalized.count("'subscriber'") >= len(SUBSCRIBER_POLICIES)
    assert "user_metadata" not in normalized

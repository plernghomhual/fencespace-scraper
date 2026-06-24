import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_tournament_brackets.sql"


def migration_sql() -> str:
    assert MIGRATION.exists(), "tournament brackets migration is missing"
    return MIGRATION.read_text()


def normalized_sql() -> str:
    return " ".join(migration_sql().lower().split())


def column_definition(column_name: str) -> str:
    for line in migration_sql().splitlines():
        line = line.strip().rstrip(",")
        if line.lower().startswith(f"{column_name.lower()} "):
            return " ".join(line.lower().split())
    raise AssertionError(f"{column_name} column is missing")


def assert_nullable(column_name: str) -> None:
    definition = column_definition(column_name)
    assert "not null" not in definition, definition


def test_tournament_brackets_table_defines_required_columns():
    normalized = normalized_sql()

    assert "create table if not exists public.fs_tournament_brackets" in normalized
    assert "id uuid primary key default gen_random_uuid()" in normalized
    assert re.search(
        r"\btournament_id uuid not null references public\.fs_tournaments\(id\)",
        normalized,
    )
    assert "event_id text" in normalized
    assert "event_key text not null" in normalized
    assert "weapon text" in normalized
    assert "gender text" in normalized
    assert "category text" in normalized
    assert "round_name text not null" in normalized
    assert "round_order integer not null" in normalized
    assert "bout_order integer not null" in normalized
    assert "bracket_key text not null" in normalized
    assert "fencer_a_id uuid references public.fs_fencers(id)" in normalized
    assert "fencer_b_id uuid references public.fs_fencers(id)" in normalized
    assert "score_a integer" in normalized
    assert "score_b integer" in normalized
    assert "scores jsonb not null default '{}'::jsonb" in normalized
    assert "winner_id uuid references public.fs_fencers(id)" in normalized
    assert "source text not null default 'unknown'" in normalized
    assert "metadata jsonb not null default '{}'::jsonb" in normalized
    assert "updated_at timestamptz not null default now()" in normalized


def test_tournament_brackets_support_compute_and_api_field_contracts():
    normalized = normalized_sql()

    assert "round_size integer" in normalized
    assert "seed_a integer" in normalized
    assert "seed_b integer" in normalized
    assert "fencer_a_seed integer generated always as (seed_a) stored" in normalized
    assert "fencer_b_seed integer generated always as (seed_b) stored" in normalized
    assert "fencer_a_name text" in normalized
    assert "fencer_a_country text" in normalized
    assert "fencer_b_name text" in normalized
    assert "fencer_b_country text" in normalized
    assert "piste text" in normalized
    assert "source_url text" in normalized
    assert "is_bye boolean not null default false" in normalized


def test_tournament_brackets_unique_keys_enable_idempotent_recompute():
    normalized = normalized_sql()

    assert (
        "constraint fs_tournament_brackets_recompute_key "
        "unique (tournament_id, event_key, round_order, bout_order)"
    ) in normalized
    assert (
        "constraint fs_tournament_brackets_bracket_key_unique unique (bracket_key)"
    ) in normalized
    assert "bracket_key text not null" in normalized


def test_tournament_brackets_indexes_support_detail_page_filters():
    normalized = normalized_sql()

    assert (
        "create index if not exists idx_fs_tournament_brackets_tournament_round "
        "on public.fs_tournament_brackets (tournament_id, round_order, bout_order)"
    ) in normalized
    assert (
        "create index if not exists idx_fs_tournament_brackets_tournament_event_id "
        "on public.fs_tournament_brackets (tournament_id, event_id)"
    ) in normalized
    assert (
        "create index if not exists idx_fs_tournament_brackets_tournament_filters "
        "on public.fs_tournament_brackets (tournament_id, weapon, gender, category)"
    ) in normalized


def test_tournament_brackets_allow_byes_missing_seeds_and_unmatched_fencers():
    for nullable_column in (
        "event_id",
        "weapon",
        "gender",
        "category",
        "round_size",
        "fencer_a_id",
        "fencer_b_id",
        "fencer_a_name",
        "fencer_b_name",
        "fencer_a_country",
        "fencer_b_country",
        "score_a",
        "score_b",
        "winner_id",
        "seed_a",
        "seed_b",
        "piste",
        "source_url",
    ):
        assert_nullable(nullable_column)

    normalized = normalized_sql()
    assert "is_bye boolean not null default false" in normalized
    assert "constraint fs_tournament_brackets_score_a_nonnegative" in normalized
    assert "constraint fs_tournament_brackets_score_b_nonnegative" in normalized
    assert "constraint fs_tournament_brackets_seed_a_positive" in normalized
    assert "constraint fs_tournament_brackets_seed_b_positive" in normalized


def test_tournament_brackets_migration_is_non_destructive_and_safe():
    normalized = normalized_sql()
    forbidden_patterns = (
        r"\bdrop\s+table\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
        r"\balter\s+table\s+\S+\s+drop\b",
        r"\bupdate\s+public\.",
    )

    for pattern in forbidden_patterns:
        assert not re.search(pattern, normalized), pattern

    assert "create table if not exists" in normalized
    assert "create index if not exists" in normalized
    assert "enable row level security" in normalized

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_fencer_stats.sql"


def read_sql() -> str:
    return MIGRATION.read_text()


def normalize(sql: str) -> str:
    return " ".join(sql.lower().split())


def table_body(sql: str, table_name: str) -> str:
    match = re.search(
        rf"create\s+table\s+if\s+not\s+exists\s+public\.{table_name}\s*\(",
        sql,
        flags=re.IGNORECASE,
    )
    assert match, f"missing CREATE TABLE IF NOT EXISTS public.{table_name}"

    depth = 1
    start = match.end()
    for index, char in enumerate(sql[start:], start=start):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return sql[start:index]
    raise AssertionError(f"unterminated CREATE TABLE for {table_name}")


def split_top_level_defs(body: str) -> list[str]:
    parts = []
    depth = 0
    current = []
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            part = " ".join("".join(current).split())
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    final = " ".join("".join(current).split())
    if final:
        parts.append(final)
    return parts


def column_defs(sql: str) -> dict[str, str]:
    body = re.sub(r"--.*$", "", table_body(sql, "fs_fencer_stats"), flags=re.MULTILINE)
    definitions = split_top_level_defs(body)
    columns: dict[str, str] = {}
    for definition in definitions:
        first_token = definition.split(maxsplit=1)[0].strip('"').lower()
        if first_token in {"constraint", "primary", "unique", "check", "foreign"}:
            continue
        columns[first_token] = definition.lower()
    return columns


def test_fencer_stats_migration_defines_identity_scoped_table_and_required_columns():
    sql = read_sql()
    normalized = normalize(sql)
    columns = column_defs(sql)

    assert "create table if not exists public.fs_fencer_stats" in normalized
    assert "references public.fs_fencer_identities(id)" in columns["identity_id"]
    assert "references public.fs_fencers(id)" not in normalized

    expected_fragments = {
        "identity_id": ["uuid", "not null"],
        "weapon": ["text", "not null"],
        "category": ["text", "not null"],
        "total_bouts": ["integer", "not null", "default 0"],
        "wins": ["integer", "not null", "default 0"],
        "losses": ["integer", "not null", "default 0"],
        "touches_scored": ["integer", "not null", "default 0"],
        "touches_received": ["integer", "not null", "default 0"],
        "win_pct": ["numeric(5,2)"],
        "current_streak": ["integer", "not null", "default 0"],
        "longest_win_streak": ["integer", "not null", "default 0"],
        "last_bout_at": ["timestamptz"],
        "updated_at": ["timestamptz", "not null", "default"],
    }
    assert set(expected_fragments).issubset(columns)
    for column, fragments in expected_fragments.items():
        for fragment in fragments:
            assert fragment in columns[column], f"{column} missing {fragment}"


def test_fencer_stats_migration_constrains_counts_and_computes_win_pct():
    normalized = normalize(read_sql())

    assert "total_bouts >= 0" in normalized
    assert "wins >= 0" in normalized
    assert "losses >= 0" in normalized
    assert "touches_scored >= 0" in normalized
    assert "touches_received >= 0" in normalized
    assert "total_bouts = wins + losses" in normalized
    assert "longest_win_streak <= wins" in normalized
    assert "abs(current_streak) <= total_bouts" in normalized
    assert "generated always as" in normalized
    assert "case when total_bouts = 0 then 0" in normalized
    assert "wins::numeric / total_bouts::numeric" in normalized


def test_fencer_stats_migration_defines_stable_keys_and_indexes():
    normalized = normalize(read_sql())

    assert "primary key (identity_id, weapon, category)" in normalized
    assert "create index if not exists fs_fencer_stats_identity_recent_idx" in normalized
    assert "on public.fs_fencer_stats (identity_id, last_bout_at desc)" in normalized
    assert "create index if not exists fs_fencer_stats_weapon_category_win_pct_idx" in normalized
    assert "on public.fs_fencer_stats (weapon, category, win_pct desc)" in normalized
    assert "where total_bouts > 0" in normalized
    assert "create index if not exists fs_fencer_stats_updated_idx" in normalized
    assert "on public.fs_fencer_stats (updated_at desc)" in normalized
    assert "alter table public.fs_fencer_stats enable row level security" in normalized


def test_fencer_stats_migration_documents_foreign_key_scope():
    sql = read_sql().lower()

    assert "--" in sql
    assert "fs_fencer_identities" in sql
    assert "fs_bouts" in sql
    assert "no foreign key" in sql


def test_fencer_stats_migration_is_non_destructive():
    normalized = normalize(read_sql())
    destructive_patterns = [
        r"\bdrop\s+table\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
        r"\balter\s+table\s+[^;]+\s+drop\s+column\b",
        r"\balter\s+table\s+[^;]+\s+drop\s+constraint\b",
    ]

    for pattern in destructive_patterns:
        assert not re.search(pattern, normalized), pattern
    assert "create table if not exists public.fs_fencer_stats" in normalized
    assert normalized.count("create index if not exists") >= 3

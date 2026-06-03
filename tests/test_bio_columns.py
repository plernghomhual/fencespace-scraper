import re
from pathlib import Path


MIGRATION = Path("supabase/migrations/20260602_fencer_bio_columns.sql")
EXPECTED_COLUMNS = {
    "bio": "text",
    "birth_date": "date",
    "birth_place": "text",
    "bio_source": "text",
}


def _sql() -> str:
    return MIGRATION.read_text()


def _normalized(sql: str) -> str:
    return " ".join(sql.lower().split())


def _fs_fencers_alter_body(sql: str) -> str:
    match = re.search(
        r"\balter\s+table\s+public\.fs_fencers\s+(.*?);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, "migration must alter public.fs_fencers"
    return match.group(1)


def _column_definitions(sql: str) -> dict[str, str]:
    body = _fs_fencers_alter_body(sql)
    definitions = re.findall(
        r"\badd\s+column\s+if\s+not\s+exists\s+([a-z_][a-z0-9_]*)\s+([a-z]+)\b",
        body,
        flags=re.IGNORECASE,
    )
    return {name.lower(): sql_type.lower() for name, sql_type in definitions}


def test_migration_adds_expected_bio_columns_with_sql_types():
    assert _column_definitions(_sql()) == EXPECTED_COLUMNS


def test_migration_uses_if_not_exists_for_each_column():
    normalized = _normalized(_sql())

    assert normalized.count("add column if not exists") == len(EXPECTED_COLUMNS)
    for column, sql_type in EXPECTED_COLUMNS.items():
        assert f"add column if not exists {column} {sql_type}" in normalized


def test_migration_only_changes_fs_fencers_table():
    normalized = _normalized(_sql())

    alter_targets = re.findall(
        r"\balter\s+table\s+(?:public\.)?([a-z_][a-z0-9_]*)\b",
        normalized,
    )
    assert alter_targets == ["fs_fencers"]
    assert "create table" not in normalized


def test_migration_has_no_destructive_or_data_rewrite_statements():
    normalized = _normalized(_sql())

    forbidden_patterns = [
        r"\bdrop\b",
        r"\btruncate\b",
        r"\bupdate\b",
        r"\bdelete\b",
        r"\binsert\b",
        r"\bmerge\b",
        r"\bcreate\s+table\s+as\b",
        r"\balter\s+column\b",
        r"\bset\s+not\s+null\b",
        r"\bdefault\b",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, normalized), f"forbidden SQL pattern: {pattern}"

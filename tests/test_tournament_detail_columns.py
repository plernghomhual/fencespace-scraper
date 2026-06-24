import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_tournament_detail_columns.sql"

EXPECTED_COLUMNS = {
    "organizer": "text",
    "entry_deadline": "date",
    "format": "text",
    "quota": "integer",
    "venue_details": "text",
    "registration_url": "text",
    "live_results_url": "text",
    "detail_source": "text",
}


def _migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _normalized_sql() -> str:
    return re.sub(r"\s+", " ", _migration_sql().lower()).strip()


def _added_columns() -> dict[str, str]:
    matches = re.findall(
        r"add\s+column\s+if\s+not\s+exists\s+([a-z_]+)\s+([a-z0-9_]+)",
        _normalized_sql(),
    )
    return dict(matches)


def test_migration_adds_exact_tournament_detail_columns_with_expected_types():
    assert _added_columns() == EXPECTED_COLUMNS


def test_migration_targets_existing_tournaments_table_only():
    sql = _normalized_sql()

    assert "alter table public.fs_tournaments" in sql
    assert "create table" not in sql
    assert "fs_competition_details" not in sql


def test_migration_is_idempotent():
    sql = _normalized_sql()

    assert sql.count("add column if not exists") == len(EXPECTED_COLUMNS)
    assert "create index if not exists idx_fs_tournaments_entry_deadline" in sql
    assert "create index if not exists idx_fs_tournaments_organizer" in sql


def test_migration_indexes_only_queryable_detail_fields():
    sql = _normalized_sql()
    indexes = re.findall(
        r"create\s+index\s+if\s+not\s+exists\s+([a-z0-9_]+)\s+on\s+public\.fs_tournaments\s*\(([^)]+)\)",
        sql,
    )

    assert indexes == [
        ("idx_fs_tournaments_entry_deadline", "entry_deadline"),
        ("idx_fs_tournaments_organizer", "organizer"),
    ]


def test_migration_has_no_destructive_or_backfill_sql():
    sql = _normalized_sql()

    forbidden_patterns = [
        r"\bdrop\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
        r"\binsert\s+into\b",
        r"\bupdate\s+public\.fs_tournaments\b",
        r"\balter\s+column\b",
        r"\brename\s+(column|to)\b",
        r"\bset\s+not\s+null\b",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, sql), pattern

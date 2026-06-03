import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_career_milestones.sql"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _normalized(sql: str) -> str:
    return " ".join(sql.lower().split())


def _table_body(sql: str, table_name: str) -> str:
    match = re.search(
        rf"create\s+table\s+if\s+not\s+exists\s+(?:public\.)?{table_name}\s*\(",
        sql,
        flags=re.IGNORECASE,
    )
    assert match, f"missing CREATE TABLE IF NOT EXISTS for {table_name}"

    start = match.end() - 1
    depth = 0
    in_single_quote = False
    for index, char in enumerate(sql[start:], start=start):
        previous = sql[index - 1] if index > 0 else ""
        if char == "'" and previous != "\\":
            in_single_quote = not in_single_quote
        if in_single_quote:
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return sql[start + 1 : index]

    raise AssertionError(f"unterminated CREATE TABLE for {table_name}")


def _split_top_level_csv(value: str) -> list[str]:
    parts = []
    start = 0
    depth = 0
    in_single_quote = False
    for index, char in enumerate(value):
        previous = value[index - 1] if index > 0 else ""
        if char == "'" and previous != "\\":
            in_single_quote = not in_single_quote
        if in_single_quote:
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    tail = value[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _columns(sql: str) -> dict[str, str]:
    columns = {}
    for entry in _split_top_level_csv(_table_body(sql, "fs_career_milestones")):
        first = entry.split(maxsplit=1)[0].strip('"').lower()
        if first in {"constraint", "primary", "foreign", "unique", "check"}:
            continue
        columns[first] = _normalized(entry)
    return columns


def test_migration_defines_required_career_milestone_columns():
    columns = _columns(_sql())

    expected_columns = {
        "id",
        "identity_id",
        "fencer_id",
        "fie_id",
        "fencer_name",
        "milestone_type",
        "milestone_date",
        "tournament_id",
        "weapon",
        "season",
        "title",
        "description",
        "rank",
        "medal",
        "source",
        "metadata",
        "created_at",
        "person_key",
        "tournament_key",
    }
    assert expected_columns <= columns.keys()

    assert "uuid primary key default gen_random_uuid()" in columns["id"]
    assert "identity_id uuid" in columns["identity_id"]
    assert "references public.fs_fencer_identities(id)" in columns["identity_id"]
    assert "fencer_id uuid" in columns["fencer_id"]
    assert "references public.fs_fencers(id)" in columns["fencer_id"]
    assert "milestone_type text not null" in columns["milestone_type"]
    assert "milestone_date date not null" in columns["milestone_date"]
    assert "tournament_id uuid" in columns["tournament_id"]
    assert "references public.fs_tournaments(id)" in columns["tournament_id"]
    assert "rank integer" in columns["rank"]
    assert "medal text" in columns["medal"]
    assert "metadata jsonb not null default '{}'" in columns["metadata"]
    assert "created_at timestamptz not null" in columns["created_at"]


def test_nullable_tournament_and_optional_result_fields_are_supported():
    columns = _columns(_sql())
    normalized = _normalized(_sql())

    for column in ("identity_id", "fencer_id", "tournament_id", "weapon", "season", "description", "rank", "medal"):
        assert "not null" not in columns[column], f"{column} must stay nullable"

    person_key = re.sub(r"\s+", "", columns["person_key"])
    tournament_key = re.sub(r"\s+", "", columns["tournament_key"])
    assert "generated always as" in columns["person_key"]
    assert "coalesce(identity_id::text,fencer_id::text" in person_key
    assert "generated always as" in columns["tournament_key"]
    assert "coalesce(tournament_id::text,'__no_tournament__')" in tournament_key
    assert "fs_career_milestones_person_required" in normalized
    assert "person_key is not null" in normalized


def test_unique_key_deduplicates_same_person_type_tournament_or_null_tournament_and_date():
    normalized = _normalized(_sql())

    assert "constraint fs_career_milestones_unique_person_type_event_date" in normalized
    assert "unique (person_key, milestone_type, tournament_key, milestone_date)" in normalized
    assert "__no_tournament__" in normalized


def test_indexes_support_fencer_timeline_and_milestone_type_filters():
    normalized = _normalized(_sql())

    assert "create index if not exists idx_fs_career_milestones_identity_timeline" in normalized
    assert "on public.fs_career_milestones (identity_id, milestone_date desc, created_at desc)" in normalized
    assert "where identity_id is not null" in normalized
    assert "create index if not exists idx_fs_career_milestones_fencer_timeline" in normalized
    assert "on public.fs_career_milestones (fencer_id, milestone_date desc, created_at desc)" in normalized
    assert "where fencer_id is not null" in normalized
    assert "create index if not exists idx_fs_career_milestones_type_date" in normalized
    assert "on public.fs_career_milestones (milestone_type, milestone_date desc)" in normalized


def test_migration_is_idempotent_and_rejects_destructive_sql():
    normalized = _normalized(_sql())

    assert normalized.count("create table if not exists public.fs_career_milestones") == 1
    assert normalized.count("create index if not exists") >= 3
    assert "alter table public.fs_career_milestones enable row level security" in normalized

    destructive_patterns = [
        r"\bdrop\s+table\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
        r"\balter\s+table\b[^;]*\bdrop\b",
        r"\bdrop\s+index\b",
    ]
    for pattern in destructive_patterns:
        assert not re.search(pattern, normalized), f"destructive SQL found: {pattern}"

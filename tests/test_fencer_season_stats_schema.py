import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_fencer_season_stats.sql"


def read_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


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
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    in_single_quote = False
    for index, char in enumerate(body):
        previous = body[index - 1] if index > 0 else ""
        if char == "'" and previous != "\\":
            in_single_quote = not in_single_quote
        if not in_single_quote:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
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
    body = re.sub(r"--.*$", "", table_body(sql, "fs_fencer_season_stats"), flags=re.MULTILINE)
    columns: dict[str, str] = {}
    for definition in split_top_level_defs(body):
        first_token = definition.split(maxsplit=1)[0].strip('"').lower()
        if first_token in {"constraint", "primary", "unique", "check", "foreign"}:
            continue
        columns[first_token] = definition.lower()
    return columns


def test_season_stats_migration_defines_identity_scoped_required_columns():
    sql = read_sql()
    normalized = normalize(sql)
    columns = column_defs(sql)

    assert "create table if not exists public.fs_fencer_season_stats" in normalized
    assert "references public.fs_fencer_identities(id)" in columns["fencer_identity_id"]
    assert "references public.fs_fencers(id)" in columns["fencer_id"]
    assert "references public.fs_tournaments(id)" not in normalized

    expected_fragments = {
        "fencer_identity_id": ["uuid", "not null"],
        "fencer_id": ["uuid"],
        "season": ["integer", "not null"],
        "weapon": ["text", "not null"],
        "gender": ["text", "not null"],
        "category": ["text", "not null"],
        "starts": ["integer", "not null", "default 0"],
        "best_finish": ["integer"],
        "medals": ["integer", "not null", "default 0"],
        "gold_medals": ["integer", "not null", "default 0"],
        "silver_medals": ["integer", "not null", "default 0"],
        "bronze_medals": ["integer", "not null", "default 0"],
        "top8_count": ["integer", "not null", "default 0"],
        "top16_count": ["integer", "not null", "default 0"],
        "top32_count": ["integer", "not null", "default 0"],
        "bouts": ["integer", "not null", "default 0"],
        "wins": ["integer", "not null", "default 0"],
        "losses": ["integer", "not null", "default 0"],
        "touches_scored": ["integer", "not null", "default 0"],
        "touches_received": ["integer", "not null", "default 0"],
        "touches": ["integer"],
        "win_pct": ["numeric(5,2)"],
        "rank_delta": ["integer"],
        "updated_at": ["timestamptz", "not null", "default"],
    }
    assert set(expected_fragments).issubset(columns)
    for column, fragments in expected_fragments.items():
        for fragment in fragments:
            assert fragment in columns[column], f"{column} missing {fragment}"


def test_season_stats_uses_fie_end_year_integer_seasons():
    sql = read_sql()
    normalized = normalize(sql)
    columns = column_defs(sql)

    assert columns["season"].startswith("season integer not null")
    assert "fs_fencer_season_stats_season_check" in normalized
    assert "season between 1900 and 2200" in normalized
    assert "season text" not in normalized
    assert "season ~" not in normalized


def test_season_stats_unique_key_matches_aggregation_dimensions():
    normalized = normalize(read_sql())

    assert "constraint fs_fencer_season_stats_pkey primary key" in normalized
    assert (
        "primary key (fencer_identity_id, season, weapon, gender, category)"
        in normalized
    )
    assert "on_conflict=\"fencer_identity_id,season,weapon,gender,category\"" not in normalized


def test_season_stats_counts_are_constrained_and_win_pct_is_generated():
    normalized = normalize(read_sql())

    for fragment in (
        "starts >= 0",
        "medals >= 0",
        "gold_medals >= 0",
        "silver_medals >= 0",
        "bronze_medals >= 0",
        "top8_count >= 0",
        "top16_count >= 0",
        "top32_count >= 0",
        "bouts >= 0",
        "wins >= 0",
        "losses >= 0",
        "touches_scored >= 0",
        "touches_received >= 0",
        "bouts = wins + losses",
        "medals = gold_medals + silver_medals + bronze_medals",
        "top8_count <= top16_count",
        "top16_count <= top32_count",
        "top32_count <= starts",
        "generated always as",
        "touches_scored + touches_received",
        "case when bouts = 0 then 0",
        "wins::numeric / bouts::numeric",
    ):
        assert fragment in normalized


def test_season_stats_indexes_support_fencer_pages_and_leaderboards():
    normalized = normalize(read_sql())

    assert (
        "create index if not exists idx_fs_fencer_season_stats_fencer_detail "
        "on public.fs_fencer_season_stats "
        "(fencer_identity_id, season desc, weapon, gender, category)"
    ) in normalized
    assert (
        "create index if not exists idx_fs_fencer_season_stats_fencer_row_detail "
        "on public.fs_fencer_season_stats (fencer_id, season desc) "
        "where fencer_id is not null"
    ) in normalized
    assert (
        "create index if not exists idx_fs_fencer_season_stats_leaderboard "
        "on public.fs_fencer_season_stats "
        "(season, weapon, gender, category, win_pct desc, best_finish asc nulls last)"
    ) in normalized
    assert (
        "create index if not exists idx_fs_fencer_season_stats_medal_leaderboard "
        "on public.fs_fencer_season_stats "
        "(season, weapon, gender, category, medals desc, top8_count desc)"
    ) in normalized


def test_season_stats_migration_is_idempotent_and_non_destructive():
    normalized = normalize(read_sql())

    assert normalized.count("create table if not exists public.fs_fencer_season_stats") == 1
    assert normalized.count("create index if not exists") >= 4
    assert "alter table public.fs_fencer_season_stats enable row level security" in normalized

    destructive_patterns = [
        r"\bdrop\s+table\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
        r"\balter\s+table\b[^;]*\bdrop\b",
        r"\bdrop\s+index\b",
    ]
    for pattern in destructive_patterns:
        assert not re.search(pattern, normalized), f"destructive SQL found: {pattern}"

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_ranking_sparklines.sql"

EXPECTED_COLUMNS = {
    "fencer_id",
    "fie_fencer_id",
    "source",
    "weapon",
    "gender",
    "category",
    "seasons",
    "ranks",
    "points",
    "history",
    "latest_rank",
    "latest_points",
    "best_rank",
    "worst_rank",
    "delta",
    "sample_count",
    "updated_at",
}

SENSITIVE_COLUMNS = {
    "metadata",
    "scraped_at",
    "scraper_metadata",
    "run_id",
    "raw_payload",
    "request_headers",
    "error",
}


def _sql() -> str:
    assert MIGRATION.exists(), "missing ranking sparkline migration"
    return MIGRATION.read_text()


def _normalized(sql: str) -> str:
    return " ".join(sql.lower().split())


def _final_select(sql: str) -> str:
    match = re.search(
        r"\)\s+select\s+(.*?)\s+from\s+canonical\s+c\b",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, "migration should have a final SELECT from canonical rows"
    return match.group(1)


def _selected_columns(sql: str) -> set[str]:
    columns = set()
    for raw_line in _final_select(sql).splitlines():
        line = raw_line.strip().rstrip(",")
        if not line:
            continue
        alias_match = re.search(r"\bas\s+([a-z_][a-z0-9_]*)$", line, flags=re.IGNORECASE)
        if alias_match:
            columns.add(alias_match.group(1).lower())
            continue
        columns.add(line.rsplit(".", 1)[-1].lower())
    return columns


def test_migration_creates_public_ranking_sparkline_materialized_view():
    sql = _sql()
    normalized = _normalized(sql)

    assert "create materialized view if not exists public.v_ranking_sparklines" in normalized
    assert _selected_columns(sql) == EXPECTED_COLUMNS
    assert SENSITIVE_COLUMNS.isdisjoint(_selected_columns(sql))
    assert "comment on materialized view public.v_ranking_sparklines" in normalized


def test_sparkline_payload_uses_ordered_arrays_and_json_points():
    normalized = _normalized(_sql())

    ordered = "order by c.season asc, c.rank asc, c.points desc nulls last"
    assert f"array_agg(c.season {ordered}) as seasons" in normalized
    assert f"array_agg(c.rank {ordered}) as ranks" in normalized
    assert f"array_agg(c.points {ordered}) as points" in normalized
    assert "jsonb_agg(jsonb_build_object(" in normalized
    assert "'season', c.season" in normalized
    assert "'rank', c.rank" in normalized
    assert "'points', c.points" in normalized
    assert f"{ordered}) as history" in normalized


def test_sparkline_summary_fields_are_computed_from_rank_history():
    normalized = _normalized(_sql())

    assert "l.latest_rank" in normalized
    assert "l.latest_points" in normalized
    assert "min(c.rank) as best_rank" in normalized
    assert "max(c.rank) as worst_rank" in normalized
    assert "(f.first_rank - l.latest_rank) as delta" in normalized
    assert "count(*)::integer as sample_count" in normalized
    assert "max(c.updated_at) as updated_at" in normalized


def test_sparkline_view_dedupes_canonical_history_rows_deterministically():
    normalized = _normalized(_sql())

    assert "from public.fs_rankings_history r" in normalized
    assert "from public.fs_rankings_trends" not in normalized
    assert "from public.fs_national_fed_rankings" not in normalized
    assert "row_number() over" in normalized
    assert "partition by source, fie_fencer_id, season, weapon, gender, category" in normalized
    assert "scraped_at desc nulls last" in normalized
    assert "rank asc nulls last" in normalized
    assert "points desc nulls last" in normalized
    assert "where rn = 1" in normalized


def test_public_access_is_granted_only_on_safe_projection_and_no_destructive_sql():
    normalized = _normalized(_sql())

    assert "revoke all on public.v_ranking_sparklines from public" in normalized
    assert "grant select on public.v_ranking_sparklines to anon, authenticated" in normalized

    destructive_patterns = [
        "drop ",
        "delete from",
        "truncate",
        "update public.fs_rankings_history",
        "insert into public.fs_rankings_history",
        "alter table public.fs_rankings_history",
    ]
    for pattern in destructive_patterns:
        assert pattern not in normalized

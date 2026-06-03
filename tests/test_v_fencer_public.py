import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_v_fencer_public.sql"

REQUIRED_PUBLIC_COLUMNS = {
    "id",
    "name",
    "weapon",
    "category",
    "primary_fencer_id",
    "display_name",
    "country",
    "nationality",
    "gender",
    "weapons",
    "categories",
    "weapon_summary",
    "category_summary",
    "bio",
    "birth_date",
    "birth_place",
    "image_url",
    "headshot_url",
    "wikipedia_url",
    "media_urls",
    "world_rank",
    "fie_points",
    "national_rank",
    "national_rank_points",
    "national_rank_source",
    "national_rank_season",
    "ranking_summary",
    "total_bouts",
    "wins",
    "losses",
    "win_pct",
    "total_competitions",
    "gold_medals",
    "silver_medals",
    "bronze_medals",
    "top8_count",
    "stats_summary",
    "updated_at",
}

BACKWARD_COMPAT_PREFIX = [
    "id",
    "name",
    "country",
    "weapon",
    "category",
    "world_rank",
    "fie_points",
    "image_url",
]

EXCLUDED_PUBLIC_COLUMNS = {
    "metadata",
    "identity_metadata",
    "fie_id",
    "fie_ids",
    "fs_fencer_row_ids",
    "bio_text",
    "bio_source",
    "club",
    "height",
    "weight",
    "reach",
    "hand",
    "handedness",
    "local_image_path",
    "source_url",
    "scraped_at",
    "created_at",
    "raw_payload",
    "api_key",
    "service_key",
    "handle",
    "social_handle",
    "instagram",
    "twitter",
    "facebook",
    "tiktok",
    "threads",
}


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _normalized(sql: str) -> str:
    return " ".join(sql.lower().split())


def _split_top_level_csv(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        current.append(char)

        if quote:
            if char == quote:
                if quote == "'" and next_char == "'":
                    current.append(next_char)
                    index += 1
                else:
                    quote = None
            index += 1
            continue

        if char in {"'", '"'}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            current.pop()
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []

        index += 1

    final = "".join(current).strip()
    if final:
        parts.append(final)
    return parts


def _view_select_body(sql: str, view_name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+view\s+(?:public\.)?{view_name}\s+"
        rf"(?:with\s*\([^)]*\)\s+)?as\s+with\b(?P<body>.*)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing CREATE OR REPLACE VIEW for {view_name}"

    body = match.group("body")
    select_matches = list(re.finditer(
        r"\)\s*select\s+(?P<select>.*?)\s+from\s+identity_summary\s+s\b",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    ))
    assert select_matches, "final view projection should select from identity_summary"
    return select_matches[-1].group("select")


def _view_column_order(sql: str, view_name: str = "v_fencer_public") -> list[str]:
    columns: list[str] = []
    for part in _split_top_level_csv(_view_select_body(sql, view_name)):
        alias = re.search(r"\bas\s+([a-z_][a-z0-9_]*)\s*$", part, flags=re.IGNORECASE)
        if alias:
            columns.append(alias.group(1).lower())
            continue
        columns.append(part.rsplit(".", 1)[-1].strip().strip('"').lower())
    return columns


def _view_columns(sql: str, view_name: str = "v_fencer_public") -> set[str]:
    return set(_view_column_order(sql, view_name))


def test_public_fencer_view_exposes_expected_athlete_fields():
    columns = _view_columns(_sql())

    missing = REQUIRED_PUBLIC_COLUMNS - columns
    assert not missing
    assert EXCLUDED_PUBLIC_COLUMNS.isdisjoint(columns)


def test_public_fencer_view_preserves_existing_column_prefix_for_replace():
    assert _view_column_order(_sql())[: len(BACKWARD_COMPAT_PREFIX)] == BACKWARD_COMPAT_PREFIX


def test_public_fencer_view_uses_security_invoker_and_public_grants():
    normalized = _normalized(_sql())

    assert "create or replace view public.v_fencer_public" in normalized
    assert "security_barrier = true" in normalized
    assert "security_invoker = true" in normalized
    assert "revoke all on public.v_fencer_public from public" in normalized
    assert "grant select on public.v_fencer_public to anon, authenticated" in normalized


def test_public_fencer_view_groups_by_canonical_identity():
    normalized = _normalized(_sql())

    assert "from public.fs_fencer_identities i" in normalized
    assert "join public.fs_fencers f" in normalized
    assert "f.id = any(i.fs_fencer_row_ids)" in normalized
    assert "not exists" in normalized
    assert "partition by identity_id" in normalized
    assert "group by identity_id" in normalized
    assert "array_agg(distinct" in normalized


def test_public_fencer_view_joins_public_safe_summary_sources():
    normalized = _normalized(_sql())

    expected_sources = {
        "public.fs_fencer_stats",
        "public.fs_fencer_career_stats",
        "public.fs_ranking_history_trajectory",
    }
    for source in expected_sources:
        assert source in normalized

    assert "public.fs_fencer_social_media" not in normalized
    assert "fs_scraper_state" not in normalized
    assert "fs_scraper_runs" not in normalized
    assert "fs_api_keys" not in normalized


def test_public_fencer_view_does_not_leak_private_or_internal_fields():
    sql = _sql().lower()
    select_body = _view_select_body(sql, "v_fencer_public")
    normalized_select = _normalized(select_body)

    forbidden_fragments = {
        "metadata",
        "fs_fencer_row_ids",
        "fie_ids",
        "bio_text as bio_text",
        "club",
        "height",
        "weight",
        "local_image_path",
        "handle",
        "service_key",
        "api_key",
    }
    for fragment in forbidden_fragments:
        assert fragment not in normalized_select


def test_public_fencer_view_migration_is_non_destructive():
    normalized = _normalized(_sql())
    destructive_patterns = [
        r"\bdrop\s+table\b",
        r"\bdrop\s+view\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
        r"\balter\s+table\s+[^;]+\s+drop\s+column\b",
        r"\balter\s+table\s+[^;]+\s+drop\s+constraint\b",
    ]

    for pattern in destructive_patterns:
        assert not re.search(pattern, normalized), pattern
    assert "create or replace view public.v_fencer_public" in normalized

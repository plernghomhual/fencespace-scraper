import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-01T12:00:00+00:00"
ALICE = "00000000-0000-0000-0000-000000000001"
BOB = "00000000-0000-0000-0000-000000000002"
CAROL = "00000000-0000-0000-0000-000000000003"
DAN = "00000000-0000-0000-0000-000000000004"
ERIN = "00000000-0000-0000-0000-000000000005"
FRAN = "00000000-0000-0000-0000-000000000006"
GINA = "00000000-0000-0000-0000-000000000007"
IDENTITY_ALICE = "10000000-0000-0000-0000-000000000001"


def test_build_featured_rows_balances_medals_rank_activity_and_completeness():
    from compute_featured_athletes import build_featured_athlete_rows

    fencers = [
        {
            "id": ALICE,
            "fie_id": "111",
            "name": "Alice Example",
            "country": "USA",
            "weapon": "Foil",
            "world_rank": 2,
            "bio": "Olympic and world medalist.",
            "image_url": "https://example.test/alice.jpg",
        },
        {
            "id": BOB,
            "fie_id": "222",
            "name": "Bob No Medal",
            "country": "France",
            "weapon": "Epee",
            "world_rank": 1,
        },
    ]
    identities = [
        {
            "id": IDENTITY_ALICE,
            "canonical_name": "Alice Example",
            "country": "USA",
            "fie_ids": ["111"],
            "fs_fencer_row_ids": [ALICE],
            "metadata": {},
        }
    ]
    stats = [
        {
            "identity_id": IDENTITY_ALICE,
            "weapon": "Foil",
            "category": "Senior",
            "total_bouts": 18,
            "last_bout_at": "2026-05-01T00:00:00+00:00",
        }
    ]
    rankings = [
        {
            "fencer_id": ALICE,
            "fie_fencer_id": "111",
            "season": 2026,
            "country": "USA",
            "weapon": "Foil",
            "category": "Senior",
            "rank": 1,
            "points": 250,
        },
        {
            "fencer_id": BOB,
            "fie_fencer_id": "222",
            "season": 2026,
            "country": "France",
            "weapon": "Epee",
            "category": "Senior",
            "rank": 1,
            "points": 260,
        },
    ]
    tournaments = [
        {"id": "gp-2026", "start_date": "2026-05-20", "weapon": "Foil", "type": "GP"},
        {"id": "wc-2025", "start_date": "2025-12-15", "weapon": "Foil", "type": "WC"},
    ]
    results = [
        {"fencer_id": ALICE, "tournament_id": "gp-2026", "rank": 1, "medal": "Gold"},
        {"fencer_id": ALICE, "tournament_id": "wc-2025", "rank": 2, "medal": "Silver"},
        {"fencer_id": BOB, "tournament_id": "gp-2026", "rank": 9},
    ]

    rows, skipped = build_featured_athlete_rows(
        fencers=fencers,
        identities=identities,
        stats=stats,
        rankings=rankings,
        results=results,
        tournaments=tournaments,
        limit=5,
        updated_at=NOW,
        reference_date=NOW,
    )

    assert skipped == 0
    assert [row["fencer_id"] for row in rows] == [ALICE, BOB]
    alice = rows[0]
    assert alice["candidate_key"] == f"identity:{IDENTITY_ALICE}"
    assert alice["identity_id"] == IDENTITY_ALICE
    assert alice["display_name"] == "Alice Example"
    assert alice["score"] == 121.0
    assert alice["rank_context"] == {
        "best_rank": 1,
        "best_rank_season": 2026,
        "best_rank_weapon": "Foil",
        "best_rank_category": "Senior",
        "points": 250.0,
    }
    assert alice["recency"] == {
        "last_result_date": "2026-05-20",
        "last_bout_at": "2026-05-01T00:00:00+00:00",
        "recent_medals": 2,
        "results_last_365_days": 2,
    }
    assert alice["reasons"] == [
        "recent_gold_medal",
        "recent_silver_medal",
        "top_5_world_rank",
        "active_recent_results",
        "complete_public_profile",
    ]
    assert rows[0]["score"] > rows[1]["score"]


def test_tie_breaking_is_deterministic_by_score_rank_recency_name_and_key():
    from compute_featured_athletes import build_featured_athlete_rows

    fencers = [
        {"id": CAROL, "name": "Zara Tie", "country": "Italy", "weapon": "Sabre", "world_rank": 20},
        {"id": DAN, "name": "Anna Tie", "country": "Canada", "weapon": "Sabre", "world_rank": 20},
    ]
    rankings = [
        {"fencer_id": CAROL, "season": 2026, "rank": 20, "weapon": "Sabre", "category": "Senior"},
        {"fencer_id": DAN, "season": 2026, "rank": 20, "weapon": "Sabre", "category": "Senior"},
    ]

    rows, skipped = build_featured_athlete_rows(
        fencers=fencers,
        identities=[],
        stats=[],
        rankings=rankings,
        results=[],
        tournaments=[],
        limit=5,
        updated_at=NOW,
        reference_date=NOW,
    )

    assert skipped == 0
    assert [(row["display_name"], row["selection_rank"]) for row in rows] == [
        ("Anna Tie", 1),
        ("Zara Tie", 2),
    ]
    assert rows[0]["score"] == rows[1]["score"]


def test_diversity_caps_prevent_country_or_weapon_monopoly_by_default():
    from compute_featured_athletes import build_featured_athlete_rows

    fencers = [
        {"id": ALICE, "name": "Alice USA", "country": "USA", "weapon": "Foil", "world_rank": 1},
        {"id": BOB, "name": "Bob USA", "country": "USA", "weapon": "Foil", "world_rank": 2},
        {"id": CAROL, "name": "Carol USA", "country": "USA", "weapon": "Foil", "world_rank": 3},
        {"id": DAN, "name": "Dan USA", "country": "USA", "weapon": "Foil", "world_rank": 4},
        {"id": ERIN, "name": "Erin Italy", "country": "Italy", "weapon": "Epee", "world_rank": 25},
        {"id": FRAN, "name": "Fran Korea", "country": "Korea", "weapon": "Sabre", "world_rank": 30},
    ]

    rows, skipped = build_featured_athlete_rows(
        fencers=fencers,
        identities=[],
        stats=[],
        rankings=[],
        results=[],
        tournaments=[],
        limit=4,
        max_per_country=2,
        max_per_weapon=2,
        updated_at=NOW,
        reference_date=NOW,
    )

    assert skipped == 0
    assert [row["fencer_id"] for row in rows] == [ALICE, BOB, ERIN, FRAN]
    assert max(sum(1 for row in rows if row["country"] == country) for country in {"USA", "Italy", "Korea"}) <= 2
    assert max(sum(1 for row in rows if row["weapon"] == weapon) for weapon in {"Foil", "Epee", "Sabre"}) <= 2

    uncapped, _ = build_featured_athlete_rows(
        fencers=fencers,
        identities=[],
        stats=[],
        rankings=[],
        results=[],
        tournaments=[],
        limit=4,
        enforce_diversity=False,
        updated_at=NOW,
        reference_date=NOW,
    )
    assert [row["fencer_id"] for row in uncapped] == [ALICE, BOB, CAROL, DAN]


def test_missing_names_retired_and_private_candidates_are_skipped():
    from compute_featured_athletes import build_featured_athlete_rows

    fencers = [
        {"id": ALICE, "name": "", "country": "USA", "weapon": "Foil", "world_rank": 1},
        {"id": BOB, "name": "Retired Fencer", "country": "France", "weapon": "Epee", "world_rank": 2, "retired": True},
        {
            "id": CAROL,
            "name": "Private Fencer",
            "country": "Italy",
            "weapon": "Sabre",
            "world_rank": 3,
            "metadata": {"privacy": "private"},
        },
        {"id": DAN, "name": "Public Fencer", "country": "Canada", "weapon": "Foil", "world_rank": 40},
    ]

    rows, skipped = build_featured_athlete_rows(
        fencers=fencers,
        identities=[],
        stats=[],
        rankings=[],
        results=[],
        tournaments=[],
        limit=10,
        updated_at=NOW,
        reference_date=NOW,
    )

    assert skipped == 3
    assert [row["fencer_id"] for row in rows] == [DAN]
    assert rows[0]["display_name"] == "Public Fencer"


def test_empty_inputs_return_no_rows_and_store_path_does_not_upsert():
    from compute_featured_athletes import build_featured_athlete_rows, compute_featured_athletes

    rows, skipped = build_featured_athlete_rows(
        fencers=[],
        identities=[],
        stats=[],
        rankings=[],
        results=[],
        tournaments=[],
        updated_at=NOW,
        reference_date=NOW,
    )
    assert rows == []
    assert skipped == 0

    client = FakeSupabase(
        {
            "fs_fencers": [],
            "fs_fencer_identities": [],
            "fs_fencer_stats": [],
            "fs_rankings_history": [],
            "fs_results": [],
            "fs_tournaments": [],
        }
    )
    summary = compute_featured_athletes(
        client=client,
        log_run=False,
        update_state=False,
        updated_at=NOW,
        reference_date=NOW,
    )

    assert summary == {
        "fencers_read": 0,
        "identity_rows": 0,
        "stats_read": 0,
        "rankings_read": 0,
        "results_read": 0,
        "tournaments_read": 0,
        "candidate_rows": 0,
        "written": 0,
        "skipped": 0,
    }
    assert client.upserts == []


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.columns = None
        self.range_start = 0
        self.range_end = None
        self.upsert_rows = None
        self.on_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.upsert_rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            if self.name not in self.client.tables:
                raise RuntimeError(f"missing table {self.name}")
            return FakeResult(self.client.tables[self.name][self.range_start : self.range_end + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": list(self.upsert_rows),
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult([])
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_compute_featured_athletes_fetches_sources_and_upserts_candidates():
    from compute_featured_athletes import compute_featured_athletes

    client = FakeSupabase(
        {
            "fs_fencers": [
                {
                    "id": ALICE,
                    "fie_id": "111",
                    "name": "Alice Example",
                    "country": "USA",
                    "weapon": "Foil",
                    "world_rank": 2,
                    "bio": "Bio",
                    "image_url": "https://example.test/alice.jpg",
                }
            ],
            "fs_fencer_identities": [
                {
                    "id": IDENTITY_ALICE,
                    "canonical_name": "Alice Example",
                    "country": "USA",
                    "fie_ids": ["111"],
                    "fs_fencer_row_ids": [ALICE],
                    "metadata": {},
                }
            ],
            "fs_fencer_stats": [
                {
                    "identity_id": IDENTITY_ALICE,
                    "weapon": "Foil",
                    "category": "Senior",
                    "total_bouts": 18,
                    "last_bout_at": "2026-05-01T00:00:00+00:00",
                }
            ],
            "fs_rankings_history": [
                {
                    "fencer_id": ALICE,
                    "fie_fencer_id": "111",
                    "season": 2026,
                    "country": "USA",
                    "weapon": "Foil",
                    "category": "Senior",
                    "rank": 1,
                    "points": 250,
                }
            ],
            "fs_results": [
                {"fencer_id": ALICE, "tournament_id": "gp-2026", "rank": 1, "medal": "Gold"},
            ],
            "fs_tournaments": [
                {"id": "gp-2026", "start_date": "2026-05-20", "weapon": "Foil", "type": "GP"},
            ],
        }
    )

    summary = compute_featured_athletes(
        client=client,
        page_size=2,
        log_run=False,
        update_state=False,
        updated_at=NOW,
        reference_date=NOW,
    )

    assert summary == {
        "fencers_read": 1,
        "identity_rows": 1,
        "stats_read": 1,
        "rankings_read": 1,
        "results_read": 1,
        "tournaments_read": 1,
        "candidate_rows": 1,
        "written": 1,
        "skipped": 0,
    }
    assert ("fs_featured_athlete_candidates", "candidate_key") in {
        (call["table"], call["on_conflict"]) for call in client.upserts
    }
    row = client.upserts[0]["rows"][0]
    assert row["candidate_key"] == f"identity:{IDENTITY_ALICE}"
    assert row["selection_rank"] == 1
    assert row["selected"] is True
    assert row["reasons"][0] == "recent_gold_medal"


def normalize(sql: str) -> str:
    return " ".join(sql.lower().split())


def test_featured_athletes_migration_defines_public_safe_candidate_table_and_view():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_featured_athletes.sql"

    sql = migration.read_text()
    normalized = normalize(sql)

    assert "create table if not exists public.fs_featured_athlete_candidates" in normalized
    assert "candidate_key text primary key" in normalized
    assert "identity_id uuid references public.fs_fencer_identities(id)" in normalized
    assert "fencer_id uuid not null references public.fs_fencers(id)" in normalized
    assert "display_name text not null" in normalized
    assert "score numeric(8,3) not null" in normalized
    assert "reasons jsonb not null default '[]'::jsonb" in normalized
    assert "rank_context jsonb not null default '{}'::jsonb" in normalized
    assert "recency jsonb not null default '{}'::jsonb" in normalized
    assert "country text" in normalized
    assert "weapon text" in normalized
    assert "selection_rank integer" in normalized
    assert "updated_at timestamptz not null" in normalized
    assert "alter table public.fs_featured_athlete_candidates enable row level security" in normalized
    assert "create or replace view public.v_featured_athletes_public" in normalized
    assert "where selected = true" in normalized
    assert "grant select on public.v_featured_athletes_public to anon, authenticated" in normalized
    view_select = re.search(
        r"create\s+or\s+replace\s+view\s+public\.v_featured_athletes_public\s+"
        r"(?:with\s*\([^)]*\)\s+)?as\s+select\s+(.*?)\s+from\s+",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert view_select, "missing public view select list"
    assert "metadata" not in view_select.group(1).lower()


def test_featured_athletes_migration_is_additive_and_non_destructive():
    root = Path(__file__).resolve().parents[1]
    sql = normalize((root / "supabase" / "migrations" / "20260602_featured_athletes.sql").read_text())

    destructive_patterns = [
        r"\bdrop\s+table\b",
        r"\btruncate\b",
        r"\bdelete\s+from\b",
        r"\balter\s+table\s+[^;]+\s+drop\s+column\b",
        r"\balter\s+table\s+[^;]+\s+drop\s+constraint\b",
    ]
    for pattern in destructive_patterns:
        assert not re.search(pattern, sql), pattern
    assert "create index if not exists fs_featured_athlete_candidates_score_idx" in sql
    assert "create index if not exists fs_featured_athlete_candidates_diversity_idx" in sql

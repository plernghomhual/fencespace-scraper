import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


MIGRATION = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "20260602_national_rank.sql"


def test_migration_adds_four_idempotent_columns_and_safe_index():
    sql = MIGRATION.read_text()
    lowered = sql.lower()

    assert "drop " not in lowered
    assert "truncate " not in lowered
    assert "delete from" not in lowered

    expected_columns = {
        "national_rank": "integer",
        "national_rank_points": "numeric",
        "national_rank_source": "text",
        "national_rank_season": "text",
    }
    for column, column_type in expected_columns.items():
        pattern = rf"alter\s+table\s+(?:public\.)?fs_fencers\s+add\s+column\s+if\s+not\s+exists\s+{column}\s+{column_type}"
        assert re.search(pattern, lowered), column

    assert "create index if not exists" in lowered
    assert "fs_fencers" in lowered
    assert "national_rank" in lowered


def test_select_latest_rankings_normalizes_mixed_seasons_per_group():
    from scripts.backfill_national_rank import select_latest_rankings

    rows = [
        {
            "id": "old",
            "source": "british_fencing",
            "country": "Great Britain",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "season": 2025,
            "rank": 7,
        },
        {
            "id": "current-range",
            "source": "british_fencing",
            "country": "Great Britain",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "season": "2025-2026",
            "rank": 3,
        },
        {
            "id": "current-year",
            "source": "british_fencing",
            "country": "Great Britain",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "season": "2026",
            "rank": 4,
        },
        {
            "id": "other-country",
            "source": "british_fencing",
            "country": "Ireland",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "season": "2024-2025",
            "rank": 1,
        },
        {
            "id": "invalid-season",
            "source": "british_fencing",
            "country": "Great Britain",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "season": "2026/27",
            "rank": 1,
        },
    ]

    selected, stats = select_latest_rankings(rows)

    assert [row["id"] for row in selected] == ["current-range", "current-year", "other-country"]
    assert {row["season"] for row in selected if row["country"] == "Great Britain"} == {"2025-2026"}
    assert stats["ranking_rows_read"] == 5
    assert stats["selected_rankings"] == 3
    assert stats["skipped_invalid_season"] == 1


def test_build_update_payloads_matches_identities_and_skips_unsafe_overwrites():
    from scripts.backfill_national_rank import build_update_payloads

    fencers = [
        {"id": "gb-row-1", "fie_id": "1001", "name": "Alice Smith", "country": "Great Britain", "weapon": "Foil", "category": "Women's Senior"},
        {"id": "gb-row-2", "fie_id": "1001", "name": "A. Smith", "country": "Great Britain", "weapon": "Foil", "category": "Women's Senior"},
        {"id": "fie-only", "fie_id": "2002", "name": "Bob Lee", "country": "Canada", "weapon": "Epee", "category": "Men's Senior"},
        {"id": "ambiguous-1", "fie_id": "3001", "name": "Jordan Lee", "country": "United States", "weapon": "Sabre", "category": "Men's Senior"},
        {"id": "ambiguous-2", "fie_id": "3002", "name": "Jordan Lee", "country": "United States", "weapon": "Sabre", "category": "Men's Senior"},
        {
            "id": "current-other-source",
            "fie_id": "4004",
            "name": "Current Rank",
            "country": "France",
            "weapon": "Foil",
            "category": "Women's Senior",
            "national_rank": 2,
            "national_rank_source": "ffe",
            "national_rank_season": "2025-2026",
        },
        {
            "id": "newer-existing",
            "fie_id": "5005",
            "name": "Newer Existing",
            "country": "Italy",
            "weapon": "Epee",
            "category": "Men's Senior",
            "national_rank": 1,
            "national_rank_source": "italy",
            "national_rank_season": "2025-2026",
        },
    ]
    identities = [
        {
            "id": "identity-gb",
            "canonical_name": "Alice Smith",
            "country": "Great Britain",
            "fie_ids": ["1001"],
            "fs_fencer_row_ids": ["gb-row-1", "gb-row-2"],
        }
    ]
    rankings = [
        {
            "id": "r-identity",
            "fencer_id": "gb-row-1",
            "source": "british_fencing",
            "country": "Great Britain",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "season": "2025-2026",
            "rank": 3,
            "points": "101.5",
        },
        {
            "id": "r-fie",
            "fie_id": "2002",
            "source": "canada",
            "country": "Canada",
            "weapon": "Epee",
            "gender": "Men",
            "category": "Senior",
            "season": "2025-2026",
            "rank": 9,
            "points": 88,
        },
        {
            "id": "r-ambiguous",
            "name": "Jordan Lee",
            "source": "usa",
            "country": "United States",
            "weapon": "Sabre",
            "gender": "Men",
            "category": "Senior",
            "season": "2025-2026",
            "rank": 11,
        },
        {
            "id": "r-current-other-source",
            "fie_id": "4004",
            "source": "other_france",
            "country": "France",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "season": "2025-2026",
            "rank": 1,
        },
        {
            "id": "r-stale",
            "fie_id": "5005",
            "source": "italy",
            "country": "Italy",
            "weapon": "Epee",
            "gender": "Men",
            "category": "Senior",
            "season": "2024-2025",
            "rank": 4,
        },
    ]

    payloads, stats = build_update_payloads(rankings, fencers, identities)

    by_id = {row["id"]: row for row in payloads}
    assert set(by_id) == {"gb-row-1", "gb-row-2", "fie-only"}
    assert by_id["gb-row-1"] == {
        "id": "gb-row-1",
        "national_rank": 3,
        "national_rank_points": 101.5,
        "national_rank_source": "british_fencing",
        "national_rank_season": "2025-2026",
    }
    assert by_id["gb-row-2"]["national_rank"] == 3
    assert by_id["fie-only"]["national_rank_source"] == "canada"
    assert stats["matched_rankings"] == 2
    assert stats["unmatched_rankings"] == 3
    assert stats["skipped_ambiguous"] == 1
    assert stats["skipped_current_conflict"] == 1
    assert stats["skipped_stale"] == 1


def test_build_update_payloads_prefers_higher_confidence_for_same_fencer():
    from scripts.backfill_national_rank import build_update_payloads

    fencers = [
        {"id": "same-fencer", "fie_id": "9009", "name": "Chris Park", "country": "Korea", "weapon": "Sabre", "category": "Men's Senior"},
    ]
    rankings = [
        {
            "id": "low-confidence",
            "name": "Chris Park",
            "source": "korea",
            "country": "Korea",
            "weapon": "Sabre",
            "gender": "Men",
            "category": "Senior",
            "season": "2025-2026",
            "rank": 6,
        },
        {
            "id": "high-confidence",
            "fie_id": "9009",
            "source": "korea",
            "country": "Korea",
            "weapon": "Sabre",
            "gender": "Men",
            "category": "Senior",
            "season": "2025-2026",
            "rank": 4,
        },
    ]

    payloads, stats = build_update_payloads(rankings, fencers, [])

    assert payloads == [
        {
            "id": "same-fencer",
            "national_rank": 4,
            "national_rank_points": None,
            "national_rank_source": "korea",
            "national_rank_season": "2025-2026",
        }
    ]
    assert stats["skipped_lower_confidence"] == 1


def test_backfill_missing_rankings_records_skips_without_upsert():
    from scripts.backfill_national_rank import backfill_national_rank

    client = FakeSupabase(
        {
            "fs_national_fed_rankings": [],
            "fs_fencers": [{"id": "f1", "fie_id": "1", "name": "No Ranking", "country": "France"}],
            "fs_fencer_identities": [],
        }
    )

    summary = backfill_national_rank(client, page_size=50, batch_size=2)

    assert summary.written == 0
    assert summary.skipped == 0
    assert client.upserts == []


def test_backfill_fetches_current_rankings_and_upserts_payloads():
    from scripts.backfill_national_rank import backfill_national_rank

    client = FakeSupabase(
        {
            "fs_national_fed_rankings": [
                {
                    "id": "old",
                    "source": "british_fencing",
                    "country": "Great Britain",
                    "weapon": "Foil",
                    "gender": "Women",
                    "category": "Senior",
                    "season": "2024-2025",
                    "rank": 8,
                    "fie_id": "1001",
                },
                {
                    "id": "new",
                    "source": "british_fencing",
                    "country": "Great Britain",
                    "weapon": "Foil",
                    "gender": "Women",
                    "category": "Senior",
                    "season": "2025-2026",
                    "rank": 2,
                    "points": 155.25,
                    "fie_id": "1001",
                },
            ],
            "fs_fencers": [
                {"id": "f1", "fie_id": "1001", "name": "Alice Smith", "country": "Great Britain", "weapon": "Foil", "category": "Women's Senior"},
            ],
            "fs_fencer_identities": [],
        }
    )

    summary = backfill_national_rank(client, page_size=50, batch_size=2)

    assert summary.written == 1
    assert summary.skipped == 0
    assert [call["table"] for call in client.selects] == [
        "fs_national_fed_rankings",
        "fs_fencers",
        "fs_fencer_identities",
    ]
    assert client.upserts == [
        {
            "table": "fs_fencers",
            "rows": [
                {
                    "id": "f1",
                    "national_rank": 2,
                    "national_rank_points": 155.25,
                    "national_rank_source": "british_fencing",
                    "national_rank_season": "2025-2026",
                }
            ],
            "on_conflict": "id",
        }
    ]


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.columns = None
        self.filters = []
        self.range_start = None
        self.range_end = None
        self.rows = None
        self.on_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            rows = list(self.client.tables.get(self.name, []))
            for column, value in self.filters:
                rows = [row for row in rows if row.get(column) == value]
            if self.range_start is not None and self.range_end is not None:
                rows = rows[self.range_start : self.range_end + 1]
            self.client.selects.append({"table": self.name, "columns": self.columns, "filters": self.filters})
            return FakeResult(rows)
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
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

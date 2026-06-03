from pathlib import Path

import pytest

from compute_junior_conversion import build_junior_conversion_report, compute_junior_conversion


IDENTITY_A = "00000000-0000-0000-0000-0000000000a0"
ROW_A_JUNIOR = "00000000-0000-0000-0000-0000000000a1"
ROW_A_SENIOR = "00000000-0000-0000-0000-0000000000a2"
IDENTITY_B = "00000000-0000-0000-0000-0000000000b0"
ROW_B = "00000000-0000-0000-0000-0000000000b1"
IDENTITY_C = "00000000-0000-0000-0000-0000000000c0"
ROW_C = "00000000-0000-0000-0000-0000000000c1"
NOW = "2026-06-02T12:00:00+00:00"


def row_by_window(rows, *, country, weapon, gender, category, season, window):
    matches = [
        row
        for row in rows
        if row["country"] == country
        and row["weapon"] == weapon
        and row["gender"] == gender
        and row["category"] == category
        and row["cohort_season"] == season
        and row["window_years"] == window
    ]
    assert len(matches) == 1
    return matches[0]


def test_conversion_report_links_canonical_identity_and_counts_country_transfer():
    report = build_junior_conversion_report(
        rankings=[
            {
                "fie_fencer_id": "1001",
                "season": "2024",
                "country": "USA",
                "weapon": "foil",
                "gender": "F",
                "category": "Junior",
                "rank": 7,
            },
            {
                "fie_fencer_id": "2001",
                "season": 2025,
                "country": "Canada",
                "weapon": "Foil",
                "gender": "Women",
                "category": "Senior",
                "rank": 12,
            },
        ],
        results=[
            {
                "fencer_id": ROW_A_SENIOR,
                "tournament_id": "senior-worlds-2025",
                "country": "Canada",
                "rank": 3,
            },
        ],
        tournaments=[
            {
                "id": "senior-worlds-2025",
                "season": "2025",
                "weapon": "Foil",
                "gender": "Women",
                "category": "Senior",
                "start_date": "2025-04-01",
            },
        ],
        fencers=[
            {"id": ROW_A_JUNIOR, "fie_id": "1001", "country": "USA"},
            {"id": ROW_A_SENIOR, "fie_id": "2001", "country": "Canada"},
        ],
        identities=[
            {
                "id": IDENTITY_A,
                "fs_fencer_row_ids": [ROW_A_JUNIOR, ROW_A_SENIOR],
                "fie_ids": ["1001", "2001"],
                "country": "USA",
            },
        ],
        windows=(1,),
        computed_at=NOW,
    )

    assert report["skipped"] == {
        "without_identity": 0,
        "without_country": 0,
        "without_weapon": 0,
        "without_category": 0,
        "without_season": 0,
        "non_junior_or_senior": 0,
    }
    row = row_by_window(
        report["rows"],
        country="United States",
        weapon="Foil",
        gender="Women's",
        category="Women's Junior",
        season=2024,
        window=1,
    )
    assert row["sample_count"] == 1
    assert row["senior_appearance_count"] == 1
    assert row["senior_appearance_rate"] == 100.0
    assert row["senior_ranking_count"] == 1
    assert row["senior_ranking_rate"] == 100.0
    assert row["senior_medal_count"] == 1
    assert row["senior_medal_rate"] == 100.0
    assert row["senior_top8_count"] == 1
    assert row["senior_top8_rate"] == 100.0
    assert row["senior_top16_count"] == 1
    assert row["senior_top16_rate"] == 100.0
    assert row["country_transfer_count"] == 1
    assert row["country_transfer_rate"] == 100.0
    assert row["metadata"]["cohort_fencer_ids"] == [IDENTITY_A]
    assert row["metadata"]["window_start_season"] == 2025
    assert row["metadata"]["window_end_season"] == 2025
    assert row["computed_at"] == NOW


def test_conversion_windows_exclude_same_season_and_count_later_windows():
    report = build_junior_conversion_report(
        rankings=[
            {
                "fencer_id": ROW_B,
                "season": 2022,
                "country": "Italy",
                "weapon": "Epee",
                "gender": "Men",
                "category": "Junior",
                "rank": 4,
            },
            {
                "fencer_id": ROW_B,
                "season": 2022,
                "country": "Italy",
                "weapon": "Epee",
                "gender": "Men",
                "category": "Senior",
                "rank": 99,
            },
            {
                "fencer_id": ROW_B,
                "season": 2024,
                "country": "Italy",
                "weapon": "Epee",
                "gender": "Men",
                "category": "Senior",
                "rank": 16,
            },
        ],
        results=[],
        tournaments=[],
        fencers=[{"id": ROW_B, "fie_id": "3001"}],
        identities=[{"id": IDENTITY_B, "fs_fencer_row_ids": [ROW_B], "fie_ids": ["3001"]}],
        windows=(1, 2),
        computed_at=NOW,
    )

    one_year = row_by_window(
        report["rows"],
        country="Italy",
        weapon="Epee",
        gender="Men's",
        category="Men's Junior",
        season=2022,
        window=1,
    )
    two_year = row_by_window(
        report["rows"],
        country="Italy",
        weapon="Epee",
        gender="Men's",
        category="Men's Junior",
        season=2022,
        window=2,
    )

    assert one_year["senior_appearance_count"] == 0
    assert one_year["senior_appearance_rate"] == 0.0
    assert two_year["senior_appearance_count"] == 1
    assert two_year["senior_ranking_count"] == 1
    assert two_year["senior_top16_count"] == 1
    assert two_year["senior_top8_count"] == 0


def test_cohort_detection_dedupes_sources_and_reports_sparse_skips():
    report = build_junior_conversion_report(
        rankings=[
            {
                "fie_fencer_id": "4001",
                "season": "2025-2026",
                "country": "France",
                "weapon": "Sabre",
                "gender": "Women",
                "category": "Junior",
                "rank": 2,
            },
            {
                "fie_fencer_id": "4001",
                "season": 2026,
                "country": "France",
                "weapon": "Sabre",
                "gender": "Women",
                "category": "Junior",
                "rank": 1,
            },
            {
                "fie_fencer_id": "",
                "season": 2026,
                "country": "France",
                "weapon": "Sabre",
                "gender": "Women",
                "category": "Junior",
                "rank": 9,
            },
            {
                "fie_fencer_id": "4001",
                "season": 2026,
                "country": "France",
                "weapon": "Sabre",
                "gender": "Women",
                "rank": 9,
            },
        ],
        results=[
            {
                "fencer_id": ROW_C,
                "tournament_id": "junior-worlds-2026",
                "country": "France",
                "rank": 5,
            },
        ],
        tournaments=[
            {
                "id": "junior-worlds-2026",
                "season": 2026,
                "weapon": "Sabre",
                "gender": "Women",
                "category": "Junior",
                "start_date": "2026-03-01",
            },
        ],
        fencers=[{"id": ROW_C, "fie_id": "4001"}],
        identities=[{"id": IDENTITY_C, "fs_fencer_row_ids": [ROW_C], "fie_ids": ["4001"]}],
        windows=(1,),
        computed_at=NOW,
    )

    row = row_by_window(
        report["rows"],
        country="France",
        weapon="Sabre",
        gender="Women's",
        category="Women's Junior",
        season=2026,
        window=1,
    )

    assert row["sample_count"] == 1
    assert row["junior_result_count"] == 1
    assert row["junior_ranking_count"] == 1
    assert report["skipped"]["without_identity"] == 1
    assert report["skipped"]["without_category"] == 1


def test_result_rows_with_null_dimensions_fall_back_to_tournament_context():
    report = build_junior_conversion_report(
        rankings=[],
        results=[
            {
                "fencer_id": ROW_B,
                "tournament_id": "junior-2024",
                "country": "Germany",
                "weapon": None,
                "gender": None,
                "category": None,
                "season": None,
                "rank": 6,
            },
            {
                "fencer_id": ROW_B,
                "tournament_id": "senior-2025",
                "country": "Germany",
                "weapon": None,
                "gender": None,
                "category": None,
                "season": None,
                "rank": 8,
            },
        ],
        tournaments=[
            {
                "id": "junior-2024",
                "season": 2024,
                "weapon": "Epee",
                "gender": "Men",
                "category": "Junior",
            },
            {
                "id": "senior-2025",
                "season": 2025,
                "weapon": "Epee",
                "gender": "Men",
                "category": "Senior",
            },
        ],
        fencers=[{"id": ROW_B, "fie_id": "3001"}],
        identities=[{"id": IDENTITY_B, "fs_fencer_row_ids": [ROW_B], "fie_ids": ["3001"]}],
        windows=(1,),
        computed_at=NOW,
    )

    row = row_by_window(
        report["rows"],
        country="Germany",
        weapon="Epee",
        gender="Men's",
        category="Men's Junior",
        season=2024,
        window=1,
    )

    assert row["sample_count"] == 1
    assert row["junior_result_count"] == 1
    assert row["senior_appearance_count"] == 1
    assert row["senior_top8_count"] == 1
    assert report["skipped"] == {
        "without_identity": 0,
        "without_country": 0,
        "without_weapon": 0,
        "without_category": 0,
        "without_season": 0,
        "non_junior_or_senior": 0,
    }


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.start = 0
        self.end = 999
        self.pending_upsert = None
        self.pending_conflict = None

    def select(self, columns):
        self.client.selects.append((self.table_name, columns))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def limit(self, _n):
        return self

    def upsert(self, rows, on_conflict):
        self.pending_upsert = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.pending_upsert is not None:
            self.client.upserts.append(
                {
                    "table": self.table_name,
                    "rows": self.pending_upsert,
                    "on_conflict": self.pending_conflict,
                }
            )
            return FakeResult([])
        if self.table_name == "fs_junior_conversion_rates":
            return FakeResult([])
        table = self.client.tables.get(self.table_name, [])
        return FakeResult(table[self.start : self.end + 1])


class FakeClient:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_compute_junior_conversion_fetches_inputs_and_upserts_rates():
    client = FakeClient(
        {
            "fs_rankings_history": [
                {
                    "fie_fencer_id": "1001",
                    "season": 2024,
                    "country": "USA",
                    "weapon": "Foil",
                    "gender": "Women",
                    "category": "Junior",
                    "rank": 7,
                },
                {
                    "fie_fencer_id": "1001",
                    "season": 2025,
                    "country": "USA",
                    "weapon": "Foil",
                    "gender": "Women",
                    "category": "Senior",
                    "rank": 10,
                },
            ],
            "fs_results": [],
            "fs_tournaments": [],
            "fs_fencers": [{"id": ROW_A_JUNIOR, "fie_id": "1001"}],
            "fs_fencer_identities": [
                {"id": IDENTITY_A, "fs_fencer_row_ids": [ROW_A_JUNIOR], "fie_ids": ["1001"]}
            ],
        }
    )

    summary = compute_junior_conversion(
        client=client,
        windows=(1,),
        computed_at=NOW,
        log_run=False,
        update_state=False,
    )

    assert summary["rankings_read"] == 2
    assert summary["results_read"] == 0
    assert summary["identity_rows"] == 1
    assert summary["rows_written"] == 1
    assert summary["failed"] == 0
    assert summary["skipped_without_identity"] == 0
    assert ("fs_rankings_history", "fencer_id,fie_fencer_id,season,country,weapon,gender,category,rank,points,name,scraped_at") in client.selects
    assert ("fs_junior_conversion_rates", "country") in client.selects
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_junior_conversion_rates"
    assert upsert["on_conflict"] == "country,weapon,gender,category,cohort_season,window_years"
    assert upsert["rows"][0]["sample_count"] == 1


def test_junior_conversion_migration_defines_rate_table_and_conflict_key():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_junior_conversion.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_junior_conversion_rates" in normalized
    assert "primary key (country, weapon, gender, category, cohort_season, window_years)" in normalized
    assert "sample_count integer not null" in normalized
    assert "senior_appearance_rate numeric" in normalized

import os
import sys
from pathlib import Path
from typing import Any, cast

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


TOURNAMENT_ID = "00000000-0000-0000-0000-000000000065"

FIE_DETAIL_HTML = """
<html><head><script>
window.__translations__ = {};
window._competition = {
  "competitionId": 145,
  "name": "Grand Prix",
  "season": 2025,
  "type": "individual",
  "fencerCount": 212,
  "coachCount": 35,
  "invitationUrl": "https://static.fie.org/uploads/36/180643-Fencing%20Grand%20Prix%20Shanghai20250326.pdf",
  "regulationUrl": null
};
window._athletes = [
  {"fencer": {"name": "LECHNER Moritz", "nationality": "AUT"}},
  {"fencer": {"name": "CHOI Chi Lok", "nationality": "HKG"}},
  {"fencer": {"name": "HAYASHI Shoren", "nationality": "JPN"}},
  {"fencer": {"name": "Other Athlete", "nationality": "JPN"}}
];
window._pools = {
  "pools": [
    {"poolId": 1, "piste": "blue", "rows": [
      {"rank": 1}, {"rank": 2}, {"rank": 3}, {"rank": 4}, {"rank": 5}, {"rank": 6}, {"rank": 7}
    ]},
    {"poolId": 2, "piste": "red", "rows": [
      {"rank": 1}, {"rank": 2}, {"rank": 3}, {"rank": 4}, {"rank": 5}, {"rank": 6}, {"rank": 7}
    ]}
  ]
};
window._tableau = [
  {"suiteTableId": "SuiteTab_A", "rounds": {"A128": [], "A64": [], "A32": []}}
];
window._downloadLinks = {
  "entriesPdf": "/competition/2025/145/entry/pdf?lang=en"
};
</script></head><body></body></html>
"""

INVITATION_TEXT = """
Fencing Grand Prix Shanghai
Entry fees:
Individual competition - EUR 100.

Prize Money
1st place EUR 5,000
2nd place EUR 3,000
3rd place EUR 1,000
"""


def test_parse_competition_detail_extracts_format_counts_and_money():
    from scrape_competition_details import parse_competition_detail_page

    row = parse_competition_detail_page(
        FIE_DETAIL_HTML,
        tournament_id=TOURNAMENT_ID,
        source_url="https://fie.org/competitions/2025/145",
        document_texts=[INVITATION_TEXT],
    )

    assert row["tournament_id"] == TOURNAMENT_ID
    assert row["participant_count"] == 212
    assert row["countries_represented"] == 3
    assert row["format_type"] == "pools + direct elimination"
    assert row["pool_size"] == 7
    assert row["de_rounds"] == 3
    assert row["entry_fee"] == pytest.approx(100.0)
    assert row["prize_pool"] == pytest.approx(9000.0)
    assert row["currency"] == "EUR"
    assert row["metadata"]["competition_id"] == 145
    assert row["metadata"]["pool_count"] == 2
    assert row["metadata"]["pool_sizes"] == [7, 7]
    assert row["metadata"]["de_round_names"] == ["A128", "A64", "A32"]
    assert row["metadata"]["document_urls"] == [
        "https://static.fie.org/uploads/36/180643-Fencing%20Grand%20Prix%20Shanghai20250326.pdf"
    ]


def test_parse_competition_detail_handles_missing_optional_blocks():
    from scrape_competition_details import parse_competition_detail_page

    html = """
    <script>
    window._competition = {"competitionId": 999, "name": "No Results", "type": "individual"};
    window._athletes = [];
    </script>
    """

    row = parse_competition_detail_page(html, tournament_id=TOURNAMENT_ID)

    assert row["participant_count"] is None
    assert row["countries_represented"] is None
    assert row["format_type"] is None
    assert row["pool_size"] is None
    assert row["de_rounds"] is None
    assert row["entry_fee"] is None
    assert row["prize_pool"] is None
    assert row["currency"] is None


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.start = 0
        self.end = 999
        self.not_null_columns = []
        self.pending_upsert = None
        self.pending_conflict = None

    def select(self, columns):
        self.client.selects.append((self.table_name, columns))
        return self

    @property
    def not_(self):
        return self

    def is_(self, column, value):
        assert value == "null"
        self.not_null_columns.append(column)
        self.client.not_null_filters.append((self.table_name, column))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, row, on_conflict):
        self.pending_upsert = row
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.pending_upsert is not None:
            self.client.upserts.append(
                (self.table_name, self.pending_upsert, self.pending_conflict)
            )
            return FakeResult([self.pending_upsert])

        rows = list(self.client.tables[self.table_name])
        for column in self.not_null_columns:
            rows = [row for row in rows if row.get(column) is not None]
        return FakeResult(rows[self.start : self.end + 1])


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "fs_competition_details": [
                {"tournament_id": "existing-tournament"},
            ],
            "fs_tournaments": [
                {
                    "id": TOURNAMENT_ID,
                    "fie_id": 145,
                    "competition_url_id": 145,
                    "season": "2025",
                    "name": "Grand Prix",
                },
                {
                    "id": "no-fie-id",
                    "fie_id": None,
                    "competition_url_id": None,
                    "season": "2025",
                    "name": "Domestic Event",
                },
                {
                    "id": "existing-tournament",
                    "fie_id": 146,
                    "competition_url_id": 146,
                    "season": "2025",
                    "name": "Already Scraped",
                },
            ],
        }
        self.selects = []
        self.not_null_filters = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_find_tournaments_needing_details_filters_existing_and_requires_fie_id():
    from scrape_competition_details import find_tournaments_needing_details

    fake = FakeSupabase()

    rows = find_tournaments_needing_details(fake)

    tables = cast(dict[str, list[dict[str, Any]]], fake.tables)
    assert rows == [tables["fs_tournaments"][0]]
    assert ("fs_tournaments", "fie_id") in fake.not_null_filters


def test_scrape_competition_details_upserts_parsed_rows():
    from scrape_competition_details import scrape_competition_details

    fake = FakeSupabase()

    result = scrape_competition_details(
        client=fake,
        fetch_html=lambda season, url_id: FIE_DETAIL_HTML,
        fetch_document_texts=lambda urls: [INVITATION_TEXT],
        log_run=False,
        update_state=False,
        sleep=lambda _seconds: None,
    )

    assert result == {"processed": 1, "written": 1, "failed": 0, "skipped": 0}
    assert len(fake.upserts) == 1
    table_name, row, conflict = fake.upserts[0]
    assert table_name == "fs_competition_details"
    assert conflict == "tournament_id"
    assert row["tournament_id"] == TOURNAMENT_ID
    assert row["participant_count"] == 212
    assert row["prize_pool"] == pytest.approx(9000.0)
    assert row["metadata"]["source_url"] == "https://fie.org/competitions/2025/145"


def test_competition_details_migration_defines_table_and_conflict_key():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260601_competition_details.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_competition_details" in normalized
    assert "tournament_id uuid unique references public.fs_tournaments(id)" in normalized
    assert "metadata jsonb default '{}'::jsonb" in normalized
    assert "create index if not exists fs_competition_details_tournament_id_idx" in normalized

import os
import sys
from typing import Any, cast

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


TOURNAMENT_ID = "00000000-0000-0000-0000-000000000145"
LIVE_RESULTS_URL = "https://www.fencingtimelive.com/tournaments/eventSchedule/223806A144D347D2BFEFE4B7E6D36E2D"
INVITATION_URL = "https://static.fie.org/uploads/test/fie-grand-prix-invitation.pdf"


FIE_DETAIL_HTML = f"""
<html>
<body>
  <main>
    <dl>
      <dt>Location</dt><dd>Shanghai</dd>
      <dt>Country</dt><dd>China</dd>
      <dt>Competition Format</dt><dd>144 Fencers - One round of pools followed by direct elimination</dd>
      <dt>DT President/Event Manager</dt><dd>Shi, TIAN</dd>
    </dl>
    <a href="{LIVE_RESULTS_URL}">Live Results</a>
    <a href="/competitions/2025/145/entries">Entries</a>
    <a href="{INVITATION_URL}">Invitation</a>
  </main>
  <script>
  window._competition = {{
    "competitionId": 145,
    "name": "Fencing Grand Prix Shanghai",
    "season": 2025,
    "type": "individual",
    "fencerCount": 144,
    "location": "Shanghai",
    "country": "China",
    "invitationUrl": "{INVITATION_URL}"
  }};
  window._athletes = [
    {{"fencer": {{"name": "LEE Kiefer", "nationality": "USA"}}}},
    {{"fencer": {{"name": "CHEN Qingyuan", "nationality": "CHN"}}}},
    {{"fencer": {{"name": "AZUMA Sera", "nationality": "JPN"}}}}
  ];
  window._pools = {{
    "pools": [
      {{"poolId": 1, "rows": [{{"rank": 1}}, {{"rank": 2}}, {{"rank": 3}}, {{"rank": 4}}, {{"rank": 5}}, {{"rank": 6}}]}},
      {{"poolId": 2, "rows": [{{"rank": 1}}, {{"rank": 2}}, {{"rank": 3}}, {{"rank": 4}}, {{"rank": 5}}, {{"rank": 6}}]}}
    ]
  }};
  window._tableau = [
    {{"rounds": {{"A64": [], "A32": [], "A16": []}}}}
  ];
  </script>
</body>
</html>
"""


INVITATION_TEXT = """
Fencing Grand Prix Shanghai
Organizer
Chinese Fencing Association

Venue
Shanghai Gymnasium
1111 Caoxi Road, Shanghai, China

Entry deadline: 15 April 2025
Participation quota: 144 fencers
Formula: One round of pools followed by direct elimination
Entry fees:
Individual competition - EUR 100.
"""


MALFORMED_DETAIL_HTML = """
<html>
<body>
  <dl>
    <dt>Competition Format</dt><dd>approximately many fencers</dd>
    <dt>Location</dt><dd>Not Set</dd>
  </dl>
  <a href="/competitions/2025/999/entries">Entries</a>
  <script>
  window._competition = {"competitionId": 999, "name": "Malformed Fields", "type": "individual"};
  window._athletes = [];
  </script>
</body>
</html>
"""


MALFORMED_INVITATION_TEXT = """
Organiser: To be confirmed
Entry deadline: next Friday
Quota: as per FIE rules
Venue: Not Set
"""


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
        self.null_columns = []
        self.eq_filters = []
        self.pending_upsert = None
        self.pending_conflict = None
        self.pending_update = None

    def select(self, columns):
        self.client.selects.append((self.table_name, columns))
        return self

    @property
    def not_(self):
        self._negated = True
        return self

    def is_(self, column, value):
        assert value == "null"
        if getattr(self, "_negated", False):
            self.not_null_columns.append(column)
            self.client.not_null_filters.append((self.table_name, column))
            self._negated = False
        else:
            self.null_columns.append(column)
        return self

    def eq(self, column, value):
        self.eq_filters.append((column, value))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, row, on_conflict):
        self.pending_upsert = row
        self.pending_conflict = on_conflict
        return self

    def update(self, row):
        self.pending_update = row
        return self

    def execute(self):
        if self.pending_upsert is not None:
            self.client.upserts.append((self.table_name, self.pending_upsert, self.pending_conflict))
            return FakeResult([self.pending_upsert])

        if self.pending_update is not None:
            self.client.updates.append((self.table_name, self.pending_update, list(self.eq_filters)))
            return FakeResult([self.pending_update])

        rows = list(self.client.tables[self.table_name])
        for column in self.not_null_columns:
            rows = [row for row in rows if row.get(column) is not None]
        for column in self.null_columns:
            rows = [row for row in rows if row.get(column) is None]
        for column, value in self.eq_filters:
            rows = [row for row in rows if row.get(column) == value]
        return FakeResult(rows[self.start : self.end + 1])


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "fs_competition_details": [
                {"tournament_id": "complete-existing"},
                {"tournament_id": "missing-tournament-fields"},
            ],
            "fs_tournaments": [
                {
                    "id": TOURNAMENT_ID,
                    "fie_id": 145,
                    "competition_url_id": 145,
                    "season": "2025",
                    "name": "Fencing Grand Prix Shanghai",
                    "organizer": None,
                    "entry_deadline": None,
                    "format": None,
                    "quota": None,
                    "venue_details": None,
                    "registration_url": None,
                    "live_results_url": None,
                    "detail_source": None,
                },
                {
                    "id": "missing-tournament-fields",
                    "fie_id": 146,
                    "competition_url_id": 146,
                    "season": "2025",
                    "name": "Needs Tournament Columns",
                    "organizer": None,
                    "entry_deadline": None,
                    "format": None,
                    "quota": None,
                    "venue_details": None,
                    "registration_url": None,
                    "live_results_url": None,
                    "detail_source": None,
                },
                {
                    "id": "complete-existing",
                    "fie_id": 147,
                    "competition_url_id": 147,
                    "season": "2025",
                    "name": "Complete Existing",
                    "organizer": "FIE",
                    "entry_deadline": "2025-04-01",
                    "format": "pools",
                    "quota": 64,
                    "venue_details": "Lausanne, Switzerland",
                    "registration_url": "https://fie.org/competitions/2025/147/entries",
                    "live_results_url": LIVE_RESULTS_URL,
                    "detail_source": "https://fie.org/competitions/2025/147",
                },
                {
                    "id": "no-fie-id",
                    "fie_id": None,
                    "competition_url_id": None,
                    "season": "2025",
                    "name": "Domestic Event",
                },
            ],
        }
        self.selects = []
        self.not_null_filters = []
        self.upserts = []
        self.updates = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_parse_detail_extracts_rendered_document_and_link_fields():
    from scrape_competition_details import parse_competition_detail_page

    row = parse_competition_detail_page(
        FIE_DETAIL_HTML,
        tournament_id=TOURNAMENT_ID,
        source_url="https://fie.org/competitions/2025/145",
        document_texts=[INVITATION_TEXT],
    )

    fields = row["metadata"]["detail_fields"]

    assert row["participant_count"] == 144
    assert row["countries_represented"] == 3
    assert row["format_type"] == "pools + direct elimination"
    assert row["pool_size"] == 6
    assert row["de_rounds"] == 3
    assert fields["organizer"] == "Chinese Fencing Association"
    assert fields["entry_deadline"] == "2025-04-15"
    assert fields["format"] == "One round of pools followed by direct elimination"
    assert fields["quota"] == 144
    assert fields["venue_details"] == "Shanghai Gymnasium, 1111 Caoxi Road, Shanghai, China"
    assert fields["registration_url"] == "https://fie.org/competitions/2025/145/entries"
    assert fields["live_results_url"] == LIVE_RESULTS_URL
    assert row["metadata"]["detail_fields_raw"]["entry_deadline"] == "Entry deadline: 15 April 2025"
    assert INVITATION_URL in row["metadata"]["document_urls"]


def test_parse_detail_handles_missing_and_malformed_fields_without_guessing():
    from scrape_competition_details import parse_competition_detail_page

    row = parse_competition_detail_page(
        MALFORMED_DETAIL_HTML,
        tournament_id=TOURNAMENT_ID,
        source_url="https://fie.org/competitions/2025/999",
        document_texts=[MALFORMED_INVITATION_TEXT],
    )

    fields = row["metadata"]["detail_fields"]

    assert fields["organizer"] == "To be confirmed"
    assert fields["entry_deadline"] is None
    assert fields["quota"] is None
    assert fields["venue_details"] is None
    assert fields["registration_url"] == "https://fie.org/competitions/2025/999/entries"
    assert row["metadata"]["detail_fields_raw"]["entry_deadline"] == "Entry deadline: next Friday"
    assert row["metadata"]["detail_fields_raw"]["quota"] == "Quota: as per FIE rules"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2025-04-15", "2025-04-15"),
        ("15 April 2025", "2025-04-15"),
        ("15.04.2025 23:59 CET", "2025-04-15"),
        ("Entry deadline: Apr 15, 2025", "2025-04-15"),
        ("04/05/2025", None),
        ("next Friday", None),
    ],
)
def test_normalize_detail_date_is_defensive(raw, expected):
    from scrape_competition_details import normalize_detail_date

    assert normalize_detail_date(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Participation quota: 144 fencers", 144),
        ("Maximum number of entries: 20 per country", 20),
        ("Competition Format 256 Fencers", 256),
        ("No quota", None),
        ("as per FIE rules", None),
    ],
)
def test_normalize_quota(raw, expected):
    from scrape_competition_details import normalize_quota

    assert normalize_quota(raw) == expected


def test_make_absolute_url_normalizes_relative_fie_links():
    from scrape_competition_details import make_absolute_url

    assert make_absolute_url("/competitions/2025/145/entries") == "https://fie.org/competitions/2025/145/entries"
    assert make_absolute_url(LIVE_RESULTS_URL) == LIVE_RESULTS_URL


def test_find_tournaments_needing_details_includes_existing_detail_rows_missing_tournament_columns():
    from scrape_competition_details import find_tournaments_needing_details

    fake = FakeSupabase()

    rows = find_tournaments_needing_details(fake)

    assert [row["id"] for row in rows] == [TOURNAMENT_ID, "missing-tournament-fields"]
    assert ("fs_tournaments", "fie_id") in fake.not_null_filters


def test_scraper_updates_existing_tournament_and_never_upserts_tournaments():
    from scrape_competition_details import scrape_competition_details

    fake = FakeSupabase()
    tables = cast(dict[str, list[dict[str, Any]]], fake.tables)
    tables["fs_tournaments"] = [tables["fs_tournaments"][0]]
    tables["fs_competition_details"] = []

    result = scrape_competition_details(
        client=fake,
        fetch_html=lambda season, url_id: FIE_DETAIL_HTML,
        fetch_document_texts=lambda urls: [INVITATION_TEXT],
        log_run=False,
        update_state=False,
        sleep=lambda _seconds: None,
    )

    assert result == {"processed": 1, "written": 1, "failed": 0, "skipped": 0}
    assert [(table, conflict) for table, _row, conflict in fake.upserts] == [
        ("fs_competition_details", "tournament_id")
    ]
    assert all(table != "fs_tournaments" for table, _row, _conflict in fake.upserts)
    assert len(fake.updates) == 1
    table_name, update, filters = fake.updates[0]
    assert table_name == "fs_tournaments"
    assert filters == [("id", TOURNAMENT_ID)]
    assert update == {
        "organizer": "Chinese Fencing Association",
        "entry_deadline": "2025-04-15",
        "format": "One round of pools followed by direct elimination",
        "quota": 144,
        "venue_details": "Shanghai Gymnasium, 1111 Caoxi Road, Shanghai, China",
        "registration_url": "https://fie.org/competitions/2025/145/entries",
        "live_results_url": LIVE_RESULTS_URL,
        "detail_source": "https://fie.org/competitions/2025/145",
    }


def test_scraper_handles_missing_detail_html_gracefully():
    from scrape_competition_details import scrape_competition_details

    fake = FakeSupabase()
    tables = cast(dict[str, list[dict[str, Any]]], fake.tables)
    tables["fs_tournaments"] = [tables["fs_tournaments"][0]]
    tables["fs_competition_details"] = []

    result = scrape_competition_details(
        client=fake,
        fetch_html=lambda season, url_id: None,
        log_run=False,
        update_state=False,
        sleep=lambda _seconds: None,
    )

    assert result == {"processed": 1, "written": 0, "failed": 1, "skipped": 0}
    assert fake.upserts == []
    assert fake.updates == []

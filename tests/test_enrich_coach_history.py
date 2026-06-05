from typing import Any
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FEDERATION_STAFF_HTML = """
<html>
  <body>
    <h1>National Team Staff</h1>
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Position</th>
          <th>Team</th>
          <th>Club</th>
          <th>Date Range</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Jane Smith</td>
          <td>Women's Epee National Coach</td>
          <td>USA Women's Epee</td>
          <td>Manhattan Fencing</td>
          <td>1 September 2024 - 31 August 2025</td>
        </tr>
        <tr>
          <td>Not A Coach</td>
          <td>Communications</td>
          <td>National Office</td>
          <td></td>
          <td></td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""


ANNOUNCEMENT_HTML = """
<article>
  <h1>British Fencing confirms GBR coaching team</h1>
  <p>
    British Fencing has appointed Jane Smith as Head Coach of the GBR Women's
    Foil squad from 1 August 2025 to 31 July 2026.
  </p>
  <p>Smith will work with fencer Alice Example during the senior season.</p>
</article>
"""


WIKIDATA_BINDINGS = [
    {
        "coach": {"value": "http://www.wikidata.org/entity/Q123"},
        "coachLabel": {"value": "Giovanna Trillini"},
        "roleLabel": {"value": "fencing coach"},
        "teamLabel": {"value": "Italy national fencing team"},
        "countryLabel": {"value": "Italy"},
        "start_time": {"value": "2021-09-01T00:00:00Z"},
        "end_time": {"value": "2024-08-31T00:00:00Z"},
        "reference_url": {"value": "https://www.federscherma.it/example-coach-announcement"},
    },
    {
        "coach": {"value": "http://www.wikidata.org/entity/Q999"},
        "coachLabel": {"value": "Unsourced Coach"},
        "roleLabel": {"value": "fencing coach"},
        "teamLabel": {"value": "Example team"},
    },
]


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.filters = []
        self.limit_value = None
        self.selected = None

    def upsert(self, rows, on_conflict=None):
        self.client.calls.append((self.name, "upsert", rows, on_conflict))
        return self

    def select(self, columns):
        self.selected = columns
        return self

    def ilike(self, key, value):
        self.filters.append(("ilike", key, value))
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        if self.name == "fs_fencers" and self.selected:
            name = None
            country = None
            for op, key, value in self.filters:
                if op == "ilike" and key == "name":
                    name = str(value).strip("%")
                if op == "eq" and key == "country":
                    country = value
            return FakeResult(self.client.fencers.get((name, country), []))
        return FakeResult([{"id": "ok"}])


class FakeClient:
    def __init__(self, fencers=None):
        self.calls = []
        self.fencers = fencers or {}

    def table(self, name):
        return FakeTable(self, name)


class FakeResponse:
    status_code = 200
    text = "<html><body><h1>National coaches</h1></body></html>"


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers, timeout))
        return FakeResponse()


def normalize_sql(sql):
    return " ".join(sql.lower().split())


def test_coach_history_migration_defines_storage_shape():
    migration = Path("supabase/migrations/20260602_coach_history.sql")
    assert migration.exists()

    normalized = normalize_sql(migration.read_text())

    assert "create table if not exists public.fs_coach_history" in normalized
    assert "id text primary key" in normalized
    assert "coach_id uuid references public.fs_coaches(id)" in normalized
    assert "coach_name text not null" in normalized
    assert "country text" in normalized
    assert "team text" in normalized
    assert "club text" in normalized
    assert "role text not null" in normalized
    assert "start_date date" in normalized
    assert "end_date date" in normalized
    assert "source_url text not null" in normalized
    assert "source_type text not null" in normalized
    assert "metadata jsonb default '{}'::jsonb" in normalized
    assert "create unique index if not exists fs_coach_history_source_unique_idx" in normalized
    assert "create index if not exists fs_coach_history_coach_id_idx" in normalized
    assert "drop table" not in normalized
    assert "truncate" not in normalized


def test_parse_federation_staff_page_builds_source_backed_history_rows():
    from enrich_coach_history import parse_federation_staff_page

    rows = parse_federation_staff_page(
        FEDERATION_STAFF_HTML,
        country="USA",
        federation="USA Fencing",
        source_url="https://www.usafencing.org/national-team-staff",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["coach_name"] == "Jane Smith"
    assert row["country"] == "USA"
    assert row["team"] == "USA Women's Epee"
    assert row["club"] == "Manhattan Fencing"
    assert row["role"] == "National Coach"
    assert row["start_date"] == "2024-09-01"
    assert row["end_date"] == "2025-08-31"
    assert row["source_url"] == "https://www.usafencing.org/national-team-staff"
    assert row["source_type"] == "federation_staff"
    assert row["metadata"]["federation"] == "USA Fencing"
    assert row["metadata"]["role_raw"] == "Women's Epee National Coach"
    assert row["id"]


def test_normalize_role_labels_and_public_date_ranges():
    from enrich_coach_history import normalize_role_label, parse_date_range

    assert normalize_role_label("Women's Foil National Coach") == "National Coach"
    assert normalize_role_label("adjoint sabre dames") == "Assistant Coach"
    assert normalize_role_label("High Performance Lead") == "Performance Lead"

    assert parse_date_range("from 1 September 2024 to 31 August 2025") == (
        "2024-09-01",
        "2025-08-31",
    )
    assert parse_date_range("2024-09-01 - 2025-08-31") == (
        "2024-09-01",
        "2025-08-31",
    )
    assert parse_date_range("2024-25 season") == (None, None)


def test_parse_wikidata_bindings_requires_public_reference_url():
    from enrich_coach_history import parse_wikidata_bindings

    rows = parse_wikidata_bindings(WIKIDATA_BINDINGS)

    assert len(rows) == 1
    assert rows[0]["coach_name"] == "Giovanna Trillini"
    assert rows[0]["country"] == "Italy"
    assert rows[0]["team"] == "Italy national fencing team"
    assert rows[0]["role"] == "Coach"
    assert rows[0]["start_date"] == "2021-09-01"
    assert rows[0]["end_date"] == "2024-08-31"
    assert rows[0]["source_type"] == "wikidata"
    assert rows[0]["metadata"]["wikidata_id"] == "Q123"


def test_official_announcement_parser_keeps_clear_fencer_link_evidence():
    from enrich_coach_history import parse_official_announcement

    rows = parse_official_announcement(
        ANNOUNCEMENT_HTML,
        country="GBR",
        federation="British Fencing",
        source_url="https://www.britishfencing.com/25-26-gbr-coaches/",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["coach_name"] == "Jane Smith"
    assert row["country"] == "GBR"
    assert row["team"] == "GBR Women's Foil squad"
    assert row["role"] == "Head Coach"
    assert row["start_date"] == "2025-08-01"
    assert row["end_date"] == "2026-07-31"
    assert row["metadata"]["fencer_name"] == "Alice Example"
    assert row["metadata"]["link_evidence"] == "official_announcement_named_fencer"


def test_upsert_skips_ambiguous_fencer_links():
    from enrich_coach_history import upsert_coach_history

    client = FakeClient(
        fencers={
            ("Alice Example", "GBR"): [
                {"id": "fencer-1"},
                {"id": "fencer-2"},
            ]
        }
    )
    rows = [
        {
            "id": "history-1",
            "coach_id": "00000000-0000-0000-0000-000000000001",
            "coach_name": "Jane Smith",
            "country": "GBR",
            "team": "GBR Women's Foil squad",
            "club": None,
            "role": "Head Coach",
            "start_date": "2025-08-01",
            "end_date": "2026-07-31",
            "source_url": "https://www.britishfencing.com/25-26-gbr-coaches/",
            "source_type": "official_announcement",
            "metadata": {
                "fencer_name": "Alice Example",
                "link_evidence": "official_announcement_named_fencer",
            },
        }
    ]

    result = upsert_coach_history(rows, client=client)

    assert result == {"history_written": 1, "relationships_written": 0, "relationships_skipped": 1}
    assert client.calls[0] == ("fs_coach_history", "upsert", rows, "id")
    assert not any(call[0] == "fs_fencer_coach_relationship" for call in client.calls)


def test_fetch_source_pages_rate_limits_and_skips_blocked_stubs():
    from enrich_coach_history import fetch_source_pages

    session = FakeSession()
    sleeps: list[Any] = []
    pages, summary = fetch_source_pages(
        [
            {
                "source_type": "federation_staff",
                "country": "USA",
                "federation": "USA Fencing",
                "urls": ["https://example.test/staff"],
            },
            {
                "source_type": "official_announcement",
                "country": "FRA",
                "federation": "FF Escrime",
                "url": "https://blocked.example.test/staff",
                "blocked": True,
                "reason": "requires JavaScript-rendered authenticated archive",
            },
        ],
        session=session,
        sleeper=sleeps.append,
        request_delay=0.25,
    )

    assert [page["url"] for page in pages] == ["https://example.test/staff"]
    assert summary == {"fetched": 1, "failed": 0, "blocked": 1}
    assert len(session.calls) == 1
    assert sleeps == [0.25]

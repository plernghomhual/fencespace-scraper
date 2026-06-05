from typing import Any, cast
from pathlib import Path


USAFENCING_CLUBS_PAYLOAD = cast(dict[str, Any], {
    "indexData": {
        "models": [
            {
                "id": 101,
                "name": "Salle Durkan Fencing Center",
                "slug": "salle-durkan-fencing-center",
                "website": "https://salledurkan.example",
                "club_type": "Premium Club",
                "publicAddress": {
                    "street1": "10 Main Street",
                    "city": "New York",
                    "state": "NY",
                    "zip": "10001",
                    "formatted_address": "10 Main Street, New York, NY 10001",
                },
                "division": {"label": "Metropolitan NYC"},
                "region": {"label": "Region 3"},
                "inactive": False,
            },
            {
                "id": 102,
                "name": "Hidden Address Fencing",
                "publicAddress": {},
            },
        ],
        "pages": {"hasMorePages": False},
    }
})


PUBLIC_FACILITY_HTML = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "SportsActivityLocation",
        "name": "London Fencing Club",
        "url": "https://londonfencing.example",
        "email": "info@londonfencing.example",
        "telephone": "+44 20 7946 0100",
        "address": {
          "@type": "PostalAddress",
          "streetAddress": "12 Club Lane",
          "addressLocality": "London",
          "addressCountry": "United Kingdom"
        }
      }
    </script>
  </head>
  <body>
    <article class="club-card">
      <h3>London Fencing Club</h3>
      <p class="address">12 Club Lane, London, United Kingdom</p>
      <p>Programs: beginner classes, youth program, open bouting</p>
      <p>Weapons: foil and epee</p>
      <p>Contact: info@londonfencing.example Main phone +44 20 7946 0100</p>
      <p>Coach mobile +44 7700 900123 Jane private jane.doe@gmail.com</p>
      <a href="https://londonfencing.example">Website</a>
    </article>
  </body>
</html>
"""


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.rows = None
        self.on_conflict = None
        self.columns = None

    def select(self, columns):
        self.columns = columns
        return self

    def range(self, start, end):
        return self

    def upsert(self, rows, on_conflict):
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.columns is not None:
            return FakeResult(self.client.tables.get(self.name, []))
        self.client.upserts.append(
            {
                "table": self.name,
                "rows": self.rows,
                "on_conflict": self.on_conflict,
            }
        )
        return FakeResult([])


class FakeSupabase:
    def __init__(self, tables=None):
        self.tables = tables or {}
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_parse_usafencing_directory_extracts_public_training_facilities():
    from scrape_training_facilities import (
        DirectorySource,
        parse_usafencing_facilities,
    )

    source = DirectorySource(
        url="https://member.usafencing.org/clubs",
        name="USA Fencing club directory",
        country="USA",
        source_kind="federation_api",
        parser="usafencing_api",
    )

    rows = parse_usafencing_facilities(USAFENCING_CLUBS_PAYLOAD, source)

    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Salle Durkan Fencing Center"
    assert row["type"] == "club"
    assert row["address"] == "10 Main Street, New York, NY 10001"
    assert row["city"] == "New York"
    assert row["country"] == "USA"
    assert row["website"] == "https://salledurkan.example"
    assert row["source_url"] == "https://member.usafencing.org/clubs"
    assert row["metadata"]["usafencing_id"] == 101
    assert row["metadata"]["division"] == "Metropolitan NYC"


def test_parse_public_facility_html_extracts_location_programs_and_public_contact():
    from scrape_training_facilities import DirectorySource, parse_facilities_from_html

    source = DirectorySource(
        url="https://www.britishfencing.com/clubfinder/",
        name="British Fencing Club Finder",
        country="United Kingdom",
        source_kind="federation_page",
        parser="html",
    )

    rows = parse_facilities_from_html(PUBLIC_FACILITY_HTML, source)

    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "London Fencing Club"
    assert row["type"] == "club"
    assert row["address"] == "12 Club Lane, London, United Kingdom"
    assert row["city"] == "London"
    assert row["country"] == "United Kingdom"
    assert row["website"] == "https://londonfencing.example"
    assert row["weapons"] == ["epee", "foil"]
    assert row["programs"] == ["beginner", "open bouting", "youth"]
    assert row["contact_public"] == {
        "email": "info@londonfencing.example",
        "phone": "+44 20 7946 0100",
    }
    assert "jane.doe@gmail.com" not in str(row)
    assert "+44 7700 900123" not in str(row)


def test_dedupe_facilities_normalizes_name_address_and_country():
    from scrape_training_facilities import dedupe_facilities

    rows = [
        {
            "name": "Salle Durkan Fencing Center",
            "type": "club",
            "address": "10 Main Street, New York, NY 10001",
            "city": "New York",
            "country": "USA",
            "weapons": ["foil"],
            "programs": ["youth"],
            "source_url": "https://example.test/a",
            "metadata": {"source_kind": "club_page"},
        },
        {
            "name": "  salle durkan   fencing center  ",
            "type": "club",
            "address": "10 Main St., New York NY 10001",
            "city": "New York",
            "country": "United States",
            "weapons": ["epee", "foil"],
            "programs": ["adult classes"],
            "source_url": "https://example.test/b",
            "metadata": {"source_kind": "federation_api"},
        },
    ]

    deduped = dedupe_facilities(rows)

    assert len(deduped) == 1
    merged = deduped[0]
    assert merged["name"] == "Salle Durkan Fencing Center"
    assert merged["address"] == "10 Main Street, New York, NY 10001"
    assert merged["country"] == "USA"
    assert merged["weapons"] == ["epee", "foil"]
    assert merged["programs"] == ["adult classes", "youth"]
    assert merged["metadata"]["duplicate_source_urls"] == ["https://example.test/b"]


def test_scrape_training_facilities_no_geocoder_fallback_keeps_address_only():
    from scrape_training_facilities import (
        DirectorySource,
        FetchedContent,
        scrape_training_facilities,
    )

    source = DirectorySource(
        url="https://www.britishfencing.com/clubfinder/",
        name="British Fencing Club Finder",
        country="United Kingdom",
        source_kind="federation_page",
        parser="html",
    )

    def fetcher(_source):
        return FetchedContent(
            content=PUBLIC_FACILITY_HTML.encode("utf-8"),
            content_type="text/html",
            final_url="https://www.britishfencing.com/clubfinder/",
        )

    client = FakeSupabase()

    summary = scrape_training_facilities(
        client=client,
        sources=[source],
        fetcher=fetcher,
        geocoder=None,
        include_existing_clubs=False,
        log_run=False,
        update_state=False,
    )

    assert summary == {
        "sources": 1,
        "parsed": 1,
        "written": 1,
        "failed": 0,
        "skipped": 0,
        "existing_clubs": 0,
        "geocoded": 0,
    }
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_training_facilities"
    assert upsert["on_conflict"] == "name,address,country"
    row = upsert["rows"][0]
    assert row["address"] == "12 Club Lane, London, United Kingdom"
    assert "lat" not in row
    assert "lon" not in row


def test_scrape_training_facilities_paginates_usafencing_directory():
    from scrape_training_facilities import (
        DirectorySource,
        FetchedContent,
        scrape_training_facilities,
    )

    source = DirectorySource(
        url=(
            "https://member.usafencing.org/clubs?q=&division=&state=&club_type="
            "&sort=name&page=1&perPage=1"
        ),
        name="USA Fencing club directory",
        country="USA",
        source_kind="federation_api",
        parser="usafencing_api",
    )
    page_one = {
        "indexData": {
            "models": [USAFENCING_CLUBS_PAYLOAD["indexData"]["models"][0]],
            "pages": {"hasMorePages": True},
        }
    }
    page_two = {
        "indexData": {
            "models": [
                {
                    "id": 103,
                    "name": "North Shore Fencing Club",
                    "website": "https://northshore.example",
                    "publicAddress": {
                        "formatted_address": "55 Lake Road, Chicago, IL 60601",
                        "city": "Chicago",
                    },
                }
            ],
            "pages": {"hasMorePages": False},
        }
    }
    calls = []

    def fetcher(requested_source):
        calls.append(requested_source.url)
        payload = page_two if "page=2" in requested_source.url else page_one
        return FetchedContent(
            content=__import__("json").dumps(payload).encode("utf-8"),
            content_type="application/json",
            final_url=requested_source.url,
        )

    client = FakeSupabase()

    summary = scrape_training_facilities(
        client=client,
        sources=[source],
        fetcher=fetcher,
        include_existing_clubs=False,
        log_run=False,
        update_state=False,
    )

    assert calls == [
        "https://member.usafencing.org/clubs?q=&division=&state=&club_type=&sort=name&page=1&perPage=1",
        "https://member.usafencing.org/clubs?q=&division=&state=&club_type=&sort=name&page=2&perPage=1",
    ]
    assert summary["parsed"] == 2
    assert {row["name"] for row in client.upserts[0]["rows"]} == {
        "Salle Durkan Fencing Center",
        "North Shore Fencing Club",
    }


def test_existing_club_rows_become_training_facilities_without_private_fields():
    from scrape_training_facilities import facilities_from_existing_clubs

    client = FakeSupabase(
        tables={
            "fs_clubs": [
                {
                    "name": "Capital Fencing Academy",
                    "address": "6 Tennis Court, Hamilton Township, NJ 08619",
                    "city": "Hamilton Township",
                    "country": "USA",
                    "website": "https://capfencing.example",
                    "instagram": "capfencing",
                    "metadata": {
                        "private_owner_email": "owner@gmail.com",
                        "weapons": ["saber"],
                    },
                }
            ]
        }
    )

    rows = facilities_from_existing_clubs(client)

    assert rows == [
        {
            "name": "Capital Fencing Academy",
            "type": "club",
            "address": "6 Tennis Court, Hamilton Township, NJ 08619",
            "city": "Hamilton Township",
            "country": "USA",
            "website": "https://capfencing.example",
            "contact_public": {"instagram": "capfencing"},
            "weapons": ["saber"],
            "programs": [],
            "source_url": None,
            "metadata": {"source_kind": "existing_fs_clubs"},
        }
    ]
    assert "owner@gmail.com" not in str(rows)


def test_training_facilities_migration_defines_table_and_indexes():
    migration = Path("supabase/migrations/20260602_training_facilities.sql")

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_training_facilities" in normalized
    assert "name text not null" in normalized
    assert "type text" in normalized
    assert "address text" in normalized
    assert "contact_public jsonb default '{}'" in normalized
    assert "weapons text[]" in normalized
    assert "programs text[]" in normalized
    assert "lat double precision" in normalized
    assert "lon double precision" in normalized
    assert "metadata jsonb default '{}'" in normalized
    assert "unique (name, address, country)" in normalized
    assert "alter table public.fs_training_facilities enable row level security" in normalized
    assert "idx_fs_training_facilities_country_city" in normalized
    assert "idx_fs_training_facilities_weapons" in normalized

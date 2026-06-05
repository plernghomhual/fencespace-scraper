from typing import Any, cast
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"


WIKIDATA_BINDINGS = [
    {
        "club": {"value": "http://www.wikidata.org/entity/QLEV"},
        "clubLabel": {"value": "Levallois Sporting Club"},
        "countryLabel": {"value": "France"},
        "website": {"value": "https://www.levallois-sporting-club.fr/"},
        "inception": {"value": "+1941-00-00T00:00:00Z"},
        "article": {"value": "https://en.wikipedia.org/wiki/Levallois_Sporting_Club"},
        "athlete": {"value": "http://www.wikidata.org/entity/QFENCER"},
        "athleteLabel": {"value": "Public Fencer"},
        "fie_id": {"value": "12345"},
    },
    {
        "club": {"value": "http://www.wikidata.org/entity/QLEV"},
        "clubLabel": {"value": "Levallois Sporting Club"},
        "countryLabel": {"value": "France"},
        "athlete": {"value": "http://www.wikidata.org/entity/QUNMATCHED"},
        "athleteLabel": {"value": "Sourced Claim"},
    },
]


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.columns = None
        self.range_start = 0
        self.range_end = None
        self.rows = None
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
        self.rows = list(rows)
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            rows = self.client.tables.get(self.name, [])
            return FakeResult(rows[self.range_start:cast(int, self.range_end) + 1])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult([])
        raise AssertionError(f"unexpected operation {self.operation} on {self.name}")


class FakeClient:
    def __init__(self, tables=None):
        self.tables: dict[str, list[dict[str, Any]]] = {
            "fs_national_fed_rankings": [],
            "fs_results": [],
            "fs_fencers": [],
            "fs_club_rankings": [],
            "fs_clubs": [],
        }
        if tables:
            self.tables.update(tables)
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_club_enrichment_migration_defines_public_table_shape_and_conflict_key():
    migration = Path("supabase/migrations/20260602_club_enrichment.sql")

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_club_enrichment" in normalized
    assert "club_name text not null" in normalized
    assert "normalized_club_name text not null" in normalized
    assert "country text not null" in normalized
    assert "website text" in normalized
    assert "founding_date text" in normalized
    assert "history_summary text" in normalized
    assert "notable_alumni jsonb not null default '[]'::jsonb" in normalized
    assert "source_urls jsonb not null default '[]'::jsonb" in normalized
    assert "metadata jsonb not null default '{}'::jsonb" in normalized
    assert "unique (normalized_club_name, country)" in normalized
    assert "drop table" not in normalized
    assert "truncate table" not in normalized
    assert "delete from" not in normalized


def test_official_club_page_parser_extracts_founded_history_and_website():
    from enrich_clubs import parse_official_club_page

    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@type": "SportsClub",
            "name": "Downtown Fencing Club",
            "url": "https://downtown.example/",
            "foundingDate": "1984-05-10",
            "description": "Downtown Fencing Club is a public fencing club."
          }
        </script>
        <meta name="description" content="Fallback description">
      </head>
      <body>
        <section id="history">
          <h2>History</h2>
          <p>
            Founded in 1984, Downtown Fencing Club has trained national team
            fencers and hosts public youth programs.
          </p>
        </section>
      </body>
    </html>
    """

    parsed = parse_official_club_page(html, source_url="https://downtown.example/about")

    assert parsed["website"] == "https://downtown.example/"
    assert parsed["founding_date"] == "1984-05-10"
    assert parsed["history_summary"].startswith("Founded in 1984")
    assert parsed["source_urls"] == ["https://downtown.example/about"]
    assert parsed["metadata"]["source_type"] == "official_club_page"


def test_wikidata_bindings_group_claims_and_link_notable_alumni_conservatively():
    from enrich_clubs import build_wikidata_enrichments, club_key

    fencer_index = {
        "by_fie_id": {"12345": {"fencer-1"}},
        "by_wikidata_id": {},
    }

    grouped = build_wikidata_enrichments(WIKIDATA_BINDINGS, fencer_index=fencer_index)
    rows = grouped[club_key("Levallois Sporting Club", "FRA")]

    assert len(rows) == 1
    row = rows[0]
    assert row["club_name"] == "Levallois Sporting Club"
    assert row["country"] == "France"
    assert row["website"] == "https://www.levallois-sporting-club.fr/"
    assert row["founding_date"] == "1941"
    assert row["metadata"]["wikidata_id"] == "QLEV"
    assert "https://en.wikipedia.org/wiki/Levallois_Sporting_Club" in row["source_urls"]
    assert row["notable_alumni"] == [
        {
            "name": "Public Fencer",
            "fencer_id": "fencer-1",
            "fie_id": "12345",
            "wikidata_id": "QFENCER",
            "source": "wikidata:P54",
        },
        {
            "name": "Sourced Claim",
            "wikidata_id": "QUNMATCHED",
            "source": "wikidata:P54",
        },
    ]


def test_fetch_club_candidates_keeps_same_name_separate_by_country():
    from enrich_clubs import fetch_club_candidates

    client = FakeClient(
        {
            "fs_national_fed_rankings": [
                {
                    "id": "rank-usa",
                    "club": "Blade Club",
                    "country": "USA",
                    "metadata": {"source_url": "https://usa.example/rankings"},
                },
                {
                    "id": "rank-can",
                    "club": "Blade Club",
                    "country": "CAN",
                    "metadata": {"source_url": "https://canada.example/rankings"},
                },
            ],
            "fs_results": [
                {
                    "id": "result-usa",
                    "club": "Blade-Club",
                    "country": "United States",
                    "metadata": {"source_url": "https://usa.example/results"},
                }
            ],
        }
    )

    candidates = fetch_club_candidates(client, page_size=10)

    by_country = {candidate.country: candidate for candidate in candidates}
    assert set(by_country) == {"United States", "Canada"}
    assert by_country["United States"].normalized_name == "blade club"
    assert by_country["Canada"].normalized_name == "blade club"
    assert by_country["United States"].source_tables == (
        "fs_national_fed_rankings",
        "fs_results",
    )
    assert by_country["United States"].source_urls == (
        "https://usa.example/rankings",
        "https://usa.example/results",
    )


def test_enrich_clubs_writes_ambiguous_stub_instead_of_merging():
    from enrich_clubs import enrich_clubs

    client = FakeClient(
        {
            "fs_national_fed_rankings": [
                {"id": "rank-1", "club": "Blade Club", "country": "USA", "metadata": {}}
            ],
            "fs_fencers": [{"id": "fencer-1", "fie_id": "12345", "metadata": {}}],
        }
    )
    bindings = [
        {
            "club": {"value": "http://www.wikidata.org/entity/QBLADE1"},
            "clubLabel": {"value": "Blade Club"},
            "countryLabel": {"value": "United States"},
            "website": {"value": "https://blade-one.example/"},
        },
        {
            "club": {"value": "http://www.wikidata.org/entity/QBLADE2"},
            "clubLabel": {"value": "Blade Club"},
            "countryLabel": {"value": "United States"},
            "website": {"value": "https://blade-two.example/"},
        },
    ]

    summary = enrich_clubs(
        client=client,
        wikidata_bindings=bindings,
        fetch_official_pages=False,
        log_run=False,
        update_state=False,
        request_delay=0,
        enriched_at=NOW,
    )

    assert summary == {
        "clubs_seen": 1,
        "source_backed": 0,
        "stubbed": 1,
        "ambiguous": 1,
        "written": 1,
        "failed": 0,
        "skipped": 0,
    }
    assert client.upserts == [
        {
            "table": "fs_club_enrichment",
            "rows": [
                {
                    "club_name": "Blade Club",
                    "normalized_club_name": "blade club",
                    "country": "United States",
                    "website": None,
                    "founding_date": None,
                    "history_summary": None,
                    "notable_alumni": [],
                    "source_urls": [],
                    "metadata": {
                        "status": "ambiguous_source",
                        "source_count": 2,
                        "source_tables": ["fs_national_fed_rankings"],
                        "wikidata_ids": ["QBLADE1", "QBLADE2"],
                    },
                    "enriched_at": NOW,
                }
            ],
            "on_conflict": "normalized_club_name,country",
        }
    ]

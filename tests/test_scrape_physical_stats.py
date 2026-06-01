import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIE_PROFILE_HTML = """
<html>
  <body>
    <div class="ProfileInfo-item"><span>Height</span><span>181 cm</span></div>
    <div class="ProfileInfo-item"><span>Weight</span><span>64 kg</span></div>
    <p class="AthleteBio-body">
      <span class="AthleteBio-label">Reach</span>
      <span class="Bio-stat">183 cm</span>
    </p>
  </body>
</html>
"""


WIKIPEDIA_INFOBOX_HTML = """
<html>
  <body>
    <table class="infobox vcard">
      <tbody>
        <tr>
          <th scope="row">Height</th>
          <td>1.81 m (5 ft 11 in)</td>
        </tr>
        <tr>
          <th scope="row">Weight</th>
          <td>64 kg (141 lb)</td>
        </tr>
        <tr>
          <th scope="row">Reach</th>
          <td>72 in (183 cm)</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""


def test_parse_fie_profile_physical_stats():
    from scrape_physical_stats import parse_fie_physical_stats

    stats = parse_fie_physical_stats(FIE_PROFILE_HTML)

    assert stats.height == 181
    assert stats.weight == 64
    assert stats.reach == 183


def test_parse_wikipedia_infobox_physical_stats():
    from scrape_physical_stats import parse_wikipedia_infobox

    stats = parse_wikipedia_infobox(WIKIPEDIA_INFOBOX_HTML)

    assert stats.height == 181
    assert stats.weight == 64
    assert stats.reach == 183


def test_merge_stats_prefers_fie_and_uses_wikipedia_for_missing_fields():
    from scrape_physical_stats import PhysicalStats, merge_source_stats

    stats, sources = merge_source_stats(
        [
            ("fie_athlete_profile", PhysicalStats(height=181, weight=64)),
            ("wikipedia_infobox", PhysicalStats(height=180, weight=63, reach=183)),
        ]
    )

    assert stats == PhysicalStats(height=181, weight=64, reach=183)
    assert sources == {
        "height": "fie_athlete_profile",
        "weight": "fie_athlete_profile",
        "reach": "wikipedia_infobox",
    }


def test_build_update_payload_fills_only_missing_fields_and_merges_metadata():
    from scrape_physical_stats import PhysicalStats, build_update_payload

    row = {
        "id": "row-1",
        "height": 180,
        "weight": None,
        "reach": None,
        "metadata": {"existing": "yes"},
    }
    stats = PhysicalStats(height=181, weight=64, reach=183)
    sources = {
        "height": "fie_athlete_profile",
        "weight": "fie_athlete_profile",
        "reach": "wikipedia_infobox",
    }

    payload = build_update_payload(row, stats, sources, attempted_at="2026-06-01T00:00:00+00:00")

    assert "height" not in payload
    assert payload["weight"] == 64
    assert payload["reach"] == 183
    assert payload["metadata"]["existing"] == "yes"
    assert "height_source" not in payload["metadata"]
    assert payload["metadata"]["weight_source"] == "fie_athlete_profile"
    assert payload["metadata"]["reach_source"] == "wikipedia_infobox"
    assert payload["metadata"]["physical_stats_scrape"]["status"] == "updated"


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.payload = None
        self.filters = []

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.name, columns))
        return self

    def or_(self, expression):
        self.filters.append(("or", expression))
        self.client.filters.append(("or", expression))
        return self

    def limit(self, value):
        self.filters.append(("limit", value))
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def execute(self):
        if self.operation == "select":
            return FakeResult(self.client.rows)
        if self.operation == "update":
            eq_filters = [item for item in self.filters if item[0] == "eq"]
            self.client.updates.append(
                {
                    "table": self.name,
                    "payload": self.payload,
                    "eq": eq_filters[-1][1:],
                }
            )
            return FakeResult([])
        raise AssertionError(f"unexpected operation: {self.operation}")


class FakeSupabase:
    def __init__(self, rows):
        self.rows = rows
        self.selects = []
        self.filters = []
        self.updates = []

    def table(self, name):
        return FakeTable(self, name)


def test_scrape_physical_stats_queries_missing_fields_and_updates_by_id():
    from scrape_physical_stats import PhysicalStats, scrape_physical_stats

    client = FakeSupabase(
        [
            {
                "id": "row-1",
                "fie_id": "12345",
                "name": "Arianna Errigo",
                "height": None,
                "weight": None,
                "reach": None,
                "metadata": {"wikipedia_title": "Arianna_Errigo"},
            }
        ]
    )

    summary = scrape_physical_stats(
        client=client,
        fie_fetcher=lambda fie_id: PhysicalStats(height=181, weight=64),
        wikipedia_fetcher=lambda row: PhysicalStats(reach=183),
        log_run=False,
        update_state=False,
        now=lambda: "2026-06-01T00:00:00+00:00",
    )

    assert summary["processed"] == 1
    assert summary["written"] == 1
    assert summary["failed"] == 0
    assert client.selects == [
        (
            "fs_fencers",
            "id,fie_id,name,country,height,weight,reach,metadata",
        )
    ]
    assert ("or", "height.is.null,weight.is.null,reach.is.null") in client.filters
    assert client.updates[0]["table"] == "fs_fencers"
    assert client.updates[0]["eq"] == ("id", "row-1")
    assert client.updates[0]["payload"]["height"] == 181
    assert client.updates[0]["payload"]["weight"] == 64
    assert client.updates[0]["payload"]["reach"] == 183
    assert client.updates[0]["payload"]["metadata"]["height_source"] == "fie_athlete_profile"
    assert client.updates[0]["payload"]["metadata"]["weight_source"] == "fie_athlete_profile"
    assert client.updates[0]["payload"]["metadata"]["reach_source"] == "wikipedia_infobox"


def test_physical_stats_migration_adds_nullable_columns():
    migration = Path("supabase/migrations/20260601_physical_stats.sql")

    sql = migration.read_text().lower()

    assert "alter table public.fs_fencers" in sql
    assert "add column if not exists height integer" in sql
    assert "add column if not exists weight integer" in sql
    assert "add column if not exists reach integer" in sql

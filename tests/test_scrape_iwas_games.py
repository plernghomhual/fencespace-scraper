import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


HISTORIC_RESULTS_HTML = """
<html><body>
  <h2>World Championships</h2>
  <table>
    <tr><th>Year</th><th>Location</th><th>Competition</th><th>Download FILES</th></tr>
    <tr>
      <td>2023</td><td>Terni, Italy</td><td>Wheelchair Fencing World Championships</td>
      <td><a href="https://iwas.ophardt.online/en/search/results/1234">Download</a></td>
    </tr>
    <tr>
      <td>2025</td><td>Iksan, South Korea</td><td>Para Fencing World Championships</td>
      <td></td>
    </tr>
  </table>
  <h2>Satellite</h2>
  <table>
    <tr><th>Year</th><th>Location</th><th>Competition</th><th>Download FILES</th></tr>
    <tr>
      <td>2023</td><td>Orange, France</td><td>Satellite Competition</td>
      <td><a href="/wp-content/uploads/2023/10/orange-results.pdf">Download</a></td>
    </tr>
    <tr>
      <td>2025</td><td>Hong Kong, China</td><td>Satellite Competition</td>
      <td></td>
    </tr>
  </table>
</body></html>
"""


OPHARDT_RESULTS_HTML = """
<html><body>
  <h1>2023 Satellite Competition - Orange</h1>
  <h4>Epee male Senior Individual A</h4>
  <table class="table table-striped">
    <thead>
      <tr><th>Rank</th><th>Status</th><th>Round</th><th>Name</th><th>YOB</th><th>Gender</th><th>Class</th><th>Nation</th><th>Points</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>N</td><td>Final</td><td><a href="/en/biography/1001">COUTYA Dimitri</a></td><td>1997</td><td>M</td><td>A</td><td>Great Britain</td><td>48</td></tr>
      <tr><td>2</td><td>N</td><td>Final</td><td>KINGMANAW Visit</td><td>1989</td><td>M</td><td>A</td><td>Thailand</td><td>-</td></tr>
      <tr><td>3</td><td>N</td><td>Semi</td><td>DABROWSKI Michal</td><td>1986</td><td>M</td><td>A</td><td>POL</td><td>16.5</td></tr>
      <tr><td>4</td><td>N</td><td>Tableau</td><td>LAM Pui Shan</td><td>1994</td><td>M</td><td></td><td>Hong Kong, China</td><td></td></tr>
    </tbody>
  </table>
  <h4>Foil female Senior Individual</h4>
  <table class="table table-striped">
    <thead>
      <tr><th>Rank</th><th>Name</th><th>Nation</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>VIO Beatrice</td><td>Italy</td></tr>
    </tbody>
  </table>
</body></html>
"""


PDF_RESULTS_TEXT = """
Wheelchair Fencing
Medallists by Event
Event Date Medal Name Sport Class NPC Code
Men's Épée Category A FRI 6 SEP 2024 GOLD SUN Gang CHN
SILVER GILLIVER Piers GBR
BRONZE AKKAYA Hakan TUR
Women's Foil Category B WED 4 SEP 2024 GOLD JANA Saysunee THA
SILVER XIAO Rong CHN
BRONZE VIO GRANDIS Beatrice Maria ITA
"""


def test_parse_historic_results_page_maps_public_and_missing_sources():
    from scrape_iwas_games import parse_historic_results_page

    sources = parse_historic_results_page(
        HISTORIC_RESULTS_HTML,
        base_url="https://parafencing.org/results-and-rankings/historic-results/",
    )

    public = [source for source in sources if source["status"] == "public_results"]
    missing = [source for source in sources if source["status"] == "missing_public_data"]
    assert [source["source_kind"] for source in public] == ["world_championship", "satellite"]
    assert public[0]["source_format"] == "ophardt_html"
    assert public[0]["iwas_result_id"] == "1234"
    assert public[1]["source_format"] == "pdf"
    assert public[1]["source_url"] == "https://parafencing.org/wp-content/uploads/2023/10/orange-results.pdf"
    assert len(missing) == 2
    assert missing[-1]["location"] == "Hong Kong, China"
    assert missing[-1]["evidence"]["reason"] == "historic_results_row_without_download"


def test_parse_html_results_page_classifications_medals_points_and_countries():
    from scrape_iwas_games import parse_html_results_document

    events = parse_html_results_document(
        OPHARDT_RESULTS_HTML,
        source_url="https://iwas.ophardt.online/en/search/results/1234",
    )

    event = events[0]
    assert event["weapon"] == "Epee"
    assert event["gender"] == "Men"
    assert event["classification"] == "A"
    assert event["category"] == "Senior A"
    assert event["source_url"] == "https://iwas.ophardt.online/en/search/results/1234"
    assert event["rows"][0] == {
        "rank": 1,
        "fencer": "COUTYA Dimitri",
        "country": "GBR",
        "medal": "Gold",
        "points": 48.0,
        "classification": "A",
        "fie_id": "1001",
        "source_url": "https://iwas.ophardt.online/en/search/results/1234",
        "date": None,
    }
    assert event["rows"][1]["points"] is None
    assert event["rows"][2]["medal"] == "Bronze"
    assert event["rows"][3]["country"] == "HKG"
    assert event["rows"][3]["classification"] == "A"


def test_parse_html_results_page_handles_missing_classification_without_crashing():
    from scrape_iwas_games import parse_html_results_document

    events = parse_html_results_document(OPHARDT_RESULTS_HTML, source_url="https://example.test/results")

    incomplete = events[1]
    assert incomplete["weapon"] == "Foil"
    assert incomplete["gender"] == "Women"
    assert incomplete["classification"] is None
    assert incomplete["category"] == "Senior"
    assert incomplete["rows"][0]["classification"] is None
    assert incomplete["rows"][0]["country"] == "ITA"


def test_parse_pdf_text_fixture_parses_paralympic_medallist_rows():
    from scrape_iwas_games import parse_pdf_results_text

    events = parse_pdf_results_text(
        PDF_RESULTS_TEXT,
        source_url="https://parafencing.org/wp-content/uploads/2024/09/PG2024_WFE_B99_WFE-.pdf",
        competition_name="Paris 2024 Paralympic Games",
    )

    assert len(events) == 2
    assert events[0]["weapon"] == "Epee"
    assert events[0]["gender"] == "Men"
    assert events[0]["classification"] == "A"
    assert events[0]["date"] == "2024-09-06"
    assert events[0]["rows"][0]["fencer"] == "SUN Gang"
    assert events[0]["rows"][0]["medal"] == "Gold"
    assert events[0]["rows"][0]["country"] == "CHN"
    assert events[1]["category"] == "Senior B"
    assert events[1]["rows"][2]["fencer"] == "VIO GRANDIS Beatrice Maria"


def test_public_evidence_overrides_false_has_results_flag():
    from scrape_iwas_games import should_import_result_source

    source = {
        "source_url": "https://iwas.ophardt.online/en/search/results/1234",
        "status": "public_results",
    }

    assert should_import_result_source(source, {"hasResults": 0}) is True
    assert should_import_result_source({"source_url": None, "status": "missing_public_data"}, {"hasResults": 0}) is False


def test_build_no_public_data_stub_documents_missing_public_data():
    from scrape_iwas_games import build_no_public_data_stub

    source = {
        "year": "2025",
        "location": "Hong Kong, China",
        "competition": "Satellite Competition",
        "source_kind": "satellite",
        "source_url": None,
        "status": "missing_public_data",
        "evidence": {"reason": "historic_results_row_without_download"},
    }

    stub = build_no_public_data_stub(source)

    assert stub["source_id"] == "iwas-games:2025:hong-kong-china:satellite-competition:stub"
    assert stub["type"] == "wheelchair_satellite"
    assert stub["has_results"] is False
    assert stub["metadata"]["status"] == "missing_public_data"
    assert stub["metadata"]["evidence"]["reason"] == "historic_results_row_without_download"


def test_prepare_result_rows_matches_fie_id_then_name_country_and_logs_unmatched():
    from scrape_iwas_games import build_fencer_index, prepare_result_rows

    fencer_index = build_fencer_index(
        [
            {"id": "fie-priority", "fie_id": "1001", "name": "Wrong Name", "country": "GBR"},
            {"id": "name-match", "fie_id": None, "name": "KINGMANAW Visit", "country": "THA"},
        ]
    )
    event = {
        "source_kind": "satellite",
        "competition_name": "Orange Satellite",
        "event_name": "Epee male Senior Individual A",
        "weapon": "Epee",
        "gender": "Men",
        "classification": "A",
        "category": "Senior A",
        "source_url": "https://iwas.ophardt.online/en/search/results/1234",
        "rows": [
            {"rank": 1, "fencer": "COUTYA Dimitri", "country": "GBR", "fie_id": "1001", "medal": "Gold", "points": 48.0},
            {"rank": 2, "fencer": "KINGMANAW Visit", "country": "Thailand", "fie_id": None, "medal": "Silver", "points": None},
            {"rank": 3, "fencer": "Unknown Athlete", "country": "POL", "fie_id": None, "medal": "Bronze", "points": 16.0},
        ],
    }
    unmatched: list[Any] = []

    rows = prepare_result_rows("tournament-1", event, fencer_index, unmatched)

    assert [row["fencer_id"] for row in rows] == ["fie-priority", "name-match"]
    assert rows[0]["fie_fencer_id"] == "1001"
    assert rows[0]["metadata"]["match_method"] == "fie_id"
    assert rows[1]["metadata"]["match_method"] == "name_country"
    assert unmatched == [
        {
            "name": "Unknown Athlete",
            "country": "POL",
            "fie_id": None,
            "source_url": "https://iwas.ophardt.online/en/search/results/1234",
            "reason": "no_fencer_match",
        }
    ]
    assert all(row["fencer_id"] for row in rows)


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.action = None
        self.payload = None
        self.filters = []
        self.on_conflict = None

    def upsert(self, payload, on_conflict=None):
        self.action = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def delete(self):
        self.action = "delete"
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        if self.action == "upsert":
            self.client.upserts.append((self.table_name, self.payload, self.on_conflict))
            return FakeResult([{"id": "tournament-1"}])
        if self.action == "delete":
            self.client.deletes.append((self.table_name, tuple(self.filters)))
            return FakeResult()
        if self.action == "insert":
            self.client.inserts.append((self.table_name, self.payload))
            return FakeResult(self.payload)
        return FakeResult()


class FakeClient:
    def __init__(self):
        self.upserts = []
        self.deletes = []
        self.inserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_upsert_event_results_never_inserts_null_fencer_orphans():
    from scrape_iwas_games import build_fencer_index, upsert_event_results

    fake = FakeClient()
    fencer_index = build_fencer_index([{"id": "matched", "fie_id": "1001", "name": "COUTYA Dimitri", "country": "GBR"}])
    event = {
        "source_kind": "satellite",
        "competition_name": "Orange Satellite",
        "event_name": "Epee male Senior Individual A",
        "weapon": "Epee",
        "gender": "Men",
        "classification": "A",
        "category": "Senior A",
        "source_url": "https://iwas.ophardt.online/en/search/results/1234",
        "rows": [
            {"rank": 1, "fencer": "COUTYA Dimitri", "country": "GBR", "fie_id": "1001", "medal": "Gold", "points": 48.0},
            {"rank": 2, "fencer": "Missing Person", "country": "ITA", "fie_id": None, "medal": "Silver", "points": None},
        ],
    }

    written, skipped, unmatched = upsert_event_results(fake, "tournament-1", event, fencer_index)

    assert written == 1
    assert skipped == 1
    assert unmatched[0]["name"] == "Missing Person"
    assert fake.deletes == []
    table_name, inserted, _conflict = fake.upserts[0]
    assert table_name == "fs_results"
    assert len(inserted) == 1
    assert inserted[0]["fencer_id"] == "matched"
    assert inserted[0]["metadata"]["unmatched_rows_skipped"] == 1
    assert all(row["fencer_id"] is not None for row in inserted)


def test_rate_limiter_waits_between_requests():
    from scrape_iwas_games import RateLimiter

    observed_sleeps: list[Any] = []
    now = iter([10.0, 10.2, 11.0])
    limiter = RateLimiter(delay_seconds=1.0, monotonic=lambda: next(now), sleep=observed_sleeps.append)

    limiter.wait()
    limiter.wait()

    assert observed_sleeps == [0.8]

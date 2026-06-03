import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FTL_EVENT_HTML = """
<!doctype html>
<html>
<head><title>British Youth Championships 2024 - U-14 Women's Épée</title></head>
<body>
  <h1>British Youth Championships 2024</h1>
  <h2>U-14 Women's Épée</h2>
  <p>May 4, 2024</p>
  <table class="table table-striped">
    <thead>
      <tr>
        <th>Place</th>
        <th>Name</th>
        <th>Club</th>
        <th>Division/Region</th>
        <th>Points</th>
        <th>Licence</th>
        <th>DOB</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>1</td>
        <td>
          <a href="/fencers/private-minor-id">TAYLOR Maya</a>
          <span class="sr-only">licence 123456</span>
        </td>
        <td> knightsbridge fencing club </td>
        <td>London Region</td>
        <td>32</td>
        <td>123456</td>
        <td>2010-01-05</td>
      </tr>
      <tr>
        <td>2</td>
        <td>SMITH Olivia</td>
        <td>Unknown</td>
        <td>SCOTLAND EAST</td>
        <td>26</td>
        <td>987654</td>
        <td>2011-08-13</td>
      </tr>
      <tr>
        <td>3=</td>
        <td>JONES Carys</td>
        <td>Cardiff Academy</td>
        <td>Wales</td>
        <td>20</td>
        <td></td>
        <td></td>
      </tr>
    </tbody>
  </table>
</body>
</html>
"""


FTL_SCHEDULE_HTML = """
<html><body>
  <h1>British Youth Championships 2024</h1>
  <p>May 4, 2024 - May 6, 2024</p>
  <h5>Saturday May 4, 2024</h5>
  <table>
    <tr><th>Start</th><th>Event</th><th>Status</th></tr>
    <tr>
      <td>8:45 AM</td>
      <td><a href="/events/view/public-event-1">U-12 Men's Foil</a></td>
      <td>Finished at 3:35 PM (78 competitors)</td>
    </tr>
    <tr>
      <td>8:45 AM</td>
      <td><a href="/events/view/public-event-2">U-14 Women's Épée</a></td>
      <td>Finished at 2:09 PM (59 competitors)</td>
    </tr>
  </table>
</body></html>
"""


PDF_TEXT = """
THE SWORD JULY 2014
British Youth Championships
EPEE
Boys U12 (71)
1. BAIGNERES Jean-Baptiste (LONDON)
2. ASHFORTH Myles (EASTERN)
3= GENIESER George (LONDON)
3= JARVIE Lachlan (SOUTH EAST)
Girls U16 (53)
1. SCHNEIDER Emily (SOUTHERN)
2. JORDAN Anna (EAST MIDLANDS)
3= LUCAS Tyler (LONDON)
FOIL
Girls U14 Foil (18)
1. RIGBY Emily (NORTH WEST)
"""


LOGIN_REQUIRED_HTML = """
<html><body>
  <h1>Welcome to Fencing Time Live</h1>
  <p>To see tournament information on Fencing Time Live, you need to be logged in.</p>
</body></html>
"""


def test_parse_ftl_results_extracts_event_rows_and_avoids_minor_profile_data():
    from scrape_british_youth import parse_ftl_results_html

    event = parse_ftl_results_html(
        FTL_EVENT_HTML,
        "https://www.fencingtimelive.com/events/view/public-event-2",
    )

    assert event["event_name"] == "U-14 Women's Épée"
    assert event["weapon"] == "Epee"
    assert event["gender"] == "Women"
    assert event["age_group"] == "U14"
    assert event["season"] == "2024"
    assert event["date"] == "2024-05-04"
    assert event["source_url"] == "https://www.fencingtimelive.com/events/view/public-event-2"

    assert event["results"][0] == {
        "rank": 1,
        "name": "TAYLOR Maya",
        "club": "Knightsbridge Fencing Club",
        "region": "London",
        "points": 32.0,
        "medal": "Gold",
    }
    assert event["results"][1]["club"] is None
    assert event["results"][1]["region"] == "Scotland East"
    assert event["results"][2]["medal"] == "Bronze"
    assert "licence" not in event["results"][0]
    assert "birth_date" not in event["results"][0]
    assert "profile_url" not in event["results"][0]


def test_parse_british_youth_pdf_text_extracts_regions_age_groups_and_medals():
    from scrape_british_youth import parse_pdf_text

    events = parse_pdf_text(
        PDF_TEXT,
        source_url="https://www.britishfencing.com/uploads/files/the_sword_magazine_-_july_2014.pdf",
        season="2014",
    )

    assert [event["event_name"] for event in events] == [
        "Boys U12 Epee",
        "Girls U16 Epee",
        "Girls U14 Foil",
    ]
    first = events[0]
    assert first["weapon"] == "Epee"
    assert first["gender"] == "Men"
    assert first["age_group"] == "U12"
    assert first["source_url"].endswith("the_sword_magazine_-_july_2014.pdf")
    assert first["results"][0] == {
        "rank": 1,
        "name": "BAIGNERES Jean-Baptiste",
        "club": None,
        "region": "London",
        "points": None,
        "medal": "Gold",
    }
    assert first["results"][2]["rank"] == 3
    assert first["results"][2]["medal"] == "Bronze"
    assert events[1]["results"][1]["region"] == "East Midlands"
    assert events[2]["results"][0]["region"] == "North West"


def test_parse_ftl_schedule_discovers_public_event_links():
    from scrape_british_youth import parse_ftl_schedule

    events = parse_ftl_schedule(
        FTL_SCHEDULE_HTML,
        "https://www.fencingtimelive.com/tournaments/eventSchedule/8EE15CF32DD94520BA98F08DAC10DDC7",
    )

    assert events == [
        {
            "event_name": "U-12 Men's Foil",
            "weapon": "Foil",
            "gender": "Men",
            "age_group": "U12",
            "date": "2024-05-04",
            "source_url": "https://www.fencingtimelive.com/events/view/public-event-1",
            "status": "Finished at 3:35 PM (78 competitors)",
        },
        {
            "event_name": "U-14 Women's Épée",
            "weapon": "Epee",
            "gender": "Women",
            "age_group": "U14",
            "date": "2024-05-04",
            "source_url": "https://www.fencingtimelive.com/events/view/public-event-2",
            "status": "Finished at 2:09 PM (59 competitors)",
        },
    ]


def test_login_required_result_page_returns_documented_skip():
    from scrape_british_youth import classify_source_status

    status = classify_source_status(
        LOGIN_REQUIRED_HTML,
        "https://fencingtimelive.com/tournaments/eventSchedule/D1A408A165A941658BDB6AADF78FD367",
    )

    assert status == {
        "url": "https://fencingtimelive.com/tournaments/eventSchedule/D1A408A165A941658BDB6AADF78FD367",
        "status": "skipped",
        "reason": "login_required",
    }


def test_public_ftl_page_with_login_nav_is_not_marked_non_public():
    from scrape_british_youth import classify_source_status

    html = """
    <html><body>
      <h1>Fencing Time Live</h1>
      <a href="/account/login">Log in</a>
      <h2>British Youth Championships 2024</h2>
      <h3>Event Schedule</h3>
    </body></html>
    """

    assert classify_source_status(
        html,
        "https://www.fencingtimelive.com/tournaments/eventSchedule/8EE15CF32DD94520BA98F08DAC10DDC7",
    ) == {
        "url": "https://www.fencingtimelive.com/tournaments/eventSchedule/8EE15CF32DD94520BA98F08DAC10DDC7",
        "status": "available",
        "reason": None,
    }


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = None
        self.payload = None
        self.filters = []

    def select(self, *_args):
        self.operation = "select"
        return self

    def upsert(self, payload, on_conflict=None):
        self.operation = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        self.client.upserts.append((self.table_name, payload, on_conflict))
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        self.client.inserts.append((self.table_name, payload))
        return self

    def delete(self):
        self.operation = "delete"
        self.client.deletes.append(self.table_name)
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def limit(self, _count):
        return self

    def execute(self):
        if self.table_name == "fs_tournaments" and self.operation == "upsert":
            return FakeResponse([{"id": "tournament-1"}])
        if self.table_name == "fs_fencers":
            filters = {(op, column): value for op, column, value in self.filters}
            if filters.get(("ilike", "name")) == "Known Fencer" and filters.get(("eq", "country")) == "GBR":
                return FakeResponse([{"id": "known-fencer-id"}])
            return FakeResponse([])
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.upserts = []
        self.inserts = []
        self.deletes = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_upsert_tournament_preserves_source_metadata(monkeypatch):
    import scrape_british_youth

    fake = FakeClient()
    monkeypatch.setattr(scrape_british_youth, "supabase", fake)

    tournament_id = scrape_british_youth.upsert_tournament(
        {
            "event_name": "U-14 Women's Épée",
            "weapon": "Epee",
            "gender": "Women",
            "age_group": "U14",
            "season": "2024",
            "date": "2024-05-04",
            "source_url": "https://www.fencingtimelive.com/events/view/public-event-2",
            "source_kind": "ftl_html",
            "results": [],
        }
    )

    assert tournament_id == "tournament-1"
    table, row, conflict = fake.upserts[0]
    assert table == "fs_tournaments"
    assert conflict == "source_id"
    assert row["source_id"] == "british_youth:2024:u14-women-epee"
    assert row["category"] == "U14"
    assert row["metadata"]["source_url"].endswith("public-event-2")
    assert row["metadata"]["source_kind"] == "ftl_html"


def test_upsert_results_logs_unmatched_rows_without_blocking_insert(monkeypatch, capsys):
    import scrape_british_youth

    fake = FakeClient()
    monkeypatch.setattr(scrape_british_youth, "supabase", fake)

    written = scrape_british_youth.upsert_results(
        "tournament-1",
        [
            {
                "rank": 1,
                "name": "Known Fencer",
                "club": "Knightsbridge Fencing Club",
                "region": "London",
                "points": 32.0,
                "medal": "Gold",
            },
            {
                "rank": 2,
                "name": "Unmatched Fencer",
                "club": "Cardiff Academy",
                "region": "Wales",
                "points": 26.0,
                "medal": "Silver",
            },
        ],
    )

    assert written == 2
    inserted_rows = fake.inserts[0][1]
    assert inserted_rows[0]["fencer_id"] == "known-fencer-id"
    assert inserted_rows[1]["fencer_id"] is None
    assert inserted_rows[1]["metadata"]["match_status"] == "unmatched"
    assert "Unmatched British youth fencer: Unmatched Fencer" in capsys.readouterr().out

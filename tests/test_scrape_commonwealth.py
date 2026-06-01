import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


HISTORY_HTML = """
<html><body>
<a href="/index.php/about-cff/history/90-1950-british-empire-games-auckland-new-zealand">
  1950 British Empire Games - Auckland, New Zealand
</a>
<a href="/images/results/1998_open_results.pdf">
  1998 Commonwealth Fencing Championships - Shah Alam, Malaysia
</a>
<a href="/index.php/about-cff/history/20-2018-commonwealth-senior-and-veteran-championships-canberra-australia">
  2018 Commonwealth Senior and Veteran Championships - Canberra, Australia
</a>
</body></html>
"""


PDF_TEXT_2006 = """
Commonwealth Open Fencing Championships Results
2006: Belfast, Northern Ireland
Men’s Individual Foil
1 MCGUIRE Josh CAN
2 COOK Keith SCO
3= BROOKE Alastair WAL
3= GAUDREAU-POLLENDER Julien CAN
5 MANSOUR David WAL
Men’s Team Foil
1 CANADA CAN
2 SCOTLAND SCO
3 ENGLAND ENG
4 WALES WAL
Women’s Individual Foil
1 KWAN Monica CAN
2 DAOUST Elise CAN
3= GARDNER Kate NIR
3= WRIGHT Elizabeth SCO
"""


PDF_TEXT_1998 = """
Commonwealth Fencing Championships Results
1998: Shah Alam, Malaysia
Men’s Individual Foil
01 Donnie McKenzie Scot 15-13
02 Paul Walsh Eng
03 Sam Johnson Eng
03 Chris Howarth Eng
05 Frank Bartollilo Aust
Women’s Individual Foil
01 Eloise Smith Eng 15-10
02 Linda Strachan Eng
03 Lucy Harris Eng
03 Fiona McIntosh Scot
"""


AUSFENCING_EVENT_HTML = """
<html><body>
<h1>Men’s Epee Individual (Canberra)</h1>
<h2>Fencers</h2>
<table>
  <tr><th>Name</th><th>First Name</th><th>State/ Country</th></tr>
  <tr><td>CURRAN JONES</td><td>Tommy</td><td>ENG</td></tr>
</table>
<h2>Results after Poules</h2>
<table>
  <tr><th>Rank</th><th>Name</th><th>State/ Country</th></tr>
  <tr><td>1</td><td>SANCHEZ-LETHEM, Paul</td><td>ENG</td></tr>
</table>
<h2>Final Results</h2>
<table>
  <tr><th>Rank</th><th>Name</th><th>State/ Country</th></tr>
  <tr><td>1</td><td>CURRAN JONES, Tommy</td><td>ENG</td></tr>
  <tr><td>2</td><td>JOHNSTON, Calum</td><td>SCO</td></tr>
  <tr><td>3=</td><td>KUMAR, Sunil</td><td>IND</td></tr>
  <tr><td>3=</td><td>GATES, Darcy</td><td>CAN</td></tr>
  <tr><td>5</td><td>RADFORD, Kristian</td><td>AUS</td></tr>
</table>
</body></html>
"""


NO_DATA_HTML = """
<html><body>
<h1>Final Results</h1>
<p>Results will be published after the event.</p>
</body></html>
"""


def test_parse_history_page_distinguishes_games_from_standalone_championships():
    from scrape_commonwealth import parse_history_page

    editions = parse_history_page(HISTORY_HTML, "https://commonwealthfencing.org/history")

    assert editions[0]["edition_id"] == "1950"
    assert editions[0]["kind"] == "commonwealth_games"
    assert editions[1]["edition_id"] == "1998"
    assert editions[1]["kind"] == "standalone_championship"
    assert editions[2]["edition_id"] == "2018"
    assert editions[2]["kind"] == "standalone_championship"


def test_classify_event_weapon_gender_and_team():
    from scrape_commonwealth import classify_event

    assert classify_event("Men’s Individual Foil") == {
        "weapon": "Foil",
        "gender": "Men",
        "team": False,
        "event_code": "men-foil-individual",
    }
    assert classify_event("Senior Women's Epee Team") == {
        "weapon": "Epee",
        "gender": "Women",
        "team": True,
        "event_code": "women-epee-team",
    }


def test_parse_pdf_text_events_handles_captured_2006_tables_and_medals():
    from scrape_commonwealth import parse_pdf_text_events

    events = parse_pdf_text_events(PDF_TEXT_2006, source_url="https://commonwealthfencing.org/images/results/2006_open_results.pdf")

    assert [event["event_code"] for event in events] == [
        "men-foil-individual",
        "men-foil-team",
        "women-foil-individual",
    ]
    individual = events[0]
    assert individual["edition_id"] == "2006"
    assert individual["edition_name"] == "2006 Commonwealth Fencing Championships - Belfast, Northern Ireland"
    assert individual["results"][:4] == [
        {"rank": 1, "name": "Josh MCGUIRE", "country": "CAN", "medal": "Gold", "fie_id": None},
        {"rank": 2, "name": "Keith COOK", "country": "SCO", "medal": "Silver", "fie_id": None},
        {"rank": 3, "name": "Alastair BROOKE", "country": "WAL", "medal": "Bronze", "fie_id": None},
        {"rank": 3, "name": "Julien GAUDREAU-POLLENDER", "country": "CAN", "medal": "Bronze", "fie_id": None},
    ]
    assert events[1]["results"][0] == {"rank": 1, "name": "CANADA", "country": "CAN", "medal": "Gold", "fie_id": None}


def test_parse_pdf_text_events_handles_captured_1998_country_aliases_and_scores():
    from scrape_commonwealth import parse_pdf_text_events

    events = parse_pdf_text_events(PDF_TEXT_1998, source_url="https://commonwealthfencing.org/images/results/1998_open_results.pdf")

    assert events[0]["edition_id"] == "1998"
    assert events[0]["results"][0] == {"rank": 1, "name": "Donnie McKenzie", "country": "SCO", "medal": "Gold", "fie_id": None}
    assert events[0]["results"][4] == {"rank": 5, "name": "Frank Bartollilo", "country": "AUS", "medal": None, "fie_id": None}


def test_parse_ausfencing_page_uses_final_results_not_poule_rankings():
    from scrape_commonwealth import parse_ausfencing_competition_page

    event = parse_ausfencing_competition_page(
        AUSFENCING_EVENT_HTML,
        url="https://www.ausfencing.org/competitions/mens-epee-individual-canberra-10/",
        edition_id="2018",
        edition_name="2018 Commonwealth Senior Championships - Canberra, Australia",
    )

    assert event["event_code"] == "men-epee-individual"
    assert event["results"][:4] == [
        {"rank": 1, "name": "Tommy Curran Jones", "country": "ENG", "medal": "Gold", "fie_id": None},
        {"rank": 2, "name": "Calum Johnston", "country": "SCO", "medal": "Silver", "fie_id": None},
        {"rank": 3, "name": "Sunil Kumar", "country": "IND", "medal": "Bronze", "fie_id": None},
        {"rank": 3, "name": "Darcy Gates", "country": "CAN", "medal": "Bronze", "fie_id": None},
    ]


def test_parse_ausfencing_page_returns_none_for_no_data_pages():
    from scrape_commonwealth import parse_ausfencing_competition_page

    event = parse_ausfencing_competition_page(
        NO_DATA_HTML,
        url="https://www.cffc2022.com/final-results",
        edition_id="2022",
        edition_name="2022 Commonwealth Fencing Championships - London, England",
    )

    assert event is None


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.inserted = None

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def limit(self, _count):
        return self

    def delete(self):
        self.client.deleted.append(self.table_name)
        return self

    def insert(self, rows):
        self.inserted = rows
        self.client.inserted.extend(rows)
        return self

    def execute(self):
        if self.table_name != "fs_fencers":
            return FakeResponse([])
        filters = {(op, column): value for op, column, value in self.filters}
        if filters.get(("eq", "fie_id")) == "12345":
            return FakeResponse([{"id": "fie-match"}])
        if filters.get(("ilike", "name")) == "Name Match" and filters.get(("eq", "country")) == "SCO":
            return FakeResponse([{"id": "name-country-match"}])
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.inserted = []
        self.deleted = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_upsert_results_matches_fencer_by_fie_id_before_name_country(monkeypatch):
    import scrape_commonwealth

    fake = FakeClient()
    monkeypatch.setattr(scrape_commonwealth, "supabase", fake)

    written = scrape_commonwealth.upsert_results(
        tournament_id="tournament-1",
        result_rows=[
            {"rank": 1, "name": "Ignored Name", "country": "ENG", "medal": "Gold", "fie_id": "12345"},
            {"rank": 2, "name": "Name Match", "country": "SCO", "medal": "Silver", "fie_id": None},
        ],
    )

    assert written == 2
    assert fake.inserted[0]["fencer_id"] == "fie-match"
    assert fake.inserted[1]["fencer_id"] == "name-country-match"
    assert fake.inserted[0]["metadata"]["source"] == "commonwealth"

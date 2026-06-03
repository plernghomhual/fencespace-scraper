import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


BUCS_EVENT_RESULTS_HTML = """
<html><body>
<h1>BUCS Fencing: North West 2021-22</h1>
<h2>Results</h2>
<table>
  <tr><th>Weapon</th><th>Student</th><th>Institution</th></tr>
  <tr><td>Men's Epee Beginner</td><td>Corentin Magnoux</td><td>Manchester</td></tr>
  <tr><td>Women's Foil Open</td><td>Sydney Williams-Howe</td><td>Manchester</td></tr>
  <tr><td>Women's Sabre Open</td><td>Alyssa Saw</td><td>Manchester</td></tr>
</table>
</body></html>
"""


BUCS_FLATTENED_RESULTS_HTML = """
<html><body>
<h1>BUCS Fencing: North West 2021-22</h1>
<h2>Results</h2>
<p>Weapon</p>
<p>Student</p>
<p>Institution</p>
<p>Men's Epee Beginner</p>
<p>Corentin Magnoux</p>
<p>Manchester</p>
<p>Men's Epee Open</p>
<p>Gavriel Athanasiou</p>
<p>Lancaster</p>
<p>Return to Events</p>
</body></html>
"""


FTL_RESULTS_HTML = """
<html><body>
<h1>Senior Women's Epee</h1>
<table>
  <tr><th>Place</th><th>Name</th><th>Club</th><th>FIE ID</th></tr>
  <tr><td>1</td><td>Alice Example</td><td>Nottingham Trent</td><td>123456</td></tr>
  <tr><td>2</td><td>Beta Fencer</td><td>University of Manchester</td><td></td></tr>
  <tr><td>3T</td><td>Gamma Athlete</td><td>UWE</td><td></td></tr>
</table>
</body></html>
"""


BIG_WEDNESDAY_TEXT = """
MATCH RESULTS
Sport Gender Level First Named Team (home) V Second Named Team (away) Notes
Fencing Men Trophy Nottingham 2 128 - 118 Exeter
Fencing Women Trophy Birmingham 135 - 109 Exeter
Fencing Men Champ Durham 88 - 120 Nottingham 1
Fencing Women Champ Nottingham 101 - 99 Durham
BUCS BIG WEDNESDAY 2025
LOUGHBOROUGH UNIVERSITY
"""


BUCS_PLAY_BLOCKED_HTML = """
<html><body>
<h1>BUCS Fencing</h1>
<h2>Fixtures and Results 2025-26</h2>
<p>All fixtures and results for the 2025-26 season can be accessed on BUCS Play.</p>
<p>To view last season's fixtures and results, please register for BUCS Play and select the 24-25 season.</p>
</body></html>
"""


def test_parse_bucs_event_results_page_handles_captured_regional_winner_table():
    from scrape_bucs import parse_bucs_event_results_page

    events = parse_bucs_event_results_page(
        BUCS_EVENT_RESULTS_HTML,
        "https://www.bucs.org.uk/events-page/bucs-fencing-north-west-1.html?tab=Results",
    )

    assert [event["event_code"] for event in events] == [
        "men-epee-beginner-individual",
        "women-foil-open-individual",
        "women-sabre-open-individual",
    ]
    first = events[0]
    assert first["season"] == "2021-2022"
    assert first["weapon"] == "Epee"
    assert first["gender"] == "Men"
    assert first["category"] == "Beginner"
    assert first["team"] is False
    assert first["results"] == [
        {
            "placement": 1,
            "rank": 1,
            "name": "Corentin Magnoux",
            "fie_id": None,
            "country": "GBR",
            "university": "University of Manchester",
            "raw_university": "Manchester",
            "team": False,
            "source_url": "https://www.bucs.org.uk/events-page/bucs-fencing-north-west-1.html?tab=Results",
        }
    ]


def test_parse_bucs_event_results_page_handles_flattened_pixl8_results_block():
    from scrape_bucs import parse_bucs_event_results_page

    events = parse_bucs_event_results_page(
        BUCS_FLATTENED_RESULTS_HTML,
        "https://www.bucs.org.uk/events-page/bucs-fencing-north-west-1.html?tab=Results",
    )

    assert [event["event_code"] for event in events] == [
        "men-epee-beginner-individual",
        "men-epee-open-individual",
    ]
    assert events[1]["results"][0]["name"] == "Gavriel Athanasiou"
    assert events[1]["results"][0]["university"] == "Lancaster University"


def test_parse_fencingtimelive_results_page_handles_individual_ranking_table():
    from scrape_bucs import parse_fencingtimelive_results_page

    event = parse_fencingtimelive_results_page(
        FTL_RESULTS_HTML,
        "https://www.fencingtimelive.com/events/view/example",
        season="2025-2026",
        tournament_name="BUCS Fencing: Individual Championships 2025-26",
    )

    assert event["source_id"] == "bucs:2025-2026:senior-women-epee-individual"
    assert event["event_name"] == "Senior Women's Epee"
    assert event["weapon"] == "Epee"
    assert event["gender"] == "Women"
    assert event["category"] == "Senior"
    assert event["team"] is False
    assert event["results"] == [
        {
            "placement": 1,
            "rank": 1,
            "name": "Alice Example",
            "fie_id": "123456",
            "country": "GBR",
            "university": "Nottingham Trent University",
            "raw_university": "Nottingham Trent",
            "team": False,
            "source_url": "https://www.fencingtimelive.com/events/view/example",
        },
        {
            "placement": 2,
            "rank": 2,
            "name": "Beta Fencer",
            "fie_id": None,
            "country": "GBR",
            "university": "University of Manchester",
            "raw_university": "University of Manchester",
            "team": False,
            "source_url": "https://www.fencingtimelive.com/events/view/example",
        },
        {
            "placement": 3,
            "rank": 3,
            "name": "Gamma Athlete",
            "fie_id": None,
            "country": "GBR",
            "university": "University of the West of England",
            "raw_university": "UWE",
            "team": False,
            "source_url": "https://www.fencingtimelive.com/events/view/example",
        },
    ]


def test_parse_big_wednesday_pdf_text_keeps_team_results_separate_from_fencers():
    from scrape_bucs import parse_big_wednesday_pdf_text

    events = parse_big_wednesday_pdf_text(
        BIG_WEDNESDAY_TEXT,
        "https://www.bucs.org.uk/static/BBW-2025-Results-Final.pdf",
    )

    assert [event["event_code"] for event in events] == [
        "men-trophy-team",
        "women-trophy-team",
        "men-champ-team",
        "women-champ-team",
    ]
    first = events[0]
    assert first["season"] == "2024-2025"
    assert first["weapon"] == "Mixed"
    assert first["team"] is True
    assert first["results"] == [
        {
            "placement": 1,
            "rank": 1,
            "name": "Nottingham 2",
            "university": "University of Nottingham",
            "raw_university": "Nottingham 2",
            "team_number": 2,
            "score_for": 128,
            "score_against": 118,
            "team": True,
            "source_url": "https://www.bucs.org.uk/static/BBW-2025-Results-Final.pdf",
        },
        {
            "placement": 2,
            "rank": 2,
            "name": "Exeter",
            "university": "University of Exeter",
            "raw_university": "Exeter",
            "team_number": None,
            "score_for": 118,
            "score_against": 128,
            "team": True,
            "source_url": "https://www.bucs.org.uk/static/BBW-2025-Results-Final.pdf",
        },
    ]


def test_normalizes_university_names_and_season_strings():
    from scrape_bucs import normalize_season, normalize_university_name, split_team_suffix

    assert normalize_season("2025-26") == "2025-2026"
    assert normalize_season("24-25") == "2024-2025"
    assert normalize_season("2025/2026") == "2025-2026"
    assert normalize_season("Season 2024-25") == "2024-2025"

    assert normalize_university_name("Manchester") == "University of Manchester"
    assert normalize_university_name("Nottingham Trent") == "Nottingham Trent University"
    assert normalize_university_name("UWE") == "University of the West of England"
    assert split_team_suffix("Nottingham 2") == ("Nottingham", 2)


def test_detect_blocked_public_results_stub_for_bucs_play_login_only_pages():
    from scrape_bucs import blocked_public_results_stub

    stub = blocked_public_results_stub(
        BUCS_PLAY_BLOCKED_HTML,
        "https://www.bucs.org.uk/sports-page/fencing.html",
    )

    assert stub == {
        "source_url": "https://www.bucs.org.uk/sports-page/fencing.html",
        "status": "blocked",
        "reason": "BUCS Play registration/login required for fixtures and results",
        "skipped": True,
    }


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.insert_rows = None

    def select(self, columns):
        self.filters.append(("select", columns))
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def limit(self, value):
        self.filters.append(("limit", value))
        return self

    def delete(self):
        self.client.deleted.append(self.table_name)
        return self

    def insert(self, rows):
        self.insert_rows = rows
        self.client.inserted.extend(rows)
        return self

    def execute(self):
        filters = {
            (item[0], item[1]): item[2]
            for item in self.filters
            if item[0] in {"eq", "ilike"}
        }
        if self.table_name == "fs_fencers":
            if filters.get(("eq", "fie_id")) == "123456":
                return FakeResponse([{"id": "fie-row", "fie_id": "123456"}])
            if filters.get(("ilike", "name")) == "Direct Match" and filters.get(("eq", "country")) == "GBR":
                return FakeResponse([{"id": "direct-row", "fie_id": None}])
        if self.table_name == "fs_fencer_identities":
            if filters.get(("ilike", "canonical_name")) == "Identity Match" and filters.get(("eq", "country")) == "GBR":
                return FakeResponse([{"fs_fencer_row_ids": ["identity-row"], "fie_ids": []}])
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.inserted = []
        self.deleted = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_upsert_results_skips_unmatched_individual_rows_and_keeps_team_rows(monkeypatch, capsys):
    import scrape_bucs

    fake = FakeClient()
    monkeypatch.setattr(scrape_bucs, "supabase", fake)
    event = {
        "source_id": "bucs:2025-2026:test",
        "team": False,
        "results": [
            {"rank": 1, "placement": 1, "name": "Any Name", "fie_id": "123456", "country": "GBR", "university": "University of Nottingham", "team": False},
            {"rank": 2, "placement": 2, "name": "Identity Match", "fie_id": None, "country": "GBR", "university": "University of Manchester", "team": False},
            {"rank": 3, "placement": 3, "name": "Direct Match", "fie_id": None, "country": "GBR", "university": "University of Exeter", "team": False},
            {"rank": 4, "placement": 4, "name": "Missing Person", "fie_id": None, "country": "GBR", "university": "University of Warwick", "team": False},
            {"rank": 1, "placement": 1, "name": "Nottingham 1", "university": "University of Nottingham", "team": True},
        ],
    }

    counts = scrape_bucs.upsert_results("tournament-1", event)

    assert counts == {"written": 4, "skipped": 1, "failed": 0}
    assert fake.deleted == ["fs_results"]
    assert [row["name"] for row in fake.inserted] == ["Any Name", "Identity Match", "Direct Match", "Nottingham 1"]
    assert [row["fencer_id"] for row in fake.inserted] == ["fie-row", "identity-row", "direct-row", None]
    assert fake.inserted[-1]["metadata"]["team"] is True
    assert "unmatched fencer: Missing Person" in capsys.readouterr().out

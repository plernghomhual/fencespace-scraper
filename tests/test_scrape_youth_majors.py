import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIE_YOUTH_WORLD_COMP = {
    "competitionId": 223,
    "name": "Championnats du monde juniors-cadets",
    "country": "BUL",
    "location": "Plovdiv",
    "startDate": "01-04-2023",
    "endDate": "09-04-2023",
    "weapon": "epee",
    "gender": "women",
    "category": "junior",
    "type": "individual",
    "hasResults": 0,
    "season": 2023,
}


def test_is_youth_world_championship_matches_fie_names_and_excludes_other_junior_events():
    from scrape_youth_majors import is_youth_world_championship

    assert is_youth_world_championship(FIE_YOUTH_WORLD_COMP)
    assert is_youth_world_championship(
        {
            **FIE_YOUTH_WORLD_COMP,
            "name": "Champ du monde juniors-cadets",
            "category": "cadet",
        }
    )
    assert is_youth_world_championship(
        {
            **FIE_YOUTH_WORLD_COMP,
            "name": "Junior and Cadet World Championships",
            "category": "cadet",
        }
    )
    assert not is_youth_world_championship(
        {
            **FIE_YOUTH_WORLD_COMP,
            "name": "Commonwealth Junior and Cadet Fencing Championship",
        }
    )
    assert not is_youth_world_championship(
        {
            **FIE_YOUTH_WORLD_COMP,
            "name": "World Championships",
            "category": "senior",
        }
    )


def test_competition_to_tournament_row_sets_url_id_and_overrides_youth_has_results():
    from scrape_youth_majors import competition_to_tournament_row

    row = competition_to_tournament_row(FIE_YOUTH_WORLD_COMP, 2023)

    assert row["fie_id"] == 223
    assert row["competition_url_id"] == 223
    assert row["source_id"] == "fie:youth_worlds:2023:223"
    assert row["name"] == "Championnats du monde juniors-cadets"
    assert row["season"] == "2023"
    assert row["weapon"] == "Epee"
    assert row["gender"] == "Women"
    assert row["category"] == "Junior"
    assert row["type"] == "individual"
    assert row["start_date"] == "2023-04-01"
    assert row["end_date"] == "2023-04-09"
    assert row["has_results"] is True
    assert row["metadata"]["scraped_by"] == "scrape_youth_majors"
    assert row["metadata"]["competition_family"] == "cadet_junior_world_championships"


def test_missing_fie_competitions_compares_existing_source_ids_by_season():
    from scrape_youth_majors import missing_fie_competitions

    missing = missing_fie_competitions(
        season=2023,
        competitions=[
            {"competitionId": 223, "name": "Champ du monde juniors-cadets"},
            {"competitionId": "224", "name": "Champ du monde juniors-cadets"},
            {"competitionId": 225, "name": "Champ du monde juniors-cadets"},
        ],
        existing_source_ids={"fie:youth_worlds:2023:223", "fie:youth_worlds:2023:224"},
    )

    assert missing == [{"competitionId": 225, "name": "Champ du monde juniors-cadets"}]


def test_fetch_youth_world_competitions_uses_month_fallback_after_season_error(monkeypatch):
    from scrape_youth_majors import fetch_youth_world_competitions

    class FakeResponse:
        def __init__(self, status_code, items=None):
            self.status_code = status_code
            self.text = "{}" if status_code == 200 else "server error"
            self._items = items or []

        def json(self):
            return {"items": self._items, "pageSize": 300}

    class FakeSession:
        def post(self, url, headers, json, timeout):
            if not json["fromDate"]:
                return FakeResponse(500)
            if json["fromDate"] == "2023-04-01":
                return FakeResponse(200, [FIE_YOUTH_WORLD_COMP])
            return FakeResponse(200, [])

    monkeypatch.setattr("scrape_youth_majors.time.sleep", lambda seconds: None)

    competitions = fetch_youth_world_competitions(FakeSession(), 2023)

    assert competitions == [FIE_YOUTH_WORLD_COMP]


def test_parse_fie_result_rows_normalizes_people_and_dedupes():
    from scrape_youth_majors import parse_fie_result_rows

    rows = parse_fie_result_rows(
        tournament_id="tournament-1",
        rows=[
            {
                "rank": 1,
                "name": "RAKHIMOVA Sevara",
                "nationality": "UZB",
                "country": None,
                "fencerId": 43309,
                "victory": 6,
                "matches": 6,
                "td": 30,
                "tr": 12,
                "diff": 18,
            },
            {
                "rank": "1",
                "name": "RAKHIMOVA Sevara",
                "nationality": "UZB",
                "fencerId": 43309,
            },
            {"rank": None, "name": "Skip Me", "nationality": "USA"},
        ],
    )

    assert len(rows) == 1
    assert rows[0]["tournament_id"] == "tournament-1"
    assert rows[0]["fie_fencer_id"] == "43309"
    assert rows[0]["name"] == "Sevara Rakhimova"
    assert rows[0]["nationality"] == "Uzb"
    assert rows[0]["country"] == "Uzb"
    assert rows[0]["rank"] == 1
    assert rows[0]["placement"] == 1


EYOF_EDITIONS_HTML = """
<html><body>
<table>
  <tr>
    <td><a href="/editions/701">XVII</a></td>
    <td>2023</td>
    <td>Maribor</td>
    <td>European Youth Olympic Festival</td>
  </tr>
  <tr>
    <td><a href="/editions/702">IV</a></td>
    <td>2026</td>
    <td>Dakar</td>
    <td>Youth Olympic Games</td>
  </tr>
</table>
</body></html>
"""


EYOF_SPORT_HTML = """
<html><body>
<table class="table">
  <tr><th>Event</th><th>Status</th><th>Date</th><th>Participants</th><th>Countries</th></tr>
  <tr>
    <td><a href="/results/55555">Foil, Individual, Girls</a></td>
    <td>EYOF</td><td>26 July 2023</td><td>36</td><td>24</td>
  </tr>
  <tr>
    <td><a href="/results/55556">Sabre, Team, Boys</a></td>
    <td>EYOF</td><td>27 July 2023</td><td>48</td><td>12</td>
  </tr>
</table>
</body></html>
"""


EYOF_RESULTS_HTML = """
<html><body>
<h1>Foil, Individual, Girls</h1>
<table class="table table-striped">
  <tr><th>Pos</th><th>Number</th><th>Competitor</th><th>NOC</th><th>Medal</th></tr>
  <tr><td>1</td><td>12</td><td><a href="/athletes/101">Ada Smith</a></td><td>GBR</td><td>Gold</td></tr>
  <tr><td>2</td><td>18</td><td><a href="/athletes/102">Bea Rossi</a></td><td>ITA</td><td>Silver</td></tr>
  <tr><td>3</td><td>22</td><td>Clara Novak</td><td>CZE</td><td>Bronze</td></tr>
</table>
</body></html>
"""


def test_parse_eyof_editions_from_olympedia_overview_fixture():
    from scrape_youth_majors import parse_eyof_editions

    editions = parse_eyof_editions(EYOF_EDITIONS_HTML)

    assert editions == [
        {
            "edition_id": "701",
            "edition_name": "Maribor 2023 European Youth Olympic Festival",
            "year": "2023",
        }
    ]


def test_parse_eyof_sport_page_and_classify_boys_girls_events():
    from scrape_youth_majors import classify_event, parse_eyof_sport_page

    events = parse_eyof_sport_page(EYOF_SPORT_HTML, edition_id="701", edition_name="Maribor 2023 European Youth Olympic Festival")

    assert len(events) == 2
    assert events[0]["result_id"] == "55555"
    assert events[0]["event_name"] == "Foil, Individual, Girls"
    assert classify_event(events[0]["event_name"]) == {"weapon": "Foil", "gender": "Women", "team": False}
    assert classify_event(events[1]["event_name"]) == {"weapon": "Sabre", "gender": "Men", "team": True}


def test_parse_olympedia_results_and_convert_eyof_rows_to_db_rows():
    from scrape_youth_majors import olympedia_rows_to_db, parse_olympedia_results_page

    placements = parse_olympedia_results_page(EYOF_RESULTS_HTML, result_id="55555")
    db_rows = olympedia_rows_to_db("tournament-2", placements)

    assert len(db_rows) == 3
    assert db_rows[0] == {
        "tournament_id": "tournament-2",
        "name": "Ada Smith",
        "nationality": "GBR",
        "rank": 1,
        "medal": "Gold",
        "fencer_id": None,
        "metadata": {"olympedia_athlete_id": "101"},
    }
    assert db_rows[2]["metadata"] == {"olympedia_athlete_id": None}


def test_remember_done_value_merges_existing_state(monkeypatch):
    calls = []

    monkeypatch.setattr("scrape_youth_majors.get_state", lambda source, key: ["111"])
    monkeypatch.setattr("scrape_youth_majors.set_state", lambda source, key, value: calls.append((source, key, value)))

    from scrape_youth_majors import SOURCE, remember_done_value

    remember_done_value("eyof_done_result_ids", "222")

    assert calls == [(SOURCE, "eyof_done_result_ids", ["111", "222"])]

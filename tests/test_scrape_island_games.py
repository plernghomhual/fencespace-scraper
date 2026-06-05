from typing import Any, cast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ISLAND_GAMES_RESULT_HTML = """
<html>
<body>
  <h1>International Island Games XXI Faroe Islands 2027</h1>
  <h2>Fencing</h2>
  <h3>Men's Foil Individual</h3>
  <table>
    <thead>
      <tr>
        <th>Position</th><th>Bib</th><th>Competitor</th><th>Island</th><th>Result</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>1st</td><td>101</td><td>Alex Sample</td><td>GUE</td><td></td></tr>
      <tr><td>2nd</td><td>102</td><td>Jamie Example</td><td>JER</td><td></td></tr>
      <tr><td>3rd</td><td>103</td><td>Casey Fixture</td><td>IOM</td><td></td></tr>
    </tbody>
  </table>
</body>
</html>
"""


OCEANIA_TOURNAMENT_HTML = """
<html>
<body>
  <h1>2019 - Oceania Open Championships</h1>
  <h3>Results</h3>
  <h5><a href="/competitions/mens-foil-individual-canberra-16/">Men’s Foil Individual (Canberra)</a></h5>
  <h5><a href="/competitions/womens-epee-individual-canberra-14/">Women’s Epee Individual (Canberra)</a></h5>
  <h5><a href="/news/not-a-result/">Tournament report</a></h5>
</body>
</html>
"""


OCEANIA_RESULT_HTML = """
<html>
<body>
  <h2>Men’s Foil Individual (Canberra)</h2>
  <h2>Results after Poules</h2>
  <table>
    <tr><th>Rank</th><th>Name</th><th>State/ Country</th></tr>
    <tr><td>1</td><td>MORRIS, Jesse</td><td>NSW</td></tr>
  </table>
  <h2>Final Results</h2>
  <table>
    <tr><th>Rank</th><th>Name</th><th>State/ Country</th></tr>
    <tr><td>1</td><td>DOUGLAS, Sholto</td><td>NSW</td></tr>
    <tr><td>2</td><td>NAGLE, Christopher</td><td>VIC</td></tr>
    <tr><td>3</td><td>FERGUSON, Clayton</td><td>SA</td></tr>
    <tr><td>3</td><td>WEBBER, Lucas</td><td>VIC</td></tr>
    <tr><td>5</td><td>MORRIS, Jesse</td><td>NSW</td></tr>
  </table>
</body>
</html>
"""


NO_DATA_HTML = """
<html>
<body>
  <h1>International Island Games XX Orkney 2025 Results</h1>
  <h2>Sports</h2>
  <ul><li>Archery</li><li>Swimming</li><li>Triathlon</li></ul>
  <p>No fencing results are published on this page.</p>
</body>
</html>
"""


def test_parse_island_games_html_table_returns_fencing_event_rows():
    from scrape_island_games import parse_island_games_result_page

    events = parse_island_games_result_page(
        ISLAND_GAMES_RESULT_HTML,
        edition_id="faroe-2027",
        edition_name="Faroe Islands 2027",
    )

    assert len(events) == 1
    event = events[0]
    assert event["source_id"] == "island_games:faroe-2027:mens-foil-individual"
    assert event["event_code"] == "mens-foil-individual"
    assert event["weapon"] == "Foil"
    assert event["gender"] == "Men"
    assert event["category"] == "Senior"
    assert event["rows"] == [
        {
            "rank": 1,
            "name": "Alex Sample",
            "country": "GUE",
            "medal": "Gold",
            "weapon": "Foil",
            "gender": "Men",
            "category": "Senior",
        },
        {
            "rank": 2,
            "name": "Jamie Example",
            "country": "JER",
            "medal": "Silver",
            "weapon": "Foil",
            "gender": "Men",
            "category": "Senior",
        },
        {
            "rank": 3,
            "name": "Casey Fixture",
            "country": "IOM",
            "medal": "Bronze",
            "weapon": "Foil",
            "gender": "Men",
            "category": "Senior",
        },
    ]


def test_parse_oceania_tournament_page_discovers_event_links_and_source_ids():
    from scrape_island_games import parse_oceania_tournament_page

    events = parse_oceania_tournament_page(
        OCEANIA_TOURNAMENT_HTML,
        page_url="https://www.ausfencing.org/tournament/2019-oceania-open-championships/",
    )

    assert len(events) == 2
    assert events[0]["year"] == "2019"
    assert events[0]["event_name"] == "Men’s Foil Individual (Canberra)"
    assert events[0]["event_code"] == "mens-foil-individual-canberra-16"
    assert events[0]["source_id"] == "oceania:2019:mens-foil-individual-canberra-16"
    assert events[0]["weapon"] == "Foil"
    assert events[0]["gender"] == "Men"
    assert events[0]["category"] == "Senior"
    assert events[0]["url"] == "https://www.ausfencing.org/competitions/mens-foil-individual-canberra-16/"


def test_parse_oceania_result_page_uses_final_results_table():
    from scrape_island_games import parse_oceania_result_page

    event = cast(dict[str, Any], parse_oceania_result_page(
        OCEANIA_RESULT_HTML,
        year="2019",
        event_code="mens-foil-individual-canberra-16",
        event_name="Men’s Foil Individual (Canberra)",
        category="Senior",
    ))

    assert event["source_id"] == "oceania:2019:mens-foil-individual-canberra-16"
    assert event["weapon"] == "Foil"
    assert event["gender"] == "Men"
    assert len(event["rows"]) == 5
    assert event["rows"][0] == {
        "rank": 1,
        "name": "Sholto Douglas",
        "country": "NSW",
        "medal": "Gold",
        "weapon": "Foil",
        "gender": "Men",
        "category": "Senior",
    }
    assert event["rows"][2]["medal"] == "Bronze"
    assert event["rows"][3]["medal"] == "Bronze"
    assert all(row["name"] != "Jesse Morris" for row in event["rows"][:4])


def test_no_data_pages_return_empty_results():
    from scrape_island_games import parse_island_games_result_page, parse_oceania_result_page

    assert parse_island_games_result_page(NO_DATA_HTML, edition_id="orkney-2025") == []
    assert (
        parse_oceania_result_page(
            "<html><body><h1>Women’s Epee Individual</h1><p>No results available.</p></body></html>",
            year="2025",
            event_code="womens-epee-individual",
            event_name="Women’s Epee Individual",
            category="Senior",
        )
        is None
    )

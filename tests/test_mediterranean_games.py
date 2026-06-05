from typing import Any, cast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


TARRAGONA_SCHEDULE_HTML = """
<html><body>
<nav>
  <a href="en/FEN/schedule/event/M.INDIV------EPEE---">Men's Individual epée</a>
  <a href="en/FEN/schedule/event/W.INDIV------EPEE---">Women's Individual epée</a>
  <a href="en/FEN/schedule/event/W.INDIV------SABLE--">Women's Individual sable</a>
  <a href="en/FEN/schedule/event/W.INDIV------FOIL---">Women's Individual foil</a>
  <a href="en/FEN/medals/by-event">Medals</a>
</nav>
</body></html>
"""


TARRAGONA_FINAL_RANK_HTML = """
<html><body>
<table>
  <tr><th>Rank</th><th>Name</th></tr>
  <tr>
    <td>1</td>
    <td><a href="en/FEN/entries/noc/ESP">ESP</a> <a href="en/FEN/athlete/18006785">PEREIRA RAMOS Yulen Alexander</a></td>
  </tr>
  <tr>
    <td>2</td>
    <td><a href="en/FEN/entries/noc/FRA">FRA</a> <a href="en/FEN/athlete/18005387">CANONNE Romain</a></td>
  </tr>
  <tr>
    <td>3</td>
    <td><a href="en/FEN/entries/noc/FRA">FRA</a> <a href="en/FEN/athlete/18005393">GALLY Aymerick</a></td>
  </tr>
  <tr>
    <td>3</td>
    <td><a href="en/FEN/entries/noc/MAR">MAR</a> <a href="en/FEN/athlete/18006290">ELKORD Houssam</a></td>
  </tr>
  <tr>
    <td>5</td>
    <td><a href="en/FEN/entries/noc/POR">POR</a> <a href="en/FEN/athlete/18013053">CANDEIAS Ricardo</a></td>
  </tr>
</table>
</body></html>
"""


ORAN_STANDINGS_TEXT = """
Centre MBA - Halle 01 et 02
Fencing
Men's Épée Individual
Standings
As of MON 4 JUL 2022 at 18:44
Rank Name Country
Gold ELSAYED Mohamed EGY - Egypt
Silver CUOMO Valerio ITA - Italy
Bronze PAOLINI Giacomo ITA - Italy
Bronze TAGLIARIOL Matteo ITA - Italy
5 YASSEEN Mohammed EGY - Egypt
6 JERENT Daniel FRA - France
FENMEPEE----------------------------_76I 1.0 Report Created MON 4 JUL 2022 18:44 Page 1 / 1
Data Processing and Timing by Microplus - www.microplustiming.com
"""


def test_discover_editions_reports_structured_and_skipped_sources():
    from scrape_mediterranean_games import discover_editions

    structured, skipped = discover_editions()

    assert [edition["edition_id"] for edition in structured] == ["2018", "2022"]
    assert structured[0]["edition_name"] == "Tarragona 2018"
    assert structured[1]["source_type"] == "oran_pdf"
    assert any(item["edition_id"] == "1951" and "unstructured" in item["reason"] for item in skipped)


def test_parse_tarragona_schedule_discovers_event_codes():
    from scrape_mediterranean_games import parse_tarragona_schedule_page

    events = parse_tarragona_schedule_page(TARRAGONA_SCHEDULE_HTML, "2018", "Tarragona 2018")

    assert [event["event_code"] for event in events] == [
        "M.INDIV------EPEE---",
        "W.INDIV------EPEE---",
        "W.INDIV------SABLE--",
        "W.INDIV------FOIL---",
    ]
    assert events[0]["event_name"] == "Men's Individual epée"
    assert events[0]["source_id"] == "mediterranean:2018:M.INDIV------EPEE---"


def test_classify_event_title_handles_accents_gender_and_sable_label():
    from scrape_mediterranean_games import classify_event

    assert classify_event("Men's Individual épée") == {"weapon": "Epee", "gender": "Men", "team": False}
    assert classify_event("Women's Épée Individual") == {"weapon": "Epee", "gender": "Women", "team": False}
    assert classify_event("Women's Individual sable") == {"weapon": "Sabre", "gender": "Women", "team": False}
    assert classify_event("Men's Foil Team") == {"weapon": "Foil", "gender": "Men", "team": True}


def test_parse_tarragona_final_rank_assigns_medals_and_athlete_ids():
    from scrape_mediterranean_games import parse_tarragona_final_rank_page

    rows = parse_tarragona_final_rank_page(TARRAGONA_FINAL_RANK_HTML)

    assert rows[:4] == [
        {"rank": 1, "name": "PEREIRA RAMOS Yulen Alexander", "country": "ESP", "medal": "Gold", "athlete_id": "18006785"},
        {"rank": 2, "name": "CANONNE Romain", "country": "FRA", "medal": "Silver", "athlete_id": "18005387"},
        {"rank": 3, "name": "GALLY Aymerick", "country": "FRA", "medal": "Bronze", "athlete_id": "18005393"},
        {"rank": 3, "name": "ELKORD Houssam", "country": "MAR", "medal": "Bronze", "athlete_id": "18006290"},
    ]
    assert rows[4]["medal"] is None


def test_parse_oran_standings_text_assigns_medals_and_event_code():
    from scrape_mediterranean_games import parse_oran_standings_text

    event = cast(dict[str, Any], parse_oran_standings_text(ORAN_STANDINGS_TEXT))

    assert event["event_code"] == "FENMEPEE"
    assert event["event_name"] == "Men's Épée Individual"
    assert event["rows"][:5] == [
        {"rank": 1, "name": "ELSAYED Mohamed", "country": "EGY", "medal": "Gold", "athlete_id": None},
        {"rank": 2, "name": "CUOMO Valerio", "country": "ITA", "medal": "Silver", "athlete_id": None},
        {"rank": 3, "name": "PAOLINI Giacomo", "country": "ITA", "medal": "Bronze", "athlete_id": None},
        {"rank": 3, "name": "TAGLIARIOL Matteo", "country": "ITA", "medal": "Bronze", "athlete_id": None},
        {"rank": 5, "name": "YASSEEN Mohammed", "country": "EGY", "medal": None, "athlete_id": None},
    ]


def test_missing_result_tables_return_empty_rows():
    from scrape_mediterranean_games import parse_tarragona_final_rank_page, parse_oran_standings_text

    assert parse_tarragona_final_rank_page("<html><body><p>No standings yet</p></body></html>") == []
    assert parse_oran_standings_text("Fencing\nMen's Épée Individual\nNo result table available") is None

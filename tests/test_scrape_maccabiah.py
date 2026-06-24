import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


OLYMPEDIA_LIKE_EVENTS_HTML = """
<html><body>
<table class="table">
  <tr><th>Event</th><th>Status</th><th>Date</th></tr>
  <tr>
    <td><a href="/results/98765">Foil, Individual, Men / רומח גברים</a></td>
    <td>Maccabiah</td>
    <td>18 July 2022</td>
  </tr>
  <tr>
    <td><a href="/athletes/1">Biography only</a></td>
    <td>No result</td>
    <td></td>
  </tr>
</table>
</body></html>
"""


OLYMPEDIA_LIKE_RESULTS_HTML = """
<html><body>
<h1>Foil, Individual, Men</h1>
<table class="biodata"><tr><td>Ignored</td></tr></table>
<table class="table table-striped">
  <tr><th>Pos</th><th>Number</th><th>Competitor</th><th>NOC</th><th>Medal</th></tr>
  <tr><td>1</td><td>12</td><td><a href="/athletes/101">Eli Dershwitz</a></td><td>USA</td><td>Gold</td></tr>
  <tr><td>2</td><td>9</td><td>Yuval Freilich</td><td>ISR</td><td>Silver</td></tr>
  <tr><td>=3</td><td>4</td><td>John Smith</td><td>CAN</td><td>Bronze</td></tr>
</table>
</body></html>
"""


OFFICIAL_M21_PAGE_HTML = """
<html><body>
<h1>Fencing</h1>
<a href="https://engarde-service.com/app.php?id=2502G6">Fencing - All Information</a>
<table>
  <tr><th>Date</th><th>Time</th><th>Date</th><th>Time</th><th>Venue</th><th>City</th></tr>
  <tr><td>7/17/22</td><td>10:00</td><td>7/17/22</td><td>15:30</td><td>Leader Sport Center</td><td>Ganey Tikva</td></tr>
  <tr><td>7/18/22</td><td>10:00</td><td>7/18/22</td><td>13:00</td><td>Leader Sport Center</td><td>Ganey Tikva</td></tr>
</table>
</body></html>
"""


# Captured from https://engarde-service.com/prog/smart_get_event_and_compeV2.php
# with Date=2022-07-19. The real response is larger; this keeps the public
# Maccabiah structures and field names intact.
OFFICIAL_EVENT_LISTING = """
|encoding=|{[dates_avant (2022-07-17 2022-07-18 )] [date 2022-07-19]
[event ({[event maccabia2022] [idgroupe 2502] [date 2022-07-17] [date_fin 2022-07-19] [titre "Maccabiah 2022 individuals"] [description ""]} )]
[compe (
{[event maccabia2022] [compe mac-fmj] [IdSmart 2502G6] [pays "ISR"] [ville "Ganei Tikva"] [titre "Maccabiah 2022 foil male junior"] [date 2022-07-17] [dateFin 2022-07-17] [sexe m] [arme f] [indiv 1] [type ] [categorie "junior"]}
{[event maccabiah2022team] [compe mac-efo-team] [IdSmart 2504T3] [pays "ISR"] [ville "Ganei Tikva"] [titre "Maccabiah epee female open Team"] [date 2022-07-19] [dateFin 2022-07-19] [sexe f] [arme e] [indiv 0] [type ] [categorie "senior"]}
{[event other2022] [compe other] [IdSmart 9999] [pays "FRA"] [ville "Paris"] [titre "Unrelated foil male"] [date 2022-07-19] [dateFin 2022-07-19] [sexe m] [arme f] [indiv 1] [type ] [categorie "senior"]}
)]} ;#!no_tache:1
"""


# Captured shape from https://engarde-service.com/prog/smart_get_data.php
# with IdCompe=2502G6, ceci=*, competition=2502G6.
OFFICIAL_RESULT_DATA = """
{[IdCompe 2502G6]
[nation (
{[classe nation] [nom "CAN"] [continent "AMN"] [cle 1]}
{[classe nation] [nom "GER"] [continent "EUR"] [cle 2]}
{[classe nation] [nom "ISR"] [continent "ASI"] [cle 5]}
{[classe nation] [nom "USA"] [continent "AMN"] [cle 8]}
)]
[tireur (
{[classe tireur] [sexe masculin] [nom "Aidan"] [prenom "Samuel"] [nation1 1] [cle 1] [dossard 1001]}
{[classe tireur] [sexe masculin] [nom "Haviv"] [prenom "Liam"] [nation1 5] [cle 7] [dossard 1007]}
{[classe tireur] [sexe masculin] [nom "ELIYAHU Dahan"] [prenom "Yali"] [nation1 5] [cle 9] [dossard 1009]}
{[classe tireur] [sexe masculin] [nom "Goldman"] [prenom "Jacob"] [nation1 8] [cle 21] [dossard 1021]}
)]
[classements (
{[date_oed "1392"] [nom clas_gene] [nutour 100] [classement ((q 1 7 t ()) (e 2 21 t ()) (e 3 9 t ()) (e 3 1 t ()))] [cle "clas_gene"]}
{[date_oed "1052"] [nom clas_fin_poules] [nutour 100] [classement ((q 1 1 4 4 20 4 1 4 2))] [cle "clas_fin_poules"]}
)]} ;#!no_tache:5
"""


OFFICIAL_TABLE_RESULTS_HTML = """
<html><body>
<h1>Fencing Results / תוצאות סיף</h1>
<table>
  <tr><th>Rank</th><th>Name</th><th>Delegation</th></tr>
  <tr><td>1</td><td>Maria Cohen</td><td>ISR</td></tr>
  <tr><td>2</td><td>Rachel Levy</td><td>USA</td></tr>
  <tr><td>3</td><td>Anna Klein</td><td>CAN</td></tr>
</table>
</body></html>
"""


OFFICIAL_NO_RESULTS_HTML = """
<html><body>
<h1>Fencing</h1>
<h2>FENCING REGULATIONS</h2>
<p>The Fencing Committee of the 20th Maccabiah will be responsible for the Fencing competitions.</p>
<p>Male: Individual and team competitions will be held in SABRE, FOIL and EPEE.</p>
</body></html>
"""


def test_parse_olympedia_like_events_and_results():
    from scrape_maccabiah import (
        parse_olympedia_like_events,
        parse_olympedia_like_results,
    )

    edition = {
        "edition_id": "m21",
        "edition_name": "21st Maccabiah 2022",
        "base_url": "https://history.example.test",
    }
    events = parse_olympedia_like_events(OLYMPEDIA_LIKE_EVENTS_HTML, edition)

    assert len(events) == 1
    assert events[0]["source_id"] == "maccabiah:m21:98765"
    assert events[0]["event_code"] == "98765"
    assert events[0]["original_title"] == "Foil, Individual, Men / רומח גברים"
    assert events[0]["classification"] == {"weapon": "Foil", "gender": "Men", "team": False, "category": "Senior"}

    rows = parse_olympedia_like_results(OLYMPEDIA_LIKE_RESULTS_HTML)
    assert rows == [
        {"rank": 1, "name": "Eli Dershwitz", "country": "USA", "medal": "Gold", "athlete_id": "101"},
        {"rank": 2, "name": "Yuval Freilich", "country": "ISR", "medal": "Silver", "athlete_id": None},
        {"rank": 3, "name": "John Smith", "country": "CAN", "medal": "Bronze", "athlete_id": None},
    ]


def test_parse_official_site_table_rows_without_medal_column():
    from scrape_maccabiah import parse_official_table_rows

    rows = parse_official_table_rows(OFFICIAL_TABLE_RESULTS_HTML)

    assert rows == [
        {"rank": 1, "name": "Maria Cohen", "country": "ISR", "medal": "Gold", "athlete_id": None},
        {"rank": 2, "name": "Rachel Levy", "country": "USA", "medal": "Silver", "athlete_id": None},
        {"rank": 3, "name": "Anna Klein", "country": "CAN", "medal": "Bronze", "athlete_id": None},
    ]


def test_parse_official_page_listing_and_engarde_results():
    from scrape_maccabiah import (
        discover_official_page,
        parse_official_event_listing,
        parse_official_result_data,
    )

    edition = {"edition_id": "m21", "edition_name": "21st Maccabiah 2022"}
    page = discover_official_page(OFFICIAL_M21_PAGE_HTML, edition, "https://m21.maccabiah.com/en/the-games/m21-sports/fencing")
    assert page["engarde_ids"] == ["2502G6"]
    assert page["probe_dates"] == ["2022-07-17", "2022-07-18"]

    events = parse_official_event_listing(OFFICIAL_EVENT_LISTING, edition, page["source_url"])
    assert [event["event_code"] for event in events] == ["2502G6", "2504T3"]
    assert events[0]["source_id"] == "maccabiah:m21:2502G6"
    assert events[0]["classification"] == {"weapon": "Foil", "gender": "Men", "team": False, "category": "Junior"}
    assert events[1]["classification"] == {"weapon": "Epee", "gender": "Women", "team": True, "category": "Senior"}
    assert events[0]["metadata"]["original_title"] == "Maccabiah 2022 foil male junior"

    rows = parse_official_result_data(OFFICIAL_RESULT_DATA)
    assert rows == [
        {"rank": 1, "name": "Liam Haviv", "country": "ISR", "medal": "Gold", "entity_key": "7"},
        {"rank": 2, "name": "Jacob Goldman", "country": "USA", "medal": "Silver", "entity_key": "21"},
        {"rank": 3, "name": "Yali Eliyahu Dahan", "country": "ISR", "medal": "Bronze", "entity_key": "9"},
        {"rank": 3, "name": "Samuel Aidan", "country": "CAN", "medal": "Bronze", "entity_key": "1"},
    ]


def test_official_no_results_page_returns_documented_stub():
    from scrape_maccabiah import discover_official_page

    edition = {"edition_id": "m20", "edition_name": "20th Maccabiah 2017"}
    page = discover_official_page(OFFICIAL_NO_RESULTS_HTML, edition, "https://m20.maccabiah.com/the-games/667-fencing")

    assert page["engarde_ids"] == []
    assert page["probe_dates"] == []
    assert page["stub"]["source_id"] == "maccabiah:m20:no-structured-results"
    assert page["stub"]["metadata"]["source_limitations"] == "official page contains fencing regulations but no structured result link"


def test_upsert_tournament_payload_preserves_original_title(monkeypatch):
    import scrape_maccabiah
    from scrape_maccabiah import upsert_tournament

    captured = {}

    class FakeExecute:
        data = [{"id": "tournament-1"}]

    class FakeTable:
        def upsert(self, row, on_conflict):
            captured["row"] = row
            captured["on_conflict"] = on_conflict
            return self

        def execute(self):
            return FakeExecute()

    class FakeSupabase:
        def table(self, name):
            captured["table"] = name
            return FakeTable()

    monkeypatch.setattr(scrape_maccabiah, "supabase", FakeSupabase())
    event = {
        "source_id": "maccabiah:m21:2502G6",
        "edition_id": "m21",
        "edition_name": "21st Maccabiah 2022",
        "event_code": "2502G6",
        "event_title": "Maccabiah 2022 foil male junior",
        "original_title": "Maccabiah 2022 foil male junior",
        "date": "2022-07-17",
        "date_end": "2022-07-17",
        "country": "ISR",
        "city": "Ganei Tikva",
        "classification": {"weapon": "Foil", "gender": "Men", "team": False, "category": "Junior"},
        "metadata": {"source_format": "official_engarde", "original_title": "Maccabiah 2022 foil male junior"},
    }

    tournament_id = upsert_tournament(event)

    assert tournament_id == "tournament-1"
    assert captured["table"] == "fs_tournaments"
    assert captured["on_conflict"] == "source_id"
    assert captured["row"]["source_id"] == "maccabiah:m21:2502G6"
    assert captured["row"]["metadata"]["original_title"] == "Maccabiah 2022 foil male junior"
    assert captured["row"]["metadata"]["team"] is False

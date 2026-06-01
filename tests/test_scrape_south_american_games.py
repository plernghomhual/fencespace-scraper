import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


WIKIPEDIA_MEDALISTS_HTML = """
<html><body>
<h3>Men</h3>
<table class="wikitable plainrowheaders">
  <tr><th>Event</th><th>Gold</th><th>Silver</th><th>Bronze</th></tr>
  <tr>
    <td rowspan="2">Espada individual</td>
    <td rowspan="2"><a href="/wiki/Jhon_Rodriguez">Jhon Rodríguez</a><br><a href="/wiki/Colombia">Colombia</a></td>
    <td rowspan="2"><a href="/wiki/Francisco_Limardo">Francisco Limardo</a><br><a href="/wiki/Venezuela">Venezuela</a></td>
    <td><a href="/wiki/Alexandre_Camargo">Alexandre Camargo</a><br><a href="/wiki/Brazil">Brazil</a></td>
  </tr>
  <tr>
    <td><a href="/wiki/Jesus_Lugones">Jesús Lugones</a><br><a href="/wiki/Argentina">Argentina</a></td>
  </tr>
  <tr>
    <td>Florete equipos</td>
    <td><a href="/wiki/Brazil">Brazil</a><br><a href="/wiki/Guilherme_Toldo">Guilherme Toldo</a><br><a href="/wiki/Henrique_Marques">Henrique Marques</a></td>
    <td><a href="/wiki/Argentina">Argentina</a><br><a href="/wiki/Augusto_Servello">Augusto Servello</a><br><a href="/wiki/Dante_Cerquetti">Dante Cerquetti</a></td>
    <td><a href="/wiki/Venezuela">Venezuela</a><br><a href="/wiki/Antonio_Leal">Antonio Leal</a><br><a href="/wiki/Cesar_Aguirre">César Aguirre</a></td>
  </tr>
</table>
<h3>Women</h3>
<table class="wikitable plainrowheaders">
  <tr><th>Event</th><th>Gold</th><th>Silver</th><th>Bronze</th></tr>
  <tr>
    <td>Sabre equipes</td>
    <td><a href="/wiki/Brazil">Brazil</a><br><a href="/wiki/Karina_Avila">Karina Ávila</a><br><a href="/wiki/Luana_Pekelman">Luana Pekelman</a></td>
    <td><a href="/wiki/Colombia">Colombia</a><br><a href="/wiki/Jessica_Morales">Jessica Morales</a><br><a href="/wiki/Maria_Blanco">María Angélica Blanco</a></td>
    <td><a href="/wiki/Argentina">Argentina</a><br><a href="/wiki/Alicia_Perroni">Alicia Perroni</a><br><a href="/wiki/Macarena_Moran">Macarena Morán</a></td>
  </tr>
</table>
</body></html>
"""


GENERIC_RESULTS_HTML = """
<html><body>
<table class="table table-striped">
  <tr><th>Posición</th><th>Atleta</th><th>País</th><th>Medalla</th></tr>
  <tr><td>1º</td><td>María Luisa Doig</td><td>PER</td><td>Oro</td></tr>
  <tr><td>2</td><td>Clara Isabel Di Tella</td><td>ARG</td><td>Plata</td></tr>
  <tr><td>3</td><td>Nathalie Moellhausen<br>Melisa Englert</td><td>BRA<br>ARG</td><td>Bronce</td></tr>
</table>
</body></html>
"""


def test_classify_event_handles_spanish_and_portuguese_labels():
    from scrape_south_american_games import classify_event

    assert classify_event("Espada individual masculino") == {
        "weapon": "Epee",
        "gender": "Men",
        "team": False,
    }
    assert classify_event("Florete por equipos femenino") == {
        "weapon": "Foil",
        "gender": "Women",
        "team": True,
    }
    assert classify_event("Sabre equipes feminina") == {
        "weapon": "Sabre",
        "gender": "Women",
        "team": True,
    }
    assert classify_event("Espada individual masculina") == {
        "weapon": "Epee",
        "gender": "Men",
        "team": False,
    }


def test_parse_generic_result_table_splits_shared_bronze_rows():
    from scrape_south_american_games import parse_result_rows

    rows = parse_result_rows(GENERIC_RESULTS_HTML)

    assert rows == [
        {"rank": 1, "name": "María Luisa Doig", "country": "PER", "medal": "Gold", "athlete_id": None},
        {"rank": 2, "name": "Clara Isabel Di Tella", "country": "ARG", "medal": "Silver", "athlete_id": None},
        {"rank": 3, "name": "Nathalie Moellhausen", "country": "BRA", "medal": "Bronze", "athlete_id": None},
        {"rank": 3, "name": "Melisa Englert", "country": "ARG", "medal": "Bronze", "athlete_id": None},
    ]


def test_parse_medalist_events_handles_rowspan_bronzes_and_team_rosters():
    from scrape_south_american_games import parse_medalist_events

    edition = {"edition_id": "2022", "edition_name": "Asunción 2022", "year": "2022"}
    events = parse_medalist_events(WIKIPEDIA_MEDALISTS_HTML, edition)

    assert len(events) == 3
    individual = events[0]
    assert individual["event_code"] == "men_epee_individual"
    assert individual["classification"] == {"weapon": "Epee", "gender": "Men", "team": False}
    assert individual["rows"] == [
        {"rank": 1, "name": "Jhon Rodríguez", "country": "COL", "medal": "Gold", "athlete_id": None},
        {"rank": 2, "name": "Francisco Limardo", "country": "VEN", "medal": "Silver", "athlete_id": None},
        {"rank": 3, "name": "Alexandre Camargo", "country": "BRA", "medal": "Bronze", "athlete_id": None},
        {"rank": 3, "name": "Jesús Lugones", "country": "ARG", "medal": "Bronze", "athlete_id": None},
    ]

    team = events[1]
    assert team["event_code"] == "men_foil_team"
    assert team["classification"] == {"weapon": "Foil", "gender": "Men", "team": True}
    assert team["rows"][:2] == [
        {"rank": 1, "name": "Guilherme Toldo", "country": "BRA", "medal": "Gold", "athlete_id": None},
        {"rank": 1, "name": "Henrique Marques", "country": "BRA", "medal": "Gold", "athlete_id": None},
    ]

    portuguese = events[2]
    assert portuguese["event_code"] == "women_sabre_team"
    assert portuguese["classification"] == {"weapon": "Sabre", "gender": "Women", "team": True}


def test_build_tournament_row_uses_required_source_id():
    from scrape_south_american_games import build_tournament_row

    event = {
        "edition_id": "2022",
        "edition_name": "Asunción 2022",
        "year": "2022",
        "event_code": "men_epee_individual",
        "event_name": "Espada individual masculino",
        "source_url": "https://example.test/results",
        "rows": [],
    }
    classification = {"weapon": "Epee", "gender": "Men", "team": False}

    row = build_tournament_row(event, classification)

    assert row["source_id"] == "south_american_games:2022:men_epee_individual"
    assert row["type"] == "south_american_games"
    assert row["weapon"] == "Epee"
    assert row["gender"] == "Men"
    assert row["metadata"]["team"] is False

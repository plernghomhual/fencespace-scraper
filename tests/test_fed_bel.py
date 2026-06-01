"""
Tests for scrape_fed_bel.py.

Fixtures mirror the public Ophardt pages linked from:
  https://www.fencing-belgium.be/nationa-a-l
  https://fencing.ophardt.online/en/search/rankings/159

Probe notes:
  - GET HTML, no auth, server-rendered tables.
  - Individual Senior and U20 rankings are public for all Foil/Epee/Sabre,
    Men/Women combinations.
  - Ranking page columns: Rank | Points | T-P | Name | Nation | Clubs | YOB.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_OPHARDT_EN = """
<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Discipline</th><th>Gender</th><th>Ageclass</th><th>Category</th><th>Calculated on</th></tr>
  </thead>
  <tbody>
    <tr><td>Epee</td><td>Men's</td><td>Senior</td><td>Individual</td><td>29.03.2026. 12:07</td></tr>
  </tbody>
</table>
<table>
  <thead>
    <tr>
      <th>Rank</th>
      <th>Points</th>
      <th>T-P</th>
      <th>Name</th>
      <th>Nation</th>
      <th>Clubs</th>
      <th>YOB</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>329.007</td>
      <td>0</td>
      <td>
        DE BOCK Cyrille Details Biography DE BOCK Cyrille
        <table><tr><th>Rank</th><th>Points</th><th>Competition</th></tr><tr><td>5</td><td>63.36</td><td>Ronse</td></tr></table>
      </td>
      <td>BEL FRA</td>
      <td>FF Les Mousquetaires Cinaciens</td>
      <td>2005</td>
    </tr>
    <tr>
      <td>2</td>
      <td>303.944</td>
      <td>0</td>
      <td>SAMYN Ward Details Biography SAMYN Ward</td>
      <td>BEL</td>
      <td>VS SC Parcival Leuven</td>
      <td>2007</td>
    </tr>
    <tr>
      <td>3</td>
      <td>273.966</td>
      <td>0</td>
      <td>HUSSON Geoffroy Details Biography HUSSON Geoffroy</td>
      <td>BEL</td>
      <td>FF La Maison de l'Escrime</td>
      <td>1993</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


FIXTURE_FRENCH_HEADERS = """
<table>
  <thead>
    <tr><th>Place</th><th>Points</th><th>P-T</th><th>Nom</th><th>Nation</th><th>Clubs</th><th>ddn</th></tr>
  </thead>
  <tbody>
    <tr>
      <td>2</td>
      <td>261,937</td>
      <td>0</td>
      <td>BRUYNOOGHE Renée Détails Biographie BRUYNOOGHE Renée</td>
      <td>BEL</td>
      <td>VS Confrerie Gent</td>
      <td>2006</td>
    </tr>
  </tbody>
</table>
"""


FIXTURE_DUTCH_HEADERS = """
<table>
  <thead>
    <tr><th>Plaats</th><th>Punten</th><th>Naam</th><th>Club</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>198,207</td><td>TACK Zoë</td><td>VS Confrerie Gent</td></tr>
  </tbody>
</table>
"""


FIXTURE_GERMAN_HEADERS = """
<table>
  <thead>
    <tr><th>Platz</th><th>Punkte</th><th>Ü-P</th><th>Name</th><th>Nation</th><th>Vereine</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>329,454</td><td>0</td><td>BÖTING Charlotte Detail Biographie BÖTING Charlotte</td><td>BEL</td><td>VS SC Latem-Deurle</td></tr>
    <tr><td>2</td><td>201,5</td><td>0</td><td>D'HOOGHE Élise Detail Biographie D'HOOGHE Élise</td><td>BEL</td><td>FF La Maison de l'Escrime</td></tr>
  </tbody>
</table>
"""


FIXTURE_NONSTANDARD_ROWS = """
<table>
  <thead>
    <tr><th>Rang</th><th>Nom</th><th>Club</th><th>Points</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Forfait</td><td>Example Club</td><td>0</td></tr>
    <tr><td>DQ</td><td>Disqualified</td><td>Example Club</td><td>0</td></tr>
    <tr><td>Total</td><td>Summary</td><td></td><td>999</td></tr>
    <tr><td>4</td><td>VAN LAECKE Wout</td><td>VS SC Parcival Leuven</td><td>515,133</td></tr>
  </tbody>
</table>
"""


def test_parse_bel_rankings_returns_rows_from_ophardt_fixture():
    from scrape_fed_bel import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_OPHARDT_EN)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "DE BOCK Cyrille",
        "club": "FF Les Mousquetaires Cinaciens",
        "points": 329.007,
    }
    assert rows[2]["name"] == "HUSSON Geoffroy"
    assert rows[2]["club"] == "FF La Maison de l'Escrime"


def test_parse_bel_empty_html_returns_empty_list():
    from scrape_fed_bel import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_bel_no_table_or_no_data_returns_empty_list():
    from scrape_fed_bel import parse_rankings_table

    assert parse_rankings_table("<html><body><p>Aucun classement disponible.</p></body></html>") == []
    assert parse_rankings_table("<table><thead><tr><th>Rank</th><th>Name</th></tr></thead><tbody></tbody></table>") == []


def test_parse_bel_skips_dns_dq_and_summary_rows():
    from scrape_fed_bel import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NONSTANDARD_ROWS)

    assert rows == [
        {
            "rank": 4,
            "name": "VAN LAECKE Wout",
            "club": "VS SC Parcival Leuven",
            "points": 515.133,
        }
    ]


def test_parse_bel_handles_french_dutch_and_german_headers():
    from scrape_fed_bel import parse_rankings_table

    french = parse_rankings_table(FIXTURE_FRENCH_HEADERS)
    dutch = parse_rankings_table(FIXTURE_DUTCH_HEADERS)
    german = parse_rankings_table(FIXTURE_GERMAN_HEADERS)

    assert french[0]["name"] == "BRUYNOOGHE Renée"
    assert french[0]["points"] == 261.937
    assert dutch[0]["name"] == "TACK Zoë"
    assert dutch[0]["points"] == 198.207
    assert german[0]["name"] == "BÖTING Charlotte"
    assert german[1]["name"] == "D'HOOGHE Élise"
    assert german[1]["club"] == "FF La Maison de l'Escrime"


def test_bel_ranking_combos_cover_public_senior_and_junior_individuals():
    from scrape_fed_bel import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert set(RANKING_COMBOS) == {
        ("Foil", "Men", "Senior"),
        ("Foil", "Women", "Senior"),
        ("Epee", "Men", "Senior"),
        ("Epee", "Women", "Senior"),
        ("Sabre", "Men", "Senior"),
        ("Sabre", "Women", "Senior"),
        ("Foil", "Men", "Junior"),
        ("Foil", "Women", "Junior"),
        ("Epee", "Men", "Junior"),
        ("Epee", "Women", "Junior"),
        ("Sabre", "Men", "Junior"),
        ("Sabre", "Women", "Junior"),
    }


def test_fetch_bel_rankings_page_returns_none_on_http_error(monkeypatch):
    import scrape_fed_bel

    class Response:
        status_code = 404
        text = "not found"

    def fake_get(*args, **kwargs):
        return Response()

    monkeypatch.setattr(scrape_fed_bel.requests, "get", fake_get)

    assert scrape_fed_bel.fetch_rankings_page("Epee", "Men", "Senior") is None

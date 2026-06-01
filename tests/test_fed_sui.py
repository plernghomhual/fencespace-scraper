"""
Tests for scrape_fed_sui.py.

Probe findings (2026-06-01):
  - swiss-fencing.ch links official national rankings to Ophardt Online:
    https://fencing.ophardt.online/fr/search/rankings/12
  - Requested swiss-fencing.ch paths /classements, /rankings, /ranglisten, and
    /ranking return 404, but the linked Ophardt "Circuit National" table is public.
  - Ranking pages are server-rendered HTML:
    https://fencing.ophardt.online/fr/search/rankings/show/<id>
    redirects to /fr/show-ranking/html/<id>.
  - Main table columns: Place | Points | P-T | Nom | Nation | Clubs | ddn | ...
"""
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_OPHARDT_FR = """<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Discipline</th><th>Sexe</th><th>Groupe d´âge</th><th>Categorie</th><th>Calculé le</th></tr>
  </thead>
  <tbody>
    <tr><td>Epée</td><td>Dames</td><td>Senior</td><td>Individuel</td><td>08.03.2026. 15:59</td></tr>
  </tbody>
</table>
<table>
  <thead>
    <tr>
      <th>Place</th>
      <th>Points</th>
      <th>P-T</th>
      <th>Nom</th>
      <th>Nation</th>
      <th>Clubs</th>
      <th>ddn</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>52</td>
      <td>0</td>
      <td>BRUNNER Pauline Détails Biographie BRUNNER Pauline × Place Points Compétition Ville Date 3 20 Geneva Tournament Genève (SUI)</td>
      <td>SUI</td>
      <td>SECH Chaux-de-Fonds</td>
      <td>1994</td>
    </tr>
    <tr>
      <td>2</td>
      <td>40,5</td>
      <td>0</td>
      <td>DEGEN Laura Détails Biographie DEGEN Laura × Place Points Compétition Ville Date</td>
      <td>SUI</td>
      <td>ZSZ FCZ Zug</td>
      <td>2001</td>
    </tr>
  </tbody>
</table>
</body>
</html>"""


FIXTURE_NO_TABLE = """<!DOCTYPE html>
<html><body><p>Aucun classement disponible.</p></body></html>
"""


FIXTURE_SKIP_ROWS = """<!DOCTYPE html>
<html>
<body>
<table>
  <thead><tr><th>Place</th><th>Points</th><th>P-T</th><th>Nom</th><th>Nation</th><th>Clubs</th></tr></thead>
  <tbody>
    <tr><td>DNS</td><td>0</td><td>0</td><td>Absent Fencer</td><td>SUI</td><td>Club A</td></tr>
    <tr><td>DQ</td><td>0</td><td>0</td><td>Disqualified Fencer</td><td>SUI</td><td>Club B</td></tr>
    <tr><td>Total</td><td>92</td><td></td><td>Résumé</td><td></td><td></td></tr>
    <tr><td>3</td><td>26</td><td>0</td><td>DUBOIS Zoé Détails Biographie DUBOIS Zoé ×</td><td>SUI</td><td>VD CEF Founex</td></tr>
  </tbody>
</table>
</body>
</html>"""


FIXTURE_GERMAN_HEADERS = """<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Rang</th><th>Name</th><th>Verein</th><th>Punkte</th></tr>
  </thead>
  <tbody>
    <tr><td>1.</td><td>MÜLLER Zoë-Léna</td><td>ZFC Zürich</td><td>1'234,5</td></tr>
  </tbody>
</table>
</body>
</html>"""


def test_parse_swiss_ophardt_rankings_returns_rows():
    from scrape_fed_sui import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_OPHARDT_FR)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "BRUNNER Pauline"
    assert rows[0]["club"] == "SECH Chaux-de-Fonds"
    assert rows[0]["points"] == 52.0
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "DEGEN Laura"
    assert rows[1]["points"] == 40.5


def test_parse_swiss_rankings_empty_html_returns_empty_list():
    from scrape_fed_sui import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("   ") == []


def test_parse_swiss_rankings_no_table_returns_empty_list():
    from scrape_fed_sui import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_TABLE) == []


def test_parse_swiss_rankings_skips_dns_dq_and_summary_rows():
    from scrape_fed_sui import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_SKIP_ROWS)

    assert rows == [
        {
            "rank": 3,
            "name": "DUBOIS Zoé",
            "club": "VD CEF Founex",
            "points": 26.0,
        }
    ]


def test_parse_swiss_rankings_accepts_language_headers_and_preserves_accents():
    from scrape_fed_sui import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_GERMAN_HEADERS)

    assert rows == [
        {
            "rank": 1,
            "name": "MÜLLER Zoë-Léna",
            "club": "ZFC Zürich",
            "points": 1234.5,
        }
    ]


def test_ranking_combos_cover_all_senior_and_junior_weapon_gender_combos():
    from scrape_fed_sui import RANKING_COMBOS

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


def test_current_season_format():
    from scrape_fed_sui import current_season

    season = current_season()
    assert re.match(r"^\d{4}-\d{4}$", season)
    start, end = season.split("-")
    assert int(end) == int(start) + 1


def test_fetch_rankings_page_returns_none_on_http_error(monkeypatch):
    import scrape_fed_sui

    class Response:
        status_code = 404
        text = "not found"

    def fake_get(*args, **kwargs):
        return Response()

    monkeypatch.setattr(scrape_fed_sui.requests, "get", fake_get)

    assert scrape_fed_sui.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_on_network_error(monkeypatch):
    import scrape_fed_sui

    def fake_get(*args, **kwargs):
        raise requests.RequestException("connection failed")

    monkeypatch.setattr(scrape_fed_sui.requests, "get", fake_get)

    assert scrape_fed_sui.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_row_metadata_includes_language_and_source_url():
    from scrape_fed_sui import _row_metadata

    metadata = _row_metadata("Epee", "Women", "Senior")

    assert metadata["source_language"] == "fr"
    assert metadata["data_format"] == "html"
    assert metadata["file_url"] == "https://fencing.ophardt.online/fr/search/rankings/show/21064"
    assert metadata["official_index_url"] == "https://fencing.ophardt.online/fr/search/rankings/12"

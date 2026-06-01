"""
Tests for scrape_fed_esp.py.

Probe findings:
  - The old rfeespada.es host did not resolve from the local probe.
  - esgrima.es links RFEE rankings to Skermo:
    https://app.skermo.org/ranking-rfee/public/RFEE
  - Ranking pages are public server-rendered HTML tables fetched by GET:
    ?setLang=es&season=16&weapon=F&category=7&gender=M
  - Columns: Posicion/Posición | Nombre | Apellidos | Fecha nacimiento | Club | Puntuación
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_HTML = """
<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr>
      <th>Posición</th>
      <th>Nombre</th>
      <th>Apellidos</th>
      <th>Fecha nacimiento</th>
      <th>Club</th>
      <th>Puntuación</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>1. IGNACIO</td>
      <td>BRETEAU IANNUZZI</td>
      <td>03/08/1999</td>
      <td>CEA-C</td>
      <td>5.641,93</td>
    </tr>
    <tr>
      <td>2</td>
      <td>2. DARIO</td>
      <td>OLANGUA FERNÁNDEZ</td>
      <td>18/12/2007</td>
      <td>SAM-B</td>
      <td>5.205,96</td>
    </tr>
    <tr>
      <td>3</td>
      <td>3. LAIA</td>
      <td>MARTÍN HERNÁNDEZ</td>
      <td>28/10/2007</td>
      <td>EHB-B</td>
      <td>12.292,34</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


FIXTURE_SIMPLE_HEADERS = """
<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Puesto</th><th>Nombre</th><th>Club</th><th>Puntos</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>ÍÑIGO PEÑA ÑUÑO</td><td>CESAN</td><td>1.234,50</td></tr>
  </tbody>
</table>
</body>
</html>
"""


FIXTURE_EMPTY_TABLE = """
<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Posición</th><th>Nombre</th><th>Apellidos</th><th>Club</th><th>Puntuación</th></tr>
  </thead>
  <tbody></tbody>
</table>
</body>
</html>
"""


FIXTURE_NO_DATA = """
<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Posición</th><th>Nombre</th><th>Club</th><th>Puntuación</th></tr>
  </thead>
  <tbody>
    <tr><td colspan="4">No hay datos disponibles</td></tr>
  </tbody>
</table>
</body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Posición</th><th>Nombre</th><th>Apellidos</th><th>Club</th><th>Puntuación</th></tr>
  </thead>
  <tbody>
    <tr><td>DQ</td><td>PERSONA</td><td>DESCALIFICADA</td><td>CLUB</td><td>0</td></tr>
    <tr><td>DNS</td><td>PERSONA</td><td>NO PRESENTADA</td><td>CLUB</td><td>0</td></tr>
    <tr><td>Total</td><td>Participantes</td><td></td><td></td><td>2</td></tr>
    <tr><td>4</td><td>4. MARÍA JOSÉ</td><td>MUÑOZ SÁNCHEZ</td><td>CE-M</td><td>987,65</td></tr>
  </tbody>
</table>
</body>
</html>
"""


def test_parse_esp_rankings_returns_rows():
    from scrape_fed_esp import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "IGNACIO BRETEAU IANNUZZI",
        "club": "CEA-C",
        "points": 5641.93,
    }
    assert rows[1]["name"] == "DARIO OLANGUA FERNÁNDEZ"
    assert rows[1]["points"] == 5205.96
    assert rows[2]["name"] == "LAIA MARTÍN HERNÁNDEZ"
    assert rows[2]["points"] == 12292.34


def test_parse_esp_rankings_empty_html_returns_empty_list():
    from scrape_fed_esp import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table(FIXTURE_EMPTY_TABLE) == []


def test_parse_esp_rankings_no_table_or_no_data_returns_empty_list():
    from scrape_fed_esp import parse_rankings_table

    assert parse_rankings_table("<html><body><p>Sin clasificaciones.</p></body></html>") == []
    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_esp_rankings_skips_dns_dq_and_summary_rows():
    from scrape_fed_esp import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 1
    assert rows[0]["rank"] == 4
    assert rows[0]["name"] == "MARÍA JOSÉ MUÑOZ SÁNCHEZ"
    assert rows[0]["points"] == 987.65


def test_parse_esp_rankings_spanish_headers_and_characters():
    from scrape_fed_esp import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_SIMPLE_HEADERS)

    assert len(rows) == 1
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "ÍÑIGO PEÑA ÑUÑO"
    assert rows[0]["club"] == "CESAN"
    assert rows[0]["points"] == 1234.5


def test_fetch_rankings_page_returns_none_on_http_error(monkeypatch):
    from scrape_fed_esp import fetch_rankings_page

    class Response:
        status_code = 404
        text = "not found"
        url = "https://app.skermo.org/ranking-rfee/public/RFEE"

    def fake_get(*args, **kwargs):
        return Response()

    monkeypatch.setattr("scrape_fed_esp.requests.get", fake_get)

    assert fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_uses_public_skermo_params(monkeypatch):
    from scrape_fed_esp import fetch_rankings_page

    captured = {}

    class Response:
        status_code = 200
        text = FIXTURE_HTML
        url = "https://app.skermo.org/ranking-rfee/public/RFEE"

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs["params"]
        captured["headers"] = kwargs["headers"]
        return Response()

    monkeypatch.setattr("scrape_fed_esp.requests.get", fake_get)

    html = fetch_rankings_page("Foil", "Men", "Senior")

    assert html == FIXTURE_HTML
    assert captured["url"] == "https://app.skermo.org/ranking-rfee/public/RFEE"
    assert captured["params"]["setLang"] == "es"
    assert captured["params"]["weapon"] == "F"
    assert captured["params"]["category"] == "7"
    assert captured["params"]["gender"] == "M"
    assert "Mozilla/5.0" in captured["headers"]["User-Agent"]


def test_current_season_uses_end_year_for_pre_july_season(monkeypatch):
    import scrape_fed_esp

    class FixedDatetime:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 6, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(scrape_fed_esp, "datetime", FixedDatetime)
    monkeypatch.setattr(
        scrape_fed_esp,
        "_shared_normalize_season",
        lambda end_year: f"{end_year - 1}-{end_year}",
    )

    assert scrape_fed_esp.current_season() == "2025-2026"
    assert scrape_fed_esp._season_to_skermo_id(scrape_fed_esp.current_season()) == "16"

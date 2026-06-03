"""
Tests for scrape_fed_ven.py.

Probe evidence:
  - Probe target: fevenesgrima.com.ve.
  - Method tried: GET with browser-like headers.
  - Paths tried from the sandbox: /, /ranking, /rankings, /ranking-nacional,
    /rankings-nacionales, /clasificacion, /clasificaciones, /resultados,
    /competencias, and WordPress wp-json search/page/post ranking endpoints
    on apex and www hosts, over both HTTPS and HTTP.
  - Response format: no response body; every probed URL failed DNS resolution.
  - Escalated outside-sandbox confirmation was blocked by the approval system,
    so no durable public ranking source could be verified.

Fixtures use the required Venezuela Spanish ranking column shape:
  Posición/Puesto | Esgrimista/Nombre | Estado/Club | Puntos
"""

import os
import sys
from datetime import datetime, timezone

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


SPANISH_RANKING_HTML = """
<!doctype html>
<html lang="es">
<body>
  <table class="tabla-ranking">
    <thead>
      <tr>
        <th>Posición</th>
        <th>Esgrimista</th>
        <th>Estado</th>
        <th>Puntos</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>LIMARDO Gascón Rubén Darío</td><td>Bolívar</td><td>1.234,50</td></tr>
      <tr><td>2.</td><td>RODRÍGUEZ María José</td><td>Distrito Capital</td><td>98,75</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


NATIVE_SCRIPT_HEADER_HTML = """
<table>
  <tr><th>Puesto</th><th>Nombre</th><th>Club</th><th>Puntos acumulados</th></tr>
  <tr><td>1°</td><td>HERNÁNDEZ Ana Софía</td><td>Caracas Fencing Club</td><td>1,234.50</td></tr>
  <tr><td>2</td><td>李 MARTÍNEZ Valeria</td><td></td><td>42,5</td></tr>
</table>
"""


SKIP_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Pos.</th><th>Esgrimista</th><th>Estado</th><th>Puntos</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>No se presentó</td><td>Carabobo</td><td>0</td></tr>
    <tr><td>DQ</td><td>Descalificado</td><td>Miranda</td><td>0</td></tr>
    <tr><td>Total</td><td>Resumen categoría</td><td></td><td>3.000</td></tr>
    <tr><td>abc</td><td>Fila malformada</td><td>Zulia</td><td>7</td></tr>
    <tr><td>0</td><td>Sin ranking</td><td>Lara</td><td>0</td></tr>
    <tr><td>3</td><td>PÉREZ Núñez Carlos</td><td>Aragua</td><td>12,25</td></tr>
  </tbody>
</table>
"""


NO_DATA_HTML = """
<html>
<body>
  <h1>Clasificación nacional</h1>
  <p>No hay ranking disponible para esta categoría.</p>
</body>
</html>
"""


class FakeResponse:
    def __init__(self, *, status_code=200, text="", url="https://example.test/ranking"):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = {"content-type": "text/html; charset=UTF-8"}


def test_parse_rankings_table_returns_valid_rows():
    from scrape_fed_ven import parse_rankings_table

    rows = parse_rankings_table(SPANISH_RANKING_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "LIMARDO Gascón Rubén Darío",
            "club": "Bolívar",
            "points": 1234.5,
        },
        {
            "rank": 2,
            "name": "RODRÍGUEZ María José",
            "club": "Distrito Capital",
            "points": 98.75,
        },
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_ven import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_ven import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_non_numeric_and_zero_rank_rows():
    from scrape_fed_ven import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "PÉREZ Núñez Carlos",
            "club": "Aragua",
            "points": 12.25,
        }
    ]


def test_parse_language_specific_headers_and_native_script_names_are_preserved():
    from scrape_fed_ven import parse_rankings_table

    rows = parse_rankings_table(NATIVE_SCRIPT_HEADER_HTML)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "HERNÁNDEZ Ana Софía"
    assert rows[0]["club"] == "Caracas Fencing Club"
    assert rows[0]["points"] == 1234.5
    assert rows[1]["name"] == "李 MARTÍNEZ Valeria"
    assert rows[1]["club"] is None
    assert rows[1]["points"] == 42.5


def test_ranking_combos_cover_all_required_venezuela_rankings():
    from scrape_fed_ven import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_returns_none_without_public_combo_url(capsys):
    from scrape_fed_ven import BASE_URL, fetch_rankings_page

    assert fetch_rankings_page("Foil", "Men", "Senior") is None
    assert f"No scrapeable rankings at {BASE_URL}" in capsys.readouterr().out


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_ven

    def fake_request(method, url, **kwargs):
        return FakeResponse(status_code=404, text="missing", url=url)

    monkeypatch.setitem(
        scrape_fed_ven.PUBLIC_RANKING_URLS,
        ("Foil", "Men", "Senior"),
        "https://example.test/ranking/senior-men-foil",
    )
    monkeypatch.setattr(scrape_fed_ven, "federation_request", fake_request)

    assert scrape_fed_ven.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_on_network_error(monkeypatch):
    import scrape_fed_ven

    def raise_timeout(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setitem(
        scrape_fed_ven.PUBLIC_RANKING_URLS,
        ("Epee", "Women", "Junior"),
        "https://example.test/ranking/junior-women-epee",
    )
    monkeypatch.setattr(scrape_fed_ven, "federation_request", raise_timeout)

    assert scrape_fed_ven.fetch_rankings_page("Epee", "Women", "Junior") is None


@pytest.mark.parametrize(
    "html",
    [
        "<html><body><form action='/login'><input type='password'></form>Iniciar sesión</body></html>",
        "<html><body><div id='app'></div><script src='/main.js'></script>Debe activar JavaScript</body></html>",
        NO_DATA_HTML,
    ],
)
def test_fetch_rankings_page_returns_none_for_login_js_or_no_data_pages(monkeypatch, html):
    import scrape_fed_ven

    def fake_request(method, url, **kwargs):
        return FakeResponse(text=html, url=url)

    monkeypatch.setitem(
        scrape_fed_ven.PUBLIC_RANKING_URLS,
        ("Sabre", "Men", "Senior"),
        "https://example.test/ranking/senior-men-sabre",
    )
    monkeypatch.setattr(scrape_fed_ven, "federation_request", fake_request)

    assert scrape_fed_ven.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_fetch_rankings_page_returns_html_when_rankings_table_is_present(monkeypatch):
    import scrape_fed_ven

    def fake_request(method, url, **kwargs):
        return FakeResponse(text=SPANISH_RANKING_HTML, url=url)

    monkeypatch.setitem(
        scrape_fed_ven.PUBLIC_RANKING_URLS,
        ("Foil", "Women", "Senior"),
        "https://example.test/ranking/senior-women-foil",
    )
    monkeypatch.setattr(scrape_fed_ven, "federation_request", fake_request)

    assert scrape_fed_ven.fetch_rankings_page("Foil", "Women", "Senior") == SPANISH_RANKING_HTML


def test_main_attempts_all_12_combos_and_records_stub_summary(monkeypatch, capsys):
    import scrape_fed_ven

    attempted = []
    complete_calls = []
    state_calls = []

    class FakeLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            return self

        def complete(self, **kwargs):
            complete_calls.append(kwargs)

        def error(self, exc_str):
            raise AssertionError(f"unexpected error log: {exc_str}")

    def fake_fetch(weapon, gender, category):
        attempted.append((weapon, gender, category))
        return None

    monkeypatch.setattr(scrape_fed_ven, "ScraperRunLogger", FakeLogger)
    monkeypatch.setattr(scrape_fed_ven, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_ven, "write_rankings", lambda *args, **kwargs: 0)
    monkeypatch.setattr(scrape_fed_ven, "set_state", lambda source, key, value: state_calls.append((source, key, value)))
    monkeypatch.setattr(scrape_fed_ven.time, "sleep", lambda seconds: None)

    scrape_fed_ven.main()

    output = capsys.readouterr().out
    assert attempted == scrape_fed_ven.RANKING_COMBOS
    assert "No scrapeable rankings at" in output
    assert complete_calls[0]["written"] == 0
    assert complete_calls[0]["failed"] == 12
    assert complete_calls[0]["skipped"] == 0
    assert state_calls[0][0] == scrape_fed_ven.SOURCE
    assert state_calls[0][1] == "last_run"
    summary = state_calls[0][2]
    assert summary["metadata"]["combos_attempted"] == 12
    assert summary["metadata"]["combos_working"] == 0
    assert len(summary["metadata"]["failed_combos"]) == 12


def test_current_season_uses_yyyy_range_before_july(monkeypatch):
    import scrape_fed_ven

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 2, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(scrape_fed_ven, "datetime", FixedDateTime)

    assert scrape_fed_ven.current_season() == "2025-2026"

"""
Tests for scrape_fed_mex.py.

Probe evidence:
  - Target URL: fme.com.mx
  - Request method: GET
  - Non-escalated probe tried https/http and www/non-www variants plus common
    Spanish ranking/API paths. Every target failed DNS resolution.
  - Required escalated retry was rejected by the approval usage-limit gate.
  - Search found older esgrimamexico.com.mx PDF result archives, not a durable
    current fme.com.mx national rankings source.

The scraper is therefore a safe stub for live fetching, but keeps parser
coverage for realistic Spanish HTML ranking tables.
"""

import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


SPANISH_RANKING_HTML = """
<!doctype html>
<html>
<body>
  <table>
    <thead>
      <tr>
        <th>Posición</th>
        <th>Nombre</th>
        <th>Club</th>
        <th>Puntos</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>1</td>
        <td>CANO NIÑO José Ángel</td>
        <td>CDMX</td>
        <td>1.234,50</td>
      </tr>
      <tr>
        <td>2º</td>
        <td>MARTÍNEZ 山田 Ana María</td>
        <td>JAL</td>
        <td>98,75</td>
      </tr>
    </tbody>
  </table>
</body>
</html>
"""


PUESTO_HEADER_HTML = """
<table>
  <tr><th>Puesto</th><th>Atleta</th><th>Asociación</th><th>Pts.</th></tr>
  <tr><td>3</td><td>DE LA PEÑA Sofía</td><td>UNAM</td><td>42,5</td></tr>
</table>
"""


NO_DATA_HTML = """
<!doctype html>
<html>
<body>
  <h1>Rankings</h1>
  <p>No hay datos disponibles para esta categoría.</p>
</body>
</html>
"""


NON_STANDARD_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Posición</th><th>Nombre</th><th>Club</th><th>Puntos</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Atleta Ausente</td><td>BC</td><td>0</td></tr>
    <tr><td>DQ</td><td>Atleta Descalificado</td><td>NL</td><td>0</td></tr>
    <tr><td>Total</td><td>Resumen general</td><td></td><td>120</td></tr>
    <tr><td>0</td><td>Ranking cero</td><td>PUE</td><td>0</td></tr>
    <tr><td>abc</td><td>Fila sin ranking</td><td>YUC</td><td>12</td></tr>
    <tr><td>4</td><td>GÓMEZ Hernández Lucía</td><td>QRO</td><td>12,25</td></tr>
  </tbody>
</table>
"""


class Response:
    def __init__(self, status_code=200, text="", url="https://fme.com.mx/rankings"):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = {"content-type": "text/html; charset=utf-8"}


def test_parse_spanish_table_returns_valid_rows():
    from scrape_fed_mex import parse_rankings_table

    rows = parse_rankings_table(SPANISH_RANKING_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "CANO NIÑO José Ángel",
            "club": "CDMX",
            "points": 1234.5,
        },
        {
            "rank": 2,
            "name": "MARTÍNEZ 山田 Ana María",
            "club": "JAL",
            "points": 98.75,
        },
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_mex import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_mex import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_zero_rank_and_non_numeric_rows():
    from scrape_fed_mex import parse_rankings_table

    rows = parse_rankings_table(NON_STANDARD_ROWS_HTML)

    assert rows == [
        {
            "rank": 4,
            "name": "GÓMEZ Hernández Lucía",
            "club": "QRO",
            "points": 12.25,
        }
    ]


def test_parse_spanish_puesto_headers_and_club_abbreviations():
    from scrape_fed_mex import parse_rankings_table

    rows = parse_rankings_table(PUESTO_HEADER_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "DE LA PEÑA Sofía",
            "club": "UNAM",
            "points": 42.5,
        }
    ]


def test_ranking_combos_contains_all_twelve_standard_combos():
    from scrape_fed_mex import RANKING_COMBOS

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


def test_fetch_returns_none_for_404(monkeypatch):
    import scrape_fed_mex

    monkeypatch.setattr(
        scrape_fed_mex,
        "federation_request",
        lambda *args, **kwargs: Response(status_code=404),
    )

    assert scrape_fed_mex.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_returns_none_for_network_error(monkeypatch):
    import scrape_fed_mex

    def fail_request(*args, **kwargs):
        raise requests.ConnectionError("dns failure")

    monkeypatch.setattr(scrape_fed_mex, "federation_request", fail_request)

    assert scrape_fed_mex.fetch_rankings_page("Epee", "Women", "Junior") is None


@pytest.mark.parametrize(
    ("status_code", "body"),
    [
        (403, "<html><body>Access denied</body></html>"),
        (200, "<html><form><input name='password'></form>Iniciar sesión</html>"),
        (200, "<html><div id='root'></div><script src='/app.js'></script></html>"),
    ],
)
def test_fetch_returns_none_for_blocked_login_or_js_only_pages(
    monkeypatch,
    status_code,
    body,
):
    import scrape_fed_mex

    monkeypatch.setattr(
        scrape_fed_mex,
        "federation_request",
        lambda *args, **kwargs: Response(status_code=status_code, text=body),
    )

    assert scrape_fed_mex.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_fetch_unknown_combo_returns_none():
    from scrape_fed_mex import fetch_rankings_page

    assert fetch_rankings_page("Rapier", "Mixed", "Open") is None


def test_main_stub_attempts_all_twelve_combos_and_exits_zero(monkeypatch, capsys):
    import scrape_fed_mex

    attempted = []
    completed = []
    states = []

    class FakeRunLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            return self

        def complete(self, *, written=0, failed=0, skipped=0, metadata=None):
            completed.append(
                {
                    "written": written,
                    "failed": failed,
                    "skipped": skipped,
                    "metadata": metadata,
                }
            )

        def error(self, exc_str):
            raise AssertionError(f"unexpected logger error: {exc_str}")

    def fake_fetch(weapon, gender, category):
        attempted.append((weapon, gender, category))
        return None

    monkeypatch.setattr(scrape_fed_mex, "ScraperRunLogger", FakeRunLogger)
    monkeypatch.setattr(scrape_fed_mex, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_mex, "write_rankings", lambda *args, **kwargs: 0)
    monkeypatch.setattr(scrape_fed_mex.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        scrape_fed_mex,
        "set_state",
        lambda source, key, value: states.append((source, key, value)),
    )

    scrape_fed_mex.main()

    out = capsys.readouterr().out
    assert attempted == scrape_fed_mex.RANKING_COMBOS
    assert "No scrapeable rankings at" in out
    assert completed == [
        {
            "written": 0,
            "failed": 12,
            "skipped": 0,
            "metadata": {
                "season": scrape_fed_mex.current_season(),
                "combos": 12,
                "working_combos": 0,
                "failed_combos": [
                    f"{weapon} {gender} {category}"
                    for weapon, gender, category in scrape_fed_mex.RANKING_COMBOS
                ],
                "probe_status": "stub_no_public_rankings",
            },
        }
    ]
    assert states[-1][0] == scrape_fed_mex.SOURCE
    assert states[-1][1] == "last_run"

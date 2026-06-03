"""
Tests for scrape_fed_pur.py.

Probe evidence:
  - Requested host fepur.org did not resolve from the local sandbox probe.
  - Current public federation site: https://fedesgrimapuertorico.org/ranking/
  - Ranking page is public HTML with category sections ADULTO/JUVENIL/etc.
  - Adult ranking link observed in the rendered page:
      /wp-content/uploads/2026/04/Ranking-Nacional-Adulto-2025-2026-Actualizado-abril-252026.xlsx
  - Request method: GET.
  - Response format: XLSX workbook links from the ranking page.
"""

import io
import os
import sys
from datetime import datetime, timezone

from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


SPANISH_TABLE_HTML = """
<table>
  <thead>
    <tr><th>Posición</th><th>Nombre</th><th>Club</th><th>Puntos</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>RIVERA Sofía</td><td>Club Olímpico</td><td>1.234,50</td></tr>
    <tr><td>2</td><td>MARTÍNEZ José 佐藤</td><td>San Juan FC</td><td>980,25</td></tr>
  </tbody>
</table>
"""


SKIP_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Puesto</th><th>Atleta</th><th>Club</th><th>Puntuación</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>No Presentó</td><td>Bayamón</td><td>0</td></tr>
    <tr><td>DQ</td><td>Descalificada</td><td>Ponce</td><td>0</td></tr>
    <tr><td>Total</td><td>Resumen</td><td></td><td>100</td></tr>
    <tr><td>N/A</td><td>Fila inválida</td><td></td><td>10</td></tr>
    <tr><td>3</td><td>GONZÁLEZ Camila</td><td>Mayagüez</td><td>77,5</td></tr>
  </tbody>
</table>
"""


NO_DATA_HTML = """
<html><body><h1>Ranking</h1><p>No hay ranking disponible.</p></body></html>
"""


RANKING_INDEX_HTML = """
<html>
<body>
  <h2>ADULTO</h2>
  <p><a href="https://example.test/adulto.xlsx">Ver ranking</a></p>
  <h2>JUVENIL</h2>
  <p><a href="/juvenil-download/">Ver ranking</a></p>
</body>
</html>
"""


JUNIOR_DOWNLOAD_PAGE = """
<html><body><a href="https://example.test/juvenil.xlsx">Ranking Nacional Juvenil</a></body></html>
"""


LOGIN_ONLY_HTML = """
<html><body><form><input name="log" /><p>Iniciar sesión para ver el ranking.</p></form></body></html>
"""


JS_ONLY_HTML = """
<html><body><div id="app">Loading rankings...</div><script src="/ranking.js"></script></body></html>
"""


class FakeResponse:
    def __init__(self, *, status_code=200, text="", content=b"", headers=None, url="https://example.test/"):
        self.status_code = status_code
        self.text = text
        self.content = content
        self.headers = headers or {}
        self.url = url


def _make_workbook_bytes(sheet_title="Espada Femenino Adulto", include_sheet=True) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_title if include_sheet else "Resumen"
    worksheet.append(["Federación de Esgrima de Puerto Rico"])
    worksheet.append(["Ranking Nacional 2025-2026"])
    worksheet.append(["Posición", "Nombre", "Club", "Puntos"])
    worksheet.append([1, "RIVERA Sofía", "Club Olímpico", "1.234,50"])
    worksheet.append([2, "MARTÍNEZ José 佐藤", "San Juan FC", "980,25"])
    if not include_sheet:
        other = workbook.create_sheet("Florete Masculino Adulto")
        other.append(["Posición", "Nombre", "Club", "Puntos"])
        other.append([1, "LÓPEZ Andrés", "Carolina", 55])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_parse_rankings_table_returns_valid_spanish_rows():
    from scrape_fed_pur import parse_rankings_table

    rows = parse_rankings_table(SPANISH_TABLE_HTML)

    assert rows == [
        {"rank": 1, "name": "RIVERA Sofía", "club": "Club Olímpico", "points": 1234.5},
        {"rank": 2, "name": "MARTÍNEZ José 佐藤", "club": "San Juan FC", "points": 980.25},
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_pur import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_pur import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_non_numeric_rank_rows():
    from scrape_fed_pur import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {"rank": 3, "name": "GONZÁLEZ Camila", "club": "Mayagüez", "points": 77.5}
    ]


def test_ranking_combos_attempt_all_required_puerto_rico_combos():
    from scrape_fed_pur import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_discovers_public_xlsx_and_extracts_matching_sheet(monkeypatch):
    import scrape_fed_pur

    calls = []
    adult_bytes = _make_workbook_bytes("Espada Femenino Adulto")

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        if url == scrape_fed_pur.RANKING_PAGE:
            return FakeResponse(
                text=RANKING_INDEX_HTML,
                content=RANKING_INDEX_HTML.encode(),
                headers={"content-type": "text/html"},
                url=url,
            )
        if url == "https://example.test/adulto.xlsx":
            return FakeResponse(
                content=adult_bytes,
                headers={
                    "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                },
                url=url,
            )
        return FakeResponse(status_code=404, text="missing", content=b"missing", url=url)

    monkeypatch.setattr(scrape_fed_pur, "federation_request", fake_request)
    scrape_fed_pur._CATEGORY_LINK_CACHE = None
    scrape_fed_pur._WORKBOOK_CACHE.clear()

    content = scrape_fed_pur.fetch_rankings_page("Epee", "Women", "Senior")
    rows = scrape_fed_pur.parse_rankings_table(content)

    assert calls[0] == ("get", scrape_fed_pur.RANKING_PAGE)
    assert calls[1] == ("get", "https://example.test/adulto.xlsx")
    assert rows[0]["name"] == "RIVERA Sofía"
    assert rows[0]["points"] == 1234.5


def test_fetch_rankings_page_follows_download_page_for_junior_workbook(monkeypatch):
    import scrape_fed_pur

    junior_bytes = _make_workbook_bytes("Sable Masculino Juvenil")

    def fake_request(method, url, **kwargs):
        if url == scrape_fed_pur.RANKING_PAGE:
            return FakeResponse(
                text=RANKING_INDEX_HTML,
                content=RANKING_INDEX_HTML.encode(),
                headers={"content-type": "text/html"},
                url=url,
            )
        if url == "https://fedesgrimapuertorico.org/juvenil-download/":
            return FakeResponse(
                text=JUNIOR_DOWNLOAD_PAGE,
                content=JUNIOR_DOWNLOAD_PAGE.encode(),
                headers={"content-type": "text/html"},
                url=url,
            )
        if url == "https://example.test/juvenil.xlsx":
            return FakeResponse(
                content=junior_bytes,
                headers={
                    "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                },
                url=url,
            )
        return FakeResponse(status_code=404, text="missing", content=b"missing", url=url)

    monkeypatch.setattr(scrape_fed_pur, "federation_request", fake_request)
    scrape_fed_pur._CATEGORY_LINK_CACHE = None
    scrape_fed_pur._WORKBOOK_CACHE.clear()

    content = scrape_fed_pur.fetch_rankings_page("Sabre", "Men", "Junior")

    assert "RIVERA Sofía" in content


def test_fetch_rankings_page_returns_none_on_404_network_login_js_and_missing_combo(monkeypatch):
    import requests
    import scrape_fed_pur

    scenarios = {
        "404": FakeResponse(status_code=404, text="missing", content=b"missing"),
        "login": FakeResponse(text=LOGIN_ONLY_HTML, content=LOGIN_ONLY_HTML.encode(), headers={"content-type": "text/html"}),
        "js": FakeResponse(text=JS_ONLY_HTML, content=JS_ONLY_HTML.encode(), headers={"content-type": "text/html"}),
    }

    for response in scenarios.values():
        monkeypatch.setattr(scrape_fed_pur, "federation_request", lambda *args, **kwargs: response)
        scrape_fed_pur._CATEGORY_LINK_CACHE = None
        scrape_fed_pur._WORKBOOK_CACHE.clear()
        assert scrape_fed_pur.fetch_rankings_page("Foil", "Men", "Senior") is None

    def network_error(*args, **kwargs):
        raise requests.RequestException("blocked")

    monkeypatch.setattr(scrape_fed_pur, "federation_request", network_error)
    scrape_fed_pur._CATEGORY_LINK_CACHE = None
    scrape_fed_pur._WORKBOOK_CACHE.clear()
    assert scrape_fed_pur.fetch_rankings_page("Foil", "Men", "Senior") is None

    def missing_combo_request(method, url, **kwargs):
        if url == scrape_fed_pur.RANKING_PAGE:
            return FakeResponse(
                text=RANKING_INDEX_HTML,
                content=RANKING_INDEX_HTML.encode(),
                headers={"content-type": "text/html"},
                url=url,
            )
        return FakeResponse(
            content=_make_workbook_bytes(include_sheet=False),
            headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            url=url,
        )

    monkeypatch.setattr(scrape_fed_pur, "federation_request", missing_combo_request)
    scrape_fed_pur._CATEGORY_LINK_CACHE = None
    scrape_fed_pur._WORKBOOK_CACHE.clear()
    assert scrape_fed_pur.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_current_season_format_and_before_july(monkeypatch):
    import scrape_fed_pur

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 2, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(scrape_fed_pur, "datetime", FixedDateTime)

    assert scrape_fed_pur.current_season() == "2025-2026"

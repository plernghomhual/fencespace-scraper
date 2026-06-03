"""
Tests for scrape_fed_chi.py.

Probe evidence:
  - Requested host: feche.cl.
  - Current public FECHE site found during probe: https://esgrima.cl.
  - Weapon pages:
      https://esgrima.cl/espada/
      https://esgrima.cl/florete/
      https://esgrima.cl/sable/
  - Public ranking files are PDFs under:
      https://esgrima.cl/wp-content/uploads/2025/04/
  - Required category mapping:
      TODO COMPETIDOR -> Senior
      JUVENIL -> Junior

Relevant PDF text columns:
  Puntaje TOTAL | Ranking | DEPORTISTA | RUT | DV | FECHA DE NACIMIENTO | CLUB | event points
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_PDF_TEXT = """
RANKING NACIONAL 2025 RANKING 1 RANKING 2 RANKING 3 CAMPEONATO DE CHILE
ESPADA FEMENINA JUVENIL 13/04/2025 18/05/2025 22/06/2025
Puntaje
TOTAL
Ranking DEPORTISTA RUT D V FECHA DE NACIMIENTO CLUB Posicion Puntos
606.8 1 FRINDT ALLIENDE Marianne 21678613 0 03/01/2006 CDM 1 100 5 49 7 32
492,4 2 COMBATTI FLORES Simone 22608389 8 31/12/2007 CDEA 3 62 1 100 MED 81
488.4 3 RUIZ CORTES Pia 22484595 2 27/08/2007 CDEA 3 62 2 78 5 44
Posición Club Partic.
Ranking de Participantes por Club
1 CEPA 4
"""


FIXTURE_WRAPPED_SOURCE_ROW = """
RANKING NACIONAL 2025
FLORETE FEMENINO TODO COMPETIDOR
Puntaje TOTAL Ranking DEPORTISTA RUT DV FECHA DE NACIMIENTO CLUB Posicion Puntos
17 22 GARCIA SAMARTINO Helena PAAJ34584
4
23/2/2012 LF - 0 11 17 - 0 - 0 - 0
16 23 SABOGAL RENGIFO Alejandra 26113203 6 11/1/1995 CDEVA - 0 - 0 11 8 11 8
"""


SPANISH_HEADER_HTML = """
<html>
<body>
  <table>
    <thead>
      <tr><th>Puesto</th><th>Nombre</th><th>Club</th><th>Puntos</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>MUÑOZ CORVALAN Matilda 李</td><td>ELITE</td><td>1.234,50</td></tr>
      <tr><td>2</td><td>JAÑA OYARZUN María</td><td>A14</td><td>151,2</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


NO_DATA_HTML = """
<html><body><h1>Ranking</h1><p>No hay datos disponibles para esta categoría.</p></body></html>
"""


NON_STANDARD_ROWS = """
<table>
  <tr><th>Ranking</th><th>Nombre</th><th>Club</th><th>Puntos</th></tr>
  <tr><td>DNS</td><td>No se presentó</td><td>ABC</td><td>0</td></tr>
  <tr><td>DQ</td><td>Descalificada</td><td>ABC</td><td>0</td></tr>
  <tr><td>Total</td><td>Resumen</td><td></td><td>900</td></tr>
  <tr><td>0</td><td>Sin ranking válido</td><td>ABC</td><td>0</td></tr>
  <tr><td>Ranking</td><td>Encabezado repetido</td><td>Club</td><td>Puntos</td></tr>
  <tr><td>3</td><td>ÁVILA José</td><td>PR AMK Mestre Kato</td><td>98,5</td></tr>
</table>
"""


MALFORMED_TEXT = """
RANKING NACIONAL 2025
abc 1 SIN RANK CLUB 10
25 BADLY FORMED WITHOUT DATE OR CLUB 5
0 4 ZERO POINTS BUT VALID 12345678 1 01/01/2000 CDM - 0
"""


WEAPON_PAGE_HTML = """
<html>
<body>
  <h2>RANKING NACIONAL FEMENINO</h2>
  <h2>ESPADA 2026</h2>
  <a href="/wp-content/uploads/2025/04/ESPADA-FEMENINA-JUVENIL.pdf">JUVENIL</a>
  <a href="/wp-content/uploads/2025/04/ESPADA-FEMENINA-TODO-COMPETIDOR.pdf">TODO COMPETIDOR</a>
  <h2>RANKING INTERNACIONAL FEMENINO</h2>
  <a href="/wp-content/uploads/2025/04/INTERNACIONAL-FEMENINA.pdf">TODO COMPETIDOR</a>
  <h2>RANKING NACIONAL MASCULINO</h2>
  <h2>ESPADA 2026</h2>
  <a href="/wp-content/uploads/2025/04/ESPADA-MASCULINA-JUVENIL.pdf">JUVENIL</a>
  <a href="/wp-content/uploads/2025/04/ESPADA-MASCULINA-TODO-COMPETIDOR.pdf">TODO COMPETIDOR</a>
</body>
</html>
"""


def test_parse_chi_pdf_text_returns_ranked_rows():
    from scrape_fed_chi import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_PDF_TEXT)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "FRINDT ALLIENDE Marianne",
        "club": "CDM",
        "points": 606.8,
    }
    assert rows[1]["name"] == "COMBATTI FLORES Simone"
    assert rows[1]["points"] == 492.4


def test_parse_chi_pdf_text_handles_wrapped_id_rows_from_source():
    from scrape_fed_chi import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_WRAPPED_SOURCE_ROW)

    assert rows[0] == {
        "rank": 22,
        "name": "GARCIA SAMARTINO Helena",
        "club": "LF",
        "points": 17.0,
    }
    assert rows[1]["name"] == "SABOGAL RENGIFO Alejandra"
    assert rows[1]["club"] == "CDEVA"


def test_parse_chi_empty_html_returns_empty_list():
    from scrape_fed_chi import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_chi_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_chi import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_chi_skips_dns_dq_summary_zero_rank_and_malformed_rows():
    from scrape_fed_chi import parse_rankings_table

    rows = parse_rankings_table(NON_STANDARD_ROWS)
    malformed_rows = parse_rankings_table(MALFORMED_TEXT)

    assert rows == [
        {
            "rank": 3,
            "name": "ÁVILA José",
            "club": "PR AMK Mestre Kato",
            "points": 98.5,
        }
    ]
    assert malformed_rows == [
        {
            "rank": 4,
            "name": "ZERO POINTS BUT VALID",
            "club": "CDM",
            "points": 0.0,
        }
    ]


def test_parse_chi_spanish_headers_preserve_utf8_and_native_script_names():
    from scrape_fed_chi import parse_rankings_table

    rows = parse_rankings_table(SPANISH_HEADER_HTML)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "MUÑOZ CORVALAN Matilda 李"
    assert rows[0]["club"] == "ELITE"
    assert rows[0]["points"] == 1234.5
    assert rows[1]["name"] == "JAÑA OYARZUN María"
    assert rows[1]["points"] == 151.2


def test_ranking_combos_cover_all_required_chile_rankings():
    from scrape_fed_chi import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_extract_links_from_weapon_page_maps_public_national_sections():
    from scrape_fed_chi import _extract_links_from_weapon_page

    links = _extract_links_from_weapon_page("Epee", "https://esgrima.cl/espada/", WEAPON_PAGE_HTML)

    assert links[("Epee", "Women", "Junior")].endswith("/ESPADA-FEMENINA-JUVENIL.pdf")
    assert links[("Epee", "Women", "Senior")].endswith("/ESPADA-FEMENINA-TODO-COMPETIDOR.pdf")
    assert links[("Epee", "Men", "Junior")].endswith("/ESPADA-MASCULINA-JUVENIL.pdf")
    assert links[("Epee", "Men", "Senior")].endswith("/ESPADA-MASCULINA-TODO-COMPETIDOR.pdf")
    assert all("INTERNACIONAL" not in url for url in links.values())
    assert len(links) == 4


def test_fetch_rankings_page_extracts_pdf_text(monkeypatch):
    import scrape_fed_chi

    calls = []

    class FakeResponse:
        status_code = 200
        content = b"%PDF fake"
        text = ""
        headers = {"content-type": "application/pdf"}

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(
        scrape_fed_chi,
        "_RANKING_URLS_CACHE",
        {("Epee", "Men", "Senior"): "https://example.test/epee.pdf"},
    )
    monkeypatch.setattr(scrape_fed_chi, "federation_request", fake_request)
    monkeypatch.setattr(scrape_fed_chi, "_extract_pdf_text", lambda content: FIXTURE_PDF_TEXT)

    content = scrape_fed_chi.fetch_rankings_page("Epee", "Men", "Senior")

    assert content == FIXTURE_PDF_TEXT
    assert calls[0][0] == "get"
    assert calls[0][1] == "https://example.test/epee.pdf"


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_chi

    class FakeResponse:
        status_code = 404
        content = b"missing"
        text = "missing"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(
        scrape_fed_chi,
        "_RANKING_URLS_CACHE",
        {("Foil", "Women", "Senior"): "https://example.test/missing.pdf"},
    )
    monkeypatch.setattr(scrape_fed_chi, "federation_request", lambda *args, **kwargs: FakeResponse())

    assert scrape_fed_chi.fetch_rankings_page("Foil", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_on_blocked_status(monkeypatch):
    import scrape_fed_chi

    class FakeResponse:
        status_code = 403
        content = b"forbidden"
        text = "Forbidden"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(
        scrape_fed_chi,
        "_RANKING_URLS_CACHE",
        {("Sabre", "Women", "Junior"): "https://example.test/blocked.pdf"},
    )
    monkeypatch.setattr(scrape_fed_chi, "federation_request", lambda *args, **kwargs: FakeResponse())

    assert scrape_fed_chi.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_fetch_rankings_page_returns_none_on_login_only_html(monkeypatch):
    import scrape_fed_chi

    class FakeResponse:
        status_code = 200
        content = b"<html><form>Password</form></html>"
        text = "<html><body>Iniciar sesión para continuar</body></html>"
        headers = {"content-type": "text/html; charset=UTF-8"}

    monkeypatch.setattr(
        scrape_fed_chi,
        "_RANKING_URLS_CACHE",
        {("Epee", "Women", "Junior"): "https://example.test/login"},
    )
    monkeypatch.setattr(scrape_fed_chi, "federation_request", lambda *args, **kwargs: FakeResponse())

    assert scrape_fed_chi.fetch_rankings_page("Epee", "Women", "Junior") is None


def test_fetch_rankings_page_returns_none_on_js_only_html(monkeypatch):
    import scrape_fed_chi

    class FakeResponse:
        status_code = 200
        content = b"<html><div id='root'></div><script src='app.js'></script></html>"
        text = "<html><body><div id='root'></div><noscript>Enable JavaScript</noscript></body></html>"
        headers = {"content-type": "text/html; charset=UTF-8"}

    monkeypatch.setattr(
        scrape_fed_chi,
        "_RANKING_URLS_CACHE",
        {("Foil", "Men", "Junior"): "https://example.test/js"},
    )
    monkeypatch.setattr(scrape_fed_chi, "federation_request", lambda *args, **kwargs: FakeResponse())

    assert scrape_fed_chi.fetch_rankings_page("Foil", "Men", "Junior") is None


def test_fetch_rankings_page_returns_none_when_combo_missing(monkeypatch):
    import scrape_fed_chi

    monkeypatch.setattr(scrape_fed_chi, "_RANKING_URLS_CACHE", {})

    assert scrape_fed_chi.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_current_season_format_and_before_july(monkeypatch):
    import scrape_fed_chi

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 2, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(scrape_fed_chi, "datetime", FixedDateTime)

    assert scrape_fed_chi.current_season() == "2025-2026"


def test_main_attempts_all_12_combos_and_records_state(monkeypatch):
    import scrape_fed_chi

    attempted = []
    written_batches = []
    state_payload = {}
    complete_payload = {}
    fake_urls = {
        combo: f"https://example.test/{combo[0]}-{combo[1]}-{combo[2]}.pdf"
        for combo in scrape_fed_chi.RANKING_COMBOS
    }

    class FakeRunLog:
        def start(self):
            return self

        def complete(self, **kwargs):
            complete_payload.update(kwargs)

        def error(self, exc_str):
            raise AssertionError(exc_str)

    def fake_fetch(weapon, gender, category):
        attempted.append((weapon, gender, category))
        return FIXTURE_PDF_TEXT

    def fake_write(rows, source, season):
        written_batches.append((rows, source, season))
        return len(rows)

    monkeypatch.setattr(scrape_fed_chi, "_RANKING_URLS_CACHE", fake_urls)
    monkeypatch.setattr(scrape_fed_chi, "ScraperRunLogger", lambda module: FakeRunLog())
    monkeypatch.setattr(scrape_fed_chi, "get_state", lambda source, key: None)
    monkeypatch.setattr(scrape_fed_chi, "set_state", lambda source, key, value: state_payload.update(value))
    monkeypatch.setattr(scrape_fed_chi, "current_season", lambda: "2025-2026")
    monkeypatch.setattr(scrape_fed_chi, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_chi, "write_rankings", fake_write)
    monkeypatch.setattr(scrape_fed_chi.time, "sleep", lambda seconds: None)

    scrape_fed_chi.main()

    assert attempted == scrape_fed_chi.RANKING_COMBOS
    assert len(written_batches) == 12
    assert complete_payload["written"] == 36
    assert complete_payload["failed"] == 0
    assert complete_payload["skipped"] == 0
    assert state_payload["working_combos"] == 12
    assert state_payload["total_combos"] == 12

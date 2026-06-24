import requests

FIXTURE_RANKING_HTML = """
<html>
  <body>
    <h3>Ranking</h3>
    <p>Arma: ESPADA</p>
    <p>Genero: FEMENINO</p>
    <p>Tipo: INDIVIDUAL</p>
    <p>Categoria: JUVENIL</p>
    <h3>Puntajes</h3>
    <table>
      <thead>
        <tr>
          <th>Puesto</th>
          <th>Puntos</th>
          <th>Nombre</th>
          <th>Liga</th>
          <th>Club</th>
          <th>Fecha de nacimiento</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>1</td>
          <td>155.31</td>
          <td>CANO JIMÉNEZ IVANA GABRIELA</td>
          <td>CUNDINAMARCA</td>
          <td>GUARDIA REAL</td>
          <td>2007-03-07</td>
        </tr>
        <tr>
          <td>2</td>
          <td>132.92</td>
          <td>GONZALEZ RODRÍGUEZ ISABELLA</td>
          <td>ANTIOQUIA</td>
          <td>TIZONA ANTIOQUIA</td>
          <td>2006-10-12</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""


FIXTURE_NO_DATA_HTML = """
<html>
  <body>
    <h3>Ranking</h3>
    <p>No hay registros disponibles</p>
  </body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
<table>
  <tr>
    <th>Puesto</th>
    <th>Puntos</th>
    <th>Nombre</th>
    <th>Liga</th>
    <th>Club</th>
    <th>Fecha de nacimiento</th>
  </tr>
  <tr><td>DNS</td><td></td><td>NO PRESENTADA</td><td>BOGOTA</td><td>ARES</td><td></td></tr>
  <tr><td>DQ</td><td>0</td><td>DESCALIFICADA</td><td>VALLE</td><td>CELTAS</td><td></td></tr>
  <tr><td>Total:</td><td>188.0</td><td></td><td></td><td></td><td></td></tr>
  <tr><td>--</td><td>14.0</td><td>RANKLESS ROW</td><td>META</td><td>MOSQVILLAVO</td><td></td></tr>
  <tr>
    <td>3</td>
    <td>125,30</td>
    <td>CASTELLANOS REGALADO EMILY</td>
    <td>CUNDINAMARCA</td>
    <td>GUARDIA REAL</td>
    <td>2011-09-26</td>
  </tr>
</table>
"""


FIXTURE_SPANISH_HEADERS_AND_NATIVE_NAMES = """
<table>
  <tr>
    <th>Posición</th>
    <th>Puntaje</th>
    <th>Deportista</th>
    <th>Liga</th>
    <th>Club</th>
  </tr>
  <tr>
    <td>4</td>
    <td>104,46</td>
    <td>ZULUAGA ZULUAGA SOFIA</td>
    <td>ANTIOQUIA</td>
    <td>FENCING</td>
  </tr>
  <tr>
    <td>5</td>
    <td>98,75</td>
    <td>MARÍA JOSÉ 周</td>
    <td>BOGOTA</td>
    <td>SABRE D´OR</td>
  </tr>
</table>
"""


class FakeResponse:
    def __init__(self, status_code=200, text=FIXTURE_RANKING_HTML):
        self.status_code = status_code
        self.text = text


def test_parse_colombia_returns_rank_name_club_and_points():
    from scrape_fed_col import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_RANKING_HTML)

    assert rows[:2] == [
        {
            "rank": 1,
            "name": "CANO JIMÉNEZ IVANA GABRIELA",
            "club": "GUARDIA REAL",
            "points": 155.31,
        },
        {
            "rank": 2,
            "name": "GONZALEZ RODRÍGUEZ ISABELLA",
            "club": "TIZONA ANTIOQUIA",
            "points": 132.92,
        },
    ]


def test_parse_colombia_empty_html_returns_empty_list():
    from scrape_fed_col import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_colombia_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_col import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA_HTML) == []


def test_parse_colombia_skips_dns_dq_summary_and_non_numeric_rank_rows():
    from scrape_fed_col import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert rows == [
        {
            "rank": 3,
            "name": "CASTELLANOS REGALADO EMILY",
            "club": "GUARDIA REAL",
            "points": 125.3,
        }
    ]


def test_parse_colombia_spanish_headers_decimal_commas_and_native_names():
    from scrape_fed_col import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_SPANISH_HEADERS_AND_NATIVE_NAMES)

    assert rows[0] == {
        "rank": 4,
        "name": "ZULUAGA ZULUAGA SOFIA",
        "club": "FENCING",
        "points": 104.46,
    }
    assert rows[1]["name"] == "MARÍA JOSÉ 周"
    assert rows[1]["club"] == "SABRE D´OR"
    assert rows[1]["points"] == 98.75


def test_ranking_combos_cover_all_required_colombia_rankings():
    from scrape_fed_col import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_uses_public_combo_mapping(monkeypatch):
    import scrape_fed_col

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(scrape_fed_col, "federation_request", fake_request)

    content = scrape_fed_col.fetch_rankings_page("Epee", "Women", "Junior")

    assert content == FIXTURE_RANKING_HTML
    assert calls[0][0] == "get"
    assert calls[0][1] == "https://sistemainfo.fedesgrimacolombia.com/rankings/3"
    assert calls[0][2]["headers"] == scrape_fed_col.HEADERS
    assert calls[0][2]["timeout"] == 20


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_col

    monkeypatch.setattr(
        scrape_fed_col,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(status_code=404, text="missing"),
    )

    assert scrape_fed_col.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_network_error(monkeypatch):
    import scrape_fed_col

    def fake_request(*args, **kwargs):
        raise requests.RequestException("timeout")

    monkeypatch.setattr(scrape_fed_col, "federation_request", fake_request)

    assert scrape_fed_col.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_blocked_login_or_js_only(monkeypatch):
    import scrape_fed_col

    cases = [
        FakeResponse(status_code=403, text="Forbidden"),
        FakeResponse(status_code=200, text="<form><input type='password'></form>"),
        FakeResponse(status_code=200, text="<noscript>Enable JavaScript</noscript>"),
    ]

    for response in cases:
        monkeypatch.setattr(
            scrape_fed_col,
            "federation_request",
            lambda *args, response=response, **kwargs: response,
        )
        assert scrape_fed_col.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_missing_combo():
    from scrape_fed_col import fetch_rankings_page

    assert fetch_rankings_page("Foil", "Men", "Cadet") is None


def test_main_attempts_all_12_combos_and_logs_failures(monkeypatch):
    import scrape_fed_col

    attempted = []
    written_batches = []
    completed = {}

    class FakeLogger:
        def start(self):
            return self

        def complete(self, **kwargs):
            completed.update(kwargs)

        def error(self, exc):
            raise AssertionError(f"unexpected error log: {exc}")

    def fake_fetch(weapon, gender, category):
        attempted.append((weapon, gender, category))
        if (weapon, gender, category) == ("Foil", "Men", "Senior"):
            return FIXTURE_RANKING_HTML
        return None

    def fake_write(rows, **kwargs):
        written_batches.append((rows, kwargs))
        return len(rows)

    monkeypatch.setattr(scrape_fed_col, "ScraperRunLogger", lambda module: FakeLogger())
    monkeypatch.setattr(scrape_fed_col, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_col, "write_rankings", fake_write)
    monkeypatch.setattr(scrape_fed_col.time, "sleep", lambda seconds: None)

    scrape_fed_col.main()

    assert attempted == scrape_fed_col.RANKING_COMBOS
    assert len(written_batches) == 1
    assert written_batches[0][0][0]["source"] == scrape_fed_col.SOURCE
    assert written_batches[0][0][0]["country"] == scrape_fed_col.COUNTRY
    assert completed["written"] == 2
    assert completed["failed"] == 11
    assert completed["skipped"] == 0

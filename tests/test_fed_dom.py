from datetime import UTC, datetime, timezone

SPANISH_RANKING_HTML = """
<html>
  <body>
    <table class="ranking">
      <thead>
        <tr><th>Pos</th><th>Nombre</th><th>Club</th><th>Puntos</th></tr>
      </thead>
      <tbody>
        <tr><td>1</td><td>GARCIA Maria Jose</td><td>Club Naco</td><td>1.234,50</td></tr>
        <tr><td>2</td><td>RODRIGUEZ Ana Lucia</td><td>Centro Olimpico</td><td>98,75</td></tr>
      </tbody>
    </table>
  </body>
</html>
"""


LANGUAGE_HEADER_HTML = """
<table>
  <tr>
    <th>Posición</th>
    <th>Atleta</th>
    <th>Asociación / Club</th>
    <th>Puntos Totales</th>
  </tr>
  <tr>
    <td>1.</td>
    <td>PEÑA Sofía</td>
    <td>La Romana</td>
    <td>250,25</td>
  </tr>
  <tr>
    <td>2</td>
    <td>佐藤 Maria</td>
    <td>Santo Domingo</td>
    <td>175</td>
  </tr>
</table>
"""


SKIP_ROWS_HTML = """
<table>
  <tr><th>Pos</th><th>Nombre</th><th>Club</th><th>Puntos</th></tr>
  <tr><td>DNS</td><td>NO PRESENTE</td><td>Club Norte</td><td>0</td></tr>
  <tr><td>DQ</td><td>DESCALIFICADA</td><td>Club Sur</td><td>0</td></tr>
  <tr><td>Total</td><td>Resumen</td><td></td><td>600</td></tr>
  <tr><td>--</td><td>Sin ranking</td><td></td><td></td></tr>
  <tr><td>3</td><td>MARTINEZ Luis</td><td>Club Mauricio Baez</td><td>50,5</td></tr>
</table>
"""


NO_TABLE_HTML = """
<html>
  <body>
    <h1>ranking - fedomes</h1>
    <p>No hay ranking publicado en esta pagina.</p>
  </body>
</html>
"""


class FakeResponse:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {"content-type": "text/html; charset=UTF-8"}


def test_parse_spanish_ranking_table_returns_rank_name_club_points():
    from scrape_fed_dom import parse_rankings_table

    rows = parse_rankings_table(SPANISH_RANKING_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "GARCIA Maria Jose",
            "club": "Club Naco",
            "points": 1234.5,
        },
        {
            "rank": 2,
            "name": "RODRIGUEZ Ana Lucia",
            "club": "Centro Olimpico",
            "points": 98.75,
        },
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_dom import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_dom import parse_rankings_table

    assert parse_rankings_table(NO_TABLE_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_non_numeric_rows():
    from scrape_fed_dom import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "MARTINEZ Luis",
            "club": "Club Mauricio Baez",
            "points": 50.5,
        }
    ]


def test_parse_language_headers_and_native_script_names_are_preserved():
    from scrape_fed_dom import parse_rankings_table

    rows = parse_rankings_table(LANGUAGE_HEADER_HTML)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "PEÑA Sofía"
    assert rows[0]["club"] == "La Romana"
    assert rows[0]["points"] == 250.25
    assert rows[1]["name"] == "佐藤 Maria"
    assert rows[1]["club"] == "Santo Domingo"
    assert rows[1]["points"] == 175.0


def test_ranking_combos_cover_all_standard_dom_rankings():
    from scrape_fed_dom import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_returns_none_for_missing_public_combo(monkeypatch, capsys):
    import scrape_fed_dom

    monkeypatch.setattr(scrape_fed_dom, "PUBLIC_RANKING_URLS", {})
    monkeypatch.setattr(scrape_fed_dom.requests, "get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network should not be called")))

    assert scrape_fed_dom.fetch_rankings_page("Foil", "Men", "Senior") is None
    captured = capsys.readouterr()
    assert "No scrapeable rankings at https://www.fedomes.org/ranking" in captured.out


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_dom

    monkeypatch.setattr(
        scrape_fed_dom,
        "PUBLIC_RANKING_URLS",
        {("Foil", "Men", "Senior"): "https://example.test/ranking"},
    )
    monkeypatch.setattr(scrape_fed_dom.requests, "get", lambda *args, **kwargs: FakeResponse(status_code=404, text="missing"))

    assert scrape_fed_dom.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_when_blocked(monkeypatch):
    import scrape_fed_dom

    monkeypatch.setattr(
        scrape_fed_dom,
        "PUBLIC_RANKING_URLS",
        {("Epee", "Women", "Senior"): "https://example.test/blocked"},
    )
    monkeypatch.setattr(scrape_fed_dom.requests, "get", lambda *args, **kwargs: FakeResponse(status_code=403, text="Forbidden"))

    assert scrape_fed_dom.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_for_login_only_page(monkeypatch):
    import scrape_fed_dom

    monkeypatch.setattr(
        scrape_fed_dom,
        "PUBLIC_RANKING_URLS",
        {("Sabre", "Men", "Junior"): "https://example.test/login"},
    )
    monkeypatch.setattr(
        scrape_fed_dom.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(text="<form><input type='password'></form><p>Iniciar sesion</p>"),
    )

    assert scrape_fed_dom.fetch_rankings_page("Sabre", "Men", "Junior") is None


def test_fetch_rankings_page_returns_none_for_js_shell_without_public_api(monkeypatch):
    import scrape_fed_dom

    monkeypatch.setattr(
        scrape_fed_dom,
        "PUBLIC_RANKING_URLS",
        {("Sabre", "Women", "Junior"): "https://example.test/js-only"},
    )
    monkeypatch.setattr(
        scrape_fed_dom.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            text="<html><body><div id='app'></div><script src='/static/app.js'></script></body></html>"
        ),
    )

    assert scrape_fed_dom.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_current_season_uses_federation_range_format(monkeypatch):
    import scrape_fed_dom

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 2, tzinfo=tz or UTC)

    monkeypatch.setattr(scrape_fed_dom, "datetime", FixedDateTime)

    assert scrape_fed_dom.current_season() == "2025-2026"

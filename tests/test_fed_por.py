import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


PORTUGUESE_TABLE_HTML = """
<!doctype html>
<html>
  <body>
    <table>
      <thead>
        <tr>
          <th>Posição</th>
          <th>Nome</th>
          <th>Clube</th>
          <th>Pontos</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>1.º</td>
          <td>GOMES João</td>
          <td>Associação Desportiva do Centro Cultural da Quinta dos Lombos</td>
          <td>1.234,50</td>
        </tr>
        <tr>
          <td>2</td>
          <td>CONCEIÇÃO Ana 龍</td>
          <td>Clube de Esgrima de São Jorge</td>
          <td>987,25</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""


OPHARDT_TABLE_HTML = """
<table class="table table-striped table-sm rankingbody fixedheader">
  <thead>
    <tr>
      <th>Rank</th>
      <th>Pontos</th>
      <th>P-T</th>
      <th>Nome</th>
      <th>País</th>
      <th>Clubes</th>
      <th>Nasc</th>
    </tr>
  </thead>
  <tr>
    <td>3</td>
    <td>451,75</td>
    <td>0</td>
    <td>
      <div class="btn-group">
        <a class="dropdown-toggle" href="#">SANTOS Maria</a>
        <ul class="dropdown-menu"><li>Detalhes</li><li>Biografia</li></ul>
      </div>
    </td>
    <td>POR</td>
    <td>Academia de Esgrima João Gomes</td>
    <td>2006</td>
  </tr>
</table>
"""


SKIP_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Pos.</th><th>Nome</th><th>Clube</th><th>Pontos</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Atleta Ausente</td><td>Lisboa</td><td>0</td></tr>
    <tr><td>DQ</td><td>Atleta Desclassificado</td><td>Porto</td><td>0</td></tr>
    <tr><td>Total</td><td>Resumo</td><td></td><td>3.000</td></tr>
    <tr><td>abc</td><td>Linha inválida</td><td>Coimbra</td><td>1</td></tr>
    <tr><td>4</td><td>ÁVILA José</td><td>Clube de Esgrima do Porto</td><td>98,5</td></tr>
  </tbody>
</table>
"""


NO_TABLE_HTML = "<html><body><p>Nenhum ranking disponível.</p></body></html>"


INDEX_MATRIX_HTML = """
<table>
  <tr>
    <th></th>
    <th>Espada Feminina</th>
    <th>Florete Feminino</th>
    <th>Sabre Feminino</th>
    <th>Espada Masculina</th>
    <th>Florete Masculino</th>
    <th>Sabre Masculino</th>
  </tr>
  <tr>
    <td>Seniores</td>
    <td><a href="/pt/search/rankings/show/24001">Ranking Nacional</a></td>
    <td><a href="/pt/search/rankings/show/24002">Ranking Nacional</a></td>
    <td><a href="/pt/search/rankings/show/24003">Ranking Nacional</a></td>
    <td><a href="/pt/search/rankings/show/24004">Ranking Nacional</a></td>
    <td><a href="/pt/search/rankings/show/24005">Ranking Nacional</a></td>
    <td><a href="/pt/search/rankings/show/24006">Ranking Nacional</a></td>
  </tr>
  <tr>
    <td>Juniores U20</td>
    <td><a href="/pt/search/rankings/show/24007">Ranking Nacional</a></td>
    <td><a href="/pt/search/rankings/show/24008">Ranking Nacional</a></td>
    <td><a href="/pt/search/rankings/show/24009">Ranking Nacional</a></td>
    <td><a href="/pt/search/rankings/show/24010">Ranking Nacional</a></td>
    <td><a href="/pt/search/rankings/show/24011">Ranking Nacional</a></td>
    <td><a href="/pt/search/rankings/show/24012">Ranking Nacional</a></td>
  </tr>
</table>
"""


class DummyResponse:
    def __init__(self, status_code=200, text="", url="https://example.test/ranking"):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = {"content-type": "text/html; charset=utf-8"}


def test_parse_rankings_table_returns_valid_rows_with_portuguese_headers():
    from scrape_fed_por import parse_rankings_table

    rows = parse_rankings_table(PORTUGUESE_TABLE_HTML)

    assert rows[0] == {
        "rank": 1,
        "name": "GOMES João",
        "club": "Associação Desportiva do Centro Cultural da Quinta dos Lombos",
        "points": 1234.5,
    }
    assert rows[1]["name"] == "CONCEIÇÃO Ana 龍"
    assert rows[1]["club"] == "Clube de Esgrima de São Jorge"
    assert rows[1]["points"] == 987.25


def test_parse_rankings_table_handles_ophardt_rows_and_dropdown_details():
    from scrape_fed_por import parse_rankings_table

    rows = parse_rankings_table(OPHARDT_TABLE_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "SANTOS Maria",
            "club": "Academia de Esgrima João Gomes",
            "points": 451.75,
        }
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_por import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("   ") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_por import parse_rankings_table

    assert parse_rankings_table(NO_TABLE_HTML) == []


def test_parse_skips_dns_dq_summary_and_non_numeric_rank_rows():
    from scrape_fed_por import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {
            "rank": 4,
            "name": "ÁVILA José",
            "club": "Clube de Esgrima do Porto",
            "points": 98.5,
        }
    ]


def test_ranking_combos_cover_required_senior_and_junior_set():
    from scrape_fed_por import RANKING_COMBOS

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


def test_extract_ranking_links_maps_portuguese_public_matrix():
    from scrape_fed_por import _extract_ranking_links

    links = _extract_ranking_links(
        INDEX_MATRIX_HTML,
        base_url="https://fencing.ophardt.online/pt/search/rankings/44",
    )

    assert links[("Epee", "Women", "Senior")].endswith("/24001")
    assert links[("Foil", "Men", "Senior")].endswith("/24005")
    assert links[("Sabre", "Women", "Junior")].endswith("/24009")
    assert links[("Epee", "Men", "Junior")].endswith("/24010")
    assert len(links) == 12


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_por

    monkeypatch.setattr(
        scrape_fed_por,
        "_discover_ranking_links",
        lambda: {("Foil", "Men", "Senior"): "https://example.test/missing"},
    )
    monkeypatch.setattr(
        scrape_fed_por,
        "federation_request",
        lambda *args, **kwargs: DummyResponse(status_code=404, text="not found"),
    )

    assert scrape_fed_por.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_on_login_or_blocked_page(monkeypatch):
    import scrape_fed_por

    monkeypatch.setattr(
        scrape_fed_por,
        "_discover_ranking_links",
        lambda: {("Foil", "Women", "Senior"): "https://example.test/login"},
    )
    monkeypatch.setattr(
        scrape_fed_por,
        "federation_request",
        lambda *args, **kwargs: DummyResponse(
            status_code=200,
            text="<html><body><form><input type='password'></form>Iniciar sessão</body></html>",
        ),
    )

    assert scrape_fed_por.fetch_rankings_page("Foil", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_on_js_only_page(monkeypatch):
    import scrape_fed_por

    monkeypatch.setattr(
        scrape_fed_por,
        "_discover_ranking_links",
        lambda: {("Epee", "Men", "Senior"): "https://example.test/app"},
    )
    monkeypatch.setattr(
        scrape_fed_por,
        "federation_request",
        lambda *args, **kwargs: DummyResponse(
            status_code=200,
            text="<html><body><div id='root'></div><script src='/app.js'></script>Enable JavaScript</body></html>",
        ),
    )

    assert scrape_fed_por.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_missing_combo(monkeypatch):
    import scrape_fed_por

    monkeypatch.setattr(scrape_fed_por, "_discover_ranking_links", lambda: {})

    assert scrape_fed_por.fetch_rankings_page("Sabre", "Women", "Junior") is None

"""
Tests for scrape_fed_bra.py.

Probe evidence:
  - CBE ranking page: https://cbesgrima.org.br/ranking/
  - Public data target: https://fencing.ophardt.online/pt/search/rankings/163
  - Detail pages redirect from /pt/search/rankings/show/{id} to /pt/show-ranking/html/{id}
  - Ranking table class: table.rankingbody.fixedheader
  - Headers: Rank | Pontos | Pontos transferidos | Nome | País | Clubes | Nasc | ...
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


OPHARDT_FIXTURE_HTML = """
<!DOCTYPE html>
<html>
<body>
<h1>Brasil Esgrima Ranking: 2026</h1>
<table class="table table-striped table-sm rankingbody fixedheader">
  <thead class="thead-light">
    <tr>
      <th class="bg-light ranking">Rank</th>
      <th class="bg-light ranking">Pontos</th>
      <th class="bg-light ranking">Pontos transferidos</th>
      <th class="bg-light ranking">Nome</th>
      <th class="bg-light ranking">País</th>
      <th class="bg-light ranking">Clubes</th>
      <th class="bg-light ranking">Nasc</th>
    </tr>
  </thead>
  <tr>
    <td class="ranking">1</td>
    <td class="ranking">660</td>
    <td class="ranking">0</td>
    <td class="ranking">
      <div class="btn-group">
        <a class="dropdown-toggle" href="#" id="dLabel1">CAMARGO Alexandre</a>
        <ul class="dropdown-menu"><li>Detalhes</li><li>Biografia</li></ul>
      </div>
    </td>
    <td class="ranking">BRA ITA</td>
    <td class="ranking rankingclub">SP ECP Pinheiros, RM Roma Fencing</td>
    <td class="ranking">1999</td>
  </tr>
  <tr>
    <td class="ranking">4</td>
    <td class="ranking">347,2</td>
    <td class="ranking">0</td>
    <td class="ranking">
      <div class="btn-group">
        <a class="dropdown-toggle" href="#" id="dLabel4">BRANDT Matheus</a>
      </div>
    </td>
    <td class="ranking">BRA</td>
    <td class="ranking rankingclub">SP ECP Pinheiros</td>
    <td class="ranking">2007</td>
  </tr>
</table>
</body>
</html>
"""


PORTUGUESE_HEADER_HTML = """
<table>
  <thead>
    <tr><th>Posição</th><th>Nome</th><th>Clube</th><th>Pontos</th></tr>
  </thead>
  <tbody>
    <tr><td>1º</td><td>SILVA João</td><td>Associação São Jorge</td><td>1.234,50</td></tr>
    <tr><td>2</td><td>CONCEIÇÃO Ana 龍</td><td>Clube Paineiras</td><td>2.345,75</td></tr>
  </tbody>
</table>
"""


SKIP_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Pos.</th><th>Nome</th><th>Clube</th><th>Pontos</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Atleta Ausente</td><td>ABC</td><td>0</td></tr>
    <tr><td>DQ</td><td>Atleta Desclassificado</td><td>ABC</td><td>0</td></tr>
    <tr><td>Total</td><td>Resumo</td><td></td><td>3.000</td></tr>
    <tr><td>0</td><td>Linha Sem Ranking</td><td>ABC</td><td>0</td></tr>
    <tr><td>3</td><td>ÁVILA José</td><td>PR AMK Mestre Kato</td><td>98,5</td></tr>
  </tbody>
</table>
"""


NO_TABLE_HTML = """
<!DOCTYPE html>
<html><body><p>Nenhum ranking disponível.</p></body></html>
"""


INDEX_MATRIX_HTML = """
<table>
  <tr><th></th><th colspan="3">feminino</th><th colspan="3">masculino</th></tr>
  <tr><th></th><th>Espada</th><th>Florete</th><th>Sabre</th><th>Espada</th><th>Florete</th><th>Sabre</th></tr>
  <tr>
    <td>Senior</td>
    <td><a href="/pt/search/rankings/show/22355">Senior Individual</a></td>
    <td><a href="/pt/search/rankings/show/22357">Senior Individual</a></td>
    <td><a href="/pt/search/rankings/show/22359">Senior Individual</a></td>
    <td><a href="/pt/search/rankings/show/22356">Senior Individual</a></td>
    <td><a href="/pt/search/rankings/show/22358">Senior Individual</a></td>
    <td><a href="/pt/search/rankings/show/22360">Senior Individual</a></td>
  </tr>
  <tr>
    <td>U20</td>
    <td><a href="/pt/search/rankings/show/22343">U20 Individual</a></td>
    <td><a href="/pt/search/rankings/show/22345">U20 Individual</a></td>
    <td><a href="/pt/search/rankings/show/22347">U20 Individual</a></td>
    <td><a href="/pt/search/rankings/show/22344">U20 Individual</a></td>
    <td><a href="/pt/search/rankings/show/22346">U20 Individual</a></td>
    <td><a href="/pt/search/rankings/show/22348">U20 Individual</a></td>
  </tr>
</table>
"""


def test_parse_ophardt_rankingbody_returns_valid_rows():
    from scrape_fed_bra import parse_rankings_table

    rows = parse_rankings_table(OPHARDT_FIXTURE_HTML)

    assert len(rows) == 2
    assert rows[0] == {
        "rank": 1,
        "name": "CAMARGO Alexandre",
        "club": "SP ECP Pinheiros, RM Roma Fencing",
        "points": 660.0,
    }
    assert rows[1]["rank"] == 4
    assert rows[1]["name"] == "BRANDT Matheus"
    assert rows[1]["points"] == 347.2


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_bra import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_bra import parse_rankings_table

    assert parse_rankings_table(NO_TABLE_HTML) == []


def test_parse_skips_dns_dq_summary_and_zero_rank_rows():
    from scrape_fed_bra import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "ÁVILA José",
            "club": "PR AMK Mestre Kato",
            "points": 98.5,
        }
    ]


def test_parse_portuguese_headers_preserves_utf8_and_normalizes_points():
    from scrape_fed_bra import parse_rankings_table

    rows = parse_rankings_table(PORTUGUESE_HEADER_HTML)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "SILVA João"
    assert rows[0]["club"] == "Associação São Jorge"
    assert rows[0]["points"] == 1234.5
    assert rows[1]["name"] == "CONCEIÇÃO Ana 龍"
    assert rows[1]["points"] == 2345.75


def test_extract_ranking_links_maps_senior_and_u20_public_matrix():
    from scrape_fed_bra import _extract_ranking_links

    links = _extract_ranking_links(
        INDEX_MATRIX_HTML,
        base_url="https://fencing.ophardt.online/pt/search/rankings/163",
    )

    assert links[("Epee", "Women", "Senior")].endswith("/22355")
    assert links[("Foil", "Men", "Senior")].endswith("/22358")
    assert links[("Sabre", "Women", "Junior")].endswith("/22347")
    assert links[("Epee", "Men", "Junior")].endswith("/22344")
    assert len(links) == 12

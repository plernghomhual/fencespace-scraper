"""
Tests for scrape_fed_rsa.py.

Fixtures reflect the probed public South Africa ranking structure:
  - Federation page: https://safencer.co.za/rankings/
  - Request method: GET
  - Response format: server-rendered HTML
  - Public links: Senior/Junior Men/Women Foil/Epee/Sabre links to Ophardt pages
  - Detail table headers: Rank | Points | T-P | Name | Nation | Clubs | YOB
"""

import os
import sys
from typing import cast

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


OPHARDT_FIXTURE_HTML = """
<!doctype html>
<html>
<body>
  <h1>South Africa Ranking: 2026</h1>
  <table>
    <thead>
      <tr>
        <th>Rank</th><th>Points</th><th>T-P</th><th>Name</th><th>Nation</th><th>Clubs</th><th>YOB</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="ranking">1</td>
        <td class="ranking">655.5</td>
        <td class="ranking">0</td>
        <td class="ranking">
          <div class="btn-group">
            <a class="dropdown-toggle" href="#">MARAIS Caitlin</a>
            <ul class="dropdown-menu"><li>Details</li><li>Biography</li></ul>
          </div>
          <div class="modal">MARAIS Caitlin Rank Points Competition City Date</div>
        </td>
        <td class="ranking">RSA</td>
        <td class="ranking rankingclub">Cape Winelands Fencing Club</td>
        <td class="ranking">2001</td>
      </tr>
      <tr>
        <td class="ranking">2.</td>
        <td class="ranking">410,25</td>
        <td class="ranking">0</td>
        <td class="ranking"><a class="dropdown-toggle" href="#">VAN DER MERWE Thabo</a></td>
        <td class="ranking">RSA</td>
        <td class="ranking rankingclub">Tuks Fencing</td>
        <td class="ranking">2004</td>
      </tr>
    </tbody>
  </table>
</body>
</html>
"""


ENGLISH_HEADER_FIXTURE_HTML = """
<table>
  <thead>
    <tr><th>Position</th><th>Name</th><th>Club</th><th>Points</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>DLAMINI Nandi</td><td>Soweto Fencing</td><td>1,234.50</td></tr>
    <tr><td>2</td><td>王 Sipho</td><td>Durban Fencing Club</td><td>2.345,75</td></tr>
  </tbody>
</table>
"""


SKIP_ROWS_FIXTURE_HTML = """
<table>
  <thead>
    <tr><th>Rank</th><th>Name</th><th>Club</th><th>Points</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Absent Fencer</td><td>RSA Club</td><td>0</td></tr>
    <tr><td>DQ</td><td>Disqualified Fencer</td><td>RSA Club</td><td>0</td></tr>
    <tr><td>Total</td><td>Summary</td><td></td><td>1,000</td></tr>
    <tr><td>abc</td><td>Malformed Rank</td><td>RSA Club</td><td>12</td></tr>
    <tr><td>0</td><td>Zero Rank</td><td>RSA Club</td><td>12</td></tr>
    <tr><td>3</td><td>BOTHA Jaco</td><td>Gauteng Fencing</td><td>98,5</td></tr>
  </tbody>
</table>
"""


NO_DATA_HTML = """
<!doctype html>
<html><body><p>No rankings are currently available.</p></body></html>
"""


INDEX_HTML = """
<html>
<body>
  <h2>Senior Womens Epee</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30001">Check Rankings</a></p>
  <h2>Senior Mens Epee</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30002">Check Rankings</a></p>
  <h2>Senior Womens Foil</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30003">Check Rankings</a></p>
  <h2>Senior Mens Foil</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30004">Check Rankings</a></p>
  <h2>Senior Womens Sabre</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30005">Check Rankings</a></p>
  <h2>Senior Mens Sabre</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30006">Check Rankings</a></p>
  <h2>Junior Womens Epee</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30007">Check Rankings</a></p>
  <h2>Junior Mens Epee</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30008">Check Rankings</a></p>
  <h2>Junior Womens Foil</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30009">Check Rankings</a></p>
  <h2>Junior Mens Foil</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30010">Check Rankings</a></p>
  <h2>Junior Womens Sabre</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30011">Check Rankings</a></p>
  <h2>Junior Mens Sabre</h2><p><a href="https://fencing.ophardt.online/en/search/rankings/show/30012">Check Rankings</a></p>
</body>
</html>
"""


PARTIAL_INDEX_HTML = """
<html><body>
  <h2>Senior Womens Epee</h2><a href="/en/search/rankings/show/30001">Check Rankings</a>
</body></html>
"""


LOGIN_ONLY_HTML = """
<html><body><form><input name="login"></form><p>Please sign in to continue.</p></body></html>
"""


JS_ONLY_HTML = """
<html><body><noscript>Please enable JavaScript to view rankings.</noscript><div id="app"></div></body></html>
"""


class Response:
    def __init__(self, text="", status_code=200, url="https://safencer.co.za/rankings/"):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = {"content-type": "text/html; charset=UTF-8"}


def test_parse_ophardt_rankings_returns_valid_rows():
    from scrape_fed_rsa import parse_rankings_table

    rows = parse_rankings_table(OPHARDT_FIXTURE_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "MARAIS Caitlin",
            "club": "Cape Winelands Fencing Club",
            "points": 655.5,
        },
        {
            "rank": 2,
            "name": "VAN DER MERWE Thabo",
            "club": "Tuks Fencing",
            "points": 410.25,
        },
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_rsa import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_rsa import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_zero_rank_rows():
    from scrape_fed_rsa import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_FIXTURE_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "BOTHA Jaco",
            "club": "Gauteng Fencing",
            "points": 98.5,
        }
    ]


def test_parse_english_headers_decimal_variants_and_native_script_names():
    from scrape_fed_rsa import parse_rankings_table

    rows = parse_rankings_table(ENGLISH_HEADER_FIXTURE_HTML)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "DLAMINI Nandi"
    assert rows[0]["club"] == "Soweto Fencing"
    assert rows[0]["points"] == 1234.5
    assert rows[1]["name"] == "王 Sipho"
    assert rows[1]["points"] == 2345.75


def test_extract_ranking_links_maps_all_12_public_combos():
    from scrape_fed_rsa import _extract_ranking_links

    links = _extract_ranking_links(INDEX_HTML)

    assert links[("Epee", "Women", "Senior")].endswith("/30001")
    assert links[("Foil", "Men", "Senior")].endswith("/30004")
    assert links[("Sabre", "Women", "Junior")].endswith("/30011")
    assert links[("Epee", "Men", "Junior")].endswith("/30008")
    assert len(links) == 12


def test_fetch_rankings_page_uses_public_index_and_detail_page(monkeypatch):
    import scrape_fed_rsa

    scrape_fed_rsa._RANKING_LINK_CACHE.clear()
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url == scrape_fed_rsa.BASE_URL:
            return Response(INDEX_HTML, url=url)
        return Response(OPHARDT_FIXTURE_HTML, url=url)

    monkeypatch.setattr(scrape_fed_rsa, "federation_request", fake_request)

    html = scrape_fed_rsa.fetch_rankings_page("Foil", "Men", "Senior")

    html = cast(str, html)
    assert "MARAIS Caitlin" in html
    assert calls[0][0] == "get"
    assert calls[0][1] == "https://safencer.co.za/rankings/"
    assert calls[1][1].endswith("/30004")


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_rsa

    scrape_fed_rsa._RANKING_LINK_CACHE.clear()

    def fake_request(method, url, **kwargs):
        if url == scrape_fed_rsa.BASE_URL:
            return Response(INDEX_HTML, url=url)
        return Response("not found", status_code=404, url=url)

    monkeypatch.setattr(scrape_fed_rsa, "federation_request", fake_request)

    assert scrape_fed_rsa.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_for_network_error(monkeypatch):
    import scrape_fed_rsa

    scrape_fed_rsa._RANKING_LINK_CACHE.clear()

    def fake_request(method, url, **kwargs):
        raise requests.RequestException("connection failed")

    monkeypatch.setattr(scrape_fed_rsa, "federation_request", fake_request)

    assert scrape_fed_rsa.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_fetch_rankings_page_returns_none_for_login_only_index(monkeypatch):
    import scrape_fed_rsa

    scrape_fed_rsa._RANKING_LINK_CACHE.clear()

    def fake_request(method, url, **kwargs):
        return Response(LOGIN_ONLY_HTML, url=url)

    monkeypatch.setattr(scrape_fed_rsa, "federation_request", fake_request)

    assert scrape_fed_rsa.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_js_only_index(monkeypatch):
    import scrape_fed_rsa

    scrape_fed_rsa._RANKING_LINK_CACHE.clear()

    def fake_request(method, url, **kwargs):
        return Response(JS_ONLY_HTML, url=url)

    monkeypatch.setattr(scrape_fed_rsa, "federation_request", fake_request)

    assert scrape_fed_rsa.fetch_rankings_page("Foil", "Women", "Junior") is None


def test_fetch_rankings_page_returns_none_for_missing_combo(monkeypatch):
    import scrape_fed_rsa

    scrape_fed_rsa._RANKING_LINK_CACHE.clear()

    def fake_request(method, url, **kwargs):
        return Response(PARTIAL_INDEX_HTML, url=url)

    monkeypatch.setattr(scrape_fed_rsa, "federation_request", fake_request)

    assert scrape_fed_rsa.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_current_season_format():
    from scrape_fed_rsa import current_season

    season = current_season()

    assert len(season) == 9
    assert season[4] == "-"
    start, end = season.split("-")
    assert int(end) == int(start) + 1

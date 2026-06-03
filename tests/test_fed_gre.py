"""
Tests for scrape_fed_gre.py.

Probe evidence:
  - Federation domain requested by task: https://fencing.org.gr
  - Local shell DNS probe could not resolve external hosts in the sandbox; escalation was rejected.
  - Public Greece ranking references point to Ophardt index:
    https://fencing.ophardt.online/en/search/rankings/151
  - Request method: GET
  - Expected response format: server-rendered Ophardt HTML ranking matrix/detail tables.
  - Target combos: Senior and U20 (Junior) Foil/Epee/Sabre, Men/Women.
"""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


OPHARDT_FIXTURE_HTML = """
<!DOCTYPE html>
<html>
<body>
<h1>Greece Ranking: 2026</h1>
<table class="table table-striped table-sm rankingbody fixedheader">
  <thead class="thead-light">
    <tr>
      <th class="bg-light ranking">Rank</th>
      <th class="bg-light ranking">Points</th>
      <th class="bg-light ranking">Points transferred</th>
      <th class="bg-light ranking">Name</th>
      <th class="bg-light ranking">Country</th>
      <th class="bg-light ranking">Clubs</th>
      <th class="bg-light ranking">Born</th>
    </tr>
  </thead>
  <tr>
    <td class="ranking">1</td>
    <td class="ranking">152,5</td>
    <td class="ranking">0</td>
    <td class="ranking">
      <div class="btn-group">
        <a class="dropdown-toggle" href="#" id="dLabel1">ΚΟΥΡΟΥΣΗ Άννα-Καλλιόπη</a>
        <ul class="dropdown-menu"><li>Details</li><li>Biography</li></ul>
      </div>
    </td>
    <td class="ranking">GRE</td>
    <td class="ranking rankingclub">Α.Ο. ΑΠΟΛΛΩΝ ΒΡΙΛΗΣΣΙΩΝ</td>
    <td class="ranking">2008</td>
  </tr>
  <tr>
    <td class="ranking">2.</td>
    <td class="ranking">1.234,75</td>
    <td class="ranking">0</td>
    <td class="ranking">
      <div class="btn-group">
        <a class="dropdown-toggle" href="#" id="dLabel2">GEORGIADOU Despina</a>
      </div>
    </td>
    <td class="ranking">GRE</td>
    <td class="ranking rankingclub">Παναθηναϊκός Α.Ο.</td>
    <td class="ranking">1991</td>
  </tr>
</table>
</body>
</html>
"""


GREEK_HEADER_HTML = """
<table>
  <thead>
    <tr>
      <th>Θέση</th>
      <th>Ονοματεπώνυμο</th>
      <th>Σύλλογος</th>
      <th>Βαθμοί</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>1η</td><td>ΓΚΟΥΝΤΟΥΡΑ Δώρα</td><td>ΑΕΚ</td><td>208,000</td></tr>
    <tr><td>2</td><td>ΣΙΔΗΡΟΠΟΥΛΟΥ Νίκη-Κατερίνα</td><td>ΟΞΙΦ</td><td>12,5</td></tr>
  </tbody>
</table>
"""


SKIP_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Θέση</th><th>Όνομα</th><th>Σύλλογος</th><th>Βαθμοί</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Δεν Αγωνίστηκε</td><td>ΑΟΞ</td><td>0</td></tr>
    <tr><td>DQ</td><td>Αποκλεισμός</td><td>ΑΟΞ</td><td>0</td></tr>
    <tr><td>Σύνολο</td><td>Περίληψη</td><td></td><td>300</td></tr>
    <tr><td>abc</td><td>Μη αριθμητική θέση</td><td>ΑΟΞ</td><td>10</td></tr>
    <tr><td>0</td><td>Μηδενική θέση</td><td>ΑΟΞ</td><td>0</td></tr>
    <tr><td>3</td><td>ΠΑΥΛΙΔΟΥ Χαρά</td><td>ΟΞΙΦ</td><td>98,5</td></tr>
  </tbody>
</table>
"""


NO_TABLE_HTML = """
<!DOCTYPE html>
<html><body><p>Δεν υπάρχουν διαθέσιμες βαθμολογίες.</p></body></html>
"""


INDEX_MATRIX_HTML = """
<table>
  <tr><th></th><th colspan="3">female</th><th colspan="3">male</th></tr>
  <tr><th></th><th>Epee</th><th>Foil</th><th>Sabre</th><th>Epee</th><th>Foil</th><th>Sabre</th></tr>
  <tr>
    <td>Senior</td>
    <td><a href="/en/search/rankings/show/23001">Senior Individual</a></td>
    <td><a href="/en/search/rankings/show/23002">Senior Individual</a></td>
    <td><a href="/en/search/rankings/show/23003">Senior Individual</a></td>
    <td><a href="/en/search/rankings/show/23004">Senior Individual</a></td>
    <td><a href="/en/search/rankings/show/23005">Senior Individual</a></td>
    <td><a href="/en/search/rankings/show/23006">Senior Individual</a></td>
  </tr>
  <tr>
    <td>U20</td>
    <td><a href="/en/search/rankings/show/22991">U20 Individual</a></td>
    <td><a href="/en/search/rankings/show/22992">U20 Individual</a></td>
    <td><a href="/en/search/rankings/show/22993">U20 Individual</a></td>
    <td><a href="/en/search/rankings/show/22994">U20 Individual</a></td>
    <td><a href="/en/search/rankings/show/22995">U20 Individual</a></td>
    <td><a href="/en/search/rankings/show/22996">U20 Individual</a></td>
  </tr>
</table>
"""


def test_parse_ophardt_fixture_returns_valid_rows():
    from scrape_fed_gre import parse_rankings_table

    rows = parse_rankings_table(OPHARDT_FIXTURE_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "ΚΟΥΡΟΥΣΗ Άννα-Καλλιόπη",
            "club": "Α.Ο. ΑΠΟΛΛΩΝ ΒΡΙΛΗΣΣΙΩΝ",
            "points": 152.5,
        },
        {
            "rank": 2,
            "name": "GEORGIADOU Despina",
            "club": "Παναθηναϊκός Α.Ο.",
            "points": 1234.75,
        },
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_gre import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_gre import parse_rankings_table

    assert parse_rankings_table(NO_TABLE_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_zero_rank_rows():
    from scrape_fed_gre import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "ΠΑΥΛΙΔΟΥ Χαρά",
            "club": "ΟΞΙΦ",
            "points": 98.5,
        }
    ]


def test_parse_greek_headers_preserves_native_names_and_decimal_commas():
    from scrape_fed_gre import parse_rankings_table

    rows = parse_rankings_table(GREEK_HEADER_HTML)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "ΓΚΟΥΝΤΟΥΡΑ Δώρα"
    assert rows[0]["club"] == "ΑΕΚ"
    assert rows[0]["points"] == 208.0
    assert rows[1]["name"] == "ΣΙΔΗΡΟΠΟΥΛΟΥ Νίκη-Κατερίνα"
    assert rows[1]["points"] == 12.5


def test_ranking_combos_cover_all_required_greece_rankings():
    from scrape_fed_gre import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_extract_ranking_links_maps_senior_and_u20_public_matrix():
    from scrape_fed_gre import _extract_ranking_links

    links = _extract_ranking_links(
        INDEX_MATRIX_HTML,
        base_url="https://fencing.ophardt.online/en/search/rankings/151",
    )

    assert links[("Epee", "Women", "Senior")].endswith("/23001")
    assert links[("Foil", "Men", "Senior")].endswith("/23005")
    assert links[("Sabre", "Women", "Junior")].endswith("/22993")
    assert links[("Epee", "Men", "Junior")].endswith("/22994")
    assert len(links) == 12


def test_fetch_rankings_page_uses_discovered_public_link(monkeypatch):
    import scrape_fed_gre

    calls = []

    class FakeResponse:
        def __init__(self, status_code=200, text="", url="https://example.test/index"):
            self.status_code = status_code
            self.text = text
            self.url = url

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url == scrape_fed_gre.BASE_URL:
            return FakeResponse(text=INDEX_MATRIX_HTML, url=scrape_fed_gre.BASE_URL)
        if url.endswith("/23005"):
            return FakeResponse(text="<html>foil men senior</html>", url=url)
        return FakeResponse(status_code=404, text="missing", url=url)

    monkeypatch.setattr(scrape_fed_gre, "federation_request", fake_request)
    scrape_fed_gre._RANKING_LINK_CACHE.clear()

    content = scrape_fed_gre.fetch_rankings_page("Foil", "Men", "Senior")

    assert content == "<html>foil men senior</html>"
    assert calls[0][0] == "get"
    assert calls[0][1] == scrape_fed_gre.BASE_URL
    assert calls[1][1].endswith("/23005")


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_gre

    class FakeResponse:
        status_code = 404
        text = "missing"
        url = "https://example.test/missing"

    monkeypatch.setattr(scrape_fed_gre, "_discover_ranking_links", lambda season_year: {
        ("Epee", "Women", "Senior"): "https://example.test/missing"
    })
    monkeypatch.setattr(scrape_fed_gre, "federation_request", lambda *args, **kwargs: FakeResponse())

    assert scrape_fed_gre.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_on_network_error(monkeypatch):
    import scrape_fed_gre

    monkeypatch.setattr(scrape_fed_gre, "_discover_ranking_links", lambda season_year: {
        ("Epee", "Women", "Senior"): "https://example.test/blocked"
    })

    def raise_error(*args, **kwargs):
        raise requests.RequestException("blocked")

    monkeypatch.setattr(scrape_fed_gre, "federation_request", raise_error)

    assert scrape_fed_gre.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_for_login_only_or_blocked_index(monkeypatch):
    import scrape_fed_gre

    class FakeResponse:
        status_code = 401
        text = "<html>login required</html>"
        url = scrape_fed_gre.BASE_URL

    monkeypatch.setattr(scrape_fed_gre, "federation_request", lambda *args, **kwargs: FakeResponse())
    scrape_fed_gre._RANKING_LINK_CACHE.clear()

    assert scrape_fed_gre.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_fetch_rankings_page_returns_none_for_js_only_or_missing_combo(monkeypatch):
    import scrape_fed_gre

    class FakeResponse:
        status_code = 200
        text = "<div id='app'></div><script src='/rankings.js'></script>"
        url = scrape_fed_gre.BASE_URL

    monkeypatch.setattr(scrape_fed_gre, "federation_request", lambda *args, **kwargs: FakeResponse())
    scrape_fed_gre._RANKING_LINK_CACHE.clear()

    assert scrape_fed_gre.fetch_rankings_page("Foil", "Women", "Senior") is None


def test_main_attempts_all_12_combos_and_logs_failed_combos(monkeypatch):
    import scrape_fed_gre

    attempted = []
    states = {}
    completed = {}

    class FakeLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            return self

        def complete(self, **kwargs):
            completed.update(kwargs)

        def error(self, exc_str):
            raise AssertionError(exc_str)

    def fake_fetch(weapon, gender, category):
        attempted.append((weapon, gender, category))
        if category == "Senior":
            return OPHARDT_FIXTURE_HTML
        return None

    monkeypatch.setattr(scrape_fed_gre, "ScraperRunLogger", FakeLogger)
    monkeypatch.setattr(scrape_fed_gre, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_gre, "write_rankings", lambda rows, source, season: len(rows))
    monkeypatch.setattr(scrape_fed_gre, "set_state", lambda source, key, value: states.update({key: value}))
    monkeypatch.setattr(scrape_fed_gre.time, "sleep", lambda delay: None)

    scrape_fed_gre.main()

    assert attempted == scrape_fed_gre.RANKING_COMBOS
    assert completed["written"] == 12
    assert completed["failed"] == 6
    assert states["last_run"]["combos"] == 12
    assert len(states["last_run"]["failed_combos"]) == 6

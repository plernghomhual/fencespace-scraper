"""
Tests for scrape_fed_mar.py.

Probe evidence:
  - Target domain: https://frmescrime.ma
  - Request method attempted: GET
  - Response format expected if public: HTML ranking tables
  - 2026-06-02 sandbox probe: frmescrime.ma/www.frmescrime.ma did not resolve.
  - Escalated live probe was blocked by the approval usage gate, and search results did
    not expose a durable public ranking URL.

Fixtures are realistic French/Arabic ranking tables for the requested parser contract.
"""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FRENCH_RANKING_HTML = """
<!doctype html>
<html>
  <body>
    <table>
      <thead>
        <tr>
          <th>Classement</th>
          <th>Nom</th>
          <th>Club</th>
          <th>Points</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>1er</td>
          <td>EL FASSI Youssef</td>
          <td>Rabat Escrime Club</td>
          <td>1 234,50</td>
        </tr>
        <tr>
          <td>2</td>
          <td>BENJELLOUN Lina</td>
          <td>Académie d'Escrime de Casablanca</td>
          <td>987,25</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""


ARABIC_RANKING_HTML = """
<html lang="ar">
  <body>
    <table>
      <thead>
        <tr>
          <th>المركز</th>
          <th>الاسم</th>
          <th>النادي</th>
          <th>النقاط</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>1</td>
          <td>أمينة الإدريسي</td>
          <td>نادي الرباط للمبارزة</td>
          <td>45,75</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""


SKIP_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Rang</th><th>Nom</th><th>Club</th><th>Points</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Tireur absent</td><td>Rabat</td><td>0</td></tr>
    <tr><td>DQ</td><td>Tireur disqualifié</td><td>Casa</td><td>0</td></tr>
    <tr><td>Total</td><td>Résumé</td><td></td><td>3 000</td></tr>
    <tr><td>abc</td><td>Ligne invalide</td><td>Fès</td><td>1</td></tr>
    <tr><td>0</td><td>Rang zéro</td><td>Fès</td><td>0</td></tr>
    <tr><td>3</td><td>AIT MANSOUR Salma</td><td>Club d'Escrime de Fès</td><td>98,5</td></tr>
  </tbody>
</table>
"""


NO_DATA_HTML = """
<html>
  <body>
    <h1>Classements</h1>
    <p>Aucun classement public disponible.</p>
  </body>
</html>
"""


class DummyResponse:
    def __init__(self, status_code=200, text="", url="https://frmescrime.ma/classements"):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = {"content-type": "text/html; charset=utf-8"}


class DummyRunLogger:
    instances: list[object] = []

    def __init__(self, module):
        self.module = module
        self.completed = None
        self.errored = None
        DummyRunLogger.instances.append(self)

    def start(self):
        return self

    def complete(self, **kwargs):
        self.completed = kwargs

    def error(self, exc_str):
        self.errored = exc_str


def test_parse_rankings_table_returns_valid_rows_with_french_headers():
    from scrape_fed_mar import parse_rankings_table

    rows = parse_rankings_table(FRENCH_RANKING_HTML)

    assert rows[0] == {
        "rank": 1,
        "name": "EL FASSI Youssef",
        "club": "Rabat Escrime Club",
        "points": 1234.5,
    }
    assert rows[1]["name"] == "BENJELLOUN Lina"
    assert rows[1]["club"] == "Académie d'Escrime de Casablanca"
    assert rows[1]["points"] == 987.25


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_mar import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("   ") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_mar import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_zero_rank_rows():
    from scrape_fed_mar import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "AIT MANSOUR Salma",
            "club": "Club d'Escrime de Fès",
            "points": 98.5,
        }
    ]


def test_parse_arabic_headers_preserves_native_script_names():
    from scrape_fed_mar import parse_rankings_table

    rows = parse_rankings_table(ARABIC_RANKING_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "أمينة الإدريسي",
            "club": "نادي الرباط للمبارزة",
            "points": 45.75,
        }
    ]


def test_ranking_combos_cover_required_senior_and_junior_set():
    from scrape_fed_mar import RANKING_COMBOS

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


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_mar

    monkeypatch.setattr(
        scrape_fed_mar,
        "_discover_ranking_links",
        lambda: {("Foil", "Men", "Senior"): "https://frmescrime.ma/missing"},
    )
    monkeypatch.setattr(
        scrape_fed_mar,
        "federation_request",
        lambda *args, **kwargs: DummyResponse(status_code=404, text="not found"),
    )

    assert scrape_fed_mar.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_on_network_error(monkeypatch):
    import scrape_fed_mar

    monkeypatch.setattr(
        scrape_fed_mar,
        "_discover_ranking_links",
        lambda: {("Foil", "Women", "Senior"): "https://frmescrime.ma/error"},
    )

    def fake_request(*args, **kwargs):
        raise requests.RequestException("connection failed")

    monkeypatch.setattr(scrape_fed_mar, "federation_request", fake_request)

    assert scrape_fed_mar.fetch_rankings_page("Foil", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_on_login_or_blocked_page(monkeypatch):
    import scrape_fed_mar

    monkeypatch.setattr(
        scrape_fed_mar,
        "_discover_ranking_links",
        lambda: {("Epee", "Men", "Senior"): "https://frmescrime.ma/login"},
    )
    monkeypatch.setattr(
        scrape_fed_mar,
        "federation_request",
        lambda *args, **kwargs: DummyResponse(
            text="<html><body><form><input type='password'></form>Connexion requise</body></html>"
        ),
    )

    assert scrape_fed_mar.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_on_js_only_page(monkeypatch):
    import scrape_fed_mar

    monkeypatch.setattr(
        scrape_fed_mar,
        "_discover_ranking_links",
        lambda: {("Epee", "Women", "Senior"): "https://frmescrime.ma/app"},
    )
    monkeypatch.setattr(
        scrape_fed_mar,
        "federation_request",
        lambda *args, **kwargs: DummyResponse(
            text="<html><body><div id='app'></div><script src='/app.js'></script>Enable JavaScript</body></html>"
        ),
    )

    assert scrape_fed_mar.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_for_missing_combo(monkeypatch):
    import scrape_fed_mar

    monkeypatch.setattr(scrape_fed_mar, "_discover_ranking_links", lambda: {})

    assert scrape_fed_mar.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_main_attempts_all_12_combos_when_no_public_data(monkeypatch):
    import scrape_fed_mar

    attempted = []
    DummyRunLogger.instances.clear()

    def fake_fetch(weapon, gender, category):
        attempted.append((weapon, gender, category))
        return None

    monkeypatch.setattr(scrape_fed_mar, "ScraperRunLogger", DummyRunLogger)
    monkeypatch.setattr(scrape_fed_mar, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_mar, "set_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(scrape_fed_mar.time, "sleep", lambda *_args, **_kwargs: None)

    scrape_fed_mar.main()

    assert attempted == scrape_fed_mar.RANKING_COMBOS
    assert DummyRunLogger.instances[0].completed["written"] == 0
    assert DummyRunLogger.instances[0].completed["failed"] == 12
    assert DummyRunLogger.instances[0].completed["skipped"] == 0

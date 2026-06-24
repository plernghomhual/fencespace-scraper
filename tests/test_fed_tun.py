"""
Tests for scrape_fed_tun.py.

Probe evidence:
  - Requested host fte-tunisie.com did not resolve during probe.
  - Current public federation site: https://escrimetunisie.org/
  - Public data endpoint: GET /api/fie-athletes?weapon=<weapon>&gender=<M|F>&category=<category>
  - Response format: JSON list with FIE-ranked Tunisian athletes.
  - 10/12 Senior/Junior Foil/Epee/Sabre Men/Women filters currently return rows.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


LIVE_JSON_FIXTURE = """
[
  {
    "id": "7cc9c162-3b2a-46c3-a957-30634c00ae2f",
    "fieId": 32326,
    "name": "FERJANI Fares",
    "firstName": "Fares",
    "lastName": "FERJANI",
    "country": "TUN",
    "weapon": "sabre",
    "category": "senior",
    "gender": "M",
    "rank": 8,
    "points": "135.000"
  },
  {
    "id": "f7e8e82c-308e-4bb4-b5e5-a35f24d40d8d",
    "fieId": 59221,
    "name": "REZGUI Yesmine",
    "country": "TUN",
    "weapon": "sabre",
    "category": "senior",
    "gender": "F",
    "rank": 75,
    "points": "21.000"
  }
]
"""


FRENCH_TABLE_FIXTURE = """
<table>
  <thead>
    <tr><th>Classement</th><th>Nom</th><th>Club</th><th>Points</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>BOUBAKRI Inès</td><td>ASM Tunis</td><td>1.234,50</td></tr>
    <tr><td>2</td><td>FERJANI Ahmed</td><td>Association Sportive Militaire</td><td>39,750</td></tr>
  </tbody>
</table>
"""


ARABIC_TABLE_FIXTURE = """
<table>
  <thead>
    <tr><th>المركز</th><th>الاسم</th><th>النادي</th><th>النقاط</th></tr>
  </thead>
  <tbody>
    <tr><td>3</td><td>إيناس بوبكري</td><td>النادي الرياضي لتونس</td><td>12,5</td></tr>
  </tbody>
</table>
"""


SKIP_ROWS_FIXTURE = """
<table>
  <thead>
    <tr><th>Rang</th><th>Nom</th><th>Club</th><th>Points</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Absent</td><td>FTE</td><td>0</td></tr>
    <tr><td>DQ</td><td>Disqualifié</td><td>FTE</td><td>0</td></tr>
    <tr><td>Total</td><td>2 tireurs</td><td></td><td>123</td></tr>
    <tr><td>-</td><td>Malformed</td><td>FTE</td><td>9</td></tr>
    <tr><td>0</td><td>Zero Rank</td><td>FTE</td><td>0</td></tr>
    <tr><td>4</td><td>BEN YAHMED Farah</td><td>Club de Monastir</td><td>12.000</td></tr>
  </tbody>
</table>
"""


NO_DATA_HTML = """
<!doctype html>
<html><body><p>Aucun classement disponible pour cette catégorie.</p></body></html>
"""


def test_parse_live_json_fixture_returns_valid_rows():
    from scrape_fed_tun import parse_rankings_table

    rows = parse_rankings_table(LIVE_JSON_FIXTURE)

    assert rows[0] == {
        "rank": 8,
        "name": "FERJANI Fares",
        "club": None,
        "points": 135.0,
    }
    assert rows[1]["name"] == "REZGUI Yesmine"
    assert rows[1]["points"] == 21.0


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_tun import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("[]") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_tun import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_zero_rank_rows():
    from scrape_fed_tun import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_FIXTURE)

    assert rows == [
        {
            "rank": 4,
            "name": "BEN YAHMED Farah",
            "club": "Club de Monastir",
            "points": 12.0,
        }
    ]


def test_parse_french_headers_preserves_accents_and_decimal_commas():
    from scrape_fed_tun import parse_rankings_table

    rows = parse_rankings_table(FRENCH_TABLE_FIXTURE)

    assert rows[0]["name"] == "BOUBAKRI Inès"
    assert rows[0]["club"] == "ASM Tunis"
    assert rows[0]["points"] == 1234.5
    assert rows[1]["points"] == 39.75


def test_parse_arabic_headers_preserves_native_script_names():
    from scrape_fed_tun import parse_rankings_table

    rows = parse_rankings_table(ARABIC_TABLE_FIXTURE)

    assert rows == [
        {
            "rank": 3,
            "name": "إيناس بوبكري",
            "club": "النادي الرياضي لتونس",
            "points": 12.5,
        }
    ]


def test_fetch_rankings_page_builds_public_api_request(monkeypatch):
    import scrape_fed_tun

    calls = []

    class Response:
        status_code = 200
        text = LIVE_JSON_FIXTURE
        headers = {"content-type": "application/json; charset=utf-8"}
        url = "https://escrimetunisie.org/api/fie-athletes?weapon=sabre&gender=M&category=senior"

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(scrape_fed_tun.requests, "get", fake_get)

    content = scrape_fed_tun.fetch_rankings_page("Sabre", "Men", "Senior")

    assert content == LIVE_JSON_FIXTURE
    assert calls[0][0] == (
        "https://escrimetunisie.org/api/fie-athletes?weapon=sabre&gender=M&category=senior"
    )
    assert calls[0][1]["headers"] == scrape_fed_tun.HEADERS


def test_fetch_rankings_page_returns_none_for_404_network_block_login_and_js(monkeypatch):
    import requests

    import scrape_fed_tun

    class Response:
        def __init__(self, status_code=200, text="", headers=None):
            self.status_code = status_code
            self.text = text
            self.headers = headers or {"content-type": "application/json; charset=utf-8"}
            self.url = "https://escrimetunisie.org/api/fie-athletes"

    cases = [
        Response(status_code=404, text='{"message":"not found"}'),
        Response(status_code=401, text='{"message":"Unauthorized"}'),
        Response(
            status_code=200,
            text='<!doctype html><div id="root"></div><script src="/assets/index.js"></script>',
            headers={"content-type": "text/html; charset=UTF-8"},
        ),
        requests.ConnectionError("blocked"),
    ]

    def fake_get(url, **kwargs):
        result = cases.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(scrape_fed_tun.requests, "get", fake_get)

    assert scrape_fed_tun.fetch_rankings_page("Foil", "Women", "Senior") is None
    assert scrape_fed_tun.fetch_rankings_page("Foil", "Women", "Senior") is None
    assert scrape_fed_tun.fetch_rankings_page("Foil", "Women", "Senior") is None
    assert scrape_fed_tun.fetch_rankings_page("Foil", "Women", "Senior") is None


def test_fetch_rankings_page_keeps_empty_public_combo_as_parseable_content(monkeypatch):
    import scrape_fed_tun

    class Response:
        status_code = 200
        text = "[]"
        headers = {"content-type": "application/json; charset=utf-8"}
        url = "https://escrimetunisie.org/api/fie-athletes?weapon=epee&gender=F&category=junior"

    monkeypatch.setattr(scrape_fed_tun.requests, "get", lambda *args, **kwargs: Response())

    content = scrape_fed_tun.fetch_rankings_page("Epee", "Women", "Junior")

    assert content == "[]"
    assert scrape_fed_tun.parse_rankings_table(content) == []


def test_current_season_returns_current_fencing_range():
    import scrape_fed_tun

    assert scrape_fed_tun.current_season() == "2025-2026"


def test_main_attempts_all_12_combos_and_counts_empty_combos_as_skipped(monkeypatch):
    import scrape_fed_tun

    fetched = []
    written_rows = []
    completed = []

    class FakeRun:
        def start(self):
            return self

        def complete(self, written=0, failed=0, skipped=0):
            completed.append((written, failed, skipped))

        def error(self, message):
            raise AssertionError(message)

    def fake_fetch(weapon, gender, category):
        fetched.append((weapon, gender, category))
        if (weapon, gender, category) in {
            ("Foil", "Women", "Senior"),
            ("Epee", "Women", "Junior"),
        }:
            return "[]"
        return LIVE_JSON_FIXTURE

    def fake_write(rows, source, season):
        written_rows.extend(rows)
        return len(rows)

    monkeypatch.setattr(scrape_fed_tun, "ScraperRunLogger", lambda name: FakeRun())
    monkeypatch.setattr(scrape_fed_tun, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_tun, "write_rankings", fake_write)
    monkeypatch.setattr(scrape_fed_tun, "REQUEST_DELAY", 0)
    monkeypatch.setattr(scrape_fed_tun.time, "sleep", lambda seconds: None)

    scrape_fed_tun.main()

    assert fetched == scrape_fed_tun.RANKING_COMBOS
    assert len(fetched) == 12
    assert completed == [(20, 0, 2)]
    assert all(row["source"] == "tun_fencing" for row in written_rows)
    assert all(row["country"] == "Tunisia" for row in written_rows)

"""
Tests for scrape_fed_jam.py.

Probe evidence:
  - Requested probe domain `jamaicafencing.com` was not retrievable through
    available web tooling in this session.
  - Commonwealth Fencing Federation lists the official site as
    https://jamaicanfencing.org/.
  - https://jamaicanfencing.org/ is public HTML, but exposes only a
    contact/landing page and no public rankings/results table.

Fixtures use the required Jamaica ranking column shape:
  Rank | Name | Club | Points
"""

import os
import sys
from datetime import UTC, datetime, timezone

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


REALISTIC_RANKING_HTML = """
<!DOCTYPE html>
<html>
<body>
  <table class="rankings">
    <thead>
      <tr><th>Rank</th><th>Name</th><th>Club</th><th>Points</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>MITCHELL-ROWE Decordoba</td><td>Kingston Fencing Club</td><td>1,25</td></tr>
      <tr><td>2.</td><td>CHANG Caitlin 張</td><td>Jamaican Fencing</td><td>367</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


NO_DATA_HTML = """
<!DOCTYPE html>
<html>
<body>
  <main>
    <h1>Fencing for Everyone!</h1>
    <p>No rankings available.</p>
  </main>
</body>
</html>
"""


SKIP_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Rank</th><th>Name</th><th>Club</th><th>Points</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Did Not Start</td><td>Kingston</td><td>0</td></tr>
    <tr><td>DQ</td><td>Disqualified Fencer</td><td>Kingston</td><td>0</td></tr>
    <tr><td>Total</td><td>Summary Row</td><td></td><td>400</td></tr>
    <tr><td>Rank</td><td>Name</td><td>Club</td><td>Points</td></tr>
    <tr><td>abc</td><td>Malformed Rank</td><td>Kingston</td><td>25</td></tr>
    <tr><td>3</td><td>MARTIN Shea</td><td>Mona Fencing</td><td>98,5</td></tr>
  </tbody>
</table>
"""


LANGUAGE_HEADER_HTML = """
<table>
  <thead>
    <tr><th>Ranking</th><th>Fencer</th><th>Team</th><th>Pts</th></tr>
  </thead>
  <tbody>
    <tr><td>1st</td><td>PATTERSON Luis Enrique 李</td><td>Kingston Fencing Club</td><td>1,234.50</td></tr>
    <tr><td>2</td><td>ÁLVAREZ Marí José</td><td>UWI Mona</td><td>2.345,75</td></tr>
  </tbody>
</table>
"""


class FakeResponse:
    def __init__(self, *, status_code=200, text="", url="https://example.test/rankings"):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = {"content-type": "text/html; charset=UTF-8"}


def test_parse_rankings_table_returns_valid_rows():
    from scrape_fed_jam import parse_rankings_table

    rows = parse_rankings_table(REALISTIC_RANKING_HTML)

    assert len(rows) == 2
    assert rows[0] == {
        "rank": 1,
        "name": "MITCHELL-ROWE Decordoba",
        "club": "Kingston Fencing Club",
        "points": 1.25,
    }
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "CHANG Caitlin 張"
    assert rows[1]["points"] == 367.0


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_jam import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_jam import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_non_numeric_rank_rows():
    from scrape_fed_jam import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "MARTIN Shea",
            "club": "Mona Fencing",
            "points": 98.5,
        }
    ]


def test_parse_language_specific_headers_and_native_names_are_preserved():
    from scrape_fed_jam import parse_rankings_table

    rows = parse_rankings_table(LANGUAGE_HEADER_HTML)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "PATTERSON Luis Enrique 李"
    assert rows[0]["club"] == "Kingston Fencing Club"
    assert rows[0]["points"] == 1234.5
    assert rows[1]["name"] == "ÁLVAREZ Marí José"
    assert rows[1]["points"] == 2345.75


def test_ranking_combos_cover_all_required_jamaica_rankings():
    from scrape_fed_jam import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_jam

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse(status_code=404, text="missing", url=url)

    monkeypatch.setattr(scrape_fed_jam, "federation_request", fake_request)

    assert scrape_fed_jam.fetch_rankings_page("Foil", "Men", "Senior") is None
    assert calls[0][0] == "get"
    assert calls[0][1].endswith("/rankings/senior-men-foil/")


def test_fetch_rankings_page_returns_none_on_network_error(monkeypatch):
    import scrape_fed_jam

    def fake_request(method, url, **kwargs):
        raise requests.RequestException("dns failed")

    monkeypatch.setattr(scrape_fed_jam, "federation_request", fake_request)

    assert scrape_fed_jam.fetch_rankings_page("Epee", "Women", "Junior") is None


@pytest.mark.parametrize(
    "html",
    [
        "<html><body><form><input type='password'></form>Login required</body></html>",
        "<html><body><div id='root'></div><script src='/app.js'></script>This page requires JavaScript</body></html>",
        NO_DATA_HTML,
    ],
)
def test_fetch_rankings_page_returns_none_for_blocked_login_js_or_no_data_pages(monkeypatch, html):
    import scrape_fed_jam

    def fake_request(method, url, **kwargs):
        return FakeResponse(text=html, url=url)

    monkeypatch.setattr(scrape_fed_jam, "federation_request", fake_request)

    assert scrape_fed_jam.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_fetch_rankings_page_returns_html_when_rankings_table_is_present(monkeypatch):
    import scrape_fed_jam

    def fake_request(method, url, **kwargs):
        return FakeResponse(text=REALISTIC_RANKING_HTML, url=url)

    monkeypatch.setattr(scrape_fed_jam, "federation_request", fake_request)

    assert scrape_fed_jam.fetch_rankings_page("Foil", "Women", "Senior") == REALISTIC_RANKING_HTML


def test_main_attempts_all_12_combos_and_records_stub_summary(monkeypatch, capsys):
    import scrape_fed_jam

    attempted = []
    complete_calls = []
    state_calls = []

    class FakeLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            return self

        def complete(self, **kwargs):
            complete_calls.append(kwargs)

        def error(self, exc_str):
            raise AssertionError(f"unexpected error log: {exc_str}")

    def fake_fetch(weapon, gender, category):
        attempted.append((weapon, gender, category))
        return None

    monkeypatch.setattr(scrape_fed_jam, "ScraperRunLogger", FakeLogger)
    monkeypatch.setattr(scrape_fed_jam, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_jam, "write_rankings", lambda *args, **kwargs: 0)
    monkeypatch.setattr(scrape_fed_jam, "set_state", lambda source, key, value: state_calls.append((source, key, value)))
    monkeypatch.setattr(scrape_fed_jam.time, "sleep", lambda seconds: None)

    scrape_fed_jam.main()

    output = capsys.readouterr().out
    assert len(attempted) == 12
    assert attempted == scrape_fed_jam.RANKING_COMBOS
    assert "No scrapeable rankings at" in output
    assert complete_calls[0]["written"] == 0
    assert complete_calls[0]["failed"] == 12
    assert complete_calls[0]["skipped"] == 0
    assert state_calls[0][0] == scrape_fed_jam.SOURCE
    assert state_calls[0][1] == "last_run"
    summary = state_calls[0][2]
    assert summary["combos"] == 12
    assert summary["public_combos"] == []
    assert len(summary["failed_combos"]) == 12


def test_current_season_uses_yyyy_range_before_july(monkeypatch):
    import scrape_fed_jam

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 1, tzinfo=tz or UTC)

    monkeypatch.setattr(scrape_fed_jam, "datetime", FixedDateTime)

    assert scrape_fed_jam.current_season() == "2025-2026"

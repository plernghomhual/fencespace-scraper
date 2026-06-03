"""
Tests for scrape_fed_isl.py.

Fixtures are realistic for the probed Icelandic source shape. No durable public
national ranking page was found on the public Iceland federation/club pages, so
parser fixtures use the expected Icelandic table headers:
Sæti | Nafn | Félag | Stig.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ICELANDIC_TABLE_FIXTURE = """
<!doctype html>
<html lang="is">
<body>
  <table>
    <thead>
      <tr><th>Sæti</th><th>Nafn</th><th>Félag</th><th>Stig</th></tr>
    </thead>
    <tbody>
      <tr>
        <td>1.</td>
        <td>Þórunn Ævarsdóttir</td>
        <td>Skylmingafélag Reykjavíkur</td>
        <td>245,5</td>
      </tr>
      <tr>
        <td>2</td>
        <td>Daði Örn Guðmundsson</td>
        <td>SFR</td>
        <td>1.200,25</td>
      </tr>
    </tbody>
  </table>
</body>
</html>
"""


NATIVE_SCRIPT_FIXTURE = """
<html>
<body>
  <table>
    <tr><th>Saeti</th><th>Nafn</th><th>Felag</th><th>Stig</th></tr>
    <tr><td>1</td><td>Мария Þórsdóttir</td><td>Skylmingafélag Reykjavíkur</td><td>10</td></tr>
  </table>
</body>
</html>
"""


NO_TABLE_FIXTURE = """
<html>
<body>
  <h1>Skylmingasamband Íslands</h1>
  <p>Enginn opinber stigalisti er birtur á þessari síðu.</p>
</body>
</html>
"""


SKIPPED_ROWS_FIXTURE = """
<html>
<body>
  <table>
    <thead>
      <tr><th>Sæti</th><th>Nafn</th><th>Félag</th><th>Stig</th></tr>
    </thead>
    <tbody>
      <tr><td>DNS</td><td>Did Not Start</td><td>SFR</td><td>0</td></tr>
      <tr><td>DQ</td><td>Disqualified</td><td>SFR</td><td>0</td></tr>
      <tr><td>Samtals</td><td>3 keppendur</td><td></td><td>100</td></tr>
      <tr><td>abc</td><td>Malformed Rank</td><td>SFR</td><td>12</td></tr>
      <tr><td>4</td><td></td><td>SFR</td><td>12</td></tr>
      <tr><td>5</td><td>Malformed Points</td><td>SFR</td><td>ekki stig</td></tr>
      <tr><td>6</td><td>Björgvin Þór Einarsson</td><td>SFR</td><td>12,75</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


PIPE_TEXT_FIXTURE = """
Sæti | Nafn | Félag | Stig
1 | Karitas Jónsdóttir | Skylmingafélag Reykjavíkur | 42,25
DNS | Sleppa Keppanda | SFR | 0
"""


class Response:
    def __init__(self, status_code=200, text="<html>ranking</html>"):
        self.status_code = status_code
        self.text = text


def test_parse_icelandic_rankings_returns_rows():
    from scrape_fed_isl import parse_rankings_table

    rows = parse_rankings_table(ICELANDIC_TABLE_FIXTURE)

    assert len(rows) == 2
    assert rows[0] == {
        "rank": 1,
        "name": "Þórunn Ævarsdóttir",
        "club": "Skylmingafélag Reykjavíkur",
        "points": 245.5,
    }
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "Daði Örn Guðmundsson"
    assert rows[1]["points"] == 1200.25


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_isl import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("   ") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_isl import parse_rankings_table

    assert parse_rankings_table(NO_TABLE_FIXTURE) == []


def test_parse_skips_dns_dq_summary_malformed_and_nonnumeric_rows():
    from scrape_fed_isl import parse_rankings_table

    rows = parse_rankings_table(SKIPPED_ROWS_FIXTURE)

    assert rows == [
        {
            "rank": 6,
            "name": "Björgvin Þór Einarsson",
            "club": "SFR",
            "points": 12.75,
        }
    ]


def test_parse_language_specific_headers_and_native_script_names_are_preserved():
    from scrape_fed_isl import parse_rankings_table

    rows = parse_rankings_table(NATIVE_SCRIPT_FIXTURE)

    assert rows == [
        {
            "rank": 1,
            "name": "Мария Þórsdóttir",
            "club": "Skylmingafélag Reykjavíkur",
            "points": 10.0,
        }
    ]


def test_parse_plain_text_pipe_table():
    from scrape_fed_isl import parse_rankings_table

    rows = parse_rankings_table(PIPE_TEXT_FIXTURE)

    assert rows == [
        {
            "rank": 1,
            "name": "Karitas Jónsdóttir",
            "club": "Skylmingafélag Reykjavíkur",
            "points": 42.25,
        }
    ]


def test_fetch_rankings_page_returns_none_for_missing_public_combo(capsys):
    from scrape_fed_isl import fetch_rankings_page

    assert fetch_rankings_page("Foil", "Men", "Senior") is None
    assert "No scrapeable rankings" in capsys.readouterr().out


def test_fetch_rankings_page_returns_content_for_configured_public_url(monkeypatch):
    import scrape_fed_isl

    calls = []
    url = "https://www.fencing.is/stigalisti/senior-mens-epee"
    monkeypatch.setitem(
        scrape_fed_isl.RANKING_URLS,
        ("Epee", "Men", "Senior"),
        url,
    )

    def fake_request(method, request_url, **kwargs):
        calls.append((method, request_url, kwargs))
        return Response(200, ICELANDIC_TABLE_FIXTURE)

    monkeypatch.setattr(scrape_fed_isl, "federation_request", fake_request)

    content = scrape_fed_isl.fetch_rankings_page("Epee", "Men", "Senior")

    assert content == ICELANDIC_TABLE_FIXTURE
    assert calls[0][0] == "get"
    assert calls[0][1] == url
    assert calls[0][2]["headers"] == scrape_fed_isl.HEADERS


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_isl

    monkeypatch.setitem(
        scrape_fed_isl.RANKING_URLS,
        ("Sabre", "Women", "Junior"),
        "https://www.fencing.is/missing",
    )
    monkeypatch.setattr(
        scrape_fed_isl,
        "federation_request",
        lambda *args, **kwargs: Response(404, ""),
    )

    assert scrape_fed_isl.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_fetch_rankings_page_returns_none_for_network_error(monkeypatch):
    import scrape_fed_isl

    monkeypatch.setitem(
        scrape_fed_isl.RANKING_URLS,
        ("Foil", "Women", "Senior"),
        "https://www.fencing.is/stigalisti",
    )

    def fail_request(*args, **kwargs):
        raise scrape_fed_isl.requests.RequestException("timeout")

    monkeypatch.setattr(scrape_fed_isl, "federation_request", fail_request)

    assert scrape_fed_isl.fetch_rankings_page("Foil", "Women", "Senior") is None


@pytest.mark.parametrize(
    "body",
    [
        "<html><body>Access denied by Cloudflare captcha</body></html>",
        "<html><body><form>Login required - skrá inn</form></body></html>",
        "<html><body><noscript>Please enable JavaScript</noscript><div id='root'></div></body></html>",
    ],
)
def test_fetch_rankings_page_returns_none_for_blocked_login_or_js_only(monkeypatch, body):
    import scrape_fed_isl

    monkeypatch.setitem(
        scrape_fed_isl.RANKING_URLS,
        ("Epee", "Women", "Junior"),
        "https://www.fencing.is/stigalisti",
    )
    monkeypatch.setattr(
        scrape_fed_isl,
        "federation_request",
        lambda *args, **kwargs: Response(200, body),
    )

    assert scrape_fed_isl.fetch_rankings_page("Epee", "Women", "Junior") is None


def test_main_attempts_all_twelve_combos_and_logs_stub_state(monkeypatch):
    import scrape_fed_isl

    attempted = []
    completions = []
    states = []

    class FakeLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            return self

        def complete(self, **kwargs):
            completions.append(kwargs)

        def error(self, exc_str):
            raise AssertionError(exc_str)

    def fake_fetch(weapon, gender, category):
        attempted.append((weapon, gender, category))
        return None

    monkeypatch.setattr(scrape_fed_isl, "ScraperRunLogger", FakeLogger)
    monkeypatch.setattr(scrape_fed_isl, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_isl, "write_rankings", lambda *args, **kwargs: 0)
    monkeypatch.setattr(scrape_fed_isl, "get_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(scrape_fed_isl, "set_state", lambda source, key, value: states.append((source, key, value)))
    monkeypatch.setattr(scrape_fed_isl.time, "sleep", lambda _: None)

    scrape_fed_isl.main()

    assert attempted == scrape_fed_isl.RANKING_COMBOS
    assert completions[0]["written"] == 0
    assert completions[0]["failed"] == 0
    assert completions[0]["skipped"] == 12
    assert completions[0]["metadata"]["combos_working"] == 0
    assert states[0][0] == scrape_fed_isl.SOURCE
    assert states[0][1] == "last_run"

import pytest
import requests

FIXTURE_PUBLIC_HTML = """
<html>
<body>
  <table class="rankings">
    <thead>
      <tr><th>Rank</th><th>Name</th><th>Club</th><th>Points</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>Elena Żammit</td><td>Malta Fencing Club</td><td>125.5</td></tr>
      <tr><td>2</td><td>Marco Borg</td><td>Sliema Fencing</td><td>84,25</td></tr>
    </tbody>
  </table>
</body>
</html>
"""

FIXTURE_NATIVE_NAMES = """
<table>
  <tr><th>Position</th><th>Fencer</th><th>Organisation</th><th>Total Points</th></tr>
  <tr><td>1.</td><td>Мария Camilleri</td><td>Valletta Swords</td><td>1,234.50</td></tr>
  <tr><td>2</td><td>李 Borg</td><td></td><td>42,75</td></tr>
</table>
"""

FIXTURE_NO_DATA = """
<html>
  <body>
    <h1>Rankings</h1>
    <p>No rankings available for this selection.</p>
  </body>
</html>
"""

FIXTURE_NON_STANDARD_ROWS = """
<table>
  <tr><th>Rank</th><th>Name</th><th>Club</th><th>Points</th></tr>
  <tr><td>DNS</td><td>Did Not Start</td><td>MFC</td><td>0</td></tr>
  <tr><td>DQ</td><td>Disqualified Fencer</td><td>MFC</td><td>0</td></tr>
  <tr><td>Total</td><td>2 fencers</td><td></td><td>100</td></tr>
  <tr><td>not ranked</td><td>Malformed Fencer</td><td></td><td>5</td></tr>
  <tr><td>4</td><td>Missing Points</td></tr>
  <tr><td>3</td><td>Lara Vella</td><td>University of Malta</td><td>12,5</td></tr>
</table>
"""


def test_parse_mlt_public_fixture_returns_rank_name_club_points():
    from scrape_fed_mlt import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_PUBLIC_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "Elena Żammit",
            "club": "Malta Fencing Club",
            "points": 125.5,
        },
        {
            "rank": 2,
            "name": "Marco Borg",
            "club": "Sliema Fencing",
            "points": 84.25,
        },
    ]


def test_parse_mlt_empty_html_returns_empty_list():
    from scrape_fed_mlt import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_mlt_no_table_no_data_page_returns_empty_list():
    from scrape_fed_mlt import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_mlt_skips_dns_dq_summary_and_non_numeric_rows():
    from scrape_fed_mlt import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert rows == [
        {
            "rank": 3,
            "name": "Lara Vella",
            "club": "University of Malta",
            "points": 12.5,
        }
    ]


def test_parse_mlt_preserves_language_headers_and_native_script_names():
    from scrape_fed_mlt import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NATIVE_NAMES)

    assert rows[0]["name"] == "Мария Camilleri"
    assert rows[0]["club"] == "Valletta Swords"
    assert rows[0]["points"] == 1234.5
    assert rows[1]["name"] == "李 Borg"
    assert rows[1]["club"] is None
    assert rows[1]["points"] == 42.75


def test_ranking_combos_cover_all_required_malta_rankings():
    from scrape_fed_mlt import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_mlt_stub_returns_none_without_public_combo_url(capsys):
    from scrape_fed_mlt import fetch_rankings_page

    assert fetch_rankings_page("Foil", "Men", "Senior") is None
    assert "No scrapeable rankings at https://maltasrim.com" in capsys.readouterr().out


def test_fetch_mlt_returns_none_on_404(monkeypatch):
    import scrape_fed_mlt

    class FakeResponse:
        status_code = 404
        text = "missing"

    monkeypatch.setitem(
        scrape_fed_mlt.PUBLIC_RANKING_URLS,
        ("Foil", "Men", "Senior"),
        "https://example.test/rankings",
    )
    monkeypatch.setattr(scrape_fed_mlt, "federation_request", lambda *args, **kwargs: FakeResponse())

    assert scrape_fed_mlt.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_mlt_returns_none_on_network_error(monkeypatch):
    import scrape_fed_mlt

    def raise_timeout(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setitem(
        scrape_fed_mlt.PUBLIC_RANKING_URLS,
        ("Foil", "Men", "Senior"),
        "https://example.test/rankings",
    )
    monkeypatch.setattr(scrape_fed_mlt, "federation_request", raise_timeout)

    assert scrape_fed_mlt.fetch_rankings_page("Foil", "Men", "Senior") is None


@pytest.mark.parametrize(
    "body",
    [
        "<html><body><h1>Access denied</h1></body></html>",
        "<html><body><form action='/login'><input type='password'></form></body></html>",
        "<html><body><noscript>Please enable JavaScript to continue.</noscript></body></html>",
    ],
)
def test_fetch_mlt_returns_none_for_blocked_login_or_js_only_pages(monkeypatch, body):
    import scrape_fed_mlt

    class FakeResponse:
        status_code = 200
        text = body

    monkeypatch.setitem(
        scrape_fed_mlt.PUBLIC_RANKING_URLS,
        ("Foil", "Men", "Senior"),
        "https://example.test/rankings",
    )
    monkeypatch.setattr(scrape_fed_mlt, "federation_request", lambda *args, **kwargs: FakeResponse())

    assert scrape_fed_mlt.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_mlt_returns_content_for_accessible_public_table(monkeypatch):
    import scrape_fed_mlt

    class FakeResponse:
        status_code = 200
        text = FIXTURE_PUBLIC_HTML

    monkeypatch.setitem(
        scrape_fed_mlt.PUBLIC_RANKING_URLS,
        ("Foil", "Men", "Senior"),
        "https://example.test/rankings",
    )
    monkeypatch.setattr(scrape_fed_mlt, "federation_request", lambda *args, **kwargs: FakeResponse())

    assert scrape_fed_mlt.fetch_rankings_page("Foil", "Men", "Senior") == FIXTURE_PUBLIC_HTML


def test_main_attempts_all_12_combos_and_exits_zero(monkeypatch):
    import scrape_fed_mlt

    calls = []
    completed = {}

    class FakeRunLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            return self

        def complete(self, **kwargs):
            completed.update(kwargs)

        def error(self, exc_str):
            raise AssertionError(exc_str)

    def fake_fetch(weapon, gender, category):
        calls.append((weapon, gender, category))
        return None

    monkeypatch.setattr(scrape_fed_mlt, "ScraperRunLogger", FakeRunLogger)
    monkeypatch.setattr(scrape_fed_mlt, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_mlt, "get_state", lambda source, key: None)
    monkeypatch.setattr(scrape_fed_mlt, "set_state", lambda source, key, value: None)
    monkeypatch.setattr(scrape_fed_mlt.time, "sleep", lambda delay: None)

    scrape_fed_mlt.main()

    assert calls == scrape_fed_mlt.RANKING_COMBOS
    assert completed["written"] == 0
    assert completed["failed"] == 12
    assert completed["skipped"] == 0

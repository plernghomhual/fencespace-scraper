"""
Tests for scrape_fed_lva.py.

Probe evidence:
  - Prompt host `pauksmes.lv` has no search presence; official source is https://paukosana.lv/.
  - Public source page: GET https://paukosana.lv/sacensibu-rezultati/ returns WordPress HTML.
  - The page lists official competition-result Google Drive folders, not national ranking tables.
  - WordPress API searches for "ranking" and "reitings" returned empty arrays.
  - https://paukosana.tv/results/LCH2021/index.htm returns FencingTime competition results,
    including Senior/Junior event pages, but not federation season rankings.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


LATVIAN_RANKING_HTML = """
<html>
<body>
  <h1>Latvijas Paukošanas federācijas reitings</h1>
  <table>
    <thead>
      <tr><th>Vieta</th><th>Vārds / Uzvārds</th><th>Klubs</th><th>Punkti</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>KAIRĀNE Marija</td><td>ASMENS / RĪGA</td><td>1 234,50</td></tr>
      <tr><td>2.</td><td>ČAIKOVSKIS Gļebs</td><td>DAUGAVPILS BJSS</td><td>87,25</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


NO_DATA_HTML = """
<html>
<body>
  <h2>LPF oficiālo sacensību rezultāti</h2>
  <p>2025 - 2026. gada sezona <a href="https://drive.google.com/drive/folders/example">folder</a></p>
</body>
</html>
"""


SKIP_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Vieta</th><th>Vārds</th><th>Klubs</th><th>Punkti</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Neieradās</td><td>ASMENS</td><td>0</td></tr>
    <tr><td>DQ</td><td>Diskvalificēts</td><td>RIDZENE</td><td>0</td></tr>
    <tr><td>Kopā</td><td>3 sportisti</td><td></td><td>100</td></tr>
    <tr><td>4</td><td>Trūkst šūnu</td></tr>
    <tr><td>nav</td><td>Neskaitāma rinda</td><td>RĪGA</td><td>10</td></tr>
    <tr><td>0</td><td>Nulles vieta</td><td>RĪGA</td><td>10</td></tr>
    <tr><td>3</td><td>PROŠINA Sofija</td><td>ASMENS / RĪGA</td><td>45,5</td></tr>
  </tbody>
</table>
"""


FENCINGTIME_FINAL_RESULTS_HTML = """
<html>
<body>
  <h2>Latvijas Čempionāts 2021</h2>
  <h3>Junior Women's Foil</h3>
  <h2>Final Results</h2>
  <table>
    <tr><th>Place</th><th>Name</th><th>Club(s)</th><th>Country</th></tr>
    <tr><td>1</td><td>MASLOBOJEVA Emīlija</td><td>RIDZENE / STOPINI</td><td>LAT</td></tr>
    <tr><td>3T</td><td>ŠEMAROVA Juliana</td><td>FLORETE / RIGA</td><td>LAT</td></tr>
  </table>
</body>
</html>
"""


class FakeResponse:
    def __init__(self, status_code=200, text="", url="https://paukosana.lv/sacensibu-rezultati/"):
        self.status_code = status_code
        self.text = text
        self.url = url


def test_parse_latvian_rankings_returns_valid_rows_with_points():
    from scrape_fed_lva import parse_rankings_table

    rows = parse_rankings_table(LATVIAN_RANKING_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "KAIRĀNE Marija",
            "club": "ASMENS / RĪGA",
            "points": 1234.5,
        },
        {
            "rank": 2,
            "name": "ČAIKOVSKIS Gļebs",
            "club": "DAUGAVPILS BJSS",
            "points": 87.25,
        },
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_lva import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_lva import parse_rankings_table

    assert parse_rankings_table("<html><body>Nav datu</body></html>") == []
    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_non_numeric_and_zero_rank_rows():
    from scrape_fed_lva import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "PROŠINA Sofija",
            "club": "ASMENS / RĪGA",
            "points": 45.5,
        }
    ]


def test_parse_preserves_native_script_names_from_fencingtime_fixture_without_points():
    from scrape_fed_lva import parse_rankings_table

    rows = parse_rankings_table(FENCINGTIME_FINAL_RESULTS_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "MASLOBOJEVA Emīlija",
            "club": "RIDZENE / STOPINI",
            "points": None,
        },
        {
            "rank": 3,
            "name": "ŠEMAROVA Juliana",
            "club": "FLORETE / RIGA",
            "points": None,
        },
    ]


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_lva

    monkeypatch.setattr(
        scrape_fed_lva,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(status_code=404, text="Not found"),
    )

    assert scrape_fed_lva.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_blocked_page(monkeypatch):
    import scrape_fed_lva

    monkeypatch.setattr(
        scrape_fed_lva,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(status_code=403, text="Forbidden"),
    )

    assert scrape_fed_lva.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_for_login_only_page(monkeypatch):
    import scrape_fed_lva

    monkeypatch.setattr(
        scrape_fed_lva,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(text="<form><input type='password'></form>"),
    )

    assert scrape_fed_lva.fetch_rankings_page("Sabre", "Men", "Junior") is None


def test_fetch_rankings_page_returns_none_for_js_only_no_data_page(monkeypatch):
    import scrape_fed_lva

    js_only = "<html><body><noscript>Please enable JavaScript</noscript><div id='drive_main_page'></div></body></html>"
    monkeypatch.setattr(
        scrape_fed_lva,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(text=js_only),
    )

    assert scrape_fed_lva.fetch_rankings_page("Foil", "Women", "Junior") is None


def test_fetch_rankings_page_returns_content_for_parseable_table(monkeypatch):
    import scrape_fed_lva

    monkeypatch.setattr(
        scrape_fed_lva,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(text=LATVIAN_RANKING_HTML),
    )

    assert scrape_fed_lva.fetch_rankings_page("Epee", "Men", "Senior") == LATVIAN_RANKING_HTML


def test_fetch_rankings_page_returns_none_for_unsupported_combo_without_request(monkeypatch):
    import scrape_fed_lva

    calls = []

    def fake_request(*args, **kwargs):
        calls.append(args)
        return FakeResponse(text=LATVIAN_RANKING_HTML)

    monkeypatch.setattr(scrape_fed_lva, "federation_request", fake_request)

    assert scrape_fed_lva.fetch_rankings_page("Foil", "Mixed", "Senior") is None
    assert calls == []


def test_main_attempts_all_12_combos_and_logs_stub_metadata(monkeypatch):
    import scrape_fed_lva

    attempted = []
    complete_calls = []

    class DummyLogger:
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

    monkeypatch.setattr(scrape_fed_lva, "ScraperRunLogger", DummyLogger)
    monkeypatch.setattr(scrape_fed_lva, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_lva.time, "sleep", lambda _seconds: None)

    scrape_fed_lva.main()

    assert attempted == scrape_fed_lva.RANKING_COMBOS
    assert complete_calls == [
        {
            "written": 0,
            "failed": 0,
            "skipped": 12,
            "metadata": {
                "season": scrape_fed_lva.current_season(),
                "combos_total": 12,
                "combos_working": 0,
                "working_combos": [],
                "failed_combos": [],
                "skipped_combos": [
                    f"{weapon} {gender} {category}"
                    for weapon, gender, category in scrape_fed_lva.RANKING_COMBOS
                ],
                "probed_urls": scrape_fed_lva.PROBED_URLS,
            },
        }
    ]

"""
Tests for scrape_fed_kaz.py.

Probe evidence:
  - Requested probe host `https://fencing.kz/` currently serves an unrelated
    Karaganda meat shop. Ranking/result/API paths return 404.
  - Official references point to `kazfencing.kz` / `kazfencing.com`.
    `https://kazfencing.com/` redirects to `https://kazfencing.kz/`.
  - `https://kazfencing.kz/` is public HTML for the National Fencing Federation
    of Kazakhstan, but sampled result/search pages expose prose/images only:
    no ranking tables, no public PDF/XLS/CSV ranking files, WP API 404, uploads
    directory listings 403.
  - Public Senior/Junior Foil/Epee/Sabre Men/Women ranking combos found: 0/12.

Fixtures use realistic Kazakh/Russian national ranking table headers:
  Орын / Место | Аты-жөні / ФИО | Клуб | Ұпай / Очки
"""

import os
import sys
from datetime import datetime, timezone

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


KAZAKH_TABLE_HTML = """
<!doctype html>
<html lang="kk">
<body>
  <table class="rankings">
    <thead>
      <tr><th>Орын</th><th>Аты-жөні</th><th>Клуб</th><th>Ұпай</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>САРЫБАЙ Айгерім</td><td>Алматы</td><td>1 234,50</td></tr>
      <tr><td>2.</td><td>ҚҰРБАНОВ Руслан</td><td>Астана</td><td>987.25</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


RUSSIAN_NATIVE_NAMES_HTML = """
<table>
  <tr><th>Место</th><th>ФИО</th><th>Клуб</th><th>Очки</th></tr>
  <tr><td>1 место</td><td>ДОСПАЙ Карина</td><td>Шымкент</td><td>2.345,75</td></tr>
  <tr><td>2</td><td>ӘБЖАЛ Бексұлтан</td><td></td><td>42,5</td></tr>
</table>
"""


NO_DATA_HTML = """
<html>
  <body>
    <h1>Рейтинг</h1>
    <p>Рейтинг спортсменов не опубликован.</p>
  </body>
</html>
"""


SKIP_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Место</th><th>ФИО</th><th>Клуб</th><th>Очки</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Не стартовал</td><td>Алматы</td><td>0</td></tr>
    <tr><td>DQ</td><td>Дисквалифицирован</td><td>Астана</td><td>0</td></tr>
    <tr><td>Итог</td><td>Сводная строка</td><td></td><td>300</td></tr>
    <tr><td>abc</td><td>Неверный ранг</td><td>Караганда</td><td>25</td></tr>
    <tr><td>0</td><td>Нулевой ранг</td><td>Караганда</td><td>25</td></tr>
    <tr><td>3</td><td>БАЙТАСОВ Тимур</td><td>Қарағанды</td><td>12,5</td></tr>
  </tbody>
</table>
"""


PIPE_TEXT_FIXTURE = """
Орын | Аты-жөні | Клуб | Ұпай
1 | ЛУКИН Богдан | Алматы | 88,25
DQ | Skip Fencer | Астана | 0
"""


class FakeResponse:
    def __init__(self, *, status_code=200, text="", url="https://example.test/rankings"):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = {"content-type": "text/html; charset=UTF-8"}


def test_parse_kazakh_table_returns_rank_name_club_points():
    from scrape_fed_kaz import parse_rankings_table

    rows = parse_rankings_table(KAZAKH_TABLE_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "САРЫБАЙ Айгерім",
            "club": "Алматы",
            "points": 1234.5,
        },
        {
            "rank": 2,
            "name": "ҚҰРБАНОВ Руслан",
            "club": "Астана",
            "points": 987.25,
        },
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_kaz import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("   ") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_kaz import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_non_numeric_rows():
    from scrape_fed_kaz import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "БАЙТАСОВ Тимур",
            "club": "Қарағанды",
            "points": 12.5,
        }
    ]


def test_parse_language_specific_headers_and_native_script_names_are_preserved():
    from scrape_fed_kaz import parse_rankings_table

    rows = parse_rankings_table(RUSSIAN_NATIVE_NAMES_HTML)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "ДОСПАЙ Карина"
    assert rows[0]["club"] == "Шымкент"
    assert rows[0]["points"] == 2345.75
    assert rows[1]["name"] == "ӘБЖАЛ Бексұлтан"
    assert rows[1]["club"] is None
    assert rows[1]["points"] == 42.5


def test_parse_plain_text_pipe_table():
    from scrape_fed_kaz import parse_rankings_table

    rows = parse_rankings_table(PIPE_TEXT_FIXTURE)

    assert rows == [
        {
            "rank": 1,
            "name": "ЛУКИН Богдан",
            "club": "Алматы",
            "points": 88.25,
        }
    ]


def test_ranking_combos_cover_all_required_kazakhstan_rankings():
    from scrape_fed_kaz import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_returns_none_for_missing_public_combo(capsys):
    from scrape_fed_kaz import fetch_rankings_page

    assert fetch_rankings_page("Foil", "Men", "Senior") is None
    assert "No scrapeable rankings at https://kazfencing.kz" in capsys.readouterr().out


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_kaz

    monkeypatch.setitem(
        scrape_fed_kaz.PUBLIC_RANKING_URLS,
        ("Foil", "Men", "Senior"),
        "https://example.test/rankings",
    )
    monkeypatch.setattr(
        scrape_fed_kaz,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(status_code=404, text="missing"),
    )

    assert scrape_fed_kaz.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_blocked_status(monkeypatch):
    import scrape_fed_kaz

    monkeypatch.setitem(
        scrape_fed_kaz.PUBLIC_RANKING_URLS,
        ("Epee", "Women", "Senior"),
        "https://example.test/blocked",
    )
    monkeypatch.setattr(
        scrape_fed_kaz,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(status_code=403, text="forbidden"),
    )

    assert scrape_fed_kaz.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_on_network_error(monkeypatch):
    import scrape_fed_kaz

    def fake_request(*args, **kwargs):
        raise requests.RequestException("geoblocked")

    monkeypatch.setitem(
        scrape_fed_kaz.PUBLIC_RANKING_URLS,
        ("Sabre", "Men", "Junior"),
        "https://example.test/rankings",
    )
    monkeypatch.setattr(scrape_fed_kaz, "federation_request", fake_request)

    assert scrape_fed_kaz.fetch_rankings_page("Sabre", "Men", "Junior") is None


@pytest.mark.parametrize(
    "html",
    [
        "<html><body><form action='/login'><input type='password'></form>Login required</body></html>",
        "<html><body>Access denied by security service</body></html>",
        "<html><body><noscript>Please enable JavaScript</noscript><div id='root'></div></body></html>",
    ],
)
def test_fetch_rankings_page_returns_none_for_login_blocked_or_js_only_pages(monkeypatch, html):
    import scrape_fed_kaz

    monkeypatch.setitem(
        scrape_fed_kaz.PUBLIC_RANKING_URLS,
        ("Foil", "Women", "Junior"),
        "https://example.test/login",
    )
    monkeypatch.setattr(
        scrape_fed_kaz,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(text=html),
    )

    assert scrape_fed_kaz.fetch_rankings_page("Foil", "Women", "Junior") is None


def test_fetch_rankings_page_returns_html_when_public_table_is_available(monkeypatch):
    import scrape_fed_kaz

    monkeypatch.setitem(
        scrape_fed_kaz.PUBLIC_RANKING_URLS,
        ("Epee", "Men", "Senior"),
        "https://example.test/rankings",
    )
    monkeypatch.setattr(
        scrape_fed_kaz,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(text=KAZAKH_TABLE_HTML),
    )

    assert scrape_fed_kaz.fetch_rankings_page("Epee", "Men", "Senior") == KAZAKH_TABLE_HTML


def test_main_attempts_all_12_combos_and_records_stub_summary(monkeypatch, capsys):
    import scrape_fed_kaz

    attempts = []
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
            raise AssertionError(f"unexpected error log: {exc_str}")

    def fake_fetch(weapon, gender, category):
        attempts.append((weapon, gender, category))
        return None

    monkeypatch.setattr(scrape_fed_kaz, "ScraperRunLogger", FakeLogger)
    monkeypatch.setattr(scrape_fed_kaz, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_kaz, "write_rankings", lambda *args, **kwargs: 0)
    monkeypatch.setattr(scrape_fed_kaz, "get_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(scrape_fed_kaz, "set_state", lambda source, key, value: states.append((source, key, value)))
    monkeypatch.setattr(scrape_fed_kaz.time, "sleep", lambda seconds: None)

    scrape_fed_kaz.main()

    output = capsys.readouterr().out
    assert attempts == scrape_fed_kaz.RANKING_COMBOS
    assert "No scrapeable rankings at" in output
    assert completions[0]["written"] == 0
    assert completions[0]["failed"] == 12
    assert completions[0]["skipped"] == 0
    assert states[0][0] == scrape_fed_kaz.SOURCE
    assert states[0][1] == "last_run"
    summary = states[0][2]
    assert summary["combos"] == 12
    assert summary["public_combos"] == []
    assert summary["data_format"] == "stub"
    assert len(summary["failed_combos"]) == 12


def test_current_season_uses_yyyy_range_before_july(monkeypatch):
    import scrape_fed_kaz

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 1, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(scrape_fed_kaz, "datetime", FixedDateTime)

    assert scrape_fed_kaz.current_season() == "2025-2026"

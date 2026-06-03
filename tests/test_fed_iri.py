"""
Tests for scrape_fed_iri.py.

Fixtures mirror the public Iranian federation services ranking table shape:
  https://irfnc-services.ir/Athletes/Ranking/rankshow/Foil-Female-C-I

Observed columns include:
  رده بندی | نام | استان | iffnumber | تاریخ تولد | event columns | جمع امتیاز

The scraper maps استان/باشگاه to the stored club field and preserves
Persian names exactly as published.
"""

import os
import re
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_IRI_HTML = """
<!doctype html>
<html lang="fa" dir="rtl">
<body>
  <table class="table table-striped">
    <thead>
      <tr>
        <th>رده بندی</th>
        <th>نام</th>
        <th>استان</th>
        <th>iffnumber</th>
        <th>تاریخ تولد</th>
        <th>قهرمان کشوری نوجوانان بانوان فلوره ۱۴۰۳/۶/۲۱</th>
        <th>جمع امتیاز</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>۱</td>
        <td>آیلین باقری</td>
        <td>تهران</td>
        <td>IF1208036</td>
        <td>۱۳۸۸/۰۵/۲۳</td>
        <td>۱</td>
        <td>۳۲,۵</td>
      </tr>
      <tr>
        <td>۲</td>
        <td>حنانه سادات حسینی</td>
        <td>اصفهان</td>
        <td>IF1208040</td>
        <td>۱۳۸۷/۰۷/۱۲</td>
        <td>۲</td>
        <td>۲۴</td>
      </tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_BASHGAH_HEADERS = """
<html lang="fa" dir="rtl">
<body>
  <table>
    <tr>
      <th>رتبه</th>
      <th>نام</th>
      <th>باشگاه</th>
      <th>امتیاز</th>
    </tr>
    <tr>
      <td>۳</td>
      <td>زهرا کیانی</td>
      <td>باشگاه استقلال</td>
      <td>۱٬۲۳۴٫۷۵</td>
    </tr>
  </table>
</body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
<html lang="fa" dir="rtl">
<body>
  <table>
    <tr><th>رتبه</th><th>نام</th><th>باشگاه</th><th>امتیاز</th></tr>
    <tr><td>DNS</td><td>بازیکن غایب</td><td>تهران</td><td>۰</td></tr>
    <tr><td>DQ</td><td>بازیکن حذف شده</td><td>اصفهان</td><td>۰</td></tr>
    <tr><td>جمع امتیاز</td><td>خلاصه جدول</td><td></td><td>۵۶</td></tr>
    <tr><td>الف</td><td>ردیف خراب</td><td>قم</td><td>۱۲</td></tr>
    <tr><td>۰</td><td>ردیف بدون رتبه</td><td>شیراز</td><td>۱۲</td></tr>
    <tr><td>۴</td><td>ریحانه جعفری</td><td>یزد</td><td>۱۲,۵</td></tr>
  </table>
</body>
</html>
"""


FIXTURE_NO_TABLE = """
<!doctype html>
<html lang="fa" dir="rtl">
<body>
  <h1>رده بندی</h1>
  <p>اطلاعاتی برای نمایش وجود ندارد.</p>
</body>
</html>
"""


class FakeResponse:
    def __init__(self, status_code=200, text=FIXTURE_IRI_HTML, url=None):
        self.status_code = status_code
        self.text = text
        self.url = url or "https://www.iranfencing.org/Athletes/Ranking/rankshow/Foil-Male-S-I"


def test_parse_iri_rankings_returns_rows_from_farsi_table():
    from scrape_fed_iri import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_IRI_HTML)

    assert len(rows) == 2
    assert rows[0] == {
        "rank": 1,
        "name": "آیلین باقری",
        "club": "تهران",
        "points": 32.5,
    }
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "حنانه سادات حسینی"
    assert rows[1]["points"] == 24.0


def test_parse_iri_language_headers_and_native_script_names_are_preserved():
    from scrape_fed_iri import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_BASHGAH_HEADERS)

    assert rows == [
        {
            "rank": 3,
            "name": "زهرا کیانی",
            "club": "باشگاه استقلال",
            "points": 1234.75,
        }
    ]


def test_parse_iri_empty_html_returns_empty_list():
    from scrape_fed_iri import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_iri_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_iri import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_TABLE) == []


def test_parse_iri_skips_dns_dq_summary_and_malformed_rows():
    from scrape_fed_iri import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 1
    assert rows[0]["rank"] == 4
    assert rows[0]["name"] == "ریحانه جعفری"
    assert rows[0]["points"] == 12.5


def test_iri_ranking_combos_cover_required_senior_and_junior_rankings():
    from scrape_fed_iri import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12
    assert ("Foil", "Men", "Senior") in RANKING_COMBOS
    assert ("Sabre", "Women", "Junior") in RANKING_COMBOS


def test_iri_build_rankings_url_uses_public_services_rankshow_pattern():
    from scrape_fed_iri import build_rankings_url

    assert build_rankings_url("Foil", "Men", "Senior").endswith("/Foil-Male-S-I")
    assert build_rankings_url("Epee", "Women", "Junior").endswith("/Epee-Female-J-I")
    assert build_rankings_url("Sabre", "Women", "Senior").startswith(
        "https://www.iranfencing.org/Athletes/Ranking/rankshow/"
    )


def test_iri_current_season_format():
    from scrape_fed_iri import current_season

    season = current_season()
    assert re.match(r"^\d{4}-\d{4}$", season)
    start, end = season.split("-")
    assert int(end) == int(start) + 1


def test_fetch_rankings_page_returns_public_html(monkeypatch):
    import scrape_fed_iri as iri

    requested = []

    def fake_get(url, **kwargs):
        requested.append((url, kwargs))
        return FakeResponse(text=FIXTURE_IRI_HTML, url=url)

    monkeypatch.setattr(iri.requests, "get", fake_get)

    content = iri.fetch_rankings_page("Epee", "Women", "Junior")

    assert content == FIXTURE_IRI_HTML
    assert requested[0][0].endswith("/Epee-Female-J-I")
    assert requested[0][1]["headers"]["User-Agent"].startswith("Mozilla/")
    assert requested[0][1]["timeout"] == 15


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_iri as iri

    monkeypatch.setattr(
        iri.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(status_code=404, text="Not found"),
    )

    assert iri.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_network_error(monkeypatch):
    import scrape_fed_iri as iri

    def fake_get(*args, **kwargs):
        raise requests.RequestException("blocked")

    monkeypatch.setattr(iri.requests, "get", fake_get)

    assert iri.fetch_rankings_page("Foil", "Women", "Senior") is None


@pytest.mark.parametrize(
    "page_text",
    [
        "<html><body><h1>Access Denied</h1><p>Forbidden</p></body></html>",
        "<html><body><form><input name='password'></form><p>ورود به سامانه</p></body></html>",
        "<html><body><noscript>Please enable JavaScript to view this page.</noscript></body></html>",
    ],
)
def test_fetch_rankings_page_returns_none_for_blocked_login_or_js_only_pages(
    monkeypatch, page_text
):
    import scrape_fed_iri as iri

    monkeypatch.setattr(
        iri.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(text=page_text),
    )

    assert iri.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_main_attempts_all_combos_and_logs_missing_combos(monkeypatch):
    import scrape_fed_iri as iri

    attempted = []
    completed = {}

    class FakeLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            return self

        def complete(self, **kwargs):
            completed.update(kwargs)

        def error(self, exc):
            raise AssertionError(f"unexpected error log: {exc}")

    def fake_fetch(weapon, gender, category):
        attempted.append((weapon, gender, category))
        return None

    monkeypatch.setattr(iri, "ScraperRunLogger", FakeLogger)
    monkeypatch.setattr(iri, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(iri, "write_rankings", lambda rows, source, season: len(rows))
    monkeypatch.setattr(iri.time, "sleep", lambda delay: None)

    iri.main()

    assert attempted == iri.RANKING_COMBOS
    assert completed["written"] == 0
    assert completed["failed"] == 12
    assert completed["skipped"] == 0
    assert len(completed["metadata"]["failed_combos"]) == 12

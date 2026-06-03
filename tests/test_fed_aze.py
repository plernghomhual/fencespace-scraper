"""
Tests for scrape_fed_aze.py.

Probe evidence:
  - Prompt URL azfencing.az did not resolve from the local sandbox.
  - Current public federation site is https://fencing.az.
  - Ranking pages are server-rendered HTML via GET:
      https://fencing.az/az/spaqa-reytinq/
      https://fencing.az/az/sablya-reytinq/
  - Public ranking page headings include Şpaqa/Sablya Senior, U20/gənc
    Men/Women sections. No public Foil ranking page was found.
  - Captured row shape:
      № Soyad,ad Təvəllüd Cəmi xallar
      1 Quliyeva Aynur 2007 28.5
"""

import os
import re
import sys
from datetime import datetime, timezone

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


AZE_EPEE_FIXTURE_HTML = """
<html>
<body>
  <h1>Şpaqa Reytinq</h1>
  <h2>Şpaqa qadınlar</h2>
  <p>№Soyad,ad Təvəllüd Cəmi xallar</p>
  <p>1 Quliyeva Aynur 2007 28.5</p>
  <p>2 Mehdiyeva Nəzrin 2008 26,2</p>
  <h2>Şpaqa kişilər</h2>
  <p>№Soyad,ad Təvəllüd Cəmi xallar</p>
  <p>1 Misirzadə Oruc 2009 25.8</p>
</body>
</html>
"""


AZE_AZ_HEADERS_TABLE = """
<table>
  <thead>
    <tr><th>Yer</th><th>Ad</th><th>Klub</th><th>Xal</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>ƏLİYEV Rəşad Иван</td><td>Bakı Qılıncoynatma Klubu</td><td>1 234,5</td></tr>
    <tr><td>2.</td><td>Həsənli Xədicə</td><td>Gəncə</td><td>48</td></tr>
  </tbody>
</table>
"""


SKIPPED_ROWS_TABLE = """
<table>
  <thead>
    <tr><th>№</th><th>Soyad,ad</th><th>Təvəllüd</th><th>Cəmi xallar</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Gəlmədi İdmançı</td><td>2007</td><td>0</td></tr>
    <tr><td>DQ</td><td>Diskvalifikasiya</td><td>2006</td><td>0</td></tr>
    <tr><td>Cəmi</td><td>3 idmançı</td><td></td><td>100</td></tr>
    <tr><td>A</td><td>Malformed Rank</td><td>2005</td><td>10</td></tr>
    <tr><td>3</td><td>Əlizadə Üzeyir</td><td>2009</td><td>19,6</td></tr>
  </tbody>
</table>
"""


NO_TABLE_HTML = """
<html><body><p>Reytinq məlumatı tapılmadı.</p></body></html>
"""


def test_parse_probed_azerbaijan_text_rows_returns_valid_rows():
    from scrape_fed_aze import parse_rankings_table

    rows = parse_rankings_table(AZE_EPEE_FIXTURE_HTML)

    assert rows[:3] == [
        {"rank": 1, "name": "Quliyeva Aynur", "club": None, "points": 28.5},
        {"rank": 2, "name": "Mehdiyeva Nəzrin", "club": None, "points": 26.2},
        {"rank": 1, "name": "Misirzadə Oruc", "club": None, "points": 25.8},
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_aze import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_aze import parse_rankings_table

    assert parse_rankings_table(NO_TABLE_HTML) == []


def test_parse_skips_dns_dq_summary_and_malformed_rows():
    from scrape_fed_aze import parse_rankings_table

    rows = parse_rankings_table(SKIPPED_ROWS_TABLE)

    assert rows == [
        {"rank": 3, "name": "Əlizadə Üzeyir", "club": None, "points": 19.6}
    ]


def test_parse_azerbaijani_headers_decimal_commas_and_native_names():
    from scrape_fed_aze import parse_rankings_table

    rows = parse_rankings_table(AZE_AZ_HEADERS_TABLE)

    assert rows[0] == {
        "rank": 1,
        "name": "ƏLİYEV Rəşad Иван",
        "club": "Bakı Qılıncoynatma Klubu",
        "points": 1234.5,
    }
    assert rows[1]["name"] == "Həsənli Xədicə"
    assert rows[1]["points"] == 48.0


def test_ranking_combos_cover_all_required_azerbaijan_rankings():
    from scrape_fed_aze import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_extracts_requested_public_section(monkeypatch):
    import scrape_fed_aze

    calls = []

    class Response:
        status_code = 200
        text = AZE_EPEE_FIXTURE_HTML
        url = "https://fencing.az/az/spaqa-reytinq/"

    def fake_get(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response()

    monkeypatch.setattr(scrape_fed_aze, "federation_request", fake_get)

    content = scrape_fed_aze.fetch_rankings_page("Epee", "Women", "Senior")
    rows = scrape_fed_aze.parse_rankings_table(content)

    assert calls[0][0] == "get"
    assert calls[0][1] == "https://fencing.az/az/spaqa-reytinq/"
    assert rows == [
        {"rank": 1, "name": "Quliyeva Aynur", "club": None, "points": 28.5},
        {"rank": 2, "name": "Mehdiyeva Nəzrin", "club": None, "points": 26.2},
    ]


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_aze

    class Response:
        status_code = 404
        text = "not found"
        url = "https://fencing.az/az/rapira-reytinq/"

    monkeypatch.setattr(scrape_fed_aze, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_aze.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_blocked_network(monkeypatch):
    import scrape_fed_aze

    def blocked(*args, **kwargs):
        raise requests.RequestException("geoblocked")

    monkeypatch.setattr(scrape_fed_aze, "federation_request", blocked)

    assert scrape_fed_aze.fetch_rankings_page("Sabre", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_for_login_only_page(monkeypatch):
    import scrape_fed_aze

    class Response:
        status_code = 200
        text = "<html><form><input type='password' name='password'>Login</form></html>"
        url = "https://fencing.az/az/sablya-reytinq/"

    monkeypatch.setattr(scrape_fed_aze, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_aze.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_js_only_without_ranking_data(monkeypatch):
    import scrape_fed_aze

    class Response:
        status_code = 200
        text = "<html><div id='app'></div><script src='/ranking.js'></script></html>"
        url = "https://fencing.az/az/sablya-reytinq/"

    monkeypatch.setattr(scrape_fed_aze, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_aze.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_missing_foil_combo(monkeypatch):
    import scrape_fed_aze

    def fail_if_called(*args, **kwargs):  # pragma: no cover - assertion helper
        raise AssertionError("missing public Foil combo should not make a request")

    monkeypatch.setattr(scrape_fed_aze, "federation_request", fail_if_called)

    assert scrape_fed_aze.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_current_season_format_and_before_july(monkeypatch):
    import scrape_fed_aze

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 2, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(scrape_fed_aze, "datetime", FixedDateTime)

    season = scrape_fed_aze.current_season()
    assert season == "2025-2026"
    assert re.match(r"^\d{4}-\d{4}$", season)

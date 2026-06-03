"""
Tests for scrape_fed_bul.py.

Probe evidence:
  - Official page: https://bulfencing.com/sastezania/ranglista.html
  - Ranking source: public Google Sheets CSV exports embedded by the page.
  - Public tabs cover all 12 Senior/Junior Foil/Epee/Sabre Men/Women combos.
  - Source headers include Bulgarian Cyrillic labels:
    ФАМИЛИЯ | ИМЕ | КЛУБ | Год. | Точки.
"""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


SABRE_MEN_CSV = '''\
,,,,,,22/11/2025,,17/5/2025
САБЯ мъже - ранглиста,,,,,,София,,Пловдив
,Фамилия,Име,Клуб,Год,точки,КБ1-мъж
1,Стойчев,Тодор,"ФК ""Свечников""",2003,75,1
2,Далеков,Симеон,"ФК ""Свечников""",2007,"68,5",3
3,Георгиев,Николай-Томас,"ССКФ ""Пловдив БГ""",2008,38,2
'''


BULGARIAN_HEADER_HTML = """
<html>
<body>
  <table>
    <thead>
      <tr><th>Място</th><th>Име</th><th>Клуб</th><th>Точки</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>Пастърмаджиева Виктория</td><td>Пловдив БГ</td><td>125,5</td></tr>
      <tr><td>2</td><td>Велчева Евангелина</td><td>ЕСКАЛИБУР</td><td>80</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


NO_DATA_HTML = """
<html>
<body>
  <h1>РАНГЛИСТА</h1>
  <p>Всички резултати подлежат на обновяване след всяко състезание.</p>
</body>
</html>
"""


SKIPPED_ROWS_CSV = '''\
,Фамилия,Име,Клуб,Год,Точки
DNS,Липсващ,Състезател,СКФ,2008,0
DQ,Дисквалифициран,Състезател,СКФ,2008,0
Общо,,,,,123
-,Нередовен,Ред,СКФ,2008,3
4,Гаджева,Ралица,"СКФ ""Младост""",2010,118
'''


def test_parse_csv_fixture_returns_valid_bulgarian_rows():
    from scrape_fed_bul import parse_rankings_table

    rows = parse_rankings_table(SABRE_MEN_CSV)

    assert rows[:3] == [
        {
            "rank": 1,
            "name": "Стойчев Тодор",
            "club": 'ФК "Свечников"',
            "points": 75.0,
        },
        {
            "rank": 2,
            "name": "Далеков Симеон",
            "club": 'ФК "Свечников"',
            "points": 68.5,
        },
        {
            "rank": 3,
            "name": "Георгиев Николай-Томас",
            "club": 'ССКФ "Пловдив БГ"',
            "points": 38.0,
        },
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_bul import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_bul import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_non_numeric_rank_rows():
    from scrape_fed_bul import parse_rankings_table

    rows = parse_rankings_table(SKIPPED_ROWS_CSV)

    assert rows == [
        {
            "rank": 4,
            "name": "Гаджева Ралица",
            "club": 'СКФ "Младост"',
            "points": 118.0,
        }
    ]


def test_parse_language_specific_headers_and_native_script_names_are_preserved():
    from scrape_fed_bul import parse_rankings_table

    rows = parse_rankings_table(BULGARIAN_HEADER_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "Пастърмаджиева Виктория",
            "club": "Пловдив БГ",
            "points": 125.5,
        },
        {
            "rank": 2,
            "name": "Велчева Евангелина",
            "club": "ЕСКАЛИБУР",
            "points": 80.0,
        },
    ]


def test_fetch_rankings_page_uses_public_csv_export(monkeypatch):
    import scrape_fed_bul

    calls = []

    class Response:
        status_code = 200
        text = SABRE_MEN_CSV
        headers = {"content-type": "text/csv"}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(scrape_fed_bul.requests, "get", fake_get)

    content = scrape_fed_bul.fetch_rankings_page("Sabre", "Men", "Senior")

    assert content == SABRE_MEN_CSV
    assert "output=csv" in calls[0][0]
    assert "gid=241008218" in calls[0][0]
    assert calls[0][1]["headers"] == scrape_fed_bul.HEADERS


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_bul

    class Response:
        status_code = 404
        text = "not found"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_bul.requests, "get", lambda *args, **kwargs: Response())

    assert scrape_fed_bul.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_fetch_rankings_page_decodes_google_csv_as_utf8(monkeypatch):
    import scrape_fed_bul

    raw = SABRE_MEN_CSV.encode("utf-8")

    class Response:
        status_code = 200
        content = raw
        text = raw.decode("latin1")
        headers = {"content-type": "text/csv"}

    monkeypatch.setattr(scrape_fed_bul.requests, "get", lambda *args, **kwargs: Response())

    content = scrape_fed_bul.fetch_rankings_page("Sabre", "Men", "Senior")
    rows = scrape_fed_bul.parse_rankings_table(content)

    assert rows[0]["name"] == "Стойчев Тодор"
    assert rows[0]["points"] == 75.0


def test_fetch_rankings_page_returns_none_for_network_error(monkeypatch):
    import scrape_fed_bul

    def fake_get(*args, **kwargs):
        raise requests.RequestException("blocked")

    monkeypatch.setattr(scrape_fed_bul.requests, "get", fake_get)

    assert scrape_fed_bul.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_login_only_page(monkeypatch):
    import scrape_fed_bul

    class Response:
        status_code = 200
        text = "<html><title>Sign in - Google Accounts</title>Please sign in</html>"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_bul.requests, "get", lambda *args, **kwargs: Response())

    assert scrape_fed_bul.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_js_only_page(monkeypatch):
    import scrape_fed_bul

    class Response:
        status_code = 200
        text = "<html>Please enable JavaScript to view this page.</html>"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_bul.requests, "get", lambda *args, **kwargs: Response())

    assert scrape_fed_bul.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_missing_combo():
    from scrape_fed_bul import fetch_rankings_page

    assert fetch_rankings_page("Foil", "Men", "Cadet") is None


def test_all_standard_ranking_combos_have_public_urls():
    import scrape_fed_bul

    assert len(scrape_fed_bul.RANKING_COMBOS) == 12
    for combo in scrape_fed_bul.RANKING_COMBOS:
        assert combo in scrape_fed_bul.RANKING_URLS

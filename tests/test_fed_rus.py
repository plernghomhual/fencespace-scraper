"""
Tests for scrape_fed_rus.py.

Fixture HTML reflects the live rusfencing.ru/rating.php table structure probed
on 2026-06-01:
  GET /rating.php?WEAPON=474&SEX=450&AGE=498&SEASON_CUSTOM=2025-2026&SEASON=4694833
  Tables: event list + results_table
  Ranking columns: Место | фамилия и имя | Дата рождения | Субъект РФ | Организация | ... | очки
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_HTML = """
<!doctype html>
<html>
<body>
<table class="table compact small laptopL">
  <tr>
    <th>№</th><th>ID ФФР</th><th>Соревнование</th><th>коэф.</th>
  </tr>
  <tr>
    <td>1</td><td>2025-0665</td><td>Всероссийское спортивное соревнование</td><td>0.5</td>
  </tr>
</table>
<table class="table compact small results_table">
  <thead>
    <tr>
      <th>Место</th>
      <th>фамилия и имя</th>
      <th>Дата рождения</th>
      <th>Субъект РФ</th>
      <th>Организация</th>
      <th>1 2025-0665 Всероссийское спортивное соревнование</th>
      <th>очки</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>Бородачев Кирилл</td>
      <td>23.03.2000</td>
      <td>САМ</td>
      <td>ГАУ СШОР № 5, ЦСКА</td>
      <td>16 Место: 1</td>
      <td>376</td>
    </tr>
    <tr>
      <td>2</td>
      <td>Бородачев Антон</td>
      <td>23.03.2000</td>
      <td>САМ</td>
      <td>ГАУ СШОР № 5, ЦСКА</td>
      <td>13 Место: 2</td>
      <td>213</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


FIXTURE_HEADER_VARIANTS = """
<html>
<body>
<table>
  <tr><th>Место</th><th>ФИО</th><th>Клуб</th><th>Очки</th></tr>
  <tr>
    <td>3</td>
    <td>Колобова Виолетта / KOLOBOVA Violetta</td>
    <td>Динамо-Москва</td>
    <td>121,5</td>
  </tr>
</table>
</body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
<html>
<body>
<table class="results_table">
  <tr><th>Место</th><th>фамилия и имя</th><th>Организация</th><th>очки</th></tr>
  <tr><td>DNS</td><td>Не стартовал</td><td>МОС</td><td>0</td></tr>
  <tr><td>DQ</td><td>Дисквалификация</td><td>СПБ</td><td>0</td></tr>
  <tr><td>Итого</td><td>Всего участников</td><td></td><td>2</td></tr>
  <tr><td>4</td><td>Егорян Яна</td><td>МГФСО</td><td>98,25</td></tr>
</table>
</body>
</html>
"""


FIXTURE_EMPTY_TABLE = """
<html>
<body>
<table class="results_table">
  <tr><th>Место</th><th>фамилия и имя</th><th>Организация</th><th>очки</th></tr>
</table>
</body>
</html>
"""


FIXTURE_NO_TABLE = """
<html><body><p>Данные не найдены</p></body></html>
"""


def test_parse_rus_rankings_returns_cyrillic_rows():
    from scrape_fed_rus import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Бородачев Кирилл"
    assert rows[0]["club"] == "ГАУ СШОР № 5, ЦСКА"
    assert rows[0]["points"] == 376.0


def test_parse_rus_rankings_empty_html_returns_empty_list():
    from scrape_fed_rus import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table(FIXTURE_EMPTY_TABLE) == []


def test_parse_rus_rankings_no_table_returns_empty_list():
    from scrape_fed_rus import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_TABLE) == []


def test_parse_rus_rankings_skips_dns_dq_and_summary_rows():
    from scrape_fed_rus import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 1
    assert rows[0]["rank"] == 4
    assert rows[0]["name"] == "Егорян Яна"
    assert rows[0]["points"] == 98.25


def test_parse_rus_rankings_accepts_header_variants_and_latin_alternate():
    from scrape_fed_rus import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HEADER_VARIANTS)

    assert len(rows) == 1
    assert rows[0]["rank"] == 3
    assert rows[0]["name"] == "Колобова Виолетта"
    assert rows[0]["latin_name"] == "KOLOBOVA Violetta"
    assert rows[0]["club"] == "Динамо-Москва"
    assert rows[0]["points"] == 121.5


def test_fetch_rankings_page_uses_live_rating_filters(monkeypatch):
    from scrape_fed_rus import fetch_rankings_page

    calls = []

    class Response:
        status_code = 200
        text = "<html>ok</html>"

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("scrape_fed_rus.requests.get", fake_get)

    assert fetch_rankings_page("Foil", "Men", "Senior") == "<html>ok</html>"

    assert calls[0][0] == "https://www.rusfencing.ru/rating.php"
    assert calls[0][1]["params"]["WEAPON"] == "474"
    assert calls[0][1]["params"]["SEX"] == "450"
    assert calls[0][1]["params"]["AGE"] == "498"
    assert calls[0][1]["params"]["SEASON_CUSTOM"]


def test_fetch_rankings_page_returns_none_on_404_or_request_error(monkeypatch):
    import requests

    from scrape_fed_rus import fetch_rankings_page

    class NotFound:
        status_code = 404
        text = "missing"

    monkeypatch.setattr("scrape_fed_rus.requests.get", lambda *args, **kwargs: NotFound())
    assert fetch_rankings_page("Foil", "Men", "Senior") is None

    def raise_error(*args, **kwargs):
        raise requests.RequestException("network down")

    monkeypatch.setattr("scrape_fed_rus.requests.get", raise_error)
    assert fetch_rankings_page("Foil", "Men", "Senior") is None

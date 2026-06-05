"""
Tests for scrape_fed_pol.py

Source: https://pzszerm.pl/zawody/klasyfikacje/
Probe notes:
  - /ranking and /rankingi return 404.
  - /klasyfikacje redirects to /zawody/klasyfikacje/.
  - Ranking detail pages are server-rendered HTML:
      /zawody/klasyfikacje/klasyfikacja/?id={id}
  - Current public coverage includes all 12 Senior/Junior Foil/Epee/Sabre
    Men/Women combos.

Representative Polish table headers:
  Miejsce | Imię i Nazwisko | Rocznik | Klub | Suma punktów | ...
"""
from typing import cast, Any
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_HTML = """
<!doctype html>
<html lang="pl-PL">
<body>
<table class="tab-style">
  <tr><td>Lista zawodów brana pod uwagę w klasyfikacji:</td></tr>
  <tr><td>1.</td><td>Mistrzostwa Polski Seniorów w szermierce - Warszawa 2025/2026</td></tr>
</table>
<table class="tab-style">
  <tr>
    <th>Miejsce</th>
    <th>Imię i Nazwisko</th>
    <th>Rocznik</th>
    <th>Klub</th>
    <th>Suma punktów</th>
    <th>1.</th>
  </tr>
  <tr>
    <td>1.</td>
    <td>JAKUBOWSKA Marta</td>
    <td>2006</td>
    <td>KS ORLEN AZS AWFIS GDAŃSK</td>
    <td>330</td>
    <td>Pkt: 150 M: 3</td>
  </tr>
  <tr>
    <td>2.</td>
    <td>ŻURAWSKA Karolina</td>
    <td>2004</td>
    <td>KU AZS-UAM POZNAŃ</td>
    <td>200,5</td>
    <td>Pkt: 40 M: 5</td>
  </tr>
  <tr>
    <td>3.</td>
    <td>Cieślik Jakub</td>
    <td>2002</td>
    <td></td>
    <td>131</td>
    <td></td>
  </tr>
</table>
</body>
</html>
"""


FIXTURE_ALTERNATE_HEADERS = """
<html>
<body>
<table>
  <tr>
    <th>Pozycja</th>
    <th>Zawodnik</th>
    <th>Klub</th>
    <th>Punkty</th>
  </tr>
  <tr>
    <td>4</td>
    <td>Kuźnik Bartosz</td>
    <td>AZS WRATISLAVIA WROCŁAW</td>
    <td>157,25</td>
  </tr>
  <tr>
    <td>5</td>
    <td>Łukasz Ździebło</td>
    <td>UKS ŻOLIBORZ</td>
    <td>151</td>
  </tr>
</table>
</body>
</html>
"""


FIXTURE_NO_DATA = """
<html>
<body>
  <h1>Lista klasyfikacyjna</h1>
  <p>Brak danych dla wybranej klasyfikacji.</p>
</body>
</html>
"""


FIXTURE_SKIP_ROWS = """
<html>
<body>
<table>
  <tr>
    <th>Miejsce</th>
    <th>Imię i Nazwisko</th>
    <th>Rocznik</th>
    <th>Klub</th>
    <th>Suma punktów</th>
  </tr>
  <tr><td>DNS</td><td>Nie startował</td><td></td><td>TEST</td><td>0</td></tr>
  <tr><td>DQ</td><td>Zdyskwalifikowany</td><td></td><td>TEST</td><td>0</td></tr>
  <tr><td>Razem</td><td>Podsumowanie</td><td></td><td></td><td>12</td></tr>
  <tr><td>1.</td><td>Matsuyama Aleksandra</td><td>1999</td><td>AZS AWF WARSZAWA</td><td>190</td></tr>
</table>
</body>
</html>
"""


def test_parse_pol_rankings_returns_rows_with_polish_text():
    from scrape_fed_pol import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "JAKUBOWSKA Marta",
        "club": "KS ORLEN AZS AWFIS GDAŃSK",
        "points": 330.0,
    }
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "ŻURAWSKA Karolina"
    assert rows[1]["club"] == "KU AZS-UAM POZNAŃ"
    assert rows[1]["points"] == 200.5
    assert rows[2]["club"] is None


def test_parse_pol_rankings_empty_html_returns_empty_list():
    from scrape_fed_pol import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_pol_rankings_no_table_or_no_data_returns_empty_list():
    from scrape_fed_pol import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_pol_rankings_skips_dns_dq_and_summary_rows():
    from scrape_fed_pol import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_SKIP_ROWS)

    assert rows == [
        {
            "rank": 1,
            "name": "Matsuyama Aleksandra",
            "club": "AZS AWF WARSZAWA",
            "points": 190.0,
        }
    ]


def test_parse_pol_rankings_accepts_language_specific_alternate_headers():
    from scrape_fed_pol import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_ALTERNATE_HEADERS)

    assert len(rows) == 2
    assert rows[0]["rank"] == 4
    assert rows[0]["name"] == "Kuźnik Bartosz"
    assert rows[0]["club"] == "AZS WRATISLAVIA WROCŁAW"
    assert rows[0]["points"] == 157.25
    assert rows[1]["name"] == "Łukasz Ździebło"
    assert rows[1]["points"] == 151.0


def test_pol_combo_discovery_skips_junior_younger_category():
    from scrape_fed_pol import _combo_from_label

    assert _combo_from_label("Lista klasyfikacyjna juniorów młodszych - floret mężczyzn") is None
    assert _combo_from_label("Lista klasyfikacyjna juniorów - floret mężczyzn") == (
        "Foil",
        "Men",
        "Junior",
    )


def test_pol_get_with_retry_retries_transient_http_status(monkeypatch):
    import scrape_fed_pol

    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

    responses = [Response(503), Response(200)]
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(scrape_fed_pol.requests, "get", fake_get)
    monkeypatch.setattr(scrape_fed_pol.time, "sleep", lambda seconds: None)

    response = scrape_fed_pol._get_with_retry("https://pzszerm.pl/test")

    response = cast(Any, response)
    assert response.status_code == 200
    assert len(calls) == 2

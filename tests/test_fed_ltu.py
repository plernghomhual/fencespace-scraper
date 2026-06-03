"""
Tests for scrape_fed_ltu.py.

Probe evidence, 2026-06-02:
  - https://ltf.lt/ is the Lithuanian volleyball federation, not fencing.
  - Current fencing ranking page: https://fechtavimas.lt/reitingas
  - Public ranking source: Google Sheets export from the "Visa reitingo lentelė" link.
  - Request method: GET.
  - Response format: text/csv sheet exports from a public Google spreadsheet.
  - Public domestic sheets cover epee rankings by gender and age group:
      suaugeV, suaugeM, JaunimasV_U20, JaunimasM_U20.
    No public foil/sabre domestic ranking sheets were found in the probed workbook.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


LTU_SENIOR_MEN_CSV = """
,suaugusiųjų koeficientas,,,,,,,,,1.5,,,,,,,,,,,
,Lietuvos varžybos,,J.Subačiaus Taurė (Lietuvos čempionato I etapas),,Lietuvos Taurė (Lietuvos žiemos čempionatas; II etapas,, Lietuvos III etapas,,Lietuvos suaugusiųjų čempionatas,,geriausias rezultatas,,2024/2025m,,,,,,,,
,,,Dalyvių skaičius,60,Dalyvių skaičius,45,Dalyvių skaičius,51,Dalyvių skaičius,,Geriausi 3 rezultatai LT,Geriausi 3 rezultatai UŽ,0.15,Bendra taškų suma,,,,,,,
Eil.nr.,Vardas pavardė,Gimimo metai,Vieta,Taškai,Vieta,Taškai,Vieta,Taškai,Vieta,Taškai,Taskai,Taskai,,Suma,
1,Tamošiūnas Mindaugas,1990,10,24,1,64,17,16,1,96,184,100,31,315,
2,Lozenko Makar,2003,2,56,17,16,3,48,2,84,188,88,25,301,
3,Salokas Arnas,1998,3,48,9,24,,0,3,72,144,,23,167,
"""


LTU_LOCALIZED_HEADER_CSV = """
Vieta,Vardas,Pavardė,Klubas,Taškai
1,ŽILIONYTĖ,Beatričė,Gintarinė Špaga,"1 234,50"
2,Юлия,Äėšūnaitė,Vilniaus fechtavimo klubas,"98,5"
"""


LTU_JUNIOR_MEN_U20_CSV = """
,,,Koeficientas,1,Koeficientas,1,Koeficientas,,Koeficientas,1,Koeficientas,,Koeficientas,,Koeficientas,1,Koeficientas,1.5,Koeficientas,,,,,,,,
,Jaunimas vyrai,,Lietuvos I U-20 etapas,,Subačiaus taurė,,Lietuvos žiemos taurė,,Lietuvos U-20 II etapas,,Lietuvos suaugusiųjų žiemos taurė,,Lietuvos U-20 čempionatas,,Lietuvos suaugusiųjų čempionato III etapas,,Lietuvos suaugusiųjų čempionatas,,Lietuvos U-23 čempionatas,,,,,,,,
,Lietuvos varžybos,,Dalyviu skaičius,24,Dalyviu sk,60,Dalyviu sk,,Dalyvių skaičius,19,Dalyvių skaičius,45,Dalyvių skaičius,28,Dalyvių skaičius,51,,,Dalyvių skaičius,,max 1,max2,max3,LT max suma,UŽ max suma,2024/2025m,Bendra taškų suma
Eil.nr.,Vardas pavardė,Gimimo metai,Vieta,Taškai,Vieta,Taškai,Vieta,Taškai,Vieta,Taškai,Vieta,Taškai,Vieta,Taškai,Vieta,Taškai,Vieta,Taškai,Vieta,Taškai,Taskai,Taskai,Taškai,Taškai,Taškai,Taškai,Suma
1,Rauktys Rytis,2008,1,64,8,32,,,2,56,,,2,84,19,16,18,24,,,64,84,56,204,168,41,413
"""


SKIP_ROWS_CSV = """
Vieta,Vardas / Pavardė,Klubas,Taškai
DNS,Neatvykęs Sportininkas,Klubas,0
DQ,Diskvalifikuotas Sportininkas,Klubas,0
Iš viso,3 sportininkai,,999
abc,Bloga eilutė,Klubas,1
3,ŠIMKUTĖ Aušrinė,Fechtavimo Akademija,"42,25"
"""


NO_DATA_HTML = """
<html>
<body>
  <h1>Reitingas</h1>
  <p>Reitingo duomenų nėra.</p>
</body>
</html>
"""


HTML_TABLE_FIXTURE = """
<table>
  <thead>
    <tr><th>Vieta</th><th>Vardas / Pavardė</th><th>Klubas</th><th>Taškai</th></tr>
  </thead>
  <tbody>
    <tr><td>1.</td><td>VITONĖ Patricija</td><td>SM Gaja</td><td>64,5</td></tr>
  </tbody>
</table>
"""


def test_ranking_combos_contains_all_standard_senior_and_junior_combos():
    import scrape_fed_ltu

    assert len(scrape_fed_ltu.RANKING_COMBOS) == 12
    assert ("Foil", "Men", "Senior") in scrape_fed_ltu.RANKING_COMBOS
    assert ("Epee", "Women", "Junior") in scrape_fed_ltu.RANKING_COMBOS
    assert ("Sabre", "Women", "Junior") in scrape_fed_ltu.RANKING_COMBOS


def test_parse_public_google_sheet_csv_returns_valid_rows():
    from scrape_fed_ltu import parse_rankings_table

    rows = parse_rankings_table(LTU_SENIOR_MEN_CSV)

    assert rows[:2] == [
        {
            "rank": 1,
            "name": "Tamošiūnas Mindaugas",
            "club": None,
            "points": 315.0,
        },
        {
            "rank": 2,
            "name": "Lozenko Makar",
            "club": None,
            "points": 301.0,
        },
    ]
    assert rows[2]["name"] == "Salokas Arnas"
    assert rows[2]["points"] == 167.0


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_ltu import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("   \n\t") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_ltu import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_malformed_non_numeric_dns_dq_and_summary_rows():
    from scrape_fed_ltu import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_CSV)

    assert rows == [
        {
            "rank": 3,
            "name": "ŠIMKUTĖ Aušrinė",
            "club": "Fechtavimo Akademija",
            "points": 42.25,
        }
    ]


def test_parse_lithuanian_headers_decimal_commas_and_native_scripts():
    from scrape_fed_ltu import parse_rankings_table

    rows = parse_rankings_table(LTU_LOCALIZED_HEADER_CSV)

    assert rows[0] == {
        "rank": 1,
        "name": "ŽILIONYTĖ Beatričė",
        "club": "Gintarinė Špaga",
        "points": 1234.5,
    }
    assert rows[1]["name"] == "Юлия Äėšūnaitė"
    assert rows[1]["club"] == "Vilniaus fechtavimo klubas"
    assert rows[1]["points"] == 98.5


def test_parse_public_u20_sheet_uses_eil_nr_not_later_event_vieta_columns():
    from scrape_fed_ltu import parse_rankings_table

    rows = parse_rankings_table(LTU_JUNIOR_MEN_U20_CSV)

    assert rows == [
        {
            "rank": 1,
            "name": "Rauktys Rytis",
            "club": None,
            "points": 413.0,
        }
    ]


def test_parse_html_lithuanian_table_fixture():
    from scrape_fed_ltu import parse_rankings_table

    rows = parse_rankings_table(HTML_TABLE_FIXTURE)

    assert rows == [
        {
            "rank": 1,
            "name": "VITONĖ Patricija",
            "club": "SM Gaja",
            "points": 64.5,
        }
    ]


def test_fetch_rankings_page_uses_public_epee_sheet_export(monkeypatch):
    import scrape_fed_ltu

    calls = []

    class Response:
        status_code = 200
        text = "Eil.nr.,Vardas pavardė,Suma\n1,Tamošiūnas Mindaugas,315\n"
        headers = {"content-type": "text/csv"}
        url = "https://docs.google.com/spreadsheets/d/test/export?format=csv&gid=1854966084"

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response()

    monkeypatch.setattr(scrape_fed_ltu, "federation_request", fake_request)

    content = scrape_fed_ltu.fetch_rankings_page("Epee", "Men", "Senior")

    assert "Tamošiūnas" in content
    assert calls[0][0] == "get"
    assert "format=csv" in calls[0][1]
    assert "gid=1854966084" in calls[0][1]
    assert calls[0][2]["headers"] == scrape_fed_ltu.HEADERS


def test_fetch_rankings_page_returns_none_for_missing_weapon_combo():
    from scrape_fed_ltu import fetch_rankings_page

    assert fetch_rankings_page("Foil", "Men", "Senior") is None
    assert fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_ltu

    class Response:
        status_code = 404
        text = "not found"
        headers = {"content-type": "text/html"}
        url = "https://docs.google.com/not-found"

    monkeypatch.setattr(scrape_fed_ltu, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_ltu.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_blocked_response(monkeypatch):
    import scrape_fed_ltu

    class Response:
        status_code = 403
        text = "Forbidden"
        headers = {"content-type": "text/html"}
        url = "https://docs.google.com/blocked"

    monkeypatch.setattr(scrape_fed_ltu, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_ltu.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_for_login_only_html(monkeypatch):
    import scrape_fed_ltu

    class Response:
        status_code = 200
        text = "<html><title>Sign in - Google Accounts</title><body>Login required</body></html>"
        headers = {"content-type": "text/html; charset=utf-8"}
        url = "https://accounts.google.com/signin"

    monkeypatch.setattr(scrape_fed_ltu, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_ltu.fetch_rankings_page("Epee", "Men", "Junior") is None


def test_fetch_rankings_page_returns_none_for_js_only_html(monkeypatch):
    import scrape_fed_ltu

    class Response:
        status_code = 200
        text = "<html><body>Please enable JavaScript to view this file.</body></html>"
        headers = {"content-type": "text/html; charset=utf-8"}
        url = "https://docs.google.com/spreadsheets/d/test/htmlview"

    monkeypatch.setattr(scrape_fed_ltu, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_ltu.fetch_rankings_page("Epee", "Women", "Junior") is None

import requests

import scrape_fed_est as est


LIVE_STYLE_TABLE = """
<table id="tablepress-188" class="tablepress">
  <tbody>
    <tr>
      <th>Koht</th><th>Nimi</th><th>Sünniaasta</th><th>Vanuseklass</th>
      <th>Klubi</th><th>Kokku</th><th>1 Stardipunktid</th>
    </tr>
    <tr>
      <td>1</td><td>PRIINITS Sten</td><td>1987</td><td>taiskasvanu</td>
      <td>En Garde</td><td>145</td><td>17</td>
    </tr>
    <tr>
      <td>2</td><td>JÕGISU Johanna Maria</td><td>2002</td><td>täiskasvanu</td>
      <td>Tallinna Mõõk</td><td>14,5</td><td>6</td>
    </tr>
  </tbody>
</table>
"""


ESTONIAN_HEADER_TABLE = """
<table>
  <tr><th>Koht</th><th>Nimi</th><th>Klubi</th><th>Punktid</th></tr>
  <tr><td>1</td><td>PÄRLIN Ksenja</td><td>Tartu Kalev</td><td>12,5</td></tr>
  <tr><td>2</td><td>ŽURBA Ilia</td><td>Le Glaive</td><td>1</td></tr>
</table>
"""


SKIP_ROWS_TABLE = """
<table>
  <tr><th>Koht</th><th>Nimi</th><th>Klubi</th><th>Punktid</th></tr>
  <tr><td>Koht</td><td>Nimi</td><td>Klubi</td><td>Punktid</td></tr>
  <tr><td>DNS</td><td>Puudub Vehkleja</td><td>En Garde</td><td>0</td></tr>
  <tr><td>2</td><td>DQ</td><td>En Garde</td><td>10</td></tr>
  <tr><td>3</td><td>Kokku</td><td></td><td>100</td></tr>
  <tr><td>1. Stardipunktid</td><td></td><td></td><td></td></tr>
  <tr><td>4</td><td>ANIS Dinara</td><td>Tallinna Mõõk</td><td>29</td></tr>
</table>
"""


class FakeResponse:
    def __init__(self, status_code=200, text="", content_type="text/html"):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = {"content-type": content_type}


def test_parse_rankings_table_returns_valid_rows():
    rows = est.parse_rankings_table(LIVE_STYLE_TABLE)

    assert rows[0] == {
        "rank": 1,
        "name": "PRIINITS Sten",
        "club": "En Garde",
        "points": 145.0,
    }
    assert rows[1] == {
        "rank": 2,
            "name": "JÕGISU Johanna Maria",
            "club": "Tallinna Mõõk",
        "points": 14.5,
    }


def test_parse_empty_html_returns_empty_list():
    assert est.parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    html = "<html><h1>Sellist lehekülge ei eksisteeri!</h1><p>Lehte ei leitud.</p></html>"
    assert est.parse_rankings_table(html) == []


def test_parse_skips_dns_dq_malformed_and_summary_rows():
    assert est.parse_rankings_table(SKIP_ROWS_TABLE) == [
        {
            "rank": 4,
            "name": "ANIS Dinara",
            "club": "Tallinna Mõõk",
            "points": 29.0,
        }
    ]


def test_parse_estonian_headers_decimal_commas_and_native_names():
    rows = est.parse_rankings_table(ESTONIAN_HEADER_TABLE)

    assert rows == [
        {"rank": 1, "name": "PÄRLIN Ksenja", "club": "Tartu Kalev", "points": 12.5},
        {"rank": 2, "name": "ŽURBA Ilia", "club": "Le Glaive", "points": 1.0},
    ]


def test_ranking_combos_attempt_all_standard_weapon_gender_category_pairs():
    assert len(est.RANKING_COMBOS) == 12
    assert ("Foil", "Men", "Senior") in est.RANKING_COMBOS
    assert ("Epee", "Women", "Junior") in est.RANKING_COMBOS
    assert ("Sabre", "Women", "Junior") in est.RANKING_COMBOS


def test_fetch_rankings_page_uses_public_estonia_mapping(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse(text=LIVE_STYLE_TABLE)

    monkeypatch.setattr(est, "current_season", lambda: "2025-2026")
    monkeypatch.setattr(est, "federation_request", fake_request)

    html = est.fetch_rankings_page("Epee", "Women", "Junior")

    assert html == LIVE_STYLE_TABLE
    assert calls[0][0] == "get"
    assert calls[0][1] == "https://vehklemisliit.ee/2025-2026-edetabel-u20-naised/"
    assert calls[0][2]["headers"] == est.HEADERS


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    monkeypatch.setattr(est, "current_season", lambda: "2025-2026")
    monkeypatch.setattr(
        est,
        "federation_request",
        lambda method, url, **kwargs: FakeResponse(status_code=404, text="not found"),
    )

    assert est.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_blocked_response(monkeypatch):
    monkeypatch.setattr(est, "current_season", lambda: "2025-2026")
    monkeypatch.setattr(
        est,
        "federation_request",
        lambda method, url, **kwargs: FakeResponse(status_code=403, text="Forbidden"),
    )

    assert est.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_login_only_page(monkeypatch):
    login_only = "<html><h1>Logi sisse</h1><p>Palun logi sisse edetabeli vaatamiseks.</p></html>"
    monkeypatch.setattr(est, "current_season", lambda: "2025-2026")
    monkeypatch.setattr(
        est,
        "federation_request",
        lambda method, url, **kwargs: FakeResponse(text=login_only),
    )

    assert est.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_js_only_page(monkeypatch):
    js_only = "<html><div id='app'></div><noscript>Please enable JavaScript.</noscript></html>"
    monkeypatch.setattr(est, "current_season", lambda: "2025-2026")
    monkeypatch.setattr(
        est,
        "federation_request",
        lambda method, url, **kwargs: FakeResponse(text=js_only),
    )

    assert est.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_network_error(monkeypatch):
    def fail_request(method, url, **kwargs):
        raise requests.RequestException("timeout")

    monkeypatch.setattr(est, "current_season", lambda: "2025-2026")
    monkeypatch.setattr(est, "federation_request", fail_request)

    assert est.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_missing_weapon_combo(monkeypatch):
    def fail_if_called(method, url, **kwargs):
        raise AssertionError("missing foil/sabre combos should not be requested")

    monkeypatch.setattr(est, "federation_request", fail_if_called)

    assert est.fetch_rankings_page("Foil", "Men", "Senior") is None
    assert est.fetch_rankings_page("Sabre", "Women", "Junior") is None

from datetime import datetime
from typing import cast

import pytest

SLO_PDF_TEXT = """
Rang lestvice - SZS Meč
M Člani, Moški, Meč RZL RZL RZL
Rang Tekmovalec Klub Letnik Točke
DP Kamnik 31.05.2025
A B C
1 Jan Golobič ŠD TABOR 1992 1135 132 273 249
2 Timon Grubar ŠD TABOR 2002 726 141 152 44
3 Vito Hvala SK LJUBLJANA 2007 644 115 148 32
Ž Člani, Ženski, Meč RZL RZL
Rang Tekmovalka Klub Letnik Točke
1 Francesca Parmesani SK LJUBLJANA 2002 494 150 268 76
"""


SLO_HTML_TABLE = """
<html>
  <body>
    <table>
      <thead>
        <tr><th>Mesto</th><th>Ime</th><th>Klub</th><th>Točke</th></tr>
      </thead>
      <tbody>
        <tr><td>1.</td><td>Črt Mažgon Müller</td><td>ŠD TABOR</td><td>198,5</td></tr>
        <tr><td>2</td><td>Лина Zhukovska</td><td>SK ERAZEM</td><td>87</td></tr>
      </tbody>
    </table>
  </body>
</html>
"""


SKIPPED_ROWS_HTML = """
<table>
  <tr><th>Uvrstitev</th><th>Tekmovalec</th><th>Klub</th><th>Točke</th></tr>
  <tr><td>DNS</td><td>Neznan Tekmovalec</td><td>SK LJUBLJANA</td><td>0</td></tr>
  <tr><td>DQ</td><td>Diskvalificiran Tekmovalec</td><td>SK IZOLA</td><td>0</td></tr>
  <tr><td>Skupaj</td><td>Total</td><td></td><td>300</td></tr>
  <tr><td>not-rank</td><td>Malformed</td><td>SK KAMNIK</td><td>10</td></tr>
  <tr><td>4</td><td>Živa Bizjak</td><td>SK KAMNIK</td><td>50,25</td></tr>
</table>
"""


NO_DATA_HTML = """
<html><body><p>Ni podatkov za izbrano kategorijo.</p></body></html>
"""


def test_parse_rankings_table_extracts_realistic_pdf_rows():
    from scrape_fed_slo import parse_rankings_table

    rows = parse_rankings_table(SLO_PDF_TEXT)

    assert rows[:3] == [
        {"rank": 1, "name": "Jan Golobič", "club": "ŠD TABOR", "points": 1135.0},
        {"rank": 2, "name": "Timon Grubar", "club": "ŠD TABOR", "points": 726.0},
        {"rank": 3, "name": "Vito Hvala", "club": "SK LJUBLJANA", "points": 644.0},
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_slo import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_slo import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_and_non_numeric_rank_rows():
    from scrape_fed_slo import parse_rankings_table

    rows = parse_rankings_table(SKIPPED_ROWS_HTML)

    assert rows == [
        {"rank": 4, "name": "Živa Bizjak", "club": "SK KAMNIK", "points": 50.25}
    ]


def test_parse_slovenian_headers_decimal_commas_and_native_names():
    from scrape_fed_slo import parse_rankings_table

    rows = parse_rankings_table(SLO_HTML_TABLE)

    assert rows == [
        {"rank": 1, "name": "Črt Mažgon Müller", "club": "ŠD TABOR", "points": 198.5},
        {"rank": 2, "name": "Лина Zhukovska", "club": "SK ERAZEM", "points": 87.0},
    ]


def test_ranking_combos_cover_all_required_slovenia_rankings():
    from scrape_fed_slo import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_extracts_requested_combo_from_public_pdf(monkeypatch):
    import scrape_fed_slo

    calls = []

    class Response:
        status_code = 200
        content = b"%PDF-1.4"
        text = ""
        headers = {"content-type": "application/pdf"}
        url = "https://example.test/rl_24_25_me%C4%8D.pdf"

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response()

    monkeypatch.setattr(scrape_fed_slo, "_fetch_current_sheet_text", lambda *args: None)
    monkeypatch.setattr(scrape_fed_slo, "federation_request", fake_request)
    monkeypatch.setattr(scrape_fed_slo, "_extract_pdf_text", lambda content: SLO_PDF_TEXT)
    monkeypatch.setitem(
        scrape_fed_slo.PDF_RANKING_URLS,
        "Epee",
        "https://example.test/rl_24_25_me%C4%8D.pdf",
    )

    content = scrape_fed_slo.fetch_rankings_page("Epee", "Men", "Senior")
    content = cast(str, content)
    rows = scrape_fed_slo.parse_rankings_table(content)

    assert rows[0]["name"] == "Jan Golobič"
    assert rows[0]["points"] == 1135.0
    assert calls[0][0] == "get"
    assert calls[0][1] == "https://example.test/rl_24_25_me%C4%8D.pdf"
    assert calls[0][2]["headers"] == scrape_fed_slo.HEADERS


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_slo

    class Response:
        status_code = 404
        content = b"missing"
        text = "missing"
        headers = {"content-type": "text/html"}
        url = "https://example.test/missing.pdf"

    monkeypatch.setattr(scrape_fed_slo, "_fetch_current_sheet_text", lambda *args: None)
    monkeypatch.setattr(scrape_fed_slo, "federation_request", lambda *args, **kwargs: Response())
    monkeypatch.setitem(scrape_fed_slo.PDF_RANKING_URLS, "Foil", "https://example.test/missing.pdf")

    assert scrape_fed_slo.fetch_rankings_page("Foil", "Men", "Senior") is None


@pytest.mark.parametrize(
    ("status_code", "body"),
    [
        (403, "Access denied"),
        (200, "<html><form action='ServiceLogin'>Sign in</form></html>"),
        (200, "<html><noscript>Please enable JavaScript to view this app.</noscript></html>"),
    ],
)
def test_fetch_rankings_page_returns_none_for_blocked_login_or_js_only_pages(
    monkeypatch, status_code, body
):
    import scrape_fed_slo

    class Response:
        content = body.encode("utf-8")
        text = body
        headers = {"content-type": "text/html"}
        url = "https://example.test/ranking"

        def __init__(self, status_code):
            self.status_code = status_code

    monkeypatch.setattr(scrape_fed_slo, "_fetch_current_sheet_text", lambda *args: None)
    monkeypatch.setattr(
        scrape_fed_slo,
        "federation_request",
        lambda *args, **kwargs: Response(status_code),
    )
    monkeypatch.setitem(scrape_fed_slo.PDF_RANKING_URLS, "Sabre", "https://example.test/ranking")

    assert scrape_fed_slo.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_fetch_rankings_page_returns_none_for_missing_combo_mapping(monkeypatch):
    import scrape_fed_slo

    monkeypatch.setattr(scrape_fed_slo, "_fetch_current_sheet_text", lambda *args: None)
    monkeypatch.delitem(scrape_fed_slo.PDF_RANKING_URLS, "Sabre", raising=False)

    assert scrape_fed_slo.fetch_rankings_page("Sabre", "Men", "Junior") is None


def test_current_season_uses_season_utils_format(monkeypatch):
    import scrape_fed_slo

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 2, tzinfo=tz)

    monkeypatch.setattr(scrape_fed_slo, "datetime", FixedDateTime)

    assert scrape_fed_slo.current_season() == "2025-2026"

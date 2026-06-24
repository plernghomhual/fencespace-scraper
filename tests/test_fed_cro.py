"""
Tests for scrape_fed_cro.py.

Probe evidence:
  - HMS ranking index: https://hms.hr/rang-liste
  - Request method: GET
  - Response format: server-rendered HTML index linking to public PDFs.
  - Latest probed 2025/2026 ranking media target returns application/pdf
    despite a .png path:
    https://v3-hms-master-uxhuxdpqnq-ew.a.run.app/media/221/463779/MediumSize/20260513-rang-hms-pdf.png/YAv9vjk7pjfsVeD.Eevz-BOCaQFupHlkDrgMlE119Y358~~221
  - Sampled PDF text uses Croatian labels such as:
    Rg. Prezime | Ime | Klub | Bod. Zbroj.
"""

import os
import re
import sys
from datetime import UTC, datetime, timezone
from typing import cast

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


HMS_PDF_TEXT_FIXTURE = """
HRVATSKI MAČEVALAČKI SAVEZ

RANG LISTA

FLORET JUNIORI

PRIVREMENI POREDAK
NATJECATELJSKE SEZONE
2025./2026.
13.05.2026.

Rg. Prezime
1. Badžek
2. Ambruš Maršić
3. Čupić

Ime
Leon
Andro
Марко

Klub
Dubrava
Rapir
Zagreb

god. Bod. Zbroj
2007 124
2008 98,5
2009 1.234,50
"""


CROATIAN_HEADER_HTML = """
<table>
  <thead>
    <tr><th>Mjesto</th><th>Ime i prezime</th><th>Klub</th><th>Bodovi</th></tr>
  </thead>
  <tbody>
    <tr><td>1.</td><td>ŠIMIĆ Željka</td><td>Split</td><td>1.234,50</td></tr>
    <tr><td>2</td><td>Ćosić Лука</td><td>Dubrava</td><td>98,5</td></tr>
  </tbody>
</table>
"""


SKIP_ROWS_HTML = """
<table>
  <thead>
    <tr><th>Poredak</th><th>Ime i prezime</th><th>Klub</th><th>Bod. Zbroj</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Did Not Start</td><td>Split</td><td>0</td></tr>
    <tr><td>DQ</td><td>Disqualified</td><td>Split</td><td>0</td></tr>
    <tr><td>Ukupno</td><td>Sažetak</td><td></td><td>300</td></tr>
    <tr><td>ABC</td><td>Malformed Rank</td><td>Dubrava</td><td>12</td></tr>
    <tr><td>0</td><td>Zero Rank</td><td>Dubrava</td><td>12</td></tr>
    <tr><td>3.</td><td>KNEZOVIĆ Dora</td><td>Mladost</td><td>76,25</td></tr>
  </tbody>
</table>
"""


NO_TABLE_HTML = """
<!doctype html>
<html><body><p>Nema podataka za odabranu rang listu.</p></body></html>
"""


INDEX_HTML = """
<html><body>
  <h2>RANG LISTA HMS-A 2024/2025</h2>
  <a href="/media/221/437600/MediumSize/20250729-rang-hms-zavrsna-pdf.png/old~~221">
    Rang lista HMS-a od dana 29.07.2025. (završna za sezonu)
  </a>
  <h2>RANG LISTA HMS-A 2025./2026.</h2>
  <a href="https://v3-hms-master-uxhuxdpqnq-ew.a.run.app/media/221/462692/MediumSize/20260429-rang-hms-pdf.png/older~~221">
    Rang lista HMS-a od dana 29.04.2026.
  </a>
  <a href="https://v3-hms-master-uxhuxdpqnq-ew.a.run.app/media/221/463779/MediumSize/20260513-rang-hms-pdf.png/latest~~221">
    Rang lista HMS-a od dana 13.05.2026.
  </a>
</body></html>
"""


MULTI_SECTION_TEXT = """
HRVATSKI MAČEVALAČKI SAVEZ
RANG LISTA
FLORET SENIORI
Rg. Prezime
1. Horvat
Ime
Ivan
Klub
Zagreb
god. Bod. Zbroj
2002 200

HRVATSKI MAČEVALAČKI SAVEZ
RANG LISTA
SABLJA JUNIORKE
Rg. Prezime
1. Jurić
Ime
Ana
Klub
Mladost
god. Bod. Zbroj
2006 88
"""


class FakeResponse:
    def __init__(self, *, status_code=200, text="", content=b"", headers=None):
        self.status_code = status_code
        self.text = text
        self.content = content
        self.headers = headers or {}
        self.url = "https://example.test/response"


def test_parse_hms_pdf_text_returns_valid_rows():
    from scrape_fed_cro import parse_rankings_table

    rows = parse_rankings_table(HMS_PDF_TEXT_FIXTURE)

    assert rows == [
        {"rank": 1, "name": "Badžek Leon", "club": "Dubrava", "points": 124.0},
        {"rank": 2, "name": "Ambruš Maršić Andro", "club": "Rapir", "points": 98.5},
        {"rank": 3, "name": "Čupić Марко", "club": "Zagreb", "points": 1234.5},
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_cro import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_cro import parse_rankings_table

    assert parse_rankings_table(NO_TABLE_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_zero_rank_rows():
    from scrape_fed_cro import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {"rank": 3, "name": "KNEZOVIĆ Dora", "club": "Mladost", "points": 76.25}
    ]


def test_parse_croatian_headers_preserves_utf8_and_native_script_names():
    from scrape_fed_cro import parse_rankings_table

    rows = parse_rankings_table(CROATIAN_HEADER_HTML)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "ŠIMIĆ Željka"
    assert rows[0]["club"] == "Split"
    assert rows[0]["points"] == 1234.5
    assert rows[1]["name"] == "Ćosić Лука"
    assert rows[1]["points"] == 98.5


def test_ranking_combos_cover_all_required_croatia_rankings():
    from scrape_fed_cro import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_extract_latest_pdf_url_uses_current_season_newest_link():
    from scrape_fed_cro import _extract_latest_pdf_url

    url = cast(str, _extract_latest_pdf_url(INDEX_HTML))

    assert url.endswith("/20260513-rang-hms-pdf.png/latest~~221")


def test_extract_combo_section_returns_requested_public_combo_only():
    from scrape_fed_cro import _extract_combo_section

    section = cast(str, _extract_combo_section(MULTI_SECTION_TEXT, "Sabre", "Women", "Junior"))

    assert "SABLJA JUNIORKE" in section
    assert "FLORET SENIORI" not in section
    from scrape_fed_cro import parse_rankings_table

    assert parse_rankings_table(section)[0]["name"] == "Jurić Ana"


def test_fetch_rankings_page_returns_none_on_index_404(monkeypatch):
    import scrape_fed_cro

    monkeypatch.setattr(
        scrape_fed_cro,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(status_code=404, text="missing"),
    )
    scrape_fed_cro._PDF_TEXT_CACHE.clear()

    assert scrape_fed_cro.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_on_blocked_network_error(monkeypatch):
    import scrape_fed_cro

    def blocked(*args, **kwargs):
        raise requests.RequestException("blocked")

    monkeypatch.setattr(scrape_fed_cro, "federation_request", blocked)
    scrape_fed_cro._PDF_TEXT_CACHE.clear()

    assert scrape_fed_cro.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_login_or_js_only_index(monkeypatch):
    import scrape_fed_cro

    pages = [
        "<html><body><form><input name='password'></form>Prijava</body></html>",
        "<html><body><div id='root'></div><script src='/app.js'></script></body></html>",
    ]

    for html in pages:
        monkeypatch.setattr(
            scrape_fed_cro,
            "federation_request",
            lambda *args, html=html, **kwargs: FakeResponse(text=html),
        )
        scrape_fed_cro._PDF_TEXT_CACHE.clear()
        assert scrape_fed_cro.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_when_combo_missing(monkeypatch):
    import scrape_fed_cro

    monkeypatch.setattr(scrape_fed_cro, "_get_latest_pdf_text", lambda: MULTI_SECTION_TEXT)

    assert scrape_fed_cro.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_returns_requested_combo_section(monkeypatch):
    import scrape_fed_cro

    monkeypatch.setattr(scrape_fed_cro, "_get_latest_pdf_text", lambda: MULTI_SECTION_TEXT)

    content = cast(str, scrape_fed_cro.fetch_rankings_page("Foil", "Men", "Senior"))

    assert "FLORET SENIORI" in content
    assert "SABLJA JUNIORKE" not in content
    assert scrape_fed_cro.parse_rankings_table(content)[0]["name"] == "Horvat Ivan"


def test_current_season_format_and_before_july(monkeypatch):
    import scrape_fed_cro

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 1, tzinfo=tz or UTC)

    monkeypatch.setattr(scrape_fed_cro, "datetime", FixedDateTime)

    season = scrape_fed_cro.current_season()
    assert season == "2025-2026"
    assert re.match(r"^\d{4}-\d{4}$", season)

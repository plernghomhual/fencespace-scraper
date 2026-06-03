"""Tests for the Cyprus federation rankings scraper.

Source probe (2026-06-02):
  - Requested cyprusfencing.com did not resolve in the local sandbox.
  - The current public federation site is https://fencing.org.cy/.
  - The rankings page is https://fencing.org.cy/rankings/.
  - The public rankings asset linked there is:
      https://fencing.org.cy/wp-content/uploads/Rankings-290126.pdf
  - Response format is PDF; fixtures below mirror pdfplumber-style extracted
    Greek/English text and bilingual table fallbacks.
"""

import os
import sys
from datetime import datetime, timezone

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_PDF_TEXT = """
ΚΥΠΡΙΑΚΗ ΟΜΟΣΠΟΝΔΙΑ ΞΙΦΑΣΚΙΑΣ
ΠΙΝΑΚΕΣ ΚΑΤΑΤΑΞΗΣ 2025-2026
ΞΙΦΟΣ ΜΟΝΟΜΑΧΙΑΣ - ΑΝΔΡΩΝ / EPEE MEN
Θέση Ονοματεπώνυμο Σύλλογος Βαθμοί
1 ΓΕΩΡΓΙΟΥ Ανδρέας Λευκωσία 125,50
2 CHRISTODOULOU Marios Limassol Fencing Club 98.25
Σύνολο 2 αθλητές

ΞΙΦΟΣ ΜΟΝΟΜΑΧΙΑΣ - ΝΕΑΝΙΔΩΝ / EPEE JUNIOR WOMEN
Position Name Club Points
1 ΠΑΠΑΔΟΠΟΥΛΟΥ Μαρία Cyprus Fencing Academy 87,5
DQ ΑΘΛΗΤΡΙΑ Δοκιμή Test Club 0
2 IOANNOU Eleni Nicosia Fencing Club 71.25
"""


FIXTURE_BILINGUAL_HTML = """
<table>
  <thead>
    <tr>
      <th>Θέση / Position</th>
      <th>Ονοματεπώνυμο / Name</th>
      <th>Σύλλογος / Club</th>
      <th>Βαθμοί / Points</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>ΧΑΡΑΛΑΜΠΟΥΣ Νικόλας</td>
      <td>Σ.Ξ. Λευκωσίας</td>
      <td>1.234,50</td>
    </tr>
  </tbody>
</table>
"""


FIXTURE_EMPTY_HTML = """
<table>
  <tr><th>Θέση</th><th>Ονοματεπώνυμο</th><th>Σύλλογος</th><th>Βαθμοί</th></tr>
</table>
"""


FIXTURE_NO_TABLE = """
<html><body><p>Δεν υπάρχουν διαθέσιμα στοιχεία κατάταξης.</p></body></html>
"""


FIXTURE_NON_STANDARD_ROWS = """
<table>
  <tr><th>Position</th><th>Name</th><th>Club</th><th>Points</th></tr>
  <tr><td>DNS</td><td>Missing Athlete</td><td>Club A</td><td>0</td></tr>
  <tr><td>2</td><td>DQ</td><td>Club B</td><td>0</td></tr>
  <tr><td>Σύνολο</td><td>2 athletes</td><td></td><td>0</td></tr>
  <tr><td>3</td><td>ΑΝΤΩΝΙΟΥ Σοφία</td><td>Limassol Fencing Club</td><td>44,50</td></tr>
</table>
"""


def test_parse_rankings_table_returns_pdf_rows_and_preserves_native_names():
    from scrape_fed_cyp import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_PDF_TEXT)

    assert rows[:2] == [
        {
            "rank": 1,
            "name": "ΓΕΩΡΓΙΟΥ Ανδρέας",
            "club": "Λευκωσία",
            "points": 125.5,
        },
        {
            "rank": 2,
            "name": "CHRISTODOULOU Marios",
            "club": "Limassol Fencing Club",
            "points": 98.25,
        },
    ]
    assert rows[2]["name"] == "ΠΑΠΑΔΟΠΟΥΛΟΥ Μαρία"


def test_parse_rankings_table_accepts_bilingual_headers_and_decimal_comma():
    from scrape_fed_cyp import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_BILINGUAL_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "ΧΑΡΑΛΑΜΠΟΥΣ Νικόλας",
            "club": "Σ.Ξ. Λευκωσίας",
            "points": 1234.5,
        }
    ]


def test_parse_rankings_table_empty_html_returns_empty_list():
    from scrape_fed_cyp import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("   \n\t") == []
    assert parse_rankings_table(FIXTURE_EMPTY_HTML) == []


def test_parse_rankings_table_no_table_or_no_data_returns_empty_list():
    from scrape_fed_cyp import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_TABLE) == []
    assert parse_rankings_table("Δεν υπάρχουν διαθέσιμα στοιχεία κατάταξης.") == []


def test_parse_rankings_table_skips_malformed_dns_dq_and_summary_rows():
    from scrape_fed_cyp import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert rows == [
        {
            "rank": 3,
            "name": "ΑΝΤΩΝΙΟΥ Σοφία",
            "club": "Limassol Fencing Club",
            "points": 44.5,
        }
    ]


def test_extract_combo_section_selects_requested_public_combo():
    import scrape_fed_cyp

    section = scrape_fed_cyp.extract_combo_section(FIXTURE_PDF_TEXT, "Epee", "Women", "Junior")

    assert section is not None
    rows = scrape_fed_cyp.parse_rankings_table(section)
    assert [row["name"] for row in rows] == ["ΠΑΠΑΔΟΠΟΥΛΟΥ Μαρία", "IOANNOU Eleni"]


def test_fetch_rankings_page_discovers_public_pdf_and_extracts_requested_combo(monkeypatch):
    import scrape_fed_cyp

    calls = []

    class HtmlResponse:
        status_code = 200
        url = "https://fencing.org.cy/rankings/"
        text = '<a href="/wp-content/uploads/Rankings-290126.pdf">Πίνακες Κατάταξης</a>'
        content = text.encode("utf-8")
        headers = {"content-type": "text/html; charset=UTF-8"}

    class PdfResponse:
        status_code = 200
        url = "https://fencing.org.cy/wp-content/uploads/Rankings-290126.pdf"
        text = ""
        content = b"%PDF"
        headers = {"content-type": "application/pdf"}

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return HtmlResponse() if url.endswith("/rankings/") else PdfResponse()

    monkeypatch.setattr(scrape_fed_cyp, "_ranking_text_cache", None)
    monkeypatch.setattr(scrape_fed_cyp, "federation_request", fake_request)
    monkeypatch.setattr(scrape_fed_cyp, "_extract_pdf_text", lambda content: FIXTURE_PDF_TEXT)

    text = scrape_fed_cyp.fetch_rankings_page("Epee", "Women", "Junior")

    assert text is not None
    assert "EPEE JUNIOR WOMEN" in text
    assert calls[0][1] == "https://fencing.org.cy/rankings/"
    assert calls[1][1] == "https://fencing.org.cy/wp-content/uploads/Rankings-290126.pdf"
    assert calls[0][2]["headers"] == scrape_fed_cyp.HEADERS


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_cyp

    class Response:
        status_code = 404
        url = "https://fencing.org.cy/rankings/"
        text = "not found"
        content = b"not found"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_cyp, "_ranking_text_cache", None)
    monkeypatch.setattr(scrape_fed_cyp, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_cyp.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_on_network_error(monkeypatch):
    import scrape_fed_cyp

    def raise_error(*args, **kwargs):
        raise requests.RequestException("network down")

    monkeypatch.setattr(scrape_fed_cyp, "_ranking_text_cache", None)
    monkeypatch.setattr(scrape_fed_cyp, "federation_request", raise_error)

    assert scrape_fed_cyp.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_login_only_page(monkeypatch, capsys):
    import scrape_fed_cyp

    class Response:
        status_code = 200
        url = "https://fencing.org.cy/rankings/"
        text = '<form><input type="password" name="pwd"></form><p>Login required</p>'
        content = text.encode("utf-8")
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_cyp, "_ranking_text_cache", None)
    monkeypatch.setattr(scrape_fed_cyp, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_cyp.fetch_rankings_page("Foil", "Women", "Junior") is None
    assert "login-only" in capsys.readouterr().out.lower()


def test_fetch_rankings_page_returns_none_for_js_only_page_without_api(monkeypatch, capsys):
    import scrape_fed_cyp

    class Response:
        status_code = 200
        url = "https://fencing.org.cy/rankings/"
        text = '<div id="app"></div><script src="/assets/rankings.js"></script>'
        content = text.encode("utf-8")
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_cyp, "_ranking_text_cache", None)
    monkeypatch.setattr(scrape_fed_cyp, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_cyp.fetch_rankings_page("Sabre", "Women", "Senior") is None
    assert "js-only" in capsys.readouterr().out.lower()


def test_fetch_rankings_page_returns_none_when_requested_combo_missing(monkeypatch, capsys):
    import scrape_fed_cyp

    monkeypatch.setattr(scrape_fed_cyp, "_ranking_text_cache", FIXTURE_PDF_TEXT)

    assert scrape_fed_cyp.fetch_rankings_page("Foil", "Men", "Senior") is None
    assert "no public ranking section" in capsys.readouterr().out.lower()


def test_ranking_combos_cover_twelve_standard_senior_and_junior_combos():
    from scrape_fed_cyp import RANKING_COMBOS

    expected = {
        (weapon, gender, category)
        for category in ("Senior", "Junior")
        for weapon in ("Foil", "Epee", "Sabre")
        for gender in ("Men", "Women")
    }

    assert set(RANKING_COMBOS) == expected


def test_current_season_uses_july_boundary(monkeypatch):
    import scrape_fed_cyp

    class JuneDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 30, tzinfo=timezone.utc)

    class JulyDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(scrape_fed_cyp, "datetime", JuneDateTime)
    assert scrape_fed_cyp.current_season() == "2025-2026"

    monkeypatch.setattr(scrape_fed_cyp, "datetime", JulyDateTime)
    assert scrape_fed_cyp.current_season() == "2026-2027"

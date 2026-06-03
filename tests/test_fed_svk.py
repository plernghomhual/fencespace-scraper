"""
Tests for scrape_fed_svk.py.

Fixtures mirror the public Slovak federation standings page probed at:
  https://www.slovak-fencing.sk/site/slovensky-pohar-aktual/

Source format:
  - Public WordPress HTML index page.
  - Direct application/pdf standings links under /Source/SSZ/Slov-pohar/.
  - Extracted PDF text headers include:
      Č. Meno r. Klub ... Spolu
      # MENO ROČNÍK KLUB BODY
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


PDF_SPOLU_TEXT = """
Slovenský pohár 2025-2026 v šerme kordom seniorov
17.5.2026
A B C D E F G H
Č. Meno r. Klub 8x 68x 38x 48x 75x 29x 11x x Spolu
1 GRUNERT Adrian 07 AŠ 272 600 352 1224
2 DUDUC Alex Vladimír 97 BŠK 208 152 150 406 220 1136
3 JOHANIDES Lukas Jakub 99 BŠK 256 136 304 300 996
13 YARHYCH Serhiy BŠK 88 88
"""


PDF_BODY_TEXT = """
Slovenský pohár 2024-2025 v šerme kordom SENIORIEK
# MENO ROČNÍK KLUB BODY
x5 x70 x24 x20 x25 x56 x110 x6,5 x16
1. HUBINSKÁ Viviana 2007 AŠ 754 130 208 416 0
2. CANTUCCI Gaia 2001 STU 512 512 1
3. TULEJOVÁ Zuzana 2008 BŠK 475 160 91 224 2
"""


SLOVAK_HTML_TABLE = """
<html>
  <body>
    <table>
      <thead>
        <tr><th>Poradie</th><th>Meno</th><th>Klub</th><th>Body</th></tr>
      </thead>
      <tbody>
        <tr><td>1.</td><td>ŽILINSKÁ Ária</td><td>ŠK Slávia</td><td>1 234,5</td></tr>
        <tr><td>2</td><td>Марія Černá</td><td>КШ Bratislava</td><td>98,25</td></tr>
      </tbody>
    </table>
  </body>
</html>
"""


SKIP_ROWS_TEXT = """
Slovenský pohár 2025-2026 v šerme kordom juniorov
Č. Meno r. Klub 9x 13x Spolu
DNS NEDOŠIEL Fencer AŠ 0 0
DQ VYLÚČENÝ Fencer BŠK 0 0
Súčet pretekárov 20
abc malformed row
0 ZERO Rank AŠ 0
1 REMIÁŠOVÁ Linda 2010 AŠ 100 494 100 694
"""


NO_DATA_HTML = """
<html><body><h1>Slovenský pohár aktuál</h1><p>Žiadne údaje.</p></body></html>
"""


INDEX_FIXTURE_HTML = """
<html><body>
  <a href="https://slovak-fencing.sk/Source/SSZ/slov-pohar/SP2024-25/f-juniori-24.pdf">Fleuret juniori</a>
  <a href="https://www.slovak-fencing.sk/Source/SSZ/Slov-pohar/SP2024-25/f-juniorky-24.pdf">Fleuret juniorky</a>
  <a href="https://www.slovak-fencing.sk/Source/SSZ/Slov-pohar/SP2025-26/k-juniori-25.pdf">Kord juniori</a>
  <a href="https://www.slovak-fencing.sk/Source/SSZ/Slov-pohar/SP2025-26/k-juniorky-25.pdf">Kord juniorky</a>
  <a href="https://slovak-fencing.sk/Source/SSZ/slov-pohar/SP2024-25/f-seniori-24.pdf">Fleuret seniori</a>
  <a href="https://www.slovak-fencing.sk/Source/SSZ/Slov-pohar/SP2024-25/f-seniorky-24.pdf">Fleuret seniorky</a>
  <a href="https://www.slovak-fencing.sk/Source/SSZ/Slov-pohar/SP2025-26/k-seniori-25.pdf">Kord seniori</a>
  <a href="https://www.slovak-fencing.sk/Source/SSZ/Slov-pohar/SP2024-25/k-seniorky-24.pdf">Kord seniorky</a>
</body></html>
"""


class Response:
    def __init__(self, status_code=200, text="", content=b"", headers=None, url="https://example.test/ranking.pdf"):
        self.status_code = status_code
        self.text = text
        self.content = content
        self.headers = headers or {}
        self.url = url


def test_parse_pdf_spolu_text_returns_valid_rows():
    from scrape_fed_svk import parse_rankings_table

    rows = parse_rankings_table(PDF_SPOLU_TEXT)

    assert rows[:3] == [
        {"rank": 1, "name": "GRUNERT Adrian", "club": "AŠ", "points": 1224.0},
        {"rank": 2, "name": "DUDUC Alex Vladimír", "club": "BŠK", "points": 1136.0},
        {"rank": 3, "name": "JOHANIDES Lukas Jakub", "club": "BŠK", "points": 996.0},
    ]
    assert rows[3] == {"rank": 13, "name": "YARHYCH Serhiy", "club": "BŠK", "points": 88.0}


def test_parse_pdf_body_shape_uses_body_column_not_trailing_event_number():
    from scrape_fed_svk import parse_rankings_table

    rows = parse_rankings_table(PDF_BODY_TEXT)

    assert rows == [
        {"rank": 1, "name": "HUBINSKÁ Viviana", "club": "AŠ", "points": 754.0},
        {"rank": 2, "name": "CANTUCCI Gaia", "club": "STU", "points": 512.0},
        {"rank": 3, "name": "TULEJOVÁ Zuzana", "club": "BŠK", "points": 475.0},
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_svk import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_svk import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_non_numeric_rows():
    from scrape_fed_svk import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_TEXT)

    assert rows == [
        {"rank": 1, "name": "REMIÁŠOVÁ Linda", "club": "AŠ", "points": 694.0}
    ]


def test_parse_slovak_headers_preserves_native_names_and_decimal_commas():
    from scrape_fed_svk import parse_rankings_table

    rows = parse_rankings_table(SLOVAK_HTML_TABLE)

    assert rows == [
        {"rank": 1, "name": "ŽILINSKÁ Ária", "club": "ŠK Slávia", "points": 1234.5},
        {"rank": 2, "name": "Марія Černá", "club": "КШ Bratislava", "points": 98.25},
    ]


def test_extract_ranking_links_maps_public_slovak_labels():
    from scrape_fed_svk import _extract_ranking_links

    links = _extract_ranking_links(INDEX_FIXTURE_HTML, base_url="https://www.slovak-fencing.sk/site/slovensky-pohar-aktual/")

    assert links[("Foil", "Men", "Senior")].endswith("/f-seniori-24.pdf")
    assert links[("Foil", "Women", "Junior")].endswith("/f-juniorky-24.pdf")
    assert links[("Epee", "Men", "Senior")].endswith("/k-seniori-25.pdf")
    assert links[("Epee", "Women", "Junior")].endswith("/k-juniorky-25.pdf")
    assert len(links) == 8


def test_fetch_rankings_page_returns_none_for_missing_combo(monkeypatch):
    import scrape_fed_svk

    monkeypatch.setattr(scrape_fed_svk, "discover_ranking_urls", lambda: {})

    assert scrape_fed_svk.fetch_rankings_page("Sabre", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_404_and_blocked(monkeypatch):
    import scrape_fed_svk

    monkeypatch.setattr(
        scrape_fed_svk,
        "discover_ranking_urls",
        lambda: {("Epee", "Men", "Senior"): "https://example.test/ranking.pdf"},
    )

    monkeypatch.setattr(
        scrape_fed_svk,
        "federation_request",
        lambda *args, **kwargs: Response(status_code=404, headers={"content-type": "text/html"}),
    )
    assert scrape_fed_svk.fetch_rankings_page("Epee", "Men", "Senior") is None

    monkeypatch.setattr(
        scrape_fed_svk,
        "federation_request",
        lambda *args, **kwargs: Response(status_code=403, headers={"content-type": "text/html"}),
    )
    assert scrape_fed_svk.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_rejects_login_only_and_js_only_pages(monkeypatch):
    import scrape_fed_svk

    monkeypatch.setattr(
        scrape_fed_svk,
        "discover_ranking_urls",
        lambda: {("Epee", "Women", "Senior"): "https://example.test/ranking"},
    )

    monkeypatch.setattr(
        scrape_fed_svk,
        "federation_request",
        lambda *args, **kwargs: Response(
            status_code=200,
            text='<html><form id="login"><input type="password"></form></html>',
            content=b'<html><form id="login"><input type="password"></form></html>',
            headers={"content-type": "text/html"},
        ),
    )
    assert scrape_fed_svk.fetch_rankings_page("Epee", "Women", "Senior") is None

    monkeypatch.setattr(
        scrape_fed_svk,
        "federation_request",
        lambda *args, **kwargs: Response(
            status_code=200,
            text='<html><div id="app"></div><script src="/rankings.js"></script></html>',
            content=b'<html><div id="app"></div><script src="/rankings.js"></script></html>',
            headers={"content-type": "text/html"},
        ),
    )
    assert scrape_fed_svk.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_extracts_pdf_text(monkeypatch):
    import scrape_fed_svk

    monkeypatch.setattr(
        scrape_fed_svk,
        "discover_ranking_urls",
        lambda: {("Epee", "Men", "Junior"): "https://example.test/ranking.pdf"},
    )
    monkeypatch.setattr(
        scrape_fed_svk,
        "federation_request",
        lambda *args, **kwargs: Response(
            status_code=200,
            content=b"%PDF fake",
            headers={"content-type": "application/pdf"},
        ),
    )
    monkeypatch.setattr(scrape_fed_svk, "_extract_pdf_text", lambda content: "extracted pdf text")

    assert scrape_fed_svk.fetch_rankings_page("Epee", "Men", "Junior") == "extracted pdf text"

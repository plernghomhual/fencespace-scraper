"""
Tests for scrape_fed_tur.py.

Fixtures reflect the public Turkey ranking source probed from:
  https://www.eskrim.org.tr/klasmanlar-20.html

Probe evidence:
  - `trfencing.gov.tr` did not resolve from the local sandbox probe.
  - Current public host is `https://www.eskrim.org.tr`.
  - Ranking index is GET text/html.
  - Detail links are public PDF files under `/resim/extra/Klasmanlar/...`.
  - Current index exposes all 12 Senior/Junior Foil/Epee/Sabre Men/Women combos.

PDF text columns:
  S.NO | SOYAD | AD | KULÜBÜ | DOĞUM TARİH | event point columns | TOPLAM
"""

import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


REALISTIC_PDF_TEXT = """
GENÇLER ERKEK EPE KLASMANI
S.NO SOYAD AD KULÜBÜ DOĞUM TARİH P
1 EROLÇEVİK DORUK EGO S.K. 15.09.2008 113 11,3 1 16 27,3
2 CEVİZİÇİ MEHMET ILGAR ÇANKAYA ESK SK 19.05.2009 45,5 4,55 2 13 17,55
7 MACİT URAS ESKİŞEHİR DEMİRSPOR
KULÜBÜ
12.03.2007 37,5 3,75 8 7 10,75
"""


TURKISH_HTML_TABLE = """
<html>
<body>
  <table>
    <thead>
      <tr><th>Sira</th><th>Ad Soyad</th><th>Kulup</th><th>Puan</th></tr>
      <tr><th>Sıra</th><th>İsim / Ad Soyad</th><th>Kulüp</th><th>Puan</th></tr>
    </thead>
    <tbody>
      <tr><td>1.</td><td>İNAL Sofía</td><td>İstanbul Eskrim S.K.</td><td>1.234,50</td></tr>
      <tr><td>2</td><td>YILMAZ Ada Светлана</td><td>Çankaya Eskrim SK</td><td>42,75</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


NO_DATA_HTML = """
<html><body><h1>Klasmanlar</h1><p>Bu kategori icin veri bulunamadi.</p></body></html>
"""


SKIP_ROWS_TEXT = """
BUYUKLER KADIN KILIÇ KLASMANI
Sıra Soyad Ad Kulübü Doğum Tarih Toplam
DNS GELMEYEN SPORCU TEST SK 01.01.2000 0
DQ DİSKALİFİYE SPORCU TEST SK 01.01.2000 0
Toplam 2 sporcu
0 SIFIR SIRA TEST SK 01.01.2000 0
A BAŞLIK SATIRI
3 ÖZÇETİN İREM ANKARA ZONE ESK. S.K. 22.12.2008 47,5 4,75 9 4 8,75
malformed row without numeric rank
"""


PIPE_DELIMITED_PDF_TABLE = """
S.NO | SOYAD | AD | KULUBU | DOGUM TARIH | Y.ICI | TOPLAM
1 | YAMAN | FURKAN | EGO S.K. | 17.04.2007 | 18,8 | 34,8
2 | KUMUK | POYRAZ | ULUDAG ESKRIM S.K. | 17.06.2008 | 9,8 | 22,8
"""


INDEX_FIXTURE_HTML = """
<table>
  <tr><th>Kategori/Cinsiyet</th><th>Erkek</th><th>Kiz</th></tr>
  <tr><td>Gencler</td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/G_E_E.pdf">Epe</a></td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/G_K_E.pdf">Epe</a></td></tr>
  <tr><td>Gencler</td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/G_E_F.pdf">Flore</a></td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/G_K_F.pdf">Flore</a></td></tr>
  <tr><td>Gencler</td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/G_E_K.pdf">Kilic</a></td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/G_K_K.pdf">Kilic</a></td></tr>
  <tr><td>Buyukler</td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/B_E_E.pdf">Epe</a></td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/B_K_E.pdf">Epe</a></td></tr>
  <tr><td>Buyukler</td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/B_E_F.pdf">Flore</a></td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/B_K_F.pdf">Flore</a></td></tr>
  <tr><td>Buyukler</td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/B_E_K.pdf">Kilic</a></td><td><a href="/resim/extra/Klasmanlar/25_26/mayis/12/B_K_K.pdf">Kilic</a></td></tr>
</table>
"""


def test_parse_tur_pdf_text_returns_valid_rows_and_handles_wrapped_club():
    from scrape_fed_tur import parse_rankings_table

    rows = parse_rankings_table(REALISTIC_PDF_TEXT)

    assert rows[:3] == [
        {
            "rank": 1,
            "name": "EROLÇEVİK DORUK",
            "club": "EGO S.K.",
            "points": 27.3,
        },
        {
            "rank": 2,
            "name": "CEVİZİÇİ MEHMET ILGAR",
            "club": "ÇANKAYA ESK SK",
            "points": 17.55,
        },
        {
            "rank": 7,
            "name": "MACİT URAS",
            "club": "ESKİŞEHİR DEMİRSPOR KULÜBÜ",
            "points": 10.75,
        },
    ]


def test_parse_pipe_delimited_pdf_table_uses_surname_and_given_name_columns():
    from scrape_fed_tur import parse_rankings_table

    rows = parse_rankings_table(PIPE_DELIMITED_PDF_TABLE)

    assert rows == [
        {"rank": 1, "name": "YAMAN FURKAN", "club": "EGO S.K.", "points": 34.8},
        {
            "rank": 2,
            "name": "KUMUK POYRAZ",
            "club": "ULUDAG ESKRIM S.K.",
            "points": 22.8,
        },
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_tur import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_tur import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_malformed_non_numeric_dns_dq_summary_and_zero_rank_rows():
    from scrape_fed_tur import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_TEXT)

    assert rows == [
        {
            "rank": 3,
            "name": "ÖZÇETİN İREM",
            "club": "ANKARA ZONE ESK. S.K.",
            "points": 8.75,
        }
    ]


def test_parse_turkish_headers_preserves_names_and_normalizes_decimal_commas():
    from scrape_fed_tur import parse_rankings_table

    rows = parse_rankings_table(TURKISH_HTML_TABLE)

    assert rows[0] == {
        "rank": 1,
        "name": "İNAL Sofía",
        "club": "İstanbul Eskrim S.K.",
        "points": 1234.5,
    }
    assert rows[1]["name"] == "YILMAZ Ada Светлана"
    assert rows[1]["points"] == 42.75


def test_extract_ranking_links_maps_all_standard_public_combos():
    from scrape_fed_tur import _extract_ranking_links

    links = _extract_ranking_links(
        INDEX_FIXTURE_HTML,
        base_url="https://www.eskrim.org.tr/klasmanlar-20.html",
    )

    assert len(links) == 12
    assert links[("Epee", "Men", "Junior")].endswith("/G_E_E.pdf")
    assert links[("Foil", "Women", "Junior")].endswith("/G_K_F.pdf")
    assert links[("Sabre", "Men", "Senior")].endswith("/B_E_K.pdf")
    assert links[("Epee", "Women", "Senior")].endswith("/B_K_E.pdf")


def test_fetch_rankings_page_returns_extracted_pdf_text(monkeypatch):
    import scrape_fed_tur

    class Response:
        status_code = 200
        content = b"%PDF fake"
        text = ""
        headers = {"content-type": "application/pdf"}
        url = "https://www.eskrim.org.tr/ranking.pdf"

    calls = []

    monkeypatch.setattr(
        scrape_fed_tur,
        "_discover_ranking_links",
        lambda: {("Epee", "Men", "Junior"): "https://www.eskrim.org.tr/ranking.pdf"},
    )
    monkeypatch.setattr(scrape_fed_tur, "_extract_pdf_text", lambda content: "pdf text")

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response()

    monkeypatch.setattr(scrape_fed_tur, "federation_request", fake_request)

    assert scrape_fed_tur.fetch_rankings_page("Epee", "Men", "Junior") == "pdf text"
    assert calls[0][0] == "get"
    assert calls[0][1] == "https://www.eskrim.org.tr/ranking.pdf"
    assert calls[0][2]["headers"] == scrape_fed_tur.HEADERS


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_tur

    class Response:
        status_code = 404
        content = b""
        text = "not found"
        headers = {"content-type": "text/html"}
        url = "https://www.eskrim.org.tr/missing.pdf"

    monkeypatch.setattr(
        scrape_fed_tur,
        "_discover_ranking_links",
        lambda: {("Foil", "Men", "Senior"): "https://www.eskrim.org.tr/missing.pdf"},
    )
    monkeypatch.setattr(scrape_fed_tur, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_tur.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_network_error(monkeypatch):
    import scrape_fed_tur

    monkeypatch.setattr(
        scrape_fed_tur,
        "_discover_ranking_links",
        lambda: {("Foil", "Women", "Senior"): "https://www.eskrim.org.tr/ranking.pdf"},
    )

    def fail_request(*args, **kwargs):
        raise requests.RequestException("network blocked")

    monkeypatch.setattr(scrape_fed_tur, "federation_request", fail_request)

    assert scrape_fed_tur.fetch_rankings_page("Foil", "Women", "Senior") is None


@pytest.mark.parametrize(
    "content",
    [
        "<html><body>Access Denied</body></html>",
        "<html><body>Giris yapmaniz gerekmektedir</body></html>",
        "<html><body>Please enable JavaScript to view this page</body></html>",
    ],
)
def test_fetch_rankings_page_returns_none_for_blocked_login_or_js_only_pages(monkeypatch, content):
    import scrape_fed_tur

    class Response:
        def __init__(self, body):
            self.status_code = 200
            self.content = body.encode()
            self.text = body
            self.headers = {"content-type": "text/html"}
            self.url = "https://www.eskrim.org.tr/protected"

    monkeypatch.setattr(
        scrape_fed_tur,
        "_discover_ranking_links",
        lambda: {("Sabre", "Women", "Senior"): "https://www.eskrim.org.tr/protected"},
    )
    monkeypatch.setattr(scrape_fed_tur, "federation_request", lambda *args, **kwargs: Response(content))

    assert scrape_fed_tur.fetch_rankings_page("Sabre", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_for_missing_combo(monkeypatch):
    import scrape_fed_tur

    monkeypatch.setattr(scrape_fed_tur, "_discover_ranking_links", lambda: {})

    assert scrape_fed_tur.fetch_rankings_page("Sabre", "Men", "Junior") is None


def test_ranking_combos_attempt_all_standard_senior_and_junior_events():
    from scrape_fed_tur import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert set(RANKING_COMBOS) == {
        (weapon, gender, category)
        for category in ("Senior", "Junior")
        for weapon in ("Foil", "Epee", "Sabre")
        for gender in ("Men", "Women")
    }

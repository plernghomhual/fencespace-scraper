"""
Tests for scrape_fed_ukr.py.

Fixtures are trimmed from the public NFFU rankings page:
  https://www.nffu.org.ua/рейтинги/

The live pages link to PDF ranking files under /wp-content/uploads/2026/05/.
pdfplumber text extraction keeps each fencer row as a text line with:
  rank, П. І. П., birth year, city, club/organization, total points, event columns.
"""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NFFU_PDF_TEXT = """
П. І. П. МІСЦЕ ОЧКИ МІСЦЕ ОЧКИ РАЗОМ
1 МИРОНЮК Дарія 2001 Київ ЗСУ ДШВСМ 160,00 2 14 - 0 1 16 160,00
2 ПОЛОЗЮК Аліна 2002 Миколаїв МСДОСШОР Динамо 115,00 1 16 - 0 2 14 115,00
5 МАКІЄНКО Євген 1991 Київ ЦСК ЗСУ КМШВСМ 66,50 - 0 - 0 2 14 66,50
10ГОРБАЧУК Єлизавета 2009 Львів ЛАФ Д-Атлет ЛФКС 34,50 17 3 - 0 76 0 34,50
"""


UKRAINIAN_HTML_TABLE = """
<!doctype html>
<html lang="uk">
<body>
  <table>
    <thead>
      <tr><th>Місце</th><th>Ім'я</th><th>Клуб</th><th>Очки</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>ГОЛОВКІНА Софія</td><td>КДЮСШ-2 Черкаси</td><td>32,50</td></tr>
      <tr><td>2</td><td>ЯГОДКА Андрій</td><td>ЗСУ ШВСМ Олімпієць</td><td>104.75</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


NO_DATA_HTML = """
<!doctype html>
<html lang="uk">
<body><p>Рейтинг відсутній. Дані не опубліковано.</p></body>
</html>
"""


NON_STANDARD_ROWS_TEXT = """
П. І. П. МІСЦЕ ОЧКИ РАЗОМ
РАЗОМ по команді 4 спортсмени
DNS ІВАНЕНКО Тест 2005 Київ Клуб 0
2 ПЕТРЕНКО Тест 2005 Київ Клуб DQ 0
3 СИДОРЕНКО Ігор 2004 Київ Армієць 12,00 1 12 12,00
"""


def test_parse_nffu_pdf_text_returns_rows_with_ukrainian_names():
    from scrape_fed_ukr import parse_rankings_table

    rows = parse_rankings_table(NFFU_PDF_TEXT)

    assert len(rows) == 4
    assert rows[0] == {
        "rank": 1,
        "name": "МИРОНЮК Дарія",
        "club": "ЗСУ ДШВСМ",
        "points": 160.0,
    }
    assert rows[2]["name"] == "МАКІЄНКО Євген"
    assert rows[2]["club"] == "ЦСК ЗСУ КМШВСМ"
    assert rows[2]["points"] == 66.5


def test_parse_nffu_pdf_text_handles_rank_without_space():
    from scrape_fed_ukr import parse_rankings_table

    rows = parse_rankings_table(NFFU_PDF_TEXT)

    assert rows[3]["rank"] == 10
    assert rows[3]["name"] == "ГОРБАЧУК Єлизавета"
    assert rows[3]["club"] == "ЛАФ Д-Атлет ЛФКС"
    assert rows[3]["points"] == 34.5


def test_parse_ukrainian_html_headers_preserves_native_script():
    from scrape_fed_ukr import parse_rankings_table

    rows = parse_rankings_table(UKRAINIAN_HTML_TABLE)

    assert rows == [
        {
            "rank": 1,
            "name": "ГОЛОВКІНА Софія",
            "club": "КДЮСШ-2 Черкаси",
            "points": 32.5,
        },
        {
            "rank": 2,
            "name": "ЯГОДКА Андрій",
            "club": "ЗСУ ШВСМ Олімпієць",
            "points": 104.75,
        },
    ]


def test_parse_empty_input_returns_empty_list():
    from scrape_fed_ukr import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("   \n\t") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_ukr import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []
    assert parse_rankings_table("Рейтинг відсутній") == []


def test_parse_skips_dns_dq_and_summary_rows():
    from scrape_fed_ukr import parse_rankings_table

    rows = parse_rankings_table(NON_STANDARD_ROWS_TEXT)

    assert rows == [
        {
            "rank": 3,
            "name": "СИДОРЕНКО Ігор",
            "club": "Армієць",
            "points": 12.0,
        }
    ]


def test_ranking_combos_cover_senior_and_junior_weapon_gender_matrix():
    from scrape_fed_ukr import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert set(RANKING_COMBOS) == {
        ("Foil", "Men", "Senior"),
        ("Foil", "Women", "Senior"),
        ("Epee", "Men", "Senior"),
        ("Epee", "Women", "Senior"),
        ("Sabre", "Men", "Senior"),
        ("Sabre", "Women", "Senior"),
        ("Foil", "Men", "Junior"),
        ("Foil", "Women", "Junior"),
        ("Epee", "Men", "Junior"),
        ("Epee", "Women", "Junior"),
        ("Sabre", "Men", "Junior"),
        ("Sabre", "Women", "Junior"),
    }


def test_request_headers_are_http_safe():
    from scrape_fed_ukr import HEADERS

    for header_name, header_value in HEADERS.items():
        assert header_name
        header_value.encode("latin-1")


def test_fetch_rankings_page_retries_then_extracts_pdf(monkeypatch):
    import scrape_fed_ukr

    calls = []

    class Response:
        status_code = 200
        content = b"%PDF fake"
        text = ""
        headers = {"content-type": "application/pdf"}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) < 3:
            raise requests.Timeout("slow source")
        return Response()

    monkeypatch.setattr(scrape_fed_ukr.requests, "get", fake_get)
    monkeypatch.setattr(scrape_fed_ukr.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scrape_fed_ukr, "_extract_pdf_text", lambda content: "PDF TEXT")

    content = scrape_fed_ukr.fetch_rankings_page("Foil", "Men", "Senior")

    assert content == "PDF TEXT"
    assert len(calls) == 3
    assert calls[0][0].endswith("рапіра-чол-дорослі-2.pdf")


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_ukr

    class Response:
        status_code = 404
        content = b"not found"
        text = "not found"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_ukr.requests, "get", lambda url, **kwargs: Response())

    assert scrape_fed_ukr.fetch_rankings_page("Foil", "Men", "Senior") is None

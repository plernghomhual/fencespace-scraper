from __future__ import annotations

import pytest

SERBIAN_HTML_FIXTURE = """
<html>
  <body>
    <h2>Seniori - Mač - muškarci</h2>
    <table>
      <thead>
        <tr>
          <th>Пласман</th>
          <th>Име и презиме</th>
          <th>Клуб</th>
          <th>Бодови</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>1</td><td>Јован Јовановић</td><td>МК Црвена звезда</td><td>32,5</td></tr>
        <tr><td>2</td><td>Aleksandar Nikolić</td><td>MK Partizan</td><td>26</td></tr>
      </tbody>
    </table>
  </body>
</html>
"""


SERBIAN_TEXT_FIXTURE = """
SHEET: Seniorke - Floret - žene
Pozicija | Ime i prezime | Klub | Bodovi
1 | Milica Petrović | MK Omladinac | 44,75
2 | Ана Петровић | МК Нови Сад | 20
"""


NO_TABLE_HTML = """
<html>
  <body>
    <h1>Rang liste</h1>
    <p>Rang liste Mačevalačkog Saveza Srbije u svim kategorijama i svim disciplinama.</p>
    <a href="/download/rang-liste-mss/">PREUZMI</a>
  </body>
</html>
"""


SKIPPED_ROWS_HTML = """
<table>
  <tr><th>Plasman</th><th>Ime i prezime</th><th>Klub</th><th>Bodovi</th></tr>
  <tr><td>DNS</td><td>Nije startovao</td><td>MK Test</td><td>0</td></tr>
  <tr><td>DQ</td><td>Diskvalifikovan</td><td>MK Test</td><td>0</td></tr>
  <tr><td>Ukupno</td><td>3 takmičara</td><td></td><td>58</td></tr>
  <tr><td>abc</td><td>Nevažeći plasman</td><td>MK Test</td><td>12</td></tr>
  <tr><td>3</td><td>Marko Đorđević</td><td>MK Spartak</td><td>12,5</td></tr>
</table>
"""


COMBO_TEXT = """
SHEET: Seniori - Mač - muškarci
Plasman | Ime i prezime | Klub | Bodovi
1 | Milan Ilić | MK Crvena zvezda | 32

SHEET: Juniori - Sablja - žene
Plasman | Ime i prezime | Klub | Bodovi
1 | Софија Илић | МК Партизан | 18
"""


EXPLICIT_GENDER_COMBO_TEXT = """
SHEET: Seniori - Mač - žene
Plasman | Ime i prezime | Klub | Bodovi
1 | Милица Илић | МК Нови Сад | 21

SHEET: Seniori - Mač - muškarci
Plasman | Ime i prezime | Klub | Bodovi
1 | Milan Ilić | MK Crvena zvezda | 32
"""


def test_ranking_combos_attempt_all_twelve_standard_combos():
    import scrape_fed_srb

    assert len(scrape_fed_srb.RANKING_COMBOS) == 12
    assert set(scrape_fed_srb.RANKING_COMBOS) == {
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


def test_parse_rankings_table_handles_cyrillic_headers_names_and_decimal_commas():
    from scrape_fed_srb import parse_rankings_table

    rows = parse_rankings_table(SERBIAN_HTML_FIXTURE)

    assert rows == [
        {
            "rank": 1,
            "name": "Јован Јовановић",
            "club": "МК Црвена звезда",
            "points": 32.5,
        },
        {
            "rank": 2,
            "name": "Aleksandar Nikolić",
            "club": "MK Partizan",
            "points": 26.0,
        },
    ]


def test_parse_rankings_table_handles_latin_headers_and_preserves_native_script_names():
    from scrape_fed_srb import parse_rankings_table

    rows = parse_rankings_table(SERBIAN_TEXT_FIXTURE)

    assert rows[0] == {
        "rank": 1,
        "name": "Milica Petrović",
        "club": "MK Omladinac",
        "points": 44.75,
    }
    assert rows[1]["name"] == "Ана Петровић"
    assert rows[1]["club"] == "МК Нови Сад"


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_srb import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_srb import parse_rankings_table

    assert parse_rankings_table(NO_TABLE_HTML) == []


def test_parse_skips_malformed_non_numeric_dns_dq_and_summary_rows():
    from scrape_fed_srb import parse_rankings_table

    rows = parse_rankings_table(SKIPPED_ROWS_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "Marko Đorđević",
            "club": "MK Spartak",
            "points": 12.5,
        }
    ]


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_srb

    class Response:
        status_code = 404
        text = "not found"
        content = b"not found"
        url = "https://www.mss.org.rs/rang-liste/missing"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_srb, "_RANKING_TEXT_CACHE", None)
    monkeypatch.setattr(scrape_fed_srb, "_RANKING_SOURCE_URL", None)
    monkeypatch.setattr(scrape_fed_srb, "_RANKING_FAILURE_REASON", None)
    monkeypatch.setattr(scrape_fed_srb, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_srb.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_blocked_page(monkeypatch):
    import scrape_fed_srb

    class Response:
        status_code = 403
        text = "Forbidden"
        content = b"Forbidden"
        url = "https://www.mss.org.rs/rang-liste/"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_srb, "_RANKING_TEXT_CACHE", None)
    monkeypatch.setattr(scrape_fed_srb, "_RANKING_SOURCE_URL", None)
    monkeypatch.setattr(scrape_fed_srb, "_RANKING_FAILURE_REASON", None)
    monkeypatch.setattr(scrape_fed_srb, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_srb.fetch_rankings_page("Foil", "Men", "Senior") is None


@pytest.mark.parametrize(
    "body",
    [
        "<html><form id='loginform'><input name='pwd'></form></html>",
        "<html><body>Please enable JavaScript to continue.</body></html>",
    ],
)
def test_fetch_rankings_page_returns_none_for_login_only_or_js_only_pages(monkeypatch, body):
    import scrape_fed_srb

    class Response:
        status_code = 200
        text = body
        content = body.encode("utf-8")
        url = "https://www.mss.org.rs/rang-liste/"
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_srb, "_RANKING_TEXT_CACHE", None)
    monkeypatch.setattr(scrape_fed_srb, "_RANKING_SOURCE_URL", None)
    monkeypatch.setattr(scrape_fed_srb, "_RANKING_FAILURE_REASON", None)
    monkeypatch.setattr(scrape_fed_srb, "federation_request", lambda *args, **kwargs: Response())

    assert scrape_fed_srb.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_only_requested_public_combo(monkeypatch):
    import scrape_fed_srb

    monkeypatch.setattr(scrape_fed_srb, "_download_latest_ranking_text", lambda: COMBO_TEXT)

    content = scrape_fed_srb.fetch_rankings_page("Sabre", "Women", "Junior")

    assert content is not None
    assert "Juniori - Sablja - žene" in content
    assert "SHEET: Seniori - Mač - muškarci" not in content


def test_fetch_rankings_page_returns_none_for_missing_combo(monkeypatch):
    import scrape_fed_srb

    monkeypatch.setattr(scrape_fed_srb, "_download_latest_ranking_text", lambda: COMBO_TEXT)

    assert scrape_fed_srb.fetch_rankings_page("Foil", "Women", "Junior") is None


def test_fetch_rankings_page_does_not_confuse_explicit_women_heading_for_men(monkeypatch):
    import scrape_fed_srb

    monkeypatch.setattr(
        scrape_fed_srb, "_download_latest_ranking_text", lambda: EXPLICIT_GENDER_COMBO_TEXT
    )

    content = scrape_fed_srb.fetch_rankings_page("Epee", "Men", "Senior")

    assert content is not None
    assert "muškarci" in content
    assert "žene" not in content

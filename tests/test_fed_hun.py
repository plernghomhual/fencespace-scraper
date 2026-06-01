"""
Tests for scrape_fed_hun.py.

Fixture HTML reflects the probed MVSZ rankings page:
  https://versenyinfo.hunfencing.hu/index.php?p=pRanglista&szezon=15&kor=10&nem=1&fegyver=2&submit=Mutat
  Columns: Rang | Név | Egyesület | Szül. dátum | Korosztály | Σ
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Magyar Vívó Szövetség - Adatbázis</title></head>
<body>
<table>
  <thead>
    <tr>
      <th>Rang</th>
      <th>Név</th>
      <th>Egyesület</th>
      <th>Szül. dátum</th>
      <th>Korosztály</th>
      <th>Σ</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>SZEMES Gergő</td>
      <td>FTC</td>
      <td>2003-02-11</td>
      <td>U23</td>
      <td>5508</td>
    </tr>
    <tr>
      <td>2</td>
      <td>DÓSA Dániel Márk</td>
      <td>Törekvés SE</td>
      <td>1996-01-19</td>
      <td>felnőtt</td>
      <td>4 220,5</td>
    </tr>
    <tr>
      <td>3</td>
      <td>李 Anna</td>
      <td>BHSE</td>
      <td>2005-04-20</td>
      <td>junior</td>
      <td>1200</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


FIXTURE_HELYEZES_HTML = """
<table>
  <tr>
    <th>Helyezés</th><th>Név</th><th>Egyesület</th><th>Pont</th>
  </tr>
  <tr>
    <td>1.</td><td>KÓNYA Csenge</td><td>Debreceni EAC</td><td>3 856,25</td>
  </tr>
</table>
"""


FIXTURE_EMPTY_TABLE = """
<table>
  <thead>
    <tr><th>Rang</th><th>Név</th><th>Egyesület</th><th>Σ</th></tr>
  </thead>
  <tbody></tbody>
</table>
"""


FIXTURE_NO_TABLE = """
<!DOCTYPE html>
<html><body><p>Nincs megjeleníthető ranglista.</p></body></html>
"""


FIXTURE_NON_STANDARD_ROWS = """
<table>
  <tr><th>Rang</th><th>Név</th><th>Egyesület</th><th>Σ</th></tr>
  <tr><td>1</td><td>RABB Krisztián</td><td>Vasas</td><td>8836</td></tr>
  <tr><td>DNS</td><td>NEM INDULT Példa</td><td>Vasas</td><td>0</td></tr>
  <tr><td>DQ</td><td>KIZÁRT Példa</td><td>BHSE</td><td>0</td></tr>
  <tr><td></td><td>Összesen</td><td></td><td>8836</td></tr>
  <tr><td>4</td><td>Visszalépett Példa</td><td>FTC</td><td>0</td></tr>
</table>
"""


def test_parse_hungary_rankings_returns_rows():
    from scrape_fed_hun import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "SZEMES Gergő",
        "club": "FTC",
        "points": 5508.0,
    }
    assert rows[1]["name"] == "DÓSA Dániel Márk"
    assert rows[1]["club"] == "Törekvés SE"
    assert rows[1]["points"] == 4220.5


def test_parse_hungary_rankings_preserves_utf8_names():
    from scrape_fed_hun import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert rows[1]["name"] == "DÓSA Dániel Márk"
    assert rows[2]["name"] == "李 Anna"


def test_parse_hungary_rankings_handles_hungarian_headers():
    from scrape_fed_hun import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HELYEZES_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "KÓNYA Csenge",
            "club": "Debreceni EAC",
            "points": 3856.25,
        }
    ]


def test_parse_hungary_rankings_empty_html():
    from scrape_fed_hun import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_hungary_rankings_no_table_or_no_data():
    from scrape_fed_hun import parse_rankings_table

    assert parse_rankings_table(FIXTURE_EMPTY_TABLE) == []
    assert parse_rankings_table(FIXTURE_NO_TABLE) == []


def test_parse_hungary_rankings_skips_dns_dq_summary_rows():
    from scrape_fed_hun import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert rows == [
        {
            "rank": 1,
            "name": "RABB Krisztián",
            "club": "Vasas",
            "points": 8836.0,
        }
    ]


def test_ranking_combos_attempt_all_standard_combos():
    from scrape_fed_hun import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert ("Foil", "Men", "Senior") in RANKING_COMBOS
    assert ("Sabre", "Women", "Junior") in RANKING_COMBOS


def test_fetch_rankings_page_uses_public_muvsz_params(monkeypatch):
    import scrape_fed_hun

    captured = {}

    class Response:
        status_code = 200
        text = FIXTURE_HTML
        url = "https://versenyinfo.hunfencing.hu/index.php?p=pRanglista"

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs["params"]
        captured["headers"] = kwargs["headers"]
        return Response()

    monkeypatch.setattr(scrape_fed_hun, "current_season", lambda: "2025-2026")
    monkeypatch.setattr(scrape_fed_hun.requests, "get", fake_get)

    html = scrape_fed_hun.fetch_rankings_page("Foil", "Men", "Senior")

    assert html == FIXTURE_HTML
    assert captured["url"] == scrape_fed_hun.BASE_URL
    assert captured["params"] == {
        "p": "pRanglista",
        "szezon": "15",
        "kor": "10",
        "nem": "1",
        "fegyver": "2",
        "submit": "Mutat",
    }
    assert "Mozilla/5.0" in captured["headers"]["User-Agent"]


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_hun

    class Response:
        status_code = 404
        text = "not found"
        url = "https://versenyinfo.hunfencing.hu/missing"

    monkeypatch.setattr(scrape_fed_hun, "current_season", lambda: "2025-2026")
    monkeypatch.setattr(scrape_fed_hun.requests, "get", lambda *args, **kwargs: Response())

    assert scrape_fed_hun.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_current_season_returns_range_string():
    from scrape_fed_hun import current_season

    season = current_season()

    assert len(season) == 9
    assert season[4] == "-"
    start, end = season.split("-")
    assert int(end) == int(start) + 1


def test_main_builds_rows_and_writes_rankings(monkeypatch):
    import scrape_fed_hun

    completed = {}
    written_batches = []

    class FakeRunLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            return self

        def complete(self, **kwargs):
            completed.update(kwargs)

        def error(self, exc_str):
            raise AssertionError(exc_str)

    def fake_write_rankings(rows, source, season):
        written_batches.append((rows, source, season))
        return len(rows)

    monkeypatch.setattr(scrape_fed_hun, "RANKING_COMBOS", [("Foil", "Men", "Senior")])
    monkeypatch.setattr(scrape_fed_hun, "ScraperRunLogger", FakeRunLogger)
    monkeypatch.setattr(scrape_fed_hun, "current_season", lambda: "2025-2026")
    monkeypatch.setattr(scrape_fed_hun, "fetch_rankings_page", lambda *args: FIXTURE_HTML)
    monkeypatch.setattr(scrape_fed_hun, "write_rankings", fake_write_rankings)
    monkeypatch.setattr(scrape_fed_hun.time, "sleep", lambda *_args: None)

    scrape_fed_hun.main()

    assert len(written_batches) == 1
    rows, source, season = written_batches[0]
    assert source == "hun_fencing"
    assert season == "2025-2026"
    assert rows[0]["country"] == "HUN"
    assert rows[0]["weapon"] == "Foil"
    assert rows[0]["gender"] == "Men"
    assert rows[0]["category"] == "Senior"
    assert rows[0]["name"] == "SZEMES Gergő"
    assert completed["written"] == 3
    assert completed["failed"] == 0
    assert completed["skipped"] == 0
    assert completed["metadata"]["parsed"] == 3

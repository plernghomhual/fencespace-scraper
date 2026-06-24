"""
Tests for scrape_fed_aut.py.

Fixture HTML mirrors the public ÖFV season ranking page:
  https://www.oefv.com/de/intern:13/ranglisten-saison-2025-2026

The page is server-rendered HTML behind a POST form:
  search[typ] = Damen|Herren
  search[waffen] = Florett|Degen|Sabel
  search[altersklasse] = Allgemeine Klasse|Junioren|Kadetten

Table columns:
  Rang | OEFV-Lizenznummer | Nachname | Vorname | Club | Punkte | ...
"""
import os
import sys
from datetime import UTC, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_HTML = """<!doctype html>
<html lang="de">
<body>
  <h1>Ranglisten.</h1>
  <h2>Damen Degen Junioren</h2>
  <table class="table table-striped">
    <thead>
      <tr>
        <th>Rang</th>
        <th>OEFV-Lizenznummer</th>
        <th>Nachname</th>
        <th>Vorname</th>
        <th>Club</th>
        <th>Punkte</th>
        <th>1544 Grazer_Messe C+</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>1</td>
        <td>OEFV20091006001</td>
        <td>Böhm</td>
        <td>Stephanie</td>
        <td>FUK</td>
        <td>316</td>
        <td>80</td>
      </tr>
      <tr>
        <td>2</td>
        <td>OEFV20031027002</td>
        <td>Gröss</td>
        <td>Chiara</td>
        <td>SZTK</td>
        <td>207,5</td>
        <td>48</td>
      </tr>
      <tr>
        <td>3</td>
        <td>OEFV20011119001</td>
        <td>Biro</td>
        <td>Alexander</td>
        <td>KAC</td>
        <td>568.25</td>
        <td>100</td>
      </tr>
    </tbody>
  </table>
</body>
</html>"""


FIXTURE_EMPTY_TABLE = """<!doctype html>
<html lang="de">
<body>
  <h2>Herren Säbel Allgemeine Klasse</h2>
  <table>
    <thead>
      <tr>
        <th>Rang</th><th>OEFV-Lizenznummer</th><th>Nachname</th>
        <th>Vorname</th><th>Club</th><th>Punkte</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</body>
</html>"""


FIXTURE_NO_DATA_PAGE = """<!doctype html>
<html lang="de">
<body>
  <h1>Ranglisten.</h1>
  <p>Keine Einträge gefunden.</p>
</body>
</html>"""


FIXTURE_NON_STANDARD_ROWS = """<!doctype html>
<html lang="de">
<body>
  <table>
    <thead>
      <tr>
        <th>Rang</th><th>OEFV-Lizenznummer</th><th>Nachname</th>
        <th>Vorname</th><th>Club</th><th>Punkte</th>
      </tr>
    </thead>
    <tbody>
      <tr><td colspan="6">Stand: 31.05.2026</td></tr>
      <tr><td>DNS</td><td>OEFV000</td><td>Startet</td><td>Nicht</td><td>ABC</td><td>0</td></tr>
      <tr><td>DQ</td><td>OEFV001</td><td>Disqualifiziert</td><td>Test</td><td>ABC</td><td>0</td></tr>
      <tr><td>1</td><td>OEFV20110929001</td><td>Bayer</td><td>Rosa Adelheid</td><td>FUM</td><td>333</td></tr>
      <tr><td>Gesamt</td><td></td><td></td><td></td><td></td><td>333</td></tr>
    </tbody>
  </table>
</body>
</html>"""


def test_parse_oefv_rankings_returns_rows_with_german_headers():
    from scrape_fed_aut import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "Böhm Stephanie",
        "club": "FUK",
        "points": 316.0,
    }


def test_parse_oefv_rankings_preserves_german_characters_and_decimal_commas():
    from scrape_fed_aut import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert rows[1]["name"] == "Gröss Chiara"
    assert rows[1]["points"] == 207.5
    assert rows[2]["name"] == "Biro Alexander"
    assert rows[2]["points"] == 568.25


def test_parse_oefv_rankings_empty_html():
    from scrape_fed_aut import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_oefv_rankings_no_data_page():
    from scrape_fed_aut import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA_PAGE) == []


def test_parse_oefv_rankings_empty_table():
    from scrape_fed_aut import parse_rankings_table

    assert parse_rankings_table(FIXTURE_EMPTY_TABLE) == []


def test_parse_oefv_rankings_skips_dns_dq_and_summary_rows():
    from scrape_fed_aut import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert rows == [
        {
            "rank": 1,
            "name": "Bayer Rosa Adelheid",
            "club": "FUM",
            "points": 333.0,
        }
    ]


def test_ranking_combos_include_public_senior_junior_and_cadet_lists():
    from scrape_fed_aut import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 18
    assert ("Foil", "Men", "Senior") in RANKING_COMBOS
    assert ("Sabre", "Women", "Junior") in RANKING_COMBOS
    assert ("Epee", "Women", "Cadet") in RANKING_COMBOS


def test_current_season_uses_fie_end_year_boundary(monkeypatch):
    import scrape_fed_aut

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 1, tzinfo=UTC)

    monkeypatch.setattr(scrape_fed_aut, "datetime", FixedDateTime)

    assert scrape_fed_aut.current_season() == "2025-2026"

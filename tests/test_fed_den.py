"""
Tests for scrape_fed_den.py.

Fixture HTML mirrors the public Danish rankings linked from:
  https://www.faegtning.dk/staevner/ranglister/
  https://fencing.ophardt.online/en/search/rankings/10

Ophardt ranking pages contain:
  T0: metadata table
  T1: ranking table with Rank | Points | T-P | Name | Nation | Clubs | YOB

Name cells may include dropdown/modal detail markup. Parser must keep the
visible fencer name and ignore hidden detail tables.
"""

import os
import sys
from datetime import UTC, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_OPHARDT_HTML = """<!DOCTYPE html>
<html>
<head><title>ophardt.online</title></head>
<body>
<table>
  <thead>
    <tr><th>Discipline</th><th>Gender</th><th>Ageclass</th><th>Category</th><th>Calculated on</th></tr>
  </thead>
  <tbody>
    <tr><td>Epee</td><td>Men's</td><td>Senior</td><td>Individual</td><td>15.02.2026. 10:15</td></tr>
  </tbody>
</table>
<table>
  <thead>
    <tr>
      <th class="ranking">Rank</th>
      <th class="ranking">Points</th>
      <th class="ranking">T-P</th>
      <th class="ranking">Name</th>
      <th class="ranking">Nation</th>
      <th class="ranking rankingclub">Clubs</th>
      <th class="ranking">YOB</th>
      <th class="ranking">17.05.2025 København (Senior) Danske Senior Mesterskaber</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td class="ranking">1</td>
      <td class="ranking">128</td>
      <td class="ranking">0</td>
      <td class="ranking">
        <div class="btn-group">
          <a class="dropdown-toggle" href="#">KONGSTAD Conrad Seibæk</a>
          <ul class="dropdown-menu">
            <li><a href="#">Details</a></li>
            <li><a href="/en/biography/athlete/118694">Biography</a></li>
          </ul>
        </div>
        <div class="modal">
          <h5>KONGSTAD Conrad Seibæk</h5>
          <table>
            <tr><th>Rank</th><th>Points</th><th>Competition</th></tr>
            <tr><td>1</td><td>64</td><td>Danske Senior Mesterskaber</td></tr>
          </table>
        </div>
      </td>
      <td class="ranking">DEN</td>
      <td class="ranking rankingclub">Hellerup FK</td>
      <td class="ranking">1997</td>
      <td class="ranking">64</td>
    </tr>
    <tr>
      <td class="ranking">3</td>
      <td class="ranking">60,5</td>
      <td class="ranking">0</td>
      <td class="ranking">VØLUND Jonas Details Biography VØLUND Jonas × Rank Points Competition City Date</td>
      <td class="ranking">DEN</td>
      <td class="ranking rankingclub">KFK Kalundborg</td>
      <td class="ranking">2001</td>
      <td class="ranking">28</td>
    </tr>
  </tbody>
</table>
</body>
</html>"""


FIXTURE_EMPTY_HTML = ""


FIXTURE_NO_DATA_HTML = """<!DOCTYPE html>
<html>
<body>
  <h1>Danske Nationale Ranglister</h1>
  <p>Ingen rangliste tilgængelig.</p>
</body>
</html>"""


FIXTURE_NONSTANDARD_ROWS_HTML = """<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Plads</th><th>Navn</th><th>Klub</th><th>Point</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>Udeblevet Fægter</td><td>Test FK</td><td>0</td></tr>
    <tr><td>DQ</td><td>Diskvalificeret Fægter</td><td>Test FK</td><td>0</td></tr>
    <tr><td>I alt</td><td>3 fægtere</td><td></td><td>44,5</td></tr>
    <tr><td>7</td><td>NIELSEN Frederik Holger Bøjer</td><td>Trekanten København</td><td>50,5</td></tr>
  </tbody>
</table>
</body>
</html>"""


FIXTURE_DANISH_HEADERS_HTML = """<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Placering</th><th>Navn</th><th>Klub</th><th>Points</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>ÅKESEN Søren</td><td>Københavns Fægteklub</td><td>12,25</td></tr>
  </tbody>
</table>
</body>
</html>"""


def test_parse_rankings_table_returns_ophardt_rows():
    from scrape_fed_den import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_OPHARDT_HTML)

    assert len(rows) == 2
    assert rows[0] == {
        "rank": 1,
        "name": "KONGSTAD Conrad Seibæk",
        "club": "Hellerup FK",
        "points": 128.0,
    }
    assert rows[1]["rank"] == 3
    assert rows[1]["name"] == "VØLUND Jonas"
    assert rows[1]["club"] == "KFK Kalundborg"
    assert rows[1]["points"] == 60.5


def test_parse_rankings_table_empty_html_returns_empty_list():
    from scrape_fed_den import parse_rankings_table

    assert parse_rankings_table(FIXTURE_EMPTY_HTML) == []


def test_parse_rankings_table_no_data_page_returns_empty_list():
    from scrape_fed_den import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA_HTML) == []


def test_parse_rankings_table_skips_dns_dq_and_summary_rows():
    from scrape_fed_den import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NONSTANDARD_ROWS_HTML)

    assert rows == [
        {
            "rank": 7,
            "name": "NIELSEN Frederik Holger Bøjer",
            "club": "Trekanten København",
            "points": 50.5,
        }
    ]


def test_parse_rankings_table_handles_danish_headers_and_characters():
    from scrape_fed_den import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_DANISH_HEADERS_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "ÅKESEN Søren",
            "club": "Københavns Fægteklub",
            "points": 12.25,
        }
    ]


def test_ranking_combos_cover_senior_and_junior_weapon_gender_matrix():
    from scrape_fed_den import RANKING_COMBOS

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


def test_current_season_uses_active_year_range_with_july_boundary(monkeypatch):
    import scrape_fed_den

    class JuneDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 1, tzinfo=UTC)

    class JulyDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 1, tzinfo=UTC)

    monkeypatch.setattr(scrape_fed_den, "datetime", JuneDateTime)
    assert scrape_fed_den.current_season() == "2025-2026"

    monkeypatch.setattr(scrape_fed_den, "datetime", JulyDateTime)
    assert scrape_fed_den.current_season() == "2026-2027"

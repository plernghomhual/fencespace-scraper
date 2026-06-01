"""
Tests for scrape_fed_nor.py.

Probe findings:
  - fencing.no does not resolve.
  - The live federation site is https://www.fekting.no/next/p/24263/ranking.
  - That page links to Ophardt:
    https://fencing.ophardt.online/en/search/rankings/7
  - Public 2025/2026 Norges Rankinglister coverage is Epee only:
    Senior Men/Women and U20 Men/Women.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_OPHARDT_HTML = """
<!doctype html>
<html>
<body>
  <table>
    <tr><th>Discipline</th><th>Gender</th><th>Ageclass</th></tr>
    <tr><td>Epee</td><td>Men's</td><td>U20</td></tr>
  </table>
  <table>
    <thead>
      <tr>
        <th>Rank</th><th>Points</th><th>T-P</th><th>Name</th>
        <th>Nation</th><th>Clubs</th><th>YOB</th>
      </tr>
    </thead>
      <tr>
        <td>1</td><td>138</td><td>0</td>
        <td>
          KIBSGAARD VIK Martin Aleksander
          <a>Details Biography</a>
          <div>
            KIBSGAARD VIK Martin Aleksander
            <table>
              <tr><th>Rank</th><th>Points</th><th>Competition</th></tr>
              <tr><td>2</td><td>32</td><td>Nordic Championships</td></tr>
            </table>
          </div>
        </td>
        <td>NOR</td><td>OST Njård Fekting</td><td>2007</td>
      </tr>
      <tr>
        <td>4</td><td>65</td><td>0</td>
        <td>KALSÅS Emilian Revheim Details Biography</td>
        <td>NOR</td><td>VEST Bergens FK</td><td>2008</td>
      </tr>
      <tr>
        <td>7</td><td>49</td><td>0</td>
        <td>SÆLE-MEYER Philip Details Biography</td>
        <td>NOR</td><td>VEST Bergens FK</td><td>2009</td>
      </tr>
  </table>
</body>
</html>
"""


FIXTURE_NORWEGIAN_HEADERS_HTML = """
<!doctype html>
<html>
<body>
  <table>
    <thead>
      <tr><th>Plass</th><th>Navn</th><th>Klubb</th><th>Poeng</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>VON KOSS HELLEBØ Elsa</td><td>OST Njård Fekting</td><td>100,5</td></tr>
      <tr><td>2</td><td>AUSTBØ Maria</td><td>OST Bygdø FK</td><td>88</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_SHEET_TEXT = """
Plass;Navn;Klubb;Poeng
1;AARSETH India;OST Njård Fekting;62,5
2;BERGER Elisabeth Marie;OST Bygdø FK;30
"""


FIXTURE_NO_DATA = """
<!doctype html>
<html>
<body>
  <h1>Rankinglister</h1>
  <p>Ingen rankingliste er publisert for denne klassen.</p>
</body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
<!doctype html>
<html>
<body>
  <table>
    <tr><th>Rangering</th><th>Navn</th><th>Klubb</th><th>Poeng</th></tr>
    <tr><td>DNS</td><td>Ikke startet</td><td>Oslo FK</td><td>0</td></tr>
    <tr><td>DQ</td><td>Diskvalifisert</td><td>Bergens FK</td><td>0</td></tr>
    <tr><td>SUM</td><td>4 fektere</td><td></td><td>190</td></tr>
    <tr><td>3</td><td>DAHLE Abel Austbø</td><td>OST Njård Fekting</td><td>24</td></tr>
  </table>
</body>
</html>
"""


def test_parse_nor_ophardt_html_returns_rows_and_skips_nested_detail_rows():
    from scrape_fed_nor import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_OPHARDT_HTML)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "KIBSGAARD VIK Martin Aleksander",
        "club": "OST Njård Fekting",
        "points": 138.0,
    }
    assert rows[1]["name"] == "KALSÅS Emilian Revheim"
    assert rows[2]["name"] == "SÆLE-MEYER Philip"


def test_parse_nor_language_specific_headers_and_decimal_comma():
    from scrape_fed_nor import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NORWEGIAN_HEADERS_HTML)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "VON KOSS HELLEBØ Elsa"
    assert rows[0]["club"] == "OST Njård Fekting"
    assert rows[0]["points"] == 100.5
    assert rows[1]["club"] == "OST Bygdø FK"


def test_parse_nor_sheet_like_text_with_norwegian_headers():
    from scrape_fed_nor import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_SHEET_TEXT)

    assert len(rows) == 2
    assert rows[0]["name"] == "AARSETH India"
    assert rows[0]["points"] == 62.5


def test_parse_nor_empty_html_returns_empty_list():
    from scrape_fed_nor import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_nor_no_data_page_returns_empty_list():
    from scrape_fed_nor import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_nor_skips_dns_dq_and_summary_rows():
    from scrape_fed_nor import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 1
    assert rows[0]["rank"] == 3
    assert rows[0]["name"] == "DAHLE Abel Austbø"


def test_ranking_combos_cover_all_required_norway_combos():
    from scrape_fed_nor import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_returns_none_for_unpublished_combo():
    from scrape_fed_nor import fetch_rankings_page

    assert fetch_rankings_page("Foil", "Men", "Senior") is None


def test_current_season_format():
    from scrape_fed_nor import current_season

    season = current_season()
    assert re.match(r"^\d{4}-\d{4}$", season)
    start, end = season.split("-")
    assert int(end) == int(start) + 1

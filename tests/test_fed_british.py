"""
Tests for scrape_fed_british.py

Fixture HTML reflects the real British Fencing rankings-v2 page structure:
  URL pattern: https://www.britishfencing.com/rankings-v2/<category>-<gender>-<weapon>/
  Table columns: Rank | Name | Club | Licence | Total Points | Domestic | Domestic # | International | International #
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Minimal fixture matching real britishfencing.com rankings-v2 table structure
FIXTURE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Senior Mixed/Men's Epee - BRITISH FENCING</title></head>
<body>
<table>
  <thead>
    <tr>
      <th>Rank</th>
      <th>Name</th>
      <th>Club</th>
      <th>Licence</th>
      <th>Total Points</th>
      <th>Domestic</th>
      <th>Domestic #</th>
      <th>International</th>
      <th>International #</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>BEAUTYMAN Cador</td>
      <td>Knightsbridge Fencing Club</td>
      <td>127366</td>
      <td>86846</td>
      <td>19796</td>
      <td>2</td>
      <td>67050</td>
      <td>3</td>
    </tr>
    <tr>
      <td>2</td>
      <td>EAST William</td>
      <td>Knightsbridge Fencing Club</td>
      <td>110825</td>
      <td>76826</td>
      <td>18126</td>
      <td>2</td>
      <td>58700</td>
      <td>3</td>
    </tr>
    <tr>
      <td>3</td>
      <td>JEAL James</td>
      <td>Derbyshire Epee Academy</td>
      <td>112179</td>
      <td>55888</td>
      <td>26936</td>
      <td>3</td>
      <td>28952</td>
      <td>2</td>
    </tr>
    <tr>
      <td>4</td>
      <td>ANDREWS Benjamin</td>
      <td></td>
      <td>113262</td>
      <td>49748</td>
      <td>22604</td>
      <td>3</td>
      <td>27144</td>
      <td>2</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""

FIXTURE_HTML_EMPTY_TABLE = """
<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr>
      <th>Rank</th><th>Name</th><th>Club</th><th>Licence</th>
      <th>Total Points</th><th>Domestic</th><th>Domestic #</th>
      <th>International</th><th>International #</th>
    </tr>
  </thead>
  <tbody>
  </tbody>
</table>
</body>
</html>
"""

FIXTURE_HTML_NO_TABLE = """
<!DOCTYPE html>
<html>
<body><p>No rankings available.</p></body>
</html>
"""


def test_parse_british_rankings_returns_rows():
    from scrape_fed_british import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert len(rows) == 4

    first = rows[0]
    assert first["rank"] == 1
    assert first["name"] == "BEAUTYMAN Cador"
    assert first["club"] == "Knightsbridge Fencing Club"
    assert first["points"] == 86846

    second = rows[1]
    assert second["rank"] == 2
    assert second["name"] == "EAST William"
    assert second["points"] == 76826

    # Row with empty club should have club as None or empty string
    fourth = rows[3]
    assert fourth["rank"] == 4
    assert fourth["name"] == "ANDREWS Benjamin"
    assert fourth["club"] in (None, "")


def test_parse_british_rankings_empty_table():
    from scrape_fed_british import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_EMPTY_TABLE)
    assert rows == []


def test_parse_british_rankings_no_table():
    from scrape_fed_british import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_NO_TABLE)
    assert rows == []


def test_parse_british_rankings_row_count():
    from scrape_fed_british import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)
    assert len(rows) == 4
    # All rows must have rank, name, points
    for r in rows:
        assert isinstance(r["rank"], int)
        assert isinstance(r["name"], str) and r["name"]
        assert isinstance(r["points"], (int, float))


def test_build_slug():
    from scrape_fed_british import build_slug

    # Senior men use "mixed-mens"
    assert build_slug("Foil", "Men", "Senior") == "senior-mixed-mens-foil"
    assert build_slug("Epee", "Men", "Senior") == "senior-mixed-mens-epee"
    assert build_slug("Sabre", "Men", "Senior") == "senior-mixed-mens-sabre"

    # Senior women use "womens"
    assert build_slug("Foil", "Women", "Senior") == "senior-womens-foil"
    assert build_slug("Epee", "Women", "Senior") == "senior-womens-epee"
    assert build_slug("Sabre", "Women", "Senior") == "senior-womens-sabre"

    # Junior men use "mens" (not "mixed-mens")
    assert build_slug("Foil", "Men", "Junior") == "junior-mens-foil"
    assert build_slug("Epee", "Men", "Junior") == "junior-mens-epee"
    assert build_slug("Sabre", "Men", "Junior") == "junior-mens-sabre"

    # Junior women use "womens"
    assert build_slug("Foil", "Women", "Junior") == "junior-womens-foil"
    assert build_slug("Epee", "Women", "Junior") == "junior-womens-epee"
    assert build_slug("Sabre", "Women", "Junior") == "junior-womens-sabre"

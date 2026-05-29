"""
Tests for scrape_fed_italy.py

Fixture HTML reflects Italian-style fencing ranking table structure with Italian
column headers: Pos/Posizione=rank, Atleta/Nome=name, Società=club, Punti=points.

Site context: federscherma.it does not expose structured HTML rankings (2026-05-29
probe). Rankings are served as legacy XLS files. Tests use fixture HTML to verify
parser logic works correctly for when/if the site publishes HTML tables.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Fixture: Italian-style ranking table with Italian headers
FIXTURE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Classifica Nazionale - Fioretto Maschile Senior - Federscherma</title></head>
<body>
<table>
  <thead>
    <tr>
      <th>Pos</th>
      <th>Atleta</th>
      <th>Società</th>
      <th>Punti</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>GAROZZO Daniele</td>
      <td>Fiamme Oro</td>
      <td>1250</td>
    </tr>
    <tr>
      <td>2</td>
      <td>MACCHI Tommaso</td>
      <td>CS Aeronautica Militare</td>
      <td>1100</td>
    </tr>
    <tr>
      <td>3</td>
      <td>MARINI Alessio</td>
      <td>Frascati Scherma</td>
      <td>950</td>
    </tr>
    <tr>
      <td>4</td>
      <td>BIANCHI Mario</td>
      <td></td>
      <td>800</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""

# Fixture: full Italian "Posizione" header variant
FIXTURE_HTML_POSIZIONE = """
<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr>
      <th>Posizione</th>
      <th>Nome</th>
      <th>Club</th>
      <th>Punteggio</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>ROSSINI Elena</td>
      <td>Roma Scherma</td>
      <td>980</td>
    </tr>
    <tr>
      <td>2</td>
      <td>FERRARI Giulia</td>
      <td>Torino Scherma</td>
      <td>860</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""

# Fixture: table with comma-formatted points (e.g. "1,250")
FIXTURE_HTML_COMMA_POINTS = """
<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Pos</th><th>Atleta</th><th>Società</th><th>Punti</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>VERDI Paolo</td><td>Milano Scherma</td><td>1,250</td></tr>
    <tr><td>2</td><td>NERI Luca</td><td>Bologna Scherma</td><td>1,100</td></tr>
  </tbody>
</table>
</body>
</html>
"""

# Fixture: empty table (header only)
FIXTURE_HTML_EMPTY = """
<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Pos</th><th>Atleta</th><th>Società</th><th>Punti</th></tr>
  </thead>
  <tbody></tbody>
</table>
</body>
</html>
"""

# Fixture: no table at all
FIXTURE_HTML_NO_TABLE = """
<!DOCTYPE html>
<html>
<body><p>Nessuna classifica disponibile.</p></body>
</html>
"""


def test_parse_fis_rankings_returns_rows():
    """Primary test: Italian headers, correct rank/name on first row."""
    from scrape_fed_italy import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert len(rows) == 4

    first = rows[0]
    assert first["rank"] == 1
    assert first["name"] == "GAROZZO Daniele"
    assert first["club"] == "Fiamme Oro"
    assert first["points"] == 1250.0

    second = rows[1]
    assert second["rank"] == 2
    assert second["name"] == "MACCHI Tommaso"
    assert second["points"] == 1100.0

    # Row with empty club should be None
    fourth = rows[3]
    assert fourth["rank"] == 4
    assert fourth["name"] == "BIANCHI Mario"
    assert fourth["club"] in (None, "")


def test_parse_fis_rankings_empty():
    """Empty table returns empty list."""
    from scrape_fed_italy import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_EMPTY)
    assert rows == []


def test_parse_fis_rankings_no_table():
    """Page with no table returns empty list."""
    from scrape_fed_italy import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_NO_TABLE)
    assert rows == []


def test_parse_fis_rankings_posizione_header():
    """Accepts 'Posizione'/'Nome'/'Punteggio' Italian header variants."""
    from scrape_fed_italy import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_POSIZIONE)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "ROSSINI Elena"
    assert rows[0]["club"] == "Roma Scherma"
    assert rows[0]["points"] == 980.0
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "FERRARI Giulia"


def test_parse_fis_rankings_comma_points():
    """Points with comma-thousands separator are parsed correctly."""
    from scrape_fed_italy import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_COMMA_POINTS)
    assert len(rows) == 2
    assert rows[0]["points"] == 1250.0
    assert rows[1]["points"] == 1100.0


def test_parse_fis_rankings_row_count():
    """All rows have required types."""
    from scrape_fed_italy import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)
    assert len(rows) == 4
    for r in rows:
        assert isinstance(r["rank"], int)
        assert isinstance(r["name"], str) and r["name"]
        # club may be None for empty entries
        assert r["club"] is None or isinstance(r["club"], str)


def test_fetch_rankings_page_returns_none():
    """fetch_rankings_page returns None (site inaccessible as HTML)."""
    from scrape_fed_italy import fetch_rankings_page

    result = fetch_rankings_page("Foil", "Men", "Senior")
    assert result is None


def test_current_season_format():
    """current_season returns a string in YYYY-YYYY format."""
    from scrape_fed_italy import current_season
    import re

    season = current_season()
    assert re.match(r"^\d{4}-\d{4}$", season)
    parts = season.split("-")
    assert int(parts[1]) == int(parts[0]) + 1

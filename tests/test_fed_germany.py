"""
Tests for scrape_fed_germany.py

Fixture HTML mirrors the real Ophardt Online ranking page structure:
  URL pattern: https://fencing.ophardt.online/de/search/rankings/show/<id>
  Table layout:
    T0: Metadata table (Disziplin, Geschlecht, Altersklasse, ...)
    T1: Ranking table — direct <tr> children are fencer rows; nested sub-tables
        contain per-tournament detail that is NOT included in direct children.
  Fencer row columns: Platz | Punkte | Ü-P | Name | Nation | Vereine | Jahrgang | ...
  German column names: Platz=Rank, Punkte=Points (decimal comma), Vereine=Club
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Realistic fixture matching actual Ophardt Online HTML structure.
# Name cell contains "LASTNAME Firstname Detail Biographie..." text — the
# scraper must strip everything from "Detail" onward.
FIXTURE_HTML = """<!DOCTYPE html>
<html>
<head><title>ophardt.online</title></head>
<body>
<table>
  <thead>
    <tr><th>Disziplin</th><th>Geschlecht</th><th>Altersklasse</th><th>Kategorie</th><th>Berechnet am</th></tr>
  </thead>
  <tbody>
    <tr><td>Degen</td><td>Damen</td><td>Senior</td><td>Einzel</td><td>25.05.2026</td></tr>
    <tr><td>1929 - 2010</td><td>Rollieren (1:1)</td><td>Nur eigene Nationalität</td><td>Letztes Ergebnis</td><td></td></tr>
  </tbody>
</table>
<table>
  <thead>
    <tr>
      <th class="ranking">Platz</th>
      <th class="ranking">Punkte</th>
      <th class="ranking">Ü-P</th>
      <th class="ranking">Name</th>
      <th class="ranking">Nation</th>
      <th class="ranking rankingclub">Vereine</th>
      <th class="ranking">Jahrgang</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td class="ranking">1</td>
      <td class="ranking">80,5</td>
      <td class="ranking">0</td>
      <td class="ranking">ZITTEL Alexandra Detail Biographie ZITTEL Alexandra × P</td>
      <td class="ranking">GER</td>
      <td class="ranking rankingclub">WÜ Heidenheimer SB</td>
      <td class="ranking">2004</td>
    </tr>
    <tr>
      <td class="ranking">2</td>
      <td class="ranking">71,5</td>
      <td class="ranking">0</td>
      <td class="ranking">HESS SANCHO Gala Detail Biographie HESS SANCHO Gala × P</td>
      <td class="ranking">GER</td>
      <td class="ranking rankingclub">NW TSV Bayer 04 Leverkusen, (NW Aachener FC)</td>
      <td class="ranking">1998</td>
    </tr>
    <tr>
      <td class="ranking">3</td>
      <td class="ranking">65,5</td>
      <td class="ranking">0</td>
      <td class="ranking">EHLER Alexandra Detail Biographie EHLER Alexandra × P</td>
      <td class="ranking">GER</td>
      <td class="ranking rankingclub">NW TSV Bayer 04 Leverkusen</td>
      <td class="ranking">1995</td>
    </tr>
    <tr>
      <td class="ranking">4</td>
      <td class="ranking">58</td>
      <td class="ranking">0</td>
      <td class="ranking">MÜLLER Fiona Detail Biographie MÜLLER Fiona × P</td>
      <td class="ranking">GER</td>
      <td class="ranking rankingclub"></td>
      <td class="ranking">2004</td>
    </tr>
  </tbody>
</table>
</body>
</html>"""

FIXTURE_HTML_EMPTY_TABLE = """<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Disziplin</th><th>Geschlecht</th><th>Altersklasse</th><th>Kategorie</th><th>Berechnet am</th></tr>
  </thead>
  <tbody>
    <tr><td>Florett</td><td>Herren</td><td>Junior</td><td>Einzel</td><td>25.05.2026</td></tr>
  </tbody>
</table>
<table>
  <thead>
    <tr>
      <th class="ranking">Platz</th>
      <th class="ranking">Punkte</th>
      <th class="ranking">Ü-P</th>
      <th class="ranking">Name</th>
      <th class="ranking">Nation</th>
      <th class="ranking rankingclub">Vereine</th>
      <th class="ranking">Jahrgang</th>
    </tr>
  </thead>
  <tbody>
  </tbody>
</table>
</body>
</html>"""

FIXTURE_HTML_NO_SECOND_TABLE = """<!DOCTYPE html>
<html>
<body>
<table>
  <thead>
    <tr><th>Disziplin</th></tr>
  </thead>
  <tbody>
    <tr><td>Säbel</td></tr>
  </tbody>
</table>
</body>
</html>"""

FIXTURE_HTML_NO_TABLE = """<!DOCTYPE html>
<html>
<body><p>Keine Rangliste verfügbar.</p></body>
</html>"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_parse_dfb_rankings_returns_rows():
    from scrape_fed_germany import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert len(rows) == 4

    first = rows[0]
    assert first["rank"] == 1
    assert first["name"] == "ZITTEL Alexandra"
    assert first["club"] == "WÜ Heidenheimer SB"
    assert first["points"] == 80.5

    second = rows[1]
    assert second["rank"] == 2
    assert second["name"] == "HESS SANCHO Gala"
    assert second["points"] == 71.5

    third = rows[2]
    assert third["rank"] == 3
    assert third["name"] == "EHLER Alexandra"

    # Row with empty club should have club as None or empty string
    fourth = rows[3]
    assert fourth["rank"] == 4
    assert fourth["name"] == "MÜLLER Fiona"
    assert fourth["club"] in (None, "")


def test_parse_dfb_rankings_empty():
    from scrape_fed_germany import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_EMPTY_TABLE)
    assert rows == []


def test_parse_dfb_rankings_no_second_table():
    from scrape_fed_germany import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_NO_SECOND_TABLE)
    assert rows == []


def test_parse_dfb_rankings_no_table():
    from scrape_fed_germany import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_NO_TABLE)
    assert rows == []


def test_parse_dfb_rankings_row_types():
    from scrape_fed_germany import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)
    assert len(rows) == 4
    for r in rows:
        assert isinstance(r["rank"], int)
        assert isinstance(r["name"], str) and r["name"]
        assert r["points"] is None or isinstance(r["points"], float)


def test_parse_dfb_rankings_name_stripped():
    """Ensure 'Detail Biographie ...' suffix is stripped from name."""
    from scrape_fed_germany import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)
    for r in rows:
        assert "Detail" not in r["name"]
        assert "Biographie" not in r["name"]


def test_parse_dfb_rankings_points_german_decimal():
    """German decimal comma (80,5) must be parsed as 80.5."""
    from scrape_fed_germany import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)
    assert rows[0]["points"] == 80.5
    assert rows[1]["points"] == 71.5
    assert rows[2]["points"] == 65.5
    # Integer point value (no comma)
    assert rows[3]["points"] == 58.0

"""
Tests for scrape_fed_rou.py.

Probe findings:
  - Requested host federatia-de-scrima.ro did not resolve.
  - Current public site is https://frscrima.ro/.
  - https://frscrima.ro/ranking-national/ links Junior and Cadet ranking PDFs.
  - Target Junior ranking PDFs are public application/pdf files.

PDF text fixture mirrors pdfplumber extraction from:
  https://frscrima.ro/wp-content/uploads/2021/12/FLF-JUNIORI-3.pdf
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_PDF_TEXT = """
Anul Loc Total Nume si Prenume Club Nasterii
FEDERAŢIA ROMÂNĂ DE SCRIMĂ
FLORETA FEMININ JUNIORI
1 39 Teodorescu Maria 2005 CS Rapid Bucuresti 2 7.5 12 16 1.5
2 26.5 Dincă Andreea 2005 CSA Steaua București 6 7 7.5 6
3 23.75 Miti Bikfalvi Ingrid 2006 CSU Poli Timisoara 1 5.25 1.5 10 6
4 23 Adoch Alexandra 2009 ACS Floreta Timisoara 1 12 3 7 0
Total sportivi: 53
DNS Popescu Ioana CS Rapid Bucuresti
DQ Ionescu Ana CSA Steaua București
"""


FIXTURE_HTML_ROMANIAN_HEADERS = """
<!doctype html>
<html>
<body>
<table>
  <thead>
    <tr>
      <th>Loc</th>
      <th>Nume</th>
      <th>Club</th>
      <th>Puncte</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>Brânză Ana-Maria</td>
      <td>CSA Steaua București</td>
      <td>102,5</td>
    </tr>
    <tr>
      <td>2</td>
      <td>Țurcanu Ștefania</td>
      <td>CS Dinamo București</td>
      <td>88.25</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


FIXTURE_EMPTY_HTML = """
<!doctype html>
<html>
<body>
<table>
  <thead><tr><th>Loc</th><th>Nume</th><th>Club</th><th>Puncte</th></tr></thead>
  <tbody></tbody>
</table>
</body>
</html>
"""


FIXTURE_NO_DATA_PAGE = """
<!doctype html>
<html>
<body><p>Nu există clasament public pentru această categorie.</p></body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
<!doctype html>
<html>
<body>
<table>
  <tr><th>Loc</th><th>Nume si Prenume</th><th>Club</th><th>Total</th></tr>
  <tr><td>1</td><td>Popescu Elena</td><td>CS Rapid București</td><td>41,75</td></tr>
  <tr><td>DNS</td><td>Ionescu Maria</td><td>CSA Steaua București</td><td>0</td></tr>
  <tr><td>DQ</td><td>Dumitru Ioana</td><td>CS Dinamo București</td><td>0</td></tr>
  <tr><td>Total</td><td>3 sportivi</td><td></td><td>41,75</td></tr>
</table>
</body>
</html>
"""


def test_parse_rou_pdf_text_returns_rows():
    from scrape_fed_rou import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_PDF_TEXT)

    assert len(rows) == 4
    assert rows[0] == {
        "rank": 1,
        "name": "Teodorescu Maria",
        "club": "CS Rapid Bucuresti",
        "points": 39.0,
    }
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "Dincă Andreea"
    assert rows[1]["club"] == "CSA Steaua București"
    assert rows[1]["points"] == 26.5


def test_parse_rou_html_preserves_romanian_headers_and_characters():
    from scrape_fed_rou import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_ROMANIAN_HEADERS)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Brânză Ana-Maria"
    assert rows[0]["club"] == "CSA Steaua București"
    assert rows[0]["points"] == 102.5
    assert rows[1]["name"] == "Țurcanu Ștefania"


def test_parse_rou_empty_html_returns_empty_list():
    from scrape_fed_rou import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table(FIXTURE_EMPTY_HTML) == []


def test_parse_rou_no_table_or_no_data_returns_empty_list():
    from scrape_fed_rou import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA_PAGE) == []


def test_parse_rou_skips_dns_dq_and_summary_rows():
    from scrape_fed_rou import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 1
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Popescu Elena"
    assert rows[0]["points"] == 41.75


def test_rou_ranking_combos_cover_senior_and_junior_targets():
    from scrape_fed_rou import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert ("Foil", "Men", "Senior") in RANKING_COMBOS
    assert ("Foil", "Men", "Junior") in RANKING_COMBOS
    assert ("Sabre", "Women", "Senior") in RANKING_COMBOS
    assert ("Sabre", "Women", "Junior") in RANKING_COMBOS

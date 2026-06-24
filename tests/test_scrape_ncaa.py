from bs4 import BeautifulSoup

from scrape_ncaa import SECTION_MAP, parse_section

NCAA_HTML = """
<html><body>
<a name="WS"></a>
<table>
  <tr><th>Place</th><th>Name</th><th>School</th><th>V/B</th><th>Pct.</th><th>TS</th><th>TR</th><th>Ind.</th></tr>
  <tr><td>1.</td><td>Maggie Shealy</td><td>Brandeis</td><td>18/23</td><td>0.783</td><td>109</td><td>74</td><td>+35</td></tr>
  <tr><td>2.</td><td>Alice Smith</td><td>Harvard</td><td>15/23</td><td>0.652</td><td>98</td><td>82</td><td>+16</td></tr>
  <tr><td>T3.</td><td>Carol Jones</td><td>Penn</td><td>14/23</td><td>0.609</td><td>95</td><td>88</td><td>+7</td></tr>
</table>
<a name="ME"></a>
<table>
  <tr><th>Place</th><th>Name</th><th>School</th><th>V/B</th><th>Pct.</th><th>TS</th><th>TR</th><th>Ind.</th></tr>
  <tr><td>1.</td><td>Bob Chen</td><td>Princeton</td><td>20/23</td><td>0.870</td><td>105</td><td>50</td><td>+55</td></tr>
</table>
</body></html>
"""


def test_parse_section_returns_rows():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "WS")
    assert len(rows) == 3


def test_parse_section_fields():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "WS")
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Maggie Shealy"
    assert rows[0]["school"] == "Brandeis"
    assert rows[0]["vb"] == "18/23"
    assert rows[0]["pct"] == "0.783"
    assert rows[0]["ts"] == "109"
    assert rows[0]["tr_val"] == "74"
    assert rows[0]["ind"] == "+35"


def test_parse_section_tied_place():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "WS")
    assert rows[2]["rank"] == 3  # T3. → 3


def test_parse_section_skips_header_row():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "WS")
    assert not any(r["name"].lower() in ("name", "place", "competitor") for r in rows)


def test_parse_section_missing_anchor_returns_empty():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "MF")  # not in HTML
    assert rows == []


def test_parse_section_me():
    soup = BeautifulSoup(NCAA_HTML, "html.parser")
    rows = parse_section(soup, "ME")
    assert len(rows) == 1
    assert rows[0]["name"] == "Bob Chen"
    assert rows[0]["school"] == "Princeton"


def test_section_map_has_all_six():
    assert set(SECTION_MAP.keys()) == {"WS", "WF", "WE", "MS", "MF", "ME"}
    weapons = {v[0] for v in SECTION_MAP.values()}
    genders = {v[1] for v in SECTION_MAP.values()}
    assert weapons == {"Sabre", "Foil", "Epee"}
    assert genders == {"Women", "Men"}

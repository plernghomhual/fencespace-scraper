"""
Tests for scrape_fed_fin.py.

Fixtures reflect the probed public Finland/Ophardt ranking structure:
  - Official page: https://www.fencing-pentathlon.fi/miekkailu/kilpailutoiminta/miekkailun_ranking/
  - Ranking pages: https://fencing.ophardt.online/en/search/rankings/show/<id>
  - Detail table: Discipline | Gender | Ageclass | Category | Calculated on
  - Ranking table: Rank | Points | T-P | Name | Nation | Clubs | YOB | ...
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


OPHARDT_FIXTURE_HTML = """
<!doctype html>
<html>
<body>
  <h1>Kansallinen ranking: 2025</h1>
  <table>
    <tbody>
      <tr>
        <th>Discipline</th><th>Gender</th><th>Ageclass</th><th>Category</th><th>Calculated on</th>
      </tr>
      <tr>
        <td>Epee</td><td>Men's</td><td>Senior</td><td>Individual</td><td>29.05.2026. 05:01</td>
      </tr>
    </tbody>
  </table>
  <table>
    <thead>
      <tr>
        <th>Rank</th><th>Points</th><th>T-P</th><th>Name</th><th>Nation</th><th>Clubs</th><th>YOB</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="ranking">1</td>
        <td class="ranking">810</td>
        <td class="ranking">0</td>
        <td class="ranking">
          <div class="btn-group">
            <a class="dropdown-toggle" href="#">PAAVOLAINEN Jaakko</a>
            <ul class="dropdown-menu">
              <li><a href="#">Details</a></li>
              <li><a href="/en/biography/athlete/123757">Biography</a></li>
            </ul>
          </div>
          <div class="modal">PAAVOLAINEN Jaakko Rank Points Competition City Date 53 280 European Championships</div>
        </td>
        <td class="ranking" title="Nationality: FIN / ">FIN</td>
        <td class="ranking rankingclub">ES Helsingin Miekkailijat</td>
        <td class="ranking">1996</td>
      </tr>
      <tr>
        <td class="ranking">2.</td>
        <td class="ranking">562,5</td>
        <td class="ranking">0</td>
        <td class="ranking"><a class="dropdown-toggle" href="#">HÄMÄLÄINEN Emma</a></td>
        <td class="ranking">FIN</td>
        <td class="ranking rankingclub">Oulun Miekkailuseura</td>
        <td class="ranking">2007</td>
      </tr>
    </tbody>
  </table>
</body>
</html>
"""


FINNISH_HEADER_FIXTURE_HTML = """
<html>
<body>
  <table>
    <thead>
      <tr><th>Sija</th><th>Nimi</th><th>Seura</th><th>Pisteet</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>ÖSTERMAN Åsa</td><td>Turun Miekkailijat</td><td>42,75</td></tr>
      <tr><td>2</td><td>Юлия Ääkkönen</td><td>HABDA</td><td>30</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


SKIPPED_ROWS_FIXTURE_HTML = """
<html>
<body>
  <table>
    <thead>
      <tr><th>Sija</th><th>Nimi</th><th>Seura</th><th>Pisteet</th></tr>
    </thead>
    <tbody>
      <tr><td>DNS</td><td>Missing Fencer</td><td>SK</td><td>0</td></tr>
      <tr><td>DQ</td><td>Disqualified Fencer</td><td>SK</td><td>0</td></tr>
      <tr><td>Yhteensä</td><td>3 miekkailijaa</td><td></td><td>100</td></tr>
      <tr><td>3</td><td>NIEMISTÖ Michelle</td><td>Tapanilan Erä</td><td>12,5</td></tr>
    </tbody>
  </table>
</body>
</html>
"""

COMBINED_TABLE_FIXTURE_HTML = """
<html>
<body>
  <h2>Kalpa miehet seniorit</h2>
  <table>
    <thead>
      <tr><th>Sija</th><th>Nimi</th><th>Seura</th><th>Pisteet</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>PAAVOLAINEN Jaakko</td><td>ES Helsingin Miekkailijat</td><td>810</td></tr>
    </tbody>
  </table>
  <h2>Kalpa naiset seniorit</h2>
  <table>
    <thead>
      <tr><th>Sija</th><th>Nimi</th><th>Seura</th><th>Pisteet</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>SALMINEN Anna</td><td>HABDA</td><td>885</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


NO_DATA_FIXTURE_HTML = """
<html>
<body>
  <h1>Kansallinen ranking: 2025</h1>
  <p>Ei rankingpisteitä.</p>
</body>
</html>
"""


def test_parse_ophardt_rankings_returns_valid_rows():
    from scrape_fed_fin import parse_rankings_table

    rows = parse_rankings_table(OPHARDT_FIXTURE_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "PAAVOLAINEN Jaakko",
            "club": "ES Helsingin Miekkailijat",
            "points": 810.0,
        },
        {
            "rank": 2,
            "name": "HÄMÄLÄINEN Emma",
            "club": "Oulun Miekkailuseura",
            "points": 562.5,
        },
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_fin import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_fin import parse_rankings_table

    assert parse_rankings_table(NO_DATA_FIXTURE_HTML) == []


def test_parse_skips_dns_dq_and_summary_rows():
    from scrape_fed_fin import parse_rankings_table

    rows = parse_rankings_table(SKIPPED_ROWS_FIXTURE_HTML)

    assert rows == [
        {
            "rank": 3,
            "name": "NIEMISTÖ Michelle",
            "club": "Tapanilan Erä",
            "points": 12.5,
        }
    ]


def test_parse_finnish_headers_decimal_commas_and_utf8_names():
    from scrape_fed_fin import parse_rankings_table

    rows = parse_rankings_table(FINNISH_HEADER_FIXTURE_HTML)

    assert rows[0]["name"] == "ÖSTERMAN Åsa"
    assert rows[0]["club"] == "Turun Miekkailijat"
    assert rows[0]["points"] == 42.75
    assert rows[1]["name"] == "Юлия Ääkkönen"


def test_parse_combined_public_page_keeps_all_identifiable_tables():
    from scrape_fed_fin import parse_rankings_table

    rows = parse_rankings_table(COMBINED_TABLE_FIXTURE_HTML)

    assert [row["name"] for row in rows] == ["PAAVOLAINEN Jaakko", "SALMINEN Anna"]


def test_fetch_rankings_page_returns_none_for_missing_public_combo():
    from scrape_fed_fin import fetch_rankings_page

    assert fetch_rankings_page("Foil", "Men", "Junior") is None


def test_fetch_rankings_page_uses_public_combo_mapping(monkeypatch):
    import scrape_fed_fin

    calls = []

    class Response:
        status_code = 200
        text = "<html>ranking</html>"

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(scrape_fed_fin.requests, "get", fake_get)

    content = scrape_fed_fin.fetch_rankings_page("Epee", "Women", "Senior")

    assert content == "<html>ranking</html>"
    assert calls[0][0] == "https://fencing.ophardt.online/en/search/rankings/show/21271"
    assert calls[0][1]["headers"] == scrape_fed_fin.HEADERS

"""
Tests for scrape_fed_swe.py.

Fixtures mirror Swedish federation public ranking data probed from:
  https://svenskfaktning.se/tavling/nationella-och-regionala-tavlingsserier/
  https://fencing.ophardt.online/sv/search/rankings/show/21574

Relevant Ophardt table headers:
  Plats | Poäng | Överförda poäng | Namn | Nation | Klubb/Klubbar | Född
"""

import os
import re
import sys
from datetime import UTC, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_OPHARDT_HTML = """
<!doctype html>
<html>
<body>
  <table class="table table-striped table">
    <tr><th>Klass</th><th>Kön</th><th>Åldersklass</th><th>Kategori</th><th>Beräknad den</th></tr>
    <tr><td>Värja</td><td>Herrar</td><td>Seniorer</td><td>Individuell</td><td>10.05.2026. 17:58</td></tr>
  </table>
  <table class="table table-striped table-sm rankingbody fixedheader">
    <thead>
      <tr>
        <th>Plats</th><th>Poäng</th><th>Överförda poäng</th><th>Namn</th>
        <th>Nation</th><th>Klubb/Klubbar</th><th>Född</th>
      </tr>
    </thead>
    <tr>
      <td class="ranking">1</td>
      <td class="ranking">360,5</td>
      <td class="ranking">0</td>
      <td class="ranking">
        <div class="btn-group">
          <a id="dLabel1" class="dropdown-toggle">ZIMMERMAN Filip</a>
          <ul class="dropdown-menu"><li>Detaljer</li><li>Biografi</li></ul>
        </div>
        <div class="modal fade"><h5>ZIMMERMAN Filip</h5><table><tr><td>hidden detail</td></tr></table></div>
      </td>
      <td class="ranking">SWE</td>
      <td class="ranking">MS WFF Örebro</td>
      <td class="ranking">2008</td>
    </tr>
    <tr>
      <td class="ranking">2</td>
      <td class="ranking">341,5</td>
      <td class="ranking">0</td>
      <td class="ranking"><a>BÄCKSTRÖM Ian</a></td>
      <td class="ranking">SWE</td>
      <td class="ranking">ST FFF Stockholm</td>
      <td class="ranking">2004</td>
    </tr>
  </table>
</body>
</html>
"""


FIXTURE_SWEDISH_HEADER_HTML = """
<html>
<body>
  <table>
    <thead>
      <tr><th>Placering</th><th>Namn</th><th>Förening</th><th>Poäng</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>ÅSTRÖM Elin</td><td>Göteborgs FK</td><td>125,25</td></tr>
      <tr><td>2</td><td>李 Åström</td><td>Ängby Fäktklubb</td><td>100</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_NO_DATA = """
<html><body><p>Det finns ingen ranking att visa.</p><p>No rankings available.</p></body></html>
"""


FIXTURE_NON_STANDARD_ROWS = """
Placering | Namn | Förening | Poäng
DNS | Andersson Test | Stockholms FK | 0
DQ | Diskad Test | Uppsala FK | 0
Totalt | 2 fäktare |  | 700
1 | HÅKANSSON Märta | Malmö FK | 300,5
2 | ÖBERG Sara | LUGI Fäktförening | 250
"""


def test_parse_swe_ophardt_rankingbody_rows_and_ranking_date():
    from scrape_fed_swe import extract_ranking_date, parse_rankings_table

    rows = parse_rankings_table(FIXTURE_OPHARDT_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "ZIMMERMAN Filip",
            "club": "MS WFF Örebro",
            "points": 360.5,
        },
        {
            "rank": 2,
            "name": "BÄCKSTRÖM Ian",
            "club": "ST FFF Stockholm",
            "points": 341.5,
        },
    ]
    assert extract_ranking_date(FIXTURE_OPHARDT_HTML) == "10.05.2026. 17:58"


def test_parse_swe_language_specific_headers_and_native_script_names():
    from scrape_fed_swe import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_SWEDISH_HEADER_HTML)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "ÅSTRÖM Elin"
    assert rows[0]["club"] == "Göteborgs FK"
    assert rows[0]["points"] == 125.25
    assert rows[1]["name"] == "李 Åström"
    assert rows[1]["club"] == "Ängby Fäktklubb"


def test_parse_swe_empty_html_returns_empty_list():
    from scrape_fed_swe import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_swe_no_table_no_data_page_returns_empty_list():
    from scrape_fed_swe import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_swe_skips_dns_dq_and_summary_rows():
    from scrape_fed_swe import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 2
    assert [row["name"] for row in rows] == ["HÅKANSSON Märta", "ÖBERG Sara"]
    assert rows[0]["points"] == 300.5


def test_ranking_combos_cover_all_required_sweden_rankings():
    from scrape_fed_swe import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_swe

    class FakeResponse:
        status_code = 404
        text = "not found"

    monkeypatch.setattr(
        scrape_fed_swe,
        "_ranking_url_for",
        lambda weapon, gender, category, season=None: "https://example.invalid/missing",
    )
    monkeypatch.setattr(
        scrape_fed_swe.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(),
    )

    assert scrape_fed_swe.fetch_rankings_page("Sabre", "Women", "Senior") is None


def test_current_season_format():
    from scrape_fed_swe import current_season

    season = current_season()
    assert re.match(r"^\d{4}-\d{4}$", season)
    start, end = season.split("-")
    assert int(end) == int(start) + 1


def test_current_season_uses_active_season_before_july(monkeypatch):
    import scrape_fed_swe

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 1, tzinfo=tz or UTC)

    monkeypatch.setattr(scrape_fed_swe, "datetime", FixedDateTime)

    assert scrape_fed_swe.current_season() == "2025-2026"

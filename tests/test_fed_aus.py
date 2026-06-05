"""
Tests for scrape_fed_aus.py.

Fixtures mirror Australian Fencing Federation ranking tables probed on 2026-06-01:
  Senior: https://www.ausfencing.org/open-rankings/
  Junior: https://www.ausfencing.org/junior-rankings/

Relevant table columns:
  Rank | Fencer | Pts | AFC1 2025/26 | AFC2 2025/26 | ...

AFF embeds state in the fencer display value, e.g. "CROOK, Jacob (QLD)".
"""

from typing import cast
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_AFF_TABLE = """
<!doctype html>
<html>
<body>
<table id="tablepress-44">
  <thead>
    <tr>
      <th>Rank</th>
      <th>Fencer</th>
      <th>Pts</th>
      <th>AFC1 2025/26</th>
      <th>AFC2 2025/26</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td><a href="/biography/afb-1001/">CROOK, Jacob (QLD)</a></td>
      <td>111.82</td>
      <td>-</td>
      <td>12.6</td>
    </tr>
    <tr>
      <td>2</td>
      <td>DIACHENKO, Vsevolod (VIC)</td>
      <td>89,6</td>
      <td>23.4</td>
      <td>28.8</td>
    </tr>
    <tr>
      <td>*</td>
      <td>BAKER, Matthew (NZL)</td>
      <td>49.85</td>
      <td>-</td>
      <td>7.2</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


FIXTURE_AFF_STATE_CLUB_TABLE = """
<table>
  <thead>
    <tr>
      <th>Rank</th>
      <th>Name</th>
      <th>State</th>
      <th>Club</th>
      <th>Points</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>LEE, Aeryn 李</td>
      <td>NSW</td>
      <td>Sydney Sabre Centre</td>
      <td>78,5</td>
    </tr>
  </tbody>
</table>
"""


FIXTURE_NON_STANDARD_ROWS = """
<table>
  <thead>
    <tr><th>Rank</th><th>Fencer</th><th>Pts</th></tr>
  </thead>
  <tbody>
    <tr><td>DNS</td><td>SCRATCHED, Fencer (QLD)</td><td>0</td></tr>
    <tr><td>DQ</td><td>DISQUALIFIED, Fencer (NSW)</td><td>0</td></tr>
    <tr><td>Total</td><td>3 fencers</td><td>300</td></tr>
    <tr><td>1</td><td>ROBINSON, Sora (NSW)</td><td>336.8</td></tr>
  </tbody>
</table>
"""


FIXTURE_NO_DATA = """
<!doctype html>
<html><body><p>No rankings available.</p></body></html>
"""


FIXTURE_PAGE_WITH_ACCORDIONS = """
<html>
<body>
  <button class="fl-accordion-button">Men's Epee</button>
  <div class="fl-accordion-content fl-clearfix">
    <table>
      <tr><th>Rank</th><th>Fencer</th><th>Pts</th></tr>
      <tr><td>1</td><td>CROOK, Jacob (QLD)</td><td>111.82</td></tr>
    </table>
  </div>
  <button class="fl-accordion-button">Women's Foil</button>
  <div class="fl-accordion-content fl-clearfix">
    <table>
      <tr><th>Rank</th><th>Fencer</th><th>Pts</th></tr>
      <tr><td>1</td><td>GLASSON, Sophia (NSW)</td><td>121.1</td></tr>
    </table>
  </div>
</body>
</html>
"""


def test_parse_aff_rankings_returns_rows_with_state_metadata():
    from scrape_fed_aus import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_AFF_TABLE)

    assert len(rows) == 2
    assert rows[0] == {
        "rank": 1,
        "name": "CROOK, Jacob",
        "club": None,
        "points": 111.82,
        "metadata": {"state": "QLD"},
    }
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "DIACHENKO, Vsevolod"
    assert rows[1]["points"] == 89.6
    assert rows[1]["metadata"] == {"state": "VIC"}


def test_parse_aff_language_specific_headers_and_native_script_names():
    from scrape_fed_aus import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_AFF_STATE_CLUB_TABLE)

    assert len(rows) == 1
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "LEE, Aeryn 李"
    assert rows[0]["club"] == "Sydney Sabre Centre"
    assert rows[0]["points"] == 78.5
    assert rows[0]["metadata"] == {"state": "NSW"}


def test_parse_aff_empty_html_returns_empty_list():
    from scrape_fed_aus import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_aff_no_data_page_returns_empty_list():
    from scrape_fed_aus import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_aff_skips_dns_dq_summary_and_unranked_rows():
    from scrape_fed_aus import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 1
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "ROBINSON, Sora"


def test_extract_combo_table_selects_requested_aff_section():
    from scrape_fed_aus import extract_combo_table_html, parse_rankings_table

    table_html = extract_combo_table_html(FIXTURE_PAGE_WITH_ACCORDIONS, "Foil", "Women")
    table_html = cast(str, table_html)
    rows = parse_rankings_table(table_html)

    assert len(rows) == 1
    assert rows[0]["name"] == "GLASSON, Sophia"
    assert rows[0]["metadata"] == {"state": "NSW"}


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_aus

    class FakeResponse:
        status_code = 404
        text = "not found"
        url = "https://www.ausfencing.org/missing/"

    def fake_get(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(scrape_fed_aus.requests, "get", fake_get)

    assert scrape_fed_aus.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_network_error(monkeypatch):
    import requests
    import scrape_fed_aus

    def fake_get(*args, **kwargs):
        raise requests.RequestException("network down")

    monkeypatch.setattr(scrape_fed_aus.requests, "get", fake_get)

    assert scrape_fed_aus.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_extracts_requested_combo(monkeypatch):
    import scrape_fed_aus

    class FakeResponse:
        status_code = 200
        text = FIXTURE_PAGE_WITH_ACCORDIONS
        url = "https://www.ausfencing.org/open-rankings/"

    def fake_get(url, **kwargs):
        assert url == "https://www.ausfencing.org/open-rankings/"
        return FakeResponse()

    monkeypatch.setattr(scrape_fed_aus.requests, "get", fake_get)

    html = scrape_fed_aus.fetch_rankings_page("Epee", "Men", "Senior")
    html = cast(str, html)
    rows = scrape_fed_aus.parse_rankings_table(html)

    assert rows[0]["name"] == "CROOK, Jacob"


def test_ranking_combos_cover_all_required_australia_rankings():
    from scrape_fed_aus import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_current_season_format():
    from scrape_fed_aus import current_season

    season = current_season()
    assert re.match(r"^\d{4}-\d{4}$", season)
    start, end = season.split("-")
    assert int(end) == int(start) + 1


def test_current_season_uses_july_boundary(monkeypatch):
    import scrape_fed_aus

    class JuneDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 30, tzinfo=timezone.utc)

    class JulyDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(scrape_fed_aus, "datetime", JuneDateTime)
    assert scrape_fed_aus.current_season() == "2025-2026"

    monkeypatch.setattr(scrape_fed_aus, "datetime", JulyDateTime)
    assert scrape_fed_aus.current_season() == "2026-2027"

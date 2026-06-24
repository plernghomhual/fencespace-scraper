"""
Tests for scrape_fed_nzl.py.

Fixture data mirrors the public FeNZ rankings portal discovered at:
  GET https://api.fencing.org.nz/public/ranking?weapon=foil&cat=open

The API returns JSON with top-level Mens/Womens lists and row fields:
  rank, uid, name, club, region, cat, points, comps, avg, change.
"""

import json
import os
import re
import sys
from typing import cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


API_SELECTED_FIXTURE = json.dumps(
    {
        "cat": "open",
        "weapon": "foil",
        "ranking_at": "2026-06-01",
        "last_update": "1 Jun 2026",
        "gender": "Men",
        "gender_key": "Mens",
        "source_url": "https://api.fencing.org.nz/public/ranking?weapon=foil&cat=open",
        "rows": [
            {
                "last_update": "1 Jun 2026",
                "ranking_at": "2026-06-01",
                "rank": "1",
                "uid": "12307",
                "name": "LI, Samuel",
                "club": "WEL Fencing Club",
                "region": "Central",
                "cat": "u15",
                "points": "705",
                "comps": "5",
                "avg": "141",
                "change": "0",
            },
            {
                "last_update": "1 Jun 2026",
                "ranking_at": "2026-06-01",
                "rank": "2",
                "uid": "12299",
                "name": "MURRAY, Ārihi",
                "club": "North Harbour Fencing",
                "region": "North",
                "cat": "open",
                "points": "690,5",
                "comps": "5",
                "avg": "138",
                "change": "-1",
            },
        ],
    }
)


API_RAW_FIXTURE = {
    "cat": "open",
    "weapon": "foil",
    "ranking_at": "2026-06-01",
    "last_update": "1 Jun 2026",
    "Mens": [
        {
            "rank": "1",
            "uid": "12307",
            "name": "LI, Samuel",
            "club": "WEL Fencing Club",
            "region": "Central",
            "cat": "u15",
            "points": "705",
            "comps": "5",
            "avg": "141",
            "change": "0",
        }
    ],
    "Womens": [
        {
            "rank": "1",
            "uid": "13001",
            "name": "GILLIES, Joni",
            "club": "Dunedin Fencing",
            "region": "MidSouth",
            "cat": "open",
            "points": "488",
            "comps": "4",
            "avg": "122",
            "change": "0",
        }
    ],
}


HTML_REGION_FIXTURE = """
<!doctype html>
<html>
<body>
  <table>
    <thead>
      <tr><th>Rank</th><th>Name</th><th>Region</th><th>Points</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>Āperahama 李</td><td>Central</td><td>123,5</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


HTML_NON_STANDARD_ROWS = """
<table>
  <tr><th>Rank</th><th>Name</th><th>Club</th><th>Region</th><th>Points</th></tr>
  <tr><td>DNS</td><td>Late Scratch</td><td>Pulse Fencing</td><td>North</td><td>0</td></tr>
  <tr><td>DQ</td><td>Disqualified Fencer</td><td>WEL Fencing Club</td><td>Central</td><td>0</td></tr>
  <tr><td>Total</td><td>2 fencers</td><td></td><td></td><td>0</td></tr>
  <tr><td>1</td><td>O'CONNOR, Tui</td><td>Hawkes Bay Blades</td><td>Central</td><td>377</td></tr>
</table>
"""


NO_DATA_PAGE = """
<!doctype html>
<html><body><p>No rankings available for this category.</p></body></html>
"""


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = {"content-type": "application/json"}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_parse_nzl_api_json_returns_rows_and_preserves_utf8():
    from scrape_fed_nzl import parse_rankings_table

    rows = parse_rankings_table(API_SELECTED_FIXTURE)

    assert len(rows) == 2
    assert rows[0] == {
        "rank": 1,
        "name": "LI, Samuel",
        "club": "WEL Fencing Club",
        "points": 705.0,
        "region": "Central",
        "uid": "12307",
        "category_code": "u15",
        "ranking_at": "2026-06-01",
        "last_update": "1 Jun 2026",
    }
    assert rows[1]["name"] == "MURRAY, Ārihi"
    assert rows[1]["points"] == 690.5


def test_parse_nzl_empty_html_returns_empty_list():
    from scrape_fed_nzl import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_nzl_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_nzl import parse_rankings_table

    assert parse_rankings_table(NO_DATA_PAGE) == []
    assert parse_rankings_table(json.dumps({"Mens": [], "Womens": [], "last_update": ""})) == []


def test_parse_nzl_region_header_preserves_native_script_and_decimal_comma():
    from scrape_fed_nzl import parse_rankings_table

    rows = parse_rankings_table(HTML_REGION_FIXTURE)

    assert rows == [
        {
            "rank": 1,
            "name": "Āperahama 李",
            "club": None,
            "points": 123.5,
            "region": "Central",
        }
    ]


def test_parse_nzl_skips_dns_dq_and_summary_rows():
    from scrape_fed_nzl import parse_rankings_table

    rows = parse_rankings_table(HTML_NON_STANDARD_ROWS)

    assert len(rows) == 1
    assert rows[0]["name"] == "O'CONNOR, Tui"
    assert rows[0]["rank"] == 1


def test_fetch_rankings_page_uses_public_api_and_selects_requested_gender(monkeypatch):
    import scrape_fed_nzl

    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(payload=API_RAW_FIXTURE)

    monkeypatch.setattr(scrape_fed_nzl.requests, "get", fake_get)

    content = scrape_fed_nzl.fetch_rankings_page("Foil", "Women", "Senior")
    content = cast(str, content)
    rows = scrape_fed_nzl.parse_rankings_table(content)

    assert calls[0][0] == "https://api.fencing.org.nz/public/ranking"
    assert calls[0][1]["params"] == {"weapon": "foil", "cat": "open"}
    assert rows[0]["name"] == "GILLIES, Joni"
    assert rows[0]["region"] == "MidSouth"


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_nzl

    def fake_get(url, **kwargs):
        return FakeResponse(status_code=404, text="not found")

    monkeypatch.setattr(scrape_fed_nzl.requests, "get", fake_get)

    assert scrape_fed_nzl.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_ranking_combos_cover_required_nzl_rankings():
    from scrape_fed_nzl import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_current_season_format():
    from scrape_fed_nzl import current_season

    season = current_season()
    assert re.match(r"^\d{4}-\d{4}$", season)
    start, end = season.split("-")
    assert int(end) == int(start) + 1

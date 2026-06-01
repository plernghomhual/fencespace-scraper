"""
Tests for scrape_fed_ned.py.

Source probe (2026-06-01):
  - The requested knfb.nl paths returned HTTP 200 but no ranking content.
  - KNAS links rankings at https://knas.onzeranglijsten.net/.
  - Ranking pages are public server-rendered HTML, for example:
      https://knas.onzeranglijsten.net/pag/8094/rls/4f54
  - Table columns: Plaats | Schermer | Vereniging | Punten.
    The Schermer and Vereniging headers use colspan=2, so data rows contain:
      rank, fencer_id, name, club_id, club, points.
"""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Ranglijsten - Ranglijst - Individueel - degen heren junioren - 2026-05-01</title></head>
<body>
<table class="ot-table">
  <thead class="ot-thead">
    <tr class="ot-header-row">
      <th class="is-sortable is-sorted-asc ot-header" data-sort-order="1">Plaats</th>
      <th class="is-sortable-1 is-sortable-2 ot-header" colspan="2"><span></span>Schermer</th>
      <th class="is-sortable-1 is-sortable-2 ot-header" colspan="2"><span></span>Vereniging</th>
      <th class="is-sortable ot-header">Punten</th>
    </tr>
  </thead>
  <tbody class="ot-tbody">
    <tr class="ot-filter-row">
      <td class="ot-filter"><input class="ot-filter-text" type="text"/></td>
      <td class="ot-filter"><input class="ot-filter-text" type="text"/></td>
      <td class="ot-filter"><input class="ot-filter-text" type="text"/></td>
      <td class="ot-filter"><input class="ot-filter-text" type="text"/></td>
      <td class="ot-filter"><input class="ot-filter-text" type="text"/></td>
      <td class="ot-filter"><input class="ot-filter-text" type="text"/></td>
    </tr>
    <tr class="is-even ot-row">
      <td class="ot-cell ot-cell-number" data-value="1">1</td>
      <td class="ot-cell ot-cell-number"><a class="link ot-link" href="/pag/59c1/rl1/59496a">116758</a></td>
      <td class="ot-cell ot-cell-relation">VERSTEIJNEN Jan-Koen</td>
      <td class="ot-cell ot-cell-number"><a class="link ot-link" href="/pag/59c1/rl1/d8f2b0">4012</a></td>
      <td class="ot-cell ot-cell-relation">Schermclub Den Bosch</td>
      <td class="ot-cell ot-cell-number" data-value="2532">2532</td>
    </tr>
    <tr class="is-odd ot-row">
      <td class="ot-cell ot-cell-number" data-value="2">2</td>
      <td class="ot-cell ot-cell-number"><a class="link ot-link" href="/pag/59c1/rl1/daae7e">116739</a></td>
      <td class="ot-cell ot-cell-relation">VAN DEN BERG Cedric</td>
      <td class="ot-cell ot-cell-number"><a class="link ot-link" href="/pag/59c1/rl1/541313">5027</a></td>
      <td class="ot-cell ot-cell-relation">S.V. Zaal Treffers</td>
      <td class="ot-cell ot-cell-number" data-value="2469">2.469,5</td>
    </tr>
    <tr class="is-even ot-row">
      <td class="ot-cell ot-cell-number" data-value="3">3</td>
      <td class="ot-cell ot-cell-number"><a class="link ot-link" href="/pag/59c1/rl1/a5b8a7">116978</a></td>
      <td class="ot-cell ot-cell-relation">李 Anna</td>
      <td class="ot-cell ot-cell-number"><a class="link ot-link" href="/pag/59c1/rl1/d8f2b0">4012</a></td>
      <td class="ot-cell ot-cell-relation">Scaramouche</td>
      <td class="ot-cell ot-cell-number" data-value="1234">1234</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


FIXTURE_HTML_CLUB_HEADER = """
<table>
  <tr><th>Rank</th><th>Name</th><th>Club</th><th>Points</th></tr>
  <tr><td>1</td><td>VAN DER MEER Sofie</td><td>s.v. Tréville</td><td>12,5</td></tr>
</table>
"""


FIXTURE_HTML_EMPTY = """
<table class="ot-table">
  <thead><tr><th>Plaats</th><th>Schermer</th><th>Vereniging</th><th>Punten</th></tr></thead>
  <tbody></tbody>
</table>
"""


FIXTURE_HTML_NO_TABLE = """
<!DOCTYPE html>
<html><body><p>Geen ranglijst beschikbaar.</p></body></html>
"""


FIXTURE_HTML_NON_STANDARD_ROWS = """
<table class="ot-table">
  <tr><th>Plaats</th><th>Schermer</th><th>Vereniging</th><th>Punten</th></tr>
  <tr><td>1</td><td>117325</td><td>KOCKEN Veronique</td><td>2008</td><td>s.v. Scaramouche</td><td>1425</td></tr>
  <tr><td>DNS</td><td>119791</td><td>PIEPER Vlinder</td><td>5027</td><td>S.V. Zaal Treffers</td><td>1167</td></tr>
  <tr><td>2</td><td>DQ</td><td>Samenvatting</td><td></td><td>Totaal</td><td>2592</td></tr>
  <tr><td>Total</td><td></td><td>2 schermers</td><td></td><td></td><td>2592</td></tr>
</table>
"""


def test_parse_rankings_table_returns_rows_from_knas_fixture():
    from scrape_fed_ned import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "VERSTEIJNEN Jan-Koen",
        "club": "Schermclub Den Bosch",
        "points": 2532.0,
    }
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "VAN DEN BERG Cedric"
    assert rows[1]["club"] == "S.V. Zaal Treffers"
    assert rows[1]["points"] == 2469.5


def test_parse_rankings_table_preserves_native_script_names():
    from scrape_fed_ned import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert rows[2]["name"] == "李 Anna"
    assert rows[2]["club"] == "Scaramouche"


def test_parse_rankings_table_accepts_club_header_alias():
    from scrape_fed_ned import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_CLUB_HEADER)

    assert rows == [
        {"rank": 1, "name": "VAN DER MEER Sofie", "club": "s.v. Tréville", "points": 12.5}
    ]


def test_parse_rankings_table_empty_html_returns_empty_list():
    from scrape_fed_ned import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table(FIXTURE_HTML_EMPTY) == []


def test_parse_rankings_table_no_table_or_no_data_returns_empty_list():
    from scrape_fed_ned import parse_rankings_table

    assert parse_rankings_table(FIXTURE_HTML_NO_TABLE) == []


def test_parse_rankings_table_skips_dns_dq_and_summary_rows():
    from scrape_fed_ned import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_NON_STANDARD_ROWS)

    assert rows == [
        {"rank": 1, "name": "KOCKEN Veronique", "club": "s.v. Scaramouche", "points": 1425.0}
    ]


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_ned

    class Response:
        status_code = 404
        text = "not found"
        url = "https://knas.onzeranglijsten.net/missing"

        def raise_for_status(self):
            raise AssertionError("fetch_rankings_page should not call raise_for_status")

    def fake_get(*args, **kwargs):
        return Response()

    monkeypatch.setattr(scrape_fed_ned.requests, "get", fake_get)

    assert scrape_fed_ned.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_on_network_error(monkeypatch):
    import requests
    import scrape_fed_ned

    def fake_get(*args, **kwargs):
        raise requests.RequestException("network down")

    monkeypatch.setattr(scrape_fed_ned.requests, "get", fake_get)

    assert scrape_fed_ned.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_uses_public_combo_url(monkeypatch):
    import scrape_fed_ned

    requested = {}

    class Response:
        status_code = 200
        text = "<table></table>"
        url = "https://knas.onzeranglijsten.net/pag/8094/rls/3171"

    def fake_get(url, **kwargs):
        requested["url"] = url
        return Response()

    monkeypatch.setattr(scrape_fed_ned.requests, "get", fake_get)

    assert scrape_fed_ned.fetch_rankings_page("Foil", "Men", "Senior") == "<table></table>"
    assert requested["url"] == "https://knas.onzeranglijsten.net/pag/8094/rls/3171"


def test_ranking_combos_cover_all_required_netherlands_rankings():
    from scrape_fed_ned import RANKING_COMBOS, RANKING_URLS

    expected = {
        (weapon, gender, category)
        for category in ("Senior", "Junior")
        for weapon in ("Foil", "Epee", "Sabre")
        for gender in ("Men", "Women")
    }

    assert set(RANKING_COMBOS) == expected
    assert set(RANKING_URLS) == expected


def test_current_season_uses_july_boundary(monkeypatch):
    import scrape_fed_ned

    class JuneDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 30, tzinfo=timezone.utc)

    class JulyDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(scrape_fed_ned, "datetime", JuneDateTime)
    assert scrape_fed_ned.current_season() == "2025-2026"

    monkeypatch.setattr(scrape_fed_ned, "datetime", JulyDateTime)
    assert scrape_fed_ned.current_season() == "2026-2027"

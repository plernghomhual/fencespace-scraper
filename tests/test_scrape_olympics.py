import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Fixture HTML matches real olympedia /editions/{id}/sports/FEN structure (verified 2026-05-29).
# Rows: [Event Name link→/results/N, Status, Date, Participants, Countries]
EDITION_SPORT_HTML = """
<html><body>
<table class="table">
  <tr><th>Event</th><th>Status</th><th>Date</th><th>Participants</th><th>Countries</th></tr>
  <tr>
    <td><a href="/results/11111">Épée, Individual, Men</a></td>
    <td>Olympic</td><td>20 July 1996</td><td>45</td><td>21</td>
  </tr>
  <tr>
    <td><a href="/results/22222">Foil, Team, Women</a></td>
    <td>Olympic</td><td>25 July 1996</td><td>34</td><td>11</td>
  </tr>
</table>
</body></html>
"""

# Editions listing HTML — rows contain edition links /editions/N and year text.
EDITIONS_HTML = """
<html><body>
<table>
  <tr>
    <td><a href="/editions/24">XXVI</a></td>
    <td>1996</td>
    <td>Atlanta</td>
    <td>Summer</td>
  </tr>
  <tr>
    <td><a href="/editions/25">XXVII</a></td>
    <td>2000</td>
    <td>Sydney</td>
    <td>Summer</td>
  </tr>
  <tr>
    <td><a href="/editions/60">XVII</a></td>
    <td>1994</td>
    <td>Lillehammer</td>
    <td>Winter</td>
  </tr>
</table>
</body></html>
"""

# Real result page structure: H1 = event name, table.table-striped cols:
# [Pos, Number, Competitor, NOC, Medal, ...]
RESULTS_PAGE_HTML = """
<html><body>
<h1>Épée, Individual, Men</h1>
<table class="biodata">
  <tr><td>Date</td><td>20 July 1996</td></tr>
</table>
<table class="table table-striped">
  <tr><th>Pos</th><th>Number</th><th>Competitor</th><th>NOC</th><th></th><th></th><th></th></tr>
  <tr><td>1</td><td>9</td><td><a href="/athletes/99">Éric Srecki</a></td><td>FRA</td><td>Gold</td><td></td><td></td></tr>
  <tr><td>2</td><td>5</td><td><a href="/athletes/88">Ehren Hymmen</a></td><td>GER</td><td>Silver</td><td></td><td></td></tr>
  <tr><td>3</td><td>7</td><td><a href="/athletes/77">Kaido Kaaberma</a></td><td>EST</td><td>Bronze</td><td></td><td></td></tr>
  <tr><td>4</td><td>3</td><td><a href="/athletes/66">Ivan Trevejo</a></td><td>CUB</td><td></td><td></td><td></td></tr>
</table>
</body></html>
"""


def test_parse_edition_sport_page_returns_event_list():
    from scrape_olympics import parse_edition_sport_page
    events = parse_edition_sport_page(EDITION_SPORT_HTML, edition_id="24", edition_name="Atlanta 1996")
    assert len(events) == 2
    assert events[0]["result_id"] == "11111"
    assert events[0]["event_name"] == "Épée, Individual, Men"
    assert events[0]["edition_name"] == "Atlanta 1996"
    assert events[0]["edition_id"] == "24"


def test_parse_results_page_returns_placements():
    from scrape_olympics import parse_results_page
    rows = parse_results_page(RESULTS_PAGE_HTML, result_id="11111")
    assert len(rows) == 4
    gold = rows[0]
    assert gold["rank"] == 1
    assert gold["name"] == "Éric Srecki"
    assert gold["country"] == "FRA"
    assert gold["medal"] == "Gold"
    assert rows[3]["medal"] is None


def test_parse_edition_sport_page_skips_non_result_rows():
    from scrape_olympics import parse_edition_sport_page
    html = "<html><body><table><tr><td>No links here</td></tr></table></body></html>"
    events = parse_edition_sport_page(html, edition_id="1", edition_name="Test 1900")
    assert events == []


def test_classify_event_weapon_gender():
    from scrape_olympics import classify_event
    assert classify_event("Épée, Individual, Men") == {"weapon": "Epee", "gender": "Men", "team": False}
    assert classify_event("Foil, Team, Women") == {"weapon": "Foil", "gender": "Women", "team": True}
    assert classify_event("Sabre, Individual, Men") == {"weapon": "Sabre", "gender": "Men", "team": False}

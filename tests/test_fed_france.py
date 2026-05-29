"""
Tests for scrape_fed_france.py

Site: https://www.ffescrime.fr/classements/
Structure discovered via probe (2026-05-29):
  - Filter query on /classements/ returns /fiche-classements/{id} links
  - Each fiche-classements page has rankings rendered server-side in:
      div.section__table-row > div.row__title > ul > li

  li indices (after stripping mobile-label spans):
    0 = Rang (rank, int)
    1 = Nom (last name, uppercase)
    2 = Prénom (first name)
    3 = Club
    4 = Points (float string like "47190.00")
    5 = row arrow (empty, skip)

  Table header columns: Rang | Nom | Prénom | Club | Points
  Name assembled as: "{LAST} {First}" → "JEAN JOSEPH Kendrick"
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ---------------------------------------------------------------------------
# Fixtures — match real ffescrime.fr fiche-classements page structure
# ---------------------------------------------------------------------------

FIXTURE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Fiche classements détails - FF Escrime</title></head>
<body>
<div class="section__table js-load-more">
  <div class="section__table-head">
    <ul>
      <li>Rang</li>
      <li>Nom</li>
      <li>Prénom</li>
      <li>Club</li>
      <li>Points</li>
    </ul>
  </div>
  <div class="section__table-rows loaded__wrap">

    <div class="section__table-row">
      <div class="row__title">
        <ul data-cla="820" data-light="" data-tir="30743">
          <li><span class="mobile-libelle-detail-classement">Rang :</span>1</li>
          <li><span class="mobile-libelle-detail-classement">Nom :</span>JEAN JOSEPH</li>
          <li><span class="mobile-libelle-detail-classement">Prénom :</span>Kendrick</li>
          <li><span class="mobile-libelle-detail-classement">Club :</span>LEVALLOIS SPORTING CLUB</li>
          <li><span class="mobile-libelle-detail-classement">Points :</span>47190.00</li>
          <li><span class="row__arrow"></span></li>
        </ul>
      </div>
    </div>

    <div class="section__table-row">
      <div class="row__title">
        <ul data-cla="820" data-light="" data-tir="5530">
          <li><span class="mobile-libelle-detail-classement">Rang :</span>2</li>
          <li><span class="mobile-libelle-detail-classement">Nom :</span>BILLA</li>
          <li><span class="mobile-libelle-detail-classement">Prénom :</span>Gaetan</li>
          <li><span class="mobile-libelle-detail-classement">Club :</span>Paris UC escrime</li>
          <li><span class="mobile-libelle-detail-classement">Points :</span>46681.00</li>
          <li><span class="row__arrow"></span></li>
        </ul>
      </div>
    </div>

    <div class="section__table-row">
      <div class="row__title">
        <ul data-cla="820" data-light="" data-tir="9999">
          <li><span class="mobile-libelle-detail-classement">Rang :</span>3</li>
          <li><span class="mobile-libelle-detail-classement">Nom :</span>DUPONT</li>
          <li><span class="mobile-libelle-detail-classement">Prénom :</span>Pierre</li>
          <li><span class="mobile-libelle-detail-classement">Club :</span></li>
          <li><span class="mobile-libelle-detail-classement">Points :</span>12345.50</li>
          <li><span class="row__arrow"></span></li>
        </ul>
      </div>
    </div>

  </div>
</div>
</body>
</html>
"""

FIXTURE_HTML_EMPTY_ROWS = """
<!DOCTYPE html>
<html>
<body>
<div class="section__table js-load-more">
  <div class="section__table-head">
    <ul>
      <li>Rang</li><li>Nom</li><li>Prénom</li><li>Club</li><li>Points</li>
    </ul>
  </div>
  <div class="section__table-rows loaded__wrap">
  </div>
</div>
</body>
</html>
"""

FIXTURE_HTML_NO_TABLE = """
<!DOCTYPE html>
<html>
<body><p>Aucun classement disponible.</p></body>
</html>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_parse_fff_rankings_returns_rows():
    from scrape_fed_france import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)

    assert len(rows) == 3

    first = rows[0]
    assert first["rank"] == 1
    assert first["name"] == "JEAN JOSEPH Kendrick"
    assert first["club"] == "LEVALLOIS SPORTING CLUB"
    assert first["points"] == 47190.0

    second = rows[1]
    assert second["rank"] == 2
    assert second["name"] == "BILLA Gaetan"
    assert second["club"] == "Paris UC escrime"
    assert second["points"] == 46681.0


def test_parse_fff_rankings_empty_club_is_none():
    from scrape_fed_france import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)
    third = rows[2]
    assert third["rank"] == 3
    assert third["name"] == "DUPONT Pierre"
    # Empty club string should become None
    assert third["club"] is None
    assert third["points"] == 12345.5


def test_parse_fff_rankings_empty():
    from scrape_fed_france import parse_rankings_table

    # Empty rows div
    rows = parse_rankings_table(FIXTURE_HTML_EMPTY_ROWS)
    assert rows == []

    # No section__table-row divs at all
    rows = parse_rankings_table(FIXTURE_HTML_NO_TABLE)
    assert rows == []


def test_parse_fff_rankings_row_types():
    from scrape_fed_france import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML)
    assert len(rows) == 3
    for r in rows:
        assert isinstance(r["rank"], int)
        assert isinstance(r["name"], str) and r["name"]
        assert r["club"] is None or isinstance(r["club"], str)
        assert isinstance(r["points"], float)

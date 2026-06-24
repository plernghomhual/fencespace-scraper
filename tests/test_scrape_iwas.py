from bs4 import BeautifulSoup

from scrape_iwas import parse_event_label, parse_ranking_overview, parse_ranking_page, parse_results_page

OVERVIEW_HTML = """
<html><body>
<table>
  <tr>
    <th></th>
    <th>Epee female</th>
    <th>Epee male</th>
    <th>Foil female</th>
  </tr>
  <tr>
    <td>Senior A</td>
    <td><a href="/en/search/rankings/show/910">Rankings</a></td>
    <td><a href="/en/search/rankings/show/911">Rankings</a></td>
    <td><a href="/en/search/rankings/show/912">Rankings</a></td>
  </tr>
  <tr>
    <td>Senior B</td>
    <td><a href="/en/search/rankings/show/920">Rankings</a></td>
    <td></td>
    <td></td>
  </tr>
</table>
</body></html>
"""

DETAIL_HTML = """
<html><body>
<div class="card-body">
  <table class="table table-striped">
    <thead>
      <tr><th>Rank</th><th>Points</th><th>Name</th><th>Nation</th><th>YOB</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>196.0</td><td>KIM Jiyeon</td><td>KOR</td><td>1985</td></tr>
      <tr><td>2</td><td>180.5</td><td>SMITH Jane</td><td>GBR</td><td>1990</td></tr>
      <tr><td>3</td><td>150.0</td><td>ZHANG Wei</td><td>CHN</td><td>1992</td></tr>
    </tbody>
  </table>
</div>
</body></html>
"""

RESULTS_HTML = """
<html><body>
<h1>2023 World Para Fencing Championships</h1>
<div>
  <h4>Epee male Senior Individual A</h4>
  <table class="table table-striped">
    <thead>
      <tr><th>Rank</th><th>Status</th><th>Round</th><th>Name</th><th>YOB</th><th>Gender</th><th>&#160;</th><th>Nation</th><th>Club</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>N</td><td></td><td>LAMBERTINI Emanuele</td><td>1999</td><td>M</td><td>A</td><td>ITA</td><td>ASD</td></tr>
      <tr><td>2</td><td>N</td><td></td><td>LEE Taewon</td><td>1990</td><td>M</td><td>A</td><td>KOR</td><td></td></tr>
    </tbody>
  </table>
  <h4>Foil female Senior Individual B</h4>
  <table class="table table-striped">
    <thead>
      <tr><th>Rank</th><th>Status</th><th>Round</th><th>Name</th><th>YOB</th><th>Gender</th><th>&#160;</th><th>Nation</th><th>Club</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>N</td><td></td><td>WANG Fang</td><td>1988</td><td>F</td><td>B</td><td>CHN</td><td></td></tr>
    </tbody>
  </table>
</div>
</body></html>
"""


def test_parse_ranking_overview_returns_entries():
    entries = parse_ranking_overview(OVERVIEW_HTML)
    assert len(entries) == 4  # 3 in Senior A row + 1 in Senior B row


def test_parse_ranking_overview_fields():
    entries = parse_ranking_overview(OVERVIEW_HTML)
    first = entries[0]
    assert first["id"] == 910
    assert first["weapon"] == "Epee"
    assert first["gender"] == "Women"
    assert first["category"] == "Senior A"


def test_parse_ranking_overview_second_weapon():
    entries = parse_ranking_overview(OVERVIEW_HTML)
    assert entries[1]["id"] == 911
    assert entries[1]["weapon"] == "Epee"
    assert entries[1]["gender"] == "Men"
    assert entries[1]["category"] == "Senior A"


def test_parse_ranking_overview_skips_empty_cells():
    entries = parse_ranking_overview(OVERVIEW_HTML)
    senior_b = [e for e in entries if e["category"] == "Senior B"]
    assert len(senior_b) == 1
    assert senior_b[0]["id"] == 920


def test_parse_ranking_page_returns_rows():
    rows = parse_ranking_page(DETAIL_HTML)
    assert len(rows) == 3


def test_parse_ranking_page_fields():
    rows = parse_ranking_page(DETAIL_HTML)
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "KIM Jiyeon"
    assert rows[0]["country"] == "KOR"
    assert rows[0]["points"] == 196.0


def test_parse_ranking_page_empty_returns_empty():
    rows = parse_ranking_page("<html><body></body></html>")
    assert rows == []


def test_parse_ranking_page_skips_header_rows():
    rows = parse_ranking_page(DETAIL_HTML)
    assert not any(r["name"].lower() == "name" for r in rows)


def test_parse_ranking_page_points_as_float():
    rows = parse_ranking_page(DETAIL_HTML)
    for r in rows:
        assert r["points"] is None or isinstance(r["points"], float)


def test_parse_event_label_epee_male_senior_a():
    weapon, gender, category = parse_event_label("Epee male Senior Individual A")
    assert weapon == "Epee"
    assert gender == "Men"
    assert category == "Senior A"


def test_parse_event_label_foil_female_senior_b():
    weapon, gender, category = parse_event_label("Foil female Senior Individual B")
    assert weapon == "Foil"
    assert gender == "Women"
    assert category == "Senior B"


def test_parse_event_label_sabre_male_u23_c():
    weapon, gender, category = parse_event_label("Sabre male U23 Individual C")
    assert weapon == "Sabre"
    assert gender == "Men"
    assert category == "U23 C"


def test_parse_results_page_returns_events():
    events = parse_results_page(RESULTS_HTML)
    assert len(events) == 2


def test_parse_results_page_event_fields():
    events = parse_results_page(RESULTS_HTML)
    e = events[0]
    assert e["weapon"] == "Epee"
    assert e["gender"] == "Men"
    assert e["category"] == "Senior A"
    assert len(e["rows"]) == 2
    assert e["rows"][0]["rank"] == 1
    assert e["rows"][0]["name"] == "LAMBERTINI Emanuele"
    assert e["rows"][0]["country"] == "ITA"


def test_parse_results_page_second_event():
    events = parse_results_page(RESULTS_HTML)
    e = events[1]
    assert e["weapon"] == "Foil"
    assert e["gender"] == "Women"
    assert e["category"] == "Senior B"

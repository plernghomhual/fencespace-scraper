import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")


TOURNAMENT_LISTING_JSON = json.dumps({
    "events": [
        {
            "org": "life",
            "ev": "em15cp",
            "title": "Championnat de Paris M15",
            "date_from": "2026-05-31",
            "date_to": "2026-05-31",
            "ioc_organisme": "FRA",
            "ioc_competition": "FRA",
            "city": "Paris Montparnasse",
            "competitions": 4,
        }
    ],
    "last": 1,
    "page": 1,
})


ORGANISM_LISTING_JSON = json.dumps({
    "status": "ok",
    "result": [
        {
            "Organisme": "scfu",
            "Event": "syt25",
            "Titre": "Surrey Youth Team 2025",
            "date": "2025-06-29",
            "compet": "5",
        }
    ],
})


RESULTS_HTML = """
<!doctype html>
<html>
<body>
  <h3>Villa de Madrid MEN SABRE 23-24 MAY 2025</h3>
  <h3>Overall ranking (258 fencers)</h3>
  <table>
    <tr><th>Rank</th><th>Name</th><th>First name</th><th>Country</th><th>Status</th></tr>
    <tr><td>1</td><td>BAZADZE</td><td>Sandro</td><td>GEO</td><td></td></tr>
    <tr><td>2</td><td>YILDIRIM</td><td>Enver</td><td>TUR</td><td></td></tr>
    <tr><td>3</td><td>PARK</td><td>Sangwon</td><td>KOR</td><td></td></tr>
  </table>
</body>
</html>
"""


SPANISH_RESULTS_HTML = """
<!doctype html>
<html>
<body>
  <table>
    <tr><th>Cl.</th><th>Apellido-nom</th><th>Nombre</th><th>Club</th></tr>
    <tr><td>1</td><td>GONZALEZ CARVAJAL MARTINEZ</td><td>Joaquin</td><td>CE-M</td></tr>
  </table>
</body>
</html>
"""


UKRAINIAN_RESULTS_HTML = """
<!doctype html>
<html>
<body>
  <table>
    <tr><th>№</th><th>Прізвище</th><th>Ім'я</th><th>Спорт.організація</th><th>Статус</th></tr>
    <tr><td>1</td><td>СТАЦЕНКО</td><td>Олексій</td><td>ДШВСМ, ЗСУ</td><td></td></tr>
  </table>
</body>
</html>
"""


POOL_HTML = """
<!doctype html>
<html>
<body>
  <h3>Poules</h3>
  <table>
    <tr><td>Poule No 1</td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>RABB Krisztian</td><td>HUN</td><td></td><td></td><td>V</td><td>3</td></tr>
    <tr><td>MAKLAKOV Julian</td><td>GER</td><td></td><td>2</td><td></td><td>V</td></tr>
    <tr><td>FARRE Oriol</td><td>ESP</td><td></td><td>V</td><td>4</td><td></td></tr>
  </table>
</body>
</html>
"""


DE_HTML = """
<!doctype html>
<html>
<body>
  <h3>Main tableau of 64</h3>
  <table>
    <tr><td></td><td>Main tableau of 64</td><td></td><td>Main tableau of 32</td></tr>
    <tr><td>1</td><td>OH Sanguk</td><td>KOR</td><td></td></tr>
    <tr><td></td><td>10:00 Piste BLUE Referee: OCHOTORENA Jose Luis ESP</td><td></td><td>OH Sanguk KOR</td></tr>
    <tr><td>64</td><td>KOVAL Stsiapan</td><td>AIN_</td><td>15/10</td></tr>
    <tr><td>33</td><td>ILIASZ Nicolas</td><td>HUN</td><td></td></tr>
    <tr><td></td><td>10:15 Piste BLUE Referee: JEANNY Aurelie FRA</td><td></td><td>ILIASZ Nicolas HUN</td></tr>
    <tr><td>32</td><td>SARON Mitchell</td><td>USA</td><td>15/12</td></tr>
  </table>
</body>
</html>
"""


def test_parse_tournament_listing():
    from scrape_engarde import parse_tournament_listing

    rows = parse_tournament_listing(TOURNAMENT_LISTING_JSON, "global_recent")
    org_rows = parse_tournament_listing(ORGANISM_LISTING_JSON, "uk_scfu")

    assert rows[0]["event_id"] == "em15cp"
    assert rows[0]["name"] == "Championnat de Paris M15"
    assert rows[0]["start_date"] == "2026-05-31"
    assert rows[0]["organism"] == "life"
    assert rows[0]["source_id"] == "engarde:global_recent:life:em15cp"
    assert org_rows[0]["event_id"] == "syt25"
    assert org_rows[0]["name"] == "Surrey Youth Team 2025"
    assert org_rows[0]["start_date"] == "2025-06-29"


def test_parse_results_table():
    from scrape_engarde import parse_results_table

    rows = parse_results_table(RESULTS_HTML)

    assert len(rows) == 3
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Sandro Bazadze"
    assert rows[0]["last_name"] == "Bazadze"
    assert rows[0]["first_name"] == "Sandro"
    assert rows[0]["country"] == "GEO"
    assert rows[1]["name"] == "Enver Yildirim"


def test_parse_results_table_handles_live_spanish_headers():
    from scrape_engarde import parse_results_table

    rows = parse_results_table(SPANISH_RESULTS_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "Joaquin Gonzalez Carvajal Martinez",
            "last_name": "Gonzalez Carvajal Martinez",
            "first_name": "Joaquin",
            "club": "CE-M",
            "country": None,
            "raw_cells": ["1", "GONZALEZ CARVAJAL MARTINEZ", "Joaquin", "CE-M"],
        }
    ]


def test_parse_results_table_handles_live_cyrillic_headers():
    from scrape_engarde import parse_results_table

    rows = parse_results_table(UKRAINIAN_RESULTS_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "Олексій Стаценко",
            "last_name": "Стаценко",
            "first_name": "Олексій",
            "club": "ДШВСМ, ЗСУ",
            "country": None,
            "raw_cells": ["1", "СТАЦЕНКО", "Олексій", "ДШВСМ, ЗСУ", ""],
        }
    ]


def test_parse_pool_bouts():
    from scrape_engarde import parse_pool_bouts

    bouts = parse_pool_bouts(POOL_HTML)

    assert len(bouts) == 3
    assert bouts[0]["round"] == "Poule No 1"
    assert bouts[0]["fencer_a"] == "RABB Krisztian"
    assert bouts[0]["country_a"] == "HUN"
    assert bouts[0]["score_a"] == 5
    assert bouts[0]["fencer_b"] == "MAKLAKOV Julian"
    assert bouts[0]["country_b"] == "GER"
    assert bouts[0]["score_b"] == 2
    assert bouts[1]["score_a"] == 3
    assert bouts[1]["score_b"] == 5


def test_parse_de_bouts():
    from scrape_engarde import parse_de_bouts

    bouts = parse_de_bouts(DE_HTML)

    assert len(bouts) == 2
    assert bouts[0]["round"] == "Main tableau of 64"
    assert bouts[0]["fencer_a"] == "OH Sanguk"
    assert bouts[0]["country_a"] == "KOR"
    assert bouts[0]["score_a"] == 15
    assert bouts[0]["fencer_b"] == "KOVAL Stsiapan"
    assert bouts[0]["country_b"] == "AIN_"
    assert bouts[0]["score_b"] == 10
    assert bouts[1]["fencer_a"] == "ILIASZ Nicolas"
    assert bouts[1]["score_a"] == 15
    assert bouts[1]["fencer_b"] == "SARON Mitchell"
    assert bouts[1]["score_b"] == 12


def test_empty_tournament():
    from scrape_engarde import parse_results_table

    assert parse_results_table("<html><body><p>No results available.</p></body></html>") == []


def test_404_handled(monkeypatch):
    from scrape_engarde import EngardeClient

    client = EngardeClient(request_delay=0, max_retries=1)

    def fake_request(method, url, timeout=30, **kwargs):
        return SimpleNamespace(status_code=404, text="Not found", headers={"content-type": "text/html"})

    monkeypatch.setattr(client.session, "request", fake_request)

    assert client.get_text("https://engarde-service.com/missing") is None

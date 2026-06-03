import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FRENCH_HTML = """
<html><body>
<h2>Fleuret Dames Senior - 25 juin 2025</h2>
<table>
  <tr><th>Rang</th><th>Tireuse</th><th>Pays</th><th>Médaille</th><th>Points</th><th>ID FIE</th></tr>
  <tr><td>1</td><td>TANTAST Yasmine</td><td>Algérie</td><td>or</td><td>64,5</td><td>12345</td></tr>
  <tr><td>2</td><td>EL SAYED Nada</td><td>Égypte</td><td>argent</td><td>52</td><td></td></tr>
</table>
</body></html>
"""


ARABIC_HTML = """
<html><body>
<h2>سيف المبارزة رجال فردي - 26 يونيو 2025</h2>
<table>
  <tr><th>الترتيب</th><th>اللاعب</th><th>الدولة</th><th>النقاط</th></tr>
  <tr><td>1</td><td>محمد السيد</td><td>مصر</td><td>48</td></tr>
  <tr><td>3=</td><td>أحمد السكري</td><td>تونس</td><td></td></tr>
</table>
</body></html>
"""


SPARSE_ENGLISH_HTML = """
<html><body>
<h3>Women's Sabre Teams</h3>
<table>
  <tr><th>Place</th><th>Team</th><th>Nation</th></tr>
  <tr><td>1.</td><td>Egypt</td><td>EGY</td></tr>
  <tr><td>2.</td><td>South Africa</td><td>RSA</td></tr>
  <tr><td>DNS</td><td>Morocco</td><td>MAR</td></tr>
</table>
</body></html>
"""


FENCINGWORLDWIDE_TEXT = """
African Championships 2025
Lagos, Nigeria
Results for Women's Foil Individual
25 June 2025
Final Ranking
1. ALG TANTAST Yasmine
2. EGY EL SAYED Nada
3. CIV AHOUADI Estelle
T5. RSA VAN TONDER Petra Did not start
"""


def test_parse_html_result_events_normalizes_french_rows():
    from scrape_african_conf import parse_html_result_events

    events = parse_html_result_events(FRENCH_HTML, source_url="https://www.cae-fencing.org/resultats-2025")

    assert len(events) == 1
    event = events[0]
    assert event["event_name"] == "Fleuret Dames Senior - 25 juin 2025"
    assert event["event_date"] == "2025-06-25"
    assert event["classification"] == {"weapon": "Foil", "gender": "Women", "category": "Senior", "team": False}
    assert event["results"] == [
        {
            "rank": 1,
            "name": "Yasmine Tantast",
            "country": "ALG",
            "medal": "Gold",
            "points": 64.5,
            "fie_id": "12345",
            "source_url": "https://www.cae-fencing.org/resultats-2025",
        },
        {
            "rank": 2,
            "name": "Nada El Sayed",
            "country": "EGY",
            "medal": "Silver",
            "points": 52.0,
            "fie_id": None,
            "source_url": "https://www.cae-fencing.org/resultats-2025",
        },
    ]


def test_parse_html_result_events_normalizes_arabic_rows():
    from scrape_african_conf import parse_html_result_events

    events = parse_html_result_events(ARABIC_HTML, source_url="https://example.test/arabic-results")

    assert len(events) == 1
    event = events[0]
    assert event["event_date"] == "2025-06-26"
    assert event["classification"] == {"weapon": "Epee", "gender": "Men", "category": "Senior", "team": False}
    assert event["results"] == [
        {
            "rank": 1,
            "name": "محمد السيد",
            "country": "EGY",
            "medal": "Gold",
            "points": 48.0,
            "fie_id": None,
            "source_url": "https://example.test/arabic-results",
        },
        {
            "rank": 3,
            "name": "أحمد السكري",
            "country": "TUN",
            "medal": "Bronze",
            "points": None,
            "fie_id": None,
            "source_url": "https://example.test/arabic-results",
        },
    ]


def test_parse_html_result_events_handles_sparse_team_tables():
    from scrape_african_conf import parse_html_result_events

    events = parse_html_result_events(
        SPARSE_ENGLISH_HTML,
        source_url="https://www.fencingworldwide.com/en/30332-2025/results/",
        default_date="2025-06-27",
    )

    assert len(events) == 1
    event = events[0]
    assert event["classification"] == {"weapon": "Sabre", "gender": "Women", "category": "Senior", "team": True}
    assert event["results"] == [
        {
            "rank": 1,
            "name": "Egypt",
            "country": "EGY",
            "medal": "Gold",
            "points": None,
            "fie_id": None,
            "source_url": "https://www.fencingworldwide.com/en/30332-2025/results/",
        },
        {
            "rank": 2,
            "name": "South Africa",
            "country": "RSA",
            "medal": "Silver",
            "points": None,
            "fie_id": None,
            "source_url": "https://www.fencingworldwide.com/en/30332-2025/results/",
        },
    ]


def test_parse_fencingworldwide_text_result_page_preserves_source_evidence():
    from scrape_african_conf import parse_fencingworldwide_text_result_page

    event = parse_fencingworldwide_text_result_page(
        FENCINGWORLDWIDE_TEXT,
        source_url="https://www.fencingworldwide.com/en/4642-2025/results/",
    )

    assert event["edition_name"] == "African Championships 2025 - Lagos, Nigeria"
    assert event["event_name"] == "Women's Foil Individual"
    assert event["event_date"] == "2025-06-25"
    assert event["source_kind"] == "fencingworldwide_text"
    assert event["results"] == [
        {
            "rank": 1,
            "name": "Yasmine Tantast",
            "country": "ALG",
            "medal": "Gold",
            "points": None,
            "fie_id": None,
            "source_url": "https://www.fencingworldwide.com/en/4642-2025/results/",
        },
        {
            "rank": 2,
            "name": "Nada El Sayed",
            "country": "EGY",
            "medal": "Silver",
            "points": None,
            "fie_id": None,
            "source_url": "https://www.fencingworldwide.com/en/4642-2025/results/",
        },
        {
            "rank": 3,
            "name": "Estelle Ahouadi",
            "country": "CIV",
            "medal": "Bronze",
            "points": None,
            "fie_id": None,
            "source_url": "https://www.fencingworldwide.com/en/4642-2025/results/",
        },
    ]


def test_no_public_data_stub_documents_probed_sources():
    from scrape_african_conf import build_no_public_data_stub

    stub = build_no_public_data_stub(
        [
            {"url": "https://afrique-escrime.org/resultats", "status": 404, "reason": "placeholder mirror"},
            {"url": "https://www.fencingtimelive.com/tournaments/eventSchedule/x", "status": 200, "reason": "login required"},
        ]
    )

    assert stub["source_kind"] == "no_public_data_stub"
    assert stub["results"] == []
    assert stub["skipped_reason"] == "no durable public African championship result rows found"
    assert stub["probe_results"][1]["reason"] == "login required"


class FakeHttpResponse:
    def __init__(self, url, text, status_code=200, content_type="text/html"):
        self.url = url
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code
        self.headers = {"content-type": content_type}


class FakeHttpSession:
    def __init__(self, pages):
        self.pages = pages
        self.headers = {}
        self.requested = []

    def get(self, url, timeout=25, allow_redirects=True):
        self.requested.append(url)
        response = self.pages[url]
        return FakeHttpResponse(url, response)


def test_discover_events_follows_public_tournament_result_links(monkeypatch):
    import scrape_african_conf

    tournament_url = "https://www.fencingworldwide.com/en/30332-2025/tournament/"
    result_url = "https://www.fencingworldwide.com/en/4642-2025/results/"
    session = FakeHttpSession(
        {
            tournament_url: f'<html><body><a href="{result_url}">Results</a></body></html>',
            result_url: FENCINGWORLDWIDE_TEXT,
        }
    )
    monkeypatch.setattr(scrape_african_conf, "PROBE_URLS", [])
    monkeypatch.setattr(scrape_african_conf, "KNOWN_PUBLIC_SOURCES", [tournament_url])
    monkeypatch.setattr(scrape_african_conf, "REQUEST_DELAY", 0)

    events, probe_results = scrape_african_conf.discover_events(session=session)

    assert probe_results == []
    assert session.requested == [tournament_url, result_url]
    assert events[0]["source_url"] == result_url
    assert events[0]["event_code"] == "women-foil-individual"


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.contains_filters = []
        self.inserted = None

    def select(self, columns):
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def contains(self, column, value):
        self.contains_filters.append((column, value))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def delete(self):
        self.client.deleted.append(self.table_name)
        return self

    def insert(self, rows):
        self.inserted = rows
        self.client.inserted.extend(rows)
        return self

    def execute(self):
        if self.table_name == "fs_fencer_identities":
            if ("fie_ids", ["12345"]) in self.contains_filters:
                return FakeResponse([{"id": "identity-fie", "fs_fencer_row_ids": ["fencer-by-fie"]}])
            filter_map = {(op, col): val for op, col, val in self.filters}
            if filter_map.get(("ilike", "canonical_name")) == "Identity Match" and filter_map.get(("eq", "country")) == "EGY":
                return FakeResponse([{"id": "identity-name", "fs_fencer_row_ids": ["fencer-by-identity"]}])
        if self.table_name == "fs_fencers":
            filter_map = {(op, col): val for op, col, val in self.filters}
            if filter_map.get(("eq", "fie_id")) == "999":
                return FakeResponse([{"id": "fencer-direct-fie"}])
            if filter_map.get(("ilike", "name")) == "Direct Match" and filter_map.get(("eq", "country")) == "RSA":
                return FakeResponse([{"id": "fencer-direct-name"}])
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.inserted = []
        self.deleted = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_upsert_results_matches_fie_id_then_identity_then_name_country_and_skips_unmatched(monkeypatch):
    import scrape_african_conf

    fake = FakeClient()
    monkeypatch.setattr(scrape_african_conf, "supabase", fake)

    summary = scrape_african_conf.upsert_results(
        tournament_id="tournament-1",
        result_rows=[
            {"rank": 1, "name": "Ignored Name", "country": "ALG", "medal": "Gold", "fie_id": "12345"},
            {"rank": 2, "name": "Identity Match", "country": "EGY", "medal": "Silver", "fie_id": None},
            {"rank": 3, "name": "Direct Match", "country": "RSA", "medal": "Bronze", "fie_id": "999"},
            {"rank": 4, "name": "Unmatched Person", "country": "TUN", "medal": None, "fie_id": None},
        ],
        team=False,
    )

    assert summary["written"] == 3
    assert summary["skipped"] == 1
    assert [(row["name"], row["fencer_id"]) for row in fake.inserted] == [
        ("Ignored Name", "fencer-by-fie"),
        ("Identity Match", "fencer-by-identity"),
        ("Direct Match", "fencer-direct-fie"),
    ]
    assert all(row["fencer_id"] for row in fake.inserted)
    assert summary["unmatched"][0]["reason"] == "unmatched_fencer"
    assert summary["unmatched"][0]["name"] == "Unmatched Person"


def test_upsert_results_allows_team_country_rows_without_fencer_id(monkeypatch):
    import scrape_african_conf

    fake = FakeClient()
    monkeypatch.setattr(scrape_african_conf, "supabase", fake)

    summary = scrape_african_conf.upsert_results(
        tournament_id="team-tournament",
        result_rows=[{"rank": 1, "name": "Egypt", "country": "EGY", "medal": "Gold", "fie_id": None}],
        team=True,
    )

    assert summary["written"] == 1
    assert summary["skipped"] == 0
    assert fake.inserted[0]["fencer_id"] is None
    assert fake.inserted[0]["metadata"]["team"] is True

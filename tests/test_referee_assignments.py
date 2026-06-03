import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")


FIE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Competition ID="gp-2026" Nom="Grand Prix Foil">
  <Arbitres>
    <Arbitre ID="101" Licence="2380" Nom="ABAJO" Prenom="Jose Luis" Nation="ESP" />
    <Arbitre ID="102" Licence="18437" Nom="SMITH" Prenom="Jane" Nation="USA" />
  </Arbitres>
  <Phase Libelle="Tableau of 16">
    <Match ID="m-1" No="5" Piste="BLUE">
      <Arbitres>
        <Arbitre REF="101" Role="P" />
        <Arbitre REF="102" Role="V" />
      </Arbitres>
    </Match>
    <Match ID="m-2" No="6" Piste="RED" />
  </Phase>
</Competition>
"""


ENGARDE_HTML = """
<html>
<body>
  <h2>Main tableau of 64</h2>
  <table>
    <tr><td>16</td><td>OH Sanguk</td><td>KOR</td><td>15/10</td></tr>
    <tr>
      <td></td>
      <td>10:15 Piste BLUE Referee: JEANNY Aurelie FRA; Video Referee: ROSSI Marco ITA</td>
      <td></td><td>KOVAL Stsiapan AIN_</td>
    </tr>
    <tr><td>32</td><td>SARON Mitchell</td><td>USA</td><td>15/12</td></tr>
    <tr><td></td><td>11:00 Piste RED</td><td></td><td>ILIASZ Nicolas HUN</td></tr>
  </table>
</body>
</html>
"""


PDF_TEXT = """
FEDERATION INTERNATIONALE D'ESCRIME
Bout 17 Round Tableau of 32 Piste YELLOW
Referee: KIM Min Su KOR ID 7788
Video Referee: GARCIA Ana ESP
Bout 18 Round Tableau of 32 Piste GREEN
"""


API_JSON = {
    "eventId": "api-event-1",
    "bouts": [
        {
            "id": "api-bout-9",
            "round": "Tableau of 8",
            "piste": "GREEN",
            "referees": [
                {
                    "id": "2380",
                    "name": "ABAJO Jose Luis",
                    "country": "ESP",
                    "role": "referee",
                },
                {
                    "name": "SMITH Jane",
                    "country": "USA",
                    "role": "assistant referee",
                },
            ],
        }
    ],
}


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeResponse:
    def __init__(self, text, status_code=200, content_type="text/html"):
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        return self.responses.pop(0)


class FakeTable:
    def __init__(self, name, client):
        self.name = name
        self.client = client
        self.operation = None
        self.payload = None
        self.on_conflict = None
        self.filters = []

    def upsert(self, rows, on_conflict=None):
        self.operation = "upsert"
        self.payload = rows
        self.on_conflict = on_conflict
        self.client.upserts.append((self.name, rows, on_conflict))
        return self

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.name, columns))
        return self

    @property
    def not_(self):
        return self

    def is_(self, column, value):
        self.filters.append(("not_is", column, value))
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, value):
        return self

    def execute(self):
        if self.operation == "select" and self.name == "fs_tournaments":
            return FakeResult(self.client.tournaments)
        return FakeResult([])


class FakeClient:
    def __init__(self, tournaments=None):
        self.tournaments = tournaments or []
        self.upserts = []
        self.selects = []

    def table(self, name):
        return FakeTable(name, self)


def test_parse_fie_xml_assignments_handles_multiple_refs_and_missing_bout():
    from scrape_referee_assignments import parse_fie_xml_assignments

    rows = parse_fie_xml_assignments(
        FIE_XML,
        source_url="https://static.fie.org/results.xml",
        tournament_id="t-1",
        event_id="foil-men",
    )

    assert len(rows) == 3
    assert rows[0]["referee_name"] == "ABAJO Jose Luis"
    assert rows[0]["referee_fie_id"] == "101"
    assert rows[0]["referee_fie_license_id"] == "2380"
    assert rows[0]["country"] == "ESP"
    assert rows[0]["role"] == "primary"
    assert rows[1]["role"] == "video"
    assert rows[1]["referee_name"] == "SMITH Jane"
    assert rows[0]["piste"] == "BLUE"
    assert rows[0]["round"] == "Tableau of 16"
    assert rows[2]["assignment_status"] == "missing"
    assert rows[2]["referee_name"] is None
    assert rows[2]["bout_source_id"] == "m-2"


def test_parse_engarde_html_keeps_name_only_refs_unlinked():
    from scrape_referee_assignments import parse_engarde_html_assignments

    rows = parse_engarde_html_assignments(
        ENGARDE_HTML,
        source_url="https://engarde-service.com/competition/example/tableau64.htm",
        tournament_id="t-1",
    )

    assigned = [row for row in rows if row["assignment_status"] == "assigned"]
    missing = [row for row in rows if row["assignment_status"] == "missing"]

    assert len(assigned) == 2
    assert assigned[0]["referee_name"] == "JEANNY Aurelie"
    assert assigned[0]["country"] == "FRA"
    assert assigned[0]["role"] == "primary"
    assert assigned[0]["piste"] == "BLUE"
    assert assigned[0]["referee_id"] is None
    assert assigned[0]["referee_fie_id"] is None
    assert assigned[1]["referee_name"] == "ROSSI Marco"
    assert assigned[1]["role"] == "video"
    assert missing[0]["piste"] == "RED"


def test_parse_engarde_html_handles_adjacent_role_labels_without_semicolon():
    from scrape_referee_assignments import parse_engarde_html_assignments

    html = """
    <html><body>
      <h2>Tableau of 8</h2>
      <table>
        <tr><td></td><td>12:00 Piste GREEN Referee: DOE Jane USA Video Referee: ROE John CAN</td></tr>
      </table>
    </body></html>
    """

    rows = parse_engarde_html_assignments(
        html,
        source_url="https://engarde-service.com/competition/example/tableau8.htm",
        tournament_id="t-1",
    )

    assert [(row["role"], row["referee_name"], row["country"]) for row in rows] == [
        ("primary", "DOE Jane", "USA"),
        ("video", "ROE John", "CAN"),
    ]


def test_parse_api_assignments_preserves_ids_and_name_only_rows():
    from scrape_referee_assignments import parse_api_assignments

    rows = parse_api_assignments(
        json.dumps(API_JSON),
        source_url="https://results.example.test/api/bouts",
        tournament_id="t-1",
    )

    assert [row["role"] for row in rows] == ["primary", "assistant"]
    assert rows[0]["referee_name"] == "ABAJO Jose Luis"
    assert rows[0]["referee_fie_id"] == "2380"
    assert rows[1]["referee_name"] == "SMITH Jane"
    assert rows[1]["referee_fie_id"] is None
    assert rows[1]["referee_id"] is None
    assert rows[0]["source_key"] != rows[1]["source_key"]


def test_parse_pdf_text_assignments_handles_multiple_refs_and_empty_bout():
    from scrape_referee_assignments import parse_pdf_text_assignments

    rows = parse_pdf_text_assignments(
        PDF_TEXT,
        source_url="https://static.fie.org/bout-sheet.pdf",
        tournament_id="t-1",
    )

    assert len(rows) == 3
    assert rows[0]["bout_source_id"] == "17"
    assert rows[0]["round"] == "Tableau of 32"
    assert rows[0]["piste"] == "YELLOW"
    assert rows[0]["referee_name"] == "KIM Min Su"
    assert rows[0]["referee_fie_id"] == "7788"
    assert rows[1]["role"] == "video"
    assert rows[1]["referee_name"] == "GARCIA Ana"
    assert rows[2]["assignment_status"] == "missing"
    assert rows[2]["bout_source_id"] == "18"


def test_blocked_live_result_source_returns_stub_status():
    from scrape_referee_assignments import parse_assignment_content

    login_html = """
    <html><body><h1>Login required</h1><form><input type="password" /></form></body></html>
    """

    result = parse_assignment_content(
        login_html.encode("utf-8"),
        content_type="text/html",
        source_url="https://www.fencingtimelive.com/tournaments/eventSchedule/abc",
        tournament_id="t-1",
    )

    assert result.rows == []
    assert result.blocked is True
    assert result.reason == "login_required"


def test_upsert_assignments_dedupes_only_by_source_key_not_name_identity():
    from scrape_referee_assignments import build_assignment_row, upsert_assignments

    first = build_assignment_row(
        tournament_id="t-1",
        event_id="foil-men",
        bout_source_id="bout-1",
        referee_name="JEANNY Aurelie",
        country="FRA",
        role="primary",
        piste="BLUE",
        round_name="Tableau of 64",
        source_url="https://engarde-service.com/a/tableau64.htm",
    )
    duplicate = dict(first)
    second_bout_same_name = build_assignment_row(
        tournament_id="t-1",
        event_id="foil-men",
        bout_source_id="bout-2",
        referee_name="JEANNY Aurelie",
        country="FRA",
        role="primary",
        piste="RED",
        round_name="Tableau of 64",
        source_url="https://engarde-service.com/a/tableau64.htm",
    )
    client = FakeClient()

    written = upsert_assignments(client, [first, duplicate, second_bout_same_name])

    assert written == 2
    assert client.upserts == [
        ("fs_referee_assignments", [first, second_bout_same_name], "source_key")
    ]


def test_scrape_referee_assignments_fetches_public_sources_and_skips_blocked(monkeypatch):
    from scrape_referee_assignments import scrape_referee_assignments

    client = FakeClient()
    session = FakeSession(
        [
            FakeResponse(json.dumps(API_JSON), content_type="application/json"),
            FakeResponse(
                "<html><body><form><input type='password' /></form>Login required</body></html>",
                content_type="text/html",
            ),
        ]
    )
    states = []
    monkeypatch.setattr(
        "scrape_referee_assignments.set_state",
        lambda source, key, value: states.append((source, key, value)),
    )

    summary = scrape_referee_assignments(
        client=client,
        session=session,
        sources=[
            {
                "source_url": "https://results.example.test/api/bouts",
                "tournament_id": "t-1",
                "event_id": "api-event-1",
            },
            {
                "source_url": "https://www.fencingtimelive.com/tournaments/eventSchedule/abc",
                "tournament_id": "t-2",
            },
        ],
        delay=0,
        log_run=False,
    )

    assert summary["written"] == 2
    assert summary["blocked"] == 1
    assert summary["failed"] == 0
    assert client.upserts[0][0] == "fs_referee_assignments"
    assert all(call[0] != "fs_referees" for call in client.upserts)
    assert states[-1][0:2] == ("referee_assignments", "last_run")
    assert states[-1][2]["written"] == 2


def test_referee_assignments_migration_defines_table_shape_and_indexes():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_referee_assignments.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_referee_assignments" in normalized
    assert "source_key text not null unique" in normalized
    assert "tournament_id uuid references public.fs_tournaments(id)" in normalized
    assert "event_id text" in normalized
    assert "bout_id text" in normalized
    assert "referee_id uuid references public.fs_referees(id)" in normalized
    assert "referee_name text" in normalized
    assert "referee_fie_id text" in normalized
    assert "referee_fie_license_id text" in normalized
    assert "assignment_status text not null default 'assigned'" in normalized
    assert "metadata jsonb default '{}'" in normalized
    assert "idx_fs_referee_assignments_tournament_event" in normalized
    assert "idx_fs_referee_assignments_bout" in normalized
    assert "idx_fs_referee_assignments_referee_license" in normalized

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIE_REFEREE_JSON = [
    {
        "id": 2380,
        "name": "ABAJO Jose Luis",
        "country": "Spain",
        "countryCode": "ESP",
        "date": "1978-06-22",
        "weaponCategory": "E=B / F=B",
        "flag": "ES",
        "gender": "M",
        "age": 47,
    },
    {
        "id": 18437,
        "name": "SMITH Jane",
        "country": "United States",
        "countryCode": "USA",
        "weaponCategory": "S=A",
    },
]


REFEREE_TABLE_HTML = """
<table>
  <thead>
    <tr><th>License ID</th><th>Name</th><th>Country</th><th>Category</th></tr>
  </thead>
  <tbody>
    <tr><td>321</td><td>DOE John</td><td>USA</td><td>E=A / S=B</td></tr>
    <tr><td>654</td><td>DUPONT Marie</td><td>FRA</td><td>Foil B</td></tr>
  </tbody>
</table>
"""


REFEREE_PDF_TEXT = """
INTERNATIONAL REFEREES
License Name Country Category
7788 KIM Min Su KOR E=A / F=B
9900 GARCIA Ana ESP S=C
"""


USA_COACH_HTML = """
<html>
<body>
  <h1>National Team Staff</h1>
  <table>
    <thead><tr><th>Title</th><th>Name</th><th>Email</th></tr></thead>
    <tbody>
      <tr><td>Women's Epee National Coach</td><td>Sebastien dos Santos</td><td>s@example.org</td></tr>
      <tr><td>Men's Foil National Coach</td><td>Greg Massialas OLY</td><td>g@example.org</td></tr>
    </tbody>
  </table>
  <h3>Women's Saber National Coach: Dagmara Wozniak OLY</h3>
</body>
</html>
"""


FRANCE_COACH_HTML = """
<html>
<body>
  <h3>Fleuret hommes</h3>
  <p>Emeric CLOS (manager)</p>
  <h3>Épée dames</h3>
  <p>Frédéric CHOTIN (manager) Robin RIEU (adjoint)</p>
  <h3>Sabre dames</h3>
  <p>Matthieu GOURDAIN (manager), Damien TOUYA (adjoint)</p>
</body>
</html>
"""


RELATIONSHIP_HTML = """
<article>
  <h1>Alice Volpi</h1>
  <p>Coach: Giovanna Trillini</p>
  <p>National team: Italy women's foil</p>
</article>
<article>
  <p>Coach Marco Villa: Luigi Samele, Luca Curatoli</p>
</article>
"""


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, name, client):
        self.name = name
        self.client = client
        self.actions = []
        self._select = None
        self._filters = []

    def upsert(self, rows, on_conflict=None):
        self.actions.append(("upsert", rows, on_conflict))
        self.client.calls.append((self.name, "upsert", rows, on_conflict))
        return self

    def select(self, *args, **kwargs):
        self._select = (args, kwargs)
        return self

    def ilike(self, key, value):
        self._filters.append(("ilike", key, value))
        return self

    def eq(self, key, value):
        self._filters.append(("eq", key, value))
        return self

    def limit(self, value):
        return self

    def execute(self):
        if self.name == "fs_fencers" and self._select:
            name = None
            country = None
            for op, key, value in self._filters:
                if op == "ilike" and key == "name":
                    name = value
                if op == "eq" and key == "country":
                    country = value
            return FakeResult(self.client.fencer_rows.get((name, country), []))
        return FakeResult([{"id": "ok"}])


class FakeClient:
    def __init__(self):
        self.calls = []
        self.fencer_rows = {
            ("Alice Volpi", "ITA"): [{"id": "fencer-alice"}],
            ("Luigi Samele", "ITA"): [{"id": "fencer-luigi"}],
            ("Luca Curatoli", "ITA"): [{"id": "fencer-luca"}],
        }

    def table(self, name):
        return FakeTable(name, self)


class FakeResponse:
    def __init__(self, data, status_code=200, content_type="application/json"):
        import json

        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.text = json.dumps(data) if not isinstance(data, str) else data
        self.content = self.text.encode()


class FakeRefereeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, timeout=None, params=None):
        self.calls.append((url, params))
        page = (params or {}).get("fetchPage", 1)
        if page == 1:
            return FakeResponse([FIE_REFEREE_JSON[0]])
        if page == 2:
            return FakeResponse([FIE_REFEREE_JSON[1]])
        return FakeResponse([])


def test_parse_fie_referee_json_maps_license_country_and_weapons():
    from scrape_referees import parse_referees_json

    rows = parse_referees_json(FIE_REFEREE_JSON)

    assert rows[0]["name"] == "ABAJO Jose Luis"
    assert rows[0]["country"] == "ESP"
    assert rows[0]["fie_license_id"] == "2380"
    assert rows[0]["category"] == "B"
    assert rows[0]["certification_level"] == "E=B / F=B"
    assert rows[0]["weapons"] == ["Epee", "Foil"]
    assert rows[0]["metadata"]["source_country"] == "Spain"
    assert rows[1]["weapons"] == ["Sabre"]


def test_parse_referee_html_table_accepts_license_and_category_headers():
    from scrape_referees import parse_referees_html

    rows = parse_referees_html(REFEREE_TABLE_HTML)

    assert [row["fie_license_id"] for row in rows] == ["321", "654"]
    assert rows[0]["name"] == "DOE John"
    assert rows[0]["country"] == "USA"
    assert rows[0]["weapons"] == ["Epee", "Sabre"]
    assert rows[1]["weapons"] == ["Foil"]
    assert rows[1]["category"] == "B"


def test_parse_referee_pdf_text_extracts_table_like_rows():
    from scrape_referees import parse_referee_pdf_text

    rows = parse_referee_pdf_text(REFEREE_PDF_TEXT)

    assert len(rows) == 2
    assert rows[0]["fie_license_id"] == "7788"
    assert rows[0]["name"] == "KIM Min Su"
    assert rows[0]["country"] == "KOR"
    assert rows[0]["weapons"] == ["Epee", "Foil"]
    assert rows[1]["name"] == "GARCIA Ana"
    assert rows[1]["weapons"] == ["Sabre"]


def test_fetch_referees_paginates_fie_search_endpoint_until_empty_page():
    from scrape_referees import fetch_referees

    session = FakeRefereeSession()
    rows = fetch_referees(session=session)

    assert [row["fie_license_id"] for row in rows] == ["2380", "18437"]
    assert session.calls == [
        ("https://fie.org/referees/search", {"fetchPage": 1}),
        ("https://fie.org/referees/search", {"fetchPage": 2}),
        ("https://fie.org/referees/search", {"fetchPage": 3}),
    ]


def test_upsert_referees_dedupes_by_fie_license_id():
    from scrape_referees import upsert_referees

    client = FakeClient()
    written = upsert_referees(
        [
            {"name": "DOE John", "country": "USA", "fie_license_id": "321"},
            {"name": "DOE John", "country": "USA", "fie_license_id": "321", "category": "A"},
        ],
        client=client,
    )

    assert written == 1
    assert client.calls == [
        ("fs_referees", "upsert", [{"name": "DOE John", "country": "USA", "fie_license_id": "321", "category": "A"}], "fie_license_id")
    ]


def test_parse_coach_html_tables_and_heading_profiles():
    from scrape_coaches import parse_coaches_html

    rows = parse_coaches_html(USA_COACH_HTML, country="USA", federation="USA Fencing", source_url="https://www.usafencing.org/national-team-staff")

    names = {row["name"] for row in rows}
    assert {"Sebastien dos Santos", "Greg Massialas OLY", "Dagmara Wozniak OLY"} <= names
    epee = next(row for row in rows if row["name"] == "Sebastien dos Santos")
    assert epee["weapons"] == ["Epee"]
    assert epee["national_team_role"] == "Women's Epee National Coach"
    assert epee["metadata"]["email"] == "s@example.org"
    saber = next(row for row in rows if row["name"] == "Dagmara Wozniak OLY")
    assert saber["weapons"] == ["Sabre"]


def test_parse_coach_html_handles_weapon_headings_with_multiple_staff():
    from scrape_coaches import parse_coaches_html

    rows = parse_coaches_html(FRANCE_COACH_HTML, country="FRA", federation="FF Escrime", source_url="https://www.ffescrime.fr/haut-niveau/structures-du-programme-dexcellence/insep/")

    by_name = {row["name"]: row for row in rows}
    assert by_name["Emeric CLOS"]["weapons"] == ["Foil"]
    assert by_name["Emeric CLOS"]["national_team_role"] == "Fleuret hommes manager"
    assert by_name["Frédéric CHOTIN"]["weapons"] == ["Epee"]
    assert by_name["Robin RIEU"]["national_team_role"] == "Épée dames adjoint"
    assert by_name["Damien TOUYA"]["weapons"] == ["Sabre"]


def test_parse_fencer_coach_relationships_and_upsert_matches_fencers():
    from scrape_coaches import parse_fencer_coach_relationships, upsert_coaches_and_relationships

    relationships = parse_fencer_coach_relationships(RELATIONSHIP_HTML, country="ITA", federation="Fed. Italiana Scherma")
    assert relationships == [
        {"coach_name": "Giovanna Trillini", "fencer_name": "Alice Volpi", "country": "ITA", "metadata": {"federation": "Fed. Italiana Scherma"}},
        {"coach_name": "Marco Villa", "fencer_name": "Luigi Samele", "country": "ITA", "metadata": {"federation": "Fed. Italiana Scherma"}},
        {"coach_name": "Marco Villa", "fencer_name": "Luca Curatoli", "country": "ITA", "metadata": {"federation": "Fed. Italiana Scherma"}},
    ]

    client = FakeClient()
    result = upsert_coaches_and_relationships(
        [{"name": "Giovanna Trillini", "country": "ITA", "federation": "Fed. Italiana Scherma", "national_team_role": "Foil Coach", "weapons": ["Foil"], "metadata": {}}],
        relationships[:1],
        client=client,
    )

    assert result == {"coaches_written": 1, "relationships_written": 1, "relationships_skipped": 0}
    assert client.calls[0][0:2] == ("fs_coaches", "upsert")
    assert client.calls[0][3] == "id"
    assert client.calls[1][0:2] == ("fs_fencer_coach_relationship", "upsert")
    assert client.calls[1][2][0]["fencer_id"] == "fencer-alice"
    assert client.calls[1][3] == "fencer_id,coach_id"

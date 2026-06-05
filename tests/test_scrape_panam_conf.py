from typing import Any, cast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


SPANISH_HTML = """
<html><body>
<h1>Campeonato Panamericano Adulto 2025 - Florete Femenino Individual</h1>
<p>24 de junio de 2025</p>
<a href="https://fencing.ophardt.online/en/widget/event/31914">Resultados en vivo</a>
<table>
  <tr><th>Puesto</th><th>Esgrimista</th><th>País</th><th>Puntos</th></tr>
  <tr><td>1</td><td>KIEFER Lee</td><td>Estados Unidos</td><td>64,000</td></tr>
  <tr><td>2</td><td>BOTELLO Natalia</td><td>México</td><td>52,5</td></tr>
  <tr><td>3=</td><td>PÉREZ MAURICE María Belén</td><td>Argentina</td><td>40</td></tr>
</table>
</body></html>
"""


FIE_INLINE_JSON_HTML = """
<html><head><title>Pan American Fencing Championships 2025 - Men Individual Foil</title></head>
<body>
<script>
window.__competition = {
  "competitionId": 799,
  "name": "Pan American Fencing Championships 2025 - Men Individual Foil",
  "startDate": "2025-06-24",
  "location": "Rio de Janeiro",
  "country": "Brazil",
  "weapon": "foil",
  "gender": "men",
  "category": "senior",
  "rows": [
    {"rank": "1", "name": "MASSIALAS Alexander", "nationality": "USA", "fencerId": 12345, "points": "64"},
    {"rank": "2", "name": "ITKIN Nick", "country": "United States", "fencerId": 67890, "points": 52.5}
  ]
};
</script>
</body></html>
"""


PDF_TEXT = """
Campeonato Panamericano Cadete y Juvenil 2025
Espada Masculina Junior Individual
Puesto Nombre País Puntos
1 LIMARDO Jesus Venezuela 64,0
2 SZAPARY Tristan USA 52.0
3= CAMARGO Alexandre Brasil 40
"""


def test_parse_spanish_html_table_normalizes_rank_name_country_points_and_links():
    from scrape_panam_conf import parse_html_result_page

    event = parse_html_result_page(
        SPANISH_HTML,
        source_url="https://example.test/panam/results",
    )

    event = cast(dict[str, Any], event)
    assert event["event_code"] == "women-foil-individual"
    assert event["category"] == "Senior"
    assert event["date"] == "2025-06-24"
    assert event["source_links"] == [
        {
            "url": "https://fencing.ophardt.online/en/widget/event/31914",
            "kind": "ophardt",
            "label": "Resultados en vivo",
        }
    ]
    assert event["results"] == [
        {
            "rank": 1,
            "name": "Lee Kiefer",
            "country": "USA",
            "points": 64.0,
            "medal": "Gold",
            "fie_id": None,
            "team": False,
        },
        {
            "rank": 2,
            "name": "Natalia Botello",
            "country": "MEX",
            "points": 52.5,
            "medal": "Silver",
            "fie_id": None,
            "team": False,
        },
        {
            "rank": 3,
            "name": "María Belén Pérez Maurice",
            "country": "ARG",
            "points": 40.0,
            "medal": "Bronze",
            "fie_id": None,
            "team": False,
        },
    ]


def test_parse_fie_inline_json_result_page_extracts_english_metadata_and_fie_ids():
    from scrape_panam_conf import parse_fie_results_page

    event = parse_fie_results_page(
        FIE_INLINE_JSON_HTML,
        source_url="https://fie.org/competitions/2025/799?tab=results",
    )

    event = cast(dict[str, Any], event)
    assert event["event_code"] == "men-foil-individual"
    assert event["date"] == "2025-06-24"
    assert event["source_kind"] == "fie_inline_json"
    assert event["results"] == [
        {
            "rank": 1,
            "name": "Alexander Massialas",
            "country": "USA",
            "points": 64.0,
            "medal": "Gold",
            "fie_id": "12345",
            "team": False,
        },
        {
            "rank": 2,
            "name": "Nick Itkin",
            "country": "USA",
            "points": 52.5,
            "medal": "Silver",
            "fie_id": "67890",
            "team": False,
        },
    ]


def test_parse_pdf_text_events_handles_spanish_headings_and_country_names():
    from scrape_panam_conf import parse_pdf_text_events

    events = parse_pdf_text_events(
        PDF_TEXT,
        source_url="https://example.test/campeonato-panamericano.pdf",
    )

    assert len(events) == 1
    event = cast(dict[str, Any], events[0])
    assert event["event_code"] == "men-epee-individual"
    assert event["category"] == "Junior"
    assert event["results"] == [
        {
            "rank": 1,
            "name": "Jesus Limardo",
            "country": "VEN",
            "points": 64.0,
            "medal": "Gold",
            "fie_id": None,
            "team": False,
        },
        {
            "rank": 2,
            "name": "Tristan Szapary",
            "country": "USA",
            "points": 52.0,
            "medal": "Silver",
            "fie_id": None,
            "team": False,
        },
        {
            "rank": 3,
            "name": "Alexandre Camargo",
            "country": "BRA",
            "points": 40.0,
            "medal": "Bronze",
            "fie_id": None,
            "team": False,
        },
    ]


def test_country_code_normalization_covers_pafc_spanish_english_aliases():
    from scrape_panam_conf import normalize_country_code

    assert normalize_country_code("Estados Unidos") == "USA"
    assert normalize_country_code("United States of America") == "USA"
    assert normalize_country_code("México") == "MEX"
    assert normalize_country_code("Brasil") == "BRA"
    assert normalize_country_code("Puerto Rico") == "PUR"
    assert normalize_country_code("U.S. Virgin Islands") == "ISV"
    assert normalize_country_code("Islas Vírgenes de EE.UU.") == "ISV"
    assert normalize_country_code("Dominican Republic") == "DOM"
    assert normalize_country_code("Haiti") == "HAI"
    assert normalize_country_code("Belice") == "BIZ"
    assert normalize_country_code("Cayman Islands") == "CAY"
    assert normalize_country_code("British Virgin Islands") == "IVB"


def test_blocked_source_stubs_are_deterministic_probe_evidence():
    from scrape_panam_conf import blocked_source_stubs

    stubs = blocked_source_stubs()
    urls = {stub["url"] for stub in stubs}

    assert "https://www.panam-fencing.org" in urls
    assert "https://panamericanfencing.org" in urls
    assert any(stub["status"] == "blocked" and "sandbox DNS" in stub["reason"] for stub in stubs)


def test_build_result_rows_skips_unmatched_individuals_but_allows_team_rows(monkeypatch):
    import scrape_panam_conf

    calls = []

    def fake_match(fie_id=None, name=None, country=None):
        calls.append((fie_id, name, country))
        if fie_id == "12345":
            return "fie-match", "fie_id"
        return None, None

    monkeypatch.setattr(scrape_panam_conf, "_match_fencer", fake_match)

    db_rows, unmatched = scrape_panam_conf.build_result_rows(
        tournament_id="tournament-1",
        source_id="panam:2025:mf",
        result_rows=[
            {"rank": 1, "name": "Alexander Massialas", "country": "USA", "medal": "Gold", "fie_id": "12345", "team": False},
            {"rank": 2, "name": "Unmatched Fencer", "country": "MEX", "medal": "Silver", "fie_id": None, "team": False},
            {"rank": 1, "name": "Canada", "country": "CAN", "medal": "Gold", "fie_id": None, "team": True},
        ],
    )

    assert calls == [
        ("12345", "Alexander Massialas", "USA"),
        (None, "Unmatched Fencer", "MEX"),
    ]
    assert [row["name"] for row in db_rows] == ["Alexander Massialas", "Canada"]
    assert db_rows[0]["fencer_id"] == "fie-match"
    assert db_rows[0]["metadata"]["fencer_match"] == "fie_id"
    assert db_rows[1]["fencer_id"] is None
    assert db_rows[1]["metadata"]["team"] is True
    assert unmatched == [
        {
            "source_id": "panam:2025:mf",
            "rank": 2,
            "name": "Unmatched Fencer",
            "country": "MEX",
            "fie_id": None,
            "reason": "no_fencer_match",
        }
    ]


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, table_name, client):
        self.table_name = table_name
        self.client = client
        self.filters = []

    def select(self, _columns):
        self.client.calls.append((self.table_name, "select", _columns))
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def limit(self, _count):
        return self

    def execute(self):
        if self.table_name != "fs_fencers":
            return FakeResponse([])
        filters = {(op, column): value for op, column, value in self.filters}
        if filters.get(("eq", "fie_id")) == "777":
            return FakeResponse([{"id": "by-fie-id"}])
        if filters.get(("ilike", "name")) == "Name Country" and filters.get(("eq", "country")) == "CAN":
            return FakeResponse([{"id": "by-name-country"}])
        if filters.get(("ilike", "name")) == "Ambiguous" and filters.get(("eq", "country")) == "USA":
            return FakeResponse([{"id": "one"}, {"id": "two"}])
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.calls = []

    def table(self, table_name):
        return FakeQuery(table_name, self)


def test_match_fencer_prefers_fie_id_then_unique_name_country(monkeypatch):
    import scrape_panam_conf

    monkeypatch.setattr(scrape_panam_conf, "supabase", FakeClient())

    assert scrape_panam_conf._match_fencer(fie_id="777", name="Ignored", country="USA") == ("by-fie-id", "fie_id")
    assert scrape_panam_conf._match_fencer(fie_id=None, name="Name Country", country="CAN") == (
        "by-name-country",
        "name_country",
    )
    assert scrape_panam_conf._match_fencer(fie_id=None, name="Ambiguous", country="USA") == (None, None)


class FakeIdentityQuery(FakeQuery):
    def execute(self):
        filters = {(op, column): value for op, column, value in self.filters}
        if self.table_name == "fs_fencers":
            return FakeResponse([])
        if (
            self.table_name == "fs_fencer_identities"
            and filters.get(("ilike", "canonical_name")) == "Canonical Person"
            and filters.get(("eq", "country")) == "CHI"
        ):
            return FakeResponse([{"fs_fencer_row_ids": ["identity-member-id"], "canonical_id": "identity-id"}])
        return FakeResponse([])


class FakeIdentityClient(FakeClient):
    def table(self, table_name):
        return FakeIdentityQuery(table_name, self)


def test_match_fencer_falls_back_to_unique_canonical_identity(monkeypatch):
    import scrape_panam_conf

    monkeypatch.setattr(scrape_panam_conf, "supabase", FakeIdentityClient())

    assert scrape_panam_conf._match_fencer(fie_id=None, name="Canonical Person", country="CHI") == (
        "identity-member-id",
        "identity_name_country",
    )

from typing import Any, cast
import io
import os
import sys

import xlwt

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ITALY_4FENCE_HTML = """
<html><body>
<h1>Campionati Italiani Assoluti Frecciarossa - Fioretto Femminile</h1>
<h2>CLASSIFICA FINALE</h2>
<table>
  <tr>
    <th>Pos.</th><th>Cognome</th><th>Nome</th><th>Societa</th><th>N.Fis</th><th>Punt.</th>
  </tr>
  <tr><td>1</td><td>VOLPI</td><td>ALICE</td><td>RMFFO</td><td>605811</td><td>1000</td></tr>
  <tr><td>2</td><td>ERRIGO</td><td>ARIANNA</td><td>RMCC</td><td>136327</td><td>920,5</td></tr>
  <tr><td>3</td><td>BATINI</td><td>MARTINA</td><td>RMCC</td><td>147440</td><td>850</td></tr>
</table>
</body></html>
"""


FRANCE_ENGARDE_HTML = """
<html><body>
<h1>Championnat de France Fleuret Homme M17 2026</h1>
<h3>Classement general (84 tireurs)</h3>
<table>
  <tr><th>Rg</th><th>Nom</th><th>Prenom</th><th>Club</th><th>Statut</th></tr>
  <tr><td>1</td><td>BLANCHARD</td><td>Leo Singharat</td><td>ANTONY</td><td></td></tr>
  <tr><td>2</td><td>GIRONDIN</td><td>Noah</td><td>PARIS SCUF</td><td></td></tr>
  <tr><td>3</td><td>BESLIER</td><td>Gabriel</td><td>PARIS CEP</td><td></td></tr>
</table>
</body></html>
"""


HONG_KONG_PDF_TEXT = """
FILA 2025 Hong Kong Open Fencing Championships
ME Final Classification
Rank | Name | Club | Country | Points
1 | CHEUNG KA LONG | HKSI | HKG | 1000
2 | WU WAN HEI LUCAS | FENCERS CLUB HONG KONG | HKG | 920
3 | LAM TAT MAN DARWIN | FENCING POINT | HKG | 850
"""


def metadata(**overrides):
    data = {
        "country": "ITA",
        "tournament": "Campionati Italiani Assoluti Frecciarossa",
        "event": "Fioretto Femminile",
        "weapon": "Foil",
        "gender": "Women",
        "category": "Senior",
        "season": "2025-2026",
        "source_url": "https://www.4fence.it/FIS/Risultati/current/",
    }
    data.update(overrides)
    return data


def test_country_configs_cover_top_20_with_probe_evidence_and_stubs():
    import scrape_national_champs as champs

    country_configs = cast(list[dict[str, Any]], champs.COUNTRY_CONFIGS)
    assert len(country_configs) == 20
    assert len({cfg["country"] for cfg in country_configs}) == 20
    assert {"ITA", "FRA", "GER", "CAN", "GBR", "HKG"}.issubset(
        {cfg["country"] for cfg in country_configs}
    )
    for cfg in country_configs:
        assert cfg["federation_url"].startswith("https://")
        assert cfg["language"]
        assert cfg["result_page_types"]
        assert cfg["fallback_notes"]
        assert cfg["probe_evidence"]

    blocked = [cfg for cfg in country_configs if cfg["status"] == "blocked"]
    parsable = [cfg for cfg in country_configs if cfg["status"] == "parsable"]
    assert blocked
    assert len(parsable) >= 3


def test_parse_4fence_html_final_classification_with_italian_columns():
    from scrape_national_champs import parse_4fence_html

    rows = parse_4fence_html(ITALY_4FENCE_HTML, metadata())

    assert rows[:3] == [
        {
            "tournament": "Campionati Italiani Assoluti Frecciarossa",
            "event": "Fioretto Femminile",
            "rank": 1,
            "fencer_name": "Alice Volpi",
            "country": "ITA",
            "club": "RMFFO",
            "points": 1000.0,
            "medal": "Gold",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "season": "2025-2026",
            "source_url": "https://www.4fence.it/FIS/Risultati/current/",
            "fie_id": "605811",
        },
        {
            "tournament": "Campionati Italiani Assoluti Frecciarossa",
            "event": "Fioretto Femminile",
            "rank": 2,
            "fencer_name": "Arianna Errigo",
            "country": "ITA",
            "club": "RMCC",
            "points": 920.5,
            "medal": "Silver",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "season": "2025-2026",
            "source_url": "https://www.4fence.it/FIS/Risultati/current/",
            "fie_id": "136327",
        },
        {
            "tournament": "Campionati Italiani Assoluti Frecciarossa",
            "event": "Fioretto Femminile",
            "rank": 3,
            "fencer_name": "Martina Batini",
            "country": "ITA",
            "club": "RMCC",
            "points": 850.0,
            "medal": "Bronze",
            "weapon": "Foil",
            "gender": "Women",
            "category": "Senior",
            "season": "2025-2026",
            "source_url": "https://www.4fence.it/FIS/Risultati/current/",
            "fie_id": "147440",
        },
    ]


def test_parse_engarde_html_final_classification_with_french_columns():
    from scrape_national_champs import parse_engarde_html

    rows = parse_engarde_html(
        FRANCE_ENGARDE_HTML,
        metadata(
            country="FRA",
            tournament="Championnat de France Fleuret Homme M17 2026",
            event="Fleuret Homme M17",
            weapon="Foil",
            gender="Men",
            category="Cadet",
            source_url="https://engarde-service.com/competition/cesgl/cidfm17f/cidfm17fh",
        ),
    )

    assert rows[0]["fencer_name"] == "Leo Singharat Blanchard"
    assert rows[0]["club"] == "ANTONY"
    assert rows[0]["country"] == "FRA"
    assert rows[0]["medal"] == "Gold"
    assert rows[2]["rank"] == 3
    assert rows[2]["medal"] == "Bronze"


def test_parse_pdf_text_results_with_hong_kong_fixture():
    from scrape_national_champs import parse_pdf_text_results

    rows = parse_pdf_text_results(
        HONG_KONG_PDF_TEXT,
        metadata(
            country="HKG",
            tournament="FILA 2025 Hong Kong Open Fencing Championships",
            event="ME",
            weapon="Epee",
            gender="Men",
            source_url="https://www.hkfa.org.hk/results/25_HKOresults.pdf",
        ),
    )

    assert rows[0]["rank"] == 1
    assert rows[0]["fencer_name"] == "Cheung Ka Long"
    assert rows[0]["club"] == "HKSI"
    assert rows[0]["country"] == "HKG"
    assert rows[0]["points"] == 1000.0
    assert rows[1]["source_url"] == "https://www.hkfa.org.hk/results/25_HKOresults.pdf"


def test_parse_spreadsheet_results_with_xls_export_fixture():
    from scrape_national_champs import parse_spreadsheet_results

    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Senior WE")
    for col, header in enumerate(["Rank", "FIE ID", "Name", "Country", "Club", "Points"]):
        sheet.write(0, col, header)
    sheet.write(1, 0, 1)
    sheet.write(1, 1, "999001")
    sheet.write(1, 2, "Eleanor Harvey")
    sheet.write(1, 3, "CAN")
    sheet.write(1, 4, "Canadian Fencing Academy")
    sheet.write(1, 5, 1000)
    sheet.write(2, 0, 2)
    sheet.write(2, 2, "Jessica Guo")
    sheet.write(2, 3, "CAN")
    sheet.write(2, 4, "Vango Toronto")
    sheet.write(2, 5, 920)
    buf = io.BytesIO()
    workbook.save(buf)

    rows = parse_spreadsheet_results(
        buf.getvalue(),
        metadata(
            country="CAN",
            tournament="Canada Cup #1 and Senior National Championships",
            event="Senior Women's Epee",
            weapon="Epee",
            gender="Women",
            source_url="https://fencing.ca/results-2/",
        ),
        file_ext=".xls",
    )

    assert rows[0]["fie_id"] == "999001"
    assert rows[0]["fencer_name"] == "Eleanor Harvey"
    assert rows[1]["fencer_name"] == "Jessica Guo"
    assert rows[1]["medal"] == "Silver"


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.operation = None
        self.payload = None

    def select(self, _columns):
        self.operation = "select"
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def limit(self, _count):
        return self

    def delete(self):
        self.operation = "delete"
        self.client.deleted.append((self.table_name, list(self.filters)))
        return self

    def insert(self, rows):
        self.operation = "insert"
        self.payload = rows
        self.client.inserted.extend(rows)
        return self

    def upsert(self, row, on_conflict=None):
        self.operation = "upsert"
        self.payload = row
        self.client.upserts.append({"table": self.table_name, "row": row, "on_conflict": on_conflict})
        return self

    def execute(self):
        if self.table_name == "fs_fencers" and self.operation == "select":
            filters = {(kind, column): value for kind, column, value in self.filters}
            if filters.get(("eq", "fie_id")) == "12345":
                return FakeResponse([{"id": "fie-match"}])
            if filters.get(("ilike", "name")) == "Name Match" and filters.get(("eq", "country")) == "SCO":
                return FakeResponse([{"id": "name-country-match"}])
            return FakeResponse([])
        if self.table_name == "fs_tournaments" and self.operation == "upsert":
            return FakeResponse([{"id": "tournament-1"}])
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.inserted = []
        self.deleted = []
        self.upserts = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_result_adapter_matches_fie_id_then_name_country_and_logs_unmatched():
    from scrape_national_champs import build_result_db_rows

    fake = FakeClient()
    unmatched = []
    rows = [
        {"rank": 1, "fencer_name": "Wrong Name", "country": "ENG", "medal": "Gold", "fie_id": "12345"},
        {"rank": 2, "fencer_name": "Name Match", "country": "SCO", "medal": "Silver", "fie_id": None},
        {"rank": 3, "fencer_name": "Missing Person", "country": "CAN", "medal": "Bronze", "fie_id": None},
    ]

    db_rows = build_result_db_rows(
        fake,
        tournament_id="tournament-1",
        parsed_rows=rows,
        unmatched_logger=lambda message: unmatched.append(message),
    )

    assert [row["fencer_id"] for row in db_rows] == ["fie-match", "name-country-match", None]
    assert len(db_rows) == 3
    assert len(unmatched) == 1
    assert "Missing Person" in unmatched[0]
    assert "tournament-1" in unmatched[0]


def test_blocked_source_stub_exits_zero_with_probe_evidence(capsys):
    from scrape_national_champs import run_country_config

    summary = run_country_config(
        {
            "country": "CAN",
            "name": "Canada",
            "status": "blocked",
            "parser": None,
            "probe_evidence": "Fencing Time Live redirected to /account/login during 2026-06-02 probe.",
            "fallback_notes": "Wait for public export or authenticated API handoff.",
        },
        client=None,
    )

    assert summary == {"written": 0, "failed": 0, "skipped": 1}
    output = capsys.readouterr().out
    assert "CAN blocked" in output
    assert "redirected to /account/login" in output

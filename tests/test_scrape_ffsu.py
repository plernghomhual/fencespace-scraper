import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FFSU_INDIVIDUAL_PDF_TEXT = """
Championnat de France FFSU
Epée Dames Individuel
Classement général (ordre des rangs - 36 tireuses)
page 1/1
rg nom prénom club statut
1 NAUCELLE-JARDEL Thaïs GROUPE EDHEC
2 VERGNES Anna AS SCIENCES PO LILLE
3 FRANCILLONNE Océane ASE LILLE ILIS
Document engarde-escrime.com - 2024-03-28 18:02 - Page 9
Championnat de France FFSU
Fleuret Hommes Individuel
Classement général (ordre des rangs - 40 tireurs)
page 1/1
rg nom prénom club
1 BAUDCHON Florent ASU ARTOIS
2 EL RHAZZOULY Amir UNIV PARIS PANTHEON ASSAS
Total 40 tireurs
"""


FFSU_TEAM_PDF_TEXT = """
FFSU
Sabre Dames Equipes
Classement général (ordre des rangs - 5 équipes)
page 1/1
rg nom drap club statut
1 SORBONNE UNIVERSITÉ
 BARBIER Louise
 LUSINIER Kelly
2 ASU BORDEAUX SANTÉ
 BAYLAUCQ Garance
"""


FFSU_TEAM_MULTIPAGE_TEXT = """
Championant de France FFSU
Epée Hommes Equipes
Classement général (ordre des rangs - 12 équipes)
page 1/2
rg nom
1 PARIS NORD
2 URCA REIMS 1
Document engarde-escrime.com - 2024-03-29 14:18 - Page 9Championant de France FFSU
Epée Hommes Equipes
Classement général (ordre des rangs - 12 équipes)
page 2/2
rg nom
12 POLE LEONARD DE VINCI
"""


FFSU_HTML_TABLE = """
<html>
  <body>
    <h2>Fleuret Hommes Individuel</h2>
    <table>
      <tr>
        <th>Place</th><th>Nom</th><th>Prénom</th><th>Sexe</th>
        <th>AS</th><th>Académie</th><th>Résultat</th>
      </tr>
      <tr>
        <td>1</td><td>LEFÈVRE</td><td>Émile</td><td>M</td>
        <td>AS Univ. de Tours</td><td>ORLEANS-TOURS</td><td>100</td>
      </tr>
      <tr>
        <td>2</td><td>RÉGNIER</td><td>Zoé</td><td>F</td>
        <td>Université Paris Cité</td><td>PARIS</td><td>87.5</td>
      </tr>
      <tr><td>Total</td><td>2 tireurs</td><td></td><td></td><td></td><td></td><td></td></tr>
    </table>
  </body>
</html>
"""


def test_parse_ffsu_pdf_text_handles_french_headers_accents_and_summary_rows():
    from scrape_ffsu import parse_ffsu_text_result

    events = parse_ffsu_text_result(
        FFSU_INDIVIDUAL_PDF_TEXT,
        season="Saison 2023-2024",
        source_url="https://sport-u.com/resultats-individuels-2024.pdf",
    )

    assert len(events) == 2
    epee_women = events[0]
    assert epee_women["source_id"] == "ffsu:2023-2024:epee-women-individual"
    assert epee_women["event_name"] == "Epée Dames Individuel"
    assert epee_women["weapon"] == "Epee"
    assert epee_women["gender"] == "Women"
    assert epee_women["category"] == "Senior"
    assert epee_women["season"] == "2023-2024"
    assert epee_women["results"][:3] == [
        {
            "rank": 1,
            "name": "Naucelle-Jardel Thaïs",
            "university": "Groupe EDHEC",
            "medal": "Gold",
            "points": None,
            "status": None,
            "team": False,
            "source_url": "https://sport-u.com/resultats-individuels-2024.pdf",
        },
        {
            "rank": 2,
            "name": "Vergnes Anna",
            "university": "AS Sciences Po Lille",
            "medal": "Silver",
            "points": None,
            "status": None,
            "team": False,
            "source_url": "https://sport-u.com/resultats-individuels-2024.pdf",
        },
        {
            "rank": 3,
            "name": "Francillonne Océane",
            "university": "ASE Lille ILIS",
            "medal": "Bronze",
            "points": None,
            "status": None,
            "team": False,
            "source_url": "https://sport-u.com/resultats-individuels-2024.pdf",
        },
    ]

    foil_men = events[1]
    assert foil_men["event_code"] == "foil-men-individual"
    assert [row["rank"] for row in foil_men["results"]] == [1, 2]


def test_parse_ffsu_pdf_team_text_skips_roster_lines_and_preserves_university_rows():
    from scrape_ffsu import parse_ffsu_text_result

    events = parse_ffsu_text_result(
        FFSU_TEAM_PDF_TEXT,
        season="2024",
        source_url="https://sport-u.com/resultats-equipes-2024.pdf",
    )

    assert len(events) == 1
    event = events[0]
    assert event["event_code"] == "sabre-women-team"
    assert event["team"] is True
    assert event["results"] == [
        {
            "rank": 1,
            "name": "Sorbonne Université",
            "university": "Sorbonne Université",
            "medal": "Gold",
            "points": None,
            "status": None,
            "team": True,
            "source_url": "https://sport-u.com/resultats-equipes-2024.pdf",
        },
        {
            "rank": 2,
            "name": "ASU Bordeaux Santé",
            "university": "ASU Bordeaux Santé",
            "medal": "Silver",
            "points": None,
            "status": None,
            "team": True,
            "source_url": "https://sport-u.com/resultats-equipes-2024.pdf",
        },
    ]


def test_parse_ffsu_pdf_text_merges_repeated_headings_for_multipage_team_events():
    from scrape_ffsu import parse_ffsu_text_result

    events = parse_ffsu_text_result(
        FFSU_TEAM_MULTIPAGE_TEXT,
        season="2023-2024",
        source_url="https://sport-u.com/resultats-equipes-2024.pdf",
    )

    assert len(events) == 1
    assert events[0]["event_code"] == "epee-men-team"
    assert [row["rank"] for row in events[0]["results"]] == [1, 2, 12]
    assert events[0]["results"][-1]["name"] == "Pôle Leonard de Vinci"


def test_parse_ffsu_html_table_supports_french_headers_points_and_summary_rows():
    from scrape_ffsu import parse_ffsu_html_result

    events = parse_ffsu_html_result(
        FFSU_HTML_TABLE,
        season="24-25",
        source_url="https://sport-u-paysdelaloire.com/resultats-cr-escrime-24-25.pdf",
    )

    assert len(events) == 1
    event = events[0]
    assert event["season"] == "2024-2025"
    assert event["event_code"] == "foil-men-individual"
    assert event["results"] == [
        {
            "rank": 1,
            "name": "Lefèvre Émile",
            "university": "AS Université de Tours",
            "medal": "Gold",
            "points": 100,
            "status": None,
            "team": False,
            "source_url": "https://sport-u-paysdelaloire.com/resultats-cr-escrime-24-25.pdf",
        },
        {
            "rank": 2,
            "name": "Régnier Zoé",
            "university": "Université Paris Cité",
            "medal": "Silver",
            "points": 87.5,
            "status": None,
            "team": False,
            "source_url": "https://sport-u-paysdelaloire.com/resultats-cr-escrime-24-25.pdf",
        },
    ]


def test_parse_ffsu_workbook_supports_event_headings_inside_sheets():
    from openpyxl import Workbook
    from scrape_ffsu import parse_ffsu_workbook_bytes

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Résultats CFU"
    sheet.append(["Epée Dames Individuel"])
    sheet.append(["Place", "Nom", "Prénom", "AS", "Points"])
    sheet.append([1, "NAUCELLE-JARDEL", "Thaïs", "GROUPE EDHEC", 100])
    sheet.append([2, "RÉGNIER", "Zoé", "UNIVERSITE PARIS CITE", 87.5])
    sheet.append([])
    sheet.append(["Sabre Hommes Equipes"])
    sheet.append(["Rang", "Association", "Points"])
    sheet.append([1, "ASU BORDEAUX SANTÉ", 50])

    buffer = BytesIO()
    workbook.save(buffer)

    events = parse_ffsu_workbook_bytes(
        buffer.getvalue(),
        season="CFU 2025",
        source_url="https://sport-u.com/wp-content/uploads/sites/15/2025/04/Resultats-CFU-Escrime-2025.xlsx",
    )

    assert [event["event_code"] for event in events] == ["epee-women-individual", "sabre-men-team"]
    assert events[0]["season"] == "2024-2025"
    assert events[0]["results"][0]["name"] == "Naucelle-Jardel Thaïs"
    assert events[0]["results"][1]["university"] == "Université Paris Cité"
    assert events[1]["results"][0]["name"] == "ASU Bordeaux Santé"
    assert events[1]["results"][0]["points"] == 50


def test_normalizes_french_seasons_names_and_university_labels():
    from scrape_ffsu import (
        normalize_person_name,
        normalize_season,
        normalize_university_label,
    )

    assert normalize_season("Saison 2024-2025") == "2024-2025"
    assert normalize_season("CFU Escrime 2025") == "2024-2025"
    assert normalize_season("resultats-cr-escrime-24-25.pdf") == "2024-2025"
    assert normalize_person_name("D'ALMEIDA Daryl") == "D'Almeida Daryl"
    assert normalize_person_name("LEFÈVRE Émile") == "Lefèvre Émile"
    assert normalize_university_label("UNIVERSITE PARIS CITE") == "Université Paris Cité"
    assert normalize_university_label("ASU BX COLLÈGE SANTÉ") == "ASU BX Collège Santé"
    assert normalize_university_label("AS Univ. de Tours") == "AS Université de Tours"
    assert normalize_university_label("SCIENCE PO LILLE") == "Sciences Po Lille"


def test_discover_result_sources_from_public_ffsu_page_html():
    from scrape_ffsu import discover_result_sources

    html = """
    <h2>Saison 2024-2025</h2>
    <a href="/wp-content/uploads/sites/15/2025/04/Resultats-CFU-Escrime-2025.xlsx">Résultats CFU Escrime 2025</a>
    <a href="/wp-content/uploads/sites/15/2025/04/Dossier-CFE-Escrime-2025.pdf">Dossier CFE Escrime 2025</a>
    <h2>2023-2024</h2>
    <a href="/wp-content/uploads/sites/15/2024/04/Resultats-Individuels-CFU-2024.pdf">Résultats Individuels CFU 2024</a>
    <a href="/wp-content/uploads/sites/15/2024/04/Resultats-Equipe-CFU-2024.pdf">-Résultats Equipes CFU 2024</a>
    """

    sources = discover_result_sources(html, base_url="https://sport-u.com/sports-ind/ESCRIME/")

    assert sources == [
        {
            "title": "Résultats CFU Escrime 2025",
            "url": "https://sport-u.com/wp-content/uploads/sites/15/2025/04/Resultats-CFU-Escrime-2025.xlsx",
            "season": "2024-2025",
            "format": "xlsx",
        },
        {
            "title": "Résultats Individuels CFU 2024",
            "url": "https://sport-u.com/wp-content/uploads/sites/15/2024/04/Resultats-Individuels-CFU-2024.pdf",
            "season": "2023-2024",
            "format": "pdf",
        },
        {
            "title": "-Résultats Equipes CFU 2024",
            "url": "https://sport-u.com/wp-content/uploads/sites/15/2024/04/Resultats-Equipe-CFU-2024.pdf",
            "season": "2023-2024",
            "format": "pdf",
        },
    ]


def test_no_public_data_stub_is_deterministic_and_counts_skipped_sources():
    from scrape_ffsu import build_no_public_data_stub, discover_result_sources

    html = """
    <h2>CFU ESCRIME</h2>
    <a href="/wp-content/uploads/sites/15/2026/03/Dossier-CFU-Escrime-2026.pdf">Dossier CFU Escrime 2026</a>
    <a href="/sports-ind/ESCRIME/">Informations</a>
    """

    assert discover_result_sources(html, base_url="https://sport-u.com/sports-ind/ESCRIME/") == []
    stub = build_no_public_data_stub(
        [{"url": "https://sport-u.com/sports-ind/ESCRIME/", "status": 200, "evidence": "no public result links"}]
    )

    assert stub["source"] == "ffsu"
    assert stub["events"] == []
    assert stub["written"] == 0
    assert stub["failed"] == 0
    assert stub["skipped"] == 1
    assert "no public FFSU fencing result files" in stub["reason"]


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def limit(self, *_args):
        return self

    def delete(self):
        self.client.deleted.append(self.table_name)
        return self

    def insert(self, rows):
        self.client.inserted.extend(rows)
        return self

    def upsert(self, row, on_conflict=None):
        self.client.upserted.append((self.table_name, row, on_conflict))
        return self

    def execute(self):
        if self.table_name == "fs_tournaments" and self.client.upserted:
            return FakeResponse([{"id": "tournament-1"}])
        if self.table_name != "fs_fencers":
            return FakeResponse([])
        filters = {(op, column): value for op, column, value in self.filters}
        if filters.get(("ilike", "name")) == "Naucelle-Jardel Thaïs" and filters.get(("eq", "country")) == "FRA":
            return FakeResponse([{"id": "matched-fencer"}])
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.deleted = []
        self.inserted = []
        self.upserted = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_upsert_maps_ffsu_events_to_tournaments_results_and_logs_unmatched(monkeypatch):
    import scrape_ffsu

    fake = FakeClient()
    monkeypatch.setattr(scrape_ffsu, "supabase", fake)
    event = scrape_ffsu.parse_ffsu_text_result(
        FFSU_INDIVIDUAL_PDF_TEXT,
        season="2023-2024",
        source_url="https://sport-u.com/resultats-individuels-2024.pdf",
    )[0]

    tournament_id = scrape_ffsu.upsert_tournament(event)
    result = scrape_ffsu.upsert_results(tournament_id, event)

    assert tournament_id == "tournament-1"
    table_name, tournament_row, on_conflict = fake.upserted[0]
    assert table_name == "fs_tournaments"
    assert on_conflict == "source_id"
    assert tournament_row["source_id"] == "ffsu:2023-2024:epee-women-individual"
    assert tournament_row["type"] == "ffsu_university"
    assert tournament_row["season"] == "2023-2024"
    assert tournament_row["metadata"]["source_url"] == "https://sport-u.com/resultats-individuels-2024.pdf"

    assert result["written"] == 3
    assert result["unmatched"] == 2
    assert len(result["unmatched_rows"]) == 2
    assert fake.deleted == ["fs_results"]
    assert fake.inserted[0]["fencer_id"] == "matched-fencer"
    assert fake.inserted[0]["metadata"]["university"] == "Groupe EDHEC"
    assert fake.inserted[1]["fencer_id"] is None

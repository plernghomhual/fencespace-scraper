import io
import os
import sys
from typing import Any

from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


EFC_HTML = """
<html><body>
<h1>Cadet Circuit Cabries</h1>
<dl>
  <dt>Date:</dt><dd>05/12/2025 - 07/12/2025</dd>
  <dt>Place:</dt><dd>Cabries</dd>
  <dt>Category:</dt><dd>Cadets</dd>
  <dt>Weapon:</dt><dd>Foil</dd>
</dl>
<a href="https://efc-prod.s3.amazonaws.com/documents/fra/igm/cqb/invitation.pdf">Invitation</a>
<a href="https://engarde-service.com/tournament/occ/occ2025">Live results</a>

<h2>Individual - Cadets - Female - Foil</h2>
<table>
  <tr><th>Rank</th><th>Points</th><th>Name</th><th>Age</th><th>Nationality</th></tr>
  <tr><td>1</td><td>96</td><td>LEE Lavender</td><td>16</td><td>United States</td></tr>
  <tr><td>2</td><td>78</td><td>WANG Yixi</td><td>15</td><td>China</td></tr>
</table>

<h2>Individuel - Juniors - Masculin - Épée</h2>
<table>
  <tr><th>Rang</th><th>Pts</th><th>Nom</th><th>Club</th><th>Nation</th><th>ID FIE</th></tr>
  <tr><td>1.</td><td>32,5</td><td>PELLE Domonkos</td><td>BVSC</td><td>HUN</td><td>98765</td></tr>
  <tr><td>3=</td><td>20</td><td>LOCATELLI Marco Francesco</td><td>CS Milano</td><td>ITA</td><td></td></tr>
</table>

<h2>Individual - U14 - Female - Epee</h2>
<table>
  <tr><th>Rank</th><th>Points</th><th>Name</th><th>Age</th><th>Nationality</th></tr>
  <tr><td>1</td><td>32</td><td>BEGO Noemi</td><td>13</td><td>Italy</td></tr>
</table>
</body></html>
"""


PDF_TEXT = """
European Championships U20
Date:
27/02/2025 - 02/03/2025
Place:
Antalya
Individual - Juniors - Male - Epee
Rank Points Name Age Nationality
1 32 PELLE Domonkos 19 Hungary
2 26 BUELAU Matthew 20 Germany
3 20 KUZNIK Bartosz 18 Poland
"""


def test_parse_event_page_handles_cadet_junior_multilingual_headers_and_skips_u14():
    from scrape_efc_youth import parse_event_page

    parsed = parse_event_page(EFC_HTML, "https://efc.leonidovich.net/results/cadet-circuit-cabries-fra-2025-2026")

    assert [event["event_name"] for event in parsed["events"]] == [
        "Individual - Cadets - Female - Foil",
        "Individuel - Juniors - Masculin - Épée",
    ]
    assert parsed["skipped"] == [
        {
            "source_url": "https://efc.leonidovich.net/results/cadet-circuit-cabries-fra-2025-2026",
            "event_name": "Individual - U14 - Female - Epee",
            "reason": "blocked_minor_category:U14",
        }
    ]

    cadet = parsed["events"][0]
    assert cadet["competition_name"] == "Cadet Circuit Cabries"
    assert cadet["date"] == "2025-12-05"
    assert cadet["end_date"] == "2025-12-07"
    assert cadet["category"] == "Cadet"
    assert cadet["gender"] == "Women"
    assert cadet["weapon"] == "Foil"
    assert cadet["source_links"] == [
        "https://efc-prod.s3.amazonaws.com/documents/fra/igm/cqb/invitation.pdf",
        "https://engarde-service.com/tournament/occ/occ2025",
    ]
    assert cadet["results"][0] == {
        "rank": 1,
        "fencer": "Lavender Lee",
        "country": "USA",
        "club": None,
        "points": 96.0,
        "fie_id": None,
        "source_url": "https://efc.leonidovich.net/results/cadet-circuit-cabries-fra-2025-2026",
        "date": "2025-12-05",
    }

    junior = parsed["events"][1]
    assert junior["category"] == "Junior"
    assert junior["gender"] == "Men"
    assert junior["weapon"] == "Epee"
    assert junior["results"][0] == {
        "rank": 1,
        "fencer": "Domonkos Pelle",
        "country": "HUN",
        "club": "BVSC",
        "points": 32.5,
        "fie_id": "98765",
        "source_url": "https://efc.leonidovich.net/results/cadet-circuit-cabries-fra-2025-2026",
        "date": "2025-12-05",
    }


def test_parse_pdf_text_events_uses_public_result_rows_without_profiles():
    from scrape_efc_youth import parse_pdf_text_events

    events = parse_pdf_text_events(PDF_TEXT, "https://fencing-efc.eu/results/u20-antalya.pdf")

    assert len(events) == 1
    assert events[0]["competition_name"] == "European Championships U20"
    assert events[0]["category"] == "Junior"
    assert events[0]["date"] == "2025-02-27"
    assert events[0]["results"][:2] == [
        {
            "rank": 1,
            "fencer": "Domonkos Pelle",
            "country": "HUN",
            "club": None,
            "points": 32.0,
            "fie_id": None,
            "source_url": "https://fencing-efc.eu/results/u20-antalya.pdf",
            "date": "2025-02-27",
        },
        {
            "rank": 2,
            "fencer": "Matthew Buelau",
            "country": "GER",
            "club": None,
            "points": 26.0,
            "fie_id": None,
            "source_url": "https://fencing-efc.eu/results/u20-antalya.pdf",
            "date": "2025-02-27",
        },
    ]


def test_parse_xlsx_events_handles_federation_download_workbook():
    from scrape_efc_youth import parse_xlsx_events

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Junior ME"
    sheet.append(["Competition", "European Championships U20"])
    sheet.append(["Date", "27/02/2025"])
    sheet.append(["Event", "Individual - Juniors - Male - Epee"])
    sheet.append([])
    sheet.append(["Classement", "Points", "Nom", "Club", "Pays", "FIE ID"])
    sheet.append([1, 32, "PELLE Domonkos", "BVSC", "HUN", 98765])
    sheet.append([2, 26, "BUELAU Matthew", None, "GER", None])
    stream = io.BytesIO()
    workbook.save(stream)

    events = parse_xlsx_events(stream.getvalue(), "https://fencing-efc.eu/download/u20-results.xlsx")

    assert len(events) == 1
    assert events[0]["event_name"] == "Individual - Juniors - Male - Epee"
    assert events[0]["results"][0]["fie_id"] == "98765"
    assert events[0]["results"][1]["country"] == "GER"


def test_result_rows_do_not_store_minor_age_or_profile_urls_and_log_unmatched():
    from scrape_efc_youth import build_result_rows

    unmatched: list[Any] = []
    event = {
        "source_url": "https://fencing-efc.eu/results/cadet-circuit",
        "event_name": "Individual - Cadets - Female - Foil",
        "category": "Cadet",
        "weapon": "Foil",
        "gender": "Women",
        "date": "2025-12-05",
        "results": [
            {
                "rank": 1,
                "fencer": "Lavender Lee",
                "country": "USA",
                "club": "Golden Gate",
                "points": 96.0,
                "fie_id": None,
                "age": 16,
                "profile_url": "https://www.fencing-efc.eu/fencers/867828",
            }
        ],
    }

    rows = build_result_rows("tournament-1", event, lambda row: None, unmatched.append)

    assert rows[0]["name"] == "Lavender Lee"
    assert rows[0]["fencer_id"] is None
    assert rows[0]["metadata"] == {
        "source": "efc_youth",
        "source_url": "https://fencing-efc.eu/results/cadet-circuit",
        "event_name": "Individual - Cadets - Female - Foil",
        "category": "Cadet",
        "weapon": "Foil",
        "gender": "Women",
        "club": "Golden Gate",
        "points": 96.0,
        "fie_id": None,
        "unmatched": True,
    }
    assert "age" not in rows[0]["metadata"]
    assert "profile_url" not in rows[0]["metadata"]
    assert unmatched == [{"name": "Lavender Lee", "country": "USA", "fie_id": None}]


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []

    def select(self, _columns):
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
        self.client.deleted.append(self.table_name)
        return self

    def insert(self, rows):
        self.client.inserted.extend(rows)
        return self

    def execute(self):
        if self.table_name != "fs_fencers":
            return FakeResponse([])
        filters = {(op, column): value for op, column, value in self.filters}
        if filters.get(("eq", "fie_id")) == "98765":
            return FakeResponse([{"id": "fie-id-match"}])
        if filters.get(("ilike", "name")) == "Matthew Buelau" and filters.get(("eq", "country")) == "GER":
            return FakeResponse([{"id": "name-country-match"}])
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.inserted = []
        self.deleted = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_upsert_results_matches_fie_id_before_name_country_and_logs_unmatched(monkeypatch):
    import scrape_efc_youth

    fake = FakeClient()
    unmatched: list[Any] = []
    monkeypatch.setattr(scrape_efc_youth, "supabase", fake)
    monkeypatch.setattr(scrape_efc_youth, "log_unmatched_fencer", unmatched.append)

    written = scrape_efc_youth.upsert_results(
        "tournament-1",
        {
            "source_url": "https://fencing-efc.eu/results/u20",
            "event_name": "Individual - Juniors - Male - Epee",
            "category": "Junior",
            "weapon": "Epee",
            "gender": "Men",
            "date": "2025-02-27",
            "results": [
                {"rank": 1, "fencer": "Domonkos Pelle", "country": "HUN", "club": "BVSC", "points": 32.0, "fie_id": "98765"},
                {"rank": 2, "fencer": "Matthew Buelau", "country": "GER", "club": None, "points": 26.0, "fie_id": None},
                {"rank": 3, "fencer": "Bartosz Kuznik", "country": "POL", "club": None, "points": 20.0, "fie_id": None},
            ],
        },
    )

    assert written == 3
    assert fake.inserted[0]["fencer_id"] == "fie-id-match"
    assert fake.inserted[1]["fencer_id"] == "name-country-match"
    assert fake.inserted[2]["fencer_id"] is None
    assert unmatched == [{"name": "Bartosz Kuznik", "country": "POL", "fie_id": None}]


class FakeRunLogger:
    def __init__(self):
        self.started = False
        self.completed = None
        self.errors = []

    def start(self):
        self.started = True
        return self

    def complete(self, **kwargs):
        self.completed = kwargs

    def error(self, exc):
        self.errors.append(str(exc))


def test_run_once_records_blocked_sources_as_skipped_without_inventing_rows(monkeypatch):
    import scrape_efc_youth

    logger = FakeRunLogger()
    states = []
    monkeypatch.setattr(scrape_efc_youth, "get_state", lambda source, key: [])
    monkeypatch.setattr(scrape_efc_youth, "set_state", lambda source, key, value: states.append((source, key, value)))
    monkeypatch.setattr(
        scrape_efc_youth,
        "fetch_source_content",
        lambda url: (None, scrape_efc_youth.blocked_source_stub(url, "HTTP 403")),
    )

    result = scrape_efc_youth.run_once(["https://www.fencing-efc.eu/results/private-blocked"], run_logger=logger)

    assert result == {"written": 0, "failed": 0, "skipped": 1}
    assert logger.started is True
    assert logger.completed == {
        "written": 0,
        "failed": 0,
        "skipped": 1,
        "metadata": {
            "blocked_sources": [
                {
                    "source_url": "https://www.fencing-efc.eu/results/private-blocked",
                    "reason": "HTTP 403",
                }
            ],
            "unmatched_fencers": [],
        },
    }
    assert states[-1] == ("efc_youth", "last_run_summary", result)

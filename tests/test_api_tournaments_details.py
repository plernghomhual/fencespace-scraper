import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "api" / "v1" / "tournament_details.py"
TOURNAMENT_ID = "00000000-0000-0000-0000-000000000065"
MISSING_ID = "00000000-0000-0000-0000-000000000066"


def load_module():
    spec = importlib.util.spec_from_file_location("api_v1_tournament_details", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.limit_count = None
        self.selected = None

    def select(self, columns):
        self.selected = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def execute(self):
        rows = list(self.client.tables.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self):
        self.selects = []
        self.tables = {
            "fs_tournaments": [
                {
                    "id": TOURNAMENT_ID,
                    "name": "Seoul Grand Prix",
                    "season": 2026,
                    "start_date": "2026-04-29T10:00:00+09:00",
                    "end_date": "2026-05-01",
                    "country": "KOR",
                    "weapon": "Epee",
                    "category": "Senior",
                    "type": "GP",
                    "metadata": {"internal_note": "do not expose"},
                },
                {
                    "id": MISSING_ID,
                    "name": "Sparse Event",
                    "season": 2026,
                    "country": "USA",
                },
            ],
            "fs_competition_details": [
                {
                    "tournament_id": TOURNAMENT_ID,
                    "organizer": "Korean Fencing Federation",
                    "format_type": "Pools + Direct Elimination",
                    "entry_deadline": "2026-04-01T23:59:00Z",
                    "quota": "212",
                    "venue_name": "Olympic Gymnasium",
                    "venue_city": "Seoul",
                    "venue_country": "KOR",
                    "venue_address": "424 Olympic-ro",
                    "registration_url": "HTTPS://Registration.Example.test/Events/65?Ref=FS",
                    "live_url": "javascript:alert(1)",
                    "metadata": {
                        "scraped_by": "scrape_competition_details",
                        "source_url": "HTTPS://FIE.ORG/competitions/2026/65",
                        "document_urls": ["https://static.fie.org/internal.pdf"],
                    },
                    "scraped_at": "2026-04-02T12:30:00Z",
                },
            ],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_build_tournament_detail_payload_returns_complete_public_details():
    module = load_module()
    fake = FakeSupabase()

    payload = module.get_tournament_detail_payload(fake, TOURNAMENT_ID)

    assert payload == {
        "tournament_id": TOURNAMENT_ID,
        "tournament": {
            "id": TOURNAMENT_ID,
            "name": "Seoul Grand Prix",
            "season": 2026,
            "start_date": "2026-04-29",
            "end_date": "2026-05-01",
            "country": "KOR",
            "weapon": "Epee",
            "category": "Senior",
            "type": "GP",
        },
        "organizer": "Korean Fencing Federation",
        "format": "Pools + Direct Elimination",
        "entry_deadline": "2026-04-01",
        "quota": 212,
        "venue": {
            "name": "Olympic Gymnasium",
            "city": "Seoul",
            "country": "KOR",
            "address": "424 Olympic-ro",
        },
        "registration_url": "https://registration.example.test/Events/65?Ref=FS",
        "live_url": None,
        "source": {
            "url": "https://fie.org/competitions/2026/65",
            "scraped_at": "2026-04-02T12:30:00+00:00",
        },
    }
    assert "metadata" not in payload
    assert "scraped_by" not in repr(payload)
    assert fake.selects == [("fs_tournaments", "*"), ("fs_competition_details", "*")]


def test_tournament_detail_payload_uses_nulls_for_missing_detail_row():
    module = load_module()
    payload = module.get_tournament_detail_payload(FakeSupabase(), MISSING_ID)

    assert payload["tournament_id"] == MISSING_ID
    assert payload["tournament"]["name"] == "Sparse Event"
    assert payload["organizer"] is None
    assert payload["format"] is None
    assert payload["entry_deadline"] is None
    assert payload["quota"] is None
    assert payload["venue"] == {"name": None, "city": None, "country": None, "address": None}
    assert payload["registration_url"] is None
    assert payload["live_url"] is None
    assert payload["source"] == {"url": None, "scraped_at": None}


def test_detail_payload_normalizes_metadata_urls_dates_and_rejects_invalid_values():
    module = load_module()
    tournament = {"id": TOURNAMENT_ID, "name": "Normalization Test", "start_date": "not a date"}
    detail = {
        "organiser": "  British Fencing  ",
        "competition_format": "  Poules  ",
        "registration_deadline": "2026-03-08",
        "entry_quota": "bad-number",
        "location": "  Copper Box Arena  ",
        "registration_link": "http://Example.COM/register#section",
        "live_results_url": "ftp://example.com/live",
        "metadata": {
            "live_url": "https://Live.Example.COM/results",
            "source_url": "/internal/path",
            "updated_at": "2026-03-01 12:00:00+00:00",
        },
    }

    payload = module.build_tournament_detail_payload(tournament, detail)

    assert payload["tournament"]["start_date"] is None
    assert payload["organizer"] == "British Fencing"
    assert payload["format"] == "Poules"
    assert payload["entry_deadline"] == "2026-03-08"
    assert payload["quota"] is None
    assert payload["venue"]["name"] == "Copper Box Arena"
    assert payload["registration_url"] == "http://example.com/register#section"
    assert payload["live_url"] == "https://live.example.com/results"
    assert payload["source"] == {"url": None, "scraped_at": "2026-03-01T12:00:00+00:00"}


def test_invalid_tournament_id_returns_bad_request():
    module = load_module()

    with pytest.raises(module.HTTPException) as excinfo:
        module.get_tournament_detail_payload(FakeSupabase(), "../not-a-uuid")

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Invalid tournament ID"


def test_missing_tournament_returns_not_found():
    module = load_module()
    valid_missing_id = "00000000-0000-0000-0000-000000000999"

    with pytest.raises(module.HTTPException) as excinfo:
        module.get_tournament_detail_payload(FakeSupabase(), valid_missing_id)

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "Tournament not found"


def test_router_returns_scoped_detail_response(monkeypatch):
    module = load_module()
    app = FastAPI()
    app.include_router(module.router)
    monkeypatch.setattr(module, "get_supabase_client", lambda: FakeSupabase())

    response = TestClient(app).get(f"/tournaments/{TOURNAMENT_ID}/details")

    assert response.status_code == 200
    assert response.json()["organizer"] == "Korean Fencing Federation"

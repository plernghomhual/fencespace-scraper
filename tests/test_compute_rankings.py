import importlib
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def fake_supabase(monkeypatch):
    fake_module = types.SimpleNamespace(
        Client=object,
        create_client=lambda url, key: object(),
    )
    monkeypatch.setenv("SUPABASE_URL", "http://localhost")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "supabase", fake_module)
    yield


@pytest.fixture
def compute_module(fake_supabase):
    sys.modules.pop("compute_national_rankings", None)
    module = importlib.import_module("compute_national_rankings")
    yield module
    sys.modules.pop("compute_national_rankings", None)


@pytest.fixture
def scraper_module(fake_supabase):
    sys.modules.pop("scraper", None)
    module = importlib.import_module("scraper")
    yield module
    sys.modules.pop("scraper", None)


def test_result_weight_prefers_type_field_over_name_fallback(compute_module):
    assert compute_module.result_weight({"type": "WCH"}) == 5.0
    assert compute_module.result_weight({"type": "GP", "name": "World Championships"}) == 4.0
    assert compute_module.result_weight({"type": "WC", "name": "Grand Prix Cairo"}) == 3.0
    assert compute_module.result_weight({"type": "CC", "name": "World Championships"}) == 2.5


def test_result_weight_falls_back_to_tournament_text_without_type(compute_module):
    assert compute_module.result_weight({"name": "World Championships Milan"}) == 5.0
    assert compute_module.result_weight({"name": "Grand Prix Budapest"}) == 4.0
    assert compute_module.result_weight({"name": "World Cup Cairo"}) == 3.0
    assert compute_module.result_weight({"name": "Asian Zonal Championships"}) == 2.5
    assert compute_module.result_weight({"name": "National Championship"}) == 1.0


def test_dedupe_fencers_by_fie_id_keeps_most_complete_row(scraper_module):
    rows = [
        {
            "fie_id": "1001",
            "name": "Doe",
            "country": None,
            "weapon": "Foil",
            "category": "Men's Senior",
            "world_rank": None,
            "fie_points": 0,
        },
        {
            "fie_id": "1001",
            "name": "John Doe",
            "country": "United States",
            "weapon": "Epee",
            "category": "Men's Senior",
            "world_rank": 12,
            "fie_points": 42,
            "image_url": "https://example.test/john.jpg",
            "date_of_birth": "1999-01-02",
            "hand": "right",
            "height": 183,
        },
        {
            "fie_id": "1002",
            "name": "Jane Smith",
            "country": "Canada",
            "weapon": "Sabre",
            "category": "Women's Junior",
        },
        {
            "fie_id": "",
            "name": "Missing Id",
            "country": "France",
        },
    ]

    deduped = scraper_module.dedupe_fencers_by_fie_id(rows)

    assert [row["fie_id"] for row in deduped] == ["1001", "1002"]
    assert deduped[0]["name"] == "John Doe"
    assert deduped[0]["country"] == "United States"
    assert deduped[0]["weapon"] == "Epee"


def test_scrape_all_rankings_deduplicates_before_upsert(scraper_module, monkeypatch):
    combos = [
        {"weapon": "F", "gender": "M", "category": "S", "label": "Men's Senior Foil"},
        {"weapon": "E", "gender": "M", "category": "S", "label": "Men's Senior Epee"},
    ]
    combo_rows = {
        "F": [
            {"fie_id": "1001", "name": "Doe", "country": None, "weapon": "Foil"},
            {"fie_id": "1002", "name": "Jane Smith", "country": "Canada", "weapon": "Foil"},
        ],
        "E": [
            {"fie_id": "1001", "name": "John Doe", "country": "United States", "weapon": "Epee"},
        ],
    }
    upserts = []

    def fake_scrape_rankings(weapon, gender, category, label):
        return combo_rows[weapon]

    def fake_batch_upsert(table, rows, on_conflict, batch_size=100):
        upserts.append((table, rows, on_conflict, batch_size))

    monkeypatch.setattr(scraper_module, "scrape_rankings", fake_scrape_rankings)
    monkeypatch.setattr(scraper_module, "batch_upsert", fake_batch_upsert)

    written = scraper_module.scrape_all_rankings(combos=combos, pause_seconds=0)

    assert written == 2
    assert len(upserts) == 1
    assert upserts[0][0] == "fs_fencers"
    assert upserts[0][2] == "fie_id,weapon,category"
    assert [row["fie_id"] for row in upserts[0][1]] == ["1001", "1002"]
    assert upserts[0][1][0]["name"] == "John Doe"

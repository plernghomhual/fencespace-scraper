import importlib.util
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ROOT = Path(__file__).resolve().parents[1]
FENCER_ALICE_FOIL = "00000000-0000-0000-0000-000000000001"
FENCER_ALICE_EPEE = "00000000-0000-0000-0000-000000000002"
FENCER_EMPTY = "00000000-0000-0000-0000-000000000003"
FENCER_MISSING = "00000000-0000-0000-0000-000000000004"


def load_stats_module():
    path = ROOT / "api" / "v1" / "fencer_stats.py"
    spec = importlib.util.spec_from_file_location("fencespace_api_v1_fencer_stats", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.eq_filters = []
        self.in_filters = []
        self.contains_filters = []
        self.limit_count = None
        self.selected = None
        self.order_calls = []

    def select(self, columns):
        self.selected = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.eq_filters.append((column, value))
        return self

    def in_(self, column, values):
        self.in_filters.append((column, [str(value) for value in values]))
        return self

    def contains(self, column, values):
        self.contains_filters.append((column, [str(value) for value in values]))
        return self

    def order(self, column, **kwargs):
        self.order_calls.append((column, kwargs))
        return self

    def limit(self, count):
        self.limit_count = count
        self.client.limits.append((self.table_name, count))
        return self

    def execute(self):
        if self.table_name not in self.client.tables:
            raise RuntimeError(f"missing table {self.table_name}")
        rows = list(self.client.tables[self.table_name])
        for column, value in self.eq_filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        for column, values in self.in_filters:
            rows = [row for row in rows if str(row.get(column)) in values]
        for column, values in self.contains_filters:
            rows = [
                row
                for row in rows
                if all(value in {str(item) for item in row.get(column, [])} for value in values)
            ]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.limits = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def assert_public_payload(value):
    forbidden = {"metadata", "source_url", "scraper_state", "run_id", "updated_at", "created_at"}
    if isinstance(value, dict):
        assert not (set(value) & forbidden)
        for child in value.values():
            assert_public_payload(child)
    elif isinstance(value, list):
        for child in value:
            assert_public_payload(child)


def test_public_stats_aggregates_identity_rows_and_weapon_breakdowns():
    module = load_stats_module()
    client = FakeSupabase(
        {
            "fs_fencers": [
                {"id": FENCER_ALICE_FOIL, "name": "Alice Example"},
                {"id": FENCER_ALICE_EPEE, "name": "Alice Example"},
            ],
            "fs_fencer_identities": [
                {
                    "id": "identity-1",
                    "canonical_name": "Alice Example",
                    "fs_fencer_row_ids": [FENCER_ALICE_FOIL, FENCER_ALICE_EPEE],
                    "metadata": {"private_note": "do not expose"},
                },
                {
                    "id": "identity-duplicate",
                    "canonical_name": "Alice Example",
                    "fs_fencer_row_ids": [FENCER_ALICE_EPEE, FENCER_ALICE_FOIL],
                },
            ],
            "fs_fencer_stats": [
                {
                    "id": "stat-foil",
                    "fencer_id": FENCER_ALICE_FOIL,
                    "weapon": "Foil",
                    "total_bouts": 10,
                    "wins": 7,
                    "losses": 3,
                    "touches_scored": 100,
                    "touches_received": 80,
                    "win_pct": 0.91,
                    "current_streak": 4,
                    "metadata": {"raw": True},
                },
                {
                    "id": "stat-epee",
                    "fencer_id": FENCER_ALICE_EPEE,
                    "weapon": "Epee",
                    "bouts": 5,
                    "wins": 2,
                    "losses": 3,
                    "total_touches_scored": 45,
                    "total_touches_received": 50,
                    "source_url": "https://internal.example.test",
                },
            ],
            "fs_fencer_career_stats": [
                {
                    "fencer_id": FENCER_ALICE_FOIL,
                    "total_competitions": 3,
                    "gold_medals": 1,
                    "silver_medals": 0,
                    "bronze_medals": 0,
                    "top8_count": 2,
                    "best_rank": 1,
                    "updated_at": "2026-06-02T00:00:00Z",
                },
                {
                    "fencer_id": FENCER_ALICE_EPEE,
                    "total_competitions": 1,
                    "gold_medals": 0,
                    "silver_medals": 0,
                    "bronze_medals": 1,
                    "top8_count": 1,
                    "best_rank": 3,
                },
            ],
            "fs_fencer_season_stats": [
                {
                    "fencer_id": FENCER_ALICE_FOIL,
                    "season": 2026,
                    "weapon": "Foil",
                    "starts": 2,
                    "wins": 4,
                    "losses": 1,
                    "touches_scored": 50,
                    "touches_received": 30,
                    "gold_medals": 1,
                    "top8_count": 2,
                    "best_finish": 1,
                    "metadata": {"internal": True},
                },
                {
                    "fencer_id": FENCER_ALICE_EPEE,
                    "season": 2026,
                    "weapon": "Epee",
                    "starts": 1,
                    "wins": 2,
                    "losses": 2,
                    "touches_scored": 37,
                    "touches_received": 39,
                    "bronze_medals": 1,
                    "top8_count": 1,
                    "best_finish": 3,
                },
            ],
        }
    )

    payload = module.get_public_fencer_stats(FENCER_ALICE_FOIL, client=client)

    assert payload["fencer_id"] == FENCER_ALICE_FOIL
    assert payload["bout_record"] == {"bouts": 15, "wins": 9, "losses": 6, "win_pct": 0.6}
    assert payload["touches"] == {"scored": 145, "received": 130, "differential": 15}
    assert payload["placements"]["starts"] == 4
    assert payload["placements"]["medals"] == {"gold": 1, "silver": 0, "bronze": 1, "total": 2}
    assert payload["placements"]["top8"] == 3
    assert payload["placements"]["best_finish"] == 1
    assert payload["streaks"] == {"current": None, "longest_win": None}

    weapons = {row["weapon"]: row for row in payload["weapon_breakdown"]}
    assert weapons["Foil"]["bout_record"] == {"bouts": 10, "wins": 7, "losses": 3, "win_pct": 0.7}
    assert weapons["Epee"]["touches"] == {"scored": 45, "received": 50, "differential": -5}
    assert payload["season_breakdown"] == [
        {
            "season": 2026,
            "weapon": "Epee",
            "starts": 1,
            "bout_record": {"bouts": 4, "wins": 2, "losses": 2, "win_pct": 0.5},
            "touches": {"scored": 37, "received": 39, "differential": -2},
            "placements": {"medals": {"gold": 0, "silver": 0, "bronze": 1, "total": 1}, "top8": 1, "top16": 0, "top32": 0, "best_finish": 3},
        },
        {
            "season": 2026,
            "weapon": "Foil",
            "starts": 2,
            "bout_record": {"bouts": 5, "wins": 4, "losses": 1, "win_pct": 0.8},
            "touches": {"scored": 50, "received": 30, "differential": 20},
            "placements": {"medals": {"gold": 1, "silver": 0, "bronze": 0, "total": 1}, "top8": 2, "top16": 0, "top32": 0, "best_finish": 1},
        },
    ]
    assert ("fs_fencer_identities", "id,fs_fencer_row_ids") in client.selects
    assert ("fs_fencer_stats", module.MAX_STATS_ROWS) in client.limits
    assert_public_payload(payload)


def test_public_stats_returns_zero_blocks_for_existing_fencer_with_no_stats_tables():
    module = load_stats_module()
    client = FakeSupabase({"fs_fencers": [{"id": FENCER_EMPTY, "name": "No Stats"}]})

    payload = module.get_public_fencer_stats(FENCER_EMPTY, client=client)

    assert payload["bout_record"] == {"bouts": 0, "wins": 0, "losses": 0, "win_pct": None}
    assert payload["touches"] == {"scored": 0, "received": 0, "differential": 0}
    assert payload["placements"] == {
        "starts": 0,
        "medals": {"gold": 0, "silver": 0, "bronze": 0, "total": 0},
        "top8": 0,
        "top16": 0,
        "top32": 0,
        "best_finish": None,
    }
    assert payload["weapon_breakdown"] == []
    assert payload["season_breakdown"] == []
    assert payload["available_sources"] == {"bout_stats": False, "career_stats": False, "season_stats": False}


def test_public_stats_validation_and_not_found_errors():
    module = load_stats_module()
    client = FakeSupabase({"fs_fencers": [{"id": FENCER_EMPTY, "name": "No Stats"}]})

    with pytest.raises(HTTPException) as bad_id:
        module.get_public_fencer_stats("not-a-uuid", client=client)
    assert bad_id.value.status_code == 422

    with pytest.raises(HTTPException) as bad_weapon:
        module.get_public_fencer_stats(FENCER_EMPTY, client=client, weapon="Longsword")
    assert bad_weapon.value.status_code == 422

    with pytest.raises(HTTPException) as missing:
        module.get_public_fencer_stats(FENCER_MISSING, client=client)
    assert missing.value.status_code == 404


def test_public_stats_route_validates_expensive_request_caps(monkeypatch):
    module = load_stats_module()
    client = FakeSupabase({"fs_fencers": [{"id": FENCER_EMPTY, "name": "No Stats"}]})
    monkeypatch.setattr(module, "get_supabase_client", lambda: client)

    app = FastAPI()
    app.include_router(module.router)
    test_client = TestClient(app)

    response = test_client.get(f"/fencer/{FENCER_EMPTY}/stats?season_limit={module.MAX_SEASON_ROWS + 1}")

    assert response.status_code == 422

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
TOURNAMENT_ID = "11111111-1111-4111-8111-111111111111"
OTHER_TOURNAMENT_ID = "22222222-2222-4222-8222-222222222222"
EVENT_EPEE = "33333333-3333-4333-8333-333333333333"
EVENT_FOIL = "44444444-4444-4444-8444-444444444444"
FENCER_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
FENCER_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
FENCER_C = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
FENCER_D = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"


def load_bracket_module():
    module_path = ROOT / "api" / "v1" / "tournament_brackets.py"
    spec = importlib.util.spec_from_file_location("tournament_brackets_under_test", module_path)
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
        self.filters = []
        self.orders = []
        self.start = None
        self.end = None
        self.selected = None

    def select(self, columns):
        self.selected = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.client.filters.append((self.table_name, column, value))
        return self

    def order(self, column, **kwargs):
        self.orders.append((column, kwargs))
        self.client.orders.append((self.table_name, column, kwargs))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.client.ranges.append((self.table_name, start, end))
        return self

    def execute(self):
        rows = list(self.client.tables.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        if self.orders:
            for column, kwargs in reversed(self.orders):
                descending = kwargs.get("desc", False)
                rows.sort(key=lambda row: (row.get(column) is None, row.get(column)), reverse=descending)
        if self.start is not None and self.end is not None:
            rows = rows[self.start : self.end + 1]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self, rows):
        self.tables = {"fs_tournament_brackets": rows}
        self.selects = []
        self.filters = []
        self.orders = []
        self.ranges = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def bracket_row(**overrides):
    row = {
        "id": "row-1",
        "tournament_id": TOURNAMENT_ID,
        "event_id": EVENT_EPEE,
        "event_key": "senior-men-epee",
        "weapon": "Epee",
        "gender": "Men",
        "category": "Senior",
        "round_name": "Table of 8",
        "round_order": 1,
        "bout_order": 1,
        "fencer_a_id": FENCER_A,
        "fencer_a_name": "Alex Lee",
        "fencer_a_country": "KOR",
        "fencer_a_seed": 1,
        "fencer_b_id": FENCER_B,
        "fencer_b_name": "Mina Park",
        "fencer_b_country": "KOR",
        "fencer_b_seed": 8,
        "score_a": 15,
        "score_b": 8,
        "winner_id": FENCER_A,
        "is_bye": False,
        "source": "fixture",
        "metadata": {"piste": "Blue", "source_bout_id": "de-1"},
    }
    row.update(overrides)
    return row


def test_helper_groups_complete_bracket_by_event_round_and_bout_order():
    module = load_bracket_module()
    fake = FakeSupabase(
        [
            bracket_row(id="late-bout", bout_order=2, fencer_a_id=FENCER_C, fencer_a_seed=4),
            bracket_row(id="first-bout", bout_order=1),
            bracket_row(
                id="semifinal",
                round_name="Semifinal",
                round_order=2,
                bout_order=1,
                fencer_a_id=FENCER_A,
                fencer_a_seed=1,
                fencer_b_id=FENCER_C,
                fencer_b_seed=4,
                score_a=15,
                score_b=12,
                winner_id=FENCER_A,
            ),
            bracket_row(
                id="foil-bout",
                event_id=EVENT_FOIL,
                event_key="junior-women-foil",
                weapon="Foil",
                gender="Women",
                category="Junior",
                fencer_a_id=FENCER_D,
                fencer_b_id=FENCER_B,
                fencer_a_seed=2,
                fencer_b_seed=7,
            ),
        ]
    )

    payload = module.get_tournament_bracket_payload(fake, TOURNAMENT_ID)

    assert payload["tournament_id"] == TOURNAMENT_ID
    assert payload["count"] == {"events": 2, "rounds": 3, "bouts": 4}
    assert [event["event_key"] for event in payload["events"]] == [
        "senior-men-epee",
        "junior-women-foil",
    ]

    epee = payload["events"][0]
    assert epee["weapon"] == "Epee"
    assert epee["gender"] == "Men"
    assert epee["category"] == "Senior"
    assert [round_["round_name"] for round_ in epee["rounds"]] == ["Table of 8", "Semifinal"]
    assert [bout["id"] for bout in epee["rounds"][0]["bouts"]] == ["first-bout", "late-bout"]

    first = epee["rounds"][0]["bouts"][0]
    assert first["status"] == "complete"
    assert first["score"] == {"a": 15, "b": 8}
    assert first["winner_id"] == FENCER_A
    assert first["fencer_a"] == {
        "id": FENCER_A,
        "name": "Alex Lee",
        "country": "KOR",
        "seed": 1,
    }
    assert first["fencer_b"]["id"] == FENCER_B
    assert first["metadata"] == {"piste": "Blue", "source_bout_id": "de-1"}


def test_helper_preserves_byes_and_missing_scores_without_fabricating_matches():
    module = load_bracket_module()
    fake = FakeSupabase(
        [
            bracket_row(
                id="bye-bout",
                fencer_b_id=None,
                fencer_b_name=None,
                fencer_b_seed=None,
                score_a=None,
                score_b=None,
                winner_id=FENCER_A,
                is_bye=True,
            ),
            bracket_row(
                id="incomplete-bout",
                bout_order=2,
                fencer_a_id=FENCER_C,
                fencer_b_id=FENCER_D,
                score_a=None,
                score_b=None,
                winner_id=None,
            ),
        ]
    )

    payload = module.get_tournament_bracket_payload(fake, TOURNAMENT_ID)
    bouts = payload["events"][0]["rounds"][0]["bouts"]

    assert [bout["id"] for bout in bouts] == ["bye-bout", "incomplete-bout"]
    assert bouts[0]["status"] == "bye"
    assert bouts[0]["is_bye"] is True
    assert bouts[0]["fencer_b"] is None
    assert bouts[0]["score"] == {"a": None, "b": None}
    assert bouts[1]["status"] == "incomplete"
    assert bouts[1]["winner_id"] is None
    assert bouts[1]["score"] == {"a": None, "b": None}


def test_helper_applies_event_filters_and_returns_empty_for_missing_data():
    module = load_bracket_module()
    fake = FakeSupabase(
        [
            bracket_row(),
            bracket_row(
                id="foil-bout",
                event_id=EVENT_FOIL,
                event_key="junior-women-foil",
                weapon="Foil",
                gender="Women",
                category="Junior",
            ),
            bracket_row(id="other-tournament", tournament_id=OTHER_TOURNAMENT_ID),
        ]
    )

    payload = module.get_tournament_bracket_payload(
        fake,
        TOURNAMENT_ID,
        weapon="Foil",
        gender="Women",
        category="Junior",
        event_id=EVENT_FOIL,
    )
    empty = module.get_tournament_bracket_payload(fake, OTHER_TOURNAMENT_ID, weapon="Sabre")

    assert [event["event_key"] for event in payload["events"]] == ["junior-women-foil"]
    assert payload["count"] == {"events": 1, "rounds": 1, "bouts": 1}
    assert empty["events"] == []
    assert empty["count"] == {"events": 0, "rounds": 0, "bouts": 0}
    assert ("fs_tournament_brackets", "tournament_id", TOURNAMENT_ID) in fake.filters
    assert ("fs_tournament_brackets", "weapon", "Foil") in fake.filters
    assert ("fs_tournament_brackets", "event_id", EVENT_FOIL) in fake.filters


def test_helper_rejects_invalid_tournament_id_and_oversized_response():
    module = load_bracket_module()

    with pytest.raises(ValueError, match="Invalid tournament_id"):
        module.get_tournament_bracket_payload(FakeSupabase([]), "not-a-uuid")

    with pytest.raises(HTTPException) as exc:
        module.get_tournament_bracket_payload(
            FakeSupabase([bracket_row(id="one"), bracket_row(id="two")]),
            TOURNAMENT_ID,
            max_rows=1,
        )

    assert exc.value.status_code == 413
    assert "exceeds max_rows" in exc.value.detail


def test_router_exposes_brackets_endpoint_with_dependency_injection():
    module = load_bracket_module()
    fake = FakeSupabase([bracket_row(id="route-bout")])
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_supabase_client] = lambda: fake

    client = TestClient(app)
    response = client.get(f"/tournaments/{TOURNAMENT_ID}/brackets?weapon=Epee")

    assert response.status_code == 200
    assert response.json()["events"][0]["rounds"][0]["bouts"][0]["id"] == "route-bout"

    invalid = client.get("/tournaments/not-a-uuid/brackets")
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "Invalid tournament_id"

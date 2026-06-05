import importlib.util
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


MODULE_PATH = Path(__file__).resolve().parents[1] / "api" / "v1" / "fencer_h2h.py"

ALICE_FOIL = "00000000-0000-0000-0000-000000000001"
ALICE_EPEE = "00000000-0000-0000-0000-000000000002"
BOB_EPEE = "00000000-0000-0000-0000-000000000003"
BOB_FOIL = "00000000-0000-0000-0000-000000000004"
CAROL = "00000000-0000-0000-0000-000000000005"
DAN = "00000000-0000-0000-0000-000000000006"
EMPTY_FENCER = "00000000-0000-0000-0000-000000000007"


def load_h2h_module():
    if not MODULE_PATH.exists():
        pytest.fail("api/v1/fencer_h2h.py is missing")
    spec = importlib.util.spec_from_file_location("fencer_h2h_under_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load module")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
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
        self.overlap_filters = []
        self.start = None
        self.end = None
        self.selected = None

    def select(self, columns):
        self.selected = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.eq_filters.append((column, value))
        return self

    def in_(self, column, values):
        self.in_filters.append((column, {str(value) for value in values}))
        return self

    def overlaps(self, column, values):
        self.overlap_filters.append((column, {str(value) for value in values}))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.client.ranges.append((self.table_name, start, end))
        return self

    def execute(self):
        if self.table_name not in self.client.tables:
            raise RuntimeError(f"missing table {self.table_name}")

        rows = list(self.client.tables[self.table_name])
        for column, value in self.eq_filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        for column, values in self.in_filters:
            rows = [row for row in rows if str(row.get(column)) in values]
        for column, values in self.overlap_filters:
            rows = [
                row
                for row in rows
                if values.intersection({str(item) for item in row.get(column, [])})
            ]
        if self.start is not None and self.end is not None:
            rows = rows[self.start : self.end + 1]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self, tables=None):
        self.tables = tables or base_tables()
        self.selects = []
        self.ranges = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def fencer_row(fencer_id, name, country, weapon, category):
    return {
        "id": fencer_id,
        "fie_id": f"FIE-{fencer_id[-4:]}",
        "name": name,
        "country": country,
        "weapon": weapon,
        "category": category,
        "world_rank": 12,
        "metadata": {"internal": True},
        "updated_at": "2026-06-01T00:00:00+00:00",
        "scraped_at": "2026-06-01T00:00:00+00:00",
    }


def h2h_row(
    fencer_a_id,
    fencer_b_id,
    weapon,
    a_wins,
    b_wins,
    bouts_total,
    last_meeting_date,
    last_winner_id,
):
    return {
        "id": f"h2h-{fencer_a_id[-2:]}-{fencer_b_id[-2:]}-{weapon}",
        "fencer_a_id": fencer_a_id,
        "fencer_b_id": fencer_b_id,
        "weapon": weapon,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "a_touches": a_wins * 15,
        "b_touches": b_wins * 15,
        "bouts_total": bouts_total,
        "last_meeting_date": last_meeting_date,
        "last_winner_id": last_winner_id,
        "updated_at": "2026-06-01T00:00:00+00:00",
        "metadata": {"private": True},
    }


def base_tables():
    return {
        "fs_fencers": [
            fencer_row(ALICE_FOIL, "Alice Kim", "KOR", "Foil", "Senior"),
            fencer_row(ALICE_EPEE, "Alice Kim", "KOR", "Epee", "Junior"),
            fencer_row(BOB_EPEE, "Bob Stone", "USA", "Epee", "Senior"),
            fencer_row(BOB_FOIL, "Bob Stone", "USA", "Foil", "Senior"),
            fencer_row(CAROL, "Carol Diaz", "ESP", "Sabre", "Senior"),
            fencer_row(DAN, "Dan Novak", "CZE", "Foil", "Senior"),
            fencer_row(EMPTY_FENCER, "Empty Fencer", "CAN", "Epee", "Senior"),
        ],
        "fs_fencer_identities": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "canonical_name": "Alice Kim",
                "country": "KOR",
                "fie_ids": ["FIE-0001", "FIE-0002"],
                "fs_fencer_row_ids": [ALICE_FOIL, ALICE_EPEE],
                "metadata": {"private": True},
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "canonical_name": "Bob Stone",
                "country": "USA",
                "fie_ids": ["FIE-0003", "FIE-0004"],
                "fs_fencer_row_ids": [BOB_EPEE, BOB_FOIL],
                "metadata": {"private": True},
            },
        ],
        "fs_head_to_head": [
            h2h_row(ALICE_FOIL, BOB_EPEE, "Foil", 2, 1, 3, "2026-01-10", ALICE_FOIL),
            h2h_row(BOB_FOIL, ALICE_EPEE, "Epee", 1, 4, 5, "2026-03-01", BOB_FOIL),
            h2h_row(ALICE_FOIL, CAROL, "Sabre", 0, 2, 2, "2025-11-01", CAROL),
            h2h_row(ALICE_FOIL, DAN, "Foil", 1, 0, 1, "2025-05-05", ALICE_FOIL),
        ],
    }


def test_helper_groups_duplicate_fencer_identities_and_sanitizes_public_response():
    module = load_h2h_module()
    payload = module.get_fencer_h2h(FakeSupabase(), ALICE_FOIL)

    assert payload["fencer_id"] == ALICE_FOIL
    assert payload["filters"] == {"weapon": None, "category": None}
    assert payload["weapon_filters"] == ["Epee", "Foil", "Sabre"]
    assert payload["pagination"] == {"limit": 50, "offset": 0, "count": 3, "total": 3}

    bob = payload["opponents"][0]
    assert bob["opponent"]["id"] == BOB_EPEE
    assert bob["opponent"]["name"] == "Bob Stone"
    assert "metadata" not in bob["opponent"]
    assert "updated_at" not in bob["opponent"]
    assert bob["total_bouts"] == 8
    assert bob["fencer_wins"] == 6
    assert bob["opponent_wins"] == 2
    assert bob["last_meeting"] == {
        "date": "2026-03-01",
        "weapon": "Epee",
        "winner_id": BOB_FOIL,
    }
    assert bob["records"] == [
        {
            "weapon": "Epee",
            "bouts_total": 5,
            "fencer_wins": 4,
            "opponent_wins": 1,
            "fencer_touches": 60,
            "opponent_touches": 15,
            "last_meeting_date": "2026-03-01",
            "last_winner_id": BOB_FOIL,
        },
        {
            "weapon": "Foil",
            "bouts_total": 3,
            "fencer_wins": 2,
            "opponent_wins": 1,
            "fencer_touches": 30,
            "opponent_touches": 15,
            "last_meeting_date": "2026-01-10",
            "last_winner_id": ALICE_FOIL,
        },
    ]
    assert all("updated_at" not in record for opponent in payload["opponents"] for record in opponent["records"])


def test_helper_filters_by_weapon_and_identity_scoped_category():
    module = load_h2h_module()
    payload = module.get_fencer_h2h(
        FakeSupabase(),
        ALICE_FOIL,
        weapon="epee",
        category="junior",
    )

    assert payload["filters"] == {"weapon": "Epee", "category": "Junior"}
    assert payload["weapon_filters"] == ["Epee", "Foil", "Sabre"]
    assert [opponent["opponent"]["name"] for opponent in payload["opponents"]] == ["Bob Stone"]
    assert payload["opponents"][0]["records"][0]["weapon"] == "Epee"
    assert payload["opponents"][0]["fencer_wins"] == 4


def test_helper_paginates_after_grouping_opponent_summaries():
    module = load_h2h_module()
    payload = module.get_fencer_h2h(FakeSupabase(), ALICE_FOIL, limit=1, offset=1)

    assert payload["pagination"] == {"limit": 1, "offset": 1, "count": 1, "total": 3}
    assert [opponent["opponent"]["name"] for opponent in payload["opponents"]] == ["Carol Diaz"]


def test_helper_returns_empty_arrays_when_fencer_has_no_h2h_rows():
    module = load_h2h_module()
    payload = module.get_fencer_h2h(FakeSupabase(), EMPTY_FENCER)

    assert payload == {
        "fencer_id": EMPTY_FENCER,
        "filters": {"weapon": None, "category": None},
        "weapon_filters": [],
        "opponents": [],
        "pagination": {"limit": 50, "offset": 0, "count": 0, "total": 0},
    }


def test_helper_raises_404_for_missing_fencer():
    module = load_h2h_module()

    with pytest.raises(HTTPException) as exc:
        module.get_fencer_h2h(FakeSupabase(), "00000000-0000-0000-0000-000000000099")

    assert exc.value.status_code == 404
    assert exc.value.detail == "Fencer not found"


@pytest.mark.parametrize(
    ("kwargs", "detail"),
    [
        ({"fencer_id": "not-a-uuid"}, "Invalid fencer ID"),
        ({"weapon": "axe"}, "Invalid weapon"),
        ({"category": "open"}, "Invalid category"),
        ({"limit": 0}, "Invalid pagination"),
        ({"offset": -1}, "Invalid pagination"),
    ],
)
def test_helper_validates_ids_filters_and_pagination(kwargs, detail):
    module = load_h2h_module()
    params = {"supabase": FakeSupabase(), "fencer_id": ALICE_FOIL}
    params.update(kwargs)

    with pytest.raises(HTTPException) as exc:
        module.get_fencer_h2h(**params)

    assert exc.value.status_code == 422
    assert exc.value.detail == detail


def test_router_exposes_fencer_h2h_endpoint_with_query_validation():
    module = load_h2h_module()
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_supabase_client] = lambda: FakeSupabase()
    client = TestClient(app)

    response = client.get(f"/fencer/{ALICE_FOIL}/h2h?weapon=foil&limit=2&offset=0")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"] == {"weapon": "Foil", "category": None}
    assert [opponent["opponent"]["name"] for opponent in payload["opponents"]] == [
        "Bob Stone",
        "Dan Novak",
    ]

    invalid = client.get(f"/fencer/{ALICE_FOIL}/h2h?limit=501")
    assert invalid.status_code == 422

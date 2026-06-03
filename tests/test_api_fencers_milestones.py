import importlib.util
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "api" / "v1" / "fencer_milestones.py"

FENCER_CANONICAL = "00000000-0000-0000-0000-000000000001"
FENCER_DUPLICATE = "00000000-0000-0000-0000-000000000002"
FENCER_EMPTY = "00000000-0000-0000-0000-000000000003"
FENCER_MISSING = "00000000-0000-0000-0000-000000000004"
IDENTITY_ID = "10000000-0000-0000-0000-000000000001"


def load_module():
    spec = importlib.util.spec_from_file_location("api_v1_fencer_milestones", MODULE_PATH)
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

    def select(self, columns):
        self.selected = columns
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

    def limit(self, count):
        self.limit_count = count
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        self.client.queries.append(
            {
                "table": self.table_name,
                "eq": list(self.eq_filters),
                "in": list(self.in_filters),
                "contains": list(self.contains_filters),
                "limit": self.limit_count,
            }
        )
        rows = list(self.client.tables.get(self.table_name, []))
        for column, value in self.eq_filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        for column, values in self.in_filters:
            rows = [row for row in rows if str(row.get(column)) in values]
        for column, values in self.contains_filters:
            rows = [
                row
                for row in rows
                if all(str(value) in {str(item) for item in row.get(column, [])} for value in values)
            ]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.queries = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def make_client(milestones):
    return FakeSupabase(
        {
            "fs_fencers": [
                {"id": FENCER_CANONICAL, "name": "Alice Example", "country": "USA"},
                {"id": FENCER_DUPLICATE, "name": "Alice Example", "country": "USA"},
                {"id": FENCER_EMPTY, "name": "Empty Fencer", "country": "CAN"},
            ],
            "fs_fencer_identities": [
                {
                    "id": IDENTITY_ID,
                    "canonical_id": FENCER_CANONICAL,
                    "fs_fencer_row_ids": [FENCER_CANONICAL, FENCER_DUPLICATE],
                }
            ],
            "fs_career_milestones": milestones,
        }
    )


def test_timeline_orders_dedupes_duplicate_fencer_rows_and_returns_public_safe_fields():
    module = load_module()
    client = make_client(
        [
            {
                "id": "internal-latest",
                "fencer_id": FENCER_CANONICAL,
                "fencer_identity_id": IDENTITY_ID,
                "milestone_type": "first_gold",
                "milestone_date": "2026-04-15",
                "title": "First senior gold",
                "description": "Won Seoul Grand Prix.",
                "tournament_id": "t-2",
                "tournament_name": "Seoul Grand Prix",
                "weapon": "Epee",
                "source": "fie-results",
                "evidence": {"url": "https://example.test/result", "rank": 1, "private_note": "drop"},
                "metadata": {"raw_payload": {"secret": "not public"}},
            },
            {
                "id": "internal-duplicate",
                "fencer_id": FENCER_DUPLICATE,
                "fencer_identity_id": IDENTITY_ID,
                "milestone_type": "first_gold",
                "milestone_date": "2026-04-15",
                "title": "First senior gold",
                "description": "Won Seoul Grand Prix.",
                "tournament_id": "t-2",
                "tournament_name": "Seoul Grand Prix",
                "weapon": "Epee",
                "source": "fie-results",
                "evidence": {"url": "https://example.test/result", "rank": 1},
            },
            {
                "id": "internal-tie-b",
                "fencer_id": FENCER_CANONICAL,
                "milestone_type": "first_top8",
                "milestone_date": "2025-03-02",
                "title": "First top eight",
                "description": "Reached a World Cup quarterfinal.",
                "tournament_id": "t-1",
                "tournament_name": "Paris World Cup",
                "weapon": "Foil",
                "source": {"name": "FIE", "url": "https://example.test/paris"},
            },
            {
                "id": "internal-tie-a",
                "fencer_id": FENCER_DUPLICATE,
                "milestone_type": "first_medal",
                "milestone_date": "2025-03-02",
                "title": "First medal",
                "description": "Bronze at Paris World Cup.",
                "tournament_id": "t-1",
                "tournament_name": "Paris World Cup",
                "weapon": "Foil",
                "source": "fie-results",
            },
        ]
    )

    payload = module.get_fencer_milestone_timeline(client, FENCER_DUPLICATE, limit=10, offset=0)

    assert payload["pagination"] == {"limit": 10, "offset": 0, "count": 3}
    assert [(row["date"], row["type"], row["title"]) for row in payload["data"]] == [
        ("2026-04-15", "first_gold", "First senior gold"),
        ("2025-03-02", "first_medal", "First medal"),
        ("2025-03-02", "first_top8", "First top eight"),
    ]
    first = payload["data"][0]
    assert first == {
        "type": "first_gold",
        "date": "2026-04-15",
        "title": "First senior gold",
        "description": "Won Seoul Grand Prix.",
        "tournament": {"id": "t-2", "name": "Seoul Grand Prix"},
        "weapon": "Epee",
        "evidence": {"url": "https://example.test/result", "rank": 1},
        "source": "fie-results",
    }
    assert "id" not in first
    assert "fencer_id" not in first
    assert "metadata" not in first


def test_timeline_filters_type_and_paginates_after_dedupe():
    module = load_module()
    client = make_client(
        [
            {
                "fencer_id": FENCER_CANONICAL,
                "fencer_identity_id": IDENTITY_ID,
                "milestone_type": "first_gold",
                "milestone_date": "2026-04-15",
                "title": "First senior gold",
                "tournament_id": "t-2",
                "weapon": "Epee",
            },
            {
                "fencer_id": FENCER_DUPLICATE,
                "fencer_identity_id": IDENTITY_ID,
                "milestone_type": "first-gold",
                "milestone_date": "2025-04-15",
                "title": "Earlier gold",
                "tournament_id": "t-1",
                "weapon": "Foil",
            },
            {
                "fencer_id": FENCER_CANONICAL,
                "fencer_identity_id": IDENTITY_ID,
                "milestone_type": "first_medal",
                "milestone_date": "2024-01-01",
                "title": "First medal",
                "tournament_id": "t-0",
                "weapon": "Foil",
            },
        ]
    )

    payload = module.get_fencer_milestone_timeline(
        client,
        FENCER_CANONICAL,
        milestone_type="first-gold",
        limit=1,
        offset=1,
    )

    assert payload["pagination"] == {"limit": 1, "offset": 1, "count": 1}
    assert [(row["date"], row["title"]) for row in payload["data"]] == [("2025-04-15", "Earlier gold")]


def test_timeline_returns_empty_array_for_fencer_with_no_milestones():
    module = load_module()
    client = make_client([])

    payload = module.get_fencer_milestone_timeline(client, FENCER_EMPTY)

    assert payload == {"data": [], "pagination": {"limit": 50, "offset": 0, "count": 0}}


def test_timeline_raises_404_for_missing_fencer():
    module = load_module()
    client = make_client([])

    with pytest.raises(HTTPException) as exc_info:
        module.get_fencer_milestone_timeline(client, FENCER_MISSING)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Fencer not found"


@pytest.mark.parametrize(
    ("kwargs", "detail"),
    [
        ({"fencer_id": "not-a-uuid"}, "Invalid fencer_id"),
        ({"fencer_id": FENCER_CANONICAL, "milestone_type": "raw_sql"}, "Invalid milestone_type"),
        ({"fencer_id": FENCER_CANONICAL, "limit": 0}, "limit must be between 1 and 500"),
        ({"fencer_id": FENCER_CANONICAL, "limit": 501}, "limit must be between 1 and 500"),
        ({"fencer_id": FENCER_CANONICAL, "offset": -1}, "offset must be greater than or equal to 0"),
    ],
)
def test_timeline_validates_params(kwargs, detail):
    module = load_module()
    client = make_client([])

    with pytest.raises(HTTPException) as exc_info:
        module.get_fencer_milestone_timeline(client, **kwargs)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == detail


def test_create_router_exposes_importable_fastapi_route():
    module = load_module()
    client = make_client(
        [
            {
                "fencer_id": FENCER_CANONICAL,
                "fencer_identity_id": IDENTITY_ID,
                "milestone_type": "first_result",
                "milestone_date": "2024-11-01",
                "title": "First international result",
                "source": "fie-results",
            }
        ]
    )
    app = FastAPI()
    app.include_router(module.create_router(lambda: client))

    response = TestClient(app).get(f"/fencer/{FENCER_CANONICAL}/milestones")

    assert response.status_code == 200
    assert response.json()["data"][0]["title"] == "First international result"

import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "api" / "v1" / "fencer_ranking_trajectory.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fencer_ranking_trajectory_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_payload_normalizes_mixed_seasons_and_sorts_chronologically():
    module = load_module()
    rows = [
        {
            "fencer_id": "f1",
            "source": "fie",
            "season": 2026,
            "weapon": "Epee",
            "category": "Senior",
            "rank": 9,
            "points": "141.5",
            "rank_delta": -2,
            "metadata": {"private": True},
            "name": "Should Not Leak",
        },
        {
            "fencer_id": "f1",
            "source": "fie",
            "season": "2023-2024",
            "weapon": "Epee",
            "category": "Senior",
            "rank": 12,
            "points": 100,
        },
        {
            "fencer_id": "f1",
            "source": "fie",
            "season": "2025",
            "weapon": "Epee",
            "category": "Senior",
            "rank": 11,
            "points": None,
        },
    ]

    payload = module.build_ranking_trajectory_payload(rows, fencer_id="f1")

    assert [point["season"] for point in payload["history"]] == [
        "2023-2024",
        "2024-2025",
        "2025-2026",
    ]
    assert [point["season_end_year"] for point in payload["history"]] == [2024, 2025, 2026]
    assert payload["history"][2]["points"] == 141.5
    assert payload["history"][2]["rank_delta"] == -2
    assert "metadata" not in payload["history"][2]
    assert "name" not in payload["history"][2]


def test_build_payload_applies_filters_after_normalization_and_limit():
    module = load_module()
    rows = [
        {"fencer_id": "f1", "source": "fie", "season": 2026, "weapon": "Epee", "category": "Senior", "rank": 1},
        {
            "fencer_id": "f1",
            "source": "british_fencing",
            "season": "2025-2026",
            "weapon": "Epee",
            "category": "Senior",
            "rank": 4,
        },
        {
            "fencer_id": "f1",
            "source": "british_fencing",
            "season": "2024-2025",
            "weapon": "Foil",
            "category": "Senior",
            "rank": 7,
        },
        {
            "fencer_id": "f1",
            "source": "british_fencing",
            "season": "2025-2026",
            "weapon": "Epee",
            "category": "Junior",
            "rank": 2,
        },
    ]

    payload = module.build_ranking_trajectory_payload(
        rows,
        fencer_id="f1",
        source="british_fencing",
        season="2026",
        weapon="epee",
        category="senior",
        limit=1,
    )

    assert payload["filters"] == {
        "source": "british_fencing",
        "season": "2025-2026",
        "weapon": "Epee",
        "category": "Senior",
        "limit": 1,
    }
    assert payload["count"] == 1
    assert payload["history"] == [
        {
            "source": "british_fencing",
            "season": "2025-2026",
            "season_end_year": 2026,
            "weapon": "Epee",
            "category": "Senior",
            "rank": 4,
            "points": None,
            "rank_delta": None,
            "points_delta": None,
            "updated_at": None,
        }
    ]


def test_build_payload_returns_empty_history_for_fencer_without_rankings():
    module = load_module()
    rows = [
        {"fencer_id": "other", "source": "fie", "season": 2026, "weapon": "Epee", "category": "Senior", "rank": 1}
    ]

    payload = module.build_ranking_trajectory_payload(rows, fencer_id="f1")

    assert payload["fencer_id"] == "f1"
    assert payload["count"] == 0
    assert payload["history"] == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fencer_id": ""},
        {"fencer_id": "../f1"},
        {"fencer_id": "f1", "source": "bad source"},
        {"fencer_id": "f1", "weapon": "pistol"},
        {"fencer_id": "f1", "category": "Open"},
        {"fencer_id": "f1", "season": "2025/2026"},
        {"fencer_id": "f1", "limit": 0},
        {"fencer_id": "f1", "limit": 101},
    ],
)
def test_validate_trajectory_params_rejects_invalid_values(kwargs):
    module = load_module()

    with pytest.raises(ValueError):
        module.validate_trajectory_params(**kwargs)


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.selected = None

    def select(self, columns):
        self.selected = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.client.filters.append((self.table_name, column, value))
        return self

    def execute(self):
        if self.client.raise_missing_table:
            raise RuntimeError('relation "fs_ranking_history_trajectory" does not exist')
        rows = list(self.client.rows)
        for column, value in self.filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self, rows=None, raise_missing_table=False):
        self.rows = rows or []
        self.raise_missing_table = raise_missing_table
        self.selects = []
        self.filters = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_router_returns_ordered_public_trajectory_with_fake_client(monkeypatch):
    module = load_module()
    fake = FakeSupabase(
        [
            {"fencer_id": "f1", "source": "fie", "season": 2026, "weapon": "Epee", "category": "Senior", "rank": 5},
            {
                "fencer_id": "f1",
                "source": "fie",
                "season": "2024-2025",
                "weapon": "Epee",
                "category": "Senior",
                "rank": 7,
            },
        ]
    )
    monkeypatch.setattr(module, "get_supabase_client", lambda: fake)
    app = FastAPI()
    app.include_router(module.router)

    response = TestClient(app).get("/fencers/f1/ranking-trajectory?source=fie&limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert [point["season"] for point in payload["history"]] == ["2024-2025", "2025-2026"]
    assert [point["rank"] for point in payload["history"]] == [7, 5]
    assert ("fs_ranking_history_trajectory", "fencer_id", "f1") in fake.filters
    assert "source_table" not in payload


def test_router_returns_empty_history_when_trajectory_table_is_missing(monkeypatch):
    module = load_module()
    fake = FakeSupabase(raise_missing_table=True)
    monkeypatch.setattr(module, "get_supabase_client", lambda: fake)
    app = FastAPI()
    app.include_router(module.router)

    response = TestClient(app).get("/fencers/f1/ranking-trajectory")

    assert response.status_code == 200
    assert response.json()["history"] == []
    assert response.json()["count"] == 0

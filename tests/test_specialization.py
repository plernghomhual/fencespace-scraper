import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FENCER_ALICE_FOIL = "00000000-0000-0000-0000-0000000000a1"
FENCER_ALICE_EPEE_ROW = "00000000-0000-0000-0000-0000000000a2"
FENCER_BOB = "00000000-0000-0000-0000-0000000000b1"
FENCER_CAROL = "00000000-0000-0000-0000-0000000000c1"
FENCER_DANA = "00000000-0000-0000-0000-0000000000d1"
FENCER_ERIN = "00000000-0000-0000-0000-0000000000e1"
FENCER_FAYE = "00000000-0000-0000-0000-0000000000f1"
NOW = "2026-06-01T12:00:00+00:00"


def test_specialization_report_classifies_weapons_and_compares_success_rates():
    from compute_specialization import build_specialization_report

    tournaments = {
        "foil-2025": {
            "id": "foil-2025",
            "season": "2025",
            "weapon": "foil",
            "category": "Senior",
            "gender": "Women",
            "start_date": "2025-01-10",
        },
        "foil-2026": {
            "id": "foil-2026",
            "season": "2026",
            "weapon": "Foil",
            "category": "Senior",
            "gender": "Women",
            "start_date": "2026-01-10",
        },
        "epee-2025": {
            "id": "epee-2025",
            "season": "2025",
            "weapon": "Epee",
            "category": "Senior",
            "gender": "Men",
            "start_date": "2025-02-05",
        },
        "epee-2026": {
            "id": "epee-2026",
            "season": "2026",
            "weapon": "Epee",
            "category": "Senior",
            "gender": "Men",
            "start_date": "2026-02-05",
        },
        "sabre-2026": {
            "id": "sabre-2026",
            "season": "2026",
            "weapon": "Sabre",
            "category": "Senior",
            "gender": "Men",
            "start_date": "2026-03-01",
        },
        "foil-2024": {
            "id": "foil-2024",
            "season": "2024",
            "weapon": "Foil",
            "category": "Senior",
            "gender": "Women",
            "start_date": "2024-12-12",
        },
    }
    results = [
        {"fencer_id": FENCER_ALICE_FOIL, "tournament_id": "foil-2025", "rank": 1},
        {"fencer_id": FENCER_ALICE_EPEE_ROW, "tournament_id": "foil-2026", "rank": 2},
        {"fencer_id": FENCER_BOB, "tournament_id": "epee-2025", "rank": 3},
        {"fencer_id": FENCER_BOB, "tournament_id": "epee-2026", "rank": 5},
        {"fencer_id": FENCER_BOB, "tournament_id": "sabre-2026", "rank": 9},
        {"fencer_id": FENCER_CAROL, "tournament_id": "foil-2024", "rank": 4},
        {"fencer_id": None, "tournament_id": "foil-2024", "rank": 8},
    ]

    report = build_specialization_report(
        results=results,
        tournaments=tournaments,
        identity_map={FENCER_ALICE_EPEE_ROW: FENCER_ALICE_FOIL},
        computed_at=NOW,
    )
    fencers = {row["fencer_id"]: row for row in report["fencers"]}

    alice = fencers[FENCER_ALICE_FOIL]
    assert alice["classification"] == "single_weapon"
    assert alice["primary_weapon"] == "Foil"
    assert alice["weapons"] == ["Foil"]
    assert alice["total_competitions"] == 2
    assert alice["avg_rank"] == 1.5
    assert alice["medal_count"] == 2
    assert alice["medals_per_competition"] == 1.0

    bob = fencers[FENCER_BOB]
    assert bob["classification"] == "multi_weapon"
    assert bob["primary_weapon"] == "Epee"
    assert bob["weapons"] == ["Epee", "Sabre"]
    assert bob["per_weapon"]["Epee"]["results"] == 2
    assert bob["per_weapon"]["Epee"]["avg_rank"] == 4.0
    assert bob["per_weapon"]["Sabre"]["avg_rank"] == 9.0
    assert bob["medal_count"] == 1
    assert bob["medals_per_competition"] == pytest.approx(0.33)

    aggregate = report["aggregate"]
    assert aggregate["specialists"]["fencers"] == 2
    assert aggregate["generalists"]["fencers"] == 1
    assert aggregate["specialists"]["avg_rank"] == pytest.approx(2.33)
    assert aggregate["generalists"]["avg_rank"] == pytest.approx(5.67)
    assert aggregate["specialists"]["medals_per_competition"] == pytest.approx(0.67)
    assert aggregate["generalists"]["avg_rank_by_weapon"] == {"Epee": 4.0, "Sabre": 9.0}
    assert aggregate["specialist_vs_generalist"]["verdict"] == "specialists_outperform"
    assert report["skipped_results"] == 1


def test_report_computes_junior_to_senior_transition_and_weapon_switching():
    from compute_specialization import build_specialization_report

    tournaments = {
        "junior-foil": {
            "id": "junior-foil",
            "season": "2023",
            "weapon": "Foil",
            "category": "Women's Junior",
            "start_date": "2023-05-01",
        },
        "senior-epee": {
            "id": "senior-epee",
            "season": "2024",
            "weapon": "Epee",
            "category": "Women's Senior",
            "start_date": "2024-11-10",
        },
        "junior-sabre": {
            "id": "junior-sabre",
            "season": "2023",
            "weapon": "Sabre",
            "category": "Junior",
            "start_date": "2023-06-01",
        },
        "senior-foil": {
            "id": "senior-foil",
            "season": "2024",
            "weapon": "Foil",
            "category": "Senior",
            "start_date": "2024-04-01",
        },
    }
    results = [
        {"fencer_id": FENCER_DANA, "tournament_id": "junior-foil", "rank": 6},
        {"fencer_id": FENCER_DANA, "tournament_id": "senior-epee", "rank": 4},
        {"fencer_id": FENCER_ERIN, "tournament_id": "junior-sabre", "rank": 2},
        {"fencer_id": FENCER_FAYE, "tournament_id": "senior-foil", "rank": 7},
    ]
    fencers = [
        {"id": FENCER_DANA, "date_of_birth": "2006-01-15"},
        {"id": FENCER_ERIN, "date_of_birth": "2007-09-01"},
        {"id": FENCER_FAYE, "date_of_birth": "2002-03-20"},
    ]

    report = build_specialization_report(
        results=results,
        tournaments=tournaments,
        fencers=fencers,
        computed_at=NOW,
    )

    transition = report["category_transition"]
    assert transition["junior_fencers"] == 2
    assert transition["senior_transitioners"] == 1
    assert transition["junior_to_senior_pct"] == 50.0
    assert transition["avg_transition_age"] == 18.8
    assert transition["avg_years_between_first_junior_and_senior"] == 1.5
    assert transition["transitions"] == [
        {
            "fencer_id": FENCER_DANA,
            "first_junior_competition": "junior-foil",
            "first_senior_competition": "senior-epee",
            "first_junior_date": "2023-05-01",
            "first_senior_date": "2024-11-10",
            "transition_age": 18.8,
            "years_between": 1.5,
        }
    ]

    switching = report["weapon_switching"]
    assert switching["fencers_with_multiple_seasons"] == 1
    assert switching["switching_fencers"] == 1
    assert switching["switching_pct"] == 100.0
    assert switching["avg_rank_delta_after_switch"] == -2.0
    assert switching["improved_after_switch_pct"] == 100.0
    assert switching["switches"] == [
        {
            "fencer_id": FENCER_DANA,
            "from_season": "2023",
            "to_season": "2024",
            "from_weapon": "Foil",
            "to_weapon": "Epee",
            "before_avg_rank": 6.0,
            "after_avg_rank": 4.0,
            "rank_delta": -2.0,
        }
    ]


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.columns = None
        self.range_start = 0
        self.range_end = None

    def select(self, columns):
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def execute(self):
        if self.name not in self.client.tables:
            raise RuntimeError(f"missing table {self.name}")
        end = self.range_end if self.range_end is not None else len(self.client.tables[self.name]) - 1
        return FakeResult(self.client.tables[self.name][self.range_start : end + 1])

    def upsert(self, rows, on_conflict=None):
        self.client.upserted.setdefault(self.name, []).extend(rows)
        return self


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.upserted = {}

    def table(self, name):
        return FakeTable(self, name)


def test_compute_specialization_fetches_inputs_and_returns_compact_summary():
    from compute_specialization import compute_specialization

    client = FakeSupabase(
        {
            "fs_results": [
                {"fencer_id": FENCER_ALICE_FOIL, "tournament_id": "foil-2025", "rank": 1},
                {"fencer_id": FENCER_ALICE_EPEE_ROW, "tournament_id": "epee-2026", "rank": 5},
                {"fencer_id": None, "tournament_id": "foil-2025", "rank": 8},
            ],
            "fs_tournaments": [
                {
                    "id": "foil-2025",
                    "season": "2025",
                    "weapon": "Foil",
                    "category": "Senior",
                    "start_date": "2025-01-10",
                },
                {
                    "id": "epee-2026",
                    "season": "2026",
                    "weapon": "Epee",
                    "category": "Senior",
                    "start_date": "2026-01-10",
                },
            ],
            "fs_fencers": [
                {"id": FENCER_ALICE_FOIL, "fie_id": "1001", "date_of_birth": "2005-01-01"},
                {"id": FENCER_ALICE_EPEE_ROW, "fie_id": "1001", "date_of_birth": "2005-01-01"},
            ],
            "fs_fencer_identities": [
                {
                    "canonical_id": FENCER_ALICE_FOIL,
                    "fs_fencer_row_ids": [FENCER_ALICE_FOIL, FENCER_ALICE_EPEE_ROW],
                }
            ],
            "fs_fencer_specialization": [],
        }
    )

    summary = compute_specialization(
        client=client,
        page_size=2,
        log_run=False,
        update_state=False,
        computed_at=NOW,
    )

    assert summary["results_read"] == 3
    assert summary["tournaments_read"] == 2
    assert summary["fencers_read"] == 2
    assert summary["identity_rows"] == 1
    assert summary["fencers_analyzed"] == 1
    assert summary["single_weapon_fencers"] == 0
    assert summary["multi_weapon_fencers"] == 1
    assert summary["skipped_results"] == 1
    assert summary["weapon_switching_fencers"] == 1
    assert summary["report"]["fencers"][0]["primary_weapon"] == "Epee"
    assert (
        "tournament_id,fencer_id,fie_fencer_id,weapon,category,season,rank,placement,medal,date"
        in [columns for _, columns in client.selects]
    )

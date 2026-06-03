import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ENTRANTS = [
    {"fencer_id": "fencer-a", "name": "Ada Allez", "seed": 1},
    {"fencer_id": "fencer-b", "name": "Bea Blade", "seed": 2},
    {"fencer_id": "fencer-c", "name": "Cy Cut", "seed": 3},
    {"fencer_id": "fencer-d", "name": "Dee Duel", "seed": 4},
]


def test_seed_determinism_for_simple_standings_mode():
    from simulate_tournament import simulate_tournament

    ratings = {
        "fencer-a": 1900,
        "fencer-b": 1700,
        "fencer-c": 1500,
        "fencer-d": 1300,
    }

    first = simulate_tournament(
        entrants=ENTRANTS,
        elo_ratings=ratings,
        format_hint="standings",
        seed=20260602,
        iterations=250,
    )
    second = simulate_tournament(
        entrants=ENTRANTS,
        elo_ratings=ratings,
        format_hint="standings",
        seed=20260602,
        iterations=250,
    )

    assert first == second
    assert first["mode"] == "simple_standings"
    assert first["seed"] == 20260602
    assert first["iterations"] == 250


def test_probability_markets_normalize_to_available_slots():
    from simulate_tournament import simulate_tournament

    result = simulate_tournament(
        entrants=ENTRANTS,
        elo_ratings={"fencer-a": 1700, "fencer-b": 1600, "fencer-c": 1500, "fencer-d": 1400},
        format_hint="standings",
        seed=17,
        iterations=300,
    )

    probabilities = result["probabilities"]
    assert sum(probabilities["winner"].values()) == pytest.approx(1.0)
    assert sum(probabilities["medal"].values()) == pytest.approx(3.0)
    assert sum(probabilities["top8"].values()) == pytest.approx(4.0)
    assert set(probabilities["winner"]) == {"fencer-a", "fencer-b", "fencer-c", "fencer-d"}


def test_known_small_direct_elimination_bracket_uses_elo_not_historical_winners():
    from simulate_tournament import simulate_tournament

    entrants = copy.deepcopy(ENTRANTS)
    bracket_rows = [
        {
            "round_name": "Table of 4",
            "bout_order": 1,
            "fencer_a_id": "fencer-a",
            "fencer_b_id": "fencer-d",
            "winner_id": "fencer-d",
        },
        {
            "round_name": "Table of 4",
            "bout_order": 2,
            "fencer_a_id": "fencer-b",
            "fencer_b_id": "fencer-c",
            "winner_id": "fencer-c",
        },
        {
            "round_name": "Final",
            "bout_order": 1,
            "fencer_a_id": "fencer-d",
            "fencer_b_id": "fencer-c",
            "winner_id": "fencer-d",
        },
    ]
    original_entrants = copy.deepcopy(entrants)
    original_bracket_rows = copy.deepcopy(bracket_rows)

    result = simulate_tournament(
        entrants=entrants,
        elo_ratings={
            "fencer-a": 2400,
            "fencer-b": 1600,
            "fencer-c": 1600,
            "fencer-d": 1000,
        },
        format_hint="direct_elimination",
        bracket_rows=bracket_rows,
        seed=11,
        iterations=400,
    )

    assert entrants == original_entrants
    assert bracket_rows == original_bracket_rows
    assert result["mode"] == "direct_elimination"
    assert result["confidence"] == "high"
    assert result["probabilities"]["winner"]["fencer-a"] > 0.96
    assert result["probabilities"]["winner"]["fencer-d"] < 0.01
    assert sum(result["probabilities"]["medal"].values()) == pytest.approx(4.0)
    assert all(value == pytest.approx(1.0) for value in result["probabilities"]["top8"].values())
    assert "historical winner fields ignored" in " ".join(result["warnings"])


def test_missing_elo_uses_neutral_rating_and_flags_lower_confidence():
    from simulate_tournament import DEFAULT_ELO, simulate_tournament

    result = simulate_tournament(
        entrants=[
            {"fencer_id": "fencer-a", "name": "Ada Allez"},
            {"fencer_id": "fencer-b", "name": "Bea Blade"},
        ],
        elo_ratings={},
        format_hint=None,
        bracket_rows=None,
        seed=5,
        iterations=100,
    )

    assert result["mode"] == "partial_data_fallback"
    assert result["confidence"] == "low"
    assert result["participants"] == [
        {"fencer_id": "fencer-a", "name": "Ada Allez", "rating": DEFAULT_ELO, "seed": None},
        {"fencer_id": "fencer-b", "name": "Bea Blade", "rating": DEFAULT_ELO, "seed": None},
    ]
    assert sum(result["probabilities"]["winner"].values()) == pytest.approx(1.0)
    assert sum(result["probabilities"]["medal"].values()) == pytest.approx(2.0)
    assert any("Missing Elo" in warning for warning in result["warnings"])
    assert any("No bracket" in warning for warning in result["warnings"])


def test_cli_writes_json_without_mutating_source_tables(tmp_path):
    from simulate_tournament import main

    payload = {
        "tournament_id": "fixture-tournament",
        "entrants": [
            {"fencer_id": "fencer-a", "name": "Ada Allez", "seed": 1},
            {"fencer_id": "fencer-b", "name": "Bea Blade", "seed": 2},
        ],
        "elo_ratings": {"fencer-a": 1800, "fencer-b": 1200},
        "format": "standings",
    }
    input_path = tmp_path / "fixture.json"
    output_path = tmp_path / "simulation.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    assert main(
        [
            "--tournament-id",
            "fixture-tournament",
            "--input-json",
            str(input_path),
            "--seed",
            "99",
            "--iterations",
            "50",
            "--output-json",
            str(output_path),
            "--no-log",
        ]
    ) == 0

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["tournament_id"] == "fixture-tournament"
    assert written["mode"] == "simple_standings"
    assert sum(written["probabilities"]["winner"].values()) == pytest.approx(1.0)
    assert json.loads(input_path.read_text(encoding="utf-8")) == payload

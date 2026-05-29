"""
Tests for scrape_fed_canada.py

Data source: https://rankingapi.fencing.ca/api/rankings/published
  — Public REST API (no auth) backing ranking.fencing.ca
  — Single JSON array; each item has weapon, gender, ageCategory, ranks[]
  — Weapon values: "epee", "fleuret" (=Foil), "sabre"
  — Gender values: "M", "F"
  — ageCategory.code: "senior", "junior", "cadet", "V4", etc.
  — Each rank entry: {position, points, player{firstName, lastName, club, ...}}

Fixtures are trimmed representations of real API responses.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_API_RESPONSE = [
    {
        "_id": "aaaa0001",
        "weapon": "fleuret",
        "gender": "M",
        "ageCategory": {"_id": "aaa1", "name": "Senior", "code": "senior"},
        "ranks": [
            {
                "_id": "r001",
                "position": 1,
                "points": 429.6,
                "player": {
                    "_id": "p001",
                    "firstName": "Adrian",
                    "lastName": "Wong",
                    "club": "TFC",
                    "province": "ON",
                    "cffNumber": "C01-0001",
                },
            },
            {
                "_id": "r002",
                "position": 2,
                "points": 361.9,
                "player": {
                    "_id": "p002",
                    "firstName": "jason",
                    "lastName": "yu",
                    "club": "UTA",
                    "province": "AB",
                    "cffNumber": "C01-0002",
                },
            },
            {
                "_id": "r003",
                "position": 3,
                "points": 335.2,
                "player": {
                    "_id": "p003",
                    "firstName": "xinhao (sonny)",
                    "lastName": "xu",
                    "club": "",
                    "province": "ON",
                    "cffNumber": "C01-0003",
                },
            },
        ],
    },
    {
        "_id": "aaaa0002",
        "weapon": "epee",
        "gender": "F",
        "ageCategory": {"_id": "aaa2", "name": "Junior", "code": "junior"},
        "ranks": [
            {
                "_id": "r010",
                "position": 1,
                "points": 250.0,
                "player": {
                    "_id": "p010",
                    "firstName": "Marie",
                    "lastName": "Dupont",
                    "club": "MCF",
                    "province": "QC",
                    "cffNumber": "C02-0001",
                },
            },
        ],
    },
    {
        # Cadet category — should be skipped (not in RANKING_COMBOS)
        "_id": "aaaa0003",
        "weapon": "sabre",
        "gender": "M",
        "ageCategory": {"_id": "aaa3", "name": "Cadet", "code": "cadet"},
        "ranks": [
            {
                "_id": "r020",
                "position": 1,
                "points": 100.0,
                "player": {
                    "_id": "p020",
                    "firstName": "Test",
                    "lastName": "Cadet",
                    "club": "ABC",
                    "province": "BC",
                    "cffNumber": "C03-0001",
                },
            },
        ],
    },
]

FIXTURE_API_EMPTY_RANKS = [
    {
        "_id": "bbbb0001",
        "weapon": "sabre",
        "gender": "F",
        "ageCategory": {"_id": "bbb1", "name": "Senior", "code": "senior"},
        "ranks": [],
    }
]

FIXTURE_API_EMPTY_LIST = []

FIXTURE_API_MISSING_FIELDS = [
    {
        "_id": "cccc0001",
        "weapon": None,
        "gender": "M",
        "ageCategory": {"code": "senior"},
        "ranks": [
            {
                "_id": "r030",
                "position": 1,
                "points": 50.0,
                "player": {"firstName": "Ghost", "lastName": "Fencer", "club": "X"},
            }
        ],
    },
    {
        "_id": "cccc0002",
        "weapon": "epee",
        "gender": None,
        "ageCategory": {"code": "senior"},
        "ranks": [],
    },
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParseCffRankings:
    def test_returns_rows_for_foil_men_senior(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        key = ("Foil", "Men", "Senior")
        assert key in result
        rows = result[key]
        assert len(rows) == 3

    def test_first_row_rank_and_name(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        first = result[("Foil", "Men", "Senior")][0]
        assert first["rank"] == 1
        assert first["name"] == "Adrian Wong"

    def test_first_row_points(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        first = result[("Foil", "Men", "Senior")][0]
        assert first["points"] == 429.6

    def test_first_row_club(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        first = result[("Foil", "Men", "Senior")][0]
        assert first["club"] == "TFC"

    def test_second_row(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        second = result[("Foil", "Men", "Senior")][1]
        assert second["rank"] == 2
        assert second["name"] == "Jason Yu"
        assert second["points"] == 361.9

    def test_name_is_title_cased(self):
        """Names from the API can be lowercase; parser should title-case them."""
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        rows = result[("Foil", "Men", "Senior")]
        # "jason yu" -> "Jason Yu"
        assert rows[1]["name"] == "Jason Yu"

    def test_empty_club_becomes_none(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        # Third entry has club=""
        third = result[("Foil", "Men", "Senior")][2]
        assert third["club"] is None

    def test_epee_women_junior(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        key = ("Epee", "Women", "Junior")
        assert key in result
        rows = result[key]
        assert len(rows) == 1
        assert rows[0]["name"] == "Marie Dupont"
        assert rows[0]["points"] == 250.0

    def test_cadet_category_excluded(self):
        """Cadet combos are not in RANKING_COMBOS and should not appear in results."""
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        assert ("Sabre", "Men", "Cadet") not in result

    def test_empty_ranks_list_returns_empty(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_EMPTY_RANKS)
        # Key may or may not be present; if present, rows must be empty
        rows = result.get(("Sabre", "Women", "Senior"), [])
        assert rows == []

    def test_empty_api_response_returns_empty_dict(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_EMPTY_LIST)
        assert result == {}

    def test_missing_weapon_field_skipped(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_MISSING_FIELDS)
        # weapon=None and gender=None items should produce no results
        assert result == {}

    def test_all_rows_have_required_fields(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        for combo, rows in result.items():
            for r in rows:
                assert isinstance(r["rank"], int), f"rank must be int, got {type(r['rank'])}"
                assert isinstance(r["name"], str) and r["name"], "name must be non-empty str"
                assert r["points"] is None or isinstance(r["points"], float)

    def test_fleuret_mapped_to_foil(self):
        """CFF uses 'fleuret'; must map to 'Foil'."""
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        # "fleuret" weapon -> key starts with "Foil"
        foil_keys = [k for k in result if k[0] == "Foil"]
        assert len(foil_keys) > 0

    def test_gender_m_maps_to_men(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        men_keys = [k for k in result if k[1] == "Men"]
        assert len(men_keys) > 0

    def test_gender_f_maps_to_women(self):
        from scrape_fed_canada import parse_cff_rankings

        result = parse_cff_rankings(FIXTURE_API_RESPONSE)
        women_keys = [k for k in result if k[1] == "Women"]
        assert len(women_keys) > 0

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


SATELLITE_COMPETITION = {
    "competitionId": 901001,
    "name": "Satellite Tournament Copenhagen",
    "country": "DEN",
    "location": "Copenhagen",
    "startDate": "12-01-2026",
    "endDate": "13-01-2026",
    "weapon": "epee",
    "gender": "men",
    "category": "senior",
    "type": "individual",
    "level": "Satellite",
    "competitionCategory": "",
    "hasResults": 0,
    "season": 2026,
}

CHALLENGE_COMPETITION = {
    "competitionId": 901002,
    "name": "Challenge International Paris",
    "country": "FRA",
    "location": "Paris",
    "startDate": "14-02-2026",
    "endDate": "15-02-2026",
    "weapon": "foil",
    "gender": "women",
    "category": "junior",
    "type": "individual",
    "level": "",
    "competitionCategory": "Challenge",
    "hasResults": 1,
    "season": 2026,
}

WORLD_CUP_COMPETITION = {
    "competitionId": 901003,
    "name": "World Cup Somewhere",
    "country": "ITA",
    "location": "Rome",
    "startDate": "20-03-2026",
    "endDate": "21-03-2026",
    "weapon": "sabre",
    "gender": "men",
    "category": "senior",
    "type": "individual",
    "level": "World Cup",
    "competitionCategory": "",
    "hasResults": 1,
    "season": 2026,
}

RESULT_HTML = """
<html><head><script>
window._competition = {"competitionId": 901001, "name": "Satellite Tournament Copenhagen"};
window._results = {"rows": [
  {"rank": "1", "name": "ROSSI Anna", "nationality": "ITA", "country": "ITA", "fencerId": 111, "victory": 6, "matches": 6, "td": 30, "tr": 12, "diff": 18},
  {"rank": "2", "name": "Marie Curie", "nationality": "FRA", "country": "FRA", "victory": 5, "matches": 6},
  {"rank": "3", "name": "Unmatched Fencer", "nationality": "USA", "fencerId": 999}
]};
</script></head><body></body></html>
"""


def test_filters_satellite_and_challenge_events_and_maps_tournament_metadata():
    from scrape_fie_satellite import (
        competition_to_tournament_row,
        filter_satellite_challenge_competitions,
        should_check_result_page,
    )

    competitions = filter_satellite_challenge_competitions(
        [SATELLITE_COMPETITION, CHALLENGE_COMPETITION, WORLD_CUP_COMPETITION]
    )

    assert [comp["competitionId"] for comp in competitions] == [901001, 901002]

    row = competition_to_tournament_row(SATELLITE_COMPETITION, 2026)
    assert row["source_id"] == "fie:satellite_challenge:2026:901001"
    assert row["fie_id"] == 901001
    assert row["name"] == "Satellite Tournament Copenhagen"
    assert row["season"] == "2026"
    assert row["weapon"] == "Epee"
    assert row["gender"] == "Men"
    assert row["category"] == "Senior"
    assert row["start_date"] == "2026-01-12"
    assert row["end_date"] == "2026-01-13"
    assert row["location"] == "Copenhagen"
    assert row["country"] == "Denmark"
    assert row["source_url"] == "https://fie.org/competitions/2026/901001"
    assert row["has_results"] is True
    assert row["metadata"]["target_series"] == "satellite"
    assert row["metadata"]["source_has_results"] == 0
    assert should_check_result_page(SATELLITE_COMPETITION) is True


def test_extracts_result_rows_matches_fie_id_first_then_identity_name_country_and_logs_unmatched():
    from scrape_fie_satellite import (
        build_fencer_index,
        extract_window_blocks,
        parse_result_rows,
    )

    fencer_index = build_fencer_index(
        [
            {"id": "fencer-fie", "fie_id": "111", "name": "Different Name", "country": "United States"},
            {"id": "fencer-name", "fie_id": None, "name": "Marie Curie", "country": "France"},
        ],
        [
            {
                "id": "identity-marie",
                "canonical_name": "Marie Curie",
                "country": "France",
                "fie_ids": [],
                "fs_fencer_row_ids": ["fencer-name"],
            }
        ],
    )
    blocks = extract_window_blocks(RESULT_HTML)

    rows, unmatched = parse_result_rows(
        tournament_id="tournament-1",
        raw_rows=blocks["_results"]["rows"],
        fencer_index=fencer_index,
        source_url="https://fie.org/competitions/2026/901001",
    )

    assert [row["name"] for row in rows] == ["Anna Rossi", "Marie Curie"]
    assert rows[0]["fie_fencer_id"] == "111"
    assert rows[0]["fencer_id"] == "fencer-fie"
    assert rows[0]["metadata"]["fencer_match_tier"] == "fie_id"
    assert rows[0]["country"] == "Italy"
    assert rows[1]["fie_fencer_id"] is None
    assert rows[1]["fencer_id"] == "fencer-name"
    assert rows[1]["metadata"]["fencer_match_tier"] == "identity_name_country"
    assert len(unmatched) == 1
    assert unmatched[0]["fie_fencer_id"] == "999"
    assert unmatched[0]["reason"] == "no_fencer_match"
    assert all(row["fencer_id"] for row in rows)


def test_fetch_result_rows_handles_404_and_empty_pages():
    from scrape_fie_satellite import NoopRateLimiter, fetch_result_rows

    class Response:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text
            self.url = "https://fie.org/competitions/2026/901001"

    class Session:
        def __init__(self, responses):
            self.responses = list(responses)

        def get(self, url, headers=None, timeout=None, allow_redirects=True):
            return self.responses.pop(0)

    assert fetch_result_rows(Session([Response(404, "not found")]), 2026, 901001, NoopRateLimiter()) == []
    assert fetch_result_rows(Session([Response(200, "<html></html>")]), 2026, 901001, NoopRateLimiter()) == []


def test_fetch_competitions_handles_404_and_empty_search_responses():
    from scrape_fie_satellite import NoopRateLimiter, fetch_competitions

    class Response:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text

        def json(self):
            return {"items": [], "pageSize": 300}

    class Session:
        def __init__(self, responses):
            self.responses = list(responses)

        def post(self, url, headers=None, json=None, timeout=None):
            return self.responses.pop(0)

    assert fetch_competitions(Session([Response(404, "not found")]), 2026, rate_limiter=NoopRateLimiter()) == []
    assert fetch_competitions(Session([Response(200, "")]), 2026, rate_limiter=NoopRateLimiter()) == []


def test_parse_result_rows_skips_ambiguous_name_country_matches_without_null_orphans():
    from scrape_fie_satellite import build_fencer_index, parse_result_rows

    fencer_index = build_fencer_index(
        [
            {"id": "fencer-a", "fie_id": None, "name": "Same Name", "country": "France"},
            {"id": "fencer-b", "fie_id": None, "name": "Same Name", "country": "France"},
        ],
        [],
    )

    rows, unmatched = parse_result_rows(
        tournament_id="tournament-2",
        raw_rows=[{"rank": "1", "name": "Same Name", "nationality": "FRA"}],
        fencer_index=fencer_index,
        source_url="https://fie.org/competitions/2026/901002",
    )

    assert rows == []
    assert len(unmatched) == 1
    assert unmatched[0]["name"] == "Same Name"
    assert unmatched[0]["reason"] == "no_fencer_match"


def test_resolve_competition_url_id_uses_existing_discovery_helper(monkeypatch):
    import scrape_fie_satellite

    calls = []

    def fake_discover(session, tournament, limiter):
        calls.append((session, tournament, limiter))
        return "resolved-url-id"

    monkeypatch.setattr(scrape_fie_satellite, "discover_url_id_for_tournament", fake_discover)

    row = scrape_fie_satellite.competition_to_tournament_row(SATELLITE_COMPETITION, 2026)
    url_id = scrape_fie_satellite.resolve_competition_url_id(
        session="session",
        tournament_row=row,
        rate_limiter="limiter",
    )

    assert url_id == "resolved-url-id"
    assert calls == [("session", row, "limiter")]

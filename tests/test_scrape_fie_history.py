import pytest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Actual API returns lowercase text for weapon/gender/category, competitionId, type as individual/team
SAMPLE_COMPETITIONS = [
    {
        "competitionId": 12345,
        "name": "Grand Prix Budapest",
        "country": "hungary",
        "location": "Budapest",
        "startDate": "12-03-2010",
        "endDate": "14-03-2010",
        "weapon": "epee",
        "gender": "men",
        "category": "senior",
        "type": "individual",
        "hasResults": 0,
        "season": 2010,
    },
    {
        "competitionId": 12346,
        "name": "World Championships",
        "country": "france",
        "location": "Paris",
        "startDate": "01-07-2010",
        "endDate": "08-07-2010",
        "weapon": "epee",
        "gender": "men",
        "category": "senior",
        "type": "team",
        "hasResults": 1,
        "season": 2010,
    },
]


def test_competition_to_tournament_row():
    from scrape_fie_history import competition_to_tournament_row
    row = competition_to_tournament_row(SAMPLE_COMPETITIONS[0], season=2010)
    assert row["fie_id"] == 12345
    assert row["name"] == "Grand Prix Budapest"
    assert row["weapon"] == "Epee"
    assert row["gender"] == "Men"
    assert row["category"] == "Senior"
    assert row["start_date"] == "2010-03-12"
    assert row["end_date"] == "2010-03-14"
    assert row["type"] == "individual"
    assert row["season"] == "2010"
    assert row["country"] == "hungary"
    assert row["location"] == "Budapest"


def test_competition_to_tournament_row_world_championship():
    from scrape_fie_history import competition_to_tournament_row
    row = competition_to_tournament_row(SAMPLE_COMPETITIONS[1], season=2010)
    assert row["type"] == "team"
    assert row["name"] == "World Championships"


def test_normalize_fie_date():
    from scrape_fie_history import normalize_fie_date
    assert normalize_fie_date("12-03-2010") == "2010-03-12"
    assert normalize_fie_date("01-07-2010") == "2010-07-01"
    assert normalize_fie_date(None) is None
    assert normalize_fie_date("") is None
    assert normalize_fie_date("bad-date") is None


def test_seasons_to_scrape():
    from scrape_fie_history import seasons_to_scrape
    seasons = seasons_to_scrape(earliest=2000, current=2026)
    assert 2000 in seasons
    assert 2026 in seasons
    assert len(seasons) == 27
    assert seasons == list(range(2000, 2027))


def test_veteran_has_results_override():
    """FIE API wrongly sets hasResults=0 for veteran events; override for past events."""
    from scrape_fie_history import competition_to_tournament_row
    comp = {
        "competitionId": 9999,
        "name": "Championnats du Monde Vétérans",
        "country": "FRA",
        "location": "Paris",
        "startDate": "01-03-2024",
        "endDate": "03-03-2024",
        "weapon": "epee",
        "gender": "men",
        "category": "veteran",
        "type": "individual",
        "hasResults": 0,
        "season": 2024,
    }
    row = competition_to_tournament_row(comp, 2024)
    assert row["has_results"] is True


def test_non_veteran_zero_results_stays_false():
    """Non-veteran events with hasResults=0 should remain has_results=False."""
    from scrape_fie_history import competition_to_tournament_row
    comp = {
        "competitionId": 8888,
        "name": "Grand Prix Paris",
        "country": "FRA",
        "location": "Paris",
        "startDate": "01-03-2024",
        "endDate": "03-03-2024",
        "weapon": "foil",
        "gender": "women",
        "category": "senior",
        "type": "individual",
        "hasResults": 0,
        "season": 2024,
    }
    row = competition_to_tournament_row(comp, 2024)
    assert row["has_results"] is False


def test_veteran_no_end_date_stays_false():
    """Veteran events without endDate (future) should not be overridden."""
    from scrape_fie_history import competition_to_tournament_row
    comp = {
        "competitionId": 7777,
        "name": "Championnats du Monde Vétérans",
        "country": "FRA",
        "location": "Paris",
        "startDate": "01-03-2025",
        "endDate": "",
        "weapon": "sabre",
        "gender": "women",
        "category": "veteran",
        "type": "individual",
        "hasResults": 0,
        "season": 2025,
    }
    row = competition_to_tournament_row(comp, 2025)
    assert row["has_results"] is False

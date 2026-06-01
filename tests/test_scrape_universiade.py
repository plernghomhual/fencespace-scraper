import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# Captured with pdfplumber from FISU's official statistics PDF
# SUMMER-STATS-1959-2025_Final-20260109.pdf, Fencing page 101.
FISU_STATS_TABLE_2019_2021 = [
    ["2019", "INDIVIDUAL EVENTS", None, None],
    [None, "GOLD", "SILVER", "BRONZE"],
    ["EPEE", "RUBES MARTIN (CZE)", "GUSEV DMITRIY (RUS)", "JANG HYOMIN (KOR)\nKOLANCZYK WOJCIECH (POL)"],
    [None, "LOUIS MARIE ALEXANDRA (FRA)", "ZHARKOVA EVGENIYA (RUS)", "TAL NICKOL (ISR)\nMARZANI ROBERTA (ITA)"],
    ["FOIL", "ROSATELLI DAMIANO (ITA)", "BIANCHI GUILLAUME (ITA)", "ELICE MEDDY (FRA)\nUENO YUTO (JPN)"],
    [None, "CIPRESSA ERICA (ITA)", "PATRU MORGANE (FRA)", "MANCINI CAMILLA (ITA)\nCALUGAREANU MALINA (ROU)"],
    ["SABRE", "OH SANGUK (KOR)", "KINDLER FREDERIC (GER)", "NERI MATTEO (ITA)\nURSACHI RAZVAN (ROU)"],
    [None, "BALZER SARA (FRA)", "LUCARINI LUCIA (ITA)", "BATTISTON MICHELA (ITA)\nJEON SUIN (KOR)"],
    ["", "", "TEAM EVENTS", ""],
    ["", "GOLD", "SILVER", "BRONZE"],
    ["EPEE", "RUS", "HUN", "KOR"],
    [None, "UKR", "USA", "POL"],
    ["FOIL", "JPN", "RUS", "ITA"],
    [None, "ITA", "RUS", "POL"],
    ["SABRE", "KOR", "GER", "FRA"],
    [None, "ITA", "FRA", "KOR"],
    ["2021", "INDIVIDUAL EVENTS", None, None],
    [None, "GOLD", "SILVER", "BRONZE"],
    ["EPEE", "JEAN-JOSEPH KENDRICK (FRA)", "SYCH YAN (UKR)", "MIDELTON LUIDGI (FRA) / XIU YUHAN (CHN)"],
    [None, "HSIEH KAYLIN SIN YAN (HKG)", "KOWALCZYK SARA MARIA (ITA)", "NIXON CATHERINE DANUTA (USA) / TERAYAMA\nTAMAKI (JPN)"],
    ["", "", "TEAM EVENTS", ""],
    ["", "GOLD", "SILVER", "BRONZE"],
    ["EPEE", "FRA", "CHN", "ITA"],
    [None, "CHN", "ITA", "HUN"],
]


def test_parse_fisu_stats_table_discovers_individual_and_team_events():
    from scrape_universiade import parse_fisu_stats_tables

    events = parse_fisu_stats_tables([FISU_STATS_TABLE_2019_2021])
    event_codes = {event["event_code"] for event in events}

    assert "epee-men-individual" in event_codes
    assert "epee-women-individual" in event_codes
    assert "sabre-women-team" in event_codes
    assert "foil-men-team" in event_codes
    assert all(event["season"] == event["edition_year"] for event in events)


def test_parse_fisu_stats_table_splits_bronze_ties_and_country_codes():
    from scrape_universiade import parse_fisu_stats_tables

    events = parse_fisu_stats_tables([FISU_STATS_TABLE_2019_2021])
    event = next(
        e for e in events
        if e["edition_id"] == "2019" and e["event_code"] == "epee-men-individual"
    )

    assert event["source_id"] == "universiade:2019:epee-men-individual"
    assert event["name"] == "2019 Summer Universiade — Epee, Individual, Men"
    assert event["weapon"] == "Epee"
    assert event["gender"] == "Men"
    assert event["team"] is False
    assert event["results"] == [
        {"rank": 1, "name": "RUBES MARTIN", "country": "CZE", "medal": "Gold", "team": False},
        {"rank": 2, "name": "GUSEV DMITRIY", "country": "RUS", "medal": "Silver", "team": False},
        {"rank": 3, "name": "JANG HYOMIN", "country": "KOR", "medal": "Bronze", "team": False},
        {"rank": 3, "name": "KOLANCZYK WOJCIECH", "country": "POL", "medal": "Bronze", "team": False},
    ]


def test_parse_fisu_stats_table_handles_team_rows():
    from scrape_universiade import parse_fisu_stats_tables

    events = parse_fisu_stats_tables([FISU_STATS_TABLE_2019_2021])
    event = next(
        e for e in events
        if e["edition_id"] == "2019" and e["event_code"] == "sabre-women-team"
    )

    assert event["name"] == "2019 Summer Universiade — Sabre, Team, Women"
    assert event["team"] is True
    assert event["results"] == [
        {"rank": 1, "name": "ITA", "country": "ITA", "medal": "Gold", "team": True},
        {"rank": 2, "name": "FRA", "country": "FRA", "medal": "Silver", "team": True},
        {"rank": 3, "name": "KOR", "country": "KOR", "medal": "Bronze", "team": True},
    ]


def test_parse_fisu_stats_table_keeps_wrapped_slash_tie_names_together():
    from scrape_universiade import parse_fisu_stats_tables

    events = parse_fisu_stats_tables([FISU_STATS_TABLE_2019_2021])
    event = next(
        e for e in events
        if e["edition_id"] == "2021" and e["event_code"] == "epee-women-individual"
    )

    assert {"rank": 3, "name": "TERAYAMA TAMAKI", "country": "JPN", "medal": "Bronze", "team": False} in event["results"]
    assert all(row["country"] for row in event["results"])


def test_upsert_tournament_uses_required_source_id_and_season(monkeypatch):
    from scrape_universiade import upsert_tournament
    import scrape_universiade

    event = {
        "source_id": "universiade:2021:epee-women-individual",
        "edition_id": "2021",
        "edition_year": "2021",
        "season": "2021",
        "name": "2021 Summer Universiade — Epee, Individual, Women",
        "event_code": "epee-women-individual",
        "weapon": "Epee",
        "gender": "Women",
        "team": False,
    }
    table = MagicMock()
    table.upsert.return_value.execute.return_value.data = [{"id": 42}]
    fake_supabase = MagicMock()
    fake_supabase.table.return_value = table
    monkeypatch.setattr(scrape_universiade, "supabase", fake_supabase)

    assert upsert_tournament(event) == 42
    table.upsert.assert_called_once()
    row = table.upsert.call_args.args[0]
    assert table.upsert.call_args.kwargs == {"on_conflict": "source_id"}
    assert row["source_id"] == "universiade:2021:epee-women-individual"
    assert row["season"] == "2021"
    assert row["type"] == "universiade"
    assert row["metadata"]["team"] is False

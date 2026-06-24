import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scrape_cac_games import (
    CAC_GAMES_ARCHIVES,
    classify_event,
    discover_events_from_manifest,
    parse_individual_standings_text,
    parse_team_medalists_text,
    wayback_raw_url,
)

INDIVIDUAL_STANDINGS_TEXT = """
ESGRIMA
FENCING
ESPADA INDIVIDUAL MASCULINO
MEN'S INDIVIDUAL EPÉE
POSICIONES FINALES
FINAL STANDINGS
A fecha 29 JUL 2018
Puesto Nombre CON Medalla
Finales
1 HENRIQUE Reynier CUB - Cuba Gold
2 LIMARDO Francisco VEN - Venezuela Silver
Semifinales
3 COQUECO Gustavo COL - Colombia Bronze
3 REYTOR Yunior CUB - Cuba Bronze
Ronda de 8
5 LIMARDO Jesus VEN - Venezuela
6 RODRIGUEZ Jhon COL - Colombia
"""


TEAM_MEDALISTS_TEXT = """
ESGRIMA
FENCING
ESPADA EQUIPO MASCULINO
MEN'S TEAM EPÉE
MIE 1 AGO 2018
MEDALLISTAS - EQUIPOS
MEDALLISTS
Medalla CON Nombre
GOLD VEN - Venezuela LIMARDO Francisco
LIMARDO Jesus
LUGO Gabriel
SILVER COL - Colombia CAMPOS Andres
COQUECO Gustavo
PACHON Santiago
RODRIGUEZ Jhon
BRONZE CUB - Cuba HENRIQUE Reynier
QUINTERO Ringo
REYTOR Yunior
RODRIGUEZ Harold
"""


def test_classify_event_handles_spanish_weapon_gender_and_team_labels():
    assert classify_event("ESPADA INDIVIDUAL MASCULINO") == {
        "weapon": "Epee",
        "gender": "Men",
        "team": False,
    }
    assert classify_event("FLORETE EQUIPO FEMENIL") == {
        "weapon": "Foil",
        "gender": "Women",
        "team": True,
    }
    assert classify_event("SABLE POR EQUIPOS DAMAS") == {
        "weapon": "Sabre",
        "gender": "Women",
        "team": True,
    }


def test_parse_individual_standings_text_parses_medals_and_non_medalists():
    rows = parse_individual_standings_text(INDIVIDUAL_STANDINGS_TEXT)

    assert rows[:4] == [
        {"rank": 1, "name": "HENRIQUE Reynier", "country": "CUB", "medal": "Gold"},
        {"rank": 2, "name": "LIMARDO Francisco", "country": "VEN", "medal": "Silver"},
        {"rank": 3, "name": "COQUECO Gustavo", "country": "COL", "medal": "Bronze"},
        {"rank": 3, "name": "REYTOR Yunior", "country": "CUB", "medal": "Bronze"},
    ]
    assert rows[4] == {
        "rank": 5,
        "name": "LIMARDO Jesus",
        "country": "VEN",
        "medal": None,
    }


def test_parse_team_medalists_text_returns_team_rows_with_rosters():
    rows = parse_team_medalists_text(TEAM_MEDALISTS_TEXT)

    assert rows[0] == {
        "rank": 1,
        "name": "Venezuela",
        "country": "VEN",
        "medal": "Gold",
        "metadata": {"roster": ["LIMARDO Francisco", "LIMARDO Jesus", "LUGO Gabriel"]},
    }
    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "Colombia"
    assert rows[1]["medal"] == "Silver"
    assert rows[2]["rank"] == 3
    assert rows[2]["country"] == "CUB"
    assert rows[2]["metadata"]["roster"][-1] == "RODRIGUEZ Harold"


def test_discover_events_from_manifest_skips_missing_early_edition_data():
    manifest = [
        {
            "edition_id": "1938",
            "edition_name": "Panama City 1938",
            "skip_reason": "No structured public fencing result archive found.",
        },
        {
            "edition_id": "2018",
            "edition_name": "Barranquilla 2018",
            "events": [
                {
                    "event_code": "FEM002000",
                    "event_name": "ESPADA INDIVIDUAL MASCULINO",
                    "result_url": "https://example.test/FEM002000.pdf",
                    "parser": "individual_standings_pdf",
                }
            ],
        },
    ]

    events, skipped = discover_events_from_manifest(manifest)

    assert skipped == [
        {
            "edition_id": "1938",
            "edition_name": "Panama City 1938",
            "reason": "No structured public fencing result archive found.",
        }
    ]
    assert events == [
        {
            "edition_id": "2018",
            "edition_name": "Barranquilla 2018",
            "event_code": "FEM002000",
            "event_name": "ESPADA INDIVIDUAL MASCULINO",
            "result_url": "https://example.test/FEM002000.pdf",
            "parser": "individual_standings_pdf",
            "source_id": "cac_games:2018:FEM002000",
        }
    ]


def test_wayback_raw_url_requests_archived_pdf_not_html_wrapper():
    wrapped = (
        "https://web.archive.org/web/20180730212832/"
        "http://resultados.elheraldo.co/resBA2018/pdf/BA2018/FE/sample.pdf"
    )

    assert wayback_raw_url(wrapped) == (
        "https://web.archive.org/web/20180730212832id_/"
        "http://resultados.elheraldo.co/resBA2018/pdf/BA2018/FE/sample.pdf"
    )
    assert wayback_raw_url(wayback_raw_url(wrapped)) == wayback_raw_url(wrapped)


def test_2018_manifest_uses_archived_elheraldo_pdf_urls():
    events, _ = discover_events_from_manifest(CAC_GAMES_ARCHIVES)
    urls = [event["result_url"] for event in events if event["edition_id"] == "2018"]

    assert len(urls) == 12
    assert all(url.startswith("https://web.archive.org/web/") for url in urls)

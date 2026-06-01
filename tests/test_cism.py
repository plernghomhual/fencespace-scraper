import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


SOURCE_PAGE_HTML = """
<html><body>
  <a href="/medias/fichiers/8__Fencing.pdf">CISM WSG Wuhan 2019 - 47th WMC Fencing</a>
  <a href="/news/fencing-associated-events/3rd-cism-military-world-summer-games-catania-ita">
    3rd CISM Military World Summer Games - Catania (ITA)
  </a>
</body></html>
"""


WUHAN_FINAL_STANDINGS_TEXT = """
Fencing
Women Individual Epee
Final Standings
As of 19 OCT 2019
Medal
Gold
Silver
Bronze
Bronze
Rank
Name
1
2
3
3
5
SUN Yiwen
ANA Popescu
ANDRIUSHINA Tatiana
PIEKARSKA Magdalena
MARZANI Roberta
Nation
CHN - China
ROU - Romania
RUS - Russia
POL - Poland
ITA - Italy
"""


SPLIT_NAME_COLUMNS_TEXT = """
48th WORLD MILITARY FENCING CHAMPIONSHIP
MEN´S INDIVIDUAL FOIL
Rank
Name
First name
Country
1
2
3
LOMBARDI
JURKIEWICZ
DOSA
Giulio
Jan
Daniel
ITA
POL
HUN
"""


DNF_STATUS_TEXT = """
Women Individual Sabre
Medal
Gold
Silver
Rank
Name
1
2
DNF
EGORIAN Iana
QIAN Jiarui
Final Standings
As of 20 OCT 2019
Nation
RUS - Russia
CHN - China
FRA - France
"""


def test_classify_event_handles_english_and_french_names():
    from scrape_cism import classify_event

    assert classify_event("Women Individual Epee") == {
        "weapon": "Epee",
        "gender": "Women",
        "team": False,
    }
    assert classify_event("MEN'S TEAM SABRE") == {
        "weapon": "Sabre",
        "gender": "Men",
        "team": True,
    }
    assert classify_event("Fleuret individuel hommes") == {
        "weapon": "Foil",
        "gender": "Men",
        "team": False,
    }
    assert classify_event("Épée par équipes dames") == {
        "weapon": "Epee",
        "gender": "Women",
        "team": True,
    }


def test_parse_source_page_discovers_world_games_pdf_edition():
    from scrape_cism import parse_source_page

    editions = parse_source_page(SOURCE_PAGE_HTML)

    assert len(editions) == 1
    assert editions[0]["edition_id"] == "wuhan-2019"
    assert editions[0]["edition_name"] == "CISM WSG Wuhan 2019 - 47th WMC Fencing"
    assert editions[0]["format"] == "pdf"
    assert editions[0]["url"] == "https://www.milsport.one/medias/fichiers/8__Fencing.pdf"


def test_parse_pdf_text_returns_individual_result_rows():
    from scrape_cism import parse_pdf_text

    events = parse_pdf_text(
        WUHAN_FINAL_STANDINGS_TEXT,
        edition_id="wuhan-2019",
        edition_name="CISM WSG Wuhan 2019 - 47th WMC Fencing",
    )

    assert len(events) == 1
    event = events[0]
    assert event["event_code"] == "women_individual_epee"
    assert event["event_name"] == "Women Individual Epee"
    assert event["metadata"]["event_title"] == "Women Individual Epee"
    assert event["classification"] == {"weapon": "Epee", "gender": "Women", "team": False}
    assert event["rows"][:4] == [
        {"rank": 1, "name": "SUN Yiwen", "country": "CHN", "medal": "Gold"},
        {"rank": 2, "name": "ANA Popescu", "country": "ROU", "medal": "Silver"},
        {"rank": 3, "name": "ANDRIUSHINA Tatiana", "country": "RUS", "medal": "Bronze"},
        {"rank": 3, "name": "PIEKARSKA Magdalena", "country": "POL", "medal": "Bronze"},
    ]


def test_parse_pdf_text_handles_split_surname_first_name_columns():
    from scrape_cism import parse_pdf_text

    events = parse_pdf_text(
        SPLIT_NAME_COLUMNS_TEXT,
        edition_id="sevilla-2025",
        edition_name="48th WMC Fencing - Sevilla (ESP)",
    )

    assert len(events) == 1
    assert events[0]["event_code"] == "men_individual_foil"
    assert events[0]["rows"] == [
        {"rank": 1, "name": "Giulio Lombardi", "country": "ITA", "medal": "Gold"},
        {"rank": 2, "name": "Jan Jurkiewicz", "country": "POL", "medal": "Silver"},
        {"rank": 3, "name": "Daniel Dosa", "country": "HUN", "medal": "Bronze"},
    ]


def test_parse_pdf_text_ignores_dnf_status_lines_before_names():
    from scrape_cism import parse_pdf_text

    events = parse_pdf_text(
        DNF_STATUS_TEXT,
        edition_id="wuhan-2019",
        edition_name="CISM WSG Wuhan 2019 - 47th WMC Fencing",
    )

    assert events[0]["rows"] == [
        {"rank": 1, "name": "EGORIAN Iana", "country": "RUS", "medal": "Gold"},
        {"rank": 2, "name": "QIAN Jiarui", "country": "CHN", "medal": "Silver"},
    ]


def test_empty_or_missing_pages_return_no_editions_or_events(monkeypatch):
    from scrape_cism import fetch_edition_events, parse_source_page

    assert parse_source_page("") == []
    assert parse_source_page("<html><body>No result links</body></html>") == []

    monkeypatch.setattr("scrape_cism._get", lambda _url: None)
    assert fetch_edition_events({
        "edition_id": "missing-1900",
        "edition_name": "Missing Edition",
        "url": "https://example.invalid/missing.pdf",
        "format": "pdf",
    }) == []

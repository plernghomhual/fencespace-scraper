import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


YOG_SPORT_HTML = """
<html><body>
<table class="table">
  <tr><th>Event</th><th>Status</th><th>Date</th></tr>
  <tr><td><a href="/results/4003540">Foil, Individual, Boys</a></td><td>YOG</td><td>17 August 2010</td></tr>
  <tr><td><a href="/results/4003711">Foil, Individual, Girls</a></td><td>YOG</td><td>17 August 2010</td></tr>
  <tr><td><a href="/results/4003882">Mixed Weapon, Team, Mixed</a></td><td>YOG</td><td>18 August 2010</td></tr>
  <tr><td><a href="/results/4003540">Foil, Individual, Boys</a></td><td>YOG</td><td>17 August 2010</td></tr>
</table>
</body></html>
"""


YOG_RESULTS_HTML = """
<html><body>
<h1>Foil, Individual, Boys</h1>
<table class="biodata">
  <tr><td>Status</td><td>YOG</td></tr>
</table>
<table class="table table-striped">
  <tr><th>Pos</th><th>Competitor</th><th>NOC</th><th></th><th></th><th></th></tr>
  <tr><td>1</td><td><a href="/athletes/123456">Edoardo Luperi</a></td><td>ITA</td><td>Gold</td><td></td><td></td></tr>
  <tr><td>2</td><td><a href="/athletes/234567">Alexander Massialas</a></td><td>USA</td><td>Silver</td><td></td><td></td></tr>
  <tr><td>3</td><td><a href="/athletes/345678">Lee Gwang-Hyeon</a></td><td>KOR</td><td>Bronze</td><td></td><td></td></tr>
  <tr><td>4</td><td>Lucas Malcotti</td><td>SUI</td><td></td><td></td><td></td></tr>
</table>
</body></html>
"""


WFG_STANDINGS_TEXT = """
King Saud University 4 Fencing
Women's Épée Individual
Standings
As of FRI 27 OCT 2023
Final
Rank Name NOC
1 ALHOSANI Zainab UAE - United Arab Emirates Gold
2 ALKHIBIRI Fawzya KSA - Saudi Arabia Silver
3 ABED Nada KSA - Saudi Arabia Bronze
3 ALAMIRI Dhay KSA - Saudi Arabia Bronze
FENWEPEE--------------------------_76I v1.0 Report Created FRI 27 OCT 2023 14:30 Page 1/1

King Saud University 4 Fencing
Men's Foil Team
Standings
As of FRI 27 OCT 2023
Final
Rank NOC
1 QAT - Qatar Gold
2 KUW - Kuwait Silver
3 BRN - Bahrain Bronze
3 UAE - United Arab Emirates Bronze
FENMTEAMFOIL----------------------_76T v1.0 Report Created FRI 27 OCT 2023 16:57 Page 1/1
"""


def test_parse_yog_edition_sport_page_dedupes_and_skips_mixed_team():
    from scrape_youth_olympics import parse_yog_edition_sport_page

    events = parse_yog_edition_sport_page(YOG_SPORT_HTML, edition_id="65", edition_name="Singapore 2010")

    assert [event["result_id"] for event in events] == ["4003540", "4003711"]
    assert events[0]["event_name"] == "Foil, Individual, Boys"
    assert events[0]["edition_id"] == "65"
    assert events[0]["edition_name"] == "Singapore 2010"


def test_parse_olympedia_results_page_handles_yog_table_without_number_column():
    from scrape_youth_olympics import parse_olympedia_results_page

    rows = parse_olympedia_results_page(YOG_RESULTS_HTML, result_id="4003540")

    assert len(rows) == 4
    assert rows[0] == {
        "rank": 1,
        "name": "Edoardo Luperi",
        "country": "ITA",
        "medal": "Gold",
        "athlete_id": "123456",
    }
    assert rows[3]["rank"] == 4
    assert rows[3]["medal"] is None
    assert rows[3]["athlete_id"] is None


def test_classify_event_maps_youth_gender_and_team_status():
    from scrape_youth_olympics import classify_event

    assert classify_event("Foil, Individual, Boys") == {"weapon": "Foil", "gender": "Men", "team": False}
    assert classify_event("Épée, Individual, Girls") == {"weapon": "Epee", "gender": "Women", "team": False}
    assert classify_event("Mixed Weapon, Team, Mixed") == {"weapon": None, "gender": "Mixed", "team": True}


def test_parse_wfg_results_book_text_returns_individual_and_team_standings():
    from scrape_youth_olympics import parse_wfg_results_book_text

    events = parse_wfg_results_book_text(WFG_STANDINGS_TEXT, year=2023)

    assert [event["event_name"] for event in events] == ["Women's Épée Individual", "Men's Foil Team"]
    assert events[0]["event_code"] == "womens-epee-individual"
    assert events[0]["classification"] == {"weapon": "Epee", "gender": "Women", "team": False}
    assert events[0]["rows"][0] == {
        "rank": 1,
        "name": "Zainab Alhosani",
        "country": "UAE",
        "country_name": "United Arab Emirates",
        "medal": "Gold",
    }
    assert events[1]["event_code"] == "mens-foil-team"
    assert events[1]["classification"] == {"weapon": "Foil", "gender": "Men", "team": True}
    assert events[1]["rows"][0]["name"] == "Qatar"
    assert events[1]["rows"][0]["country"] == "QAT"


def test_tournament_rows_use_required_source_ids():
    from scrape_youth_olympics import build_wfg_tournament_row, build_yog_tournament_row, classify_event

    yog_event = {
        "result_id": "4003540",
        "event_name": "Foil, Individual, Boys",
        "edition_id": "65",
        "edition_name": "Singapore 2010",
    }
    yog_row = build_yog_tournament_row(yog_event, classify_event(yog_event["event_name"]))
    assert yog_row["source_id"] == "yog:65:4003540"
    assert yog_row["season"] == "2010"
    assert yog_row["category"] == "Youth"

    wfg_event = {
        "year": 2023,
        "event_code": "womens-epee-individual",
        "event_name": "Women's Épée Individual",
        "classification": {"weapon": "Epee", "gender": "Women", "team": False},
    }
    wfg_row = build_wfg_tournament_row(wfg_event)
    assert wfg_row["source_id"] == "wfg:2023:womens-epee-individual"
    assert wfg_row["name"] == "Riyadh 2023 World Combat Games — Women's Épée Individual"
    assert wfg_row["category"] == "Senior"


def test_wfg_results_book_uses_raw_wayback_pdf_url():
    from scrape_youth_olympics import WFG_RESULTS_BOOKS

    assert "/web/20231105110628id_/" in WFG_RESULTS_BOOKS[2023]["url"]


def test_build_result_rows_matches_individuals_but_not_team_rows(monkeypatch):
    import scrape_youth_olympics

    calls = []

    def fake_match(name, country, fie_fencer_id=None):
        calls.append((name, country, fie_fencer_id))
        return "fencer-1"

    monkeypatch.setattr(scrape_youth_olympics, "_match_fencer", fake_match)

    rows = scrape_youth_olympics.build_result_rows(
        "tournament-1",
        [
            {
                "rank": 1,
                "name": "Edoardo Luperi",
                "country": "ITA",
                "medal": "Gold",
                "athlete_id": "123456",
            },
            {
                "rank": 1,
                "name": "Qatar",
                "country": "QAT",
                "country_name": "Qatar",
                "medal": "Gold",
                "team": True,
            },
        ],
        source="wfg",
    )

    assert calls == [("Edoardo Luperi", "ITA", None)]
    assert rows[0]["fencer_id"] == "fencer-1"
    assert rows[0]["metadata"]["olympedia_athlete_id"] == "123456"
    assert rows[1]["fencer_id"] is None
    assert rows[1]["metadata"]["country_name"] == "Qatar"

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


PAN_AM_OLYMPEDIA_HTML = """
<html><body>
<table>
  <tr class="top">
    <td><a href="/athletes/118220">Rubén Limardo</a></td>
    <td><a href="/countries/VEN">VEN</a></td>
    <td>FEN</td>
    <td>Olympics</td>
    <td>2012—2024</td>
    <td>4–4–1 2007 Rio de Janeiro FEN gold: épée, silver: épée team; 2011 Guadalajara FEN silver: épée and épée team; 2015 Toronto FEN gold: épée and épée team; 2019 Lima FEN gold: épée, bronze: épée team</td>
  </tr>
  <tr class="top">
    <td><a href="/athletes/64368">Ana María Fontán</a></td>
    <td><a href="/countries/ARG">ARG</a></td>
    <td>ATH</td>
    <td>Olympics</td>
    <td>1952</td>
    <td>0–0–1 1951 Buenos Aires ATH bronze: 4×100 m relay</td>
  </tr>
</table>
</body></html>
"""

ASIAN_OLYMPEDIA_HTML = """
<html><body>
<table>
  <tr class="top">
    <td><a href="/athletes/126267">Sun Yiwen</a></td>
    <td><a href="/countries/CHN">CHN</a></td>
    <td>FEN</td>
    <td>Olympics</td>
    <td>2016—2024</td>
    <td>2–1–0 2014 Incheon FEN gold: épée team; 2018 Jakarta/Palembang FEN gold: épée team, silver: épée</td>
  </tr>
  <tr class="top">
    <td><a href="/athletes/1">Pre-Fencing Era</a></td>
    <td><a href="/countries/JPN">JPN</a></td>
    <td>FEN</td>
    <td>Olympics</td>
    <td>1956</td>
    <td>1–0–0 1958 Tokyo FEN gold: foil</td>
  </tr>
</table>
</body></html>
"""

EUROPEAN_OLYMPEDIA_HTML = """
<html><body>
<table>
  <tr class="top">
    <td><a href="/athletes/104920">Ana Maria Brânză-Popescu</a></td>
    <td><a href="/countries/ROU">ROU</a></td>
    <td>FEN</td>
    <td>Olympics</td>
    <td>2004—2020</td>
    <td>2–0–0 2015 Bakı FEN gold: épée and épée team (competed as Ana Popescu)</td>
  </tr>
  <tr class="top">
    <td><a href="/athletes/104921">Other Athlete</a></td>
    <td><a href="/countries/ROU">ROU</a></td>
    <td>FEN</td>
    <td>Olympics</td>
    <td>2016</td>
    <td>1–0–0 2014 Baku FEN gold: foil</td>
  </tr>
</table>
</body></html>
"""

AFRICAN_PDF_TEXT = """
Fencing
Escrime
Men's Epee Individual
Epée Hommes Individuel
Final Standings | Classment Final
As of 28 AUG 2019
Rank Name Nation Medal
Finals
1 EL Houssam MAR - Morocco Gold
2 ELSAYED Ahmed EGY - Egypt Silver
Semifinals
3 GUNPUT Satya MRI - Mauritius Bronze
3 YASSEEN Mohammed EGY - Egypt Bronze
Quarterfinals
5 BEUGRE Bedi CIV - Cote D'Ivoire
6 BUHDEIMA Khaled LBA - Libya
FENMEPEE--------------------------_76 1.0 Report Created WED 28 AUG 2019
"""

AFRICAN_TEAM_PDF_TEXT = """
Fencing | Escrime | Women's Epee Team | Epée Femmes par équipe
Final Standings | Classment Final
As of 29 AUG 2019
Rank Team Medal
Finals
1 Egypt Gold
2 Tunisia Silver
3 Senegal Bronze
3 Morocco Bronze
FENWTEAMEPEE----------------------_76 1.0 Report Created THU 29 AUG 2019
"""


def test_parse_pan_american_olympedia_medal_rows():
    from scrape_continental_games import parse_olympedia_list_page

    rows = parse_olympedia_list_page(
        PAN_AM_OLYMPEDIA_HTML,
        games_type="pan_american_games",
        min_year=1951,
        athlete_gender_by_id={"118220": "Men"},
    )

    assert len(rows) == 8
    first = rows[0]
    assert first["edition_id"] == "2007-rio-de-janeiro"
    assert first["edition_name"] == "2007 Rio de Janeiro"
    assert first["event_name"] == "Men's Epee Individual"
    assert first["event_code"] == "men_epee_individual"
    assert first["athlete_name"] == "Rubén Limardo"
    assert first["country"] == "VEN"
    assert first["rank"] == 1
    assert first["medal"] == "Gold"
    assert rows[1]["event_name"] == "Men's Epee Team"
    assert rows[1]["rank"] == 2


def test_parse_asian_olympedia_filters_to_fencing_start_year():
    from scrape_continental_games import parse_olympedia_list_page

    rows = parse_olympedia_list_page(
        ASIAN_OLYMPEDIA_HTML,
        games_type="asian_games",
        min_year=1974,
        athlete_gender_by_id={"126267": "Women", "1": "Men"},
    )

    assert len(rows) == 3
    assert {row["year"] for row in rows} == {2014, 2018}
    individual = [row for row in rows if row["event_code"] == "women_epee_individual"][0]
    assert individual["edition_name"] == "2018 Jakarta/Palembang"
    assert individual["rank"] == 2
    assert individual["medal"] == "Silver"


def test_parse_european_olympedia_filters_allowed_editions():
    from scrape_continental_games import parse_olympedia_list_page

    rows = parse_olympedia_list_page(
        EUROPEAN_OLYMPEDIA_HTML,
        games_type="european_games",
        allowed_years={2015, 2019, 2023},
        athlete_gender_by_id={"104920": "Women", "104921": "Men"},
    )

    assert len(rows) == 2
    assert {row["event_code"] for row in rows} == {
        "women_epee_individual",
        "women_epee_team",
    }
    assert all(row["edition_name"] == "2015 Bakı" for row in rows)


def test_parse_african_pdf_final_standings_individual_rows():
    from scrape_continental_games import parse_african_pdf_final_standings_text

    rows = parse_african_pdf_final_standings_text(AFRICAN_PDF_TEXT, edition_name="2019 Rabat")

    assert len(rows) == 6
    assert rows[0]["games_type"] == "african_games"
    assert rows[0]["event_name"] == "Men's Epee Individual"
    assert rows[0]["event_code"] == "men_epee_individual"
    assert rows[0]["athlete_name"] == "EL Houssam"
    assert rows[0]["country"] == "MAR"
    assert rows[0]["rank"] == 1
    assert rows[0]["medal"] == "Gold"
    assert rows[3]["rank"] == 3
    assert rows[3]["medal"] == "Bronze"


def test_parse_african_pdf_final_standings_team_rows():
    from scrape_continental_games import parse_african_pdf_final_standings_text

    rows = parse_african_pdf_final_standings_text(AFRICAN_TEAM_PDF_TEXT, edition_name="2019 Rabat")

    assert len(rows) == 4
    assert rows[0]["event_name"] == "Women's Epee Team"
    assert rows[0]["event_code"] == "women_epee_team"
    assert rows[0]["athlete_name"] == "Egypt"
    assert rows[0]["country"] == "EGY"
    assert rows[2]["rank"] == 3
    assert rows[2]["medal"] == "Bronze"


def test_build_tournament_row_uses_required_source_id_format():
    from scrape_continental_games import build_tournament_row

    event = {
        "games_type": "asian_games",
        "edition_id": "2018-jakarta-palembang",
        "edition_name": "2018 Jakarta/Palembang",
        "event_code": "women_epee_individual",
        "event_name": "Women's Epee Individual",
        "year": 2018,
        "source": "olympedia",
    }

    row = build_tournament_row(event)

    assert row["source_id"] == "asian_games:2018-jakarta-palembang:women_epee_individual"
    assert row["name"] == "2018 Jakarta/Palembang — Women's Epee Individual"
    assert row["type"] == "asian_games"
    assert row["weapon"] == "Epee"
    assert row["gender"] == "Women"
    assert row["metadata"]["team"] is False


def test_group_rows_by_event_deduplicates_team_medalists():
    from scrape_continental_games import group_rows_by_event

    rows = parse_fixture_rows()
    events = group_rows_by_event(rows)

    assert len(events) == 1
    event, result_rows = events[0]
    assert event["event_code"] == "men_sabre_team"
    assert [row["athlete_name"] for row in result_rows] == ["Athlete One", "Athlete Two"]
    assert all(row["rank"] == 1 for row in result_rows)


def parse_fixture_rows():
    from scrape_continental_games import parse_olympedia_list_page

    html = """
    <html><body><table>
      <tr>
        <td><a href="/athletes/10">Athlete One</a></td><td><a href="/countries/EGY">EGY</a></td>
        <td>FEN</td><td>Olympics</td><td>2020</td>
        <td>1–0–0 2019 Rabat FEN gold: sabre team</td>
      </tr>
      <tr>
        <td><a href="/athletes/11">Athlete Two</a></td><td><a href="/countries/EGY">EGY</a></td>
        <td>FEN</td><td>Olympics</td><td>2020</td>
        <td>1–0–0 2019 Rabat FEN gold: sabre team</td>
      </tr>
    </table></body></html>
    """
    return parse_olympedia_list_page(
        html,
        games_type="african_games",
        athlete_gender_by_id={"10": "Men", "11": "Men"},
    )

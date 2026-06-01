import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


HTML_RESULTS = """
<html><body>
  <h2>Men's Epee V50 Individual</h2>
  <table class="table table-striped">
    <tr><th>Rank</th><th>Name</th><th>Country</th><th>Medal</th></tr>
    <tr><td>1</td><td>Jean Martin</td><td>FRA</td><td>Gold</td></tr>
    <tr><td>2</td><td>Marco Rossi</td><td>ITA</td><td>Silver</td></tr>
    <tr><td>T3</td><td>John Smith</td><td>USA</td><td>Bronze</td></tr>
  </table>
</body></html>
"""


def w(text, x0, top):
    return {"text": text, "x0": x0, "top": top}


PDF_WORDS = [
    # Real IMGA PDF extraction shape from All-fencing-results-2019.pdf:
    # event header words are doubled by the embedded font.
    w("EMG", 34.6, 24.8),
    w("2019", 74.4, 24.8),
    w("SScciiaabboollaa", 121.0, 25.4),
    w("--", 235.0, 25.4),
    w("FFeemmmmiinniillee", 252.2, 25.4),
    w("--", 391.0, 25.4),
    w("CCaatt..00", 408.2, 25.4),
    w("nnaa(cid:93)(cid:93)iioonnee", 18.0, 80.4),
    w("ppoossttoo", 78.3, 80.4),
    w("ssttaattoo", 124.8, 80.4),
    w("ccooggnnoommee", 168.5, 80.4),
    w("nnoommee", 254.8, 80.4),
    w("cclluubb", 310.4, 80.4),
    w("IITTAA", 18.0, 101.9),
    w("11", 78.2, 101.9),
    w("RRoossssii", 168.6, 101.9),
    w("MMaarriiaa", 254.8, 101.9),
    w("FFRRAA", 18.0, 116.8),
    w("22", 78.2, 116.8),
    w("DDuurraanndd", 168.6, 116.8),
    w("AAnnnnee", 254.8, 116.8),
]


def test_extract_age_category_preserves_veteran_labels():
    from scrape_masters_games import extract_age_category

    assert extract_age_category("Foil Men V40 Individual") == "V40"
    assert extract_age_category("Women's Epee Veteran 50+") == "Veteran 50+"
    assert extract_age_category("Sabre Masters 40-49 Women") == "Masters 40-49"
    assert extract_age_category("Sciabola - Femminile - Cat.0") == "Cat.0"
    assert extract_age_category("Foil Senior Men") is None


def test_parse_html_results_page_returns_rows_with_event_metadata():
    from scrape_masters_games import parse_html_results_page

    events = parse_html_results_page(
        HTML_RESULTS,
        edition_id="wmg-2025",
        edition_name="World Masters Games 2025",
    )

    assert len(events) == 1
    event = events[0]
    assert event["event_code"] == "mens_epee_v50_individual"
    assert event["source_id"] == "masters:wmg-2025:mens_epee_v50_individual"
    assert event["weapon"] == "Epee"
    assert event["gender"] == "Men"
    assert event["age_category"] == "V50"
    assert event["rows"][0] == {
        "rank": 1,
        "name": "Jean Martin",
        "country": "FRA",
        "medal": "Gold",
        "weapon": "Epee",
        "gender": "Men",
        "age_category": "V50",
    }
    assert event["rows"][2]["rank"] == 3


def test_parse_pdf_page_words_returns_cleaned_event_and_rows():
    from scrape_masters_games import parse_pdf_page_words

    event = parse_pdf_page_words(
        PDF_WORDS,
        edition_id="emg-2019",
        edition_name="European Masters Games 2019",
    )

    assert event["event_name"] == "Sciabola Femminile Cat.0"
    assert event["event_code"] == "sciabola_femminile_cat_0"
    assert event["source_id"] == "masters:emg-2019:sciabola_femminile_cat_0"
    assert event["weapon"] == "Sabre"
    assert event["gender"] == "Women"
    assert event["age_category"] == "Cat.0"
    assert event["rows"][0] == {
        "rank": 1,
        "name": "Rossi Maria",
        "country": "ITA",
        "medal": "Gold",
        "weapon": "Sabre",
        "gender": "Women",
        "age_category": "Cat.0",
    }
    assert event["rows"][1]["medal"] == "Silver"


def test_infer_edition_id_prefers_pdf_filename_year_over_upload_path():
    from scrape_masters_games import infer_edition_id

    assert infer_edition_id(
        "https://www.worldmasterssport.com/wp-content/uploads/2025/07/All-fencing-results-2019.pdf"
    ) == "masters-2019"
    assert infer_edition_id(
        "https://www.worldmasterssport.com/wp-content/uploads/2025/07/Fencing-Results-WMG-1998.pdf"
    ) == "wmg-1998"


def test_parse_pdf_page_words_does_not_guess_country_from_name_prefix():
    from scrape_masters_games import parse_pdf_page_words

    words = [
        w("EMG", 34.6, 24.8),
        w("2019", 74.4, 24.8),
        w("SScciiaabboollaa", 121.0, 25.4),
        w("--", 235.0, 25.4),
        w("MMaasscchhiillee", 252.2, 25.4),
        w("--", 391.0, 25.4),
        w("CCaatt..00", 408.2, 25.4),
        w("ppoossttoo", 18.0, 80.4),
        w("ccooggnnoommee", 64.5, 80.4),
        w("nnoommee", 135.0, 80.4),
        w("nnaa(cid:93)(cid:93)iioonnee", 339.4, 80.4),
        w("11", 18.0, 101.9),
        w("DDee", 64.5, 101.9),
        w("MMaarriinniiss", 83.6, 101.9),
        w("CCaarrlloo", 135.0, 101.9),
    ]

    event = parse_pdf_page_words(words, edition_id="masters-2019")

    assert event["rows"][0]["name"] == "De Marinis Carlo"
    assert event["rows"][0]["country"] is None

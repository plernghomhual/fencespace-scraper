"""
Tests for scrape_fed_isr.py.

Fixtures mirror the public Israel Fencing Association XLSX ranking workbooks
discovered under https://www.fencing.org.il/דירוגים-עונה-2023-2024/.

Relevant worksheet columns:
  דירוג | שם | אגודה | ניקוד משוקלל | ...

Hebrew right-to-left text is stored in source order and must not be reversed or
lossily normalized.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_HEBREW_XLSX_TEXT = """
רומח-בנות-בוגרים			תאריך התחלה	30/9/2023		8/12/2023
			שם תחרות ראשית	סטלייט אמסטרדם רומח בוגרים		גביע עולם - רומח בוגרות
דירוג	שם	אגודה	ניקוד משוקלל	מיקום	ניקוד	מיקום	ניקוד
1	גילי קוריצקי	הפועל כפר סבא	118.00	34	0.00	19	0.00
2	מאי טיאגונוב קגן	רומח אבירים - סיוף עכו	117,50		-	19	0.00
3	ליהי קורן	הפועל כפר סבא	115.00	59	0.00	19	0.00
"""


FIXTURE_ENGLISH_AND_HEBREW_HTML = """
<!doctype html>
<html>
<body>
  <table>
    <thead>
      <tr>
        <th>Rank</th><th>Name</th><th>שם</th><th>Club</th><th>Points</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>1</td><td>Yuval Freilich</td><td>יובל פרייליך</td><td>הפועל כפר סבא</td><td>214.5</td>
      </tr>
      <tr>
        <td>2</td><td>Dana Strelecki</td><td>דנה סטרלצקי</td><td>מכבי מעלות</td><td>97,25</td>
      </tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
דירוג	שם	אגודה	ניקוד משוקלל
DNS	סייף שלא התייצב	מכבי חיפה	0
DQ	סייפת פסולה	הפועל חיפה	0
סה"כ	3 סייפים		300
1	אדם מקורי	מכבי חריש	100
2	נועה מקורית	מגידו	88,5
"""


FIXTURE_NO_DATA = """
<html>
  <body>
    <h1>דירוגים</h1>
    <p>אין דירוגים זמינים כרגע.</p>
    <p>No rankings available.</p>
  </body>
</html>
"""


def test_parse_isr_hebrew_xlsx_text_returns_rows_and_preserves_rtl_text():
    from scrape_fed_isr import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HEBREW_XLSX_TEXT)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "גילי קוריצקי",
        "club": "הפועל כפר סבא",
        "points": 118.0,
    }
    assert rows[1]["name"] == "מאי טיאגונוב קגן"
    assert rows[1]["club"] == "רומח אבירים - סיוף עכו"
    assert rows[1]["points"] == 117.5
    assert rows[2]["name"] == "ליהי קורן"


def test_parse_isr_empty_html_returns_empty_list():
    from scrape_fed_isr import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_isr_no_data_page_returns_empty_list():
    from scrape_fed_isr import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_isr_skips_dns_dq_and_summary_rows():
    from scrape_fed_isr import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 2
    assert [row["name"] for row in rows] == ["אדם מקורי", "נועה מקורית"]
    assert rows[1]["points"] == 88.5


def test_parse_isr_english_headers_keep_native_name_metadata():
    from scrape_fed_isr import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_ENGLISH_AND_HEBREW_HTML)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Yuval Freilich"
    assert rows[0]["club"] == "הפועל כפר סבא"
    assert rows[0]["points"] == 214.5
    assert rows[0]["metadata"]["hebrew_name"] == "יובל פרייליך"
    assert rows[1]["name"] == "Dana Strelecki"
    assert rows[1]["metadata"]["hebrew_name"] == "דנה סטרלצקי"


def test_ranking_combos_cover_all_required_israel_rankings():
    from scrape_fed_isr import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_current_season_format():
    from scrape_fed_isr import current_season

    season = current_season()
    assert re.match(r"^\d{4}-\d{4}$", season)
    start, end = season.split("-")
    assert int(end) == int(start) + 1

"""
Tests for scrape_fed_hkg.py.

Probe findings for Hong Kong, China Fencing Association / HKFA:
  - Requested fencing.org.hk paths failed publicly: HTTPS handshake errors,
    HTTP returned 409 challenge pages.
  - Working ranking index: http://www.hkfa.org.hk/EN/ranking.html?mID=8
  - Request method: GET with browser-like headers.
  - Response format: ranking index is HTML; ranking files are PDFs.
  - Public coverage: all 12 Senior/Open and Junior/U20 Foil/Epee/Sabre
    Men/Women PDF combos are linked under /ranking/.

PDF text fixtures below are captured from public HKFA PDFs via pdfplumber.
HKFA PDF rows contain bilingual names in one field, for example:
  1 Choi Chun Yin Ryan 蔡俊彥 ... Overall points
"""

from typing import Any
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_PDF_TEXT = """
男子花劍排名 Ranking of Men's Foil
Best 4 at
least 2 local
Ranking Name 姓名
Overall
248 fencers 232 fencers 330 fencers 295 fencers 163 fencers 212 fencers 258 fencers 233 fencers
1 Choi Chun Yin Ryan 蔡俊彥 1 6 33 1 2 33 5 33 9 17 83
2 Cheung Ka Long 張家朗 1 19 21 3 3 17 35 37 68
2 Ho Shing Him Harris 何承謙 5 4 10 2 5 13 40 45 7 57 13 68
4 Leung Chin Yu 梁千雨 3 2 4 47 30 26 54
"""


FIXTURE_JUNIOR_PDF_TEXT = """
青年組男子花劍排名 Ranking of Junior Men's Foil
Ranking Name 姓名 Year of Birth
Overall
304 fencers 51 fencers 241 fencers 196 fencers 83 fencers 271 fencers 84 fencers 37 fencers
1 Lam Ho Long 林浩朗 2007 6 2 1 2 11 52
2 Ho Shing Him Harris 何承謙 2009 2 8 11 1 18 51 34 46
3 Wong Chit Daniel 王哲 2009 5 18 4 6 7 3 44
"""


FIXTURE_CHINESE_HTML_TABLE = """
<!doctype html>
<html>
<body>
  <table>
    <thead>
      <tr><th>排名</th><th>姓名</th><th>會籍</th><th>積分</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>蔡俊彥 Choi Chun Yin Ryan</td><td>香港劍擊學校</td><td>83,5</td></tr>
      <tr><td>2</td><td>梁千雨</td><td>港會</td><td>54</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_NO_DATA = """
<!doctype html>
<html><body><p>No rankings available.</p><p>未有排名資料</p></body></html>
"""


FIXTURE_NON_STANDARD_ROWS = """
Ranking Name 姓名
DNS Withdrawn Fencer 棄權 0
DQ Disqualified Fencer 失格 0
Overall
248 fencers 232 fencers 330 fencers
1 Wu Sophia 符妤名 1 2 6 1 3 58
2 Cheng Hiu Wai Valerie 鄭曉為 9 3 6 1 53 27 50
Summary 2 fencers total
"""


def test_parse_hkg_pdf_text_returns_rows_and_bilingual_metadata():
    from scrape_fed_hkg import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_PDF_TEXT)

    assert len(rows) == 4
    assert rows[0] == {
        "rank": 1,
        "name": "Choi Chun Yin Ryan",
        "club": None,
        "points": 83.0,
        "metadata": {"alt_name": "蔡俊彥"},
    }
    assert rows[1]["name"] == "Cheung Ka Long"
    assert rows[1]["metadata"]["alt_name"] == "張家朗"
    assert rows[2]["points"] == 68.0
    assert rows[3]["metadata"]["alt_name"] == "梁千雨"


def test_parse_hkg_junior_pdf_text_ignores_birth_year_for_points():
    from scrape_fed_hkg import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_JUNIOR_PDF_TEXT)

    assert len(rows) == 3
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Lam Ho Long"
    assert rows[0]["metadata"]["alt_name"] == "林浩朗"
    assert rows[0]["points"] == 52.0
    assert rows[1]["points"] == 46.0


def test_parse_hkg_chinese_headers_preserve_native_script_names():
    from scrape_fed_hkg import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_CHINESE_HTML_TABLE)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Choi Chun Yin Ryan"
    assert rows[0]["club"] == "香港劍擊學校"
    assert rows[0]["points"] == 83.5
    assert rows[0]["metadata"]["alt_name"] == "蔡俊彥"
    assert rows[1]["name"] == "梁千雨"
    assert rows[1]["metadata"] == {}


def test_parse_hkg_empty_html_returns_empty_list():
    from scrape_fed_hkg import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_hkg_no_data_page_returns_empty_list():
    from scrape_fed_hkg import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_hkg_skips_dns_dq_and_summary_rows():
    from scrape_fed_hkg import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 2
    assert [row["name"] for row in rows] == ["Wu Sophia", "Cheng Hiu Wai Valerie"]
    assert [row["metadata"]["alt_name"] for row in rows] == ["符妤名", "鄭曉為"]


def test_hkg_ranking_combos_cover_required_rankings():
    from scrape_fed_hkg import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_storage_rank_keeps_tied_published_rank_in_metadata():
    from scrape_fed_hkg import _storage_rank

    used_ranks: set[Any] = set()

    assert _storage_rank(1, used_ranks, 1) == (1, {})
    assert _storage_rank(2, used_ranks, 2) == (2, {})
    assert _storage_rank(2, used_ranks, 3) == (3, {"published_rank": 2})
    assert _storage_rank(3, used_ranks, 3) == (4, {"published_rank": 3})


def test_current_season_format():
    from scrape_fed_hkg import current_season

    season = current_season()
    assert re.match(r"^\d{4}-\d{4}$", season)
    start, end = season.split("-")
    assert int(end) == int(start) + 1

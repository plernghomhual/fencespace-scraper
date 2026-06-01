"""
Tests for scrape_fed_jpn.py.

Fixture text mirrors public Japan Fencing Association ranking PDFs discovered
under https://fencing-jpn.jp/cms/wp-content/uploads/2025/04/.

Relevant PDF table columns:
  順位 | 氏名 | 所属 | 2025年協会登録 | カテゴリ | 獲得総得点 | ...

The scraper stores Japanese names in the source order used by the PDFs.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_PDF_TEXT = """
2025年度　男子フルーレ（シニア）ランキング表
2025/4/1 更新
順位 | 氏名 | 所属 | 2025年 協会登録 | カテ ゴリ | 獲得 総得点 | 国内 獲得 ポイント
1 | 西藤俊哉 | 株式会社セプテーニ・ホールディングス |  | S | 88 | 88
2 | 永野雄大 | NEXUS FENCING CLUB |  | S | 87 | 79
3 | 安部慶輝 | 秋田緑ヶ丘病院 |  | S | 78,5 | 76
4 | バーナード洋人 | 加藤学園暁秀中学校・高等学校 | F1008557 | J | 99 | 87
"""


FIXTURE_WHITESPACE_PDF_TEXT = """
2025年度　女子サーブル（シニア）ランキング表
順位 氏名 所属 2025年協会登録 カテゴリ 獲得総得点 国内獲得ポイント
1 江村美咲 立飛ホールディングス S 100 100
2 小林かなえ 株式会社河合電器製作所 S 85 85
3 脇田樹魅 沼津信用金庫 U23 93 79
4 高嶋理紗 オリエンタル酵母工業株式会社(OYC) S 73 73
"""


FIXTURE_HTML_TABLE = """
<!doctype html>
<html>
<body>
  <table>
    <thead>
      <tr>
        <th>順位</th><th>選手名</th><th>所属</th><th>得点</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>辻すみれ</td><td>大垣共立銀行</td><td>108</td></tr>
      <tr><td>2</td><td>長瀬凛乃</td><td>日本女子体育大学</td><td>102.5</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
順位 | 氏名 | 所属 | 2025年 協会登録 | カテ ゴリ | 獲得 総得点
DNS | 棄権選手 | 札幌クラブ |  | S | 0
DQ | 失格選手 | 東京クラブ |  | S | 0
合計 | 4名 |  |  |  | 400
1 | 周藤美月 | 日本大学 | F1001982 | J | 166
2 | 金高生幸 | 愛知工業大学名電高等学校 |  | J | 148
"""


FIXTURE_NO_DATA = """
2025年度 ランキング表
現在公開されているランキングはありません。
No rankings available.
"""


def test_parse_jpn_pdf_text_returns_rows_and_preserves_native_scripts():
    from scrape_fed_jpn import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_PDF_TEXT)

    assert len(rows) == 4
    assert rows[0] == {
        "rank": 1,
        "name": "西藤俊哉",
        "club": "株式会社セプテーニ・ホールディングス",
        "points": 88.0,
    }
    assert rows[1]["name"] == "永野雄大"
    assert rows[1]["club"] == "NEXUS FENCING CLUB"
    assert rows[2]["points"] == 78.5
    assert rows[3]["name"] == "バーナード洋人"


def test_parse_jpn_whitespace_pdf_text_rows():
    from scrape_fed_jpn import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_WHITESPACE_PDF_TEXT)

    assert len(rows) == 4
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "江村美咲"
    assert rows[0]["club"] == "立飛ホールディングス"
    assert rows[0]["points"] == 100.0
    assert rows[2]["club"] == "沼津信用金庫"


def test_parse_jpn_language_specific_html_headers():
    from scrape_fed_jpn import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_HTML_TABLE)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "辻すみれ"
    assert rows[0]["club"] == "大垣共立銀行"
    assert rows[0]["points"] == 108.0
    assert rows[1]["name"] == "長瀬凛乃"
    assert rows[1]["points"] == 102.5


def test_parse_jpn_empty_html_returns_empty_list():
    from scrape_fed_jpn import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_jpn_no_data_page_returns_empty_list():
    from scrape_fed_jpn import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_jpn_skips_dns_dq_and_summary_rows():
    from scrape_fed_jpn import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 2
    assert [row["name"] for row in rows] == ["周藤美月", "金高生幸"]


def test_ranking_combos_cover_all_required_japan_rankings():
    from scrape_fed_jpn import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_current_season_format():
    from scrape_fed_jpn import current_season

    season = current_season()
    assert re.match(r"^\d{4}-\d{4}$", season)
    start, end = season.split("-")
    assert int(end) == int(start) + 1

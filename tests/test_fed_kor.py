"""
Tests for scrape_fed_kor.py.

Probe summary (2026-06-01):
  - koreafencing.org / www.koreafencing.org: DNS resolution failed.
  - Current KFA site: https://fencing.sports.or.kr/ returns server-rendered Korean HTML.
  - Candidate national ranking paths (/ranking, /rank, /api/rankings, etc.) return 404.
  - Public competition XHR /game/finishRank returns JSON final-standing rows:
      rankNo, plyNm, teamNm, scoreVal
    These are competition results, not national season rankings.

Fixtures below cover the requested Korean ranking table shape and a trimmed
version of the probed KFA JSON result structure.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_KOREAN_TABLE = """
<!doctype html>
<html lang="ko">
<body>
  <table class="ranking">
    <thead>
      <tr><th>순위</th><th>이름</th><th>소속</th><th>점수</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>윤정현</td><td>국군체육부대</td><td>1,234.50</td></tr>
      <tr><td>2위</td><td>오상욱 (OH Sanguk)</td><td>대전광역시청</td><td>987,5</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_ALTERNATE_KOREAN_HEADERS = """
<html>
<body>
  <table>
    <tr><th>등위</th><th>성명</th><th>팀명</th><th>포인트</th></tr>
    <tr><td>1</td><td>송세라</td><td>부산광역시청</td><td>75</td></tr>
  </table>
</body>
</html>
"""


FIXTURE_EMPTY_TABLE = """
<html>
<body>
  <table>
    <thead><tr><th>순위</th><th>이름</th><th>소속</th><th>점수</th></tr></thead>
    <tbody></tbody>
  </table>
</body>
</html>
"""


FIXTURE_NO_TABLE = """
<html>
<body><p>공개된 랭킹 자료가 없습니다.</p></body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
<html>
<body>
  <table>
    <tr><th>순위</th><th>이름</th><th>소속</th><th>점수</th></tr>
    <tr><td>DNS</td><td>기권 선수</td><td>서울특별시청</td><td>0</td></tr>
    <tr><td>DQ</td><td>실격 선수</td><td>부산광역시청</td><td>0</td></tr>
    <tr><td>합계</td><td>총점</td><td></td><td>200</td></tr>
    <tr><td>3</td><td>홍하은</td><td>서울특별시청</td><td>64.25</td></tr>
  </table>
</body>
</html>
"""


FIXTURE_KFA_FINISH_RANK_JSON = json.dumps(
    {
        "resultList": [
            {
                "rankNo": "1",
                "plyNm": "윤정현",
                "teamNm": "국군체육부대",
                "scoreVal": 0.0,
            },
            {
                "rankNo": "2",
                "plyNm": "장효민",
                "teamNm": "울산광역시청",
                "scoreVal": "0",
            },
        ]
    },
    ensure_ascii=False,
)


def test_parse_korean_table_preserves_hangul_names_and_points():
    from scrape_fed_kor import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_KOREAN_TABLE)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "윤정현"
    assert rows[0]["club"] == "국군체육부대"
    assert rows[0]["points"] == 1234.5

    assert rows[1]["rank"] == 2
    assert rows[1]["name"] == "오상욱"
    assert rows[1]["alternate_name"] == "OH Sanguk"
    assert rows[1]["points"] == 987.5


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_kor import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table(FIXTURE_EMPTY_TABLE) == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_kor import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_TABLE) == []


def test_parse_skips_dns_dq_and_summary_rows():
    from scrape_fed_kor import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert rows == [
        {
            "rank": 3,
            "name": "홍하은",
            "club": "서울특별시청",
            "points": 64.25,
        }
    ]


def test_parse_language_specific_headers_and_native_script_names():
    from scrape_fed_kor import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_ALTERNATE_KOREAN_HEADERS)

    assert rows == [
        {
            "rank": 1,
            "name": "송세라",
            "club": "부산광역시청",
            "points": 75.0,
        }
    ]


def test_parse_probed_kfa_finish_rank_json_shape():
    from scrape_fed_kor import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_KFA_FINISH_RANK_JSON)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "윤정현"
    assert rows[0]["club"] == "국군체육부대"
    assert rows[0]["points"] == 0.0

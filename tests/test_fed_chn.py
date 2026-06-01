"""
Tests for scrape_fed_chn.py.

Fixture JSON is trimmed from the public China fencing information platform API:
  GET https://fencing.yy-sport.com.cn/fencingapi/rankinfo/total/week
  params: season=2026, week=第二十一周(05月18日至05月24日), itemType=I,
          groupCode=PS/PJ, weapon=F/E/S, gender=M/F
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_API_RESPONSE = """
{
  "code": 0,
  "msg": null,
  "data": {
    "records": [
      {
        "id": 6630047,
        "season": "2026",
        "week": "第二十一周",
        "groupCode": "PS",
        "groupName": "成年组",
        "weapon": "F",
        "gender": "M",
        "athleteName": "郭一凡",
        "organName": "安徽击剑队",
        "totalRank": 1,
        "totalPoints": "472.0",
        "memberInfo": {
          "memberName": "郭一凡",
          "genderDes": "男"
        }
      },
      {
        "id": 6630331,
        "season": "2026",
        "week": "第二十一周",
        "groupCode": "PS",
        "groupName": "成年组",
        "weapon": "F",
        "gender": "F",
        "athleteName": "张思琪",
        "organName": "安徽击剑队",
        "totalRank": 2,
        "totalPoints": "436.0",
        "memberInfo": {
          "memberName": "张思琪",
          "genderDes": "女"
        }
      },
      {
        "id": 6630999,
        "season": "2026",
        "week": "第二十一周",
        "groupCode": "PS",
        "groupName": "成年组",
        "weapon": "F",
        "gender": "M",
        "athleteName": "范零",
        "organName": "测试击剑队",
        "totalRank": 3,
        "totalPoints": 0
      }
    ],
    "total": 207,
    "size": 5,
    "current": 1
  }
}
"""


FIXTURE_CHINESE_TABLE = """
<!doctype html>
<html lang="zh-CN">
<body>
  <table>
    <thead>
      <tr><th>排名</th><th>姓名</th><th>单位</th><th>积分</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>王子杰</td><td>上海体育大学击剑队</td><td>400,0</td></tr>
      <tr><td>DNS</td><td>测试弃权</td><td>测试队</td><td>0</td></tr>
      <tr><td>DQ</td><td>测试取消</td><td>测试队</td><td>0</td></tr>
      <tr><td>合计</td><td colspan="3">共 1 人</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_NO_TABLE = """
<!doctype html>
<html lang="zh-CN"><body><p>暂无数据</p></body></html>
"""


def test_parse_china_api_response_returns_cjk_rows():
    from scrape_fed_chn import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_API_RESPONSE)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "郭一凡",
        "club": "安徽击剑队",
        "points": 472.0,
    }
    assert rows[1]["name"] == "张思琪"
    assert rows[1]["points"] == 436.0
    assert rows[2]["name"] == "范零"
    assert rows[2]["points"] == 0.0


def test_parse_chinese_headers_and_decimal_comma_preserves_native_script():
    from scrape_fed_chn import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_CHINESE_TABLE)

    assert rows == [
        {
            "rank": 1,
            "name": "王子杰",
            "club": "上海体育大学击剑队",
            "points": 400.0,
        }
    ]


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_chn import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_chn import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_TABLE) == []


def test_dns_dq_and_summary_rows_are_skipped():
    from scrape_fed_chn import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_CHINESE_TABLE)

    assert len(rows) == 1
    assert all(row["name"] not in {"测试弃权", "测试取消"} for row in rows)


def test_ranking_combos_cover_senior_and_junior_all_weapons_and_genders():
    from scrape_fed_chn import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert ("Foil", "Men", "Senior") in RANKING_COMBOS
    assert ("Sabre", "Women", "Junior") in RANKING_COMBOS


def test_fetch_rankings_page_uses_supported_page_size_and_paginates(monkeypatch):
    import scrape_fed_chn as scraper

    scraper._latest_api_season.cache_clear()
    scraper._latest_week.cache_clear()
    calls = []

    def fake_get_json(url, params=None):
        calls.append((url, dict(params or {})))
        if url == scraper.SEASON_ENDPOINT:
            return {"code": 0, "data": [{"seasonDes": "2026"}]}
        if url == scraper.WEEK_ENDPOINT:
            return {"code": 0, "data": {"week": [{"value": "第二十一周(05月18日至05月24日)"}]}}
        if url == scraper.RANKINGS_ENDPOINT:
            assert params["size"] == 20
            page = params["current"]
            record = {
                "totalRank": page,
                "athleteName": "郭一凡" if page == 1 else "张思琪",
                "organName": "安徽击剑队",
                "totalPoints": "472.0" if page == 1 else "436.0",
            }
            return {"code": 0, "data": {"records": [record], "pages": 2, "total": 2}}
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(scraper, "_get_json", fake_get_json)

    content = scraper.fetch_rankings_page("Foil", "Men", "Senior")
    rows = scraper.parse_rankings_table(content)

    assert [row["name"] for row in rows] == ["郭一凡", "张思琪"]
    assert [params["current"] for url, params in calls if url == scraper.RANKINGS_ENDPOINT] == [1, 2]

    scraper._latest_api_season.cache_clear()
    scraper._latest_week.cache_clear()

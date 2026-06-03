"""
Tests for scrape_fed_tpe.py.

Probe evidence:
  - Official site: https://www.fencing.org.tw/
  - Request method: GET
  - Response format: public HTML index plus XLSX ranking files on x.webdo.cc.
  - Current homepage ranking section exposes youth workbooks including
    青年組排名(115-1)(公告版).xlsx. No current senior full-ranking workbook
    was visible in the probed public homepage snippet.
  - Traditional Chinese ranking headers include 名次/排名, 姓名, 單位/俱樂部, 積分.
"""

from __future__ import annotations

import io
import os
import re
import sys
from datetime import datetime, timezone

from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


TRADITIONAL_HTML = """
<html>
<body>
  <table>
    <thead>
      <tr><th>排名</th><th>姓名</th><th>單位</th><th>積分</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>陳弈通</td><td>奧林擊劍</td><td>1,234.50</td></tr>
      <tr><td>2</td><td>CHEN PO-HAN BORIS</td><td>奧林擊劍</td><td>98,5</td></tr>
      <tr><td>3</td><td>洪莉翔</td><td>中正國中</td><td>76</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


NO_DATA_HTML = """
<html><body><p>目前無公開排名資料，請至會員登入查詢。</p></body></html>
"""


SKIP_ROWS_HTML = """
<table>
  <tr><th>名次</th><th>姓名</th><th>俱樂部</th><th>積分</th></tr>
  <tr><td>DNS</td><td>未出賽選手</td><td>臺北</td><td>0</td></tr>
  <tr><td>DQ</td><td>取消資格選手</td><td>臺北</td><td>0</td></tr>
  <tr><td>合計</td><td>總計 2 人</td><td></td><td>120</td></tr>
  <tr><td>備註</td><td>最新完整排名將於賽程完竣後更新</td><td></td><td></td></tr>
  <tr><td>排名</td><td>姓名</td><td>單位</td><td>積分</td></tr>
  <tr><td>A</td><td>非數字名次</td><td>臺中</td><td>10</td></tr>
  <tr><td>4</td><td>吳柏賢 Michael WU</td><td>奧林擊劍</td><td>42,75</td></tr>
</table>
"""


RANKING_INDEX_HTML = """
<html>
<body>
  <section id="ranking">
    <h2>Ranking 選手排名</h2>
    <a href="https://x.webdo.cc/userfiles/taipeifencing/files/%E9%9D%92%E5%B9%B4%E7%B5%84%E6%8E%92%E5%90%8D%28115-1%29%28%E5%85%AC%E5%91%8A%E7%89%88%29.xlsx">
      青年組排名(115-1)(公告版).xlsx
    </a>
    <a href="https://x.webdo.cc/userfiles/taipeifencing/files/%E9%9D%92%E5%B0%91%E5%B9%B4%E7%B5%84%E6%8E%92%E5%90%8D%28115-1%29%28%E5%85%AC%E5%91%8A%E7%89%88%29.xlsx">
      青少年組排名(115-1)(公告版).xlsx
    </a>
    <a href="https://x.webdo.cc/userfiles/taipeifencing/files/%E5%B0%91%E5%B9%B4%E7%B5%84%E6%8E%92%E5%90%8D%28115-1%29%28%E5%85%AC%E5%91%8A%E7%89%88%29.xlsx">
      少年組排名(115-1)(公告版).xlsx
    </a>
  </section>
</body>
</html>
"""


def _make_tpe_workbook_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "青年組排名"
    ws.append(["115年度最新全國青年組積分排名", "", "", "", "", "", "", ""])
    ws.append(["男子銳劍", "", "", "", "女子鈍劍", "", "", ""])
    ws.append(["名次", "姓名", "單位", "積分", "名次", "姓名", "俱樂部", "積分"])
    ws.append([1, "邱哲瀚", "臺灣體大", 320.5, 1, "程昕", "輔仁大學", 288])
    ws.append([2, "陳秉濬", "繁星擊劍", "118,75", 2, "張皇美子", "奧林擊劍", "102,25"])
    ws.append(["合計", "2 人", "", "", "DNS", "未出賽", "臺北", 0])
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def test_parse_traditional_headers_returns_valid_rows_and_preserves_names():
    from scrape_fed_tpe import parse_rankings_table

    rows = parse_rankings_table(TRADITIONAL_HTML)

    assert len(rows) == 3
    assert rows[0] == {
        "rank": 1,
        "name": "陳弈通",
        "club": "奧林擊劍",
        "points": 1234.5,
    }
    assert rows[1]["name"] == "CHEN PO-HAN BORIS"
    assert rows[1]["points"] == 98.5
    assert rows[2]["name"] == "洪莉翔"


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_tpe import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_tpe import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_malformed_non_numeric_dns_dq_and_summary_rows():
    from scrape_fed_tpe import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_HTML)

    assert rows == [
        {
            "rank": 4,
            "name": "吳柏賢 Michael WU",
            "club": "奧林擊劍",
            "points": 42.75,
        }
    ]


def test_parse_text_table_with_language_specific_headers():
    from scrape_fed_tpe import parse_rankings_table

    text = "名次 | 姓名 | 俱樂部 | 積分\n1 | 盧星彤 | 高市劍會 | 66,5"

    rows = parse_rankings_table(text)

    assert rows == [{"rank": 1, "name": "盧星彤", "club": "高市劍會", "points": 66.5}]


def test_ranking_combos_cover_all_required_tpe_rankings():
    from scrape_fed_tpe import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_discovers_public_workbook_and_extracts_combo(monkeypatch):
    import scrape_fed_tpe

    workbook_bytes = _make_tpe_workbook_bytes()
    calls = []

    class FakeResponse:
        def __init__(self, *, url, status_code=200, text="", content=b"", headers=None):
            self.url = url
            self.status_code = status_code
            self.text = text
            self.content = content
            self.headers = headers or {}

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url == scrape_fed_tpe.BASE_URL:
            return FakeResponse(
                url=url,
                text=RANKING_INDEX_HTML,
                content=RANKING_INDEX_HTML.encode(),
                headers={"content-type": "text/html; charset=UTF-8"},
            )
        if "青年組排名" in url or "%E9%9D%92%E5%B9%B4" in url:
            return FakeResponse(
                url=url,
                content=workbook_bytes,
                headers={
                    "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                },
            )
        return FakeResponse(url=url, status_code=404, text="missing", content=b"missing")

    monkeypatch.setattr(scrape_fed_tpe, "federation_request", fake_request)
    scrape_fed_tpe._RANKING_FILE_CACHE.clear()
    scrape_fed_tpe._WORKBOOK_CACHE.clear()

    content = scrape_fed_tpe.fetch_rankings_page("Epee", "Men", "Junior")
    rows = scrape_fed_tpe.parse_rankings_table(content)

    assert calls[0][1] == scrape_fed_tpe.BASE_URL
    assert any("x.webdo.cc" in call[1] for call in calls)
    assert rows == [
        {"rank": 1, "name": "邱哲瀚", "club": "臺灣體大", "points": 320.5},
        {"rank": 2, "name": "陳秉濬", "club": "繁星擊劍", "points": 118.75},
    ]


def test_fetch_rankings_page_returns_none_for_missing_senior_combo(monkeypatch):
    import scrape_fed_tpe

    class FakeResponse:
        url = scrape_fed_tpe.BASE_URL
        status_code = 200
        text = RANKING_INDEX_HTML
        content = RANKING_INDEX_HTML.encode()
        headers = {"content-type": "text/html"}

    monkeypatch.setattr(scrape_fed_tpe, "federation_request", lambda *args, **kwargs: FakeResponse())
    scrape_fed_tpe._RANKING_FILE_CACHE.clear()
    scrape_fed_tpe._WORKBOOK_CACHE.clear()

    assert scrape_fed_tpe.fetch_rankings_page("Foil", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_on_404_download(monkeypatch):
    import scrape_fed_tpe

    class FakeResponse:
        def __init__(self, *, url, status_code=200, text="", content=b"", headers=None):
            self.url = url
            self.status_code = status_code
            self.text = text
            self.content = content
            self.headers = headers or {}

    def fake_request(method, url, **kwargs):
        if url == scrape_fed_tpe.BASE_URL:
            return FakeResponse(url=url, text=RANKING_INDEX_HTML, headers={"content-type": "text/html"})
        return FakeResponse(url=url, status_code=404, text="not found", content=b"not found")

    monkeypatch.setattr(scrape_fed_tpe, "federation_request", fake_request)
    scrape_fed_tpe._RANKING_FILE_CACHE.clear()
    scrape_fed_tpe._WORKBOOK_CACHE.clear()

    assert scrape_fed_tpe.fetch_rankings_page("Foil", "Men", "Junior") is None


def test_fetch_rankings_page_returns_none_for_blocked_login_or_js_only_pages(monkeypatch):
    import scrape_fed_tpe

    class FakeResponse:
        def __init__(self, text, status_code=200):
            self.url = scrape_fed_tpe.BASE_URL
            self.status_code = status_code
            self.text = text
            self.content = text.encode()
            self.headers = {"content-type": "text/html"}

    cases = [
        FakeResponse("會員登入 Login required"),
        FakeResponse("<html><noscript>Please enable JavaScript</noscript></html>"),
        FakeResponse("Forbidden", status_code=403),
    ]

    for response in cases:
        monkeypatch.setattr(scrape_fed_tpe, "federation_request", lambda *args, _response=response, **kwargs: _response)
        scrape_fed_tpe._RANKING_FILE_CACHE.clear()
        scrape_fed_tpe._WORKBOOK_CACHE.clear()

        assert scrape_fed_tpe.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_main_attempts_all_12_combos_and_reports_partial_coverage(monkeypatch):
    import scrape_fed_tpe

    calls = []
    completed = {}
    states = {}

    def fake_fetch(weapon, gender, category):
        calls.append((weapon, gender, category))
        if category == "Junior":
            return TRADITIONAL_HTML
        return None

    def fake_write(rows, source, season):
        return len(rows)

    class FakeLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            return self

        def complete(self, *, written=0, failed=0, skipped=0, metadata=None):
            completed.update(
                {"written": written, "failed": failed, "skipped": skipped, "metadata": metadata}
            )

        def error(self, exc_str):
            raise AssertionError(exc_str)

    monkeypatch.setattr(scrape_fed_tpe, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_tpe, "write_rankings", fake_write)
    monkeypatch.setattr(scrape_fed_tpe, "ScraperRunLogger", FakeLogger)
    monkeypatch.setattr(scrape_fed_tpe, "set_state", lambda source, key, value: states.setdefault(key, value))
    monkeypatch.setattr(scrape_fed_tpe.time, "sleep", lambda seconds: None)

    scrape_fed_tpe.main()

    assert len(calls) == 12
    assert completed["written"] == 18
    assert completed["failed"] == 6
    assert completed["skipped"] == 0
    assert len(completed["metadata"]["failed_combos"]) == 6
    assert states["last_run"]["combos_working"] == 6


def test_current_season_format_and_before_july(monkeypatch):
    import scrape_fed_tpe

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 1, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(scrape_fed_tpe, "datetime", FixedDateTime)

    season = scrape_fed_tpe.current_season()
    assert season == "2025-2026"
    assert re.match(r"^\d{4}-\d{4}$", season)

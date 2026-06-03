import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


THAI_TEXT_FIXTURE = """
Ranking 2024 - 2025 Season
อันดับ\tชื่อ\tสโมสร\tคะแนน
1\tกิตติพงษ์อินทรสุวรรณ\tBangkok Fencing Club\t120,50
2\tชุติกาญจน์ ศรีไทย\tสโมสรฟันดาบไทย\t87.25
"""


THAI_HTML_FIXTURE = """
<table>
  <thead>
    <tr><th>อันดับ</th><th>ชื่อ</th><th>สโมสร</th><th>คะแนน</th></tr>
  </thead>
  <tbody>
    <tr><td>๑</td><td>ศุภวัฒน์อินทร์ทอง</td><td>สโมสรฟันดาบกรุงเทพ</td><td>1.234,5</td></tr>
    <tr><td>2</td><td>ภัทราภรณ์ แซ่ลิ้ม</td><td>Royal Thai Navy</td><td>98</td></tr>
  </tbody>
</table>
"""


SKIP_ROWS_FIXTURE = """
<table>
  <tr><th>อันดับ</th><th>ชื่อ</th><th>สโมสร</th><th>คะแนน</th></tr>
  <tr><td>DNS</td><td>นักกีฬาถอนตัว</td><td>ABC</td><td>0</td></tr>
  <tr><td>DQ</td><td>นักกีฬาถูกตัดสิทธิ์</td><td>ABC</td><td>0</td></tr>
  <tr><td>รวม</td><td>สรุปคะแนนรวม</td><td></td><td>300</td></tr>
  <tr><td>ABC</td><td>แถวเสีย</td><td>ABC</td><td>10</td></tr>
  <tr><td>0</td><td>อันดับศูนย์</td><td>ABC</td><td>0</td></tr>
  <tr><td>3</td><td>นฤเบศร์ ทดสอบ</td><td>Fencing Arena</td><td>44,25</td></tr>
</table>
"""


NO_DATA_HTML = """
<html><body><main><p>ไม่มีข้อมูลการจัดอันดับในขณะนี้</p></main></body></html>
"""


HOMEPAGE_FIXTURE = """
<html><body>
  <h2>Ranking 2024 - 2025 Season</h2>
  <h2>รุ่นทั่วไป / Senior</h2>
  <a href="https://drive.google.com/file/d/senior-me/view?usp=sharing">เอเป้บุคคลชาย</a>
  <a href="https://drive.google.com/file/d/senior-mf/view?usp=sharing">ฟอยล์บุคคลชาย</a>
  <a href="https://drive.google.com/file/d/senior-ms/view?usp=sharing">เซเบอร์บุคคลชาย</a>
  <a href="https://drive.google.com/file/d/senior-we/view?usp=sharing">เอเป้บุคคลหญิง</a>
  <a href="https://drive.google.com/file/d/senior-wf/view?usp=sharing">ฟอยล์บุคคลหญิง</a>
  <a href="https://drive.google.com/file/d/senior-ws/view?usp=sharing">เซเบอร์บุคคลหญิง</a>
  <h2>รุ่นอายุไม่เกิน 20 ปี / Junior</h2>
  <a href="https://drive.google.com/file/d/u20-me/view?usp=sharing">เอเป้บุคคลชาย</a>
  <a href="https://drive.google.com/file/d/u20-mf/view?usp=sharing">ฟอยล์บุคคลชาย</a>
  <a href="https://drive.google.com/file/d/u20-ms/view?usp=sharing">เซเบอร์บุคคลชาย</a>
  <a href="https://drive.google.com/file/d/u20-we/view?usp=sharing">เอเป้บุคคลหญิง</a>
  <a href="https://drive.google.com/file/d/u20-wf/view?usp=sharing">ฟอยล์บุคคลหญิง</a>
  <a href="https://drive.google.com/file/d/u20-ws/view?usp=sharing">เซเบอร์บุคคลหญิง</a>
  <h2>รุ่นอายุไม่เกิน 17 ปี / Cadet</h2>
  <a href="https://drive.google.com/file/d/cadet-me/view?usp=sharing">เอเป้บุคคลชาย</a>
</body></html>
"""


class FakeResponse:
    def __init__(self, status_code=200, text="", content=b"", headers=None, url="https://example.test/"):
        self.status_code = status_code
        self.text = text
        self.content = content or text.encode("utf-8")
        self.headers = headers or {}
        self.url = url


def test_parse_pdf_text_returns_valid_rows_with_decimal_comma():
    from scrape_fed_tha import parse_rankings_table

    rows = parse_rankings_table(THAI_TEXT_FIXTURE)

    assert rows[0] == {
        "rank": 1,
        "name": "กิตติพงษ์อินทรสุวรรณ",
        "club": "Bangkok Fencing Club",
        "points": 120.5,
    }
    assert rows[1]["name"] == "ชุติกาญจน์ ศรีไทย"
    assert rows[1]["club"] == "สโมสรฟันดาบไทย"
    assert rows[1]["points"] == 87.25


def test_parse_empty_html_returns_empty_list():
    from scrape_fed_tha import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_no_table_or_no_data_page_returns_empty_list():
    from scrape_fed_tha import parse_rankings_table

    assert parse_rankings_table(NO_DATA_HTML) == []


def test_parse_skips_dns_dq_summary_malformed_and_non_numeric_rows():
    from scrape_fed_tha import parse_rankings_table

    rows = parse_rankings_table(SKIP_ROWS_FIXTURE)

    assert rows == [
        {
            "rank": 3,
            "name": "นฤเบศร์ ทดสอบ",
            "club": "Fencing Arena",
            "points": 44.25,
        }
    ]


def test_parse_thai_headers_preserves_native_script_names_and_thai_digits():
    from scrape_fed_tha import parse_rankings_table

    rows = parse_rankings_table(THAI_HTML_FIXTURE)

    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "ศุภวัฒน์อินทร์ทอง"
    assert rows[0]["club"] == "สโมสรฟันดาบกรุงเทพ"
    assert rows[0]["points"] == 1234.5
    assert rows[1]["name"] == "ภัทราภรณ์ แซ่ลิ้ม"


def test_ranking_combos_attempt_all_12_standard_combos():
    from scrape_fed_tha import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert set(RANKING_COMBOS) == {
        (weapon, gender, category)
        for category in ("Senior", "Junior")
        for weapon in ("Foil", "Epee", "Sabre")
        for gender in ("Men", "Women")
    }


def test_extract_ranking_urls_maps_public_homepage_sections():
    from scrape_fed_tha import _extract_ranking_urls

    urls = _extract_ranking_urls(HOMEPAGE_FIXTURE)

    assert len(urls) == 12
    assert urls[("Epee", "Men", "Senior")].endswith("/senior-me/view?usp=sharing")
    assert urls[("Foil", "Women", "Senior")].endswith("/senior-wf/view?usp=sharing")
    assert urls[("Sabre", "Men", "Junior")].endswith("/u20-ms/view?usp=sharing")
    assert ("Epee", "Men", "Cadet") not in urls


def test_fetch_rankings_page_extracts_text_from_public_google_drive_pdf(monkeypatch):
    import scrape_fed_tha

    requested_urls = []

    def fake_request(method, url, **kwargs):
        requested_urls.append(url)
        return FakeResponse(
            text="%PDF fake",
            content=b"%PDF fake",
            headers={"content-type": "application/pdf"},
            url=url,
        )

    monkeypatch.setattr(scrape_fed_tha, "_ranking_url_for", lambda *args: "https://drive.google.com/file/d/file-id/view?usp=sharing")
    monkeypatch.setattr(scrape_fed_tha, "federation_request", fake_request)
    monkeypatch.setattr(scrape_fed_tha, "_extract_pdf_text", lambda content: THAI_TEXT_FIXTURE)

    content = scrape_fed_tha.fetch_rankings_page("Epee", "Men", "Senior")

    assert content == THAI_TEXT_FIXTURE
    assert requested_urls == ["https://drive.google.com/uc?export=download&id=file-id"]


def test_fetch_rankings_page_returns_none_for_404(monkeypatch):
    import scrape_fed_tha

    monkeypatch.setattr(scrape_fed_tha, "_ranking_url_for", lambda *args: "https://drive.google.com/file/d/missing/view")
    monkeypatch.setattr(
        scrape_fed_tha,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(status_code=404, url=args[1]),
    )

    assert scrape_fed_tha.fetch_rankings_page("Foil", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_blocked_response(monkeypatch):
    import scrape_fed_tha

    monkeypatch.setattr(scrape_fed_tha, "_ranking_url_for", lambda *args: "https://drive.google.com/file/d/blocked/view")
    monkeypatch.setattr(
        scrape_fed_tha,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(status_code=403, text="Forbidden", url=args[1]),
    )
    monkeypatch.setattr(scrape_fed_tha.time, "sleep", lambda _seconds: None)

    assert scrape_fed_tha.fetch_rankings_page("Epee", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_for_network_error(monkeypatch):
    import scrape_fed_tha

    def raise_request_error(*args, **kwargs):
        raise requests.RequestException("network blocked")

    monkeypatch.setattr(scrape_fed_tha, "_ranking_url_for", lambda *args: "https://drive.google.com/file/d/file-id/view")
    monkeypatch.setattr(scrape_fed_tha, "federation_request", raise_request_error)
    monkeypatch.setattr(scrape_fed_tha.time, "sleep", lambda _seconds: None)

    assert scrape_fed_tha.fetch_rankings_page("Foil", "Women", "Senior") is None


@pytest.mark.parametrize(
    "html",
    [
        "<html><body>Sign in to continue to Google Drive</body></html>",
        "<html><body><noscript>Enable JavaScript</noscript><div>Loading...</div></body></html>",
    ],
)
def test_fetch_rankings_page_returns_none_for_login_only_or_js_only_pages(monkeypatch, html):
    import scrape_fed_tha

    monkeypatch.setattr(scrape_fed_tha, "_ranking_url_for", lambda *args: "https://drive.google.com/file/d/file-id/view")
    monkeypatch.setattr(
        scrape_fed_tha,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(text=html, headers={"content-type": "text/html"}, url=args[1]),
    )

    assert scrape_fed_tha.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_fetch_rankings_page_returns_none_for_missing_combo(monkeypatch):
    import scrape_fed_tha

    monkeypatch.setattr(scrape_fed_tha, "_ranking_url_for", lambda *args: None)

    assert scrape_fed_tha.fetch_rankings_page("Foil", "Women", "Junior") is None

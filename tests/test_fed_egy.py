"""Tests for the Egypt federation rankings scraper."""

import re

# Fixture based on the probed public Egypt ranking detail page:
# https://www.fencingegypt.org/EFF/Ranking/OverallRankingDetails.aspx?OverAllRankingID=12
FIXTURE_ARABIC_HTML = """
<!DOCTYPE html>
<html lang="ar">
<body>
<table class="table table-striped">
  <tr><td>تصدير إلى ملف اكسيل عودة لقائمة التصنيف</td></tr>
  <tr>
    <td>التصنيف</td>
    <td>الاسم</td>
    <td>النادى</td>
    <td>إجمالى النقاط</td>
    <td>كأس مصر (2) موسم 25-26 لسلاح الشيش فردي عمومى رجال</td>
  </tr>
  <tr>
    <td>1</td>
    <td>محمد ماهر حمزة دسوقي</td>
    <td>اكاديمية تيما</td>
    <td>243.00</td>
    <td>32.0</td>
  </tr>
  <tr>
    <td>2</td>
    <td>عبد الرحمن حسين عبد الفتاح الحسيني طلبه</td>
    <td>نادي الزهور الرياضى</td>
    <td>152.00</td>
    <td>16.0</td>
  </tr>
</table>
</body>
</html>
"""


FIXTURE_ENGLISH_HTML = """
<!DOCTYPE html>
<html lang="en">
<body>
<table>
  <thead>
    <tr>
      <th>Rank</th>
      <th>Name</th>
      <th>Club</th>
      <th>Total Points</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>NOHA HANY HUSSEIN</td>
      <td>Nasr City Sporting Club</td>
      <td>52,50</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
<!DOCTYPE html>
<html lang="ar">
<body>
<table>
  <tr><th>المركز</th><th>الاسم</th><th>النادي</th><th>النقاط</th></tr>
  <tr><td>DNS</td><td>لاعبة منسحبة</td><td>نادى الشمس الرياضي</td><td>0.00</td></tr>
  <tr><td>2</td><td>DQ</td><td>نادى المعادي الرياضي</td><td>0.00</td></tr>
  <tr><td>المجموع</td><td></td><td></td><td>296.50</td></tr>
  <tr><td>3</td><td>لجين خالد أحمد شريف شريف على</td><td>نادى المعادي الرياضي</td><td>44,50</td></tr>
</table>
</body>
</html>
"""


FIXTURE_NO_TABLE = """
<!DOCTYPE html>
<html lang="ar">
<body><p>لا توجد بيانات تصنيف متاحة حاليا.</p></body>
</html>
"""


def test_parse_rankings_table_returns_arabic_rows():
    from scrape_fed_egy import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_ARABIC_HTML)

    assert len(rows) == 2
    assert rows[0] == {
        "rank": 1,
        "name": "محمد ماهر حمزة دسوقي",
        "club": "اكاديمية تيما",
        "points": 243.0,
    }
    assert rows[1]["name"] == "عبد الرحمن حسين عبد الفتاح الحسيني طلبه"
    assert rows[1]["club"] == "نادي الزهور الرياضى"
    assert rows[1]["points"] == 152.0


def test_parse_rankings_table_preserves_native_script_names():
    from scrape_fed_egy import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_ARABIC_HTML)

    assert re.search(r"[\u0600-\u06FF]", rows[0]["name"])
    assert rows[0]["name"] == "محمد ماهر حمزة دسوقي"


def test_parse_rankings_table_accepts_english_headers_and_decimal_commas():
    from scrape_fed_egy import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_ENGLISH_HTML)

    assert rows == [
        {
            "rank": 1,
            "name": "NOHA HANY HUSSEIN",
            "club": "Nasr City Sporting Club",
            "points": 52.5,
        }
    ]


def test_parse_rankings_table_empty_html_returns_empty_list():
    from scrape_fed_egy import parse_rankings_table

    assert parse_rankings_table("") == []


def test_parse_rankings_table_no_table_returns_empty_list():
    from scrape_fed_egy import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_TABLE) == []


def test_parse_rankings_table_skips_dns_dq_and_summary_rows():
    from scrape_fed_egy import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert rows == [
        {
            "rank": 3,
            "name": "لجين خالد أحمد شريف شريف على",
            "club": "نادى المعادي الرياضي",
            "points": 44.5,
        }
    ]


def test_fetch_rankings_page_uses_public_detail_url(monkeypatch):
    import scrape_fed_egy

    calls = []

    class Response:
        status_code = 200
        text = "<html>ranking</html>"

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(scrape_fed_egy.requests, "get", fake_get)

    html = scrape_fed_egy.fetch_rankings_page("Foil", "Men", "Junior")

    assert html == "<html>ranking</html>"
    assert calls[0][0] == (
        "https://www.fencingegypt.org/EFF/Ranking/"
        "OverallRankingDetails.aspx?OverAllRankingID=11"
    )
    assert calls[0][1]["headers"] == scrape_fed_egy.HEADERS
    assert calls[0][1]["allow_redirects"] is True


def test_fetch_rankings_page_returns_none_on_http_error(monkeypatch):
    import scrape_fed_egy

    class Response:
        status_code = 404
        text = "not found"

    monkeypatch.setattr(scrape_fed_egy.requests, "get", lambda *args, **kwargs: Response())

    assert scrape_fed_egy.fetch_rankings_page("Sabre", "Women", "Senior") is None


def test_fetch_rankings_page_returns_none_on_network_error(monkeypatch):
    import scrape_fed_egy

    def raise_error(*args, **kwargs):
        raise scrape_fed_egy.requests.RequestException("network down")

    monkeypatch.setattr(scrape_fed_egy.requests, "get", raise_error)

    assert scrape_fed_egy.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_current_season_format():
    from scrape_fed_egy import current_season

    assert re.match(r"^\d{4}-\d{4}$", current_season())


def test_ranking_combos_cover_twelve_public_senior_and_junior_pages():
    from scrape_fed_egy import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert ("Foil", "Men", "Senior") in RANKING_COMBOS
    assert ("Epee", "Women", "Junior") in RANKING_COMBOS

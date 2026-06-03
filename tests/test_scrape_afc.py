import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ENGLISH_RESULT_HTML = """
<html>
  <head><title>Asian Cadet Circuit Tashkent 2022</title></head>
  <body>
    <h1>Cadet Men's Sabre Individual - Final Results</h1>
    <p>21 October 2022</p>
    <table>
      <tr>
        <th>Rank</th><th>Fencer</th><th>Country</th><th>FIE ID</th>
        <th>Medal</th><th>Points</th>
      </tr>
      <tr><td>1</td><td>LEE, Wonwoo</td><td>Korea</td><td>12345</td><td>Gold</td><td>64.0</td></tr>
      <tr><td>2</td><td>YAMADA Kentaro</td><td>Japan</td><td></td><td>Silver</td><td>52</td></tr>
      <tr><td>3=</td><td>Al-Farsi, Omar</td><td>Kuwait</td><td>99887</td><td>Bronze</td><td>40.5</td></tr>
    </table>
  </body>
</html>
"""


KOREAN_RESULT_HTML = """
<html lang="ko">
  <body>
    <h1>2025 아시아 시니어 여자 에페 개인 최종 순위</h1>
    <time datetime="2025-06-22">2025년 6월 22일</time>
    <table>
      <tr><th>순위</th><th>선수</th><th>국가</th><th>메달</th><th>점수</th></tr>
      <tr><td>1</td><td>최인정</td><td>대한민국</td><td>금</td><td>64</td></tr>
      <tr><td>2</td><td>吉村 美穂</td><td>日本</td><td>은</td><td>52</td></tr>
    </table>
  </body>
</html>
"""


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self._limit = None

    def select(self, columns):
        self.client.selects.append((self.table_name, columns))
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def limit(self, count):
        self._limit = count
        return self

    def execute(self):
        filters = {(op, column): value for op, column, value in self.filters}
        if self.table_name == "fs_fencers":
            if filters.get(("eq", "fie_id")) == "12345":
                return FakeResponse([{"id": "fie-match"}])
            if filters.get(("ilike", "name")) == "Identity Match" and filters.get(("eq", "country")) == "KOR":
                return FakeResponse([])
        if self.table_name == "fs_fencer_identities":
            if filters.get(("ilike", "canonical_name")) == "Identity Match" and filters.get(("eq", "country")) == "KOR":
                return FakeResponse([{"fs_fencer_row_ids": ["identity-row"]}])
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.selects = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


class FailingSession:
    def get(self, url, **_kwargs):
        raise requests.ConnectionError(f"blocked from test: {url}")


def test_parse_english_afc_result_page_extracts_metadata_and_rows():
    from scrape_afc import parse_html_result_events

    events = parse_html_result_events(
        ENGLISH_RESULT_HTML,
        source_url="https://asian-fencing.com/?p=7948",
        edition_name="Asian Cadet Circuit Tashkent 2022",
    )

    assert len(events) == 1
    event = events[0]
    assert event["event_name"] == "Cadet Men's Sabre Individual - Final Results"
    assert event["weapon"] == "Sabre"
    assert event["gender"] == "Men"
    assert event["category"] == "Cadet"
    assert event["team"] is False
    assert event["date"] == "2022-10-21"
    assert event["results"] == [
        {"rank": 1, "name": "Wonwoo Lee", "country": "KOR", "fie_id": "12345", "medal": "Gold", "points": 64.0, "source_url": "https://asian-fencing.com/?p=7948"},
        {"rank": 2, "name": "YAMADA Kentaro", "country": "JPN", "fie_id": None, "medal": "Silver", "points": 52.0, "source_url": "https://asian-fencing.com/?p=7948"},
        {"rank": 3, "name": "Omar Al-Farsi", "country": "KUW", "fie_id": "99887", "medal": "Bronze", "points": 40.5, "source_url": "https://asian-fencing.com/?p=7948"},
    ]


def test_parse_korean_host_result_page_handles_non_latin_headers_and_country_names():
    from scrape_afc import parse_html_result_events

    events = parse_html_result_events(
        KOREAN_RESULT_HTML,
        source_url="https://asfc.inaikasi.org/results/womens-epee",
        edition_name="Asian Senior Championships Bali 2025",
    )

    assert len(events) == 1
    event = events[0]
    assert event["weapon"] == "Epee"
    assert event["gender"] == "Women"
    assert event["category"] == "Senior"
    assert event["date"] == "2025-06-22"
    assert event["results"] == [
        {"rank": 1, "name": "최인정", "country": "KOR", "fie_id": None, "medal": "Gold", "points": 64.0, "source_url": "https://asfc.inaikasi.org/results/womens-epee"},
        {"rank": 2, "name": "吉村 美穂", "country": "JPN", "fie_id": None, "medal": "Silver", "points": 52.0, "source_url": "https://asfc.inaikasi.org/results/womens-epee"},
    ]


def test_normalize_country_code_handles_asian_aliases_cjk_and_arabic():
    from scrape_afc import normalize_country_code

    assert normalize_country_code("Hong Kong, China") == "HKG"
    assert normalize_country_code("대한민국") == "KOR"
    assert normalize_country_code("日本") == "JPN"
    assert normalize_country_code("كازاخستان") == "KAZ"
    assert normalize_country_code("Chinese Taipei") == "TPE"


def test_parse_circuit_pdf_text_keeps_points_without_inventing_medals():
    from scrape_afc import parse_pdf_text_events

    text = """
    Fencing Confederation of Asia
    Mens Epee FCA Ranking 2025
    Rank  Name  Country  FIE ID  Points
    1  PARK Sangyoung  Korea  12345  180.5
    2  YAMADA Kentaro  JPN  67890  144
    """

    events = parse_pdf_text_events(
        text,
        source_url="https://asian-fencing.com/wp-content/uploads/2025/09/Fencing-Confederation-of-Asia-mens-epee.pdf",
        edition_name="Fencing Confederation of Asia Cadet Circuit Ranking 2025",
    )

    assert len(events) == 1
    event = events[0]
    assert event["weapon"] == "Epee"
    assert event["gender"] == "Men"
    assert event["category"] == "Cadet"
    assert event["results"] == [
        {"rank": 1, "name": "PARK Sangyoung", "country": "KOR", "fie_id": "12345", "medal": None, "points": 180.5, "source_url": "https://asian-fencing.com/wp-content/uploads/2025/09/Fencing-Confederation-of-Asia-mens-epee.pdf"},
        {"rank": 2, "name": "YAMADA Kentaro", "country": "JPN", "fie_id": "67890", "medal": None, "points": 144.0, "source_url": "https://asian-fencing.com/wp-content/uploads/2025/09/Fencing-Confederation-of-Asia-mens-epee.pdf"},
    ]


def test_probe_sources_marks_network_errors_as_blocked_with_evidence():
    from scrape_afc import AFCScrapeSource, probe_sources

    source = AFCScrapeSource(
        source_id="blocked",
        url="https://example.invalid/afc",
        kind="html",
        edition_name="Blocked Test",
    )

    results = probe_sources([source], session=FailingSession(), timeout=1)

    assert results == [
        {
            "source_id": "blocked",
            "url": "https://example.invalid/afc",
            "status": None,
            "content_type": None,
            "blocked": True,
            "evidence": "ConnectionError: blocked from test: https://example.invalid/afc",
        }
    ]


def test_build_result_rows_matches_fie_id_then_identity_and_skips_unmatched():
    from scrape_afc import build_result_rows

    unmatched = []
    rows = build_result_rows(
        tournament_id="tournament-1",
        event={
            "event_name": "Senior Women's Epee Individual",
            "weapon": "Epee",
            "gender": "Women",
            "category": "Senior",
            "team": False,
            "date": "2025-06-22",
            "source_url": "https://asian-fencing.test/event",
        },
        result_rows=[
            {"rank": 1, "name": "FIE Match", "country": "KOR", "fie_id": "12345", "medal": "Gold", "points": 64.0, "source_url": "https://asian-fencing.test/event"},
            {"rank": 2, "name": "Identity Match", "country": "KOR", "fie_id": None, "medal": "Silver", "points": 52.0, "source_url": "https://asian-fencing.test/event"},
            {"rank": 3, "name": "No Match", "country": "JPN", "fie_id": None, "medal": "Bronze", "points": 40.0, "source_url": "https://asian-fencing.test/event"},
        ],
        client=FakeClient(),
        unmatched=unmatched,
    )

    assert [row["fencer_id"] for row in rows] == ["fie-match", "identity-row"]
    assert all(row["fencer_id"] for row in rows)
    assert unmatched == [
        {
            "tournament_id": "tournament-1",
            "event_name": "Senior Women's Epee Individual",
            "rank": 3,
            "name": "No Match",
            "country": "JPN",
            "fie_id": None,
            "reason": "no_fencer_match",
            "source_url": "https://asian-fencing.test/event",
        }
    ]

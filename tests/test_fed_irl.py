"""
Tests for scrape_fed_irl.py.

Probe evidence:
  - Current Fencing Ireland pages are under https://www.fencingireland.net/.
  - The site menu links Senior Rankings to public Google Sheet
    1iZdJ_GfFRx61_qwvYa5Ck9dTKN3lM852zfDSf2Cvw-g.
  - The visible sheet view exposes rows with headers:
    Rank | Fencer | Club | Points
  - Junior ranking links were not visible on the probed public
    cadet-and-junior page.
"""

from __future__ import annotations

from typing import cast
import io
import os
import re
import sys
from datetime import datetime, timezone

import pytest
import requests
from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_GOOGLE_SHEETS_TSV = """
Rank\tFencer\tClub\tPoints\tSouths\tWests
1\tJonathan Burnside\tFoyle Fencing\t587\t119\t87
2\tLiam Zone\tDUFC\t399\t152\t19
12\tEoghan Ó Hanluain Fay\tDUFC\t191\t0\t59
"""


FIXTURE_NO_DATA = """
<html>
  <body>
    <p>No rankings available.</p>
    <p>Please select another ranking file.</p>
  </body>
</html>
"""


FIXTURE_NON_STANDARD_ROWS = """
Rank | Fencer | Club | Points
DNS | Did Not Start | DUFC | 0
DQ | Disqualified Fencer | UCD | 0
Total | 2 fencers |  | 300
abc | Bad Rank | Club | 10
3 | Tom O'Brien | Ambush Fencing Club | 243
4.0 | Andrew Chirko | UCD | 374
"""


FIXTURE_LANGUAGE_AND_NATIVE_NAMES = """
<table>
  <thead>
    <tr><th>Rang</th><th>Nom</th><th>Club</th><th>Points</th></tr>
  </thead>
  <tbody>
    <tr><td>1.</td><td>张伟 Ó Néill</td><td>Épée Club</td><td>12,5</td></tr>
  </tbody>
</table>
"""


def _xlsx_bytes(sheet_name: str = "Senior Mens Epee") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(["Rank", "Fencer", "Club", "Points", "Souths"])
    ws.append([1, "Jonathan Burnside", "Foyle Fencing", 587, 119])
    ws.append([2, "Eoghan Ó Hanluain Fay", "DUFC", 191.5, 0])
    ws2 = wb.create_sheet("Notes")
    ws2.append(["not", "rankings"])
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


class FakeResponse:
    def __init__(self, *, status_code=200, text="", content=b"", headers=None):
        self.status_code = status_code
        self.text = text
        self.content = content
        self.headers = headers or {}


def test_parse_irl_google_sheets_tsv_returns_rows():
    from scrape_fed_irl import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_GOOGLE_SHEETS_TSV)

    assert len(rows) == 3
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "Jonathan Burnside"
    assert rows[0]["club"] == "Foyle Fencing"
    assert rows[0]["points"] == 587.0
    assert rows[2]["name"] == "Eoghan Ó Hanluain Fay"
    assert rows[2]["points"] == 191.0


def test_parse_irl_empty_html_returns_empty_list():
    from scrape_fed_irl import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("   ") == []


def test_parse_irl_no_table_no_data_page_returns_empty_list():
    from scrape_fed_irl import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_irl_skips_dns_dq_summary_malformed_and_non_numeric_rank_rows():
    from scrape_fed_irl import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert [row["name"] for row in rows] == ["Tom O'Brien", "Andrew Chirko"]
    assert rows[0]["points"] == 243.0
    assert rows[1]["rank"] == 4


def test_parse_irl_language_headers_and_native_script_names_are_preserved():
    from scrape_fed_irl import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_LANGUAGE_AND_NATIVE_NAMES)

    assert rows == [
        {
            "rank": 1,
            "name": "张伟 Ó Néill",
            "club": "Épée Club",
            "points": 12.5,
        }
    ]


def test_ranking_combos_cover_all_required_ireland_rankings():
    from scrape_fed_irl import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12
    assert set(RANKING_COMBOS) == {
        ("Foil", "Men", "Senior"),
        ("Foil", "Women", "Senior"),
        ("Epee", "Men", "Senior"),
        ("Epee", "Women", "Senior"),
        ("Sabre", "Men", "Senior"),
        ("Sabre", "Women", "Senior"),
        ("Foil", "Men", "Junior"),
        ("Foil", "Women", "Junior"),
        ("Epee", "Men", "Junior"),
        ("Epee", "Women", "Junior"),
        ("Sabre", "Men", "Junior"),
        ("Sabre", "Women", "Junior"),
    }


def test_fetch_rankings_page_extracts_requested_public_workbook_sheet(monkeypatch):
    import scrape_fed_irl

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse(
            content=_xlsx_bytes(),
            headers={
                "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            },
        )

    monkeypatch.setattr(scrape_fed_irl, "federation_request", fake_request)
    scrape_fed_irl._WORKBOOK_CACHE.clear()

    content = scrape_fed_irl.fetch_rankings_page("Epee", "Men", "Senior")
    content = cast(str, content)
    rows = scrape_fed_irl.parse_rankings_table(content)

    assert calls[0][0] == "get"
    assert calls[0][1] == scrape_fed_irl.SENIOR_RANKINGS_XLSX_URL
    assert rows[0]["name"] == "Jonathan Burnside"
    assert rows[1]["points"] == 191.5


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_irl

    monkeypatch.setattr(
        scrape_fed_irl,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(status_code=404, text="missing", content=b"missing"),
    )
    scrape_fed_irl._WORKBOOK_CACHE.clear()

    assert scrape_fed_irl.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_on_network_error(monkeypatch):
    import scrape_fed_irl

    def fake_request(*args, **kwargs):
        raise requests.RequestException("connection failed")

    monkeypatch.setattr(scrape_fed_irl, "federation_request", fake_request)
    scrape_fed_irl._WORKBOOK_CACHE.clear()

    assert scrape_fed_irl.fetch_rankings_page("Epee", "Men", "Senior") is None


@pytest.mark.parametrize(
    "html",
    [
        "<html><body><a href='https://accounts.google.com/'>Sign in</a></body></html>",
        "JavaScript isn't enabled in your browser, so this file can't be opened.",
    ],
)
def test_fetch_rankings_page_returns_none_for_login_or_js_only_responses(monkeypatch, html):
    import scrape_fed_irl

    monkeypatch.setattr(
        scrape_fed_irl,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(
            text=html,
            content=html.encode("utf-8"),
            headers={"content-type": "text/html; charset=utf-8"},
        ),
    )
    scrape_fed_irl._WORKBOOK_CACHE.clear()

    assert scrape_fed_irl.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_fetch_rankings_page_returns_none_for_missing_combo_sheet(monkeypatch):
    import scrape_fed_irl

    monkeypatch.setattr(
        scrape_fed_irl,
        "federation_request",
        lambda *args, **kwargs: FakeResponse(
            content=_xlsx_bytes("Senior Mens Epee"),
            headers={
                "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            },
        ),
    )
    scrape_fed_irl._WORKBOOK_CACHE.clear()

    assert scrape_fed_irl.fetch_rankings_page("Sabre", "Women", "Junior") is None


def test_current_season_format_and_before_july(monkeypatch):
    import scrape_fed_irl

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 2, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(scrape_fed_irl, "datetime", FixedDateTime)

    season = scrape_fed_irl.current_season()
    assert season == "2025-2026"
    assert re.match(r"^\d{4}-\d{4}$", season)


def test_main_attempts_all_12_combos_and_records_missing_juniors(monkeypatch):
    import scrape_fed_irl

    calls = []
    completed = {}
    state_updates = []

    class FakeLogger:
        def start(self):
            return self

        def complete(self, **kwargs):
            completed.update(kwargs)

        def error(self, exc_str):
            completed["error"] = exc_str

    def fake_fetch(weapon, gender, category):
        calls.append((weapon, gender, category))
        if category == "Senior":
            return FIXTURE_GOOGLE_SHEETS_TSV
        return None

    monkeypatch.setattr(scrape_fed_irl, "ScraperRunLogger", lambda module: FakeLogger())
    monkeypatch.setattr(scrape_fed_irl, "get_state", lambda source, key: None)
    monkeypatch.setattr(
        scrape_fed_irl,
        "set_state",
        lambda source, key, value: state_updates.append((source, key, value)),
    )
    monkeypatch.setattr(scrape_fed_irl, "fetch_rankings_page", fake_fetch)
    monkeypatch.setattr(scrape_fed_irl, "write_rankings", lambda rows, source, season: len(rows))
    monkeypatch.setattr(scrape_fed_irl.time, "sleep", lambda seconds: None)

    scrape_fed_irl.main()

    assert calls == scrape_fed_irl.RANKING_COMBOS
    assert completed["written"] == 18
    assert completed["failed"] == 0
    assert completed["skipped"] == 6
    assert completed["metadata"]["working_combos"] == 6
    assert completed["metadata"]["attempted_combos"] == 12
    assert len(completed["metadata"]["skipped_combos"]) == 6
    assert state_updates[-1][0] == scrape_fed_irl.SOURCE
    assert state_updates[-1][1] == "last_run"

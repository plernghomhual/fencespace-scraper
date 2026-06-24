"""
Tests for scrape_fed_sgp.py.

Fixtures mirror public Singapore ranking data probed from:
  https://www.fencingsingapore.org.sg/ranking-files/

Current 25-26 ranking files are XLSX downloads, one workbook per weapon.
Relevant workbook sheets include SME/SWE/JME/JWE, SMF/SWF/JMF /JWF, SMS/SWS/JMS/JWS.
Key columns:
  # | Fencer | Club/School | ... | Final Ranking Points | Final Rank
"""

import io
import os
import re
import sys
from datetime import UTC, datetime, timezone
from typing import cast

from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


FIXTURE_XLSX_TSV = """
\t\t\t\t\tLocal Comp Final Rank\t\t\t\tOverseas Comp Final Ranking\t\t\t\t\t\t\t\t\tFor local comp seeding\t\tA+B\t\tA+C+D\t
#\tFencer\tClub/School\tBirth Year\tAge\tSST1\tSST2\tSG Open\tBest Local (1)\tBest Local (2)\tBest WC (1)\tNext Best (1)\tNext Best (2)\t5% Base pts from 2024\t33% after 2 local comp\tOverall Local Points\tLocal Rank Entry B\tFinal Ranking Points\tFinal Rank Entry C
1\tSITO JIAN TONG\tIDP\t2003\t23\t8\t\t2\t26\t14\t125.9\t15.7535\t14\t820\t0\t40\t3\t244.6035\t1
2\tONG AZFAR LUQMAN\tSSP\t2006\t20\t2\t3\t1\t32\t26\t15.8515\t26\t20\t481\t0\t58\t2\t109.589\t2
"""


FIXTURE_SCHOOL_AND_NATIVE_NAMES = """
<html>
<body>
  <table>
    <thead>
      <tr><th>Rank</th><th>Name</th><th>Club</th><th>School</th><th>Points</th></tr>
    </thead>
    <tbody>
      <tr><td>1</td><td>TANG DANIELLA WENG YAN</td><td>ZFF</td><td>MGS</td><td>289,916</td></tr>
      <tr><td>2</td><td>陈嘉仪</td><td></td><td>南洋女中</td><td>125.5</td></tr>
    </tbody>
  </table>
</body>
</html>
"""


FIXTURE_SCHOOL_ONLY = """
<table>
  <tr><th>#</th><th>Fencer</th><th>School</th><th>Total Points</th></tr>
  <tr><td>1</td><td>LEE EN QI</td><td>SSP</td><td>65,9648</td></tr>
</table>
"""


FIXTURE_NO_DATA = """
<html><body><p>No rankings available.</p><p>Please select another ranking file.</p></body></html>
"""


FIXTURE_NON_STANDARD_ROWS = """
Ranking | Fencer | Club | School | Final Ranking Points
DNS | Did Not Start | BLD | RI | 0
DQ | Disqualified Fencer | ZFF | HCI | 0
Total | 2 fencers |  |  | 300
1 | LIM JAE JIA EN | SSP | SSP | 222,390
2 | YANG SHUHAN* | ASG | NYGH | 192.3144
"""


def _make_xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "JMF "
    ws.append(
        [
            "",
            "",
            "",
            "",
            "",
            "Local Comp Final Rank",
            "",
            "",
            "",
            "",
            "Final Ranking",
        ]
    )
    ws.append(
        [
            "#",
            "Fencer",
            "Club/School",
            "Birth Year",
            "Age",
            "SJT1",
            "SJT2",
            "Overall Local Points",
            "Local Rank Entry B",
            "Final Ranking Points",
            "Final Rank Entry C",
        ]
    )
    ws.append([1, "ROBSON SAMUEL ELIJAH", "ZFF", 2007, 19, 1, 2, 47.196, 5, 852.8276, 1])
    ws.append([2, "CHUA SI JIE", "BLD", 2007, 19, 11, 12, 32.7048, 8, 299.6698, 2])
    ws_ref = wb.create_sheet("Reference")
    ws_ref.append(["Competition", "Position"])
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def test_parse_sgp_xlsx_tsv_returns_realistic_rows():
    from scrape_fed_sgp import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_XLSX_TSV)

    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    assert rows[0]["name"] == "SITO JIAN TONG"
    assert rows[0]["club"] == "IDP"
    assert rows[0]["points"] == 244.6035
    assert rows[1]["name"] == "ONG AZFAR LUQMAN"
    assert rows[1]["points"] == 109.589


def test_parse_sgp_empty_html_returns_empty_list():
    from scrape_fed_sgp import parse_rankings_table

    assert parse_rankings_table("") == []
    assert parse_rankings_table("<html><body></body></html>") == []


def test_parse_sgp_no_table_no_data_page_returns_empty_list():
    from scrape_fed_sgp import parse_rankings_table

    assert parse_rankings_table(FIXTURE_NO_DATA) == []


def test_parse_sgp_skips_dns_dq_and_summary_rows():
    from scrape_fed_sgp import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_NON_STANDARD_ROWS)

    assert len(rows) == 2
    assert [row["name"] for row in rows] == ["LIM JAE JIA EN", "YANG SHUHAN*"]
    assert rows[0]["points"] == 222.39


def test_parse_sgp_preserves_native_names_and_school_metadata():
    from scrape_fed_sgp import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_SCHOOL_AND_NATIVE_NAMES)

    assert rows[0]["club"] == "ZFF"
    assert rows[0]["school"] == "MGS"
    assert rows[0]["metadata"]["school"] == "MGS"
    assert rows[0]["points"] == 289.916
    assert rows[1]["name"] == "陈嘉仪"
    assert rows[1]["club"] is None
    assert rows[1]["school"] == "南洋女中"
    assert rows[1]["metadata"]["school"] == "南洋女中"


def test_parse_sgp_school_only_column_does_not_become_club():
    from scrape_fed_sgp import parse_rankings_table

    rows = parse_rankings_table(FIXTURE_SCHOOL_ONLY)

    assert rows == [
        {
            "rank": 1,
            "name": "LEE EN QI",
            "club": None,
            "school": "SSP",
            "points": 65.9648,
            "metadata": {"school": "SSP"},
        }
    ]


def test_ranking_combos_cover_all_required_singapore_rankings():
    from scrape_fed_sgp import RANKING_COMBOS

    assert len(RANKING_COMBOS) == 12
    assert len(set(RANKING_COMBOS)) == 12


def test_fetch_rankings_page_extracts_requested_sheet_from_public_xlsx(monkeypatch):
    import scrape_fed_sgp

    xlsx_bytes = _make_xlsx_bytes()
    calls = []

    class FakeResponse:
        def __init__(self, *, status_code=200, text="", content=b"", headers=None):
            self.status_code = status_code
            self.text = text
            self.content = content
            self.headers = headers or {}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url == "https://example.test/foil-page":
            return FakeResponse(
                text='<a class="wpdm-download-link" data-downloadurl="https://example.test/foil.xlsx">Download</a>',
                content=b"<html></html>",
                headers={"content-type": "text/html; charset=UTF-8"},
            )
        if url == "https://example.test/foil.xlsx":
            return FakeResponse(
                content=xlsx_bytes,
                headers={
                    "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                },
            )
        return FakeResponse(status_code=404, text="not found", content=b"not found")

    monkeypatch.setitem(
        scrape_fed_sgp.DOWNLOAD_PAGES,
        "Foil",
        "https://example.test/foil-page",
    )
    monkeypatch.setattr(scrape_fed_sgp.requests, "get", fake_get)
    scrape_fed_sgp._WORKBOOK_CACHE.clear()

    content = scrape_fed_sgp.fetch_rankings_page("Foil", "Men", "Junior")
    content = cast(str, content)
    rows = scrape_fed_sgp.parse_rankings_table(content)

    assert calls[0][0] == "https://example.test/foil-page"
    assert calls[1][0] == "https://example.test/foil.xlsx"
    assert rows[0]["name"] == "ROBSON SAMUEL ELIJAH"
    assert rows[0]["points"] == 852.8276


def test_fetch_rankings_page_returns_none_on_404(monkeypatch):
    import scrape_fed_sgp

    class FakeResponse:
        status_code = 404
        text = "missing"
        content = b"missing"
        headers = {"content-type": "text/html"}

    monkeypatch.setitem(scrape_fed_sgp.DOWNLOAD_PAGES, "Epee", "https://example.test/epee")
    monkeypatch.setattr(scrape_fed_sgp.requests, "get", lambda *args, **kwargs: FakeResponse())
    scrape_fed_sgp._WORKBOOK_CACHE.clear()

    assert scrape_fed_sgp.fetch_rankings_page("Epee", "Men", "Senior") is None


def test_current_season_format_and_before_july(monkeypatch):
    import scrape_fed_sgp

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 6, 1, tzinfo=tz or UTC)

    monkeypatch.setattr(scrape_fed_sgp, "datetime", FixedDateTime)

    season = scrape_fed_sgp.current_season()
    assert season == "2025-2026"
    assert re.match(r"^\d{4}-\d{4}$", season)

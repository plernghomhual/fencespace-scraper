import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


EVF_SOURCE_URL = "https://www.veteransfencing.eu/fencing/results/ec2025/"

EVF_PLOVDIV_HTML = """
<html>
  <body>
    <h2>Championships 2025 Individual \u2013 Plovdiv, Bulgaria</h2>
    <h3>Results</h3>
    <h4>Men\u2019s Foil</h4>
    <pre>
    Category 1 (29)
    1 MALACHENKO Franck     FRA
    2 TREPO Eric            FRA
    3 ILYASHEV Mikhail      UKR
    3 LE QUEMENT Guillaume  BEL
    </pre>
    <h4>Women\u2019s Ep\u00e9e</h4>
    <pre>
    Category 3 (44)
    1 HOHLBEIN Frauke       GER
    2 CANO DIOSA Rosa Maria ESP
    3 ALBERTSON Pia         SWE
    3 PINGO-ALMADA Monica   NED
    </pre>
  </body>
</html>
"""

FTL_LOGIN_HTML = """
<html>
  <body>
    <h1>Fencing Time Live</h1>
    <p>Welcome to Fencing Time Live</p>
    <p>To see tournament information on Fencing Time Live, you need to be logged in.</p>
  </body>
</html>
"""

FIE_ENTRY_TEXT = """
## Championnats du monde veterans 50-59 (Manama) 2025-11-16
Number fencer entered: 47
Fencer category: V
Weapon: F
Gender: M
Type: I
Name Country Ranking Points License ID Birth Date Date Inscription
ILICHEV PAVEL _AIN 16051974001 66353 1974-05-16 2025-10-01
"""


def test_parse_evf_results_page_preserves_age_categories_and_medals():
    from scrape_veterans import parse_evf_results_page

    events = parse_evf_results_page(EVF_PLOVDIV_HTML, source_url=EVF_SOURCE_URL)

    assert len(events) == 2

    men_foil = events[0]
    assert men_foil["tournament"] == "Championships 2025 Individual - Plovdiv, Bulgaria"
    assert men_foil["season"] == "2025"
    assert men_foil["weapon"] == "Foil"
    assert men_foil["gender"] == "Men"
    assert men_foil["age_category"] == "V1"
    assert men_foil["category"] == "Veteran 40-49"
    assert men_foil["source_url"] == EVF_SOURCE_URL

    assert men_foil["results"] == [
        {
            "rank": 1,
            "fencer": "Franck Malachenko",
            "country": "FRA",
            "club": None,
            "points": None,
            "medal": "Gold",
            "fie_id": None,
        },
        {
            "rank": 2,
            "fencer": "Eric Trepo",
            "country": "FRA",
            "club": None,
            "points": None,
            "medal": "Silver",
            "fie_id": None,
        },
        {
            "rank": 3,
            "fencer": "Mikhail Ilyashev",
            "country": "UKR",
            "club": None,
            "points": None,
            "medal": "Bronze",
            "fie_id": None,
        },
        {
            "rank": 3,
            "fencer": "Guillaume Le Quement",
            "country": "BEL",
            "club": None,
            "points": None,
            "medal": "Bronze",
            "fie_id": None,
        },
    ]


def test_parse_evf_results_page_keeps_veteran_categories_explicit():
    from scrape_veterans import parse_evf_results_page

    events = parse_evf_results_page(EVF_PLOVDIV_HTML, source_url=EVF_SOURCE_URL)

    assert {event["category"] for event in events} == {"Veteran 40-49", "Veteran 60-69"}
    assert all(event["category"] not in {"Senior", "Junior", "Cadet", "Veteran"} for event in events)
    assert all(event["metadata"]["category_family"] == "Veteran" for event in events)
    assert events[1]["event_code"] == "evf-2025-women-epee-v3"


def test_fie_veteran_has_results_false_still_attempts_results():
    from scrape_veterans import should_attempt_fie_results

    veteran = {"category": "veteran", "hasResults": 0, "endDate": "20-11-2025"}
    veteran_age_bucket = {"category": "Veteran 50-59", "hasResults": 0, "endDate": "20-11-2025"}
    senior = {"category": "senior", "hasResults": 0, "endDate": "20-11-2025"}
    future_veteran = {"category": "veteran", "hasResults": 0, "endDate": ""}

    assert should_attempt_fie_results(veteran) is True
    assert should_attempt_fie_results(veteran_age_bucket) is True
    assert should_attempt_fie_results(senior) is False
    assert should_attempt_fie_results(future_veteran) is False


def test_source_probe_stubs_login_and_entry_lists_without_inventing_results():
    from scrape_veterans import probe_source_text

    login_probe = probe_source_text(
        FTL_LOGIN_HTML,
        "https://www.fencingtimelive.com/events/results/ABC",
    )
    assert login_probe == {
        "url": "https://www.fencingtimelive.com/events/results/ABC",
        "status": "blocked",
        "reason": "login_required",
        "result_rows_available": False,
    }

    entry_probe = probe_source_text(
        FIE_ENTRY_TEXT,
        "https://www.fie.org/competition/2025/1106/entry/pdf?lang=en",
    )
    assert entry_probe == {
        "url": "https://www.fie.org/competition/2025/1106/entry/pdf?lang=en",
        "status": "skipped",
        "reason": "entry_list_not_results",
        "result_rows_available": False,
    }


def test_matching_uses_fie_id_then_canonical_name_country_and_logs_unmatched():
    from scrape_veterans import attach_fencer_matches, build_fencer_index, write_unmatched_log

    index = build_fencer_index(
        [
            {"id": "by-fie", "fie_id": "66353", "name": "Different Person", "country": "AIN"},
            {"id": "by-name", "fie_id": None, "name": "Pia Albertson", "country": "SWE"},
        ],
        identities=[
            {
                "canonical_name": "Pia Albertson",
                "country": "SWE",
                "fie_ids": [],
                "fs_fencer_row_ids": ["by-name"],
            }
        ],
    )
    raw_rows = [
        {"rank": 1, "fencer": "Pavel Ilichev", "country": "AIN", "fie_id": "66353"},
        {"rank": 3, "fencer": "ALBERTSON Pia", "country": "SWE", "fie_id": None},
        {"rank": 9, "fencer": "No Match", "country": "ESP", "fie_id": None},
    ]

    matched, unmatched = attach_fencer_matches(raw_rows, index, source_url=EVF_SOURCE_URL)

    assert [row["fencer_id"] for row in matched] == ["by-fie", "by-name"]
    assert [row["metadata"]["match_tier"] for row in matched] == [
        "tier_1_fie_id",
        "tier_2_canonical_name_country",
    ]
    assert unmatched == [
        {
            "name": "No Match",
            "country": "ESP",
            "fie_id": None,
            "source_url": EVF_SOURCE_URL,
            "reason": "no_conservative_match",
        }
    ]

    log_path = Path.cwd() / "tmp_unmatched_veterans_test.tsv"
    try:
        write_unmatched_log(log_path, unmatched)
        text = log_path.read_text()
        assert "name\tcountry\tfie_id\tsource_url\treason" in text
        assert "No Match\tESP\t\t" in text
    finally:
        if log_path.exists():
            log_path.unlink()


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.payload = None
        self.filters = []

    def delete(self):
        self.operation = "delete"
        return self

    def insert(self, rows):
        self.operation = "insert"
        self.payload = rows
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        if self.operation == "delete":
            self.client.deletes.append((self.name, tuple(self.filters)))
            return FakeResult()
        if self.operation == "insert":
            self.client.inserts.append((self.name, self.payload))
            return FakeResult(self.payload)
        raise AssertionError(f"unexpected operation {self.operation}")


class FakeClient:
    def __init__(self):
        self.deletes = []
        self.inserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_upsert_results_skips_unmatched_rows_and_never_inserts_null_fencer_orphans():
    from scrape_veterans import build_fencer_index, upsert_results

    client = FakeClient()
    index = build_fencer_index(
        [{"id": "known", "fie_id": "111", "name": "Known Fencer", "country": "FRA"}]
    )
    event = {
        "source_url": EVF_SOURCE_URL,
        "age_category": "V1",
        "category": "Veteran 40-49",
        "weapon": "Foil",
        "gender": "Men",
        "metadata": {"category_family": "Veteran"},
        "results": [
            {"rank": 1, "fencer": "Known Fencer", "country": "FRA", "fie_id": "111", "medal": "Gold", "points": None, "club": None},
            {"rank": 2, "fencer": "Unknown Fencer", "country": "FRA", "fie_id": None, "medal": "Silver", "points": None, "club": None},
        ],
    }

    result = upsert_results(client, "tournament-id", event, index)

    assert result == {"written": 1, "skipped": 1, "unmatched": 1}
    assert client.deletes == [("fs_results", (("tournament_id", "tournament-id"),))]
    assert len(client.inserts) == 1
    table, rows = client.inserts[0]
    assert table == "fs_results"
    assert len(rows) == 1
    assert rows[0]["fencer_id"] == "known"
    assert rows[0]["category"] == "Veteran 40-49"
    assert rows[0]["metadata"]["age_category"] == "V1"
    assert rows[0]["metadata"]["category_family"] == "Veteran"


def test_upsert_results_does_not_delete_existing_rows_when_all_rows_are_unmatched():
    from scrape_veterans import build_fencer_index, upsert_results

    client = FakeClient()
    event = {
        "source_url": EVF_SOURCE_URL,
        "age_category": "V2",
        "category": "Veteran 50-59",
        "weapon": "Epee",
        "gender": "Women",
        "metadata": {"category_family": "Veteran"},
        "results": [
            {"rank": 1, "fencer": "Unknown Fencer", "country": "FRA", "fie_id": None, "medal": "Gold", "points": None, "club": None},
        ],
    }

    result = upsert_results(client, "tournament-id", event, build_fencer_index([]))

    assert result == {"written": 0, "skipped": 1, "unmatched": 1}
    assert client.deletes == []
    assert client.inserts == []

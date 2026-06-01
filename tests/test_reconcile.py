import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import reconcile_data


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.filters = []
        self.start = 0
        self.end = 999

    def select(self, columns):
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        self.client.filters.append((self.name, "eq", column, value))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.client.ranges.append((self.name, start, end))
        return self

    def execute(self):
        rows = list(self.client.tables.get(self.name, []))
        for op, column, value in self.filters:
            if op == "eq":
                rows = [row for row in rows if row.get(column) == value]
        return FakeResult(rows[self.start : self.end + 1])


class FakeClient:
    def __init__(self, tables):
        self.tables = tables
        self.selects = []
        self.filters = []
        self.ranges = []

    def table(self, name):
        return FakeTable(self, name)


def test_reconcile_matches_by_fie_id_and_reports_differences():
    client = FakeClient(
        {
            "fs_fencers": [
                {
                    "id": "f1",
                    "fie_id": "1001",
                    "name": "Lee Kiefer",
                    "country": "USA",
                    "weapon": "Foil",
                    "category": "Women's Senior",
                    "world_rank": 1,
                },
                {
                    "id": "f1-duplicate",
                    "fie_id": "1001",
                    "name": "Lee Kiefer",
                    "country": "USA",
                    "weapon": "Foil",
                    "category": "Women's Senior",
                    "world_rank": None,
                },
                {
                    "id": "f2",
                    "fie_id": "2002",
                    "name": "Ysaora Thibus",
                    "country": "FRA",
                    "weapon": "Foil",
                    "category": "Women's Senior",
                    "world_rank": 4,
                },
                {
                    "id": "f3",
                    "fie_id": "3003",
                    "name": "FIE Only",
                    "country": "ITA",
                    "weapon": "Epee",
                    "category": "Men's Senior",
                    "world_rank": 12,
                },
            ],
            "fs_national_fed_rankings": [
                {
                    "id": "n1",
                    "source": "british_fencing",
                    "fie_id": "1001",
                    "name": "KIEFER Lee",
                    "country": "USA",
                    "weapon": "Foil",
                    "rank": 3,
                },
                {
                    "id": "n2",
                    "source": "british_fencing",
                    "fie_id": "2002",
                    "name": "Ysaora Thibus",
                    "country": "FRA",
                    "weapon": "Foil",
                    "rank": 4,
                },
                {
                    "id": "n3",
                    "source": "british_fencing",
                    "fie_id": "9999",
                    "name": "British Only",
                    "country": "GBR",
                    "weapon": "Sabre",
                    "rank": 10,
                },
                {
                    "id": "n4",
                    "source": "canada_fencing",
                    "fie_id": "1001",
                    "name": "Lee Kiefer",
                    "country": "USA",
                    "weapon": "Foil",
                    "rank": 1,
                },
            ],
        }
    )

    report = reconcile_data.reconcile("FIE", "british_fencing", client=client)

    assert report["matched"] == 2
    assert report["mismatched"] == 1
    assert report["in_a_only"] == 1
    assert report["in_b_only"] == 1
    assert ("fs_national_fed_rankings", "eq", "source", "british_fencing") in client.filters

    mismatch = report["samples"]["mismatched"][0]
    assert mismatch["key"] == "fie_id:1001"
    assert mismatch["source_a"]["id"] == "f1"
    assert mismatch["source_b"]["id"] == "n1"
    assert mismatch["differences"]["name"] == {
        "source_a": "Lee Kiefer",
        "source_b": "KIEFER Lee",
    }
    assert mismatch["differences"]["rank"] == {"source_a": 1, "source_b": 3}
    assert report["samples"]["in_a_only"][0]["name"] == "FIE Only"
    assert report["samples"]["in_b_only"][0]["name"] == "British Only"


def test_reconcile_falls_back_to_name_and_country_when_fie_id_missing():
    client = FakeClient(
        {
            "fs_fencers": [
                {
                    "id": "f1",
                    "fie_id": None,
                    "name": "  Arianna Errigo ",
                    "country": "ITA",
                    "weapon": "Foil",
                    "world_rank": 2,
                }
            ],
            "fs_national_fed_rankings": [
                {
                    "id": "n1",
                    "source": "italy",
                    "fie_id": None,
                    "name": "arianna   errigo",
                    "country": "ita",
                    "weapon": "Foil",
                    "rank": 2,
                }
            ],
        }
    )

    report = reconcile_data.reconcile("FIE", "italy", client=client)

    assert report["matched"] == 1
    assert report["mismatched"] == 0
    assert report["in_a_only"] == 0
    assert report["in_b_only"] == 0
    assert report["samples"]["matched"][0]["key"] == "name_country:arianna errigo|ita"


def test_olympedia_source_uses_results_metadata_and_nationality():
    client = FakeClient(
        {
            "fs_fencers": [],
            "fs_results": [
                {
                    "id": "r1",
                    "fie_fencer_id": "5005",
                    "name": "Edoardo Mangiarotti",
                    "nationality": "ITA",
                    "weapon": "Epee",
                    "rank": 1,
                    "metadata": {"olympedia_athlete_id": "12345"},
                },
                {
                    "id": "r2",
                    "fie_fencer_id": "6006",
                    "name": "Other Result",
                    "nationality": "FRA",
                    "weapon": "Foil",
                    "rank": 2,
                    "metadata": {},
                },
            ],
            "fs_national_fed_rankings": [
                {
                    "id": "n1",
                    "source": "italy",
                    "fie_id": "5005",
                    "name": "Edoardo Mangiarotti",
                    "country": "ITA",
                    "weapon": "Epee",
                    "rank": 1,
                }
            ],
        }
    )

    report = reconcile_data.reconcile("olympedia", "italy", client=client)

    assert report["matched"] == 1
    assert report["mismatched"] == 0
    assert report["in_a_only"] == 0
    assert report["in_b_only"] == 0
    assert report["samples"]["matched"][0]["source_a"]["country"] == "ITA"


def test_main_prints_summary_and_writes_json_report(tmp_path, monkeypatch, capsys):
    client = FakeClient(
        {
            "fs_fencers": [
                {
                    "id": "f1",
                    "fie_id": "1001",
                    "name": "Lee Kiefer",
                    "country": "USA",
                    "weapon": "Foil",
                    "world_rank": 1,
                }
            ],
            "fs_national_fed_rankings": [
                {
                    "id": "n1",
                    "source": "british_fencing",
                    "fie_id": "1001",
                    "name": "Lee Kiefer",
                    "country": "USA",
                    "weapon": "Foil",
                    "rank": 1,
                }
            ],
        }
    )
    output_path = tmp_path / "report.json"
    monkeypatch.setattr(reconcile_data, "_build_client", lambda: client)

    exit_code = reconcile_data.main(
        ["--source-a", "FIE", "--source-b", "british_fencing", "--output", str(output_path)]
    )

    assert exit_code == 0
    printed = capsys.readouterr().out
    assert "Reconciliation: FIE vs british_fencing" in printed
    assert "matched: 1" in printed
    assert output_path.exists()
    saved = json.loads(output_path.read_text())
    assert saved["matched"] == 1
    assert saved["samples"]["matched"][0]["source_b"]["source"] == "british_fencing"

import csv
import importlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.gte_filters = []
        self.or_filter = None
        self.start = 0
        self.end = None

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def gte(self, column, value):
        self.gte_filters.append((column, value))
        return self

    def or_(self, expression):
        self.or_filter = expression
        self.client.or_filters.append((self.table_name, expression))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.client.ranges.append((self.table_name, start, end))
        return self

    def execute(self):
        rows = list(self.client.tables.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if str(row.get(column)) == str(value)]
        for column, value in self.gte_filters:
            rows = [row for row in rows if row.get(column) is not None and row.get(column) >= value]
        if self.or_filter:
            clauses = [part.split(".eq.", 1) for part in self.or_filter.split(",")]
            rows = [
                row
                for row in rows
                if any(len(clause) == 2 and str(row.get(clause[0])) == clause[1] for clause in clauses)
            ]
        end = self.end + 1 if self.end is not None else None
        return FakeResponse(rows[self.start:end])


class FakeSupabase:
    def __init__(self):
        self.ranges = []
        self.or_filters = []
        self.tables = {
            "fs_fencers": [
                {"id": "f1", "name": "Alex Lee", "country": "KOR", "metadata": {"seed": 1}},
                {"id": "f2", "name": "Mina Park", "country": "KOR", "metadata": {"seed": 2}},
                {"id": "f3", "name": "Sam Stone", "country": "USA", "metadata": {"seed": 3}},
            ],
            "fs_tournaments": [
                {"id": "t1", "name": "Seoul GP", "season": 2026, "type": "GP"},
                {"id": "t2", "name": "Paris WC", "season": 2025, "type": "WC"},
            ],
            "fs_rankings_history": [
                {"season": 2026, "weapon": "Epee", "gender": "Men", "rank": 1, "name": "Alex Lee"},
                {"season": 2026, "weapon": "Foil", "gender": "Women", "rank": 2, "name": "Mina Park"},
            ],
            "fs_head_to_head": [
                {"fencer_a_id": "f1", "fencer_b_id": "f2", "weapon": "Epee", "bouts_total": 7},
                {"fencer_a_id": "f3", "fencer_b_id": "f1", "weapon": "Foil", "bouts_total": 3},
            ],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


def load_cli(monkeypatch, fake):
    sys.modules.pop("cli_export", None)
    module = importlib.import_module("cli_export")
    monkeypatch.setattr(module, "get_supabase_client", lambda: fake)
    return module


def test_cli_exports_fencers_json_with_automatic_pagination(tmp_path, monkeypatch):
    fake = FakeSupabase()
    module = load_cli(monkeypatch, fake)
    output = tmp_path / "fencers.json"

    status = module.main(["fencers", "--format", "json", "--output", str(output), "--page-size", "2"])

    assert status == 0
    rows = json.loads(output.read_text())
    assert [row["id"] for row in rows] == ["f1", "f2", "f3"]
    assert fake.ranges[:2] == [("fs_fencers", 0, 1), ("fs_fencers", 2, 3)]


def test_cli_exports_tournaments_csv_to_stdout(monkeypatch, capsys):
    fake = FakeSupabase()
    module = load_cli(monkeypatch, fake)

    status = module.main(["tournaments", "--season", "2026", "--format", "csv", "--page-size", "2"])

    assert status == 0
    captured = capsys.readouterr()
    rows = list(csv.DictReader(io.StringIO(captured.out)))
    assert rows == [{"id": "t1", "name": "Seoul GP", "season": "2026", "type": "GP"}]
    assert "Fetched 1 rows" in captured.err


def test_cli_exports_rankings_with_filters(monkeypatch, capsys):
    fake = FakeSupabase()
    module = load_cli(monkeypatch, fake)

    status = module.main(["rankings", "--weapon", "Epee", "--gender", "Men", "--format", "json"])

    assert status == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows == [{"season": 2026, "weapon": "Epee", "gender": "Men", "rank": 1, "name": "Alex Lee"}]


def test_cli_exports_h2h_for_fencer_with_min_bouts(monkeypatch, capsys):
    fake = FakeSupabase()
    module = load_cli(monkeypatch, fake)

    status = module.main(["h2h", "--fencer", "f1", "--min-bouts", "5", "--format", "json"])

    assert status == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows == [{"fencer_a_id": "f1", "fencer_b_id": "f2", "weapon": "Epee", "bouts_total": 7}]
    assert fake.or_filters == [("fs_head_to_head", "fencer_a_id.eq.f1,fencer_b_id.eq.f1")]

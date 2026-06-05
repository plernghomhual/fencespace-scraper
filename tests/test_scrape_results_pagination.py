import importlib
import sys
import types


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.start = None
        self.end = None
        self.selected = None

    def select(self, columns):
        self.selected = columns
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def lte(self, column, value):
        self.filters.append(("lte", column, value))
        return self

    def gte(self, column, value):
        self.filters.append(("gte", column, value))
        return self

    def neq(self, column, value):
        self.filters.append(("neq", column, value))
        return self

    def is_(self, column, value):
        self.filters.append(("is", column, value))
        return self

    @property
    def not_(self):
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        self.client.ranges.append((self.table_name, start, end))
        return self

    def execute(self):
        rows = list(self.client.tables.get(self.table_name, []))
        for operator, column, value in self.filters:
            if operator == "eq":
                rows = [row for row in rows if row.get(column) == value]
            elif operator == "neq":
                rows = [row for row in rows if row.get(column) != value]
            elif operator == "is":
                rows = [row for row in rows if row.get(column) is None]
            elif operator == "lte":
                rows = [row for row in rows if row.get(column) <= value]
            elif operator == "gte":
                rows = [row for row in rows if row.get(column) >= value]
        if self.start is not None and self.end is not None:
            rows = rows[self.start : self.end + 1]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "fs_tournaments": [{"id": f"t-{index}", "ready": True} for index in range(5)]
        }
        self.ranges = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def import_scrape_results(monkeypatch, fake_supabase):
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-role")
    monkeypatch.setitem(sys.modules, "supabase", types.SimpleNamespace(create_client=lambda *_args: fake_supabase))
    sys.modules.pop("scrape_results", None)
    return importlib.import_module("scrape_results")


def test_fetch_all_pages_reads_beyond_supabase_default_page(monkeypatch):
    fake = FakeSupabase()
    module = import_scrape_results(monkeypatch, fake)

    rows = module.fetch_all_pages(
        fake,
        "fs_tournaments",
        "id,ready",
        lambda query: query.eq("ready", True),
        page_size=2,
    )

    assert [row["id"] for row in rows] == ["t-0", "t-1", "t-2", "t-3", "t-4"]
    assert fake.ranges == [
        ("fs_tournaments", 0, 1),
        ("fs_tournaments", 2, 3),
        ("fs_tournaments", 4, 5),
    ]

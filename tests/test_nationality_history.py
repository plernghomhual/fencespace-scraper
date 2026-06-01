import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


TIMED_BINDINGS = [
    {
        "athlete": {"value": "http://www.wikidata.org/entity/QTRANSFER"},
        "athleteLabel": {"value": "Transfer Fencer"},
        "fie_id": {"value": "100"},
        "statement": {"value": "http://www.wikidata.org/entity/statement/QTRANSFER-1"},
        "country": {"value": "http://www.wikidata.org/entity/Q38"},
        "countryLabel": {"value": "Italy"},
        "start_time": {"value": "+2008-01-01T00:00:00Z"},
        "end_time": {"value": "+2012-12-31T00:00:00Z"},
    },
    {
        "athlete": {"value": "http://www.wikidata.org/entity/QTRANSFER"},
        "athleteLabel": {"value": "Transfer Fencer"},
        "fie_id": {"value": "100"},
        "statement": {"value": "http://www.wikidata.org/entity/statement/QTRANSFER-2"},
        "country": {"value": "http://www.wikidata.org/entity/Q142"},
        "countryLabel": {"value": "France"},
        "start_time": {"value": "+2013-01-01T00:00:00Z"},
    },
]


def test_build_nationality_histories_orders_timed_citizenship_statements():
    from enrich_nationality_history import build_nationality_histories

    histories = build_nationality_histories(TIMED_BINDINGS)

    assert len(histories) == 1
    history = histories[0]
    assert history["wikidata_id"] == "QTRANSFER"
    assert history["name"] == "Transfer Fencer"
    assert history["fie_id"] == "100"
    assert history["ordered"] is True
    assert history["nationality_history"] == [
        {
            "country": "Italy",
            "country_id": "Q38",
            "start_time": "2008-01-01",
            "end_time": "2012-12-31",
            "sequence_index": 0,
            "source": "wikidata",
        },
        {
            "country": "France",
            "country_id": "Q142",
            "start_time": "2013-01-01",
            "sequence_index": 1,
            "source": "wikidata",
        },
    ]


def test_build_nationality_histories_keeps_unordered_multi_citizenship_without_times():
    from enrich_nationality_history import build_nationality_histories

    bindings = [
        {
            "athlete": {"value": "http://www.wikidata.org/entity/QUNORDERED"},
            "athleteLabel": {"value": "Dual Citizen"},
            "statement": {"value": "http://www.wikidata.org/entity/statement/QUNORDERED-1"},
            "country": {"value": "http://www.wikidata.org/entity/Q30"},
            "countryLabel": {"value": "United States"},
        },
        {
            "athlete": {"value": "http://www.wikidata.org/entity/QUNORDERED"},
            "athleteLabel": {"value": "Dual Citizen"},
            "statement": {"value": "http://www.wikidata.org/entity/statement/QUNORDERED-2"},
            "country": {"value": "http://www.wikidata.org/entity/Q16"},
            "countryLabel": {"value": "Canada"},
        },
    ]

    histories = build_nationality_histories(bindings)

    assert histories[0]["ordered"] is False
    assert histories[0]["nationality_history"] == [
        {"country": "Canada", "country_id": "Q16", "source": "wikidata"},
        {"country": "United States", "country_id": "Q30", "source": "wikidata"},
    ]


def test_build_nationality_histories_skips_single_citizenship_people():
    from enrich_nationality_history import build_nationality_histories

    assert build_nationality_histories([TIMED_BINDINGS[0]]) == []


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.range_start = 0
        self.range_end = None
        self.payload = None
        self.filters = []

    def select(self, columns):
        self.operation = "select"
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        if self.name in self.client.fail_selects and self.operation == "select":
            raise RuntimeError(f"{self.name} unavailable")
        if self.operation == "select":
            rows = self.client.tables.get(self.name, [])
            return FakeResult(rows[self.range_start : self.range_end + 1])
        if self.operation == "update":
            row_id = dict(self.filters)["id"]
            self.client.updates.append(
                {
                    "table": self.name,
                    "id": row_id,
                    "payload": self.payload,
                }
            )
            for row in self.client.tables[self.name]:
                if row["id"] == row_id:
                    row.update(self.payload)
            return FakeResult([])
        raise AssertionError(f"unexpected operation {self.operation} on {self.name}")


class FakeSupabase:
    def __init__(self, tables, fail_selects=None):
        self.tables = tables
        self.fail_selects = set(fail_selects or [])
        self.selects = []
        self.updates = []

    def table(self, name):
        return FakeTable(self, name)


def test_enrich_nationality_history_updates_identity_rows_and_cross_checks_transfers():
    from enrich_nationality_history import enrich_nationality_history

    client = FakeSupabase(
        {
            "fs_fencers": [
                {
                    "id": "fencer-1",
                    "fie_id": "100",
                    "name": "Transfer Fencer",
                    "country": "Italy",
                    "metadata": {"wikidata_id": "QTRANSFER", "existing": "keep"},
                },
                {
                    "id": "fencer-2",
                    "fie_id": "100",
                    "name": "Transfer Fencer",
                    "country": "France",
                    "metadata": {},
                },
            ],
            "fs_fencer_identities": [
                {
                    "id": "identity-1",
                    "fie_ids": ["100"],
                    "fs_fencer_row_ids": ["fencer-1", "fencer-2"],
                    "metadata": {},
                }
            ],
            "fs_fencer_transfers": [
                {
                    "fencer_id": "fencer-1",
                    "from_country": "Italy",
                    "to_country": "France",
                    "source": "rankings_history",
                    "confirmed": True,
                    "season": "2013",
                },
                {
                    "fencer_id": "fencer-1",
                    "from_country": "France",
                    "to_country": "Germany",
                    "source": "results_same_season",
                    "confirmed": False,
                    "season": "2014",
                },
            ],
        }
    )

    summary = enrich_nationality_history(
        client=client,
        bindings=TIMED_BINDINGS,
        log_run=False,
        update_state=False,
        updated_at="2026-06-01T00:00:00+00:00",
    )

    assert summary == {
        "histories_found": 1,
        "fencers_matched": 2,
        "written": 2,
        "failed": 0,
        "skipped": 0,
    }
    assert {update["id"] for update in client.updates} == {"fencer-1", "fencer-2"}
    first_payload = next(update["payload"] for update in client.updates if update["id"] == "fencer-1")
    assert first_payload["metadata"]["existing"] == "keep"
    assert first_payload["metadata"]["nationality_history"][0]["country"] == "Italy"
    assert first_payload["metadata"]["nationality_history"][1]["country"] == "France"
    assert first_payload["metadata"]["nationality_history_source"] == "wikidata"
    assert first_payload["metadata"]["nationality_history_updated_at"] == "2026-06-01T00:00:00+00:00"
    assert first_payload["metadata"]["nationality_history_transfer_check"] == {
        "source": "fs_fencer_transfers",
        "checked": 2,
        "matched": 1,
        "not_matched": 1,
        "conflicts": [
            {
                "from_country": "France",
                "to_country": "Germany",
                "season": "2014",
                "source": "results_same_season",
                "confirmed": False,
            }
        ],
    }


def test_enrich_nationality_history_treats_missing_optional_transfer_table_as_nonfatal():
    from enrich_nationality_history import enrich_nationality_history

    client = FakeSupabase(
        {
            "fs_fencers": [
                {
                    "id": "fencer-1",
                    "fie_id": "100",
                    "name": "Transfer Fencer",
                    "country": "Italy",
                    "metadata": {},
                }
            ],
            "fs_fencer_identities": [],
            "fs_fencer_transfers": [],
        },
        fail_selects={"fs_fencer_transfers"},
    )

    summary = enrich_nationality_history(
        client=client,
        bindings=TIMED_BINDINGS,
        log_run=False,
        update_state=False,
        updated_at="2026-06-01T00:00:00+00:00",
    )

    assert summary["written"] == 1
    metadata = client.updates[0]["payload"]["metadata"]
    assert "nationality_history_transfer_check" not in metadata


def test_sparql_query_uses_p27_statement_qualifiers():
    from enrich_nationality_history import build_sparql_query

    query = build_sparql_query(limit=100, offset=0)

    assert "?athlete wdt:P27 ?country" in query
    assert "?athlete p:P27 ?statement" in query
    assert "pq:P580 ?start_time" in query
    assert "pq:P582 ?end_time" in query

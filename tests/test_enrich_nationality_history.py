import os
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def wikidata_binding(
    *,
    athlete="QTRANSFER",
    name="Transfer Fencer",
    fie_id="100",
    statement="QTRANSFER-1",
    country_id="Q38",
    country="Italy",
    claim_property="P27",
    country_code="ITA",
    start_time=None,
    end_time=None,
    point_in_time=None,
    team_id=None,
    team=None,
):
    binding = {
        "athlete": {"value": f"http://www.wikidata.org/entity/{athlete}"},
        "athleteLabel": {"value": name},
        "statement": {"value": f"http://www.wikidata.org/entity/statement/{statement}"},
        "claim_property": {"value": f"http://www.wikidata.org/entity/{claim_property}"},
        "country": {"value": f"http://www.wikidata.org/entity/{country_id}"},
        "countryLabel": {"value": country},
        "country_code": {"value": country_code},
    }
    if fie_id:
        binding["fie_id"] = {"value": fie_id}
    if start_time:
        binding["start_time"] = {"value": start_time}
    if end_time:
        binding["end_time"] = {"value": end_time}
    if point_in_time:
        binding["point_in_time"] = {"value": point_in_time}
    if team_id:
        binding["team"] = {"value": f"http://www.wikidata.org/entity/{team_id}"}
    if team:
        binding["teamLabel"] = {"value": team}
    return binding


TIMED_BINDINGS = [
    wikidata_binding(
        statement="QTRANSFER-IT",
        country_id="Q38",
        country="Italy",
        claim_property="P27",
        country_code="ITA",
        start_time="+2008-01-01T00:00:00Z",
        end_time="+2012-12-31T00:00:00Z",
    ),
    wikidata_binding(
        statement="QTRANSFER-FR",
        country_id="Q142",
        country="France",
        claim_property="P1532",
        country_code="FRA",
        start_time="+2013-01-01T00:00:00Z",
    ),
]


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
        self.on_conflict = None

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

    def upsert(self, payload, on_conflict):
        self.operation = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        if self.name in self.client.fail_selects and self.operation == "select":
            raise RuntimeError(f"{self.name} unavailable")
        if self.operation == "select":
            rows = self.client.tables.get(self.name, [])
            return FakeResult(rows[self.range_start : cast(int, self.range_end) + 1])
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
                    row.update(cast(dict[str, Any], self.payload))
            return FakeResult([])
        if self.operation == "upsert":
            payload = self.payload if isinstance(self.payload, list) else [self.payload]
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": payload,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult([])
        raise AssertionError(f"unexpected operation {self.operation} on {self.name}")


class FakeSupabase:
    def __init__(self, tables, fail_selects=None):
        self.tables = tables
        self.fail_selects = set(fail_selects or [])
        self.selects = []
        self.updates = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_migration_defines_history_and_discrepancy_storage():
    migration = Path("supabase/migrations/20260602_nationality_history.sql")

    sql = migration.read_text(encoding="utf-8").casefold()
    normalized = " ".join(sql.split())

    assert "create table if not exists public.fs_fencer_nationality_history" in normalized
    for column in (
        "fencer_id uuid not null references public.fs_fencers(id)",
        "fencer_identity_id uuid references public.fs_fencer_identities(id)",
        "country_code text",
        "start_date text",
        "end_date text",
        "point_in_time text",
        "source text not null",
        "confidence numeric not null",
        "metadata jsonb not null default '{}'::jsonb",
    ):
        assert column in normalized
    assert "unique (history_key)" in normalized
    assert "check (confidence >= 0 and confidence <= 1)" in normalized
    assert "alter table public.fs_fencer_nationality_history enable row level security" in normalized

    assert "create table if not exists public.fs_fencer_nationality_discrepancies" in normalized
    assert "discrepancy_key text not null" in normalized
    assert "discrepancy_type text not null" in normalized
    assert "severity text not null" in normalized
    assert "unique (discrepancy_key)" in normalized
    assert "alter table public.fs_fencer_nationality_discrepancies enable row level security" in normalized


def test_build_nationality_histories_parses_qualifiers_sources_and_codes():
    from enrich_nationality_history import build_nationality_histories

    bindings = [
        *TIMED_BINDINGS,
        wikidata_binding(
            statement="QTRANSFER-TEAM",
            country_id="Q142",
            country="France",
            claim_property="P54",
            country_code="FRA",
            point_in_time="+2014-06-01T00:00:00Z",
            team_id="QFRTEAM",
            team="France national fencing team",
        ),
    ]

    histories = build_nationality_histories(bindings)

    assert len(histories) == 1
    items = histories[0]["nationality_history"]
    assert items[0] == {
        "country": "Italy",
        "country_code": "ITA",
        "country_id": "Q38",
        "start_date": "2008-01-01",
        "end_date": "2012-12-31",
        "sequence_index": 0,
        "source": "wikidata_citizenship",
        "confidence": 0.95,
        "claim_property": "P27",
        "wikidata_statement_id": "QTRANSFER-IT",
    }
    assert items[1]["country"] == "France"
    assert items[1]["country_code"] == "FRA"
    assert items[1]["source"] == "wikidata_country_for_sport"
    assert items[1]["claim_property"] == "P1532"
    assert items[1]["confidence"] == 0.85
    assert items[2]["source"] == "wikidata_national_team"
    assert items[2]["point_in_time"] == "2014-06-01"
    assert items[2]["metadata"]["team"] == "France national fencing team"


def test_enrich_upserts_history_and_discrepancies_without_clobbering_current_country():
    from enrich_nationality_history import enrich_nationality_history

    client = FakeSupabase(
        {
            "fs_fencers": [
                {
                    "id": "fencer-1",
                    "fie_id": "100",
                    "name": "Transfer Fencer",
                    "country": "Germany",
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
                    "metadata": {"evidence": "ranking country changed"},
                },
                {
                    "fencer_id": "fencer-1",
                    "from_country": "France",
                    "to_country": "Germany",
                    "source": "results_same_season",
                    "confirmed": False,
                    "season": "2014",
                    "metadata": {"evidence": "result country changed"},
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

    assert summary["histories_found"] == 1
    assert summary["fencers_matched"] == 2
    assert all("country" not in update["payload"] for update in client.updates)

    history_upsert = next(call for call in client.upserts if call["table"] == "fs_fencer_nationality_history")
    assert history_upsert["on_conflict"] == "history_key"
    assert len(history_upsert["rows"]) == 4
    first_row = next(
        row
        for row in history_upsert["rows"]
        if row["fencer_id"] == "fencer-1" and row["country_code"] == "ITA"
    )
    assert first_row["fencer_identity_id"] == "identity-1"
    assert first_row["wikidata_id"] == "QTRANSFER"
    assert first_row["source"] == "wikidata_citizenship"
    assert first_row["start_date"] == "2008-01-01"
    assert first_row["end_date"] == "2012-12-31"
    assert first_row["confidence"] == 0.95
    assert first_row["metadata"]["source_url"] == "https://www.wikidata.org/wiki/QTRANSFER"

    discrepancy_upsert = next(
        call for call in client.upserts if call["table"] == "fs_fencer_nationality_discrepancies"
    )
    assert discrepancy_upsert["on_conflict"] == "discrepancy_key"
    discrepancy_types = {row["discrepancy_type"] for row in discrepancy_upsert["rows"]}
    assert "transfer_country_not_in_wikidata" in discrepancy_types
    assert "current_country_not_in_wikidata" in discrepancy_types
    transfer_row = next(
        row
        for row in discrepancy_upsert["rows"]
        if row["discrepancy_type"] == "transfer_country_not_in_wikidata"
    )
    assert transfer_row["source"] == "fs_fencer_transfers"
    assert transfer_row["metadata"]["transfer"]["to_country"] == "Germany"


def test_ambiguous_unqualified_claims_emit_low_confidence_discrepancy():
    from enrich_nationality_history import enrich_nationality_history

    bindings = [
        wikidata_binding(
            athlete="QAMB",
            name="Ambiguous Fencer",
            fie_id="200",
            statement="QAMB-CAN",
            country_id="Q16",
            country="Canada",
            claim_property="P27",
            country_code="CAN",
        ),
        wikidata_binding(
            athlete="QAMB",
            name="Ambiguous Fencer",
            fie_id="200",
            statement="QAMB-USA",
            country_id="Q30",
            country="United States of America",
            claim_property="P27",
            country_code="USA",
        ),
    ]
    client = FakeSupabase(
        {
            "fs_fencers": [
                {
                    "id": "fencer-amb",
                    "fie_id": "200",
                    "name": "Ambiguous Fencer",
                    "country": "Canada",
                    "metadata": {"wikidata_id": "QAMB"},
                }
            ],
            "fs_fencer_identities": [],
            "fs_fencer_transfers": [],
        }
    )

    enrich_nationality_history(
        client=client,
        bindings=bindings,
        log_run=False,
        update_state=False,
        updated_at="2026-06-01T00:00:00+00:00",
    )

    history_rows = next(call for call in client.upserts if call["table"] == "fs_fencer_nationality_history")[
        "rows"
    ]
    assert {row["country_code"] for row in history_rows} == {"CAN", "USA"}
    assert {row["confidence"] for row in history_rows} == {0.55}
    discrepancy_rows = next(
        call for call in client.upserts if call["table"] == "fs_fencer_nationality_discrepancies"
    )["rows"]
    assert any(row["discrepancy_type"] == "ambiguous_wikidata_claims" for row in discrepancy_rows)


def test_country_code_normalization_preserves_source_and_historical_codes():
    from enrich_nationality_history import normalize_country_code

    assert normalize_country_code("United States of America") == "USA"
    assert normalize_country_code("Great Britain") == "GBR"
    assert normalize_country_code("Soviet Union") == "URS"
    assert normalize_country_code("Russia", source_code="ROC") == "ROC"
    assert normalize_country_code("France", source_code="fra") == "FRA"


def test_sparql_query_fetches_citizenship_sport_country_team_and_time_qualifiers():
    from enrich_nationality_history import build_sparql_query

    query = build_sparql_query(limit=100, offset=0)

    assert "?athlete p:P27 ?statement" in query
    assert "?athlete p:P1532 ?statement" in query
    assert "?athlete p:P54 ?statement" in query
    assert "pq:P580 ?start_time" in query
    assert "pq:P582 ?end_time" in query
    assert "pq:P585 ?point_in_time" in query
    assert "wdt:P984 ?country_code" in query

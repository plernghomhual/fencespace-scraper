import os
import sys
from typing import Any

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ENTITY_FIXTURE = {
    "entities": {
        "Q312123": {
            "labels": {"en": {"value": "Sample Fencer"}},
            "claims": {
                "P69": [
                    {
                        "id": "Q312123$education-preferred",
                        "rank": "preferred",
                        "mainsnak": {
                            "snaktype": "value",
                            "datavalue": {
                                "value": {
                                    "entity-type": "item",
                                    "numeric-id": 13371,
                                    "id": "Q13371",
                                }
                            },
                        },
                    },
                    {
                        "id": "Q312123$education-normal",
                        "rank": "normal",
                        "mainsnak": {
                            "snaktype": "value",
                            "datavalue": {
                                "value": {
                                    "entity-type": "item",
                                    "numeric-id": 49108,
                                    "id": "Q49108",
                                }
                            },
                        },
                    },
                    {
                        "id": "Q312123$education-deprecated",
                        "rank": "deprecated",
                        "mainsnak": {
                            "snaktype": "value",
                            "datavalue": {
                                "value": {
                                    "entity-type": "item",
                                    "numeric-id": 999999,
                                    "id": "Q999999",
                                }
                            },
                        },
                    },
                    {
                        "id": "Q312123$education-no-value",
                        "rank": "normal",
                        "mainsnak": {"snaktype": "novalue"},
                    },
                ],
                "P106": [
                    {
                        "id": "Q312123$occupation-normal",
                        "rank": "normal",
                        "mainsnak": {
                            "snaktype": "value",
                            "datavalue": {
                                "value": {
                                    "entity-type": "item",
                                    "numeric-id": 10841764,
                                    "id": "Q10841764",
                                }
                            },
                        },
                    }
                ],
            },
        },
        "Q13371": {"labels": {"en": {"value": "Harvard University"}}},
        "Q49108": {"labels": {"fr": {"value": "Université de Notre Dame"}}},
        "Q10841764": {"labels": {"en": {"value": "fencer"}}},
    }
}


SPARQL_FIXTURE = {
    "results": {
        "bindings": [
            {
                "athlete": {"value": "http://www.wikidata.org/entity/Q312123"},
                "statement": {
                    "value": "http://www.wikidata.org/entity/statement/Q312123-education-normal"
                },
                "property": {"value": "http://www.wikidata.org/entity/P69"},
                "value": {"value": "http://www.wikidata.org/entity/Q13371"},
                "valueLabel": {"value": "Harvard University"},
                "rank": {"value": "http://wikiba.se/ontology#NormalRank"},
            },
            {
                "athlete": {"value": "http://www.wikidata.org/entity/Q312123"},
                "statement": {
                    "value": "http://www.wikidata.org/entity/statement/Q312123-occupation-preferred"
                },
                "property": {"value": "http://www.wikidata.org/entity/P106"},
                "value": {"value": "http://www.wikidata.org/entity/Q10841764"},
                "valueLabel": {"value": "fencer"},
                "rank": {"value": "http://wikiba.se/ontology#PreferredRank"},
            },
            {
                "athlete": {"value": "http://www.wikidata.org/entity/Q312123"},
                "statement": {
                    "value": "http://www.wikidata.org/entity/statement/Q312123-education-old"
                },
                "property": {"value": "http://www.wikidata.org/entity/P69"},
                "value": {"value": "http://www.wikidata.org/entity/Q999999"},
                "valueLabel": {"value": "Old School"},
                "rank": {"value": "http://wikiba.se/ontology#DeprecatedRank"},
            },
        ]
    }
}


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.filters = []
        self.limit_value = None
        self.range_bounds = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def not_(self, column, operator, value):
        self.filters.append(("not", column, operator, value))
        return self

    def order(self, column):
        self.order_column = column
        return self

    def range(self, start, end):
        self.range_bounds = (start, end)
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        if self.operation == "update":
            self.client.updates.append(
                {"table": self.name, "payload": self.payload, "filters": self.filters}
            )
            return FakeResult([])
        if self.name == "fs_fencers":
            self.client.selects.append(
                {
                    "columns": self.columns,
                    "filters": self.filters,
                    "range": self.range_bounds,
                    "limit": self.limit_value,
                }
            )
            return FakeResult(self.client.fencers)
        return FakeResult([])


class FakeSupabase:
    def __init__(self, fencers):
        self.fencers = fencers
        self.selects = []
        self.updates = []

    def table(self, name):
        return FakeTable(self, name)


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_parse_entity_claims_normalizes_sourced_education_and_occupation():
    import enrich_education as edu

    claims = edu.parse_entity_claims("Q312123", ENTITY_FIXTURE)

    assert [row["label"] for row in claims["education"]] == [
        "Harvard University",
        "Université de Notre Dame",
    ]
    assert claims["education"][0] == {
        "id": "Q13371",
        "label": "Harvard University",
        "property": "P69",
        "claim_id": "Q312123$education-preferred",
        "rank": "preferred",
        "source_url": "https://www.wikidata.org/wiki/Q312123#P69",
        "confidence": 0.95,
    }
    assert claims["education"][1]["confidence"] == 0.9
    assert claims["occupation"] == [
        {
            "id": "Q10841764",
            "label": "fencer",
            "property": "P106",
            "claim_id": "Q312123$occupation-normal",
            "rank": "normal",
            "source_url": "https://www.wikidata.org/wiki/Q312123#P106",
            "confidence": 0.9,
        }
    ]


def test_parse_entity_claims_skips_deprecated_no_value_and_falls_back_to_qid_label():
    import enrich_education as edu

    entity = {
        "entities": {
            "Q1": {
                "claims": {
                    "P69": [
                        {
                            "id": "Q1$deprecated",
                            "rank": "deprecated",
                            "mainsnak": {
                                "snaktype": "value",
                                "datavalue": {"value": {"id": "Q2"}},
                            },
                        },
                        {"id": "Q1$novalue", "rank": "normal", "mainsnak": {"snaktype": "novalue"}},
                        {
                            "id": "Q1$missing-label",
                            "rank": "normal",
                            "mainsnak": {
                                "snaktype": "value",
                                "datavalue": {"value": {"numeric-id": 3}},
                            },
                        },
                    ],
                    "P106": [],
                },
            },
            "Q2": {"labels": {"en": {"value": "Deprecated School"}}},
            "Q3": {"labels": {}},
        }
    }

    claims = edu.parse_entity_claims("Q1", entity)

    assert claims["education"] == [
        {
            "id": "Q3",
            "label": "Q3",
            "property": "P69",
            "claim_id": "Q1$missing-label",
            "rank": "normal",
            "source_url": "https://www.wikidata.org/wiki/Q1#P69",
            "confidence": 0.9,
        }
    ]
    assert claims["occupation"] == []


def test_parse_sparql_claim_bindings_filters_deprecated_ranks():
    import enrich_education as edu

    claims = edu.parse_sparql_claim_bindings(SPARQL_FIXTURE["results"]["bindings"])

    assert claims == {
        "Q312123": {
            "education": [
                {
                    "id": "Q13371",
                    "label": "Harvard University",
                    "property": "P69",
                    "claim_id": "Q312123-education-normal",
                    "rank": "normal",
                    "source_url": "https://www.wikidata.org/wiki/Q312123#P69",
                    "confidence": 0.9,
                }
            ],
            "occupation": [
                {
                    "id": "Q10841764",
                    "label": "fencer",
                    "property": "P106",
                    "claim_id": "Q312123-occupation-preferred",
                    "rank": "preferred",
                    "source_url": "https://www.wikidata.org/wiki/Q312123#P106",
                    "confidence": 0.95,
                }
            ],
        }
    }


def test_fetch_entity_claims_uses_wikidata_entity_api_and_rate_limit_session():
    import enrich_education as edu

    session = FakeSession(FakeResponse(payload=ENTITY_FIXTURE))

    claims = edu.fetch_entity_claims("Q312123", session=session)

    assert claims["education"][0]["id"] == "Q13371"
    assert session.calls[0][0] == "https://www.wikidata.org/wiki/Special:EntityData/Q312123.json"
    assert session.calls[0][1]["timeout"] == 20
    assert "User-Agent" in session.calls[0][1]["headers"]


def test_build_update_payload_merges_metadata_and_records_missing_claims():
    import enrich_education as edu

    row = {"metadata": {"wikidata_id": "Q1", "existing": True}}
    payload = edu.build_update_payload(
        row,
        {"education": [], "occupation": []},
        attempted_at="2026-06-02T12:00:00+00:00",
    )

    assert payload == {
        "metadata": {
            "wikidata_id": "Q1",
            "existing": True,
            "education": [],
            "occupation": [],
            "education_occupation_scrape": {
                "attempted_at": "2026-06-02T12:00:00+00:00",
                "status": "no_claims",
                "source": "wikidata",
                "fields_found": [],
                "errors": [],
            },
        }
    }


def test_run_enrichment_missing_credentials_is_no_network_dry_run():
    import enrich_education as edu

    def forbidden_fetcher(qid):
        raise AssertionError(f"network should not be called for {qid}")

    summary = edu.run_enrichment(
        client=None,
        get_client=lambda: None,
        claim_fetcher=forbidden_fetcher,
        log_run=False,
        update_state=False,
    )

    assert summary["dry_run"] is True
    assert summary["reason"] == "missing_supabase_credentials"
    assert summary["queried"] == 0
    assert summary["written"] == 0
    assert summary["failed"] == 0


def test_run_enrichment_updates_fencers_with_wikidata_claim_payload(monkeypatch):
    import enrich_education as edu

    client = FakeSupabase(
        [
            {
                "id": "fencer-a",
                "name": "A. Fencer",
                "metadata": {"wikidata_id": "Q312123", "existing": True},
            }
        ]
    )
    state_updates = []
    sleeps = []

    monkeypatch.setattr(edu, "get_state", lambda source, key: {"offset": 0})
    monkeypatch.setattr(edu, "set_state", lambda source, key, value: state_updates.append((source, key, value)))
    monkeypatch.setattr(edu.time, "sleep", lambda delay: sleeps.append(delay))

    summary = edu.run_enrichment(
        client=client,
        claim_fetcher=lambda qid: edu.parse_entity_claims(qid, ENTITY_FIXTURE),
        delay=0.25,
        page_size=10,
        log_run=False,
        update_state=True,
        now=lambda: "2026-06-02T12:00:00+00:00",
    )

    assert summary["queried"] == 1
    assert summary["written"] == 1
    assert summary["failed"] == 0
    assert client.selects[0]["filters"] == [("not", "metadata->>wikidata_id", "is", "null")]
    assert client.updates[0]["table"] == "fs_fencers"
    assert client.updates[0]["filters"] == [("id", "fencer-a")]
    metadata = client.updates[0]["payload"]["metadata"]
    assert metadata["existing"] is True
    assert metadata["education"][0]["claim_id"] == "Q312123$education-preferred"
    assert metadata["occupation"][0]["source_url"] == "https://www.wikidata.org/wiki/Q312123#P106"
    assert state_updates[-1][0] == "enrich_education"
    assert state_updates[-1][1] == "last_summary"
    assert sleeps == [0.25]


def test_run_enrichment_network_errors_do_not_abort(monkeypatch):
    import enrich_education as edu

    client = FakeSupabase([{"id": "fencer-a", "metadata": {"wikidata_id": "Q1"}}])
    monkeypatch.setattr(edu.time, "sleep", lambda delay: None)

    def failing_fetcher(qid):
        raise requests.ConnectionError("network unavailable")

    summary = edu.run_enrichment(
        client=client,
        claim_fetcher=failing_fetcher,
        delay=0,
        log_run=False,
        update_state=False,
    )

    assert summary["queried"] == 1
    assert summary["written"] == 0
    assert summary["failed"] == 1
    assert "network unavailable" in summary["errors"][0]
    assert client.updates == []


def test_dry_run_with_client_emits_payload_without_database_update(monkeypatch):
    import enrich_education as edu

    client = FakeSupabase([{"id": "fencer-a", "metadata": {"wikidata_id": "Q312123"}}])
    emitted: list[Any] = []
    monkeypatch.setattr(edu.time, "sleep", lambda delay: None)

    summary = edu.run_enrichment(
        client=client,
        claim_fetcher=lambda qid: edu.parse_entity_claims(qid, ENTITY_FIXTURE),
        dry_run=True,
        delay=0,
        log_run=False,
        update_state=False,
        emit=emitted.append,
    )

    assert summary["dry_run"] is True
    assert summary["written"] == 0
    assert summary["emitted"] == 1
    assert client.updates == []
    assert '"wikidata_id": "Q312123"' in emitted[0]
    assert '"education"' in emitted[0]

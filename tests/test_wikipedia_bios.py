from typing import Any, cast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"Unexpected request: {url}")
        return self.responses.pop(0)


def wikidata_entity(qid, *, title="Lee Kiefer", birth_time=None, birth_place_qid=None):
    claims = {}
    if birth_time:
        claims["P569"] = [
            {
                "mainsnak": {
                    "datavalue": {
                        "value": {
                            "time": birth_time,
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        }
                    }
                }
            }
        ]
    if birth_place_qid:
        claims["P19"] = [
            {
                "mainsnak": {
                    "datavalue": {
                        "value": {
                            "entity-type": "item",
                            "numeric-id": int(birth_place_qid.removeprefix("Q")),
                            "id": birth_place_qid,
                        }
                    }
                }
            }
        ]
    return {
        "entities": {
            qid: {
                "claims": claims,
                "sitelinks": {"enwiki": {"title": title}},
            }
        }
    }


def place_entity(qid, label):
    return {"entities": {qid: {"labels": {"en": {"language": "en", "value": label}}}}}


def page_summary(title="Lee Kiefer", extract=None):
    return {
        "type": "standard",
        "title": title,
        "extract": extract or "Lee Kiefer is an American right-handed foil fencer.",
        "content_urls": {
            "desktop": {"page": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"}
        },
    }


def test_parse_wikipedia_summary_populates_new_bio_fields():
    from scrape_wikipedia_bios import parse_wikipedia_summary

    result = parse_wikipedia_summary(
        {
            "type": "standard",
            "extract": (
                "Lee Kiefer is an American right-handed foil fencer.\n\n"
                "She won Olympic gold."
            ),
            "content_urls": {
                "desktop": {"page": "https://en.wikipedia.org/wiki/Lee_Kiefer"}
            },
        }
    )

    assert result == {
        "bio": "Lee Kiefer is an American right-handed foil fencer.",
        "bio_text": "Lee Kiefer is an American right-handed foil fencer.",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Lee_Kiefer",
        "bio_source": "https://en.wikipedia.org/wiki/Lee_Kiefer",
    }


def test_parse_wikipedia_summary_skips_missing_and_disambiguation_payloads():
    from scrape_wikipedia_bios import parse_wikipedia_summary

    assert parse_wikipedia_summary(None) is None
    assert parse_wikipedia_summary({"type": "disambiguation", "extract": "Name list"}) is None
    assert parse_wikipedia_summary({"type": "standard", "extract": ""}) is None


def test_parse_wikidata_birth_claims_normalizes_full_dates_and_place_labels():
    from scrape_wikipedia_bios import fetch_wikidata_birth_details

    session = FakeSession([FakeResponse(place_entity("Q37320", "Cleveland, Ohio"))])
    entity = wikidata_entity(
        "Q1657692",
        birth_time="+1994-06-15T00:00:00Z",
        birth_place_qid="Q37320",
    )["entities"]["Q1657692"]

    assert fetch_wikidata_birth_details(
        entity,
        session=session,
        sleep_func=lambda _: None,
    ) == {"birth_date": "1994-06-15", "birth_place": "Cleveland, Ohio"}


def test_parse_wikidata_birth_claims_preserves_partial_dates_as_null():
    from scrape_wikipedia_bios import parse_wikidata_time_value

    assert parse_wikidata_time_value({"time": "+1985-00-00T00:00:00Z", "precision": 9}) is None
    assert parse_wikidata_time_value({"time": "+1985-05-00T00:00:00Z", "precision": 10}) is None
    assert parse_wikidata_time_value({"time": "+1985-05-03T00:00:00Z", "precision": 11}) == "1985-05-03"


def test_fetch_wikipedia_enrichment_prefers_wikidata_id_over_existing_title():
    from scrape_wikipedia_bios import fetch_wikipedia_enrichment

    session = FakeSession(
        [
            FakeResponse(wikidata_entity("Q1657692", title="Correct Page")),
            FakeResponse(page_summary(title="Correct Page")),
            FakeResponse({"parse": {"text": {"*": ""}}}),
        ]
    )

    result = fetch_wikipedia_enrichment(
        {
            "metadata": {
                "wikidata_id": "Q1657692",
                "wikipedia_title": "Wrong Page",
            },
            "country": "USA",
        },
        session=session,
        sleep_func=lambda _: None,
    )

    result = cast(dict[str, Any], result)
    assert result["title"] == "Correct Page"
    assert [call["url"] for call in session.calls] == [
        "https://www.wikidata.org/wiki/Special:EntityData/Q1657692.json",
        "https://en.wikipedia.org/api/rest_v1/page/summary/Correct%20Page",
        "https://en.wikipedia.org/w/api.php",
    ]


def test_fetch_wikipedia_enrichment_uses_explicit_wikipedia_url_without_wikidata_id():
    from scrape_wikipedia_bios import fetch_wikipedia_enrichment

    session = FakeSession(
        [
            FakeResponse(page_summary(title="Lee Kiefer")),
            FakeResponse({"parse": {"text": {"*": ""}}}),
        ]
    )

    result = cast(dict[str, Any], fetch_wikipedia_enrichment(
        {"wikipedia_url": "https://en.wikipedia.org/wiki/Lee_Kiefer"},
        session=session,
        sleep_func=lambda _: None,
    ))

    assert result["title"] == "Lee Kiefer"
    assert result["bio_text"] == "Lee Kiefer is an American right-handed foil fencer."
    assert [call["url"] for call in session.calls] == [
        "https://en.wikipedia.org/api/rest_v1/page/summary/Lee%20Kiefer",
        "https://en.wikipedia.org/w/api.php",
    ]


def test_fetch_wikipedia_enrichment_skips_ambiguous_name_without_confident_source():
    from scrape_wikipedia_bios import fetch_wikipedia_enrichment

    session = FakeSession([])

    assert fetch_wikipedia_enrichment(
        {"name": "Lee Kiefer", "country": "USA"},
        session=session,
        sleep_func=lambda _: None,
    ) is None
    assert session.calls == []


class FakeUpdateQuery:
    def __init__(self):
        self.updates = []
        self.pending_payload = None

    def update(self, payload):
        self.pending_payload = payload
        return self

    def eq(self, column, value):
        self.updates.append((self.pending_payload, column, value))
        return self

    def execute(self):
        return type("Result", (), {"data": []})()


class FakeClient:
    def __init__(self):
        self.query = FakeUpdateQuery()

    def table(self, name):
        assert name == "fs_fencers"
        return self.query


def test_process_fencer_no_network_dry_run_updates_new_bio_fields(monkeypatch):
    import scrape_wikipedia_bios

    client = FakeClient()
    monkeypatch.setattr(scrape_wikipedia_bios, "supabase", client)
    session = FakeSession(
        [
            FakeResponse(
                wikidata_entity(
                    "Q1657692",
                    birth_time="+1994-06-15T00:00:00Z",
                    birth_place_qid="Q37320",
                )
            ),
            FakeResponse(place_entity("Q37320", "Cleveland, Ohio")),
            FakeResponse(page_summary()),
            FakeResponse({"parse": {"text": {"*": ""}}}),
        ]
    )

    status = scrape_wikipedia_bios.process_fencer(
        {
            "id": "fencer-1",
            "name": "Lee Kiefer",
            "country": "USA",
            "metadata": {"wikidata_id": "Q1657692"},
            "birth_place": None,
            "bio_source": None,
            "bio_text": None,
            "wikipedia_url": None,
        },
        session=session,
        sleep_func=lambda _: None,
    )

    assert status == "written"
    assert client.query.updates == [
        (
            {
                "bio_source": "https://en.wikipedia.org/wiki/Lee_Kiefer",
                "bio_text": "Lee Kiefer is an American right-handed foil fencer.",
                "wikipedia_url": "https://en.wikipedia.org/wiki/Lee_Kiefer",
                "birth_place": "Cleveland, Ohio",
            },
            "id",
            "fencer-1",
        )
    ]


def test_build_update_payload_does_not_overwrite_richer_existing_bio():
    from scrape_wikipedia_bios import build_update_payload

    fencer = {
        "bio": "Longer editor-written biography with competition history and medals.",
        "birth_date": "1994-06-15",
        "birth_place": "Cleveland, Ohio, U.S.",
        "bio_source": "manual",
    }
    enrichment = {
        "bio_text": "Lee Kiefer is a fencer.",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Lee_Kiefer",
        "birth_date": "1994-06-15",
        "birth_place": "Cleveland, Ohio",
    }

    assert build_update_payload(fencer, enrichment) == {}

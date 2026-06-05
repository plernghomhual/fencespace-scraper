from typing import Any, cast
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.url = "https://example.test/response"

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


def test_language_candidates_prefers_national_language_then_english():
    from scrape_wikipedia_bios import language_candidates

    assert language_candidates({"country": "FRA"}) == ["fr", "en"]
    assert language_candidates({"nationality": "Italy"}) == ["it", "en"]
    assert language_candidates({"country": "United States"}) == ["en"]
    assert language_candidates({"country": "UNKNOWN"}) == ["en"]


def test_normalize_wikidata_id_accepts_urls_qids_and_numbers():
    from scrape_wikipedia_bios import normalize_wikidata_id

    assert normalize_wikidata_id("Q1657692") == "Q1657692"
    assert normalize_wikidata_id("1657692") == "Q1657692"
    assert normalize_wikidata_id("https://www.wikidata.org/wiki/Q1657692") == "Q1657692"
    assert normalize_wikidata_id(None) is None
    assert normalize_wikidata_id("not-a-qid") is None


def test_parse_infobox_details_extracts_birth_place_nickname_height_weight():
    from scrape_wikipedia_bios import parse_infobox_details

    html = """
    <table class="infobox biography vcard">
      <tr>
        <th class="infobox-label">Nickname(s)</th>
        <td class="infobox-data nickname">The Baron</td>
      </tr>
      <tr>
        <th class="infobox-label">Born</th>
        <td class="infobox-data">June 15, 1994<br/>Cleveland, Ohio, U.S.</td>
      </tr>
      <tr>
        <th class="infobox-label">Height</th>
        <td class="infobox-data">1.63 m (5 ft 4 in)</td>
      </tr>
      <tr>
        <th class="infobox-label">Weight</th>
        <td class="infobox-data">50 kg (110 lb)</td>
      </tr>
    </table>
    """

    assert parse_infobox_details(html) == {
        "birth_place": "Cleveland, Ohio, U.S.",
        "nickname": "The Baron",
        "height": "1.63 m (5 ft 4 in)",
        "weight": "50 kg (110 lb)",
    }


def test_parse_infobox_details_combines_linked_birthplace_fragments():
    from scrape_wikipedia_bios import parse_infobox_details

    html = """
    <table class="infobox">
      <tr>
        <th class="infobox-label">Born</th>
        <td class="infobox-data">
          (<span>1994-06-15</span>)<br/>
          June 15, 1994<br/>
          (age 31)<br/>
          <a>Cleveland, Ohio</a><span>, U.S.</span>
        </td>
      </tr>
    </table>
    """

    assert parse_infobox_details(html)["birth_place"] == "Cleveland, Ohio, U.S."


def test_extract_birth_place_from_bio_text_handles_common_wikipedia_sentence():
    from scrape_wikipedia_bios import extract_birth_place_from_bio_text

    extract = (
        "Example Fencer (born 12 March 1990 in Paris, France) is a French "
        "right-handed foil fencer."
    )

    assert extract_birth_place_from_bio_text(extract) == "Paris, France"


def test_fetch_wikipedia_enrichment_falls_back_to_english_summary():
    from scrape_wikipedia_bios import fetch_wikipedia_enrichment

    session = FakeSession(
        [
            FakeResponse(
                {
                    "entities": {
                        "Q1657692": {
                            "sitelinks": {
                                "frwiki": {"title": "Lee Kiefer"},
                                "enwiki": {"title": "Lee Kiefer"},
                            }
                        }
                    }
                }
            ),
            FakeResponse({"detail": "Not found"}, status_code=404),
            FakeResponse(
                {
                    "type": "standard",
                    "title": "Lee Kiefer",
                    "extract": (
                        "Lee Kiefer is an American right-handed foil fencer.\n\n"
                        "She is a three-time Olympic champion."
                    ),
                    "content_urls": {
                        "desktop": {
                            "page": "https://en.wikipedia.org/wiki/Lee_Kiefer"
                        }
                    },
                    "page_url": "https://en.wikipedia.org/wiki/Lee_Kiefer",
                }
            ),
            FakeResponse({"parse": {"text": {"*": ""}}}),
        ]
    )

    result = fetch_wikipedia_enrichment(
        {"metadata": {"wikidata_id": "Q1657692"}, "country": "FRA"},
        session=session,
        sleep_func=lambda _: None,
    )

    result = cast(dict[str, Any], result)
    assert result["bio_text"] == "Lee Kiefer is an American right-handed foil fencer."
    assert result["wikipedia_url"] == "https://en.wikipedia.org/wiki/Lee_Kiefer"
    assert result["language"] == "en"
    assert [call["url"] for call in session.calls] == [
        "https://www.wikidata.org/wiki/Special:EntityData/Q1657692.json",
        "https://fr.wikipedia.org/api/rest_v1/page/summary/Lee%20Kiefer",
        "https://en.wikipedia.org/api/rest_v1/page/summary/Lee%20Kiefer",
        "https://en.wikipedia.org/w/api.php",
    ]


def test_fetch_wikipedia_enrichment_extracts_summary_and_infobox_fields():
    from scrape_wikipedia_bios import fetch_wikipedia_enrichment

    session = FakeSession(
        [
            FakeResponse(
                {
                    "entities": {
                        "Q229967": {
                            "sitelinks": {
                                "itwiki": {"title": "Valentina Vezzali"},
                                "enwiki": {"title": "Valentina Vezzali"},
                            }
                        }
                    }
                }
            ),
            FakeResponse(
                {
                    "type": "standard",
                    "title": "Valentina Vezzali",
                    "extract": "Maria Valentina Vezzali is an Italian politician and retired Olympic fencer.",
                    "content_urls": {
                        "desktop": {
                            "page": "https://it.wikipedia.org/wiki/Valentina_Vezzali"
                        }
                    },
                }
            ),
            FakeResponse(
                {
                    "parse": {
                        "text": {
                            "*": """
                            <table class="infobox">
                              <tr><th class="infobox-label">Nata</th>
                                  <td class="infobox-data">14 febbraio 1974<br/>Jesi, Italy</td></tr>
                              <tr><th class="infobox-label">Altezza</th>
                                  <td class="infobox-data">1.64 m</td></tr>
                              <tr><th class="infobox-label">Peso</th>
                                  <td class="infobox-data">53 kg</td></tr>
                            </table>
                            """
                        }
                    }
                }
            ),
        ]
    )

    result = cast(dict[str, Any], fetch_wikipedia_enrichment(
        {"metadata": {"wikidata_id": "Q229967"}, "country": "ITA"},
        session=session,
        sleep_func=lambda _: None,
    ))

    assert result == {
        "bio_text": "Maria Valentina Vezzali is an Italian politician and retired Olympic fencer.",
        "wikipedia_url": "https://it.wikipedia.org/wiki/Valentina_Vezzali",
        "birth_place": "Jesi, Italy",
        "height": "1.64 m",
        "weight": "53 kg",
        "language": "it",
        "title": "Valentina Vezzali",
    }


def test_build_update_payload_keeps_existing_non_null_fields():
    from scrape_wikipedia_bios import build_update_payload

    fencer = {
        "bio_text": None,
        "wikipedia_url": None,
        "birth_place": "Cleveland, Ohio, U.S.",
        "nickname": None,
        "height": None,
        "weight": "50 kg",
        "metadata": {"wikidata_id": "Q1657692"},
    }
    enrichment = {
        "bio_text": "Lee Kiefer is an American foil fencer.",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Lee_Kiefer",
        "birth_place": "Lexington, Kentucky, U.S.",
        "nickname": "Lee",
        "height": "1.63 m",
        "weight": "55 kg",
    }

    payload = build_update_payload(fencer, enrichment)

    assert payload == {
        "bio_text": "Lee Kiefer is an American foil fencer.",
        "wikipedia_url": "https://en.wikipedia.org/wiki/Lee_Kiefer",
        "nickname": "Lee",
        "height": "1.63 m",
    }


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.ops = []

    @property
    def not_(self):
        return self

    def select(self, columns):
        self.ops.append(("select", columns))
        return self

    def filter(self, column, operator, value):
        self.ops.append(("filter", column, operator, value))
        return self

    def is_(self, column, value):
        self.ops.append(("is", column, value))
        return self

    def gt(self, column, value):
        self.ops.append(("gt", column, value))
        return self

    def order(self, column):
        self.ops.append(("order", column))
        return self

    def limit(self, value):
        self.ops.append(("limit", value))
        return self

    def execute(self):
        return type("Result", (), {"data": self.rows})()


class FakeClient:
    def __init__(self, rows):
        self.query = FakeQuery(rows)

    def table(self, name):
        assert name == "fs_fencers"
        return self.query


def test_load_pending_fencers_queries_wikidata_metadata_and_cursor(monkeypatch):
    import scrape_wikipedia_bios

    client = FakeClient([{"id": "fencer-11", "metadata": {"wikidata_id": "Q1"}}])
    monkeypatch.setattr(scrape_wikipedia_bios, "supabase", client)
    monkeypatch.setattr(
        scrape_wikipedia_bios,
        "get_state",
        lambda source, key: "fencer-10",
    )

    rows = scrape_wikipedia_bios.load_pending_fencers(limit=25)

    assert rows == [{"id": "fencer-11", "metadata": {"wikidata_id": "Q1"}}]
    assert ("filter", "metadata->>wikidata_id", "not.is", "null") in client.query.ops
    assert ("is", "bio_text", "null") in client.query.ops
    assert ("gt", "id", "fencer-10") in client.query.ops
    assert ("order", "id") in client.query.ops
    assert ("limit", 25) in client.query.ops

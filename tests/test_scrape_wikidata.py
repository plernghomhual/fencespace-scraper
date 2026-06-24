import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

SAMPLE_BINDINGS = [
    {
        "athlete": {"value": "http://www.wikidata.org/entity/Q312123"},
        "athleteLabel": {"value": "Aldo Montano"},
        "fie_id": {"value": "37049"},
        "dob": {"value": "+1978-11-05T00:00:00Z"},
        "countryLabel": {"value": "Italy"},
        "imageUrl": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/Aldo_Montano.jpg"},
        "genderLabel": {"value": "male"},
    },
    {
        "athlete": {"value": "http://www.wikidata.org/entity/Q999999"},
        "athleteLabel": {"value": "Unknown Fencer"},
        "dob": {"value": "+1990-01-15T00:00:00Z"},
        "countryLabel": {"value": "France"},
    },
]


def test_parse_wikidata_binding_with_fie_id():
    from scrape_wikidata import parse_binding
    result = parse_binding(SAMPLE_BINDINGS[0])
    assert result["fie_id"] == "37049"
    assert result["date_of_birth"] == "1978-11-05"
    assert result["nationality"] == "Italy"
    assert result["headshot_url"] == "http://commons.wikimedia.org/wiki/Special:FilePath/Aldo_Montano.jpg"
    assert result["wikidata_id"] == "Q312123"
    assert result["gender"] == "Male"


def test_parse_wikidata_binding_without_fie_id():
    from scrape_wikidata import parse_binding
    result = parse_binding(SAMPLE_BINDINGS[1])
    assert result["fie_id"] is None
    assert result["date_of_birth"] == "1990-01-15"
    assert result["nationality"] == "France"


def test_parse_dob_handles_malformed():
    from scrape_wikidata import parse_wikidata_date
    assert parse_wikidata_date("+1978-11-05T00:00:00Z") == "1978-11-05"
    assert parse_wikidata_date("+1978-00-00T00:00:00Z") is None
    assert parse_wikidata_date(None) is None
    assert parse_wikidata_date("") is None


def test_parse_dob_year_only():
    from scrape_wikidata import parse_wikidata_date
    assert parse_wikidata_date("+1985-01-01T00:00:00Z") == "1985-01-01"


def test_build_update_payload_skips_none_fields():
    from scrape_wikidata import build_update_payload
    data = {
        "fie_id": "37049",
        "date_of_birth": "1978-11-05",
        "nationality": "Italy",
        "headshot_url": None,
        "gender": None,
        "wikidata_id": "Q312123",
    }
    payload = build_update_payload(data)
    assert "date_of_birth" in payload
    assert "nationality" in payload
    assert "headshot_url" not in payload
    assert "gender" not in payload
    assert payload["metadata"] == {"wikidata_id": "Q312123"}

import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "supabase" / "migrations" / "20260602_country_codes.sql"


def _migration_sql():
    return MIGRATION_PATH.read_text()


def _migration_seed_rows():
    sql = _migration_sql()
    match = re.search(r"\$country_codes\$(?P<json>.*?)\$country_codes\$", sql, re.S)
    assert match, "migration must store seed rows in a parseable $country_codes$ JSON block"
    rows = json.loads(match.group("json"))
    assert isinstance(rows, list)
    for row in rows:
        row.setdefault("aliases", [])
        row.setdefault("flag_emoji", _flag_emoji(row.get("alpha2")))
    return rows


def _row_by_alpha3(rows):
    return {row["alpha3"]: row for row in rows}


def _flag_emoji(alpha2):
    if not alpha2 or len(alpha2) != 2 or not alpha2.isalpha():
        return None
    return "".join(chr(ord(letter.upper()) + 127397) for letter in alpha2)


def test_migration_defines_country_code_table_shape():
    sql = _migration_sql()
    normalized = re.sub(r"\s+", " ", sql.lower())

    assert "create table if not exists public.fs_country_codes" in normalized
    assert re.search(r"alpha3\s+text\s+primary\s+key", normalized)

    expected_columns = {
        "alpha2": "text",
        "name": "text",
        "region": "text",
        "continent": "text",
        "flag_emoji": "text",
        "olympic_code": "text",
        "fie_code": "text",
        "aliases": "text[]",
        "latitude": "numeric",
        "longitude": "numeric",
        "updated_at": "timestamptz",
    }
    for column, column_type in expected_columns.items():
        assert re.search(rf"\b{column}\s+{re.escape(column_type)}(?=\s|,|\))", normalized), column

    assert "aliases text[] not null default '{}'::text[]" in normalized
    assert "chr(127397" in normalized
    assert "on conflict (alpha3) do update" in normalized
    assert "alter table public.fs_country_codes enable row level security" in normalized
    assert "fs_country_codes_aliases_idx" in normalized
    assert "using gin (aliases)" in normalized


def test_migration_seed_rows_cover_repo_and_historical_codes():
    rows = _row_by_alpha3(_migration_seed_rows())

    repo_codes = {
        "ARG",
        "AUS",
        "AUT",
        "BEL",
        "BRA",
        "CAN",
        "CHN",
        "DEN",
        "EGY",
        "ESP",
        "FIN",
        "FRA",
        "GBR",
        "HKG",
        "HUN",
        "ISR",
        "ITA",
        "JPN",
        "KOR",
        "NOR",
        "NZL",
        "POL",
        "ROU",
        "RUS",
        "SGP",
        "SWE",
        "UKR",
    }
    olympic_only_repo_codes = {"GER": "DEU", "NED": "NLD", "SUI": "CHE"}
    for alpha3 in repo_codes:
        assert alpha3 in rows
    for source_code, alpha3 in olympic_only_repo_codes.items():
        assert alpha3 in rows
        assert rows[alpha3]["olympic_code"] == source_code
        assert rows[alpha3]["fie_code"] == source_code

    edge_codes = {"AIN", "FIE", "AHO", "ROC", "URS", "YUG", "SCG", "TCH", "ENG", "SCO", "WAL", "NIR"}
    for alpha3 in edge_codes:
        assert alpha3 in rows

    assert rows["USA"]["alpha2"] == "US"
    assert rows["USA"]["flag_emoji"] == "\U0001f1fa\U0001f1f8"
    assert rows["CIV"]["aliases"] and "COTE DIVOIRE" in rows["CIV"]["aliases"]
    assert rows["AHO"]["name"] == "Netherlands Antilles"


def test_helper_lookup_by_alpha2_alpha3_olympic_fie_and_aliases():
    from scripts.country_codes import (
        lookup_by_alias,
        lookup_by_alpha2,
        lookup_by_alpha3,
        lookup_by_fie_code,
        lookup_by_olympic_code,
        lookup_country,
        to_alpha3,
    )

    assert lookup_by_alpha3("usa").name == "United States"
    assert lookup_by_alpha2("us").alpha3 == "USA"
    assert lookup_by_olympic_code("GER").alpha3 == "DEU"
    assert lookup_by_fie_code("NED").alpha3 == "NLD"
    assert lookup_by_alias("United States of America").alpha3 == "USA"
    assert lookup_country("Hong Kong, China").alpha3 == "HKG"
    assert lookup_country("Cote d'Ivoire").alpha3 == "CIV"
    assert lookup_country("Turkiye").alpha3 == "TUR"
    assert lookup_country("Korea").alpha3 == "KOR"
    assert lookup_country("AUST").alpha3 == "AUS"
    assert lookup_country("N.IRE").alpha3 == "NIR"
    assert lookup_country("Antillas Neerlandesas").alpha3 == "AHO"
    assert to_alpha3("_AIN") == "AIN"


def test_unknown_lookup_behavior_is_deterministic():
    from scripts.country_codes import country_display_name, lookup_country, to_alpha3

    assert lookup_country(None) is None
    assert lookup_country("") is None
    assert lookup_country("Atlantis") is None

    assert to_alpha3("ZZZ") == "ZZZ"
    assert to_alpha3("Atlantis") is None
    assert country_display_name("ZZZ") == "ZZZ"
    assert country_display_name("Atlantis") == "Atlantis"


def test_no_duplicate_codes_or_conflicting_aliases():
    from scripts.country_codes import COUNTRY_CODES, country_seed_rows

    def assert_unique(values, label):
        seen = {}
        for country in COUNTRY_CODES:
            value = getattr(country, label)
            if not value:
                continue
            assert value not in seen, f"{label} {value} used by {seen[value]} and {country.alpha3}"
            seen[value] = country.alpha3

    assert_unique(COUNTRY_CODES, "alpha3")
    assert_unique(COUNTRY_CODES, "alpha2")
    assert_unique(COUNTRY_CODES, "olympic_code")
    assert_unique(COUNTRY_CODES, "fie_code")

    helper_rows = _row_by_alpha3(country_seed_rows())
    sql_rows = _row_by_alpha3(_migration_seed_rows())
    assert set(sql_rows) == set(helper_rows)

    for alpha3, sql_row in sql_rows.items():
        helper_row = helper_rows[alpha3]
        for key in {
            "alpha2",
            "name",
            "region",
            "continent",
            "flag_emoji",
            "olympic_code",
            "fie_code",
            "aliases",
            "latitude",
            "longitude",
        }:
            assert sql_row[key] == helper_row[key], f"{alpha3}.{key}"


@pytest.mark.parametrize("bad_value", [None, "", "   ", object()])
def test_lookup_helpers_accept_blank_or_non_string_values(bad_value):
    from scripts.country_codes import lookup_country, to_alpha3

    assert lookup_country(bad_value) is None
    assert to_alpha3(bad_value) is None

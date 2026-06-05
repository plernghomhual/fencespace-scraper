from typing import Any, cast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.columns = None
        self.range_start = 0
        self.range_end = None
        self.payload = None
        self.on_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def upsert(self, payload, on_conflict=None):
        self.operation = "upsert"
        self.payload = dict(payload)
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            rows = list(self.client.tables.get(self.name, []))
            if self.range_end is not None:
                rows = rows[self.range_start : self.range_end + 1]
            return FakeResult([dict(row) for row in rows])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.name,
                    "row": dict(cast(dict[str, Any], self.payload)),
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult([dict(cast(dict[str, Any], self.payload))])
        raise AssertionError(f"unexpected operation for {self.name}")


class FakeClient:
    def __init__(self, tables):
        self.tables = {name: [dict(row) for row in rows] for name, rows in tables.items()}
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


class FakeGeocoder:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def __call__(self, country):
        self.calls.append(country)
        return self.results.get(country)


def test_lookup_static_country_normalizes_iso_names_and_olympic_aliases():
    from scripts.geocode_countries import lookup_static_country

    usa = lookup_static_country(" United States of America ")
    tpe = lookup_static_country("TPE")
    civ = lookup_static_country("Côte d'Ivoire")

    assert usa.alpha2 == "US"
    assert usa.alpha3 == "USA"
    assert usa.olympic_code == "USA"
    assert usa.fie_code == "USA"
    assert usa.display_name == "United States"
    assert usa.continent == "North America"
    assert usa.region == "Americas"
    assert round(usa.latitude, 4) == 39.8283
    assert round(usa.longitude, 4) == -98.5795

    assert tpe.alpha2 == "TW"
    assert tpe.alpha3 == "TWN"
    assert tpe.olympic_code == "TPE"
    assert tpe.fie_code == "TPE"
    assert tpe.display_name == "Chinese Taipei"

    assert civ.alpha3 == "CIV"
    assert civ.display_name == "Cote d'Ivoire"


def test_static_lookup_has_priority_over_nominatim():
    from scripts.geocode_countries import resolve_country_geo

    geocoder = FakeGeocoder({"France": {"lat": "0", "lon": "0"}})

    result = resolve_country_geo("France", geocoder=geocoder)

    assert result.alpha3 == "FRA"
    assert result.source == "static"
    assert result.source_metadata["matched"] == "France"
    assert geocoder.calls == []


def test_nominatim_fallback_preserves_unknown_alpha3_and_source_metadata():
    from scripts.geocode_countries import resolve_country_geo

    geocoder = FakeGeocoder(
        {
            "XKX": {
                "lat": "42.6026",
                "lon": "20.9030",
                "display_name": "Kosovo",
                "address": {"country": "Kosovo", "country_code": "xk"},
                "place_id": 123,
                "osm_type": "relation",
                "osm_id": 2088990,
            }
        }
    )

    result = resolve_country_geo("XKX", geocoder=geocoder)

    assert result.alpha2 == "XK"
    assert result.alpha3 == "XKX"
    assert result.display_name == "Kosovo"
    assert result.latitude == 42.6026
    assert result.longitude == 20.903
    assert result.source == "nominatim"
    assert result.source_metadata["nominatim"]["place_id"] == 123
    assert geocoder.calls == ["XKX"]


def test_backfill_uses_fencers_tournaments_and_medal_tables_without_duplicates():
    from scripts.geocode_countries import backfill_country_geocodes

    client = FakeClient(
        {
            "fs_fencers": [
                {"country": "USA"},
                {"country": "Atlantis"},
                {"country": ""},
            ],
            "fs_tournaments": [
                {"country": "France"},
                {"country": "TPE"},
            ],
            "fs_medal_tables": [
                {"country": "Italy"},
                {"country": "Great Britain"},
            ],
        }
    )
    state: dict[Any, Any] = {}

    summary = backfill_country_geocodes(
        client,
        allow_network=False,
        updated_at=NOW,
        state_get=lambda _source, key: state.get(key),
        state_set=lambda _source, key, value: state.__setitem__(key, value),
    )

    assert summary == {
        "countries_seen": 6,
        "resolved": 5,
        "written": 5,
        "failed": 0,
        "skipped": 1,
    }
    rows_by_alpha3 = {call["row"]["alpha3"]: call["row"] for call in client.upserts}
    assert set(rows_by_alpha3) == {"USA", "FRA", "TWN", "ITA", "GBR"}
    assert rows_by_alpha3["TWN"]["olympic_code"] == "TPE"
    assert rows_by_alpha3["GBR"]["display_name"] == "Great Britain"
    assert all(call["table"] == "fs_country_geocodes" for call in client.upserts)
    assert all(call["on_conflict"] == "alpha3" for call in client.upserts)
    assert state["missing_countries"] == ["Atlantis"]
    assert state["last_run"]["written"] == 5


def test_backfill_uses_nominatim_fallback_with_delay_between_network_requests():
    from scripts.geocode_countries import backfill_country_geocodes

    client = FakeClient(
        {
            "fs_fencers": [{"country": "AAA"}, {"country": "BBB"}],
            "fs_tournaments": [],
            "fs_medal_tables": [],
        }
    )
    geocoder = FakeGeocoder(
        {
            "AAA": {
                "lat": "1.5",
                "lon": "2.5",
                "display_name": "Alpha Federation",
                "address": {"country": "Alpha Federation", "country_code": "aa"},
            },
            "BBB": {
                "lat": "3.5",
                "lon": "4.5",
                "display_name": "Beta Federation",
                "address": {"country": "Beta Federation", "country_code": "bb"},
            },
        }
    )
    sleeps: list[Any] = []

    summary = backfill_country_geocodes(
        client,
        geocoder=geocoder,
        sleep_func=sleeps.append,
        request_delay=1.0,
        updated_at=NOW,
        state_get=lambda _source, _key: None,
        state_set=lambda _source, _key, _value: None,
    )

    assert summary["written"] == 2
    assert geocoder.calls == ["AAA", "BBB"]
    assert sleeps == [1.0]


def test_cached_failure_skips_nominatim_and_persists_new_failures():
    from scripts.geocode_countries import FAILURE_CACHE_KEY, backfill_country_geocodes

    cached_client = FakeClient(
        {
            "fs_fencers": [{"country": "AAA"}],
            "fs_tournaments": [],
            "fs_medal_tables": [],
        }
    )
    cached_state = {
        FAILURE_CACHE_KEY: {
            "aaa": {
                "country": "AAA",
                "reason": "no_result",
                "failed_at": "2026-06-01T00:00:00+00:00",
            }
        }
    }
    cached_geocoder = FakeGeocoder({"AAA": {"lat": "1", "lon": "2"}})

    cached_summary = backfill_country_geocodes(
        cached_client,
        geocoder=cached_geocoder,
        state_get=lambda _source, key: cached_state.get(key),
        state_set=lambda _source, key, value: cached_state.__setitem__(key, value),
    )

    assert cached_geocoder.calls == []
    assert cached_summary["written"] == 0
    assert cached_summary["skipped"] == 1

    failed_client = FakeClient(
        {
            "fs_fencers": [{"country": "BBB"}],
            "fs_tournaments": [],
            "fs_medal_tables": [],
        }
    )
    failed_state: dict[Any, Any] = {}
    failed_geocoder = FakeGeocoder({"BBB": None})

    failed_summary = backfill_country_geocodes(
        failed_client,
        geocoder=failed_geocoder,
        updated_at=NOW,
        state_get=lambda _source, key: failed_state.get(key),
        state_set=lambda _source, key, value: failed_state.__setitem__(key, value),
    )

    assert failed_summary["failed"] == 1
    assert failed_summary["skipped"] == 1
    assert failed_state[FAILURE_CACHE_KEY]["bbb"]["country"] == "BBB"
    assert failed_state[FAILURE_CACHE_KEY]["bbb"]["reason"] == "no_result"


def test_dry_run_disables_network_and_writes_nothing_for_missing_countries():
    from scripts.geocode_countries import backfill_country_geocodes

    client = FakeClient(
        {
            "fs_fencers": [{"country": "Atlantis"}],
            "fs_tournaments": [],
            "fs_medal_tables": [],
        }
    )
    geocoder = FakeGeocoder({"Atlantis": {"lat": "1", "lon": "2"}})
    state: dict[Any, Any] = {}

    summary = backfill_country_geocodes(
        client,
        dry_run=True,
        allow_network=False,
        geocoder=geocoder,
        updated_at=NOW,
        state_get=lambda _source, key: state.get(key),
        state_set=lambda _source, key, value: state.__setitem__(key, value),
    )

    assert summary == {
        "countries_seen": 1,
        "resolved": 0,
        "written": 0,
        "failed": 0,
        "skipped": 1,
    }
    assert geocoder.calls == []
    assert client.upserts == []
    assert state["missing_countries"] == ["Atlantis"]

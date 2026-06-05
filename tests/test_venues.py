import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enrich_locations import (
    GeocodeResult,
    NOMINATIM_FAILURE_CACHE_KEY,
    enrich_locations,
    extract_venue_name,
    geocode_location,
    location_key,
    parse_nominatim_result,
)


NOMINATIM_PARIS = {
    "place_id": 88703675,
    "licence": "Data (c) OpenStreetMap contributors, ODbL 1.0.",
    "osm_type": "relation",
    "osm_id": 71525,
    "lat": "48.8534951",
    "lon": "2.3483915",
    "class": "boundary",
    "type": "administrative",
    "place_rank": 12,
    "importance": 0.8845663630228834,
    "addresstype": "city",
    "name": "Paris",
    "display_name": "Paris, Ile-de-France, France",
    "address": {
        "city": "Paris",
        "country": "France",
        "country_code": "fr",
    },
    "boundingbox": ["48.8155755", "48.9021560", "2.2241220", "2.4697602"],
}


def test_extract_venue_after_dash_when_segment_looks_like_venue():
    name = "Challenge International de Paris - Stade Pierre de Coubertin"

    venue = extract_venue_name(name, "Paris")

    assert venue == "Stade Pierre de Coubertin"


def test_extract_known_venue_without_dash():
    name = "Challenge SNCF Reseau Stade Pierre de Coubertin Senior Foil"

    venue = extract_venue_name(name, "Paris")

    assert venue == "Stade Pierre de Coubertin"


def test_extract_venue_falls_back_to_city_for_generic_tournament_name():
    venue = extract_venue_name("World Cup Senior Men's Epee", "Vancouver")

    assert venue == "Vancouver"


def test_parse_nominatim_result_extracts_coordinates_country_code_and_metadata():
    result = parse_nominatim_result([NOMINATIM_PARIS])

    assert result == GeocodeResult(
        latitude=48.8534951,
        longitude=2.3483915,
        country_code="FR",
        metadata={
            "nominatim": {
                "display_name": "Paris, Ile-de-France, France",
                "osm_type": "relation",
                "osm_id": 71525,
                "place_id": 88703675,
            }
        },
    )


class FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_geocode_location_calls_nominatim_with_required_user_agent():
    session = FakeSession([FakeResponse(200, [NOMINATIM_PARIS])])

    result = geocode_location("Paris", "France", session=session)

    assert result.latitude == 48.8534951
    assert session.calls == [
        (
            "https://nominatim.openstreetmap.org/search",
            {
                "params": {
                    "q": "Paris France",
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 1,
                },
                "headers": {
                    "User-Agent": "FenceSpace-Scraper/1.0 (https://fencespace.app)"
                },
                "timeout": 20,
            },
        )
    ]


def test_geocode_location_retries_once_after_rate_limit():
    session = FakeSession(
        [
            FakeResponse(429, [], headers={"Retry-After": "1"}),
            FakeResponse(200, [NOMINATIM_PARIS]),
        ]
    )
    sleeps = []

    result = geocode_location("Paris", "France", session=session, sleep_func=sleeps.append)

    assert result.country_code == "FR"
    assert len(session.calls) == 2
    assert sleeps == [1.0]


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None
        self.payload = None
        self.eq_filter = None
        self.range_bounds = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        return self

    def not_(self, *_args):
        return self

    def range(self, start, end):
        self.range_bounds = (start, end)
        return self

    def upsert(self, payload, on_conflict=None):
        self.operation = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.eq_filter = (column, value)
        return self

    def execute(self):
        if self.operation == "select":
            rows = self.client.tables.get(self.name, [])
            if self.range_bounds:
                start, end = self.range_bounds
                rows = rows[start : end + 1]
            return type("Result", (), {"data": [dict(row) for row in rows]})()

        if self.operation == "upsert":
            row = dict(self.payload)
            self.client.upserts.append((self.name, row, self.on_conflict))
            if self.name == "fs_venues":
                key = (row["name"], row["city"], row["country"])
                existing = self.client.venue_keys.get(key)
                if existing:
                    existing.update(row)
                    saved = existing
                else:
                    row["id"] = f"venue-{len(self.client.tables['fs_venues']) + 1}"
                    self.client.tables["fs_venues"].append(row)
                    self.client.venue_keys[key] = row
                    saved = row
                return type("Result", (), {"data": [dict(saved)]})()
            return type("Result", (), {"data": [row]})()

        if self.operation == "update":
            column, value = self.eq_filter
            self.client.updates.append((self.name, column, value, dict(self.payload)))
            for row in self.client.tables.get(self.name, []):
                if row.get(column) == value:
                    row.update(self.payload)
            return type("Result", (), {"data": []})()

        return type("Result", (), {"data": []})()


class FakeRpc:
    def __init__(self, client, name, params):
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        self.client.rpcs.append((self.name, self.params))
        updates = self.params.get("p_updates", [])
        if self.name == "fs_bulk_update_tournament_metadata":
            for update in updates:
                for row in self.client.tables["fs_tournaments"]:
                    if row.get("id") == update.get("id"):
                        row["metadata"] = dict(update.get("metadata") or {})
        return type("Result", (), {"data": len(updates)})()


class FakeClient:
    def __init__(self, tournaments, venues=None):
        self.tables = {
            "fs_tournaments": [dict(row) for row in tournaments],
            "fs_venues": [dict(row) for row in venues or []],
        }
        self.venue_keys = {
            (row["name"], row["city"], row["country"]): row
            for row in self.tables["fs_venues"]
        }
        self.upserts = []
        self.updates = []
        self.rpcs = []

    def table(self, name):
        return FakeTable(self, name)

    def rpc(self, name, params):
        return FakeRpc(self, name, params)


class FakeGeocoder:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def __call__(self, city, country):
        self.calls.append((city, country))
        return self.results.get((city, country))


def test_enrich_locations_groups_same_venue_and_links_each_tournament_metadata():
    client = FakeClient(
        [
            {
                "id": "t1",
                "name": "Challenge International de Paris - Stade Pierre de Coubertin",
                "city": "Paris",
                "country": "France",
                "metadata": {"source": "fie"},
            },
            {
                "id": "t2",
                "name": "Challenge International de Paris - Stade Pierre de Coubertin",
                "city": "Paris",
                "country": "France",
                "metadata": {},
            },
        ]
    )
    geocoder = FakeGeocoder(
        {
            ("Paris", "France"): GeocodeResult(
                latitude=48.8534951,
                longitude=2.3483915,
                country_code="FR",
                metadata={"nominatim": {"place_id": 88703675}},
            )
        }
    )

    summary = enrich_locations(client, geocode_func=geocoder)

    assert summary.written == 1
    assert summary.failed == 0
    assert geocoder.calls == [("Paris", "France")]
    assert client.tables["fs_venues"] == [
        {
            "name": "Stade Pierre de Coubertin",
            "city": "Paris",
            "country": "France",
            "latitude": 48.8534951,
            "longitude": 2.3483915,
            "country_code": "FR",
            "competitions_count": 2,
            "metadata": {"nominatim": {"place_id": 88703675}},
            "id": "venue-1",
        }
    ]
    assert client.tables["fs_tournaments"][0]["metadata"] == {
        "source": "fie",
        "venue_id": "venue-1",
    }
    assert client.tables["fs_tournaments"][1]["metadata"] == {"venue_id": "venue-1"}


def test_enrich_locations_skips_geocode_for_existing_processed_city_but_links():
    client = FakeClient(
        [
            {
                "id": "t1",
                "name": "World Cup Senior Men's Epee",
                "city": "Paris",
                "country": "France",
                "metadata": {},
            }
        ],
        venues=[
            {
                "id": "venue-existing",
                "name": "Paris",
                "city": "Paris",
                "country": "France",
                "latitude": 48.8534951,
                "longitude": 2.3483915,
                "country_code": "FR",
                "competitions_count": 12,
                "metadata": {"nominatim": {"place_id": 88703675}},
            }
        ],
    )
    geocoder = FakeGeocoder({})

    summary = enrich_locations(client, geocode_func=geocoder)

    assert summary.written == 1
    assert summary.skipped == 1
    assert geocoder.calls == []
    assert client.tables["fs_venues"][0]["competitions_count"] == 1
    assert client.tables["fs_tournaments"][0]["metadata"] == {"venue_id": "venue-existing"}


def test_enrich_locations_records_ungeocodable_location_without_upsert_or_link():
    client = FakeClient(
        [
            {
                "id": "t1",
                "name": "Atlantis Cup",
                "city": "Atlantis",
                "country": "Ocean",
                "metadata": {},
            }
        ]
    )
    geocoder = FakeGeocoder({("Atlantis", "Ocean"): None})

    summary = enrich_locations(client, geocode_func=geocoder)

    assert summary.written == 0
    assert summary.failed == 1
    assert summary.skipped == 1
    assert client.tables["fs_venues"] == []
    assert client.tables["fs_tournaments"][0]["metadata"] == {}


def test_enrich_locations_skips_cached_nominatim_failure_without_geocoding():
    client = FakeClient(
        [
            {
                "id": "t1",
                "name": "Atlantis Cup",
                "city": "Atlantis",
                "country": "Ocean",
                "metadata": {},
            }
        ]
    )
    geocoder = FakeGeocoder(
        {
            ("Atlantis", "Ocean"): GeocodeResult(1.0, 2.0, "OC", {}),
        }
    )
    key = location_key("Atlantis", "Ocean")
    state = {
        NOMINATIM_FAILURE_CACHE_KEY: {
            key: {
                "city": "Atlantis",
                "country": "Ocean",
                "reason": "no_result",
                "failed_at": "2026-06-01T00:00:00+00:00",
            }
        }
    }

    summary = enrich_locations(
        client,
        geocode_func=geocoder,
        state_get=lambda _source, state_key: state.get(state_key),
        state_set=lambda _source, state_key, value: state.__setitem__(state_key, value),
    )

    assert geocoder.calls == []
    assert summary.failed == 0
    assert summary.skipped == 1
    assert client.tables["fs_venues"] == []


def test_enrich_locations_persists_nominatim_failure_cache_on_failed_geocode():
    client = FakeClient(
        [
            {
                "id": "t1",
                "name": "Atlantis Cup",
                "city": "Atlantis",
                "country": "Ocean",
                "metadata": {},
            }
        ]
    )
    geocoder = FakeGeocoder({("Atlantis", "Ocean"): None})
    state = {}

    enrich_locations(
        client,
        geocode_func=geocoder,
        state_get=lambda _source, state_key: state.get(state_key),
        state_set=lambda _source, state_key, value: state.__setitem__(state_key, value),
    )

    key = location_key("Atlantis", "Ocean")
    failure_cache = state[NOMINATIM_FAILURE_CACHE_KEY]
    assert failure_cache[key]["city"] == "Atlantis"
    assert failure_cache[key]["country"] == "Ocean"
    assert failure_cache[key]["reason"] == "no_result"
    assert failure_cache[key]["failed_at"]


def test_enrich_locations_sleeps_one_second_between_geocode_requests():
    client = FakeClient(
        [
            {"id": "t1", "name": "Paris Cup", "city": "Paris", "country": "France", "metadata": {}},
            {"id": "t2", "name": "Turin Cup", "city": "Turin", "country": "Italy", "metadata": {}},
        ]
    )
    geocoder = FakeGeocoder(
        {
            ("Paris", "France"): GeocodeResult(48.8534951, 2.3483915, "FR", {}),
            ("Turin", "Italy"): GeocodeResult(45.0677551, 7.6824892, "IT", {}),
        }
    )
    sleeps = []

    enrich_locations(client, geocode_func=geocoder, sleep_func=sleeps.append)

    assert geocoder.calls == [("Paris", "France"), ("Turin", "Italy")]
    assert sleeps == [1.0]

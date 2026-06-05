from typing import Any, cast
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = None
        self.columns = None
        self.start = 0
        self.end = None
        self.payload = None
        self.pending_conflict = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        self.client.selects.append((self.table_name, columns))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, row, on_conflict=None):
        self.operation = "upsert"
        self.payload = dict(row)
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "select":
            rows = list(self.client.tables.get(self.table_name, []))
            if self.end is not None:
                rows = rows[self.start : self.end + 1]
            return FakeResult([dict(row) for row in rows])
        if self.operation == "upsert":
            self.client.upserts.append(
                {
                    "table": self.table_name,
                    "row": dict(cast(dict[str, Any], self.payload)),
                    "on_conflict": self.pending_conflict,
                }
            )
            return FakeResult([dict(cast(dict[str, Any], self.payload))])
        raise AssertionError(f"unexpected operation for {self.table_name}")


class FakeSupabase:
    def __init__(self, tournaments):
        self.tables = {"fs_tournaments": [dict(row) for row in tournaments]}
        self.selects = []
        self.upserts = []

    def table(self, table_name):
        return FakeTable(self, table_name)


class FakeWeatherClient:
    source = "open_meteo_fixture"

    def __init__(self, geocodes=None, weather=None):
        self.geocodes = geocodes or {}
        self.weather = weather or {}
        self.geocode_calls = []
        self.weather_calls = []

    def geocode(self, location):
        self.geocode_calls.append(location)
        return self.geocodes.get(location)

    def fetch_weather(self, latitude, longitude, event_date):
        key = (round(latitude, 4), round(longitude, 4), event_date)
        self.weather_calls.append(key)
        return self.weather.get(key)


class FailingWeatherClient:
    source = "should_not_be_called"

    def geocode(self, location):
        raise AssertionError(f"unexpected geocode call for {location}")

    def fetch_weather(self, latitude, longitude, event_date):
        raise AssertionError("unexpected weather call")


def test_weather_migration_defines_context_table_shape():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_weather.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_competition_weather" in normalized
    assert "tournament_id uuid not null references public.fs_tournaments(id)" in normalized
    assert "unique (tournament_id)" in normalized
    assert "venue_name text" in normalized
    assert "location text" in normalized
    assert "event_date date" in normalized
    assert "is_indoor boolean" in normalized
    assert "environment text not null" in normalized
    assert "weather_relevance text not null" in normalized
    assert "temperature_celsius numeric" in normalized
    assert "humidity_percent numeric" in normalized
    assert "source text not null" in normalized
    assert "metadata jsonb not null default '{}'" in normalized
    assert "fs_competition_weather_tournament_id_idx" in normalized
    assert "fs_competition_weather_event_date_idx" in normalized


def test_indoor_default_writes_low_relevance_context_without_weather_lookup():
    from enrich_weather import enrich_competition_weather

    client = FakeSupabase(
        [
            {
                "id": "t1",
                "name": "Paris Foil World Cup",
                "start_date": "2025-01-18",
                "location": "Paris, France",
                "country": "France",
            }
        ]
    )

    summary = enrich_competition_weather(
        client=client,
        weather_client=FailingWeatherClient(),
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary == {
        "tournaments_read": 1,
        "written": 1,
        "weather_found": 0,
        "cache_hits": 0,
        "skipped": 0,
        "failed": 0,
    }
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_competition_weather"
    assert upsert["on_conflict"] == "tournament_id"
    row = upsert["row"]
    assert row["tournament_id"] == "t1"
    assert row["event_date"] == "2025-01-18"
    assert row["location"] == "Paris, France"
    assert row["environment"] == "indoor_assumed"
    assert row["is_indoor"] is True
    assert row["weather_relevance"] == "low"
    assert row["temperature_celsius"] is None
    assert row["humidity_percent"] is None
    assert row["source"] == "indoor_default"
    assert row["metadata"]["causal_claim"] is False
    assert "usually indoor" in row["metadata"]["reason"]


def test_explicit_outdoor_event_normalizes_open_meteo_fixture():
    from enrich_weather import enrich_competition_weather

    geocode = {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "name": "Paris",
        "country": "France",
        "admin1": "Ile-de-France",
    }
    weather = {
        "hourly_units": {
            "temperature_2m": "degC",
            "relative_humidity_2m": "%",
        },
        "hourly": {
            "time": ["2025-07-20T00:00", "2025-07-20T12:00"],
            "temperature_2m": [18.0, 26.0],
            "relative_humidity_2m": [72, 58],
        },
    }
    weather_client = FakeWeatherClient(
        geocodes={"Paris, France": geocode},
        weather={(48.8566, 2.3522, "2025-07-20"): weather},
    )
    client = FakeSupabase(
        [
            {
                "id": "outdoor-1",
                "name": "Paris Outdoor Foil Exhibition",
                "start_date": "2025-07-20",
                "location": "Paris, France",
                "venue_details": "Temporary outdoor piste in the plaza",
                "country": "France",
            }
        ]
    )

    summary = enrich_competition_weather(
        client=client,
        weather_client=weather_client,
        allow_network=True,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    row = client.upserts[0]["row"]
    assert summary["weather_found"] == 1
    assert row["environment"] == "outdoor"
    assert row["is_indoor"] is False
    assert row["weather_relevance"] == "possible_context_only"
    assert row["latitude"] == 48.8566
    assert row["longitude"] == 2.3522
    assert row["temperature_celsius"] == 22.0
    assert row["humidity_percent"] == 65.0
    assert row["source"] == "open_meteo_fixture"
    assert row["metadata"]["provider"] == "open_meteo"
    assert row["metadata"]["geocode"]["name"] == "Paris"
    assert row["metadata"]["causal_claim"] is False
    assert weather_client.geocode_calls == ["Paris, France"]
    assert weather_client.weather_calls == [(48.8566, 2.3522, "2025-07-20")]


def test_weather_lookup_cache_reuses_location_date_for_multiple_tournaments():
    from enrich_weather import enrich_competition_weather

    geocode = {"latitude": 48.8566, "longitude": 2.3522, "name": "Paris"}
    weather = {
        "hourly": {
            "time": ["2025-07-20T00:00", "2025-07-20T12:00"],
            "temperature_2m": [20.0, 24.0],
            "relative_humidity_2m": [60, 70],
        }
    }
    weather_client = FakeWeatherClient(
        geocodes={"Paris, France": geocode},
        weather={(48.8566, 2.3522, "2025-07-20"): weather},
    )
    client = FakeSupabase(
        [
            {
                "id": "outdoor-1",
                "name": "Outdoor Foil",
                "start_date": "2025-07-20",
                "location": "Paris, France",
                "venue_details": "Outdoor piste",
            },
            {
                "id": "outdoor-2",
                "name": "Outdoor Sabre",
                "start_date": "2025-07-20",
                "location": "Paris, France",
                "venue_details": "Outdoor piste",
            },
        ]
    )

    summary = enrich_competition_weather(
        client=client,
        weather_client=weather_client,
        allow_network=True,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary["written"] == 2
    assert summary["weather_found"] == 2
    assert summary["cache_hits"] == 1
    assert weather_client.geocode_calls == ["Paris, France"]
    assert weather_client.weather_calls == [(48.8566, 2.3522, "2025-07-20")]
    assert [call["row"]["temperature_celsius"] for call in client.upserts] == [22.0, 22.0]


def test_network_disabled_keeps_outdoor_event_as_dry_run_context():
    from enrich_weather import enrich_competition_weather

    client = FakeSupabase(
        [
            {
                "id": "outdoor-1",
                "name": "Outdoor Foil",
                "start_date": "2025-07-20",
                "location": "Paris, France",
                "venue_details": "Outdoor piste",
            }
        ]
    )

    summary = enrich_competition_weather(
        client=client,
        weather_client=None,
        allow_network=False,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    row = client.upserts[0]["row"]
    assert summary["written"] == 1
    assert summary["weather_found"] == 0
    assert row["environment"] == "outdoor"
    assert row["source"] == "dry_run"
    assert row["temperature_celsius"] is None
    assert row["humidity_percent"] is None
    assert row["metadata"]["weather_status"] == "network_disabled"
    assert row["metadata"]["probe_evidence"] == "sandbox DNS probe failed; escalated retry unavailable"


def test_missing_venue_or_date_writes_context_without_weather():
    from enrich_weather import enrich_competition_weather

    client = FakeSupabase(
        [
            {
                "id": "missing-location",
                "name": "No Location Cup",
                "start_date": "2025-01-18",
                "country": "France",
            },
            {
                "id": "missing-date",
                "name": "No Date Cup",
                "location": "Paris, France",
                "country": "France",
                "venue_details": "Outdoor piste",
            },
        ]
    )

    summary = enrich_competition_weather(
        client=client,
        weather_client=FailingWeatherClient(),
        allow_network=True,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    assert summary["written"] == 2
    assert summary["skipped"] == 2
    rows = {call["row"]["tournament_id"]: call["row"] for call in client.upserts}
    assert rows["missing-location"]["source"] == "missing_location"
    assert rows["missing-location"]["metadata"]["weather_status"] == "missing_location"
    assert rows["missing-date"]["source"] == "missing_date"
    assert rows["missing-date"]["metadata"]["weather_status"] == "missing_date"
    assert rows["missing-location"]["temperature_celsius"] is None
    assert rows["missing-date"]["humidity_percent"] is None


def test_missing_geocode_is_cached_and_writes_no_weather_values():
    from enrich_weather import enrich_competition_weather

    weather_client = FakeWeatherClient(geocodes={"Nowhere, ZZ": None})
    client = FakeSupabase(
        [
            {
                "id": "outdoor-1",
                "name": "Outdoor Foil",
                "start_date": "2025-07-20",
                "location": "Nowhere, ZZ",
                "venue_details": "Outdoor piste",
            },
            {
                "id": "outdoor-2",
                "name": "Outdoor Sabre",
                "start_date": "2025-07-20",
                "location": "Nowhere, ZZ",
                "venue_details": "Outdoor piste",
            },
        ]
    )

    summary = enrich_competition_weather(
        client=client,
        weather_client=weather_client,
        allow_network=True,
        log_run=False,
        update_state=False,
        updated_at=NOW,
    )

    rows = [call["row"] for call in client.upserts]
    assert summary["written"] == 2
    assert summary["weather_found"] == 0
    assert summary["cache_hits"] == 1
    assert weather_client.geocode_calls == ["Nowhere, ZZ"]
    assert weather_client.weather_calls == []
    assert all(row["source"] == "open_meteo_fixture" for row in rows)
    assert all(row["temperature_celsius"] is None for row in rows)
    assert all(row["metadata"]["weather_status"] == "missing_geocode" for row in rows)

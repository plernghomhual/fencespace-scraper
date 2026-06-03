import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"
TOURNAMENT_ID = "00000000-0000-0000-0000-000000000157"
VENUE_ID = "11111111-1111-1111-1111-111111111157"


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.start = 0
        self.end = 999
        self.pending_rows = None
        self.pending_conflict = None

    def select(self, columns):
        self.client.selects.append((self.name, columns))
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, rows, on_conflict):
        self.pending_rows = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.pending_rows is not None:
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.pending_rows,
                    "on_conflict": self.pending_conflict,
                }
            )
            return FakeResult(self.pending_rows)

        rows = list(self.client.tables.get(self.name, []))
        return FakeResult(rows[self.start : self.end + 1])


class FakeSupabase:
    def __init__(self, tournaments=None, venues=None):
        self.tables = {
            "fs_tournaments": tournaments or [],
            "fs_venues": venues or [],
        }
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


class FakeClock:
    def __init__(self):
        self.value = 0.0
        self.sleeps = []

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


def origin():
    from estimate_travel_costs import TravelOrigin

    return TravelOrigin(
        country="United States",
        city="New York",
        latitude=40.7128,
        longitude=-74.0060,
    )


def paris_tournament(**overrides):
    row = {
        "id": TOURNAMENT_ID,
        "name": "Paris Foil Grand Prix",
        "location": "Paris",
        "country": "France",
        "start_date": "2026-06-10",
        "end_date": "2026-06-12",
        "metadata": {"venue_id": VENUE_ID},
    }
    row.update(overrides)
    return row


def paris_venue(**overrides):
    row = {
        "id": VENUE_ID,
        "name": "Grand Palais",
        "city": "Paris",
        "country": "France",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "metadata": {"geocoder": "fixture"},
    }
    row.update(overrides)
    return row


def test_static_cost_calculation_uses_distance_dates_and_hotel_nights():
    from estimate_travel_costs import (
        StaticTravelCostProvider,
        build_travel_cost_rows,
    )

    rows, summary = build_travel_cost_rows(
        tournaments=[paris_tournament()],
        venues=[paris_venue()],
        origins=[origin()],
        provider=StaticTravelCostProvider(),
        currency="USD",
        updated_at=NOW,
    )

    assert summary["estimates"] == 1
    assert summary["skipped"] == 0
    assert len(rows) == 1
    row = rows[0]
    assert row["tournament_id"] == TOURNAMENT_ID
    assert row["origin_country"] == "United States"
    assert row["origin_city"] == "New York"
    assert row["destination"] == "Paris, France"
    assert row["date_range"] == "2026-06-10/2026-06-12"
    assert row["flight_estimate"] == pytest.approx(1050, abs=10)
    assert row["hotel_estimate"] == pytest.approx(450)
    assert row["currency"] == "USD"
    assert row["source"] == "static-dry-run"
    assert row["confidence"] >= 0.75
    assert row["metadata"]["hotel_nights"] == 3
    assert row["metadata"]["not_booking_advice"] is True
    assert "approximate" in row["metadata"]["disclaimer"].lower()


def test_missing_destination_or_date_is_skipped_but_missing_coordinates_are_estimated():
    from estimate_travel_costs import (
        StaticTravelCostProvider,
        build_travel_cost_rows,
    )

    missing_destination = paris_tournament(id="missing-destination", location=None, country=None)
    missing_date = paris_tournament(id="missing-date", start_date=None)
    missing_coordinates = paris_tournament(id="missing-coordinates", metadata={})

    rows, summary = build_travel_cost_rows(
        tournaments=[missing_destination, missing_date, missing_coordinates],
        venues=[],
        origins=[origin()],
        provider=StaticTravelCostProvider(),
        currency="USD",
        updated_at=NOW,
    )

    assert len(rows) == 1
    assert rows[0]["tournament_id"] == "missing-coordinates"
    assert rows[0]["confidence"] < 0.7
    assert "missing_coordinates" in rows[0]["metadata"]["estimate_limitations"]
    assert summary["skipped"] == 2
    assert summary["skip_reasons"] == {
        "missing_destination": 1,
        "missing_start_date": 1,
    }


def test_static_provider_is_default_dry_run_and_caches_rate_limited_estimates():
    from estimate_travel_costs import StaticTravelCostProvider, provider_from_env

    default_provider = provider_from_env({})
    assert isinstance(default_provider, StaticTravelCostProvider)

    clock = FakeClock()
    provider = StaticTravelCostProvider(
        min_interval_seconds=0.5,
        now_func=clock.now,
        sleep_func=clock.sleep,
    )
    event_a = paris_tournament()
    event_b = paris_tournament(id="second-event", location="Basel", country="Switzerland")

    provider.estimate(origin(), event_a, paris_venue())
    provider.estimate(origin(), event_a, paris_venue())
    provider.estimate(origin(), event_b, None)

    assert len(provider.cache) == 2
    assert clock.sleeps == [pytest.approx(0.5)]


def test_currency_converter_converts_usd_estimates_to_target_currency():
    from estimate_travel_costs import CurrencyConverter, StaticTravelCostProvider

    converter = CurrencyConverter({"USD": Decimal("1"), "EUR": Decimal("1.25")})
    provider = StaticTravelCostProvider(converter=converter)

    usd = provider.estimate(origin(), paris_tournament(), paris_venue(), currency="USD")
    eur = provider.estimate(origin(), paris_tournament(), paris_venue(), currency="EUR")

    assert eur.flight == pytest.approx(usd.flight / 1.25, abs=0.01)
    assert eur.hotel == pytest.approx(usd.hotel / 1.25, abs=0.01)
    assert eur.currency == "EUR"


def test_estimate_travel_costs_upserts_rows_with_expected_conflict_key():
    from estimate_travel_costs import StaticTravelCostProvider, estimate_travel_costs

    fake = FakeSupabase(
        tournaments=[paris_tournament()],
        venues=[paris_venue()],
    )

    summary = estimate_travel_costs(
        client=fake,
        origins=[origin()],
        provider=StaticTravelCostProvider(),
        currency="USD",
        updated_at=NOW,
        log_run=False,
        update_state=False,
    )

    assert summary["tournaments"] == 1
    assert summary["estimates"] == 1
    assert summary["written"] == 1
    assert len(fake.upserts) == 1
    upsert = fake.upserts[0]
    assert upsert["table"] == "fs_travel_cost_estimates"
    assert upsert["on_conflict"] == "tournament_id,origin_country,origin_city"
    assert upsert["rows"][0]["metadata"]["provider"] == "static-dry-run"


def test_travel_costs_migration_defines_table_constraints_and_disclaimer():
    migration = Path("supabase/migrations/20260602_travel_costs.sql")

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_travel_cost_estimates" in normalized
    assert "tournament_id uuid not null references public.fs_tournaments(id)" in normalized
    assert "origin_country text not null" in normalized
    assert "origin_city text not null" in normalized
    assert "destination text not null" in normalized
    assert "date_range text not null" in normalized
    assert "flight_estimate numeric" in normalized
    assert "hotel_estimate numeric" in normalized
    assert "metadata jsonb not null default '{}'::jsonb" in normalized
    assert "unique (tournament_id, origin_country, origin_city)" in normalized
    assert "enable row level security" in normalized
    assert "not booking advice" in normalized

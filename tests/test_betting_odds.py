import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]

CAPTURED_PUBLIC_ODDS_FIXTURE = {
    "events": [
        {
            "tournament_id": "11111111-1111-1111-1111-111111111111",
            "name": "FIE Foil Grand Prix Turin",
            "markets": [
                {
                    "key": "outright_winner",
                    "status": "open",
                    "last_update": "2026-06-02T12:00:00+00:00",
                    "outcomes": [
                        {"name": "Lee Kiefer", "price": "2.50"},
                        {"name": "Alice Volpi", "price": "+300"},
                        {"name": "Ysaora Thibus", "price": "7/2"},
                    ],
                },
                {
                    "key": "podium_finish",
                    "status": "withdrawn",
                    "last_update": "2026-06-02T12:00:00+00:00",
                    "outcomes": [{"name": "Lee Kiefer", "price": "1.80"}],
                },
                {
                    "key": "top_8_finish",
                    "status": "open",
                    "last_update": "2026-06-02T12:00:00+00:00",
                    "outcomes": [],
                },
                {
                    "key": "stale_outright",
                    "status": "open",
                    "last_update": "2026-06-01T10:00:00+00:00",
                    "outcomes": [{"name": "Eleanor Harvey", "price": "-200"}],
                },
            ],
        }
    ]
}


def test_decimal_odds_parsing_and_implied_probability_conversion():
    from scrape_betting_odds import decimal_to_implied_probability, parse_decimal_odds

    assert parse_decimal_odds("2.50") == pytest.approx(2.5)
    assert parse_decimal_odds("+300") == pytest.approx(4.0)
    assert parse_decimal_odds("-200") == pytest.approx(1.5)
    assert parse_decimal_odds("7/2") == pytest.approx(4.5)
    assert parse_decimal_odds("EVS") == pytest.approx(2.0)

    assert decimal_to_implied_probability(2.5) == pytest.approx(0.4)
    assert decimal_to_implied_probability(4.0) == pytest.approx(0.25)

    with pytest.raises(ValueError):
        parse_decimal_odds("0.95")
    with pytest.raises(ValueError):
        decimal_to_implied_probability(1.0)


def test_parser_builds_informational_rows_and_explicitly_tracks_skipped_markets():
    from scrape_betting_odds import OddsSource, parse_odds_payload

    source = OddsSource(
        name="public_fixture_book",
        source_url="https://odds.example.test/fencing.json",
        region="EU",
        access_policy="public_permitted",
        terms_confirmed=True,
        source_disclaimer="Fixture mirrors a public odds JSON feed that permits indexing.",
        region_disclaimer="Availability and legality vary by region.",
    )
    result = parse_odds_payload(
        CAPTURED_PUBLIC_ODDS_FIXTURE,
        source,
        scraped_at=datetime(2026, 6, 2, 12, 30, tzinfo=timezone.utc),
        stale_after_minutes=60,
    )

    assert len(result.rows) == 4
    first = result.rows[0]
    assert first["source"] == "public_fixture_book"
    assert first["tournament_id"] == "11111111-1111-1111-1111-111111111111"
    assert first["market_type"] == "outright_winner"
    assert first["participant"] == "Lee Kiefer"
    assert first["odds_decimal"] == pytest.approx(2.5)
    assert first["implied_probability"] == pytest.approx(0.4)
    assert first["region"] == "EU"
    assert first["source_url"] == "https://odds.example.test/fencing.json"
    assert first["metadata"]["informational_only"] is True
    assert first["metadata"]["no_betting_advice"] is True
    assert first["metadata"]["source_disclaimer"] == source.source_disclaimer
    assert first["metadata"]["region_disclaimer"] == source.region_disclaimer
    assert "recommendation" not in first["metadata"]

    stale = next(row for row in result.rows if row["market_type"] == "stale_outright")
    assert stale["metadata"]["stale"] is True
    assert stale["metadata"]["stale_reason"] == "last_update_older_than_60_minutes"

    skipped_reasons = {(item["market_type"], item["reason"]) for item in result.skipped}
    assert ("podium_finish", "market_withdrawn") in skipped_reasons
    assert ("top_8_finish", "missing_outcomes") in skipped_reasons


def test_informational_summary_contains_no_betting_advice_terms():
    from scrape_betting_odds import build_informational_summary

    summary = build_informational_summary(written=3, failed=0, skipped=2)
    lowered = summary.lower()

    assert "informational" in lowered
    for prohibited in ("recommend", "prediction", "wager", "pick", "tip"):
        assert prohibited not in lowered


class FakeResponse:
    def __init__(self, status_code=200, text="{}"):
        self.status_code = status_code
        self.text = text

    def json(self):
        return {}


class FakeSession:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_login_only_or_legally_unclear_sources_are_not_probed_or_scraped():
    from scrape_betting_odds import OddsSource, probe_source_access

    source = OddsSource(
        name="login_book",
        source_url="https://odds.example.test/login",
        region="US",
        access_policy="login_required",
        terms_confirmed=False,
        source_disclaimer="Login required.",
        region_disclaimer="US state restrictions may apply.",
    )
    session = FakeSession([FakeResponse(200, "{}")])

    probe = probe_source_access(source, session=session)

    assert probe.allowed is False
    assert probe.reason == "source_not_public_permitted"
    assert session.calls == []


def test_blocked_public_probe_is_skipped_without_parser_execution():
    from scrape_betting_odds import OddsSource, probe_source_access

    source = OddsSource(
        name="blocked_book",
        source_url="https://odds.example.test/fencing.json",
        region="US",
        access_policy="public_permitted",
        terms_confirmed=True,
        source_disclaimer="Public source if reachable.",
        region_disclaimer="US state restrictions may apply.",
    )
    session = FakeSession([FakeResponse(403, "Access denied")])

    probe = probe_source_access(source, session=session)

    assert probe.allowed is False
    assert probe.reason == "blocked_or_login_required"
    assert len(session.calls) == 1


class FakeResult:
    data: list[object] = []


class FakeUpsertTable:
    def __init__(self):
        self.calls = []

    def upsert(self, payload, on_conflict=None):
        self.calls.append((payload, on_conflict))
        return self

    def execute(self):
        return FakeResult()


class FakeClient:
    def __init__(self):
        self.upsert_table = FakeUpsertTable()

    def table(self, table_name):
        assert table_name == "fs_betting_odds"
        return self.upsert_table


def test_upsert_uses_stable_source_tournament_market_participant_region_conflict_key():
    from scrape_betting_odds import upsert_odds_rows

    client = FakeClient()
    row = {
        "source": "public_fixture_book",
        "tournament_id": "11111111-1111-1111-1111-111111111111",
        "market_type": "outright_winner",
        "participant": "Lee Kiefer",
        "odds_decimal": 2.5,
        "implied_probability": 0.4,
        "region": "EU",
        "source_url": "https://odds.example.test/fencing.json",
        "scraped_at": "2026-06-02T12:30:00+00:00",
        "metadata": {"informational_only": True, "no_betting_advice": True},
    }

    written, failed = upsert_odds_rows(client, [row], batch_size=50)

    assert written == 1
    assert failed == 0
    assert client.upsert_table.calls == [
        ([row], "source,tournament_id,market_type,participant,region")
    ]


def test_documented_stub_run_skips_without_requiring_supabase_client(monkeypatch):
    import scrape_betting_odds

    completed = []
    states = []

    class FakeRunLogger:
        def __init__(self, source):
            self.source = source

        def start(self):
            return self

        def complete(self, *, written=0, failed=0, skipped=0, metadata=None):
            completed.append(
                {
                    "written": written,
                    "failed": failed,
                    "skipped": skipped,
                    "metadata": metadata,
                }
            )

        def error(self, exc_str):
            raise AssertionError(exc_str)

    monkeypatch.setattr(scrape_betting_odds, "ScraperRunLogger", FakeRunLogger)
    monkeypatch.setattr(scrape_betting_odds, "get_state", lambda source, key: None)
    monkeypatch.setattr(
        scrape_betting_odds,
        "set_state",
        lambda source, key, value: states.append((source, key, value)),
    )
    monkeypatch.setattr(
        scrape_betting_odds,
        "get_supabase_client",
        lambda: (_ for _ in ()).throw(AssertionError("Supabase should not be required")),
    )

    summary = scrape_betting_odds.scrape_betting_odds(
        sources=scrape_betting_odds.DEFAULT_SOURCES,
        log_run=True,
        update_state=True,
    )

    assert summary["written"] == 0
    assert summary["failed"] == 0
    assert summary["skipped"] == 1
    assert summary["probes"][0]["reason"] == "source_not_public_permitted"
    assert completed[0]["skipped"] == 1
    assert states[0][0:2] == ("scrape_betting_odds", "last_run")


def test_betting_odds_migration_defines_compliance_safe_table():
    sql_path = ROOT / "supabase" / "migrations" / "20260602_betting_odds.sql"
    sql = " ".join(sql_path.read_text().lower().split())

    assert "create table if not exists public.fs_betting_odds" in sql
    assert "tournament_id uuid not null references public.fs_tournaments(id)" in sql
    assert "source text not null" in sql
    assert "market_type text not null" in sql
    assert "participant text not null" in sql
    assert "odds_decimal numeric" in sql
    assert "implied_probability numeric" in sql
    assert "region text not null" in sql
    assert "source_url text not null" in sql
    assert "metadata jsonb not null default '{}'::jsonb" in sql
    assert "unique (source, tournament_id, market_type, participant, region)" in sql
    assert "informational" in sql
    assert "not betting advice" in sql

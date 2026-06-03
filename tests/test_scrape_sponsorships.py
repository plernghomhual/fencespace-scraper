import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeUpsertTable:
    def __init__(self):
        self.calls = []

    def upsert(self, rows, on_conflict=None):
        self.calls.append((rows, on_conflict))
        return self

    def execute(self):
        return FakeResponse([])


class FakeClient:
    def __init__(self):
        self.upsert_table = FakeUpsertTable()

    def table(self, table_name):
        if table_name == "fs_sponsorships":
            return self.upsert_table
        raise AssertionError(table_name)


class FakeHTTPResponse:
    def __init__(self, text, status_code=200, url="https://example.test"):
        self.text = text
        self.status_code = status_code
        self.url = url


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses[url]


def test_sponsorship_migration_defines_explicit_evidence_table_shape():
    migration = ROOT / "supabase" / "migrations" / "20260602_sponsorships.sql"
    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_sponsorships" in normalized
    assert "fencer_id uuid references public.fs_fencers(id)" in normalized
    assert "fencer_name text not null" in normalized
    assert "sponsor_brand text not null" in normalized
    assert "normalized_brand text not null" in normalized
    assert "category text not null" in normalized
    assert "start_date date" in normalized
    assert "end_date date" in normalized
    assert "evidence_text text not null" in normalized
    assert "source_url text not null" in normalized
    assert "linked_equipment_brand text" in normalized
    assert "confidence text not null" in normalized
    assert "check (confidence in ('high', 'medium', 'low'))" in normalized
    assert "check (status in ('active', 'expired', 'unknown'))" in normalized
    assert "metadata jsonb not null default '{}'::jsonb" in normalized
    assert "on public.fs_sponsorships (fencer_id)" in normalized
    assert "on public.fs_sponsorships (normalized_brand)" in normalized


def test_extracts_official_announcement_but_not_equipment_usage():
    from scrape_sponsorships import extract_sponsorship_mentions

    text = """
    Red Bull announced Miles Chamley-Watson as a Red Bull athlete and sponsor partner.
    Miles Chamley-Watson wore a Nike jacket in a training photo.
    """

    mentions = extract_sponsorship_mentions(
        text,
        fencer_name="Miles Chamley-Watson",
        source_type="public_announcement",
        source_url="https://example.test/miles-red-bull",
    )

    assert [mention.sponsor_brand for mention in mentions] == ["Red Bull"]
    assert mentions[0].confidence == "high"
    assert "announced" in mentions[0].evidence_text


def test_rejects_ambiguous_or_social_media_only_mentions():
    from scrape_sponsorships import extract_sponsorship_mentions

    text = """
    Fans speculated Lee Kiefer may be sponsored by Nike after seeing a social-media post.
    Lee Kiefer appeared in Absolute Fencing gear at practice.
    """

    mentions = extract_sponsorship_mentions(
        text,
        fencer_name="Lee Kiefer",
        source_type="social_media",
        source_url="https://example.test/social",
    )

    assert mentions == []


def test_normalizes_brand_names_and_links_equipment_brands():
    from scrape_sponsorships import extract_sponsorship_mentions

    text = """
    Lee Kiefer is sponsored by Absolute Fencing Gear.
    Lee Kiefer also announced a Thorne partnership for training support.
    """

    mentions = extract_sponsorship_mentions(
        text,
        fencer_name="Lee Kiefer",
        source_type="sponsor_page",
        source_url="https://www.km-fencing.com/partners",
    )
    by_brand = {mention.sponsor_brand: mention for mention in mentions}

    assert by_brand["Absolute Fencing"].normalized_brand == "absolute-fencing"
    assert by_brand["Absolute Fencing"].category == "equipment"
    assert by_brand["Absolute Fencing"].linked_equipment_brand == "Absolute Fencing"
    assert by_brand["Thorne"].normalized_brand == "thorne"
    assert by_brand["Thorne"].category == "nutrition"


def test_expired_deals_keep_public_end_dates_and_expired_status():
    from scrape_sponsorships import extract_sponsorship_mentions

    text = "From 2019 to 2022, Gerek Meinhardt partnered with New Era Cap."

    mentions = extract_sponsorship_mentions(
        text,
        fencer_name="Gerek Meinhardt",
        source_type="public_announcement",
        source_url="https://example.test/new-era",
    )

    assert len(mentions) == 1
    assert mentions[0].sponsor_brand == "New Era Cap"
    assert mentions[0].start_date == "2019-01-01"
    assert mentions[0].end_date == "2022-12-31"
    assert mentions[0].status == "expired"


def test_wikidata_p859_sponsor_claims_parse_with_qualifier_dates():
    from scrape_sponsorships import extract_wikidata_sponsorships

    payload = {
        "entities": {
            "Q123": {
                "claims": {
                    "P859": [
                        {
                            "mainsnak": {
                                "datavalue": {
                                    "value": {
                                        "entity-type": "item",
                                        "numeric-id": 698,
                                        "id": "Q698",
                                    }
                                }
                            },
                            "qualifiers": {
                                "P580": [
                                    {
                                        "datavalue": {
                                            "value": {"time": "+2021-01-01T00:00:00Z"}
                                        }
                                    }
                                ],
                                "P582": [
                                    {
                                        "datavalue": {
                                            "value": {"time": "+2024-12-31T00:00:00Z"}
                                        }
                                    }
                                ],
                            },
                        }
                    ]
                }
            }
        }
    }

    mentions = extract_wikidata_sponsorships(
        payload,
        entity_id="Q123",
        sponsor_labels={"Q698": "Red Bull"},
        source_url="https://www.wikidata.org/wiki/Q123",
    )

    assert len(mentions) == 1
    assert mentions[0].sponsor_brand == "Red Bull"
    assert mentions[0].source_type == "wikidata"
    assert mentions[0].start_date == "2021-01-01"
    assert mentions[0].end_date == "2024-12-31"
    assert mentions[0].confidence == "medium"


def test_build_sponsorship_rows_use_stable_ids_and_metadata():
    from scrape_sponsorships import build_sponsorship_rows, extract_sponsorship_mentions

    fencer = {
        "id": "2cbb9fa2-a8cc-4bc6-871f-71ec27133fd7",
        "name": "Lee Kiefer",
        "fie_id": "21717",
        "country": "USA",
    }
    mentions = extract_sponsorship_mentions(
        "Lee Kiefer is sponsored by Absolute Fencing Gear.",
        fencer_name="Lee Kiefer",
        source_type="sponsor_page",
        source_url="https://www.km-fencing.com/partners",
    )

    rows = build_sponsorship_rows(fencer, mentions, scraped_at="2026-06-02T12:00:00+00:00")
    repeated_rows = build_sponsorship_rows(
        fencer, mentions, scraped_at="2026-06-02T12:00:00+00:00"
    )

    assert rows[0]["id"] == repeated_rows[0]["id"]
    assert rows[0]["fencer_id"] == fencer["id"]
    assert rows[0]["fencer_name"] == "Lee Kiefer"
    assert rows[0]["fie_id"] == "21717"
    assert rows[0]["sponsor_brand"] == "Absolute Fencing"
    assert rows[0]["linked_equipment_brand"] == "Absolute Fencing"
    assert rows[0]["metadata"]["matched_alias"] == "Absolute Fencing Gear"
    assert rows[0]["scraped_at"] == "2026-06-02T12:00:00+00:00"


def test_upsert_sponsorship_rows_uses_id_conflict_key():
    from scrape_sponsorships import upsert_sponsorship_rows

    fake = FakeClient()
    rows = [
        {
            "id": "4a5b73d6-3094-5e64-80c4-5c8ab037799f",
            "fencer_name": "Lee Kiefer",
            "sponsor_brand": "Absolute Fencing",
        }
    ]

    written, failed = upsert_sponsorship_rows(fake, rows, batch_size=50)

    assert written == 1
    assert failed == 0
    assert fake.upsert_table.calls == [([rows[0]], "id")]


def test_scrape_fencer_sponsorships_fetches_sponsor_pages_and_rate_limits():
    from scrape_sponsorships import scrape_fencer_sponsorships

    session = FakeSession(
        {
            "https://www.km-fencing.com/partners": FakeHTTPResponse(
                "Lee Kiefer is sponsored by Absolute Fencing Gear."
            )
        }
    )
    sleeps = []
    fencer = {
        "id": "2cbb9fa2-a8cc-4bc6-871f-71ec27133fd7",
        "name": "Lee Kiefer",
        "metadata": {"sponsor_pages": ["https://www.km-fencing.com/partners"]},
    }

    rows, skipped = scrape_fencer_sponsorships(
        [fencer],
        session,
        fetch_fie=False,
        fetch_external=True,
        fetch_wikidata=False,
        sleeper=sleeps.append,
    )

    assert skipped == 0
    assert rows[0]["source_url"] == "https://www.km-fencing.com/partners"
    assert session.calls[0][0] == "https://www.km-fencing.com/partners"
    assert len(sleeps) == 1


def test_run_records_logger_state_and_summary(monkeypatch):
    import scrape_sponsorships

    events = []
    state = {}

    class FakeLogger:
        def __init__(self, module):
            self.module = module

        def start(self):
            events.append(("start", self.module))
            return self

        def complete(self, *, written=0, failed=0, skipped=0, metadata=None):
            events.append(("complete", written, failed, skipped, metadata))

        def error(self, exc_str):
            events.append(("error", exc_str))

    monkeypatch.setattr(scrape_sponsorships, "ScraperRunLogger", FakeLogger)
    monkeypatch.setattr(scrape_sponsorships, "get_state", lambda source, key: {"ran_at": "prior"})
    monkeypatch.setattr(
        scrape_sponsorships,
        "set_state",
        lambda source, key, value: state.update({(source, key): value}),
    )
    monkeypatch.setattr(
        scrape_sponsorships,
        "load_fencers",
        lambda client, limit: [{"id": "f1", "name": "Lee Kiefer"}],
    )
    monkeypatch.setattr(
        scrape_sponsorships,
        "scrape_fencer_sponsorships",
        lambda fencers, session, **kwargs: (
            [{"id": "row-1", "fencer_name": "Lee Kiefer", "sponsor_brand": "Absolute Fencing"}],
            0,
        ),
    )
    monkeypatch.setattr(
        scrape_sponsorships,
        "upsert_sponsorship_rows",
        lambda client, rows: (1, 0),
    )

    summary = scrape_sponsorships.run(
        client=object(),
        session=type("Session", (), {"headers": {}})(),
        limit=5,
        fetch_fie=False,
        fetch_external=False,
        fetch_wikidata=False,
    )

    assert summary["fencers_scanned"] == 1
    assert summary["sponsorship_rows_found"] == 1
    assert summary["written"] == 1
    assert events[0] == ("start", "scrape_sponsorships")
    assert events[1][0:4] == ("complete", 1, 0, 0)
    assert state[("scrape_sponsorships", "last_run")]["previous_run"] == {"ran_at": "prior"}

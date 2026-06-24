import os
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260602_social_followers.sql"


WIKIDATA_SOCIAL_BINDING = {
    "athlete": {"value": "http://www.wikidata.org/entity/Q12345"},
    "athleteLabel": {"value": "Ada Blade"},
    "fie_id": {"value": "999001"},
    "instagram": {"value": "@Ada.Blade"},
    "twitter": {"value": "AdaBlade"},
    "mastodon": {"value": "@ada@mastodon.social"},
}


PUBLIC_MASTODON_ACCOUNT = {
    "id": "109999999",
    "username": "ada",
    "acct": "ada",
    "display_name": "Ada Blade",
    "url": "https://mastodon.social/@ada",
    "locked": False,
    "followers_count": 1234,
    "following_count": 98,
}


HIDDEN_COUNT_ACCOUNT = {
    "id": "109999998",
    "username": "private-fencer",
    "acct": "private-fencer",
    "display_name": "Private Fencer",
    "url": "https://mastodon.social/@private-fencer",
    "locked": True,
}


def test_parse_wikidata_social_binding_normalizes_handles_and_urls():
    from scrape_social_followers import parse_wikidata_social_binding

    profiles = parse_wikidata_social_binding(WIKIDATA_SOCIAL_BINDING)
    by_platform = {profile.platform: profile for profile in profiles}

    assert by_platform["instagram"].handle == "ada.blade"
    assert by_platform["instagram"].url == "https://www.instagram.com/ada.blade/"
    assert by_platform["twitter"].handle == "adablade"
    assert by_platform["twitter"].url == "https://x.com/adablade"
    assert by_platform["mastodon"].handle == "ada@mastodon.social"
    assert by_platform["mastodon"].url == "https://mastodon.social/@ada"
    assert by_platform["mastodon"].wikidata_id == "Q12345"
    assert by_platform["mastodon"].fie_id == "999001"


def test_source_policy_allows_only_public_api_count_sources():
    from scrape_social_followers import normalize_social_profile, source_policy_for_profile

    instagram = normalize_social_profile("instagram", "@Ada.Blade")
    mastodon = normalize_social_profile("mastodon", "@ada@mastodon.social")

    instagram_policy = source_policy_for_profile(instagram)
    mastodon_policy = source_policy_for_profile(mastodon)

    assert instagram_policy.allowed is False
    assert instagram_policy.reason == "blocked_login_or_restricted_api"
    assert mastodon_policy.allowed is True
    assert mastodon_policy.reason == "public_federated_api"


def test_login_only_profile_urls_are_skipped_before_fetch():
    from scrape_social_followers import normalize_social_profile

    assert normalize_social_profile(
        "instagram",
        "https://www.instagram.com/accounts/login/?next=/ada.blade/",
    ) is None
    assert normalize_social_profile(
        "twitter",
        "https://x.com/i/flow/login?redirect_after_login=%2Fadablade",
    ) is None


def test_parse_public_mastodon_snapshot_counts_and_date_bucket():
    from scrape_social_followers import (
        SocialProfileCandidate,
        normalize_social_profile,
        parse_mastodon_account_snapshot,
    )

    collected_at = datetime(2026, 6, 2, 15, 30, tzinfo=UTC)
    profile = cast(SocialProfileCandidate, normalize_social_profile("mastodon", "@ada@mastodon.social"))
    row = parse_mastodon_account_snapshot(
        profile,
        PUBLIC_MASTODON_ACCOUNT,
        collected_at=collected_at,
        fencer_identity_id="identity-1",
    )

    assert row["fencer_identity_id"] == "identity-1"
    assert row["fencer_id"] is None
    assert row["platform"] == "mastodon"
    assert row["handle"] == "ada@mastodon.social"
    assert row["url"] == "https://mastodon.social/@ada"
    assert row["follower_count"] == 1234
    assert row["following_count"] == 98
    assert row["source"] == "mastodon_api"
    assert row["collected_at"] == "2026-06-02T15:30:00+00:00"
    assert row["date_bucket"] == "2026-06-02"
    assert row["snapshot_key"] == "identity-1:mastodon:ada@mastodon.social:2026-06-02"
    assert row["metadata"]["counts_available"] is True


def test_parse_mastodon_snapshot_handles_missing_hidden_counts():
    from scrape_social_followers import (
        SocialProfileCandidate,
        normalize_social_profile,
        parse_mastodon_account_snapshot,
    )

    profile = cast(SocialProfileCandidate, normalize_social_profile("mastodon", "@private-fencer@mastodon.social"))
    row = parse_mastodon_account_snapshot(
        profile,
        HIDDEN_COUNT_ACCOUNT,
        collected_at=datetime(2026, 6, 2, tzinfo=UTC),
        fencer_id="fencer-1",
    )

    assert row["follower_count"] is None
    assert row["following_count"] is None
    assert row["metadata"]["counts_available"] is False
    assert row["metadata"]["locked"] is True


def test_collect_profile_snapshot_skips_blocked_platform_without_request():
    from scrape_social_followers import SocialProfileCandidate, collect_profile_snapshot, normalize_social_profile

    class Session:
        def __init__(self):
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            raise AssertionError("blocked platform should not be fetched")

    profile = cast(SocialProfileCandidate, normalize_social_profile("instagram", "@Ada.Blade"))
    session = Session()

    row, blocked = collect_profile_snapshot(
        profile,
        session=session,
        collected_at=datetime(2026, 6, 2, tzinfo=UTC),
        fencer_id="fencer-1",
    )

    assert row is None
    blocked = cast(dict[str, Any], blocked)
    assert blocked["platform"] == "instagram"
    assert blocked["reason"] == "blocked_login_or_restricted_api"
    assert session.calls == []


def test_write_snapshot_rows_upserts_on_snapshot_key():
    from scrape_social_followers import write_snapshot_rows

    class FakeExecute:
        data = [{"id": "row-1"}]

    class FakeTable:
        def __init__(self, client, name):
            self.client = client
            self.name = name

        def upsert(self, row, on_conflict):
            self.client.upserts.append(
                {"table": self.name, "row": row, "on_conflict": on_conflict}
            )
            return self

        def execute(self):
            return FakeExecute()

    class FakeClient:
        def __init__(self):
            self.upserts = []

        def table(self, name):
            return FakeTable(self, name)

    client = FakeClient()
    written = write_snapshot_rows(
        client,
        [
            {
                "snapshot_key": "identity-1:mastodon:ada@mastodon.social:2026-06-02",
                "fencer_identity_id": "identity-1",
                "fencer_id": None,
                "platform": "mastodon",
                "handle": "ada@mastodon.social",
                "url": "https://mastodon.social/@ada",
                "follower_count": 1234,
                "following_count": 98,
                "source": "mastodon_api",
                "collected_at": "2026-06-02T15:30:00+00:00",
                "date_bucket": "2026-06-02",
                "metadata": {},
            }
        ],
    )

    assert written == 1
    assert client.upserts[0]["table"] == "fs_social_followers"
    assert client.upserts[0]["on_conflict"] == "snapshot_key"


def test_social_followers_migration_defines_historical_snapshot_table():
    sql = MIGRATION.read_text().lower()

    assert "create table if not exists fs_social_followers" in sql
    for column in (
        "snapshot_key",
        "fencer_identity_id",
        "fencer_id",
        "platform",
        "handle",
        "url",
        "follower_count",
        "following_count",
        "source",
        "collected_at",
        "date_bucket",
        "metadata",
    ):
        assert column in sql
    assert "unique (snapshot_key)" in sql
    assert "check (fencer_identity_id is not null or fencer_id is not null)" in sql
    assert "check (follower_count is null or follower_count >= 0)" in sql
    assert "alter table fs_social_followers enable row level security" in sql

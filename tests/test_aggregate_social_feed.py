import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


BLUESKY_SEARCH_FIXTURE = {
    "posts": [
        {
            "uri": "at://did:plc:teamusa/app.bsky.feed.post/3lfeed001",
            "cid": "bafyfeed001",
            "author": {"handle": "teamusa.org", "displayName": "Team USA"},
            "record": {
                "text": "Gold for @leetothekiefer.com at the Turin Grand Prix! #Fencing #Foil",
                "createdAt": "2026-06-01T18:30:00.000Z",
                "langs": ["en"],
                "facets": [
                    {
                        "features": [
                            {"$type": "app.bsky.richtext.facet#tag", "tag": "Fencing"},
                            {"$type": "app.bsky.richtext.facet#tag", "tag": "Foil"},
                        ]
                    }
                ],
            },
            "labels": [],
        },
        {
            "uri": "at://did:plc:frfencing/app.bsky.feed.post/3lfeed002",
            "cid": "bafyfeed002",
            "author": {"handle": "ffe.fr", "displayName": "FFE"},
            "record": {
                "text": "La finale d'épée est en direct. #escrime #fencing",
                "createdAt": "2026-06-01T19:00:00.000Z",
                "langs": ["fr"],
                "facets": [
                    {
                        "features": [
                            {"$type": "app.bsky.richtext.facet#tag", "tag": "escrime"},
                            {"$type": "app.bsky.richtext.facet#tag", "tag": "fencing"},
                        ]
                    }
                ],
            },
            "labels": [],
        },
    ]
}


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        return self

    def upsert(self, rows, on_conflict):
        self.operation = "upsert"
        self.client.upserts.append(
            {"table": self.name, "rows": rows, "on_conflict": on_conflict}
        )
        return self

    def execute(self):
        if self.operation == "upsert":
            return FakeResult([])
        if self.name == "fs_fencer_social_media":
            return FakeResult(self.client.fencer_links)
        if self.name == "fs_tournaments":
            return FakeResult(self.client.tournaments)
        return FakeResult([])


class FakeClient:
    def __init__(self):
        self.fencer_links = []
        self.tournaments = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


class FixtureProvider:
    name = "fixture"
    platform = "bluesky"
    rate_limit_seconds = 0
    required_env = ()
    allows_text_excerpt = True

    def __init__(self, posts):
        self.posts = posts
        self.queries = []

    def missing_configuration(self):
        return []

    def fetch(self, queries):
        self.queries.extend(queries)
        return list(self.posts)


def test_migration_defines_social_feed_table_and_unique_constraint():
    sql = Path("supabase/migrations/20260602_social_feed.sql").read_text()
    lowered = " ".join(sql.lower().split())

    assert "create table if not exists fs_social_feed" in lowered
    for column in [
        "platform text not null",
        "post_id text not null",
        "author text",
        "url text not null",
        "text_excerpt text",
        "hashtags text[]",
        "language text",
        "related_fencer_ids uuid[]",
        "tournament_id uuid references fs_tournaments(id)",
        "posted_at timestamptz not null",
        "source text not null",
        "metadata jsonb",
    ]:
        assert column in lowered
    assert "unique (platform, post_id)" in lowered
    assert "char_length(text_excerpt) <= 500" in lowered
    assert "fs_social_feed_hashtags_idx" in lowered
    assert "fs_social_feed_related_fencer_ids_idx" in lowered


def test_bluesky_fixture_parser_normalizes_hashtags_language_and_excerpt():
    import aggregate_social_feed as feed

    posts = feed.parse_bluesky_search_response(BLUESKY_SEARCH_FIXTURE, query="#fencing")

    assert [post.post_id for post in posts] == [
        "at://did:plc:teamusa/app.bsky.feed.post/3lfeed001",
        "at://did:plc:frfencing/app.bsky.feed.post/3lfeed002",
    ]
    assert posts[0].platform == "bluesky"
    assert posts[0].author == "teamusa.org"
    assert posts[0].hashtags == ["fencing", "foil"]
    assert posts[0].language == "en"
    assert posts[0].posted_at == datetime(2026, 6, 1, 18, 30, tzinfo=UTC)
    assert posts[0].text.startswith("Gold for")
    assert posts[1].hashtags == ["escrime", "fencing"]
    assert posts[1].language == "fr"


def test_filter_dedupes_spam_false_positives_private_and_unsafe_posts():
    import aggregate_social_feed as feed

    good_posts = feed.parse_bluesky_search_response(BLUESKY_SEARCH_FIXTURE, query="#fencing")
    duplicate = feed.RawSocialPost(
        platform="bluesky",
        post_id=good_posts[0].post_id,
        author="copy.example",
        url=good_posts[0].url,
        text="Duplicate #fencing post",
        hashtags=["fencing"],
        language="en",
        posted_at=good_posts[0].posted_at,
        source="fixture",
        metadata={},
        allows_text_excerpt=True,
    )
    false_positive = feed.RawSocialPost(
        platform="bluesky",
        post_id="yard-fence",
        author="contractor.example",
        url="https://bsky.app/profile/contractor.example/post/yard-fence",
        text="Privacy fence installation sale this week #fencing",
        hashtags=["fencing"],
        language="en",
        posted_at=good_posts[0].posted_at,
        source="fixture",
        metadata={},
        allows_text_excerpt=True,
    )
    unsafe = feed.RawSocialPost(
        platform="bluesky",
        post_id="unsafe",
        author="unsafe.example",
        url="https://bsky.app/profile/unsafe.example/post/unsafe",
        text="Fencing stream #fencing",
        hashtags=["fencing"],
        language="en",
        posted_at=good_posts[0].posted_at,
        source="fixture",
        metadata={"possibly_sensitive": True},
        allows_text_excerpt=True,
    )
    private = feed.RawSocialPost(
        platform="mastodon",
        post_id="followers-only",
        author="@fencer@mastodon.social",
        url="https://mastodon.social/@fencer/1",
        text="Private fencing update #fencing",
        hashtags=["fencing"],
        language="en",
        posted_at=good_posts[0].posted_at,
        source="fixture",
        metadata={"visibility": "private"},
        allows_text_excerpt=True,
    )

    kept, stats = feed.filter_and_dedupe_posts(
        [*good_posts, duplicate, false_positive, unsafe, private]
    )

    assert [post.post_id for post in kept] == [post.post_id for post in good_posts]
    assert stats == {
        "input": 6,
        "kept": 2,
        "duplicates": 1,
        "spam": 0,
        "false_positives": 1,
        "unsafe_or_private": 2,
    }


def test_linking_uses_exact_handles_urls_and_event_names_not_loose_names():
    import aggregate_social_feed as feed

    posted_at = datetime(2026, 6, 1, 18, 30, tzinfo=UTC)
    loose_name_post = feed.RawSocialPost(
        platform="bluesky",
        post_id="loose",
        author="news.example",
        url="https://bsky.app/profile/news.example/post/loose",
        text="Lee Kiefer is expected to fence this weekend #fencing",
        hashtags=["fencing"],
        language="en",
        posted_at=posted_at,
        source="fixture",
        metadata={},
        allows_text_excerpt=True,
    )
    exact_handle_post = feed.RawSocialPost(
        platform="bluesky",
        post_id="exact",
        author="teamusa.org",
        url="https://bsky.app/profile/teamusa.org/post/exact",
        text="@leetothekiefer.com wins the Turin Grand Prix #fencing",
        hashtags=["fencing"],
        language="en",
        posted_at=posted_at,
        source="fixture",
        metadata={},
        allows_text_excerpt=True,
    )
    fencer_links = [
        feed.FencerSocialLink(
            fencer_id="fencer-lee",
            platform="bluesky",
            handle="leetothekiefer.com",
            url="https://bsky.app/profile/leetothekiefer.com",
        )
    ]
    tournaments = [feed.TournamentLink(id="tournament-turin", name="Turin Grand Prix")]

    rows = feed.build_feed_rows(
        [loose_name_post, exact_handle_post],
        fencer_links=fencer_links,
        tournaments=tournaments,
    )

    assert rows[0]["related_fencer_ids"] == []
    assert rows[0]["tournament_id"] is None
    assert rows[1]["related_fencer_ids"] == ["fencer-lee"]
    assert rows[1]["tournament_id"] == "tournament-turin"


def test_run_upserts_deduped_public_rows_with_supabase_conflict_key():
    import aggregate_social_feed as feed

    client = FakeClient()
    client.fencer_links = [
        {
            "fencer_id": "fencer-lee",
            "platform": "bluesky",
            "handle": "leetothekiefer.com",
            "url": "https://bsky.app/profile/leetothekiefer.com",
        }
    ]
    client.tournaments = [{"id": "tournament-turin", "name": "Turin Grand Prix"}]
    posts = feed.parse_bluesky_search_response(BLUESKY_SEARCH_FIXTURE, query="#fencing")
    provider = FixtureProvider([posts[0], posts[0], posts[1]])

    stats = feed.run(client=client, providers=[provider], env={}, sleep=lambda _: None)

    assert stats["written"] == 2
    assert stats["dry_run"] is False
    assert provider.queries == feed.DEFAULT_QUERIES
    assert len(client.upserts) == 1
    assert client.upserts[0]["table"] == "fs_social_feed"
    assert client.upserts[0]["on_conflict"] == "platform,post_id"
    rows = client.upserts[0]["rows"]
    assert rows[0]["text_excerpt"].startswith("Gold for")
    assert rows[0]["related_fencer_ids"] == ["fencer-lee"]
    assert rows[0]["metadata"]["query"] == "#fencing"
    assert rows[1]["language"] == "fr"


def test_missing_provider_keys_dry_run_exits_zero_without_upsert(capsys):
    import aggregate_social_feed as feed

    client = FakeClient()
    provider = feed.XRecentSearchProvider(env={})

    stats = feed.run(client=client, providers=[provider], env={}, sleep=lambda _: None)

    captured = capsys.readouterr()
    assert stats["dry_run"] is True
    assert stats["written"] == 0
    assert stats["missing_provider_keys"] == {"x": ["X_BEARER_TOKEN"]}
    assert client.upserts == []
    assert "dry run" in captured.out.lower()
    assert "X_BEARER_TOKEN" in captured.out


def test_main_missing_keys_dry_run_does_not_require_supabase_credentials(monkeypatch):
    import aggregate_social_feed as feed

    states = []

    class FakeRunLog:
        def start(self):
            return self

        def complete(self, **kwargs):
            self.completed = kwargs

        def error(self, exc_str):
            raise AssertionError(f"unexpected run logger error: {exc_str}")

    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(feed, "ScraperRunLogger", lambda module: FakeRunLog())
    monkeypatch.setattr(feed, "set_state", lambda source, key, value: states.append((source, key, value)))
    monkeypatch.setattr(
        feed,
        "_get_client",
        lambda env=None: (_ for _ in ()).throw(AssertionError("client should not be created")),
    )

    assert feed.main() == 0
    assert states[0][0] == feed.SOURCE
    assert states[0][1] == "last_run"
    assert states[0][2]["stats"]["dry_run"] is True

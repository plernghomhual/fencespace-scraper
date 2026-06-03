import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


API_FIXTURE = {
    "business_discovery": {
        "id": "17841400000000000",
        "username": "fencing_fie",
        "name": "International Fencing Federation",
        "media_count": 4312,
        "biography": "Official account biography should not be stored.",
        "profile_picture_url": "https://cdn.example.test/private-ish.jpg",
        "media": {
            "data": [
                {
                    "id": "17900000000000001",
                    "caption": "Lee Kiefer wins gold for USA. Congrats @leetothekiefer #fencing",
                    "media_type": "IMAGE",
                    "permalink": "https://www.instagram.com/p/CapturedFixture/?utm_source=ig_web_copy_link",
                    "timestamp": "2026-05-31T18:45:12+0000",
                    "username": "fencing_fie",
                    "like_count": 1200,
                    "comments_count": 34,
                }
            ]
        },
    }
}


class ExplodingSession:
    def get(self, *args, **kwargs):
        raise AssertionError("no-key dry run must not make HTTP calls")


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.filters = []
        self._rows = []
        self._on_conflict = None

    def select(self, columns):
        self.client.selects.append((self.name, columns))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def range(self, start, end):
        self.range_bounds = (start, end)
        return self

    def upsert(self, rows, on_conflict):
        self._rows = rows
        self._on_conflict = on_conflict
        return self

    def execute(self):
        if self._on_conflict is not None:
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self._rows,
                    "on_conflict": self._on_conflict,
                }
            )
            return FakeResult(self._rows)
        if self.name == "fs_fencers":
            return FakeResult(self.client.fencers)
        if self.name == "fs_fencer_social_media":
            return FakeResult(self.client.social_rows)
        return FakeResult([])


class FakeClient:
    def __init__(self):
        self.fencers = [
            {"id": "11111111-1111-1111-1111-111111111111", "name": "Lee Kiefer"},
            {"id": "22222222-2222-2222-2222-222222222222", "name": "Arianna Errigo"},
            {"id": "33333333-3333-3333-3333-333333333333", "name": "Kim"},
        ]
        self.social_rows = [
            {
                "fencer_id": "11111111-1111-1111-1111-111111111111",
                "handle": "leetothekiefer",
                "url": "https://www.instagram.com/leetothekiefer/",
                "metadata": {},
            },
            {
                "fencer_id": "22222222-2222-2222-2222-222222222222",
                "handle": "ariannaerrigo",
                "url": "https://www.instagram.com/ariannaerrigo/",
                "metadata": {},
            },
        ]
        self.selects = []
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_no_key_dry_run_uses_mock_fixture_without_http_or_database_writes():
    import scrape_instagram_fencing as ig

    client = FakeClient()

    result = ig.scrape_instagram_fencing(
        client=client,
        env={},
        session=ExplodingSession(),
        request_delay=0,
    )

    assert result["dry_run"] is True
    assert result["provider"] == "fixture"
    assert result["fetched"] >= 1
    assert result["written"] == 0
    assert client.upserts == []
    assert result["rows"][0]["metadata"]["provider"] == "fixture"


def test_api_fixture_parser_normalizes_public_post_metadata():
    import scrape_instagram_fencing as ig

    posts, skip_reason = ig.parse_business_discovery_payload(
        "Fencing_FIE",
        API_FIXTURE,
        known_fencers=[{"id": "11111111-1111-1111-1111-111111111111", "name": "Lee Kiefer"}],
    )

    assert skip_reason is None
    assert len(posts) == 1
    post = posts[0]
    assert post["platform"] == "instagram"
    assert post["handle"] == "fencing_fie"
    assert post["post_url"] == "https://www.instagram.com/p/CapturedFixture/"
    assert post["timestamp"] == "2026-05-31T18:45:12+00:00"
    assert post["caption_snippet"] == "Lee Kiefer wins gold for USA. Congrats @leetothekiefer #fencing"
    assert post["mention_tags"] == ["leetothekiefer"]
    assert post["related_fencer_ids"] == ["11111111-1111-1111-1111-111111111111"]
    assert post["account"]["username"] == "fencing_fie"
    assert "biography" not in post["account"]
    assert "profile_picture_url" not in post["account"]


def test_mentions_match_fencers_by_handle_and_name_without_false_short_matches():
    import scrape_instagram_fencing as ig

    caption = "Arianna Errigo fenced Lee Kiefer. @ariannaerrigo reposted; kimono is unrelated."
    known = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "Lee Kiefer", "instagram_handle": "leetothekiefer"},
        {"id": "22222222-2222-2222-2222-222222222222", "name": "Arianna Errigo", "instagram_handle": "ariannaerrigo"},
        {"id": "33333333-3333-3333-3333-333333333333", "name": "Kim", "instagram_handle": "kim"},
    ]

    mentions = ig.extract_mention_tags(caption)

    assert mentions == ["ariannaerrigo"]
    assert ig.extract_related_fencer_ids(caption, mentions, known) == [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]


def test_private_or_login_only_api_results_are_skipped():
    import scrape_instagram_fencing as ig

    posts, skip_reason = ig.parse_business_discovery_payload(
        "private_handle",
        {
            "error": {
                "message": (
                    "Unsupported get request. Object does not exist, cannot be loaded "
                    "due to missing permissions, or does not support this operation."
                )
            }
        },
        known_fencers=[],
    )

    assert posts == []
    assert skip_reason == "provider_unavailable_or_private"


def test_article_row_redacts_sensitive_caption_text_and_upserts_by_url():
    import scrape_instagram_fencing as ig

    post = {
        "platform": "instagram",
        "handle": "fencing_fie",
        "post_id": "17900000000000002",
        "post_url": "https://www.instagram.com/p/PublicFixture/",
        "timestamp": "2026-06-01T10:00:00+00:00",
        "caption_snippet": "Lee Kiefer clinic: email coach@example.com or call +1 555-123-4567 @leetothekiefer",
        "mention_tags": ["leetothekiefer"],
        "related_fencer_ids": ["11111111-1111-1111-1111-111111111111"],
        "media_type": "IMAGE",
        "account": {"username": "fencing_fie", "name": "International Fencing Federation"},
        "provider": "instagram_graph_business_discovery",
    }

    row = ig.build_article_row(post)
    client = FakeClient()

    written = ig.upsert_instagram_rows(client, [row])

    assert written == 1
    assert row["source"] == "instagram_fencing"
    assert row["source_site"] == "instagram.com"
    assert row["url"] == "https://www.instagram.com/p/PublicFixture/"
    assert "[redacted-email]" in row["summary"]
    assert "[redacted-phone]" in row["summary"]
    assert "coach@example.com" not in row["summary"]
    assert "555-123-4567" not in row["summary"]
    assert row["metadata"]["caption_snippet"] == row["summary"]
    assert "biography" not in row["metadata"]
    assert client.upserts[0]["table"] == "fs_articles"
    assert client.upserts[0]["on_conflict"] == "url"

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

NOW = "2026-06-02T12:00:00+00:00"

FENCING_NET_RETIRED_HTML = """
<html>
  <body>
    <main>
      <h1>Forums Retired</h1>
      <p>In mid 2019, we retired the Fencing.net forums, switching them over
      to an archive mode.</p>
      <p>In mid 2020, traffic to the forum's archives has become so minimal
      that maintaining them publicly in the archived format no longer makes
      sense.</p>
      <ul>
        <li><a href="/2011/03/14/installing-a-home-fencing-piste/">
          Installing a Home Fencing Piste
        </a></li>
        <li><a href="https://fencing.net/211/home-made-diy-grounded-strips/">
          "Home Made" DIY Grounded Strips
        </a></li>
      </ul>
    </main>
  </body>
</html>
"""

REDDIT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>t3_abc123</id>
    <title>Lee Kiefer point-in-line question</title>
    <link href="https://www.reddit.com/r/Fencing/comments/abc123/lee_kiefer_question/"/>
    <author><name>FoilFan42</name></author>
    <updated>2026-06-01T09:30:00+00:00</updated>
    <category term="Rules"/>
    <content type="html">submitted by /u/FoilFan42 with private@example.com</content>
  </entry>
</feed>
"""


class FakeResponse:
    def __init__(self, *, json_data=None, text="", status_code=200):
        self._json_data = json_data
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if not self.responses:
            raise AssertionError(f"Unexpected GET {url}")
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if not self.responses:
            raise AssertionError(f"Unexpected POST {url}")
        return self.responses.pop(0)


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.rows = None
        self.on_conflict = None
        self.columns = None
        self.start = 0
        self.end = 999

    def select(self, columns):
        self.columns = columns
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, rows, on_conflict):
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.rows is not None:
            self.client.upserts.append(
                {
                    "table": self.name,
                    "rows": self.rows,
                    "on_conflict": self.on_conflict,
                }
            )
            return FakeResult(self.rows)
        rows = self.client.tables.get(self.name, [])
        return FakeResult(rows[self.start : self.end + 1])


class FakeSupabase:
    def __init__(self, tables=None):
        self.tables = tables or {}
        self.upserts = []

    def table(self, name):
        return FakeTable(self, name)


def test_parse_fencing_net_retired_page_extracts_public_converted_topics():
    from scrape_fencing_forums import parse_fencing_net_forums_page

    discussions = parse_fencing_net_forums_page(
        FENCING_NET_RETIRED_HTML,
        source_url="https://fencing.net/forums/",
        scraped_at=NOW,
    )

    assert [item["title"] for item in discussions] == [
        "Installing a Home Fencing Piste",
        '"Home Made" DIY Grounded Strips',
    ]
    assert discussions[0]["source"] == "fencing_net"
    assert discussions[0]["url"] == "https://fencing.net/2011/03/14/installing-a-home-fencing-piste/"
    assert discussions[0]["author_hash"] is None
    assert discussions[0]["tags"] == ["legacy-forum", "converted-topic"]
    assert discussions[0]["metadata"]["probe_status"] == "forums_retired"
    assert discussions[0]["scraped_at"] == NOW


def test_parse_reddit_listing_hashes_author_and_drops_body_text():
    from scrape_fencing_forums import parse_reddit_listing

    discussions = parse_reddit_listing(
        {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "Lee Kiefer point-in-line question",
                            "author": "FoilFan42",
                            "selftext": "Please email private@example.com",
                            "permalink": "/r/Fencing/comments/abc123/lee_kiefer_question/",
                            "created_utc": 1780306200,
                            "link_flair_text": "Rules",
                            "score": 17,
                            "num_comments": 8,
                            "upvote_ratio": 0.95,
                        }
                    }
                ]
            }
        },
        fetched_via="api",
        scraped_at=NOW,
    )

    assert len(discussions) == 1
    discussion = discussions[0]
    assert discussion["thread_id"] == "abc123"
    assert discussion["url"] == "https://www.reddit.com/r/Fencing/comments/abc123/lee_kiefer_question/"
    assert discussion["author_hash"].startswith("sha256:")
    assert "FoilFan42" not in str(discussion)
    assert "private@example.com" not in str(discussion)
    assert discussion["summary"] == "Lee Kiefer point-in-line question"
    assert discussion["metadata"] == {
        "comments": 8,
        "fetched_via": "api",
        "score": 17,
        "subreddit": None,
        "upvote_ratio": 0.95,
    }


def test_reddit_no_credentials_uses_allowed_rss_not_public_json():
    from scrape_fencing_forums import fetch_reddit_discussions

    session = FakeSession([FakeResponse(text=REDDIT_RSS)])

    discussions = fetch_reddit_discussions(
        session=session,
        credentials={},
        scraped_at=NOW,
    )

    assert len(discussions) == 1
    assert discussions[0]["thread_id"] == "abc123"
    assert discussions[0]["metadata"]["fetched_via"] == "rss"
    requested_urls = [call[1] for call in session.calls]
    assert requested_urls == ["https://www.reddit.com/r/Fencing/.rss"]
    assert all(".json" not in url for url in requested_urls)


def test_reddit_credentials_use_oauth_api():
    from scrape_fencing_forums import fetch_reddit_discussions

    listing = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "def456",
                        "title": "Alex Massialas training clip",
                        "author": "SaberFan",
                        "permalink": "/r/Fencing/comments/def456/training_clip/",
                        "created_utc": 1780306200,
                    }
                }
            ]
        }
    }
    session = FakeSession(
        [
            FakeResponse(json_data={"access_token": "token-123"}),
            FakeResponse(json_data=listing),
        ]
    )

    discussions = fetch_reddit_discussions(
        session=session,
        credentials={
            "client_id": "client",
            "client_secret": "secret",
            "user_agent": "FenceSpace tests",
        },
        scraped_at=NOW,
    )

    assert [call[0] for call in session.calls] == ["POST", "GET"]
    assert session.calls[0][1] == "https://www.reddit.com/api/v1/access_token"
    assert session.calls[1][1] == "https://oauth.reddit.com/r/Fencing/new"
    assert discussions[0]["thread_id"] == "def456"
    assert discussions[0]["metadata"]["fetched_via"] == "api"


def test_match_fencers_is_exact_and_skips_ambiguous_names(capsys):
    from scrape_fencing_forums import attach_related_fencers, build_fencer_index

    discussions = [
        {
            "source": "reddit",
            "thread_id": "abc123",
            "title": "Lee Kiefer and Alex Massialas analysis",
            "summary": "Lee Kiefer and Alex Massialas analysis",
            "metadata": {},
        }
    ]
    fencer_index = build_fencer_index(
        [
            {"id": 1, "name": "Lee Kiefer", "country": "USA"},
            {"id": 2, "name": "Lee Kiefer", "country": "USA"},
            {"id": 3, "name": "Alex Massialas", "country": "USA"},
            {"id": 4, "name": "Lee", "country": "USA"},
        ]
    )

    attach_related_fencers(discussions, fencer_index)

    assert discussions[0]["related_fencer_ids"] == [3]
    captured = capsys.readouterr().out
    assert "ambiguous fencer match" in captured
    assert "Lee Kiefer" in captured


def test_upsert_discussions_uses_source_thread_conflict_and_minimizes_pii():
    from scrape_fencing_forums import upsert_discussion_rows

    client = FakeSupabase()
    row = {
        "source": "reddit",
        "thread_id": "abc123",
        "title": "Lee Kiefer point-in-line question",
        "url": "https://www.reddit.com/r/Fencing/comments/abc123/lee_kiefer_question/",
        "author_hash": "sha256:abc",
        "posted_at": "2026-06-01T09:30:00+00:00",
        "tags": ["Rules"],
        "related_fencer_ids": [1],
        "summary": "Lee Kiefer point-in-line question",
        "metadata": {"comments": 8},
        "scraped_at": NOW,
    }

    assert upsert_discussion_rows(client, [row], batch_size=10) == 1
    assert client.upserts == [
        {
            "table": "fs_forum_discussions",
            "rows": [row],
            "on_conflict": "source,thread_id",
        }
    ]
    assert "FoilFan42" not in str(client.upserts)


def test_scrape_forum_discussions_fetches_sources_matches_fencers_and_upserts():
    from scrape_fencing_forums import scrape_forum_discussions

    client = FakeSupabase(
        {
            "fs_fencers": [
                {"id": 10, "name": "Lee Kiefer", "country": "USA", "fie_id": "123"},
            ]
        }
    )
    session = FakeSession(
        [
            FakeResponse(text=REDDIT_RSS),
            FakeResponse(text="User-agent: *\nAllow: /forums/\n"),
            FakeResponse(text=FENCING_NET_RETIRED_HTML),
        ]
    )

    summary = scrape_forum_discussions(
        client,
        session=session,
        request_delay=0,
        scraped_at=NOW,
    )

    assert summary == {
        "sources_seen": 2,
        "discussions_found": 3,
        "rows_written": 3,
        "failed": 0,
        "skipped": 0,
    }
    assert client.upserts[0]["table"] == "fs_forum_discussions"
    assert client.upserts[0]["on_conflict"] == "source,thread_id"
    reddit_row = next(row for row in client.upserts[0]["rows"] if row["source"] == "reddit")
    assert reddit_row["related_fencer_ids"] == [10]
    assert all("FoilFan42" not in str(row) for row in client.upserts[0]["rows"])


def test_forum_discussions_migration_defines_privacy_safe_schema():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260602_forum_discussions.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_forum_discussions" in normalized
    assert "source text not null" in normalized
    assert "thread_id text not null" in normalized
    assert "author_hash text" in normalized
    assert "related_fencer_ids bigint[]" in normalized
    assert "metadata jsonb" in normalized
    assert "unique (source, thread_id)" in normalized
    assert "alter table public.fs_forum_discussions enable row level security" in normalized

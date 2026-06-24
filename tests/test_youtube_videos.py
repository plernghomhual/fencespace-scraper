import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"


YOUTUBE_SEARCH_RESPONSE = {
    "kind": "youtube#searchListResponse",
    "etag": "etag-search",
    "items": [
        {
            "kind": "youtube#searchResult",
            "etag": "etag-video",
            "id": {"kind": "youtube#video", "videoId": "abc123"},
            "snippet": {
                "publishedAt": "2026-05-25T18:30:00Z",
                "channelId": "UCfie",
                "title": "Lee Kiefer vs Alice Volpi - Women&#39;s Foil Final | Lima World Cup",
                "description": "Full bout from the Lima Women's Foil World Cup final.",
                "channelTitle": "FIE Fencing Channel",
                "liveBroadcastContent": "none",
                "thumbnails": {
                    "default": {"url": "https://i.ytimg.com/vi/abc123/default.jpg"},
                    "high": {"url": "https://i.ytimg.com/vi/abc123/hqdefault.jpg"},
                },
            },
        },
        {
            "kind": "youtube#searchResult",
            "id": {"kind": "youtube#channel", "channelId": "ignored"},
            "snippet": {"title": "FIE channel"},
        },
        {
            "kind": "youtube#searchResult",
            "id": {"kind": "youtube#video", "videoId": "private1"},
            "snippet": {
                "publishedAt": "2026-05-24T10:00:00Z",
                "title": "Private video",
                "channelTitle": "Hidden channel",
            },
        },
    ],
}


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = "ok"

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class FakeSession:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.pending_rows = None
        self.pending_conflict = None
        self.selected_columns = None
        self.range_bounds = None
        self.order_args = None

    def select(self, columns):
        self.selected_columns = columns
        return self

    def range(self, start, end):
        self.range_bounds = (start, end)
        return self

    def order(self, column, desc=False):
        self.order_args = (column, desc)
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
        rows = self.client.rows_by_table.get(self.name, [])
        if self.range_bounds is not None:
            start, end = self.range_bounds
            rows = rows[start : end + 1]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self, rows_by_table=None):
        self.rows_by_table = rows_by_table or {}
        self.upserts = []
        self.tables = []

    def table(self, name):
        self.tables.append(name)
        return FakeTable(self, name)


def test_parse_youtube_search_response_extracts_public_video_metadata_and_safe_links():
    from scrape_youtube_videos import SearchQuery, parse_youtube_search_response

    known_fencers = [
        {"id": "fencer-lee", "name": "Lee Kiefer"},
        {"id": "fencer-alice", "name": "Alice Volpi"},
    ]
    query = SearchQuery(
        text='fencing "Lee Kiefer" "Lima World Cup"',
        source_type="fencer",
        source_name="Lee Kiefer",
        tournament_id="tournament-lima",
    )

    rows = parse_youtube_search_response(
        YOUTUBE_SEARCH_RESPONSE,
        query=query,
        known_fencers=known_fencers,
        scraped_at=NOW,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["platform"] == "youtube"
    assert row["video_id"] == "abc123"
    assert row["title"] == "Lee Kiefer vs Alice Volpi - Women's Foil Final | Lima World Cup"
    assert row["channel"] == "FIE Fencing Channel"
    assert row["published_at"] == "2026-05-25T18:30:00+00:00"
    assert row["url"] == "https://www.youtube.com/watch?v=abc123"
    assert row["related_fencer_ids"] == ["fencer-lee", "fencer-alice"]
    assert row["tournament_id"] == "tournament-lima"
    assert "likely_match" in row["tags"]
    assert "foil" in row["tags"]
    assert row["metadata"]["classification"] == "likely_match"
    assert row["metadata"]["source_api"] == "youtube.search.list"
    assert row["metadata"]["query"] == 'fencing "Lee Kiefer" "Lima World Cup"'
    assert row["metadata"]["thumbnail_url"] == "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
    assert "privacy_status" not in row["metadata"]


def test_classify_video_separates_likely_match_videos_from_general_content():
    from scrape_youtube_videos import classify_video

    match_classification, match_tags = classify_video(
        "Lee Kiefer vs Alice Volpi - Women's Foil Final",
        "Full bout from the Lima World Cup.",
    )
    general_classification, general_tags = classify_video(
        "How to improve your fencing footwork",
        "Training tips for beginner foil fencers.",
    )
    interview_classification, interview_tags = classify_video(
        "Post-match interview: World Cup champion",
        "Reaction after the final.",
    )

    assert match_classification == "likely_match"
    assert {"likely_match", "foil", "final"}.issubset(match_tags)
    assert general_classification == "general"
    assert "general" in general_tags
    assert interview_classification == "general"
    assert "interview" in interview_tags


def test_fencer_matching_logs_ambiguity_and_refuses_duplicate_name_guess(capsys):
    from scrape_youtube_videos import match_related_fencers

    known_fencers = [
        {"id": "fencer-lee", "name": "Lee Kiefer"},
        {"id": "fencer-alice-a", "name": "Alice Volpi"},
        {"id": "fencer-alice-b", "name": "Alice Volpi"},
        {"id": "fencer-kim", "name": "Kim"},
    ]

    result = match_related_fencers(
        "Lee Kiefer vs Alice Volpi in the final. Kimono sponsor shown.",
        known_fencers,
        log_ambiguity=True,
    )

    assert result.related_ids == ["fencer-lee"]
    assert result.ambiguities == [
        {
            "name": "Alice Volpi",
            "candidate_ids": ["fencer-alice-a", "fencer-alice-b"],
        }
    ]
    assert "Ambiguous fencer match: Alice Volpi" in capsys.readouterr().out


def test_build_search_queries_uses_fencer_and_tournament_names():
    from scrape_youtube_videos import build_search_queries

    queries = build_search_queries(
        fencers=[
            {"id": "fencer-lee", "name": "Lee Kiefer"},
            {"id": "fencer-empty", "name": " "},
        ],
        tournaments=[
            {"id": "tournament-lima", "name": "Lima World Cup"},
            {"id": "tournament-blank", "name": None},
        ],
        fencer_limit=5,
        tournament_limit=5,
    )

    assert [query.text for query in queries] == [
        'fencing "Lee Kiefer"',
        'fencing "Lima World Cup"',
    ]
    assert queries[0].source_type == "fencer"
    assert queries[0].source_id == "fencer-lee"
    assert queries[1].source_type == "tournament"
    assert queries[1].tournament_id == "tournament-lima"


def test_search_youtube_uses_data_api_when_key_available():
    from scrape_youtube_videos import YOUTUBE_SEARCH_URL, SearchQuery, search_youtube

    session = FakeSession([FakeResponse(YOUTUBE_SEARCH_RESPONSE)])
    query = SearchQuery(text='fencing "Lee Kiefer"', source_type="fencer")

    payload = search_youtube(session, query, api_key="test-key", max_results=7)

    assert payload == YOUTUBE_SEARCH_RESPONSE
    call = session.calls[0]
    assert call["url"] == YOUTUBE_SEARCH_URL
    assert call["params"]["part"] == "snippet"
    assert call["params"]["type"] == "video"
    assert call["params"]["q"] == 'fencing "Lee Kiefer"'
    assert call["params"]["maxResults"] == 7
    assert call["params"]["key"] == "test-key"


def test_scrape_youtube_videos_without_api_key_is_dry_run_and_makes_no_api_call():
    from scrape_youtube_videos import scrape_youtube_videos

    client = FakeSupabase(
        rows_by_table={
            "fs_fencers": [{"id": "fencer-lee", "name": "Lee Kiefer"}],
            "fs_tournaments": [{"id": "tournament-lima", "name": "Lima World Cup"}],
        }
    )
    session = FakeSession([])

    summary = scrape_youtube_videos(
        client=client,
        session=session,
        api_key=None,
        log_run=False,
        update_state=False,
    )

    assert summary == {
        "queries": 0,
        "parsed": 0,
        "written": 0,
        "failed": 0,
        "skipped": 1,
        "dry_run": True,
    }
    assert session.calls == []
    assert client.tables == []
    assert client.upserts == []


def test_scrape_youtube_videos_with_api_key_searches_queries_and_upserts_public_metadata():
    from scrape_youtube_videos import scrape_youtube_videos

    client = FakeSupabase(
        rows_by_table={
            "fs_fencers": [{"id": "fencer-lee", "name": "Lee Kiefer"}],
            "fs_tournaments": [{"id": "tournament-lima", "name": "Lima World Cup"}],
        }
    )
    session = FakeSession(
        [
            FakeResponse(YOUTUBE_SEARCH_RESPONSE),
            FakeResponse(YOUTUBE_SEARCH_RESPONSE),
        ]
    )

    summary = scrape_youtube_videos(
        client=client,
        session=session,
        api_key="test-key",
        log_run=False,
        update_state=False,
        sleeper=lambda _: None,
    )

    assert summary == {
        "queries": 2,
        "parsed": 2,
        "written": 1,
        "failed": 0,
        "skipped": 0,
        "dry_run": False,
    }
    assert [call["params"]["q"] for call in session.calls] == [
        'fencing "Lee Kiefer"',
        'fencing "Lima World Cup"',
    ]
    assert len(client.upserts) == 1
    upsert = client.upserts[0]
    assert upsert["table"] == "fs_fencing_videos"
    assert upsert["on_conflict"] == "video_id"
    assert len(upsert["rows"]) == 1
    row = upsert["rows"][0]
    assert row["video_id"] == "abc123"
    assert row["tournament_id"] == "tournament-lima"
    assert row["metadata"]["source_api"] == "youtube.search.list"


def test_upsert_video_rows_dedupes_by_video_id_before_writing():
    from scrape_youtube_videos import upsert_video_rows

    client = FakeSupabase()
    duplicate_a = {
        "video_id": "abc123",
        "title": "Original",
        "url": "https://youtu.be/abc123",
        "related_fencer_ids": ["fencer-lee"],
        "tags": ["likely_match"],
        "metadata": {"first_query": "Lee Kiefer"},
    }
    duplicate_b = {
        "video_id": "abc123",
        "title": "Updated",
        "url": "https://youtu.be/abc123",
        "related_fencer_ids": ["fencer-alice"],
        "tags": ["foil"],
        "metadata": {"second_query": "Lima World Cup"},
    }
    unique = {"video_id": "def456", "title": "Second", "url": "https://youtu.be/def456"}

    written = upsert_video_rows(client, [duplicate_a, duplicate_b, unique], batch_size=10)

    expected_merged = {
        **duplicate_b,
        "related_fencer_ids": ["fencer-lee", "fencer-alice"],
        "tags": ["likely_match", "foil"],
        "metadata": {
            "first_query": "Lee Kiefer",
            "second_query": "Lima World Cup",
        },
    }
    assert written == 2
    assert client.upserts == [
        {
            "table": "fs_fencing_videos",
            "rows": [expected_merged, unique],
            "on_conflict": "video_id",
        }
    ]
    merged = client.upserts[0]["rows"][0]
    assert merged["title"] == "Updated"
    assert merged["related_fencer_ids"] == ["fencer-lee", "fencer-alice"]
    assert merged["tags"] == ["likely_match", "foil"]
    assert merged["metadata"] == {
        "first_query": "Lee Kiefer",
        "second_query": "Lima World Cup",
    }


def test_fencing_videos_migration_defines_table_indexes_and_dedupe_key():
    sql = Path("supabase/migrations/20260602_fencing_videos.sql").read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_fencing_videos" in normalized
    assert "platform text not null" in normalized
    assert "video_id text not null" in normalized
    assert "title text not null" in normalized
    assert "channel text" in normalized
    assert "published_at timestamptz" in normalized
    assert "url text not null" in normalized
    assert "related_fencer_ids uuid[]" in normalized
    assert "tournament_id uuid references public.fs_tournaments(id)" in normalized
    assert "tags text[]" in normalized
    assert "metadata jsonb not null default '{}'" in normalized
    assert "scraped_at timestamptz not null default now()" in normalized
    assert "unique (video_id)" in normalized
    assert "alter table public.fs_fencing_videos enable row level security" in normalized
    assert "create index if not exists fs_fencing_videos_published_at_idx" in normalized
    assert "create index if not exists fs_fencing_videos_related_fencer_ids_idx" in normalized

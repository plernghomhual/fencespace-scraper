import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


NOW = "2026-06-02T12:00:00+00:00"


YOUTUBE_SEARCH_FIXTURE = {
    "items": [
        {
            "id": {"kind": "youtube#video", "videoId": "good123"},
            "snippet": {
                "publishedAt": "2024-07-28T20:30:00Z",
                "channelTitle": "FIE Fencing Channel",
                "title": "Lee Kiefer vs Arianna Errigo - Paris 2024 foil fencing highlights",
                "description": "Olympic foil fencing highlights from Paris 2024.",
                "thumbnails": {
                    "default": {"url": "https://i.ytimg.com/vi/good123/default.jpg"},
                    "high": {"url": "https://i.ytimg.com/vi/good123/hqdefault.jpg"},
                },
            },
        },
        {
            "id": {"kind": "youtube#video", "videoId": "bad999"},
            "snippet": {
                "publishedAt": "2024-07-29T10:00:00Z",
                "channelTitle": "Home Repair Pro",
                "title": "Lee Kiefer privacy fence installation tips",
                "description": "Backyard wood fence installation and staining tutorial.",
                "thumbnails": {
                    "high": {"url": "https://example.test/fence.jpg"},
                },
            },
        },
    ]
}


YOUTUBE_VIDEOS_FIXTURE = {
    "items": [
        {
            "id": "good123",
            "contentDetails": {"duration": "PT12M34S"},
            "statistics": {"viewCount": "1000"},
        }
    ]
}


FENCERS = [
    {"id": "11111111-1111-1111-1111-111111111111", "name": "Lee Kiefer", "fie_id": "123", "country": "USA"},
    {"id": "22222222-2222-2222-2222-222222222222", "name": "Arianna Errigo", "fie_id": "456", "country": "ITA"},
]


TOURNAMENTS = [
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "name": "Paris 2024 Olympic Games",
        "source_id": "olympics-2024",
        "type": "OG",
        "category": "Senior",
    }
]


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.pending_rows = None
        self.pending_conflict = None
        self._range = None

    def select(self, columns):
        self.columns = columns
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def upsert(self, rows, on_conflict):
        self.pending_rows = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        if self.pending_rows is not None:
            self.client.upserts.append(
                (self.table_name, self.pending_rows, self.pending_conflict)
            )
            return FakeResponse(self.pending_rows)
        if self.table_name == "fs_fencers":
            return FakeResponse(FENCERS)
        if self.table_name == "fs_tournaments":
            return FakeResponse(TOURNAMENTS)
        return FakeResponse([])


class FakeSupabase:
    def __init__(self):
        self.upserts = []
        self.tables = []

    def table(self, table_name):
        self.tables.append(table_name)
        return FakeQuery(self, table_name)


class FailIfUsedSupabase:
    def table(self, table_name):
        raise AssertionError(f"Supabase should not be used in missing-key dry run: {table_name}")


class FakeYouTubeClient:
    def __init__(self):
        self.search_calls = []
        self.duration_calls = []

    def search(self, query, *, max_results=10, channel_id=None):
        self.search_calls.append((query, max_results, channel_id))
        return YOUTUBE_SEARCH_FIXTURE

    def video_details(self, video_ids):
        self.duration_calls.append(list(video_ids))
        return YOUTUBE_VIDEOS_FIXTURE


class FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeHTTPSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if "search" in url:
            return FakeHTTPResponse({"items": []})
        return FakeHTTPResponse(YOUTUBE_VIDEOS_FIXTURE)


def test_videos_migration_defines_table_columns_and_unique_provider_video_id():
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase"
        / "migrations"
        / "20260602_videos.sql"
    )

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_videos" in normalized
    assert "provider text not null" in normalized
    assert "video_id text not null" in normalized
    assert "title text not null" in normalized
    assert "channel text" in normalized
    assert "url text not null" in normalized
    assert "thumbnail text" in normalized
    assert "published_at timestamptz" in normalized
    assert "duration text" in normalized
    assert "related_fencer_ids uuid[] not null default '{}'" in normalized
    assert "related_tournament_ids uuid[] not null default '{}'" in normalized
    assert "tags text[] not null default '{}'" in normalized
    assert "source text not null" in normalized
    assert "metadata jsonb not null default '{}'::jsonb" in normalized
    assert "unique (provider, video_id)" in normalized
    assert "alter table public.fs_videos enable row level security" in normalized


def test_build_video_rows_parses_youtube_fixture_and_filters_false_positives():
    from aggregate_videos import RelatedTarget, build_video_rows

    rows = build_video_rows(
        YOUTUBE_SEARCH_FIXTURE["items"],
        related_targets=[
            RelatedTarget(kind="fencer", id=FENCERS[0]["id"], name="Lee Kiefer"),
            RelatedTarget(kind="tournament", id=TOURNAMENTS[0]["id"], name="Paris 2024 Olympic Games"),
        ],
        detail_by_id={"good123": {"duration": "PT12M34S", "duration_seconds": 754}},
        scraped_at=NOW,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "youtube"
    assert row["video_id"] == "good123"
    assert row["title"] == "Lee Kiefer vs Arianna Errigo - Paris 2024 foil fencing highlights"
    assert row["channel"] == "FIE Fencing Channel"
    assert row["url"] == "https://www.youtube.com/watch?v=good123"
    assert row["thumbnail"] == "https://i.ytimg.com/vi/good123/hqdefault.jpg"
    assert row["published_at"] == "2024-07-28T20:30:00Z"
    assert row["duration"] == "PT12M34S"
    assert row["related_fencer_ids"] == [FENCERS[0]["id"]]
    assert row["related_tournament_ids"] == [TOURNAMENTS[0]["id"]]
    assert "fencer:lee kiefer" in row["tags"]
    assert "tournament:paris 2024 olympic games" in row["tags"]
    assert row["metadata"]["duration_seconds"] == 754
    assert row["metadata"]["provider_payload"]["id"]["videoId"] == "good123"


def test_build_search_targets_uses_known_fencers_tournaments_and_official_channels():
    from aggregate_videos import build_search_targets

    targets = build_search_targets(FENCERS, TOURNAMENTS, include_official_channels=True)

    assert ("fencer", FENCERS[0]["id"], "Lee Kiefer", "fencing Lee Kiefer") in [
        (target.kind, target.id, target.name, target.query) for target in targets
    ]
    assert ("tournament", TOURNAMENTS[0]["id"], "Paris 2024 Olympic Games", "fencing Paris 2024 Olympic Games") in [
        (target.kind, target.id, target.name, target.query) for target in targets
    ]
    assert any(target.kind == "official_channel" and "FIE Fencing" in target.name for target in targets)


def test_generic_tournament_names_keep_enough_tokens_to_match():
    from aggregate_videos import RelatedTarget, build_video_rows

    rows = build_video_rows(
        [
            {
                "id": {"kind": "youtube#video", "videoId": "worlds2025"},
                "snippet": {
                    "publishedAt": "2025-07-30T18:00:00Z",
                    "channelTitle": "FIE Fencing Channel",
                    "title": "2025 World Fencing Championships women's epee highlights",
                    "description": "Final bouts from the world championships.",
                    "thumbnails": {"default": {"url": "https://i.ytimg.com/vi/worlds2025/default.jpg"}},
                },
            }
        ],
        related_targets=[
            RelatedTarget(
                kind="tournament",
                id="44444444-4444-4444-4444-444444444444",
                name="World Championships",
            )
        ],
        scraped_at=NOW,
    )

    assert len(rows) == 1
    assert rows[0]["related_tournament_ids"] == ["44444444-4444-4444-4444-444444444444"]


def test_aggregate_videos_dedupes_across_queries_and_upserts_provider_video_id():
    from aggregate_videos import aggregate_videos

    fake_supabase = FakeSupabase()
    fake_youtube = FakeYouTubeClient()

    summary = aggregate_videos(
        fake_supabase,
        api_key="test-key",
        youtube_client=fake_youtube,
        fencer_limit=1,
        tournament_limit=1,
        max_results_per_query=2,
        log_run=False,
        update_state=False,
        scraped_at=NOW,
    )

    assert summary["dry_run"] is False
    assert summary["queries_run"] >= 2
    assert summary["videos_found"] == 1
    assert summary["rows_written"] == 1
    assert fake_supabase.upserts == [
        (
            "fs_videos",
            [
                {
                    "provider": "youtube",
                    "video_id": "good123",
                    "title": "Lee Kiefer vs Arianna Errigo - Paris 2024 foil fencing highlights",
                    "channel": "FIE Fencing Channel",
                    "url": "https://www.youtube.com/watch?v=good123",
                    "thumbnail": "https://i.ytimg.com/vi/good123/hqdefault.jpg",
                    "published_at": "2024-07-28T20:30:00Z",
                    "duration": "PT12M34S",
                    "related_fencer_ids": [FENCERS[0]["id"]],
                    "related_tournament_ids": [TOURNAMENTS[0]["id"]],
                    "tags": [
                        "fencer:lee kiefer",
                        "tournament:paris 2024 olympic games",
                    ],
                    "source": "youtube_data_api",
                    "metadata": {
                        "duration_seconds": 754,
                        "provider_payload": YOUTUBE_SEARCH_FIXTURE["items"][0],
                        "statistics": {"viewCount": "1000"},
                        "matched_targets": [
                            {"kind": "fencer", "id": FENCERS[0]["id"], "name": "Lee Kiefer"},
                            {"kind": "tournament", "id": TOURNAMENTS[0]["id"], "name": "Paris 2024 Olympic Games"},
                        ],
                    },
                    "scraped_at": NOW,
                }
            ],
            "provider,video_id",
        )
    ]


def test_missing_youtube_key_returns_dry_run_without_supabase_reads_or_upserts():
    from aggregate_videos import aggregate_videos

    summary = aggregate_videos(
        FailIfUsedSupabase(),
        api_key=None,
        log_run=False,
        update_state=False,
        scraped_at=NOW,
    )

    assert summary == {
        "provider": "youtube",
        "dry_run": True,
        "queries_run": 0,
        "videos_found": 0,
        "rows_written": 0,
        "failed": 0,
        "skipped": 1,
        "reason": "missing YOUTUBE_API_KEY",
    }


def test_youtube_api_client_uses_metadata_endpoints_and_rate_limiter():
    from aggregate_videos import RateLimiter, YouTubeDataAPI

    sleeps = []
    times = iter([0.0, 0.0, 0.5, 0.5])
    limiter = RateLimiter(
        min_interval_seconds=1.0,
        clock=lambda: next(times),
        sleeper=sleeps.append,
    )
    session = FakeHTTPSession()
    client = YouTubeDataAPI("test-key", session=session, rate_limiter=limiter)

    client.search("fencing Lee Kiefer", max_results=2)
    client.video_details(["good123"])

    assert sleeps == [1.0]
    assert session.calls[0][0] == "https://www.googleapis.com/youtube/v3/search"
    assert session.calls[0][1]["part"] == "snippet"
    assert session.calls[0][1]["type"] == "video"
    assert session.calls[0][1]["q"] == "fencing Lee Kiefer"
    assert session.calls[0][1]["key"] == "test-key"
    assert session.calls[1][0] == "https://www.googleapis.com/youtube/v3/videos"
    assert session.calls[1][1]["part"] == "contentDetails,statistics"
    assert session.calls[1][1]["id"] == "good123"

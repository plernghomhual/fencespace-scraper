import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


PROVIDER_FIXTURE = {
    "aweme_list": [
        {
            "aweme_id": "7351234567890123456",
            "desc": "Lee Kiefer breaks down a foil touch from Paris. #Fencing #TeamUSA",
            "create_time": 1717000000,
            "author": {"unique_id": "leekiefer", "nickname": "Lee Kiefer"},
            "statistics": {
                "play_count": 12750,
                "digg_count": 830,
                "comment_count": 24,
                "share_count": 51,
            },
            "share_url": "https://www.tiktok.com/@leekiefer/video/7351234567890123456",
        }
    ]
}


KNOWN_FENCERS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Lee Kiefer",
        "country": "USA",
        "metadata": {"social_handles": {"tiktok": "leekiefer"}},
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "name": "Italo Santelli",
        "country": "ITA",
        "metadata": {"tags": ["italosantelli"]},
    },
]


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self._rows = None
        self._on_conflict = None

    def select(self, columns):
        self.client.selects.append((self.name, columns))
        return self

    def limit(self, value):
        self.client.limits.append(value)
        return self

    def upsert(self, rows, on_conflict):
        self._rows = rows
        self._on_conflict = on_conflict
        return self

    def execute(self):
        if self._rows is not None:
            self.client.upserts.append((self.name, self._rows, self._on_conflict))
        if self.name == "fs_fencers":
            return FakeResult(self.client.fencers)
        return FakeResult([])


class FakeSupabase:
    def __init__(self, fencers=None):
        self.fencers = fencers or []
        self.upserts = []
        self.selects = []
        self.limits = []

    def table(self, name):
        return FakeTable(self, name)


class FakeLogger:
    instances: list[object] = []

    def __init__(self, module):
        self.module = module
        self.completed = None
        self.errors = []
        FakeLogger.instances.append(self)

    def start(self):
        return self

    def complete(self, written=0, failed=0, skipped=0, metadata=None):
        self.completed = {
            "written": written,
            "failed": failed,
            "skipped": skipped,
            "metadata": metadata or {},
        }

    def error(self, exc_str):
        self.errors.append(exc_str)


def test_no_key_defaults_to_fixture_dry_run_without_supabase_writes(monkeypatch):
    import scrape_tiktok_fencing as tk

    client = FakeSupabase(fencers=KNOWN_FENCERS)
    state_updates = []
    FakeLogger.instances.clear()
    monkeypatch.setattr(tk, "set_state", lambda source, key, value: state_updates.append((source, key, value)))

    summary = tk.collect_tiktok_fencing(
        client=client,
        env={},
        logger_factory=FakeLogger,
        update_state=True,
    )

    assert summary["dry_run"] is True
    assert summary["provider"] == "fixture"
    assert summary["videos"] >= 1
    assert summary["would_write"] == summary["videos"]
    assert summary["written"] == 0
    assert client.upserts == []
    assert state_updates[-1][0] == "scrape_tiktok_fencing"
    assert state_updates[-1][1] == "last_run"
    assert FakeLogger.instances[0].completed["metadata"]["dry_run"] is True


def test_api_fixture_parser_normalizes_public_video_metadata():
    import scrape_tiktok_fencing as tk

    videos = tk.parse_provider_payload(PROVIDER_FIXTURE)
    row = tk.build_video_row(
        videos[0],
        target=tk.Target(kind="hashtag", value="Fencing"),
        known_fencers=KNOWN_FENCERS,
        provider_name="fixture-provider",
    )

    assert row["platform"] == "tiktok"
    assert row["video_id"] == "7351234567890123456"
    assert row["url"] == "https://www.tiktok.com/@leekiefer/video/7351234567890123456"
    assert row["creator"] == "Lee Kiefer"
    assert row["creator_handle"] == "leekiefer"
    assert row["caption_snippet"] == "Lee Kiefer breaks down a foil touch from Paris. #Fencing #TeamUSA"
    assert row["posted_at"] == "2024-05-29T16:26:40+00:00"
    assert row["metrics"] == {"views": 12750, "likes": 830, "comments": 24, "shares": 51}
    assert row["related_fencers"] == [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "Lee Kiefer", "country": "USA"}
    ]
    assert row["provider"] == "fixture-provider"


def test_malformed_provider_video_without_id_or_url_is_skipped():
    import scrape_tiktok_fencing as tk

    videos = tk.parse_provider_payload({"aweme_list": [{"id": "", "desc": "No usable TikTok URL"}]})
    row = tk.build_video_row(
        videos[0],
        target=tk.Target(kind="hashtag", value="Fencing"),
        known_fencers=KNOWN_FENCERS,
        provider_name="fixture-provider",
    )

    assert row is None


def test_hashtag_and_fencer_matching_uses_boundaries_handles_and_tags():
    import scrape_tiktok_fencing as tk

    matches = tk.match_related_fencers(
        "Lee Kiefer and @ItaloSantelli inspired a new lesson. #TeamUSA #Fencing",
        hashtags=["TeamUSA", "Fencing"],
        known_fencers=KNOWN_FENCERS,
    )

    assert matches == [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "Lee Kiefer", "country": "USA"},
        {"id": "22222222-2222-2222-2222-222222222222", "name": "Italo Santelli", "country": "ITA"},
    ]


def test_api_provider_rate_limits_and_wraps_provider_errors():
    import scrape_tiktok_fencing as tk

    class Response:
        status_code = 429
        text = '{"message":"too many requests"}'

        def json(self):
            return {"message": "too many requests"}

    class Session:
        def __init__(self):
            self.calls = []

        def get(self, url, params=None, headers=None, timeout=None):
            self.calls.append((url, params, headers, timeout))
            return Response()

    class Limiter:
        def __init__(self):
            self.calls = []

        def wait(self, domain):
            self.calls.append(("wait", domain))

        def record_success(self, domain):
            self.calls.append(("success", domain))

        def record_failure(self, domain):
            self.calls.append(("failure", domain))

    session = Session()
    limiter = Limiter()
    provider = tk.TikTokAPIProvider(
        base_url="https://provider.example/api",
        api_key="test-key",
        session=session,
        rate_limiter=limiter,
    )

    with pytest.raises(tk.ProviderError) as exc:
        provider.fetch_target(tk.Target(kind="hashtag", value="Fencing"), limit=10)

    assert "HTTP 429" in str(exc.value)
    assert limiter.calls == [("wait", "provider.example"), ("failure", "provider.example")]
    assert session.calls[0][1] == {"type": "hashtag", "q": "Fencing", "limit": 10}


def test_provider_errors_are_counted_without_writes(monkeypatch):
    import scrape_tiktok_fencing as tk

    class ErrorProvider:
        name = "failing-provider"

        def fetch_target(self, target, limit):
            raise tk.ProviderError("provider unavailable")

    client = FakeSupabase(fencers=KNOWN_FENCERS)
    monkeypatch.setattr(tk, "set_state", lambda source, key, value: None)

    summary = tk.collect_tiktok_fencing(
        client=client,
        provider=ErrorProvider(),
        targets=[tk.Target(kind="hashtag", value="Fencing")],
        dry_run=False,
        logger_factory=FakeLogger,
        update_state=True,
    )

    assert summary["failed"] == 1
    assert summary["written"] == 0
    assert summary["provider_errors"] == ["hashtag:Fencing: provider unavailable"]
    assert client.upserts == []


def test_migration_defines_tiktok_video_storage_table():
    sql = Path("supabase/migrations/20260602_tiktok_fencing_videos.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS fs_tiktok_fencing_videos" in sql
    assert "UNIQUE (platform, video_id)" in sql
    assert "related_fencers jsonb" in sql
    assert "metrics jsonb" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql

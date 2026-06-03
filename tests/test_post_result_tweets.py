import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.action = None
        self.columns = None
        self.filters = []
        self.ordering = []
        self.limit_value = None

    def select(self, columns):
        self.action = "select"
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def order(self, column, desc=False):
        self.ordering.append((column, desc))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        self.client.selects.append(
            {
                "table": self.name,
                "columns": self.columns,
                "filters": self.filters,
                "ordering": self.ordering,
                "limit": self.limit_value,
            }
        )
        if self.name == "fs_tournaments":
            rows = list(self.client.tournaments)
            if self.limit_value is not None:
                rows = rows[: self.limit_value]
            return FakeResult(rows)
        if self.name == "fs_results":
            tournament_id = next(
                value for op, column, value in self.filters if op == "eq" and column == "tournament_id"
            )
            rows = list(self.client.results_by_tournament.get(tournament_id, []))
            rows.sort(key=lambda row: row.get("rank") or row.get("placement") or 9999)
            if self.limit_value is not None:
                rows = rows[: self.limit_value]
            return FakeResult(rows)
        return FakeResult([])


class FakeSupabase:
    def __init__(self, tournaments=None, results_by_tournament=None):
        self.tournaments = tournaments or []
        self.results_by_tournament = results_by_tournament or {}
        self.selects = []

    def table(self, name):
        return FakeTable(self, name)


class FakeProvider:
    def __init__(self):
        self.messages = []

    def post(self, message):
        self.messages.append(message)
        return {"id": f"tweet-{len(self.messages)}"}


TOURNAMENT = {
    "id": "t-1",
    "source_id": "fie:2026:123",
    "name": "Budapest Grand Prix",
    "season": 2026,
    "start_date": "2026-03-12",
    "end_date": "2026-03-14",
    "weapon": "Sabre",
    "gender": "Men",
    "category": "Senior",
    "type": "FIE",
    "city": "Budapest",
    "country": "Hungary",
    "metadata": {"result_url": "https://fie.org/competitions/2026/123/results"},
    "has_results": True,
}

RESULT_ROWS = [
    {"rank": 1, "name": "Áron Szilágyi", "nationality": "HUN", "medal": "Gold"},
    {"rank": 2, "name": "Sanguk Oh", "nationality": "KOR", "medal": "Silver"},
    {"rank": 3, "name": "Eli Dershwitz", "nationality": "USA", "medal": "Bronze"},
    {"rank": 4, "name": "Max Hartung", "nationality": "GER"},
]


def test_format_result_post_preserves_unicode_names_and_validates_message():
    from post_result_tweets import ResultSummary, effective_x_length, format_result_post, validate_post_text

    summary = ResultSummary(
        key="fie:2026:123",
        tournament_id="t-1",
        title="Budapest Grand Prix",
        event="Senior Men's Sabre",
        location="Budapest, Hungary",
        result_url="https://fie.org/competitions/2026/123/results",
        podium=[
            {"rank": 1, "name": "Áron Szilágyi", "country": "HUN"},
            {"rank": 2, "name": "Sanguk Oh", "country": "KOR"},
            {"rank": 3, "name": "Eli Dershwitz", "country": "USA"},
        ],
    )

    message = format_result_post(summary)

    assert "Áron Szilágyi" in message
    assert "Senior Men's Sabre" in message
    assert "1. Áron Szilágyi (HUN)" in message
    assert "https://fie.org/competitions/2026/123/results" in message
    assert "#FenceSpace" in message
    assert "#Fencing" in message
    assert effective_x_length(message) <= 280
    assert validate_post_text(message) == []


def test_validate_post_text_rejects_long_messages_bad_links_and_bad_hashtags():
    from post_result_tweets import validate_post_text

    long_message = "Result: " + ("A" * 280)
    bad_link = "Result\nftp://example.com/results\n#FenceSpace"
    bad_hashtag = "Result\nhttps://example.com/results\n#bad-tag"

    assert "message exceeds 280 X characters" in validate_post_text(long_message)
    assert "unsupported link: ftp://example.com/results" in validate_post_text(bad_link)
    assert "invalid hashtag: #bad-tag" in validate_post_text(bad_hashtag)


def test_duplicate_suppression_skips_previously_posted_result(monkeypatch):
    import post_result_tweets as tweets

    client = FakeSupabase(tournaments=[TOURNAMENT], results_by_tournament={"t-1": RESULT_ROWS})
    provider = FakeProvider()
    state = {("result_tweets", "posted_result_keys"): ["fie:2026:123"]}
    monkeypatch.setattr(tweets, "get_state", lambda source, key: state.get((source, key)))
    monkeypatch.setattr(tweets, "set_state", lambda source, key, value: state.__setitem__((source, key), value))

    summary = tweets.post_result_tweets(client=client, provider=provider, live=False, log_run=False)

    assert summary["dry_run"] is True
    assert summary["generated"] == 0
    assert summary["skipped_duplicates"] == 1
    assert provider.messages == []
    assert state[("result_tweets", "posted_result_keys")] == ["fie:2026:123"]


def test_dry_run_without_credentials_generates_post_and_does_not_call_provider(monkeypatch):
    import post_result_tweets as tweets

    client = FakeSupabase(tournaments=[TOURNAMENT], results_by_tournament={"t-1": RESULT_ROWS})
    provider = FakeProvider()
    state = {}
    monkeypatch.delenv("RESULT_TWEETS_LIVE", raising=False)
    monkeypatch.delenv("X_API_BEARER_TOKEN", raising=False)
    monkeypatch.setattr(tweets, "get_state", lambda source, key: state.get((source, key)))
    monkeypatch.setattr(tweets, "set_state", lambda source, key, value: state.__setitem__((source, key), value))

    summary = tweets.post_result_tweets(client=client, provider=provider, live=False, log_run=False)

    assert summary["dry_run"] is True
    assert summary["generated"] == 1
    assert summary["posted"] == 0
    assert provider.messages == []
    assert "posted_result_keys" not in {key for _, key in state}
    assert summary["posts"][0]["message"].count("Áron Szilágyi") == 1


def test_live_post_requires_explicit_credentials(monkeypatch):
    import post_result_tweets as tweets

    client = FakeSupabase(tournaments=[TOURNAMENT], results_by_tournament={"t-1": RESULT_ROWS})
    monkeypatch.delenv("RESULT_TWEETS_LIVE", raising=False)
    monkeypatch.delenv("X_API_BEARER_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="RESULT_TWEETS_LIVE=1"):
        tweets.post_result_tweets(client=client, provider=FakeProvider(), live=True, log_run=False)


def test_live_post_uses_mock_provider_and_marks_state_after_success(monkeypatch):
    import post_result_tweets as tweets

    client = FakeSupabase(tournaments=[TOURNAMENT], results_by_tournament={"t-1": RESULT_ROWS})
    provider = FakeProvider()
    state = {}
    monkeypatch.setenv("RESULT_TWEETS_LIVE", "1")
    monkeypatch.setenv("X_API_BEARER_TOKEN", "test-token-never-printed")
    monkeypatch.setattr(tweets, "get_state", lambda source, key: state.get((source, key)))
    monkeypatch.setattr(tweets, "set_state", lambda source, key, value: state.__setitem__((source, key), value))

    summary = tweets.post_result_tweets(
        client=client,
        provider=provider,
        live=True,
        log_run=False,
        now=datetime(2026, 3, 14, 20, 0, tzinfo=timezone.utc),
    )

    assert summary["dry_run"] is False
    assert summary["posted"] == 1
    assert provider.messages == [summary["posts"][0]["message"]]
    assert state[("result_tweets", "posted_result_keys")] == ["fie:2026:123"]
    delivery_log = state[("result_tweets", "delivery_log")]
    assert delivery_log["fie:2026:123"]["provider_post_id"] == "tweet-1"
    assert delivery_log["fie:2026:123"]["posted_at"] == "2026-03-14T20:00:00+00:00"

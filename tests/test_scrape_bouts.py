import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scrape_bouts import (
    build_bout_row,
    extract_bouts,
    extract_pool_bouts,
    extract_tableau_bouts,
    make_bout_id,
    normalize_fie_id,
    to_int,
)


POOL_WINDOW_DATA = {
    "_pools": [
        {
            "poolId": 1,
            "rows": [
                {
                    "fencerId": "101",
                    "matches": [
                        None,
                        {"score": 5, "v": True},
                        {"score": 5, "v": True},
                    ],
                },
                {
                    "fencerId": "102",
                    "matches": [
                        {"score": 3, "v": False},
                        None,
                        {"score": 4, "v": False},
                    ],
                },
                {
                    "fencerId": "103",
                    "matches": [
                        {"score": 4, "v": False},
                        {"score": 5, "v": True},
                        None,
                    ],
                },
            ],
        }
    ]
}

EMPTY_WINDOW_DATA: dict[str, object] = {}


def test_extract_pool_bouts_returns_rows():
    rows = extract_pool_bouts("t1", POOL_WINDOW_DATA)
    assert len(rows) == 3  # C(3,2)=3 bouts for 3 fencers


def test_extract_pool_bouts_fields():
    rows = extract_pool_bouts("t1", POOL_WINDOW_DATA)
    bout = next((r for r in rows if r["fie_fencer_id_a"] == "101" and r["fie_fencer_id_b"] == "102"), None)
    assert bout is not None, f"Expected bout 101 vs 102, got: {[(r['fie_fencer_id_a'], r['fie_fencer_id_b']) for r in rows]}"
    assert bout["tournament_id"] == "t1"
    assert bout["score_a"] == 5
    assert bout["score_b"] == 3
    assert bout["round"] is not None


def test_extract_bouts_deduplicates():
    rows = extract_bouts("t1", POOL_WINDOW_DATA)
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))


def test_extract_bouts_empty_window_returns_empty():
    assert extract_bouts("t1", EMPTY_WINDOW_DATA) == []


def test_build_bout_row_requires_both_fencer_ids():
    assert build_bout_row("t1", "k1", "Pool 1", None, "102", 5, 3, None) is None
    assert build_bout_row("t1", "k1", "Pool 1", "101", None, 5, 3, None) is None


def test_build_bout_row_requires_at_least_one_score():
    assert build_bout_row("t1", "k1", "Pool 1", "101", "102", None, None, None) is None


def test_build_bout_row_infers_winner_from_scores():
    row = build_bout_row("t1", "k1", "Pool 1", "101", "102", 5, 3, None)
    assert row is not None
    assert row["_winner_fie_id"] == "101"


def test_build_bout_row_id_is_deterministic():
    row1 = build_bout_row("t1", "key", "Pool 1", "101", "102", 5, 3, None)
    row2 = build_bout_row("t1", "key", "Pool 1", "101", "102", 5, 3, None)
    assert row1["id"] == row2["id"]


def test_build_bout_row_different_keys_produce_different_ids():
    row1 = build_bout_row("t1", "key1", "Pool 1", "101", "102", 5, 3, None)
    row2 = build_bout_row("t1", "key2", "Pool 1", "101", "102", 5, 3, None)
    assert row1["id"] != row2["id"]


def test_normalize_fie_id_converts_float_string():
    assert normalize_fie_id("101.0") == "101"


def test_normalize_fie_id_none_returns_none():
    assert normalize_fie_id(None) is None
    assert normalize_fie_id("") is None


def test_to_int_converts_int():
    assert to_int(5) == 5
    assert to_int("7") == 7
    assert to_int(None) is None
    assert to_int("") is None


# ── HTTP 500 resilience ──────────────────────────────────────────────────────

class _MockSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self._calls = 0

    def get(self, url, **kwargs):
        resp = self._responses[self._calls % len(self._responses)]
        self._calls += 1
        return resp


class _OkResponse:
    status_code = 200

    def raise_for_status(self):
        pass

    @property
    def text(self):
        return "<html></html>"


class _ServerErrorResponse:
    status_code = 500

    def raise_for_status(self):
        import requests
        raise requests.exceptions.HTTPError("500 Server Error")

    @property
    def text(self):
        return ""


def test_http_500_does_not_abort_tournament_loop(monkeypatch):
    """One HTTP 500 must not stop the scraper from processing subsequent tournaments."""
    import scrape_bouts

    scraped_ids = []
    failed_ids = []

    tournaments = [
        {"id": "t1", "name": "First", "season": "2024", "competition_url_id": "100", "end_date": "2024-01-01", "has_results": True},
        {"id": "t2", "name": "Second", "season": "2024", "competition_url_id": "200", "end_date": "2024-01-02", "has_results": True},
        {"id": "t3", "name": "Third", "season": "2024", "competition_url_id": "300", "end_date": "2024-01-03", "has_results": True},
    ]

    session = _MockSession([_ServerErrorResponse(), _OkResponse(), _OkResponse()])

    call_count = [0]

    def fake_fetch_competition_page(sess, season, url_id):
        resp = session.get(f"https://fie.org/{season}/{url_id}")
        resp.raise_for_status()
        return f"https://fie.org/{season}/{url_id}", resp.text

    monkeypatch.setattr(scrape_bouts, "fetch_competition_page", fake_fetch_competition_page)
    monkeypatch.setattr(scrape_bouts, "fetch_all_tournaments", lambda _: tournaments)
    monkeypatch.setattr(scrape_bouts, "fetch_existing_bout_tournament_ids", lambda _: set())
    monkeypatch.setattr(scrape_bouts, "batch_upsert_bouts", lambda client, rows: None)
    monkeypatch.setattr(scrape_bouts, "load_fencer_map", lambda client, rows: {})
    monkeypatch.setattr(scrape_bouts, "attach_fencer_ids", lambda rows, fmap: rows)

    class FakeRunLog:
        def start(self): return self
        def complete(self, **kw): pass
        def error(self, msg): pass

    class FakeLogger:
        def __init__(self, name): pass
        def start(self): return FakeRunLog()

    monkeypatch.setattr(scrape_bouts, "ScraperRunLogger", FakeLogger)
    monkeypatch.setattr(scrape_bouts, "get_supabase_client", lambda: None)

    import time
    monkeypatch.setattr(time, "sleep", lambda _: None)

    scrape_bouts.scrape_bouts()

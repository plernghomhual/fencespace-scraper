import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    @property
    def positive_sleeps(self):
        return [seconds for seconds in self.sleeps if seconds > 0]


def patch_clock(monkeypatch, rate_limiter_module, now=100.0):
    clock = FakeClock(now=now)
    monkeypatch.setattr(rate_limiter_module.time, "time", clock.time)
    monkeypatch.setattr(rate_limiter_module.time, "sleep", clock.sleep)
    return clock


def test_wait_enforces_requested_rps_within_ten_percent(monkeypatch):
    import scripts.rate_limiter as rate_limiter

    clock = patch_clock(monkeypatch, rate_limiter)
    monkeypatch.setattr(rate_limiter.random, "uniform", lambda _low, _high: 0.0)
    limiter = rate_limiter.RateLimiter(default_rps=2.0, jitter=0.0)

    limiter.wait("fie.org")
    clock.now += 0.2
    limiter.wait("fie.org")

    interval_sleep = clock.positive_sleeps[0]
    assert math.isclose(interval_sleep, 0.3, rel_tol=0.10)
    assert math.isclose(limiter._last_request["fie.org"], 100.5, rel_tol=0.10)


def test_domains_are_limited_independently(monkeypatch):
    import scripts.rate_limiter as rate_limiter

    clock = patch_clock(monkeypatch, rate_limiter)
    monkeypatch.setattr(rate_limiter.random, "uniform", lambda _low, _high: 0.0)
    limiter = rate_limiter.RateLimiter(default_rps=1.0, jitter=0.0)

    limiter.wait("fie.org")
    limiter.wait("engarde-service.com")

    assert clock.positive_sleeps == []


def test_jitter_uses_configured_range_and_updates_last_request_after_sleep(monkeypatch):
    import scripts.rate_limiter as rate_limiter

    clock = patch_clock(monkeypatch, rate_limiter)
    jitter_calls = []

    def fake_uniform(low, high):
        jitter_calls.append((low, high))
        return 0.07

    monkeypatch.setattr(rate_limiter.random, "uniform", fake_uniform)
    limiter = rate_limiter.RateLimiter(default_rps=1.0, jitter=0.2)

    limiter.wait("askfred.net")

    assert jitter_calls == [(0.0, 0.2)]
    assert clock.positive_sleeps == [0.07]
    assert limiter._last_request["askfred.net"] == 100.07


def test_backoff_starts_after_three_failures_and_resets_on_success(monkeypatch):
    import scripts.rate_limiter as rate_limiter

    clock = patch_clock(monkeypatch, rate_limiter)
    limiter = rate_limiter.RateLimiter(backoff=2.0)

    limiter.record_failure("fie.org")
    limiter.record_failure("fie.org")
    limiter.record_failure("fie.org")
    assert clock.positive_sleeps == []

    limiter.record_failure("fie.org")
    limiter.record_failure("fie.org")
    assert clock.positive_sleeps == [8.0, 10.0]

    limiter.record_success("fie.org")
    limiter.record_failure("fie.org")
    assert clock.positive_sleeps == [8.0, 10.0]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"default_rps": 0.0},
        {"default_rps": -1.0},
        {"jitter": -0.1},
        {"backoff": -1.0},
    ],
)
def test_constructor_rejects_invalid_limits(kwargs):
    from scripts.rate_limiter import RateLimiter

    with pytest.raises(ValueError):
        RateLimiter(**kwargs)


def test_wait_rejects_non_positive_override_rps():
    from scripts.rate_limiter import RateLimiter

    limiter = RateLimiter()

    with pytest.raises(ValueError):
        limiter.wait("fie.org", rps=0.0)


def test_call_waits_and_returns_self(monkeypatch):
    import scripts.rate_limiter as rate_limiter

    clock = patch_clock(monkeypatch, rate_limiter)
    monkeypatch.setattr(rate_limiter.random, "uniform", lambda _low, _high: 0.0)
    limiter = rate_limiter.RateLimiter(default_rps=1.0, jitter=0.0)

    result = limiter("fie.org")

    assert result is limiter
    assert limiter._last_request["fie.org"] == clock.now

import random
import time
from collections import defaultdict


class RateLimiter:
    """Per-domain rate limiter with jitter and backoff."""

    def __init__(
        self,
        default_rps: float = 1.0,
        jitter: float = 0.1,
        backoff: float = 2.0,
    ):
        if default_rps <= 0:
            raise ValueError("default_rps must be greater than 0")
        if jitter < 0:
            raise ValueError("jitter must be greater than or equal to 0")
        if backoff < 0:
            raise ValueError("backoff must be greater than or equal to 0")

        self.default_rps = default_rps
        self.jitter = jitter
        self.backoff = backoff
        self._last_request = defaultdict(float)
        self._failures = defaultdict(int)

    def wait(self, domain: str, rps: float | None = None):
        """Sleep if needed to maintain rps for domain."""
        effective_rps = self.default_rps if rps is None else rps
        if effective_rps <= 0:
            raise ValueError("rps must be greater than 0")

        elapsed = time.time() - self._last_request[domain]
        min_interval = 1.0 / effective_rps
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        if self.jitter:
            time.sleep(random.uniform(0.0, self.jitter))

        self._last_request[domain] = time.time()

    def record_failure(self, domain: str):
        """Record a failure for this domain (increases backoff)."""
        self._failures[domain] += 1
        failures = self._failures[domain]
        if failures > 3 and self.backoff:
            time.sleep(self.backoff * failures)

    def record_success(self, domain: str):
        """Reset failure count on success."""
        self._failures[domain] = 0

    def __call__(self, domain: str, rps: float | None = None):
        """Wait for domain and return self for fluent usage."""
        self.wait(domain, rps)
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

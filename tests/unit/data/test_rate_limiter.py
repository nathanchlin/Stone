import time

from stone.data.fetchers._rate_limiter import RateLimiter, rate_limited


def test_rate_limiter_allows_burst_then_throttles():
    limiter = RateLimiter(max_rate=10.0)
    start = time.monotonic()
    for _ in range(3):
        limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.15


def test_rate_limited_decorator_applies_to_function():
    limiter = RateLimiter(max_rate=10.0)
    calls = []

    @rate_limited(limiter)
    def double(x):
        calls.append(x)
        return x * 2

    assert double(5) == 10
    assert calls == [5]

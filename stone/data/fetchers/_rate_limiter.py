"""Simple rate limiter helpers for outbound data fetches."""

import time
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class RateLimiter:
    """Enforce a minimum interval between calls."""

    def __init__(self, max_rate: float):
        if max_rate <= 0:
            raise ValueError("max_rate must be positive")
        self.min_interval = 1.0 / max_rate
        self._last_time = 0.0

    def acquire(self) -> None:
        now = time.monotonic()
        wait = self.min_interval - (now - self._last_time)
        if wait > 0:
            time.sleep(wait)
        self._last_time = time.monotonic()


def rate_limited(limiter: RateLimiter) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Apply a shared rate limiter to a callable."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            limiter.acquire()
            return func(*args, **kwargs)

        return wrapper

    return decorator

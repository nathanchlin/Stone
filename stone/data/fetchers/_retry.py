"""Retry helpers for transient fetch failures."""

from collections.abc import Callable
from functools import wraps
from http.client import RemoteDisconnected
from json import JSONDecodeError
from typing import ParamSpec, TypeVar

from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from urllib3.exceptions import ProtocolError

P = ParamSpec("P")
T = TypeVar("T")

TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    JSONDecodeError,
    RemoteDisconnected,
    RequestsConnectionError,
    RequestsTimeout,
    ProtocolError,
)


def with_retry(
    max_attempts: int = 3,
    multiplier: int = 1,
    min_wait: int = 1,
    max_wait: int = 30,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry a callable when a transient exception is raised."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
            reraise=True,
        )
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return func(*args, **kwargs)

        return wrapper

    return decorator

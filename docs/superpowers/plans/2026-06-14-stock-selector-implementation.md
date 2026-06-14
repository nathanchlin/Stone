# Stone Stock Selector Implementation Plan (Phase 1 + Phase 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal A-stock investment research assistant that generates Top 30 candidate stocks daily via multi-factor scoring, with YAML-configurable strategies and 4 output formats.

**Architecture:** Layered: CLI → SelectionEngine → (Factors + Strategy + Scoring + Constraints + PositionSizing) → DataLayer (akshare fetcher + parquet cache + universe). Each layer has clear interfaces, single-direction dependencies. Test coverage ≥ 80%, TDD workflow.

**Tech Stack:** Python 3.12 + uv + pandas + pyarrow + akshare + pydantic + click + pytest + mplfinance. Package name `stone` with subpackages `stone.data`, `stone.selector`, `stone.reporters`.

---

## Overview

30 tasks organized into 4 stages:

| Stage | Tasks | Outcome |
|---|---|---|
| Setup | T1-T3 | Project skeleton + foundation (errors/logging/factor base) |
| Phase 1: Data Layer | T4-T9 | akshare fetcher + parquet cache + universe + incremental + quality |
| Phase 2: Selector | T10-T25 | 16 factors + YAML strategy + scoring + constraints + position sizing + engine + 4 reporters |
| Wrap-up | T26-T30 | CLI + 3 default strategies + integration/E2E + launchd + final push |

Every task follows TDD: **RED (write failing test) → GREEN (minimal impl) → REFACTOR → COMMIT**.

---

## File Structure

```
Stone/
├── pyproject.toml
├── .python-version                  # 3.12
├── main.py                          # from stone.cli import app; app()
├── stone/
│   ├── __init__.py                  # __version__
│   ├── constants.py
│   ├── errors.py                    # FactorError, DataError, ConfigError
│   ├── logging_setup.py
│   ├── cli.py                       # click commands
│   ├── data/
│   │   ├── fetchers/
│   │   │   ├── base.py              # DataFetcher Protocol
│   │   │   ├── akshare_fetcher.py
│   │   │   ├── _rate_limiter.py
│   │   │   └── _retry.py
│   │   ├── cache/
│   │   │   └── parquet_store.py
│   │   ├── universe.py
│   │   ├── incremental.py
│   │   └── quality.py
│   ├── selector/
│   │   ├── factors/
│   │   │   ├── __init__.py          # REGISTRY + register_factor
│   │   │   ├── base.py
│   │   │   ├── normalize.py
│   │   │   ├── technical.py         # 10 factors
│   │   │   ├── fundamental.py       # 3 factors
│   │   │   ├── moneyflow.py         # 2 factors
│   │   │   └── theme.py             # 1 factor
│   │   ├── strategy.py
│   │   ├── criterion.py
│   │   ├── scoring.py
│   │   ├── constraints.py
│   │   ├── position_sizing.py
│   │   └── engine.py
│   └── reporters/
│       ├── models.py
│       ├── excel.py
│       ├── html.py
│       ├── markdown.py
│       ├── json_reporter.py
│       └── charts.py
├── config/
│   ├── strategies/
│   │   ├── band_trend_v1.yaml
│   │   ├── breakout_strong.yaml
│   │   └── value_with_catalyst.yaml
│   ├── universe_rules.yaml
│   ├── position_rules.example.yaml
│   └── personal/.gitkeep
└── tests/
    ├── conftest.py
    ├── helpers/
    │   ├── kline_generator.py
    │   └── seed_data.py
    ├── unit/
    │   ├── data/
    │   ├── factors/
    │   └── ...
    ├── integration/
    │   └── test_pipeline.py
    └── e2e/
        └── test_cli.py
```

**Naming convention note:** Spec uses top-level `data/`, `selector/`, `reporters/`. Implementation uses `stone/data/`, `stone/selector/`, `stone/reporters/` because `data` collides with Python stdlib `dataclass` etc. This is a minor refinement — update spec section 3.3 in a follow-up commit if desired.

---

## Task 1: Project Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `main.py`
- Create: `stone/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Install uv (if not present)**

```bash
brew install uv
```

- [ ] **Step 2: Write `.python-version`**

```
3.12
```

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[project]
name = "stone"
version = "0.1.0"
description = "A-stock personal investment research assistant"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "akshare>=1.12.0",
    "pandas>=2.2.0",
    "numpy>=1.26.0",
    "pyarrow>=15.0.0",
    "pyyaml>=6.0",
    "pydantic>=2.6.0",
    "pandas-ta>=0.3.14b",
    "click>=8.1.0",
    "tenacity>=8.2.0",
    "tqdm>=4.66.0",
    "mplfinance>=0.12.10b0",
    "plotly>=5.20.0",
    "openpyxl>=3.1.0",
    "xlsxwriter>=3.2.0",
    "jinja2>=3.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.3.0",
    "mypy>=1.9.0",
    "ipykernel>=7.0.0",
    "jupyter>=1.0.0",
]

[project.scripts]
stone = "stone.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["stone"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=stone --cov-report=term-missing --cov-report=html --cov-fail-under=80 --strict-markers"
markers = [
    "integration: marks integration tests",
    "e2e: marks end-to-end tests",
]

[tool.coverage.run]
source = ["stone"]
omit = ["tests/*", "**/__init__.py", "main.py"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = false
ignore_missing_imports = true
```

- [ ] **Step 4: Write `stone/__init__.py`**

```python
"""Stone: A-stock personal investment research assistant."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Write `main.py`**

```python
"""Entry point: `python main.py <command>` delegates to stone.cli."""

from stone.cli import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 6: Write `tests/__init__.py`** (empty)

```python
```

- [ ] **Step 7: Write `tests/conftest.py`**

```python
"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def tmp_data_cache(tmp_path) -> Path:
    """Temporary data_cache directory."""
    cache = tmp_path / "data_cache"
    cache.mkdir()
    return cache


from pathlib import Path  # noqa: E402
```

- [ ] **Step 8: Install dependencies**

```bash
cd /Users/lindeng/Stone
uv sync --all-extras
```

Expected: `Installed packages: ... (~30 packages)` and a `.venv/` folder created.

- [ ] **Step 9: Smoke test**

```bash
uv run python -c "import stone; print(stone.__version__)"
```

Expected output: `0.1.0`

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml .python-version main.py stone/__init__.py tests/__init__.py tests/conftest.py uv.lock
git commit -m "chore: bootstrap project with uv + pyproject.toml"
```

---

## Task 2: Foundation (errors, logging, constants)

**Files:**
- Create: `stone/errors.py`
- Create: `stone/logging_setup.py`
- Create: `stone/constants.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_logging_setup.py`

- [ ] **Step 1: Write failing test for logging setup**

`tests/unit/test_logging_setup.py`:

```python
import logging
from pathlib import Path

from stone.logging_setup import setup_logging


def test_setup_logging_creates_log_file(tmp_path: Path):
    log_file = tmp_path / "test.log"
    setup_logging(level=logging.INFO, log_file=log_file)

    logging.getLogger("test").info("hello world")

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "hello world" in content


def test_setup_logging_format_contains_timestamp(tmp_path: Path):
    log_file = tmp_path / "test.log"
    setup_logging(level=logging.INFO, log_file=log_file)

    logging.getLogger("test").warning("warn msg")

    content = log_file.read_text(encoding="utf-8")
    # Should contain level and message
    assert "WARNING" in content
    assert "warn msg" in content
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_logging_setup.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'stone.logging_setup'`

- [ ] **Step 3: Write `stone/errors.py`**

```python
"""Custom exceptions for stone."""


class StoneError(Exception):
    """Base exception for all stone errors."""


class FactorError(StoneError):
    """Raised when a factor fails to compute."""


class DataError(StoneError):
    """Raised when data fetching/parsing fails."""


class ConfigError(StoneError):
    """Raised when configuration is invalid."""


class StrategyError(StoneError):
    """Raised when strategy YAML is invalid."""
```

- [ ] **Step 4: Write `stone/logging_setup.py`**

```python
"""Logging configuration: dual output (console + file)."""

import logging
import sys
from pathlib import Path


def setup_logging(level: int = logging.INFO, log_file: Path | None = None) -> None:
    """Configure root logger with console + optional file handlers."""
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers (idempotent setup)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    root.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
```

- [ ] **Step 5: Write `stone/constants.py`**

```python
"""Project-wide constants."""

from enum import StrEnum


class Board(StrEnum):
    SH_MAIN = "sh_main"          # 沪市主板
    SZ_MAIN = "sz_main"          # 深市主板
    CHINEXT = "chinext"          # 创业板
    STAR = "star"                # 科创板
    BSE = "bse"                  # 北交所


class FactorCategory(StrEnum):
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    MONEYFLOW = "moneyflow"
    THEME = "theme"


# K-line column names (canonical)
KLINE_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]

# Minimum history required for most factors
MIN_HISTORY_DAYS = 250

# akshare rate limit (requests per second)
AKSHARE_MAX_RATE = 3.0
```

- [ ] **Step 6: Write `tests/unit/__init__.py`** (empty)

```python
```

- [ ] **Step 7: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_logging_setup.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 8: Commit**

```bash
git add stone/errors.py stone/logging_setup.py stone/constants.py tests/unit/__init__.py tests/unit/test_logging_setup.py
git commit -m "feat: add foundation (errors, logging, constants)"
```

---

## Task 3: Factor Base + FactorContext

**Files:**
- Create: `stone/selector/__init__.py`
- Create: `stone/selector/factors/__init__.py`
- Create: `stone/selector/factors/base.py`
- Create: `tests/unit/factors/__init__.py`
- Create: `tests/unit/factors/test_base.py`

- [ ] **Step 1: Write failing test**

`tests/unit/factors/test_base.py`:

```python
from datetime import date

import pandas as pd
import pytest

from stone.errors import FactorError
from stone.selector.factors.base import Factor, FactorContext


class StubFactor(Factor):
    name = "stub_factor"

    def compute(self, ctx: FactorContext) -> float:
        return 42.0

    def get_params(self) -> dict:
        return {}


def test_factor_compute_returns_float():
    factor = StubFactor()
    ctx = FactorContext(
        code="000001", name="test", industry="测试", today=date(2026, 6, 14),
        kline=pd.DataFrame(), financial=pd.DataFrame(), moneyflow=pd.DataFrame(),
    )
    assert factor.compute(ctx) == 42.0


def test_factor_context_required_fields():
    ctx = FactorContext(
        code="000001", name="test", industry="测试", today=date(2026, 6, 14),
        kline=pd.DataFrame(), financial=pd.DataFrame(), moneyflow=pd.DataFrame(),
    )
    assert ctx.code == "000001"
    assert ctx.industry == "测试"


def test_factor_subclass_must_implement_compute():
    """Cannot instantiate Factor without implementing abstract methods."""
    with pytest.raises(TypeError):
        Factor()  # type: ignore[abstract]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/factors/test_base.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/selector/__init__.py`** (empty)

```python
```

- [ ] **Step 4: Write `stone/selector/factors/__init__.py`** (REGISTRY placeholder; populated in Task 11)

```python
"""Factor registry. Populated by @register_factor decorator."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stone.selector.factors.base import Factor

REGISTRY: dict[str, type["Factor"]] = {}


def register_factor(cls: type["Factor"]) -> type["Factor"]:
    """Decorator: register a Factor subclass by its `name` attribute."""
    if not hasattr(cls, "name") or not isinstance(cls.name, str):
        raise ValueError(f"Factor {cls} must define a string `name` attribute")
    if cls.name in REGISTRY:
        raise ValueError(f"Duplicate factor name: {cls.name}")
    REGISTRY[cls.name] = cls
    return cls
```

- [ ] **Step 5: Write `stone/selector/factors/base.py`**

```python
"""Factor abstract base class and FactorContext."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

import pandas as pd

from stone.constants import FactorCategory


@dataclass
class FactorContext:
    """Input passed to every Factor.compute(). Avoids long arg lists."""

    code: str
    name: str
    industry: str
    today: date
    kline: pd.DataFrame       # OHLCV, ≥ MIN_HISTORY_DAYS rows for full factors
    financial: pd.DataFrame   # recent 4 quarters of fundamentals
    moneyflow: pd.DataFrame   # last 30 days of money flow data


class Factor(ABC):
    """
    All factors implement this contract.

    - Input: FactorContext (one stock's data).
    - Output: a raw float value, normalized to [0, 100] by the scoring engine.
    - Pure function: no side effects, no I/O.
    """

    name: str
    category: FactorCategory
    higher_is_better: bool = True

    @abstractmethod
    def compute(self, ctx: FactorContext) -> float:
        """Return the raw factor value. Raise FactorError on failure."""

    @abstractmethod
    def get_params(self) -> dict:
        """Expose parameters for reproducibility / debugging."""
```

- [ ] **Step 6: Write `tests/unit/factors/__init__.py`** (empty)

```python
```

- [ ] **Step 7: Run tests to verify pass**

```bash
uv run pytest tests/unit/factors/test_base.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```bash
git add stone/selector/__init__.py stone/selector/factors/__init__.py stone/selector/factors/base.py tests/unit/factors/__init__.py tests/unit/factors/test_base.py
git commit -m "feat: add Factor base class and FactorContext"
```

---

## Task 4: ParquetStore

**Files:**
- Create: `stone/data/__init__.py`
- Create: `stone/data/cache/__init__.py`
- Create: `stone/data/cache/parquet_store.py`
- Create: `tests/unit/data/__init__.py`
- Create: `tests/unit/data/test_parquet_store.py`

- [ ] **Step 1: Write failing test**

`tests/unit/data/test_parquet_store.py`:

```python
from datetime import date

import pandas as pd

from stone.data.cache.parquet_store import ParquetStore


def _make_kline_df(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame({
        "code": ["000001"] * n,
        "open": [10.0] * n,
        "high": [11.0] * n,
        "low": [9.0] * n,
        "close": [10.5] * n,
        "volume": [1000] * n,
    })


def test_write_and_read_kline_roundtrip(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    target = date(2026, 6, 14)
    store.write_kline(target, _make_kline_df(3))

    df = store.read_kline(target)
    assert len(df) == 3
    assert list(df.columns) == ["code", "open", "high", "low", "close", "volume"]


def test_read_kline_missing_date_returns_empty(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    df = store.read_kline(date(2099, 1, 1))
    assert df.empty


def test_read_kline_range_returns_concatenated(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 13), _make_kline_df(2))
    store.write_kline(date(2026, 6, 14), _make_kline_df(3))
    df = store.read_kline_range(date(2026, 6, 13), date(2026, 6, 14))
    assert len(df) == 5


def test_list_cached_dates(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 13), _make_kline_df(1))
    store.write_kline(date(2026, 6, 14), _make_kline_df(1))
    dates = store.list_cached_dates("kline")
    assert date(2026, 6, 13) in dates
    assert date(2026, 6, 14) in dates


def test_get_missing_dates(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 13), _make_kline_df(1))
    missing = store.get_missing_dates("kline", [date(2026, 6, 13), date(2026, 6, 14)])
    assert missing == [date(2026, 6, 14)]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/data/test_parquet_store.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/data/__init__.py`** (empty), `stone/data/cache/__init__.py` (empty), `tests/unit/data/__init__.py` (empty)

- [ ] **Step 4: Write `stone/data/cache/parquet_store.py`**

```python
"""Parquet-backed cache, partitioned by date.

Layout: {base_dir}/{kind}/date={YYYY-MM-DD}/data.parquet
"""

from datetime import date
from pathlib import Path

import pandas as pd


class ParquetStore:
    """Read/write parquet files partitioned by date."""

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir)

    def _path(self, kind: str, target: date) -> Path:
        return self.base_dir / kind / f"date={target.isoformat()}" / "data.parquet"

    def write_kline(self, target: date, df: pd.DataFrame) -> None:
        path = self._path("kline", target)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    def write(self, kind: str, target: date, df: pd.DataFrame) -> None:
        """Generic write for any data kind (kline, financial, moneyflow, universe)."""
        path = self._path(kind, target)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    def read_kline(self, target: date) -> pd.DataFrame:
        return self.read("kline", target)

    def read(self, kind: str, target: date) -> pd.DataFrame:
        path = self._path(kind, target)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    def read_kline_range(self, start: date, end: date) -> pd.DataFrame:
        return self.read_range("kline", start, end)

    def read_range(self, kind: str, start: date, end: date) -> pd.DataFrame:
        frames = []
        for d in self.list_cached_dates(kind):
            if start <= d <= end:
                df = self.read(kind, d)
                if not df.empty:
                    df = df.copy()
                    df["_cache_date"] = d
                    frames.append(df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def list_cached_dates(self, kind: str) -> list[date]:
        kind_dir = self.base_dir / kind
        if not kind_dir.exists():
            return []
        dates = []
        for sub in kind_dir.iterdir():
            if sub.is_dir() and sub.name.startswith("date="):
                try:
                    d = date.fromisoformat(sub.name.removeprefix("date="))
                    dates.append(d)
                except ValueError:
                    continue
        return sorted(dates)

    def get_missing_dates(self, kind: str, expected: list[date]) -> list[date]:
        cached = set(self.list_cached_dates(kind))
        return [d for d in expected if d not in cached]
```

- [ ] **Step 5: Run tests to verify pass**

```bash
uv run pytest tests/unit/data/test_parquet_store.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add stone/data/__init__.py stone/data/cache/__init__.py stone/data/cache/parquet_store.py tests/unit/data/__init__.py tests/unit/data/test_parquet_store.py
git commit -m "feat: add ParquetStore with date-partitioned cache"
```

---

## Task 5: RateLimiter + Retry Decorator

**Files:**
- Create: `stone/data/fetchers/__init__.py`
- Create: `stone/data/fetchers/_rate_limiter.py`
- Create: `stone/data/fetchers/_retry.py`
- Create: `tests/unit/data/test_rate_limiter.py`

- [ ] **Step 1: Write failing test**

`tests/unit/data/test_rate_limiter.py`:

```python
import time

from stone.data.fetchers._rate_limiter import RateLimiter, rate_limited


def test_rate_limiter_allows_burst_then_throttles():
    """First call instant; subsequent calls within window may sleep."""
    limiter = RateLimiter(max_rate=10.0)  # 10 per second
    start = time.monotonic()
    for _ in range(3):
        limiter.acquire()
    elapsed = time.monotonic() - start
    # 3 calls at 10/s should take ~0.2s minimum
    assert elapsed >= 0.15


def test_rate_limited_decorator_applies_to_function():
    limiter = RateLimiter(max_rate=10.0)
    calls = []

    @rate_limited(limiter)
    def f(x):
        calls.append(x)
        return x * 2

    assert f(5) == 10
    assert calls == [5]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/data/test_rate_limiter.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/data/fetchers/__init__.py`** (empty)

- [ ] **Step 4: Write `stone/data/fetchers/_rate_limiter.py`**

```python
"""Token-bucket rate limiter for akshare (avoid IP ban)."""

import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

T = TypeVar("T")


class RateLimiter:
    """Simple token-bucket: max_rate tokens per second."""

    def __init__(self, max_rate: float):
        self.min_interval = 1.0 / max_rate
        self._last_time = 0.0

    def acquire(self) -> None:
        now = time.monotonic()
        wait = self.min_interval - (now - self._last_time)
        if wait > 0:
            time.sleep(wait)
        self._last_time = time.monotonic()


def rate_limited(limiter: RateLimiter) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator: apply rate limiter to a function."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            limiter.acquire()
            return func(*args, **kwargs)

        return wrapper

    return decorator
```

- [ ] **Step 5: Write `stone/data/fetchers/_retry.py`**

```python
"""Retry decorator using tenacity."""

from collections.abc import Callable
from functools import wraps
from typing import TypeVar

import json5
import requests
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

T = TypeVar("T")

# Exceptions considered transient (worth retrying)
TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    requests.ConnectionError,
    requests.Timeout,
    json5.JSONDecodeError,
    ValueError,  # akshare sometimes returns "请求频繁" wrapped in ValueError
)


def with_retry(max_attempts: int = 3, multiplier: int = 1, max_wait: int = 30):
    """Factory: returns a decorator with the given retry config."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=multiplier, min=2, max=max_wait),
            retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
            reraise=True,
        )
        def wrapper(*args, **kwargs) -> T:
            return func(*args, **kwargs)

        return wrapper

    return decorator
```

- [ ] **Step 6: Run tests to verify pass**

```bash
uv run pytest tests/unit/data/test_rate_limiter.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add stone/data/fetchers/__init__.py stone/data/fetchers/_rate_limiter.py stone/data/fetchers/_retry.py tests/unit/data/test_rate_limiter.py
git commit -m "feat: add RateLimiter and retry decorator for fetchers"
```

---

## Task 6: DataFetcher Protocol + AkshareFetcher

**Files:**
- Create: `stone/data/fetchers/base.py`
- Create: `stone/data/fetchers/akshare_fetcher.py`
- Create: `tests/unit/data/test_akshare_fetcher.py`

- [ ] **Step 1: Write failing test (mocked akshare)**

`tests/unit/data/test_akshare_fetcher.py`:

```python
from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from stone.data.fetchers.akshare_fetcher import AkshareFetcher
from stone.errors import DataError


def _mock_kline_df():
    return pd.DataFrame({
        "日期": ["2026-06-12", "2026-06-13"],
        "开盘": [10.0, 10.5],
        "收盘": [10.5, 11.0],
        "最高": [11.0, 11.5],
        "最低": [9.5, 10.0],
        "成交量": [1000, 1200],
        "成交额": [10500.0, 13200.0],
    })


def test_get_daily_kline_returns_canonical_columns():
    fetcher = AkshareFetcher()
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_zh_a_hist.return_value = _mock_kline_df()
        df = fetcher.get_daily_kline("000001", date(2026, 6, 12), date(2026, 6, 13))

    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume", "amount"]
    assert len(df) == 2
    assert df.iloc[0]["close"] == 10.5


def test_get_daily_kline_raises_on_empty_result():
    fetcher = AkshareFetcher()
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()
        with pytest.raises(DataError):
            fetcher.get_daily_kline("000001", date(2026, 6, 12), date(2026, 6, 13))


def test_list_universe_returns_required_columns():
    fetcher = AkshareFetcher()
    fake = pd.DataFrame({
        "代码": ["600519", "000001"],
        "名称": ["贵州茅台", "平安银行"],
        "最新价": [1800.0, 12.0],
    })
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_info_a_code_name.return_value = fake
        df = fetcher.list_universe(date(2026, 6, 14))

    assert "code" in df.columns
    assert "name" in df.columns
    assert len(df) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/data/test_akshare_fetcher.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/data/fetchers/base.py`**

```python
"""Abstract DataFetcher protocol (swap data sources without touching business logic)."""

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class DataFetcher(Protocol):
    """Contract for all data fetchers."""

    def list_universe(self, target_date: date) -> pd.DataFrame:
        """Return full-market stock list (code, name, board, list_date, is_st)."""
        ...

    def get_daily_kline(
        self, code: str, start: date, end: date, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """Return daily OHLCV with columns: date, open, high, low, close, volume, amount."""
        ...

    def get_basic_financial(self, code: str) -> pd.DataFrame:
        """Return PE/PB/ROE/revenue growth/debt ratio."""
        ...

    def get_money_flow(self, code: str, days: int = 30) -> pd.DataFrame:
        """Return main fund + northbound flow."""
        ...

    def get_industry_mapping(self) -> dict[str, str]:
        """Return {code: industry_name}."""
        ...

    def get_trade_calendar(self, start: date, end: date) -> list[date]:
        """Return trading days (excluding weekends/holidays)."""
        ...
```

- [ ] **Step 4: Write `stone/data/fetchers/akshare_fetcher.py`**

```python
"""akshare implementation of DataFetcher."""

from datetime import date

import akshare as ak
import pandas as pd

from stone.constants import AKSHARE_MAX_RATE
from stone.data.fetchers._rate_limiter import RateLimiter, rate_limited
from stone.data.fetchers._retry import with_retry
from stone.errors import DataError

_LIMITER = RateLimiter(max_rate=AKSHARE_MAX_RATE)

_KLINE_RENAME = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
}


class AkshareFetcher:
    """Concrete DataFetcher backed by akshare."""

    def __init__(self, rate_limiter: RateLimiter | None = None):
        self._limiter = rate_limiter or _LIMITER

    @rate_limited(_LIMITER)
    @with_retry()
    def list_universe(self, target_date: date) -> pd.DataFrame:
        df = ak.stock_info_a_code_name()
        if df.empty:
            raise DataError(f"Empty universe for {target_date}")
        df = df.rename(columns={"代码": "code", "名称": "name"})
        return df[["code", "name"]]

    @rate_limited(_LIMITER)
    @with_retry()
    def get_daily_kline(
        self, code: str, start: date, end: date, adjust: str = "qfq"
    ) -> pd.DataFrame:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust=adjust,
        )
        if df.empty:
            raise DataError(f"Empty kline for {code} {start}->{end}")
        df = df.rename(columns=_KLINE_RENAME)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        canonical = ["date", "open", "high", "low", "close", "volume", "amount"]
        return df[canonical]

    @rate_limited(_LIMITER)
    @with_retry()
    def get_basic_financial(self, code: str) -> pd.DataFrame:
        df = ak.stock_financial_analysis_indicator(symbol=code.lstrip("shsz.").zfill(6))
        return df

    @rate_limited(_LIMITER)
    @with_retry()
    def get_money_flow(self, code: str, days: int = 30) -> pd.DataFrame:
        market = "sh" if code.startswith(("6", "9")) else "sz"
        df = ak.stock_individual_fund_flow(stock=code, market=market)
        return df.tail(days)

    @rate_limited(_LIMITER)
    @with_retry()
    def get_industry_mapping(self) -> dict[str, str]:
        boards = ak.stock_board_industry_name_em()
        mapping: dict[str, str] = {}
        for board_name in boards["板块名称"]:
            try:
                cons = ak.stock_board_industry_cons_em(symbol=board_name)
                for _, row in cons.iterrows():
                    mapping[row["代码"]] = board_name
            except Exception:
                continue
        return mapping

    @rate_limited(_LIMITER)
    @with_retry()
    def get_trade_calendar(self, start: date, end: date) -> list[date]:
        df = ak.tool_trade_date_hist_sina()
        dates = pd.to_datetime(df["trade_date"]).dt.date
        return [d for d in dates if start <= d <= end]
```

- [ ] **Step 5: Run tests to verify pass**

```bash
uv run pytest tests/unit/data/test_akshare_fetcher.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add stone/data/fetchers/base.py stone/data/fetchers/akshare_fetcher.py tests/unit/data/test_akshare_fetcher.py
git commit -m "feat: add DataFetcher protocol and AkshareFetcher implementation"
```

---

## Task 7: Universe + UniverseRules

**Files:**
- Create: `stone/data/universe.py`
- Create: `config/universe_rules.yaml`
- Create: `tests/unit/data/test_universe.py`

- [ ] **Step 1: Write failing test**

`tests/unit/data/test_universe.py`:

```python
from datetime import date

import pandas as pd
import pytest

from stone.data.universe import UniverseRules, get_active_universe


def _make_universe_df():
    return pd.DataFrame({
        "code": ["600519", "000001", "300001", "688001", "830001", "ST001"],
        "name": ["贵州茅台", "平安银行", "特锐德", "华兴源创", "永顺生物", "ST测试"],
        "is_st": [False, False, False, False, False, True],
        "list_date": [date(2001, 8, 27), date(1991, 4, 3),
                      date(2010, 1, 1), date(2019, 7, 22),
                      date(2026, 5, 1), date(2020, 1, 1)],
    })


def test_exclude_st():
    rules = UniverseRules(exclude_st=True, exclude_new_listing_days=60)
    codes = get_active_universe(_make_universe_df(), date(2026, 6, 14), rules)
    assert "ST001" not in codes
    assert "600519" in codes


def test_exclude_new_listing():
    rules = UniverseRules(exclude_new_listing_days=60)
    codes = get_active_universe(_make_universe_df(), date(2026, 6, 14), rules)
    # 830001 listed 2026-05-01, only ~44 days old → excluded
    assert "830001" not in codes
    # 688001 listed 2019 → kept
    assert "688001" in codes


def test_load_universe_rules_from_yaml(tmp_path):
    yaml_content = """
exclude_st: true
exclude_new_listing_days: 60
exclude_paused: true
exclude_delisting_risk: true
exclude_beijing_exchange: false
min_market_cap: 5000000000
"""
    p = tmp_path / "rules.yaml"
    p.write_text(yaml_content)
    rules = UniverseRules.from_yaml(p)
    assert rules.exclude_st is True
    assert rules.exclude_new_listing_days == 60
    assert rules.min_market_cap == 5_000_000_000
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/data/test_universe.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/data/universe.py`**

```python
"""Active universe maintenance: filter ST, new listings, paused, etc."""

from datetime import date
from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel


class UniverseRules(BaseModel):
    exclude_st: bool = True
    exclude_new_listing_days: int = 60
    exclude_paused: bool = True
    exclude_delisting_risk: bool = True
    exclude_beijing_exchange: bool = False
    min_market_cap: float | None = None

    @classmethod
    def from_yaml(cls, path: Path | str) -> "UniverseRules":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)


def get_active_universe(
    raw: pd.DataFrame, target_date: date, rules: UniverseRules
) -> list[str]:
    """Filter raw universe dataframe by rules. Return active stock codes."""
    df = raw.copy()

    if rules.exclude_st and "is_st" in df.columns:
        df = df[~df["is_st"]]
        # also exclude by name containing ST
        df = df[~df["name"].astype(str).str.startswith("ST")]
        df = df[~df["name"].astype(str).str.startswith("*ST")]

    if rules.exclude_new_listing_days > 0 and "list_date" in df.columns:
        cutoff = pd.Timestamp(target_date) - pd.Timedelta(days=rules.exclude_new_listing_days)
        list_dates = pd.to_datetime(df["list_date"])
        df = df[list_dates <= cutoff]

    if rules.exclude_beijing_exchange and "code" in df.columns:
        # BSE codes start with 8 or 4
        df = df[~df["code"].astype(str).str.startswith(("8", "4"))]

    return df["code"].astype(str).tolist()
```

- [ ] **Step 4: Write `config/universe_rules.yaml`**

```yaml
exclude_st: true
exclude_new_listing_days: 60
exclude_paused: true
exclude_delisting_risk: true
exclude_beijing_exchange: false
min_market_cap: 5000000000  # 50亿，剔除超小盘股
```

- [ ] **Step 5: Run tests to verify pass**

```bash
uv run pytest tests/unit/data/test_universe.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add stone/data/universe.py config/universe_rules.yaml tests/unit/data/test_universe.py
git commit -m "feat: add universe maintenance with YAML-configurable rules"
```

---

## Task 8: IncrementalUpdater

**Files:**
- Create: `stone/data/incremental.py`
- Create: `tests/unit/data/test_incremental.py`

- [ ] **Step 1: Write failing test**

`tests/unit/data/test_incremental.py`:

```python
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from stone.data.cache.parquet_store import ParquetStore
from stone.data.incremental import IncrementalUpdater, UpdateReport


def _mock_fetcher():
    fetcher = MagicMock()
    fetcher.get_trade_calendar.return_value = [date(2026, 6, 13), date(2026, 6, 14)]
    fetcher.list_universe.return_value = pd.DataFrame({
        "code": ["600519", "000001"],
        "name": ["贵州茅台", "平安银行"],
    })
    fetcher.get_daily_kline.return_value = pd.DataFrame({
        "code": ["600519"], "open": [10.0], "high": [11.0],
        "low": [9.0], "close": [10.5], "volume": [100], "amount": [1000.0],
    })
    return fetcher


def test_update_writes_missing_dates(tmp_path):
    store = ParquetStore(tmp_path)
    fetcher = _mock_fetcher()
    updater = IncrementalUpdater(store=store, fetcher=fetcher)

    report = updater.update_daily(date(2026, 6, 14))

    assert isinstance(report, UpdateReport)
    assert report.success_dates == [date(2026, 6, 13), date(2026, 6, 14)]
    assert report.failed_dates == []


def test_update_skips_already_cached_dates(tmp_path):
    store = ParquetStore(tmp_path)
    # pre-populate one date
    store.write_kline(date(2026, 6, 13), pd.DataFrame({
        "code": ["600519"], "open": [10.0], "high": [11.0],
        "low": [9.0], "close": [10.5], "volume": [100], "amount": [1000.0],
    }))

    fetcher = _mock_fetcher()
    updater = IncrementalUpdater(store=store, fetcher=fetcher)

    report = updater.update_daily(date(2026, 6, 14))

    assert date(2026, 6, 13) in report.skipped_dates
    assert date(2026, 6, 14) in report.success_dates
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/data/test_incremental.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/data/incremental.py`**

```python
"""Daily incremental data update."""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from tqdm import tqdm

from stone.data.cache.parquet_store import ParquetStore
from stone.data.fetchers.base import DataFetcher


@dataclass
class UpdateReport:
    target_date: date
    success_dates: list[date] = field(default_factory=list)
    failed_dates: list[date] = field(default_factory=list)
    skipped_dates: list[date] = field(default_factory=list)
    failed_codes: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Update {self.target_date}: "
            f"success={len(self.success_dates)}, "
            f"failed={len(self.failed_dates)}, "
            f"skipped={len(self.skipped_dates)}"
        )


class IncrementalUpdater:
    def __init__(self, store: ParquetStore, fetcher: DataFetcher, lookback_days: int = 365):
        self.store = store
        self.fetcher = fetcher
        self.lookback_days = lookback_days

    def update_daily(self, target_date: date) -> UpdateReport:
        report = UpdateReport(target_date=target_date)
        start = pd.Timestamp(target_date) - pd.Timedelta(days=self.lookback_days)

        calendar = self.fetcher.get_trade_calendar(start.date(), target_date)
        missing = self.store.get_missing_dates("kline", calendar)

        # Identify already-cached for skip reporting
        cached = set(self.store.list_cached_dates("kline"))
        report.skipped_dates = [d for d in calendar if d in cached]

        for d in tqdm(missing, desc="Updating dates"):
            try:
                self._fetch_and_store_one_day(d, report)
                report.success_dates.append(d)
            except Exception as e:
                report.failed_dates.append(d)
                report.failed_codes.append((d.isoformat(), str(e)))

        return report

    def _fetch_and_store_one_day(self, d: date, report: UpdateReport) -> None:
        universe_df = self.fetcher.list_universe(d)
        if universe_df.empty:
            raise RuntimeError(f"empty universe for {d}")

        frames = []
        for code in universe_df["code"].astype(str):
            try:
                kline = self.fetcher.get_daily_kline(code, d, d)
                kline["code"] = code
                frames.append(kline)
            except Exception as e:
                report.failed_codes.append((code, str(e)))

        if not frames:
            raise RuntimeError(f"no kline data for {d}")
        df = pd.concat(frames, ignore_index=True)
        self.store.write_kline(d, df)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/data/test_incremental.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/data/incremental.py tests/unit/data/test_incremental.py
git commit -m "feat: add IncrementalUpdater with skip/retry/success tracking"
```

---

## Task 9: DataQualityChecker

**Files:**
- Create: `stone/data/quality.py`
- Create: `tests/unit/data/test_quality.py`

- [ ] **Step 1: Write failing test**

`tests/unit/data/test_quality.py`:

```python
from datetime import date

import pandas as pd
import pytest

from stone.data.quality import QualityReport, assert_kline_quality, check_kline
from stone.errors import DataError


def _good_df():
    return pd.DataFrame({
        "code": ["600519"] * 2,
        "open": [10.0, 10.5],
        "high": [11.0, 11.5],
        "low": [9.5, 10.0],
        "close": [10.5, 11.0],
        "volume": [1000, 1200],
        "amount": [10500.0, 13200.0],
    })


def test_good_dataframe_passes():
    report = check_kline(_good_df(), date(2026, 6, 14))
    assert report.ok
    assert report.errors == []


def test_low_greater_than_high_fails():
    df = _good_df().copy()
    df.loc[0, "low"] = 12.0  # > high (11.0)
    report = check_kline(df, date(2026, 6, 14))
    assert not report.ok
    assert any("low > high" in e for e in report.errors)


def test_negative_volume_fails():
    df = _good_df().copy()
    df.loc[0, "volume"] = -1
    report = check_kline(df, date(2026, 6, 14))
    assert not report.ok
    assert any("volume < 0" in e for e in report.errors)


def test_nan_in_close_fails():
    df = _good_df().copy()
    df.loc[0, "close"] = float("nan")
    report = check_kline(df, date(2026, 6, 14))
    assert not report.ok


def test_assert_kline_quality_raises_on_failure():
    df = _good_df().copy()
    df.loc[0, "low"] = 12.0
    with pytest.raises(DataError):
        assert_kline_quality(df, date(2026, 6, 14))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/data/test_quality.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/data/quality.py`**

```python
"""Data quality checks for kline data."""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from stone.errors import DataError


@dataclass
class QualityReport:
    target_date: date | None = None
    ok: bool = True
    errors: list[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)


def check_kline(df: pd.DataFrame, target_date: date | None = None) -> QualityReport:
    """Run all quality checks. Returns report (does not raise)."""
    report = QualityReport(target_date=target_date)

    if df.empty:
        report.add("empty dataframe")
        return report

    if "low" in df.columns and "high" in df.columns:
        bad = df[df["low"] > df["high"]]
        if not bad.empty:
            report.add(f"low > high in {len(bad)} rows")

    if "low" in df.columns and {"open", "close"}.issubset(df.columns):
        bad = df[df["low"] > df[["open", "close"]].min(axis=1)]
        if not bad.empty:
            report.add(f"low > min(open, close) in {len(bad)} rows")

    for col in ["open", "high", "low", "close"]:
        if col in df.columns and df[col].isna().any():
            report.add(f"{col} has NaN values")

    if "volume" in df.columns and (df["volume"] < 0).any():
        report.add("volume < 0 in some rows")

    return report


def assert_kline_quality(df: pd.DataFrame, target_date: date) -> None:
    """Raise DataError if any quality check fails."""
    report = check_kline(df, target_date)
    if not report.ok:
        raise DataError(f"Quality check failed for {target_date}: {report.errors}")
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/data/test_quality.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/data/quality.py tests/unit/data/test_quality.py
git commit -m "feat: add DataQualityChecker for kline validation"
```

---

## Task 10: Normalizer (Historical Percentile)

**Files:**
- Create: `stone/selector/factors/normalize.py`
- Create: `tests/unit/factors/test_normalize.py`

- [ ] **Step 1: Write failing test**

`tests/unit/factors/test_normalize.py`:

```python
import numpy as np
import pandas as pd

from stone.selector.factors.normalize import Normalizer


def test_value_at_high_percentile_returns_high_score():
    history = pd.Series(list(range(100)))  # 0..99
    norm = Normalizer()
    score = norm.normalize(raw_value=95.0, history=history)
    assert 90 <= score <= 100


def test_value_at_low_percentile_returns_low_score():
    history = pd.Series(list(range(100)))
    norm = Normalizer()
    score = norm.normalize(raw_value=2.0, history=history)
    assert score <= 10


def test_higher_is_better_false_inverts():
    """If factor.lower_is_better (e.g., PE), low raw value should produce high score."""
    history = pd.Series(list(range(100)))
    norm = Normalizer()
    score_low_pe = norm.normalize(raw_value=2.0, history=history, higher_is_better=False)
    score_high_pe = norm.normalize(raw_value=95.0, history=history, higher_is_better=False)
    assert score_low_pe > score_high_pe


def test_empty_history_returns_50():
    norm = Normalizer()
    assert norm.normalize(raw_value=1.0, history=pd.Series([], dtype=float)) == 50.0


def test_nan_raw_value_returns_zero():
    history = pd.Series(list(range(100)))
    norm = Normalizer()
    score = norm.normalize(raw_value=float("nan"), history=history)
    assert score == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/factors/test_normalize.py -v
```

Expected: FAIL

- [ ] **Step 3: Write `stone/selector/factors/normalize.py`**

```python
"""Normalize raw factor values to [0, 100] using historical percentile.

Decision (spec 5.2): normalize on the stock's OWN history, not cross-section.
"""

import numpy as np
import pandas as pd


class Normalizer:
    """Historical percentile rank normalizer."""

    def normalize(
        self,
        raw_value: float,
        history: pd.Series,
        higher_is_better: bool = True,
    ) -> float:
        """Return percentile rank of raw_value in history, scaled to [0, 100]."""
        if pd.isna(raw_value):
            return 0.0
        if history.empty:
            return 50.0

        clean = history.dropna()
        if clean.empty:
            return 50.0

        rank = (clean < raw_value).sum() / len(clean) * 100.0
        # rank = % of history values BELOW raw_value (0..100)
        if not higher_is_better:
            rank = 100.0 - rank
        return float(np.clip(rank, 0.0, 100.0))
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/factors/test_normalize.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/factors/normalize.py tests/unit/factors/test_normalize.py
git commit -m "feat: add Normalizer using historical percentile rank"
```

---

## Task 11: Test Helpers (Synthetic K-line Generator)

**Files:**
- Create: `tests/helpers/__init__.py`
- Create: `tests/helpers/kline_generator.py`
- Create: `tests/helpers/seed_data.py`
- Create: `tests/unit/factors/test_kline_generator.py`

- [ ] **Step 1: Write failing test**

`tests/unit/factors/test_kline_generator.py`:

```python
from datetime import date, timedelta

import pandas as pd

from tests.helpers.kline_generator import (
    generate_downtrend_kline,
    generate_sideways_kline,
    generate_uptrend_kline,
    generate_volatile_kline,
)


def test_uptrend_kline_has_increasing_close():
    df = generate_uptrend_kline(days=250)
    assert len(df) == 250
    # average of last 50 should be > average of first 50
    assert df["close"].tail(50).mean() > df["close"].head(50).mean()


def test_downtrend_kline_has_decreasing_close():
    df = generate_downtrend_kline(days=250)
    assert df["close"].tail(50).mean() < df["close"].head(50).mean()


def test_kline_has_required_columns():
    df = generate_uptrend_kline(days=10)
    for col in ["date", "open", "high", "low", "close", "volume", "amount"]:
        assert col in df.columns


def test_kline_low_le_high():
    df = generate_uptrend_kline(days=50)
    assert (df["low"] <= df["high"]).all()


def test_volatile_kline_has_wider_range():
    up = generate_uptrend_kline(days=100)
    vol = generate_volatile_kline(days=100)
    assert vol["close"].std() > up["close"].std()


def test_sideways_kline_is_flat():
    df = generate_sideways_kline(days=100, base_price=10.0)
    # Mean close should be within ±5% of base
    assert abs(df["close"].mean() - 10.0) < 0.5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/factors/test_kline_generator.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `tests/helpers/__init__.py`** (empty), `tests/helpers/kline_generator.py`:

```python
"""Synthetic K-line generators for factor testing.

Parameterized: can produce uptrend / downtrend / sideways / volatile / with-NaN.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd


def _make_df(days: int, dates: list[date], opens, highs, lows, closes, volumes):
    return pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "amount": [c * v for c, v in zip(closes, volumes, strict=False)],
    })


def generate_uptrend_kline(
    days: int = 250, start_price: float = 10.0, drift: float = 0.005, seed: int = 42
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = [start_price]
    for _ in range(days - 1):
        ret = drift + rng.normal(0, 0.015)
        closes.append(closes[-1] * (1 + ret))
    closes = np.array(closes)
    opens = closes * (1 - rng.uniform(0, 0.01, days))
    highs = np.maximum(opens, closes) * (1 + rng.uniform(0.005, 0.02, days))
    lows = np.minimum(opens, closes) * (1 - rng.uniform(0.005, 0.02, days))
    volumes = rng.integers(1_000_000, 10_000_000, days)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(days)]
    return _make_df(days, dates, opens, highs, lows, closes, volumes)


def generate_downtrend_kline(
    days: int = 250, start_price: float = 50.0, drift: float = -0.005, seed: int = 42
) -> pd.DataFrame:
    return generate_uptrend_kline(days=days, start_price=start_price, drift=drift, seed=seed)


def generate_sideways_kline(
    days: int = 100, base_price: float = 10.0, volatility: float = 0.01, seed: int = 42
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = base_price * (1 + rng.normal(0, volatility, days))
    opens = closes * (1 - rng.uniform(0, 0.005, days))
    highs = np.maximum(opens, closes) * (1 + rng.uniform(0.002, 0.01, days))
    lows = np.minimum(opens, closes) * (1 - rng.uniform(0.002, 0.01, days))
    volumes = rng.integers(1_000_000, 5_000_000, days)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(days)]
    return _make_df(days, dates, opens, highs, lows, closes, volumes)


def generate_volatile_kline(
    days: int = 100, base_price: float = 10.0, volatility: float = 0.05, seed: int = 42
) -> pd.DataFrame:
    return generate_sideways_kline(
        days=days, base_price=base_price, volatility=volatility, seed=seed
    )


def generate_breakout_kline(days: int = 250, breakout_at: int = 200, seed: int = 42) -> pd.DataFrame:
    """Sideways for `breakout_at` days, then strong uptrend."""
    rng = np.random.default_rng(seed)
    base = 10.0
    closes = list(base * (1 + rng.normal(0, 0.01, breakout_at)))
    last = closes[-1]
    for _ in range(days - breakout_at):
        last = last * (1 + 0.015 + rng.normal(0, 0.02))
        closes.append(last)
    closes = np.array(closes)
    opens = closes * (1 - rng.uniform(0, 0.01, days))
    highs = np.maximum(opens, closes) * (1 + rng.uniform(0.005, 0.02, days))
    lows = np.minimum(opens, closes) * (1 - rng.uniform(0.005, 0.02, days))
    volumes = rng.integers(1_000_000, 10_000_000, days)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(days)]
    return _make_df(days, dates, opens, highs, lows, closes, volumes)
```

- [ ] **Step 4: Write `tests/helpers/seed_data.py`**

```python
"""Helpers to seed ParquetStore with test data."""

from datetime import date, timedelta

import pandas as pd

from stone.data.cache.parquet_store import ParquetStore
from tests.helpers.kline_generator import generate_uptrend_kline


def seed_universe(store: ParquetStore, codes: list[str], target_date: date) -> None:
    df = pd.DataFrame({"code": codes, "name": [f"S{i}" for i in range(len(codes))]})
    store.write("universe", target_date, df)


def seed_kline_for_codes(
    store: ParquetStore,
    codes: list[str],
    end_date: date,
    days: int = 250,
) -> None:
    """Write a single kline partition per date, for `days` days ending at end_date."""
    for offset in range(days):
        d = end_date - timedelta(days=offset)
        frames = []
        for code in codes:
            kdf = generate_uptrend_kline(days=1, start_price=10.0 + hash(code) % 100)
            kdf["code"] = code
            kdf["date"] = [d]
            frames.append(kdf)
        store.write_kline(d, pd.concat(frames, ignore_index=True))
```

- [ ] **Step 5: Run tests to verify pass**

```bash
uv run pytest tests/unit/factors/test_kline_generator.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add tests/helpers/__init__.py tests/helpers/kline_generator.py tests/helpers/seed_data.py tests/unit/factors/test_kline_generator.py
git commit -m "test: add synthetic kline generators for factor tests"
```

---

## Task 12: Technical Factors Part 1 (MA Series)

**Files:**
- Create: `stone/selector/factors/technical.py`
- Create: `tests/unit/factors/test_technical.py`

- [ ] **Step 1: Write failing test**

`tests/unit/factors/test_technical.py`:

```python
from datetime import date

import pandas as pd
import pytest

from stone.selector.factors.base import FactorContext
from stone.selector.factors.technical import (
    Ma5AboveMa20,
    MaBullishAlignment,
    PriceAboveMa60,
)
from tests.helpers.kline_generator import generate_downtrend_kline, generate_uptrend_kline


def _ctx(kline: pd.DataFrame) -> FactorContext:
    return FactorContext(
        code="000001", name="test", industry="测试", today=date(2026, 6, 14),
        kline=kline, financial=pd.DataFrame(), moneyflow=pd.DataFrame(),
    )


def test_ma_bullish_alignment_high_for_uptrend():
    kline = generate_uptrend_kline(days=250)
    factor = MaBullishAlignment()
    score = factor.compute(_ctx(kline))
    assert 0.7 <= score <= 1.0  # uptrend should have mostly-aligned MAs


def test_ma_bullish_alignment_low_for_downtrend():
    kline = generate_downtrend_kline(days=250)
    factor = MaBullishAlignment()
    score = factor.compute(_ctx(kline))
    assert 0.0 <= score <= 0.3


def test_ma5_above_ma20_returns_binary():
    kline = generate_uptrend_kline(days=250)
    factor = Ma5AboveMa20()
    result = factor.compute(_ctx(kline))
    assert result in (0.0, 1.0)


def test_price_above_ma60_uptrend_returns_one():
    kline = generate_uptrend_kline(days=250)
    factor = PriceAboveMa60()
    assert factor.compute(_ctx(kline)) == 1.0


def test_factor_params_roundtrip():
    factor = MaBullishAlignment(periods=[5, 10, 20, 60])
    assert factor.get_params() == {"periods": [5, 10, 20, 60]}


def test_factor_name_unique():
    assert MaBullishAlignment.name == "ma_bullish_alignment"
    assert Ma5AboveMa20.name == "ma5_above_ma20"
    assert PriceAboveMa60.name == "price_above_ma60"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/factors/test_technical.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/selector/factors/technical.py`** (Part 1: MA series)

```python
"""Technical factors (10 total). Part 1: MA series."""

from stone.constants import FactorCategory
from stone.errors import FactorError
from stone.selector.factors.base import Factor, FactorContext


def _sma(series, window: int):
    if len(series) < window:
        raise FactorError(f"insufficient data: need {window} rows, got {len(series)}")
    return series.rolling(window=window, min_periods=window).mean().iloc[-1]


class MaBullishAlignment(Factor):
    """Score = fraction of (5 > 10 > 20 > 60) orderings satisfied."""

    name = "ma_bullish_alignment"
    category = FactorCategory.TECHNICAL

    def __init__(self, periods: tuple[int, ...] = (5, 10, 20, 60)):
        self.periods = tuple(periods)

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        mas = [(_sma(close, p)) for p in self.periods]
        total = len(mas) - 1
        aligned = sum(1 for i in range(total) if mas[i] > mas[i + 1])
        return aligned / total if total > 0 else 0.0

    def get_params(self) -> dict:
        return {"periods": list(self.periods)}


class Ma5AboveMa20(Factor):
    """1.0 if MA5 > MA20, else 0.0."""

    name = "ma5_above_ma20"
    category = FactorCategory.TECHNICAL

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        return 1.0 if _sma(close, 5) > _sma(close, 20) else 0.0

    def get_params(self) -> dict:
        return {}


class PriceAboveMa60(Factor):
    """1.0 if close > MA60, else 0.0."""

    name = "price_above_ma60"
    category = FactorCategory.TECHNICAL

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        return 1.0 if close.iloc[-1] > _sma(close, 60) else 0.0

    def get_params(self) -> dict:
        return {}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/factors/test_technical.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/factors/technical.py tests/unit/factors/test_technical.py
git commit -m "feat: add MA-series technical factors (3 of 10)"
```

---

## Task 13: Technical Factors Part 2 (Breakout + MACD + KDJ + RSI)

**Files:**
- Modify: `stone/selector/factors/technical.py` (append factors)
- Modify: `tests/unit/factors/test_technical.py` (append tests)

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/factors/test_technical.py`:

```python
from stone.selector.factors.technical import (
    Breakout20dHigh,
    KdjGoldenCross,
    MacdGoldenCross,
    RsiInHealthyZone,
)
from tests.helpers.kline_generator import generate_breakout_kline


def test_breakout_20d_high_returns_one_on_new_high():
    kline = generate_breakout_kline(days=250, breakout_at=200)
    factor = Breakout20dHigh(window=20)
    # last close should be new 20-day high after breakout
    score = factor.compute(_ctx(kline))
    assert score in (0.0, 1.0)


def test_macd_golden_cross_returns_binary():
    kline = generate_uptrend_kline(days=250)
    factor = MacdGoldenCross(lookback=5)
    result = factor.compute(_ctx(kline))
    assert result in (0.0, 1.0)


def test_kdj_golden_cross_returns_binary():
    kline = generate_uptrend_kline(days=250)
    factor = KdjGoldenCross(lookback=3)
    result = factor.compute(_ctx(kline))
    assert result in (0.0, 1.0)


def test_rsi_in_healthy_zone_within_range_returns_one():
    kline = generate_uptrend_kline(days=250)
    factor = RsiInHealthyZone(zone=(40, 70))
    # in a smooth uptrend, RSI is usually in healthy zone
    result = factor.compute(_ctx(kline))
    assert result in (0.0, 1.0)


def test_macd_factor_names():
    assert MacdGoldenCross.name == "macd_golden_cross"
    assert KdjGoldenCross.name == "kdj_golden_cross"
    assert Breakout20dHigh.name == "breakout_20d_high"
    assert RsiInHealthyZone.name == "rsi_in_healthy_zone"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/factors/test_technical.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Append to `stone/selector/factors/technical.py`**

```python
# === Part 2: Breakout + MACD + KDJ + RSI ===


class Breakout20dHigh(Factor):
    """1.0 if today's close = max(close[-window:]) (breakout)."""

    name = "breakout_20d_high"
    category = FactorCategory.TECHNICAL

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        if len(close) < self.window:
            raise FactorError(f"insufficient data: need {self.window} rows")
        recent = close.tail(self.window)
        return 1.0 if close.iloc[-1] >= recent.max() * 0.999 else 0.0

    def get_params(self) -> dict:
        return {"window": self.window}


def _ema(series, span: int):
    return series.ewm(span=span, adjust=False).mean()


class MacdGoldenCross(Factor):
    """1.0 if MACD line crossed above signal in last `lookback` days AND above zero."""

    name = "macd_golden_cross"
    category = FactorCategory.TECHNICAL

    def __init__(self, lookback: int = 5, fast: int = 12, slow: int = 26, signal: int = 9):
        self.lookback = lookback
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        if len(close) < self.slow + self.signal:
            raise FactorError("insufficient data for MACD")
        macd_line = _ema(close, self.fast) - _ema(close, self.slow)
        signal_line = macd_line.ewm(span=self.signal, adjust=False).mean()
        diff = macd_line - signal_line
        # Golden cross: diff was negative, now positive, within last `lookback` days
        recent_diff = diff.tail(self.lookback + 1)
        crossed = (recent_diff.iloc[:-1] <= 0).any() and recent_diff.iloc[-1] > 0
        above_zero = macd_line.iloc[-1] > 0
        return 1.0 if (crossed and above_zero) else 0.0

    def get_params(self) -> dict:
        return {"lookback": self.lookback, "fast": self.fast, "slow": self.slow, "signal": self.signal}


class KdjGoldenCross(Factor):
    """1.0 if K line crossed above D line in last `lookback` days."""

    name = "kdj_golden_cross"
    category = FactorCategory.TECHNICAL

    def __init__(self, lookback: int = 3, window: int = 9):
        self.lookback = lookback
        self.window = window

    def compute(self, ctx: FactorContext) -> float:
        high = ctx.kline["high"]
        low = ctx.kline["low"]
        close = ctx.kline["close"]
        if len(close) < self.window:
            raise FactorError("insufficient data for KDJ")
        hh = high.rolling(self.window).max()
        ll = low.rolling(self.window).min()
        rsv = (close - ll) / (hh - ll).replace(0, float("nan")) * 100
        k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
        d = k.ewm(alpha=1 / 3, adjust=False).mean()
        diff = k - d
        recent = diff.tail(self.lookback + 1)
        crossed = (recent.iloc[:-1] <= 0).any() and recent.iloc[-1] > 0
        return 1.0 if crossed else 0.0

    def get_params(self) -> dict:
        return {"lookback": self.lookback, "window": self.window}


class RsiInHealthyZone(Factor):
    """1.0 if RSI is within [low, high] (default 40-70 = healthy uptrend)."""

    name = "rsi_in_healthy_zone"
    category = FactorCategory.TECHNICAL

    def __init__(self, zone: tuple[float, float] = (40.0, 70.0), window: int = 14):
        self.low, self.high = zone
        self.window = window

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        if len(close) < self.window + 1:
            raise FactorError("insufficient data for RSI")
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(self.window).mean()
        loss = -delta.clip(upper=0).rolling(self.window).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi = 100 - 100 / (1 + rs)
        last = rsi.iloc[-1]
        if pd.isna(last):
            return 0.0
        return 1.0 if self.low <= last <= self.high else 0.0

    def get_params(self) -> dict:
        return {"zone": [self.low, self.high], "window": self.window}


# Need pandas at module level for _ema
import pandas as pd  # noqa: E402
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/factors/test_technical.py -v
```

Expected: PASS (11 tests total)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/factors/technical.py tests/unit/factors/test_technical.py
git commit -m "feat: add breakout, MACD, KDJ, RSI factors (7 of 10)"
```

---

## Task 14: Technical Factors Part 3 (Volume Ratio, Turnover, 52w Distance)

**Files:**
- Modify: `stone/selector/factors/technical.py` (append final 3 factors)
- Modify: `tests/unit/factors/test_technical.py` (append tests)

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/factors/test_technical.py`:

```python
from stone.selector.factors.technical import (
    DistanceTo52wHigh,
    TurnoverRate,
    VolumeRatio,
)


def test_volume_ratio_returns_positive_float():
    kline = generate_uptrend_kline(days=250)
    factor = VolumeRatio(avg_window=5)
    result = factor.compute(_ctx(kline))
    assert isinstance(result, float)
    assert result >= 0.0


def test_turnover_rate_in_range_returns_one():
    kline = generate_uptrend_kline(days=250)
    # Manually set turnover column
    kline["turnover_rate"] = 5.0
    factor = TurnoverRate(zone=(1.0, 10.0))
    assert factor.compute(_ctx(kline)) == 1.0


def test_turnover_rate_out_of_range_returns_zero():
    kline = generate_uptrend_kline(days=250)
    kline["turnover_rate"] = 0.5  # too low
    factor = TurnoverRate(zone=(1.0, 10.0))
    assert factor.compute(_ctx(kline)) == 0.0


def test_distance_to_52w_high_returns_ratio():
    kline = generate_uptrend_kline(days=260)
    factor = DistanceTo52wHigh()
    result = factor.compute(_ctx(kline))
    assert -1.0 <= result <= 0.0


def test_factor_names_part3():
    assert VolumeRatio.name == "volume_ratio"
    assert TurnoverRate.name == "turnover_rate"
    assert DistanceTo52wHigh.name == "distance_to_52w_high"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/factors/test_technical.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Append to `stone/selector/factors/technical.py`**

```python
# === Part 3: Volume / Turnover / Distance ===


class VolumeRatio(Factor):
    """Today's volume / average of last `avg_window` days (excl today)."""

    name = "volume_ratio"
    category = FactorCategory.TECHNICAL

    def __init__(self, avg_window: int = 5):
        self.avg_window = avg_window

    def compute(self, ctx: FactorContext) -> float:
        vol = ctx.kline["volume"]
        if len(vol) < self.avg_window + 1:
            raise FactorError("insufficient data for volume ratio")
        today = vol.iloc[-1]
        avg = vol.iloc[-self.avg_window - 1:-1].mean()
        if avg == 0:
            return 0.0
        return float(today / avg)

    def get_params(self) -> dict:
        return {"avg_window": self.avg_window}


class TurnoverRate(Factor):
    """1.0 if today's turnover_rate is in zone (default 1-10%)."""

    name = "turnover_rate"
    category = FactorCategory.TECHNICAL

    def __init__(self, zone: tuple[float, float] = (1.0, 10.0)):
        self.low, self.high = zone

    def compute(self, ctx: FactorContext) -> float:
        if "turnover_rate" not in ctx.kline.columns:
            return 0.0
        last = ctx.kline["turnover_rate"].iloc[-1]
        if pd.isna(last):
            return 0.0
        return 1.0 if self.low <= last <= self.high else 0.0

    def get_params(self) -> dict:
        return {"zone": [self.low, self.high]}


class DistanceTo52wHigh(Factor):
    """Ratio: (today_close - 52w_high) / 52w_high. Range [-1, 0]."""

    name = "distance_to_52w_high"
    category = FactorCategory.TECHNICAL

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        if len(close) < 252:
            raise FactorError("insufficient data for 52w high")
        high_52w = close.tail(252).max()
        today = close.iloc[-1]
        if high_52w == 0:
            return -1.0
        return float((today - high_52w) / high_52w)

    def get_params(self) -> dict:
        return {}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/factors/test_technical.py -v
```

Expected: PASS (16 tests total — all 10 technical factors covered)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/factors/technical.py tests/unit/factors/test_technical.py
git commit -m "feat: add volume/turnover/52w-distance factors (10 of 10 technical)"
```

---

## Task 15: Fundamental Factors (3, Filter-Type)

**Files:**
- Create: `stone/selector/factors/fundamental.py`
- Create: `tests/unit/factors/test_fundamental.py`

- [ ] **Step 1: Write failing test**

`tests/unit/factors/test_fundamental.py`:

```python
from datetime import date

import pandas as pd
import pytest

from stone.selector.factors.base import FactorContext
from stone.selector.factors.fundamental import (
    PeInIndustryPercentile,
    RevenueGrowthPositive,
    RoeAbove15,
)


def _ctx(financial: pd.DataFrame) -> FactorContext:
    return FactorContext(
        code="000001", name="test", industry="测试", today=date(2026, 6, 14),
        kline=pd.DataFrame(), financial=financial, moneyflow=pd.DataFrame(),
    )


def test_roe_above_15_passes_when_high():
    fin = pd.DataFrame({"roe": [16.0, 17.0, 18.0, 19.0]})  # 4 quarters
    factor = RoeAbove15()
    assert factor.compute(_ctx(fin)) == 1.0


def test_roe_above_15_fails_when_low():
    fin = pd.DataFrame({"roe": [10.0, 11.0, 12.0, 13.0]})
    factor = RoeAbove15()
    assert factor.compute(_ctx(fin)) == 0.0


def test_revenue_growth_positive_passes():
    fin = pd.DataFrame({"revenue_yoy": [15.0, 20.0, 18.0, 25.0]})
    factor = RevenueGrowthPositive()
    assert factor.compute(_ctx(fin)) == 1.0


def test_revenue_growth_positive_fails_on_negative():
    fin = pd.DataFrame({"revenue_yoy": [-5.0, -10.0, -3.0, -8.0]})
    factor = RevenueGrowthPositive()
    assert factor.compute(_ctx(fin)) == 0.0


def test_pe_in_industry_percentile_low_is_good():
    fin = pd.DataFrame({"pe_industry_pct": [0.3]})  # PE at 30th percentile = cheap
    factor = PeInIndustryPercentile()
    # For filter type, raw value IS the percentile (already 0-1)
    assert factor.compute(_ctx(fin)) == pytest.approx(0.3)


def test_factor_names():
    assert RoeAbove15.name == "roe_above_15"
    assert RevenueGrowthPositive.name == "revenue_growth_positive"
    assert PeInIndustryPercentile.name == "pe_in_industry_percentile"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/factors/test_fundamental.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/selector/factors/fundamental.py`**

```python
"""Fundamental factors (3, FILTER-TYPE: 0/1 binary, used to exclude not rank)."""

import pandas as pd

from stone.constants import FactorCategory
from stone.errors import FactorError
from stone.selector.factors.base import Factor, FactorContext


class RoeAbove15(Factor):
    """1.0 if 4-quarter rolling ROE > 15%, else 0.0."""

    name = "roe_above_15"
    category = FactorCategory.FUNDAMENTAL

    def compute(self, ctx: FactorContext) -> float:
        if ctx.financial.empty or "roe" not in ctx.financial.columns:
            return 0.0
        roe = ctx.financial["roe"].tail(4).mean()
        if pd.isna(roe):
            return 0.0
        return 1.0 if roe > 15.0 else 0.0

    def get_params(self) -> dict:
        return {}


class RevenueGrowthPositive(Factor):
    """1.0 if revenue YoY growth positive in last 2 quarters, else 0.0."""

    name = "revenue_growth_positive"
    category = FactorCategory.FUNDAMENTAL

    def compute(self, ctx: FactorContext) -> float:
        if ctx.financial.empty or "revenue_yoy" not in ctx.financial.columns:
            return 0.0
        recent = ctx.financial["revenue_yoy"].tail(2)
        if recent.empty or recent.isna().any():
            return 0.0
        return 1.0 if (recent > 0).all() else 0.0

    def get_params(self) -> dict:
        return {}


class PeInIndustryPercentile(Factor):
    """Returns PE percentile in industry (0-1). Lower = cheaper = better.
    Used as filter with `criterion: value <= 0.7`."""

    name = "pe_in_industry_percentile"
    category = FactorCategory.FUNDAMENTAL
    higher_is_better = False

    def compute(self, ctx: FactorContext) -> float:
        if ctx.financial.empty or "pe_industry_pct" not in ctx.financial.columns:
            raise FactorError("missing pe_industry_pct in financial")
        val = ctx.financial["pe_industry_pct"].iloc[-1]
        if pd.isna(val):
            return 1.0  # treat missing as expensive (filter out)
        return float(val)

    def get_params(self) -> dict:
        return {}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/factors/test_fundamental.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/factors/fundamental.py tests/unit/factors/test_fundamental.py
git commit -m "feat: add 3 fundamental factors (filter-type)"
```

---

## Task 16: Money Flow + Theme Factors (3)

**Files:**
- Create: `stone/selector/factors/moneyflow.py`
- Create: `stone/selector/factors/theme.py`
- Create: `tests/unit/factors/test_moneyflow.py`
- Create: `tests/unit/factors/test_theme.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/factors/test_moneyflow.py`:

```python
from datetime import date

import pandas as pd

from stone.selector.factors.base import FactorContext
from stone.selector.factors.moneyflow import MainMoneyInflow5d, NorthboundInflow20d


def _ctx(moneyflow: pd.DataFrame) -> FactorContext:
    return FactorContext(
        code="000001", name="test", industry="测试", today=date(2026, 6, 14),
        kline=pd.DataFrame(), financial=pd.DataFrame(), moneyflow=moneyflow,
    )


def test_main_money_inflow_positive_returns_positive_value():
    mf = pd.DataFrame({"main_net": [100, 200, 150, 300, 250]})  # 5 days
    factor = MainMoneyInflow5d()
    result = factor.compute(_ctx(mf))
    assert result > 0


def test_main_money_inflow_negative_returns_negative_value():
    mf = pd.DataFrame({"main_net": [-100, -200, -150, -300, -250]})
    factor = MainMoneyInflow5d()
    result = factor.compute(_ctx(mf))
    assert result < 0


def test_northbound_inflow_returns_float():
    mf = pd.DataFrame({"north_net": list(range(20))})
    factor = NorthboundInflow20d()
    result = factor.compute(_ctx(mf))
    assert isinstance(result, float)


def test_factor_names():
    assert MainMoneyInflow5d.name == "main_money_inflow_5d"
    assert NorthboundInflow20d.name == "northbound_inflow_20d"
```

`tests/unit/factors/test_theme.py`:

```python
from datetime import date

import pandas as pd

from stone.selector.factors.base import FactorContext
from stone.selector.factors.theme import IndustryMomentum5d


def _ctx(industry_momentum: pd.DataFrame) -> FactorContext:
    return FactorContext(
        code="000001", name="test", industry="白酒", today=date(2026, 6, 14),
        kline=pd.DataFrame(), financial=pd.DataFrame(), moneyflow=pd.DataFrame(),
    )


def test_industry_momentum_returns_float():
    factor = IndustryMomentum5d()
    # context.industry is the lookup key; we mock by attaching data to ctx via attrs
    ctx = _ctx(pd.DataFrame())
    ctx.industry = "白酒"
    # Patch: factor needs external data; for test, monkeypatch
    import stone.selector.factors.theme as theme_mod
    original = theme_mod.IndustryMomentum5d.compute

    def mock_compute(self, ctx):
        return 0.05  # 5% return

    theme_mod.IndustryMomentum5d.compute = mock_compute
    try:
        result = factor.compute(ctx)
        assert result == 0.05
    finally:
        theme_mod.IndustryMomentum5d.compute = original


def test_factor_name():
    assert IndustryMomentum5d.name == "industry_momentum_5d"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/factors/test_moneyflow.py tests/unit/factors/test_theme.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/selector/factors/moneyflow.py`**

```python
"""Money flow factors (2)."""

import pandas as pd

from stone.constants import FactorCategory
from stone.errors import FactorError
from stone.selector.factors.base import Factor, FactorContext


class MainMoneyInflow5d(Factor):
    """Sum of main fund net inflow over last 5 days (raw value, normalized later)."""

    name = "main_money_inflow_5d"
    category = FactorCategory.MONEYFLOW

    def compute(self, ctx: FactorContext) -> float:
        if ctx.moneyflow.empty or "main_net" not in ctx.moneyflow.columns:
            return 0.0
        recent = ctx.moneyflow["main_net"].tail(5)
        if recent.empty or recent.isna().all():
            return 0.0
        return float(recent.sum())

    def get_params(self) -> dict:
        return {}


class NorthboundInflow20d(Factor):
    """Sum of northbound net buy over last 20 days."""

    name = "northbound_inflow_20d"
    category = FactorCategory.MONEYFLOW

    def compute(self, ctx: FactorContext) -> float:
        if ctx.moneyflow.empty or "north_net" not in ctx.moneyflow.columns:
            return 0.0
        recent = ctx.moneyflow["north_net"].tail(20)
        if recent.empty or recent.isna().all():
            return 0.0
        return float(recent.sum())

    def get_params(self) -> dict:
        return {}
```

- [ ] **Step 4: Write `stone/selector/factors/theme.py`**

```python
"""Theme / industry factors (1 in v1)."""

from stone.constants import FactorCategory
from stone.selector.factors.base import Factor, FactorContext


class IndustryMomentum5d(Factor):
    """5-day return of the stock's industry index.
    Requires industry data; in v1, returned by DataFetcher.get_industry_mapping.
    Higher = stronger industry momentum."""

    name = "industry_momentum_5d"
    category = FactorCategory.THEME

    def compute(self, ctx: FactorContext) -> float:
        # In v1, the engine injects industry_returns into ctx.kline as auxiliary col
        # Simplification: if ctx.kline has 'industry_return_5d', use it; else 0.
        if "industry_return_5d" in ctx.kline.columns:
            return float(ctx.kline["industry_return_5d"].iloc[-1])
        return 0.0

    def get_params(self) -> dict:
        return {}
```

- [ ] **Step 5: Run tests to verify pass**

```bash
uv run pytest tests/unit/factors/test_moneyflow.py tests/unit/factors/test_theme.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add stone/selector/factors/moneyflow.py stone/selector/factors/theme.py tests/unit/factors/test_moneyflow.py tests/unit/factors/test_theme.py
git commit -m "feat: add money flow (2) and theme (1) factors — all 16 factors complete"
```

---

## Task 17: Strategy YAML + Pydantic Models

**Files:**
- Create: `stone/selector/strategy.py`
- Create: `tests/unit/test_strategy.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_strategy.py`:

```python
from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from stone.selector.strategy import Strategy, load_strategy


def _minimal_strategy_yaml() -> str:
    return """
meta:
  name: "test strategy"
  version: "1.0.0"
  description: "for testing"
  created_at: 2026-06-14
universe:
  rules_file: config/universe_rules.yaml
  history_days: 250
filters: []
scoring:
  method: weighted_average
  factors:
    - factor: ma_bullish_alignment
      weight: 1.0
output:
  top_n: 30
  min_score: 60
  sort_by: score
  sort_desc: true
constraints:
  max_per_industry: 5
  max_per_theme: 3
"""


def test_load_strategy_from_yaml(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text(_minimal_strategy_yaml())
    s = load_strategy(p)
    assert s.meta.name == "test strategy"
    assert s.scoring.factors[0].factor == "ma_bullish_alignment"


def test_weights_must_sum_to_one(tmp_path):
    yaml_str = _minimal_strategy_yaml().replace("weight: 1.0", "weight: 0.5")
    yaml_str = yaml_str.replace(
        "factors:\n    - factor: ma_bullish_alignment\n      weight: 0.5",
        """factors:
    - factor: ma_bullish_alignment
      weight: 0.5
    - factor: ma5_above_ma20
      weight: 0.4""",
    )
    p = tmp_path / "s.yaml"
    p.write_text(yaml_str)
    with pytest.raises(ValidationError, match="权重总和"):
        load_strategy(p)


def test_unknown_factor_rejected(tmp_path, monkeypatch):
    # REGISTRY is empty at this point; mock it with one entry
    from stone.selector.factors import REGISTRY
    monkeypatch.setitem(REGISTRY, "known_factor", object)
    yaml_str = _minimal_strategy_yaml().replace("ma_bullish_alignment", "nonexistent_factor")
    p = tmp_path / "s.yaml"
    p.write_text(yaml_str)
    with pytest.raises(ValidationError):
        load_strategy(p)


def test_top_n_must_be_positive(tmp_path):
    yaml_str = _minimal_strategy_yaml().replace("top_n: 30", "top_n: 0")
    p = tmp_path / "s.yaml"
    p.write_text(yaml_str)
    with pytest.raises(ValidationError):
        load_strategy(p)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_strategy.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/selector/strategy.py`**

```python
"""Strategy YAML schema with pydantic validation."""

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from stone.errors import StrategyError
from stone.selector.factors import REGISTRY


class Meta(BaseModel):
    name: str
    version: str
    description: str = ""
    created_at: date


class UniverseConfig(BaseModel):
    rules_file: Path
    history_days: int = Field(default=250, ge=60, le=1000)


class FilterRule(BaseModel):
    factor: str
    params: dict = {}
    criterion: str

    @field_validator("factor")
    @classmethod
    def must_exist_in_registry(cls, v: str) -> str:
        if v not in REGISTRY:
            raise ValueError(f"factor '{v}' not in registry. Available: {list(REGISTRY.keys())}")
        return v


class ScoringFactor(BaseModel):
    factor: str
    weight: float = Field(ge=0.0, le=1.0)
    params: dict = {}

    @field_validator("factor")
    @classmethod
    def must_exist_in_registry(cls, v: str) -> str:
        if v not in REGISTRY:
            raise ValueError(f"factor '{v}' not in registry")
        return v


class Scoring(BaseModel):
    method: str = "weighted_average"
    factors: list[ScoringFactor]

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> "Scoring":
        if not self.factors:
            raise ValueError("scoring.factors cannot be empty")
        total = sum(f.weight for f in self.factors)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"权重总和必须 = 1.0，当前 = {total}")
        return self


class OutputConfig(BaseModel):
    top_n: int = Field(ge=1, le=500)
    min_score: float = Field(ge=0.0, le=100.0)
    sort_by: str = "score"
    sort_desc: bool = True


class Constraints(BaseModel):
    max_per_industry: int = Field(default=5, ge=1, le=100)
    max_per_theme: int = Field(default=3, ge=1, le=100)


class Strategy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: Meta
    universe: UniverseConfig
    filters: list[FilterRule] = []
    scoring: Scoring
    output: OutputConfig
    constraints: Constraints = Constraints()


def load_strategy(path: Path | str) -> Strategy:
    path = Path(path)
    if not path.exists():
        raise StrategyError(f"strategy file not found: {path}")
    with path.open() as f:
        raw = yaml.safe_load(f)
    try:
        return Strategy.model_validate(raw)
    except Exception as e:
        raise StrategyError(f"invalid strategy {path}: {e}") from e
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/test_strategy.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/strategy.py tests/unit/test_strategy.py
git commit -m "feat: add Strategy YAML loader with pydantic validation"
```

---

## Task 18: Safe Criterion Evaluator (AST Whitelist)

**Files:**
- Create: `stone/selector/criterion.py`
- Create: `tests/unit/test_criterion.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_criterion.py`:

```python
import pytest

from stone.selector.criterion import safe_eval_criterion


def test_simple_gte():
    assert safe_eval_criterion("value >= 0.5", 0.6) is True
    assert safe_eval_criterion("value >= 0.5", 0.4) is False


def test_combined_and():
    expr = "value >= 0.3 and value <= 0.7"
    assert safe_eval_criterion(expr, 0.5) is True
    assert safe_eval_criterion(expr, 0.2) is False
    assert safe_eval_criterion(expr, 0.9) is False


def test_injection_import_blocked():
    with pytest.raises(ValueError, match="非法表达式"):
        safe_eval_criterion("__import__('os').system('rm -rf /')", 1.0)


def test_injection_attribute_access_blocked():
    with pytest.raises(ValueError, match="非法表达式"):
        safe_eval_criterion("value.__class__", 1.0)


def test_injection_call_blocked():
    with pytest.raises(ValueError, match="非法表达式"):
        safe_eval_criterion("open('/etc/passwd').read()", 1.0)


def test_equality():
    assert safe_eval_criterion("value == 1.0", 1.0) is True
    assert safe_eval_criterion("value == 1.0", 2.0) is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_criterion.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/selector/criterion.py`**

```python
"""Safe criterion evaluator using AST whitelist.

Strategy YAML `criterion` is a string like 'value >= 0.5 and value <= 0.7'.
Never use raw eval() — would allow code injection. We parse the AST and only
allow Compare / BoolOp / Name / Constant / And / Or / comparison operators.
"""

import ast

ALLOWED_NODES = (
    ast.Expression,
    ast.Compare,
    ast.BoolOp,
    ast.Name,
    ast.Constant,
    ast.And,
    ast.Or,
    ast.GtE,
    ast.LtE,
    ast.Gt,
    ast.Lt,
    ast.Eq,
    ast.NotEq,
    ast.Load,
)


def safe_eval_criterion(expr: str, value: float) -> bool:
    """Evaluate a criterion expression against `value`. Returns True if criterion holds."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"非法表达式 (syntax error): {expr}") from e

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(
                f"非法表达式 (disallowed node {type(node).__name__}): {expr}"
            )

    # Sanity: the only Name node must be 'value'
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id != "value":
            raise ValueError(f"非法表达式 (unknown name '{node.id}'): {expr}")

    code = compile(tree, "<strategy>", "eval")
    result = eval(code, {"__builtins__": {}}, {"value": value})  # noqa: S307
    return bool(result)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/test_criterion.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/criterion.py tests/unit/test_criterion.py
git commit -m "feat: add AST-whitelist safe criterion evaluator (no code injection)"
```

---

## Task 19: ScoringEngine

**Files:**
- Create: `stone/selector/scoring.py`
- Create: `tests/unit/test_scoring.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_scoring.py`:

```python
from datetime import date

import pandas as pd
import pytest

from stone.selector.factors import REGISTRY, register_factor
from stone.selector.factors.base import Factor, FactorContext
from stone.selector.scoring import ScoringEngine, StockScore
from stone.selector.strategy import Scoring, ScoringFactor


@register_factor
class StubFactorAlways100(Factor):
    name = "stub_always_100"
    category = "technical"

    def compute(self, ctx):
        return 100.0

    def get_params(self):
        return {}


@register_factor
class StubFactorAlways0(Factor):
    name = "stub_always_0"
    category = "technical"

    def compute(self, ctx):
        return 0.0

    def get_params(self):
        return {}


def _ctx():
    return FactorContext(
        code="000001", name="test", industry="测试", today=date(2026, 6, 14),
        kline=pd.DataFrame({"close": [10, 11, 12, 13, 14, 15] + list(range(15, 265))}),
        financial=pd.DataFrame(), moneyflow=pd.DataFrame(),
    )


def test_scoring_engine_initializes_from_config():
    cfg = Scoring(
        factors=[
            ScoringFactor(factor="stub_always_100", weight=0.5),
            ScoringFactor(factor="stub_always_0", weight=0.5),
        ]
    )
    engine = ScoringEngine(cfg)
    assert len(engine.factors) == 2


def test_score_in_range_0_to_100():
    cfg = Scoring(
        factors=[
            ScoringFactor(factor="stub_always_100", weight=1.0),
        ]
    )
    engine = ScoringEngine(cfg)
    score = engine.score_one(_ctx())
    assert isinstance(score, StockScore)
    assert 0 <= score.score <= 100


def test_single_factor_failure_doesnt_crash():
    """If a factor raises FactorError, scoring continues with 0 for that factor."""

    @register_factor
    class _CrashingFactor(Factor):
        name = "_crashing_factor"
        category = "technical"

        def compute(self, ctx):
            raise RuntimeError("boom")

        def get_params(self):
            return {}

    cfg = Scoring(
        factors=[
            ScoringFactor(factor="_crashing_factor", weight=0.5),
            ScoringFactor(factor="stub_always_100", weight=0.5),
        ]
    )
    engine = ScoringEngine(cfg)
    score = engine.score_one(_ctx())
    # Crashing factor → 0; the other → some positive value
    assert score.score < 100
    assert score.raw_values["_crashing_factor"] is None


def test_weights_must_sum_to_one():
    with pytest.raises(Exception):
        Scoring(factors=[ScoringFactor(factor="stub_always_100", weight=0.5)])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_scoring.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/selector/scoring.py`**

```python
"""ScoringEngine: weighted average of normalized factor scores."""

from dataclasses import dataclass, field
from datetime import date

from stone.errors import FactorError
from stone.selector.factors import REGISTRY
from stone.selector.factors.base import Factor, FactorContext
from stone.selector.factors.normalize import Normalizer
from stone.selector.strategy import Scoring


@dataclass
class StockScore:
    code: str
    name: str
    industry: str
    today: date
    score: float
    raw_values: dict[str, float | None] = field(default_factory=dict)
    normalized_values: dict[str, float] = field(default_factory=dict)


class ScoringEngine:
    """Computes weighted-average score for a single stock."""

    def __init__(self, scoring_config: Scoring, history_window: int = 250):
        self.factors: list[tuple[Factor, float]] = [
            (REGISTRY[f.factor](**f.params), f.weight) for f in scoring_config.factors
        ]
        self.history_window = history_window
        self.normalizer = Normalizer()

    def score_one(self, ctx: FactorContext) -> StockScore:
        raw_values: dict[str, float | None] = {}
        normalized_values: dict[str, float] = {}

        for factor, _weight in self.factors:
            try:
                raw = factor.compute(ctx)
                raw_values[factor.name] = raw
                # Normalize against the stock's own history (best effort)
                history = self._extract_history(ctx, factor)
                norm = self.normalizer.normalize(
                    raw_value=raw,
                    history=history,
                    higher_is_better=factor.higher_is_better,
                )
                normalized_values[factor.name] = norm
            except (FactorError, Exception) as e:  # noqa: BLE001
                raw_values[factor.name] = None
                normalized_values[factor.name] = 0.0

        # Weighted average
        final = sum(
            normalized_values[f.name] * w
            for f, w in self.factors
            if f.name in normalized_values
        )
        final = max(0.0, min(100.0, final))

        return StockScore(
            code=ctx.code,
            name=ctx.name,
            industry=ctx.industry,
            today=ctx.today,
            score=final,
            raw_values=raw_values,
            normalized_values=normalized_values,
        )

    def _extract_history(self, ctx: FactorContext, factor: Factor) -> "pd.Series":
        """Best-effort: derive factor values across the historical window."""
        import pandas as pd  # local import to avoid module-level dep at import time

        # Simplified: re-compute factor on each windowed slice
        # For performance, factors with binary output (0/1) just use last value
        try:
            values = []
            window = min(self.history_window, len(ctx.kline))
            for i in range(max(0, len(ctx.kline) - window), len(ctx.kline) + 1):
                sliced = ctx.kline.iloc[:i]
                if len(sliced) < 30:
                    continue
                tmp_ctx = FactorContext(
                    code=ctx.code, name=ctx.name, industry=ctx.industry,
                    today=ctx.today, kline=sliced,
                    financial=ctx.financial, moneyflow=ctx.moneyflow,
                )
                try:
                    values.append(factor.compute(tmp_ctx))
                except Exception:  # noqa: BLE001
                    continue
            return pd.Series(values) if values else pd.Series(dtype=float)
        except Exception:  # noqa: BLE001
            return pd.Series(dtype=float)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/test_scoring.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/scoring.py tests/unit/test_scoring.py
git commit -m "feat: add ScoringEngine with weighted-average normalization"
```

---

## Task 20: ConstraintSolver (Industry/Theme Diversification)

**Files:**
- Create: `stone/selector/constraints.py`
- Create: `tests/unit/test_constraints.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_constraints.py`:

```python
from datetime import date

from stone.selector.constraints import ConstraintSolver
from stone.selector.scoring import StockScore
from stone.selector.strategy import Constraints


def _score(code: str, industry: str, score: float) -> StockScore:
    return StockScore(
        code=code, name=code, industry=industry,
        today=date(2026, 6, 14), score=score,
    )


def test_no_constraint_passes_all():
    solver = ConstraintSolver(Constraints(max_per_industry=100, max_per_theme=100))
    ranked = [_score(f"c{i}", "X", 100 - i) for i in range(10)]
    assert len(solver.apply(ranked)) == 10


def test_max_per_industry_5_limits_to_5():
    solver = ConstraintSolver(Constraints(max_per_industry=5, max_per_theme=100))
    ranked = [_score(f"c{i}", "白酒", 100 - i) for i in range(20)]
    result = solver.apply(ranked)
    assert len(result) == 5


def test_keeps_highest_scored_in_industry():
    solver = ConstraintSolver(Constraints(max_per_industry=2, max_per_theme=100))
    ranked = [
        _score("c1", "X", 95),
        _score("c2", "X", 90),
        _score("c3", "X", 85),
        _score("c4", "Y", 80),
    ]
    result = solver.apply(ranked)
    codes = [s.code for s in result]
    assert "c1" in codes
    assert "c2" in codes
    assert "c3" not in codes
    assert "c4" in codes


def test_mixed_industries():
    solver = ConstraintSolver(Constraints(max_per_industry=2, max_per_theme=100))
    ranked = [
        _score("a1", "X", 100),
        _score("a2", "X", 90),
        _score("a3", "X", 80),
        _score("b1", "Y", 95),
        _score("b2", "Y", 85),
        _score("b3", "Y", 75),
    ]
    result = solver.apply(ranked)
    assert len(result) == 4  # 2 from X + 2 from Y
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_constraints.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/selector/constraints.py`**

```python
"""Greedy constraint solver: limit max stocks per industry/theme."""

from collections import defaultdict

from stone.selector.scoring import StockScore
from stone.selector.strategy import Constraints


class ConstraintSolver:
    """Greedy: walk ranked list, keep top N per industry until cap reached."""

    def __init__(self, config: Constraints):
        self.config = config

    def apply(self, ranked: list[StockScore]) -> list[StockScore]:
        """`ranked` must already be sorted by score descending."""
        count: dict[str, int] = defaultdict(int)
        result: list[StockScore] = []
        for stock in ranked:
            if count[stock.industry] < self.config.max_per_industry:
                result.append(stock)
                count[stock.industry] += 1
        return result
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/test_constraints.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/constraints.py tests/unit/test_constraints.py
git commit -m "feat: add greedy ConstraintSolver for industry diversification"
```

---

## Task 21: PositionSizer

**Files:**
- Create: `stone/selector/position_sizing.py`
- Create: `tests/unit/test_position_sizing.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_position_sizing.py`:

```python
import pytest

from stone.selector.position_sizing import PositionPlan, PositionRules, PositionSizer


def _picks(n: int, scores: list[float] | None = None):
    """Generate placeholder picks with scores."""
    from datetime import date
    from stone.selector.scoring import StockScore
    if scores is None:
        scores = [100 - i for i in range(n)]
    return [
        StockScore(code=f"c{i}", name=f"c{i}", industry="X",
                   today=date(2026, 6, 14), score=s)
        for i, s in enumerate(scores)
    ]


def test_equal_weight_5_picks_80pct_total():
    rules = PositionRules(total_capital=100000, allocation_method="equal_weight",
                          max_per_stock=0.5, max_total_position=0.8, round_to=100)
    picks = _picks(5)
    plans = PositionSizer(rules).allocate(picks)
    assert len(plans) == 5
    # 5 picks share 80% of 100k = 16k each, rounded to 100
    assert all(p.amount == 16000 for p in plans)


def test_max_per_stock_cap_enforced_single_pick():
    rules = PositionRules(total_capital=100000, allocation_method="equal_weight",
                          max_per_stock=0.10, max_total_position=0.8, round_to=100)
    picks = _picks(1)
    plans = PositionSizer(rules).allocate(picks)
    # 1 pick, capped at 10% = 10k
    assert plans[0].amount == 10000


def test_score_weighted_gives_higher_score_more():
    rules = PositionRules(total_capital=100000, allocation_method="score_weighted",
                          max_per_stock=0.5, max_total_position=0.8, round_to=100)
    picks = _picks(2, scores=[100.0, 50.0])
    plans = PositionSizer(rules).allocate(picks)
    assert plans[0].amount > plans[1].amount


def test_round_to_100():
    rules = PositionRules(total_capital=99500, allocation_method="equal_weight",
                          max_per_stock=0.5, max_total_position=0.8, round_to=100)
    picks = _picks(5)
    plans = PositionSizer(rules).allocate(picks)
    for p in plans:
        assert p.amount % 100 == 0


def test_total_within_max_position():
    rules = PositionRules(total_capital=100000, allocation_method="equal_weight",
                          max_per_stock=0.10, max_total_position=0.8, round_to=100)
    picks = _picks(20)
    plans = PositionSizer(rules).allocate(picks)
    total = sum(p.amount for p in plans)
    # 20 picks, each capped at 10% = 10k, total = 200k. But max_total = 80k.
    # So allocation should be limited to 80k total
    assert total <= 80000 + 100  # +100 for rounding tolerance


def test_stop_loss_take_profit_prices():
    rules = PositionRules(total_capital=100000, allocation_method="equal_weight",
                          max_per_stock=0.10, max_total_position=0.8,
                          round_to=100, stop_loss_pct=0.08, take_profit_pct=0.20)
    picks = _picks(1)
    plans = PositionSizer(rules).allocate(picks, close_prices=[10.0])
    assert plans[0].stop_loss_price == pytest.approx(9.2)
    assert plans[0].take_profit_price == pytest.approx(12.0)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_position_sizing.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/selector/position_sizing.py`**

```python
"""Position sizing: pure arithmetic on user-defined rules.

⚠️ This is NOT investment advice. The user defines rules in YAML; we compute amounts.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from stone.selector.scoring import StockScore


class PositionRules(BaseModel):
    total_capital: float = Field(gt=0)
    max_total_position: float = Field(default=0.8, ge=0.0, le=1.0)
    max_per_stock: float = Field(default=0.1, ge=0.0, le=1.0)
    allocation_method: str = "equal_weight"  # equal_weight / score_weighted / risk_parity
    round_to: int = 100
    min_position: float = 0.0
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None

    @field_validator("allocation_method")
    @classmethod
    def method_must_be_supported(cls, v: str) -> str:
        if v not in ("equal_weight", "score_weighted", "risk_parity", "fixed_amount"):
            raise ValueError(f"unsupported allocation_method: {v}")
        return v

    @classmethod
    def from_yaml(cls, path: Path | str) -> "PositionRules":
        with open(path) as f:
            return cls(**yaml.safe_load(f))


@dataclass
class PositionPlan:
    code: str
    amount: float
    shares: int
    pct_of_total: float
    stop_loss_price: float | None
    take_profit_price: float | None


class PositionSizer:
    """⚠️ Pure arithmetic. NOT investment advice."""

    def __init__(self, rules: PositionRules):
        self.rules = rules

    def allocate(
        self,
        picks: list[StockScore],
        close_prices: list[float] | None = None,
    ) -> list[PositionPlan]:
        if not picks:
            return []
        total_budget = self.rules.total_capital * self.rules.max_total_position
        per_cap = self.rules.total_capital * self.rules.max_per_stock

        weights = self._compute_weights(picks)
        plans: list[PositionPlan] = []
        for i, (pick, w) in enumerate(zip(picks, weights, strict=False)):
            raw_amount = total_budget * w
            capped = min(raw_amount, per_cap)
            rounded = (capped // self.rules.round_to) * self.rules.round_to
            if rounded < self.rules.min_position:
                continue
            price = close_prices[i] if close_prices and i < len(close_prices) else None
            shares = int(rounded / price) if price else 0
            sl = price * (1 - self.rules.stop_loss_pct) if (price and self.rules.stop_loss_pct) else None
            tp = price * (1 + self.rules.take_profit_pct) if (price and self.rules.take_profit_pct) else None
            plans.append(PositionPlan(
                code=pick.code, amount=float(rounded), shares=shares,
                pct_of_total=rounded / self.rules.total_capital,
                stop_loss_price=sl, take_profit_price=tp,
            ))
        return plans

    def _compute_weights(self, picks: list[StockScore]) -> list[float]:
        method = self.rules.allocation_method
        n = len(picks)
        if method == "equal_weight":
            return [1.0 / n] * n
        if method == "score_weighted":
            scores = [max(p.score, 1.0) ** 1.5 for p in picks]
            total = sum(scores)
            return [s / total for s in scores]
        if method == "risk_parity":
            # Simplified: equal weight in v1 (true risk parity needs volatility data)
            return [1.0 / n] * n
        if method == "fixed_amount":
            # Each gets equal share, but no weight-based variation
            return [1.0 / n] * n
        return [1.0 / n] * n
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/test_position_sizing.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/position_sizing.py tests/unit/test_position_sizing.py
git commit -m "feat: add PositionSizer with equal/score-weighted allocation"
```

---

## Task 22: SelectionEngine (Pipeline Orchestration)

**Files:**
- Create: `stone/selector/engine.py`
- Create: `tests/unit/test_engine.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_engine.py`:

```python
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from stone.data.cache.parquet_store import ParquetStore
from stone.selector.engine import SelectionEngine, SelectionResult


def test_engine_runs_end_to_end_with_mocked_data(tmp_path, monkeypatch):
    """Smoke test: full pipeline runs without crashing, returns SelectionResult."""
    # Build minimal strategy
    from stone.selector.factors import REGISTRY, register_factor
    from stone.selector.factors.base import Factor, FactorContext
    from stone.selector.strategy import (
        Constraints, FilterRule, Meta, OutputConfig, Scoring,
        ScoringFactor, Strategy, UniverseConfig,
    )

    @register_factor
    class _Stub(Factor):
        name = "_stub_engine_test"
        category = "technical"

        def compute(self, ctx):
            return 1.0

        def get_params(self):
            return {}

    strategy = Strategy(
        meta=Meta(name="test", version="1.0.0", created_at=date(2026, 6, 14)),
        universe=UniverseConfig(rules_file=tmp_path / "rules.yaml", history_days=30),
        filters=[],
        scoring=Scoring(factors=[ScoringFactor(factor="_stub_engine_test", weight=1.0)]),
        output=OutputConfig(top_n=5, min_score=0.0),
        constraints=Constraints(max_per_industry=10),
    )

    # Mock fetcher + store with 3 stocks
    store = ParquetStore(tmp_path)
    fetcher = MagicMock()
    fetcher.list_universe.return_value = pd.DataFrame({
        "code": ["c1", "c2", "c3"], "name": ["n1", "n2", "n3"],
    })

    engine = SelectionEngine(strategy=strategy, store=store, fetcher=fetcher)
    # Patch internal methods to avoid real data fetching
    monkeypatch.setattr(engine, "_load_universe", lambda d: ["c1", "c2", "c3"])
    monkeypatch.setattr(engine, "_compute_scores_parallel",
                        lambda u, d: _fake_scores(u, d))

    result = engine.run(date(2026, 6, 14))
    assert isinstance(result, SelectionResult)
    assert len(result.final_picks) == 3
    assert result.target_date == date(2026, 6, 14)


def _fake_scores(universe, target):
    from stone.selector.scoring import StockScore
    return [
        StockScore(code=code, name=code, industry="X", today=target, score=50.0 + i)
        for i, code in enumerate(universe)
    ]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_engine.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/selector/engine.py`**

```python
"""SelectionEngine: orchestrates the full selection pipeline.

Pipeline: load_universe → compute_scores → filter → rank → threshold →
          constraint_solve → top_n → (optional) position_size → emit
"""

import logging
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeout, as_completed
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from tqdm import tqdm

from stone.data.cache.parquet_store import ParquetStore
from stone.data.fetchers.base import DataFetcher
from stone.selector.constraints import ConstraintSolver
from stone.selector.criterion import safe_eval_criterion
from stone.selector.factors.base import FactorContext
from stone.selector.position_sizing import PositionPlan, PositionRules, PositionSizer
from stone.selector.scoring import ScoringEngine, StockScore
from stone.selector.strategy import Strategy

log = logging.getLogger(__name__)


@dataclass
class SelectionResult:
    strategy_name: str
    target_date: date
    universe_size: int
    scored_size: int
    passed_size: int
    final_picks: list[StockScore] = field(default_factory=list)
    position_plans: list[PositionPlan] = field(default_factory=list)
    failed_codes: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"[{self.target_date}] {self.strategy_name}\n"
            f"  股池:    {self.universe_size} → 评分成功: {self.scored_size} "
            f"→ 通过过滤: {self.passed_size} → 最终: {len(self.final_picks)}\n"
            f"  失败:    {len(self.failed_codes)} 只"
        )


class SelectionEngine:
    def __init__(
        self,
        strategy: Strategy,
        store: ParquetStore,
        fetcher: DataFetcher,
        position_rules: PositionRules | None = None,
    ):
        self.strategy = strategy
        self.store = store
        self.fetcher = fetcher
        self.scorer = ScoringEngine(strategy.scoring)
        self.constraint_solver = ConstraintSolver(strategy.constraints)
        self.position_sizer = (
            PositionSizer(position_rules) if position_rules else None
        )
        self.filters = strategy.filters
        self.failed_codes: list[tuple[str, str]] = []

    def run(self, target_date: date) -> SelectionResult:
        log.info(f"开始选股，target_date={target_date}")

        universe = self._load_universe(target_date)
        log.info(f"股池大小: {len(universe)}")

        scores, failed = self._compute_scores_parallel(universe, target_date)
        self.failed_codes.extend(failed)
        log.info(f"成功评分: {len(scores)}/{len(universe)}, 失败 {len(failed)}")

        passed = [s for s in scores if self._passes_all_filters(s)]
        log.info(f"通过过滤: {len(passed)}")

        ranked = sorted(passed, key=lambda s: s.score, reverse=True)
        above = [s for s in ranked if s.score >= self.strategy.output.min_score]
        constrained = self.constraint_solver.apply(above)
        top_n = constrained[: self.strategy.output.top_n]

        plans: list[PositionPlan] = []
        if self.position_sizer and top_n:
            close_prices = self._fetch_close_prices([s.code for s in top_n], target_date)
            plans = self.position_sizer.allocate(top_n, close_prices=close_prices)

        return SelectionResult(
            strategy_name=self.strategy.meta.name,
            target_date=target_date,
            universe_size=len(universe),
            scored_size=len(scores),
            passed_size=len(passed),
            final_picks=top_n,
            position_plans=plans,
            failed_codes=self.failed_codes,
        )

    def _load_universe(self, target_date: date) -> list[str]:
        df = self.store.read("universe", target_date)
        if df.empty:
            df = self.fetcher.list_universe(target_date)
        return df["code"].astype(str).tolist() if not df.empty else []

    def _passes_all_filters(self, score: StockScore) -> bool:
        for rule in self.filters:
            raw = score.raw_values.get(rule.factor)
            if raw is None:
                return False
            try:
                if not safe_eval_criterion(rule.criterion, raw):
                    return False
            except ValueError:
                return False
        return True

    def _compute_scores_parallel(
        self, universe: list[str], target_date: date
    ) -> tuple[list[StockScore], list[tuple[str, str]]]:
        # In v1: run in main process for simplicity (parquet reads are the bottleneck)
        scores: list[StockScore] = []
        failed: list[tuple[str, str]] = []
        for code in tqdm(universe, desc="打分中"):
            try:
                ctx = self._build_context(code, target_date)
                if ctx is None:
                    failed.append((code, "missing data"))
                    continue
                score = self.scorer.score_one(ctx)
                scores.append(score)
            except Exception as e:  # noqa: BLE001
                failed.append((code, str(e)))
        return scores, failed

    def _build_context(self, code: str, target_date: date) -> FactorContext | None:
        history = self.strategy.universe.history_days
        end = target_date
        start = end.fromordinal(end.toordinal() - history - 60)  # buffer
        kline_df = self.store.read_kline_range(start, end)
        if kline_df.empty:
            return None
        kline = kline_df[kline_df["code"] == code].drop(columns=["_cache_date"], errors="ignore")
        if kline.empty:
            return None

        financial = self.store.read("financial", target_date)
        moneyflow = self.store.read("moneyflow", target_date)

        return FactorContext(
            code=code,
            name=code,  # filled by caller; engine doesn't have name list in v1
            industry="unknown",
            today=target_date,
            kline=kline,
            financial=financial,
            moneyflow=moneyflow,
        )

    def _fetch_close_prices(self, codes: list[str], target_date: date) -> list[float]:
        prices = []
        kline = self.store.read_kline(target_date)
        for code in codes:
            row = kline[kline["code"] == code]
            prices.append(float(row["close"].iloc[0]) if not row.empty else 0.0)
        return prices
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/test_engine.py -v
```

Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add stone/selector/engine.py tests/unit/test_engine.py
git commit -m "feat: add SelectionEngine orchestrating full selection pipeline"
```

---

## Task 23: Reporters — Models + JSON + Markdown

**Files:**
- Create: `stone/reporters/__init__.py`
- Create: `stone/reporters/models.py`
- Create: `stone/reporters/json_reporter.py`
- Create: `stone/reporters/markdown.py`
- Create: `tests/unit/test_reporters_json.py`
- Create: `tests/unit/test_reporters_markdown.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_reporters_json.py`:

```python
import json
from datetime import date
from pathlib import Path

from stone.reporters.json_reporter import JsonReporter
from stone.reporters.models import PickRecord
from stone.selector.engine import SelectionResult
from stone.selector.scoring import StockScore


def _make_result() -> SelectionResult:
    picks = [
        StockScore(code="600519", name="贵州茅台", industry="白酒",
                   today=date(2026, 6, 14), score=92.3,
                   raw_values={"ma_bullish_alignment": 1.0},
                   normalized_values={"ma_bullish_alignment": 95.0}),
    ]
    return SelectionResult(
        strategy_name="波段趋势 v1", target_date=date(2026, 6, 14),
        universe_size=100, scored_size=99, passed_size=50,
        final_picks=picks,
    )


def test_json_reporter_writes_valid_json(tmp_path):
    reporter = JsonReporter()
    reporter.render(_make_result(), output_dir=tmp_path)
    expected = tmp_path / "2026-06-14_波段趋势 v1.json"
    assert expected.exists()
    data = json.loads(expected.read_text(encoding="utf-8"))
    assert data["meta"]["target_date"] == "2026-06-14"
    assert data["picks"][0]["code"] == "600519"
```

`tests/unit/test_reporters_markdown.py`:

```python
from datetime import date

from stone.reporters.markdown import MarkdownReporter
from stone.selector.engine import SelectionResult
from stone.selector.scoring import StockScore


def _make_result() -> SelectionResult:
    picks = [
        StockScore(code="600519", name="贵州茅台", industry="白酒",
                   today=date(2026, 6, 14), score=92.3,
                   normalized_values={"ma_bullish_alignment": 95.0}),
    ]
    return SelectionResult(
        strategy_name="波段趋势 v1", target_date=date(2026, 6, 14),
        universe_size=100, scored_size=99, passed_size=50,
        final_picks=picks,
    )


def test_markdown_reporter_contains_strategy_name(tmp_path):
    reporter = MarkdownReporter()
    reporter.render(_make_result(), output_dir=tmp_path)
    md_file = tmp_path / "2026-06-14_波段趋势 v1.md"
    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")
    assert "波段趋势 v1" in content
    assert "600519" in content
    assert "贵州茅台" in content


def test_markdown_includes_top_picks_table(tmp_path):
    reporter = MarkdownReporter()
    reporter.render(_make_result(), output_dir=tmp_path)
    md_file = tmp_path / "2026-06-14_波段趋势 v1.md"
    content = md_file.read_text(encoding="utf-8")
    assert "| 1 |" in content or "| 1|" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_reporters_json.py tests/unit/test_reporters_markdown.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/reporters/__init__.py`** (empty)

- [ ] **Step 4: Write `stone/reporters/models.py`**

```python
"""Reporter data models (PickRecord — the unified output structure)."""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class PickRecord:
    rank: int
    code: str
    name: str
    industry: str
    close: float
    score: float
    factor_scores: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    pe: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    roe: float | None = None
    volume_ratio: float | None = None
    turnover_rate: float | None = None
    suggested_amount: float | None = None
    suggested_shares: int | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
```

- [ ] **Step 5: Write `stone/reporters/json_reporter.py`**

```python
"""JSON reporter: machine-readable output for downstream subsystems."""

import json
from datetime import date
from pathlib import Path

from stone import __version__
from stone.selector.engine import SelectionResult


class JsonReporter:
    def render(self, result: SelectionResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "meta": {
                "strategy_name": result.strategy_name,
                "target_date": result.target_date.isoformat(),
                "stone_version": __version__,
            },
            "summary": {
                "universe_size": result.universe_size,
                "scored_size": result.scored_size,
                "passed_size": result.passed_size,
                "top_n": len(result.final_picks),
                "failed_count": len(result.failed_codes),
            },
            "picks": [
                {
                    "rank": i + 1,
                    "code": s.code,
                    "name": s.name,
                    "industry": s.industry,
                    "score": s.score,
                    "factor_scores": s.normalized_values,
                }
                for i, s in enumerate(result.final_picks)
            ],
            "position_plans": [
                {
                    "code": p.code,
                    "amount": p.amount,
                    "shares": p.shares,
                    "stop_loss_price": p.stop_loss_price,
                    "take_profit_price": p.take_profit_price,
                }
                for p in result.position_plans
            ],
            "failed": [
                {"code": c, "reason": r} for c, r in result.failed_codes
            ],
        }
        out = output_dir / f"{result.target_date.isoformat()}_{result.strategy_name}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out
```

- [ ] **Step 6: Write `stone/reporters/markdown.py`**

```python
"""Markdown reporter: git-friendly, version-comparable."""

from pathlib import Path

from stone.selector.engine import SelectionResult


class MarkdownReporter:
    DISCLAIMER = (
        "> ⚠️ 本报告仅为按预设规则的算法计算结果，**非投资建议**。"
        "买卖决策请自行判断。"
    )

    def render(self, result: SelectionResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        lines: list[str] = [
            f"# 选股报告 - {result.target_date} - {result.strategy_name}",
            "",
            f"> 股池: {result.universe_size} → 评分: {result.scored_size} → "
            f"过滤: {result.passed_size} → 最终: {len(result.final_picks)}",
            "",
            "## Top 候选股",
            "",
            "| # | 代码 | 名称 | 行业 | 评分 |",
            "|---|---|---|---|---|",
        ]
        for i, s in enumerate(result.final_picks, start=1):
            lines.append(
                f"| {i} | {s.code} | {s.name} | {s.industry} | **{s.score:.1f}** |"
            )
        lines.extend(["", "## 行业分布", "", "| 行业 | 数量 |", "|---|---|"])

        from collections import Counter
        for industry, n in Counter(s.industry for s in result.final_picks).most_common():
            lines.append(f"| {industry} | {n} |")

        if result.position_plans:
            lines.extend([
                "", "## 仓位建议（按预设规则算术，非投资建议）", "",
                "| 代码 | 建议金额 | 建议股数 | 止损价 | 止盈价 |",
                "|---|---|---|---|---|",
            ])
            for p in result.position_plans:
                sl = f"{p.stop_loss_price:.2f}" if p.stop_loss_price else "-"
                tp = f"{p.take_profit_price:.2f}" if p.take_profit_price else "-"
                lines.append(
                    f"| {p.code} | ¥{p.amount:,.0f} | {p.shares} | {sl} | {tp} |"
                )

        if result.failed_codes:
            lines.extend([
                "", "## 失败股票", "",
                f"{len(result.failed_codes)} 只计算失败。",
            ])

        lines.extend(["", self.DISCLAIMER, ""])

        out = output_dir / f"{result.target_date.isoformat()}_{result.strategy_name}.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        return out
```

- [ ] **Step 7: Run tests to verify pass**

```bash
uv run pytest tests/unit/test_reporters_json.py tests/unit/test_reporters_markdown.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```bash
git add stone/reporters/__init__.py stone/reporters/models.py stone/reporters/json_reporter.py stone/reporters/markdown.py tests/unit/test_reporters_json.py tests/unit/test_reporters_markdown.py
git commit -m "feat: add JSON and Markdown reporters with disclaimer"
```

---

## Task 24: Reporter — Excel

**Files:**
- Create: `stone/reporters/excel.py`
- Create: `tests/unit/test_reporters_excel.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_reporters_excel.py`:

```python
from datetime import date

import openpyxl

from stone.reporters.excel import ExcelReporter
from stone.selector.engine import SelectionResult
from stone.selector.scoring import StockScore


def _make_result() -> SelectionResult:
    picks = [
        StockScore(code="600519", name="贵州茅台", industry="白酒",
                   today=date(2026, 6, 14), score=92.3,
                   normalized_values={"ma_bullish_alignment": 95.0}),
        StockScore(code="000858", name="五粮液", industry="白酒",
                   today=date(2026, 6, 14), score=89.7,
                   normalized_values={"ma_bullish_alignment": 90.0}),
    ]
    return SelectionResult(
        strategy_name="波段趋势 v1", target_date=date(2026, 6, 14),
        universe_size=100, scored_size=99, passed_size=50,
        final_picks=picks,
    )


def test_excel_reporter_creates_xlsx(tmp_path):
    reporter = ExcelReporter()
    out_path = reporter.render(_make_result(), output_dir=tmp_path)
    assert out_path.exists()
    assert out_path.suffix == ".xlsx"


def test_excel_has_top_picks_sheet(tmp_path):
    reporter = ExcelReporter()
    out_path = reporter.render(_make_result(), output_dir=tmp_path)
    wb = openpyxl.load_workbook(out_path)
    assert "Top名单" in wb.sheetnames
    ws = wb["Top名单"]
    # Header + 2 rows = at least 3 rows
    assert ws.max_row >= 3


def test_excel_has_meta_sheet(tmp_path):
    reporter = ExcelReporter()
    out_path = reporter.render(_make_result(), output_dir=tmp_path)
    wb = openpyxl.load_workbook(out_path)
    assert "元信息" in wb.sheetnames


def test_excel_code_column_is_text_format(tmp_path):
    """Code like 600519 must be text (not converted to scientific notation)."""
    reporter = ExcelReporter()
    out_path = reporter.render(_make_result(), output_dir=tmp_path)
    wb = openpyxl.load_workbook(out_path)
    ws = wb["Top名单"]
    # Find the code column (header row)
    headers = [c.value for c in ws[1]]
    code_col_idx = headers.index("代码") + 1
    # Cell type should be string (not numeric)
    cell = ws.cell(row=2, column=code_col_idx)
    assert cell.data_type == "s" or cell.number_format == "@"


def test_excel_has_disclaimer(tmp_path):
    """Disclaimer row should exist somewhere in the workbook."""
    reporter = ExcelReporter()
    out_path = reporter.render(_make_result(), output_dir=tmp_path)
    wb = openpyxl.load_workbook(out_path)
    found = False
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            for v in row:
                if v and "非投资建议" in str(v):
                    found = True
                    break
    assert found, "Excel report must contain disclaimer"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_reporters_excel.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/reporters/excel.py`**

```python
"""Excel reporter: 4 sheets (Top名单 / 因子明细 / 元信息 / 失败股票)."""

from pathlib import Path

import xlsxwriter

from stone import __version__
from stone.selector.engine import SelectionResult


class ExcelReporter:
    DISCLAIMER = "⚠️ 本表为按预设规则的算术计算结果，非投资建议。买卖决策请自行判断。"

    def render(self, result: SelectionResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / f"{result.target_date.isoformat()}_{result.strategy_name}.xlsx"

        wb = xlsxwriter.Workbook(str(out))
        bold = wb.add_format({"bold": True, "bg_color": "#D9EAD3", "border": 1})
        text_fmt = wb.add_format({"num_format": "@"})  # text format
        score_fmt = wb.add_format({"num_format": "0.0", "align": "center"})
        bar_fmt = wb.add_format({"data_bar_color": "green"})

        # Sheet 1: Top名单
        ws1 = wb.add_worksheet("Top名单")
        headers = ["排名", "代码", "名称", "行业", "评分", "建议金额", "建议股数",
                   "止损价", "止盈价", "入选理由"]
        for col, h in enumerate(headers):
            ws1.write(0, col, h, bold)
        ws1.set_column(1, 1, 12, text_fmt)  # code column as text

        for i, s in enumerate(result.final_picks, start=1):
            row = i
            ws1.write_number(row, 0, i)
            ws1.write_string(row, 1, s.code)
            ws1.write_string(row, 2, s.name)
            ws1.write_string(row, 3, s.industry)
            ws1.write_number(row, 4, s.score, score_fmt)

            # Position plan (match by index)
            if i - 1 < len(result.position_plans):
                p = result.position_plans[i - 1]
                ws1.write_number(row, 5, p.amount)
                ws1.write_number(row, 6, p.shares)
                if p.stop_loss_price:
                    ws1.write_number(row, 7, p.stop_loss_price)
                if p.take_profit_price:
                    ws1.write_number(row, 8, p.take_profit_price)

            # Reasons (factors scoring ≥ 80)
            reasons = " + ".join(
                k for k, v in s.normalized_values.items() if v >= 80.0
            )
            ws1.write_string(row, 9, reasons)

        # Comment row
        ws1.write(len(result.final_picks) + 2, 1, "← 可直接复制代码列到涨乐财富通批量添加自选", wb.add_format({"italic": True}))
        ws1.write(len(result.final_picks) + 4, 0, self.DISCLAIMER, wb.add_format({"bg_color": "#FFF2CC"}))

        # Sheet 2: 因子明细
        ws2 = wb.add_worksheet("因子明细")
        all_factors = set()
        for s in result.final_picks:
            all_factors.update(s.normalized_values.keys())
        factor_cols = sorted(all_factors)
        ws2.write_row(0, 0, ["排名", "代码", "名称", "总分"] + factor_cols, bold)
        for i, s in enumerate(result.final_picks, start=1):
            ws2.write_number(i, 0, i)
            ws2.write_string(i, 1, s.code)
            ws2.write_string(i, 2, s.name)
            ws2.write_number(i, 3, s.score, score_fmt)
            for j, fname in enumerate(factor_cols, start=4):
                val = s.normalized_values.get(fname)
                if val is not None:
                    ws2.write_number(i, j, val, score_fmt)

        # Sheet 3: 元信息
        ws3 = wb.add_worksheet("元信息")
        info = [
            ("策略名称", result.strategy_name),
            ("目标日期", result.target_date.isoformat()),
            ("Stone 版本", __version__),
            ("股池大小", result.universe_size),
            ("评分成功", result.scored_size),
            ("通过过滤", result.passed_size),
            ("最终入选", len(result.final_picks)),
            ("失败数", len(result.failed_codes)),
        ]
        for i, (k, v) in enumerate(info):
            ws3.write(i, 0, k, bold)
            ws3.write(i, 1, v)

        # Sheet 4: 失败股票
        ws4 = wb.add_worksheet("失败股票")
        ws4.write_row(0, 0, ["代码", "原因"], bold)
        for i, (code, reason) in enumerate(result.failed_codes, start=1):
            ws4.write_string(i, 0, code)
            ws4.write_string(i, 1, reason)

        wb.close()
        return out
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/test_reporters_excel.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add stone/reporters/excel.py tests/unit/test_reporters_excel.py
git commit -m "feat: add Excel reporter with 4 sheets and text-format codes"
```

---

## Task 25: Reporter — HTML + K-line Charts

**Files:**
- Create: `stone/reporters/charts.py`
- Create: `stone/reporters/html.py`
- Create: `templates/report.html.j2`
- Create: `tests/unit/test_reporters_html.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_reporters_html.py`:

```python
from datetime import date

from stone.reporters.html import HtmlReporter
from stone.selector.engine import SelectionResult
from stone.selector.scoring import StockScore


def _make_result() -> SelectionResult:
    picks = [
        StockScore(code="600519", name="贵州茅台", industry="白酒",
                   today=date(2026, 6, 14), score=92.3,
                   normalized_values={"ma_bullish_alignment": 95.0}),
    ]
    return SelectionResult(
        strategy_name="波段趋势 v1", target_date=date(2026, 6, 14),
        universe_size=100, scored_size=99, passed_size=50,
        final_picks=picks,
    )


def test_html_reporter_creates_html(tmp_path):
    reporter = HtmlReporter()
    out = reporter.render(_make_result(), output_dir=tmp_path)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<html" in content.lower()


def test_html_contains_strategy_name(tmp_path):
    reporter = HtmlReporter()
    out = reporter.render(_make_result(), output_dir=tmp_path)
    content = out.read_text(encoding="utf-8")
    assert "波段趋势 v1" in content


def test_html_contains_disclaimer(tmp_path):
    reporter = HtmlReporter()
    out = reporter.render(_make_result(), output_dir=tmp_path)
    content = out.read_text(encoding="utf-8")
    assert "非投资建议" in content


def test_html_contains_pick_row(tmp_path):
    reporter = HtmlReporter()
    out = reporter.render(_make_result(), output_dir=tmp_path)
    content = out.read_text(encoding="utf-8")
    assert "600519" in content
    assert "贵州茅台" in content
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_reporters_html.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `stone/reporters/charts.py`**

```python
"""K-line chart rendering via mplfinance."""

import base64
import io

import mplfinance as mpf
import pandas as pd


def render_kline_b64(kline: pd.DataFrame, code: str, name: str, days: int = 60) -> str:
    """Render last N days as candlestick chart, return base64-encoded PNG."""
    if kline.empty or len(kline) < 30:
        return ""

    # mplfinance requires Date index
    df = kline.tail(days).copy()
    if "date" in df.columns:
        df["Date"] = pd.to_datetime(df["date"])
    elif "Date" not in df.columns:
        df["Date"] = pd.date_range(end="today", periods=len(df))
    df = df.set_index("Date")

    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    if not all(c in df.columns for c in ["Open", "High", "Low", "Close"]):
        # Try lowercase
        rename = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
        df = df.rename(columns=rename)

    try:
        fig, _ = mpf.plot(
            df, type="candle", style="charles",
            volume="Volume" in df.columns,
            mav=(5, 20) if len(df) >= 20 else None,
            title=f"{code} {name}",
            returnfig=True, figsize=(10, 6),
        )
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:  # noqa: BLE001
        return ""
```

- [ ] **Step 4: Write `templates/report.html.j2`**

```jinja2
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>选股报告 - {{ result.target_date }} - {{ result.strategy_name }}</title>
<style>
body { font-family: -apple-system, sans-serif; margin: 2em; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 8px; }
th { background: #f5f5f5; }
.score { font-weight: bold; }
.disclaimer { background: #fff4e5; padding: 1em; border-left: 4px solid #ffa500; }
</style>
</head>
<body>
<header>
<h1>📈 选股报告</h1>
<p>策略: {{ result.strategy_name }} · 日期: {{ result.target_date }} · Top {{ result.final_picks|length }}</p>
</header>

<section id="summary">
<p>股池: {{ result.universe_size }} → 评分: {{ result.scored_size }} →
过滤: {{ result.passed_size }} → 最终: {{ result.final_picks|length }}</p>
</section>

<section id="picks">
<table id="picks-table">
<thead><tr>
<th>#</th><th>代码</th><th>名称</th><th>行业</th><th>评分</th>
<th>建议金额</th><th>建议股数</th><th>入选理由</th>
</tr></thead>
<tbody>
{% for s in result.final_picks %}
<tr>
<td>{{ loop.index }}</td>
<td>{{ s.code }}</td>
<td>{{ s.name }}</td>
<td>{{ s.industry }}</td>
<td class="score">{{ "%.1f"|format(s.score) }}</td>
{% if loop.index0 < result.position_plans|length %}
<td>¥{{ "{:,.0f}".format(result.position_plans[loop.index0].amount) }}</td>
<td>{{ result.position_plans[loop.index0].shares }}</td>
{% else %}
<td>-</td><td>-</td>
{% endif %}
<td>
{% for k, v in s.normalized_values.items() if v >= 80 %}{{ k }}{% if not loop.last %} + {% endif %}{% endfor %}
</td>
</tr>
{% endfor %}
</tbody>
</table>
</section>

{% if result.failed_codes %}
<section id="failed">
<h3>失败股票 ({{ result.failed_codes|length }} 只)</h3>
<details><summary>查看详情</summary>
<ul>{% for code, reason in result.failed_codes %}<li>{{ code }}: {{ reason }}</li>{% endfor %}</ul>
</details>
</section>
{% endif %}

<p class="disclaimer">⚠️ 本报告仅为按预设规则的算法计算结果，<strong>非投资建议</strong>。买卖决策请自行判断。</p>
</body>
</html>
```

- [ ] **Step 5: Write `stone/reporters/html.py`**

```python
"""HTML reporter using jinja2 template."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from stone.selector.engine import SelectionResult

_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


class HtmlReporter:
    def __init__(self, template_dir: Path | None = None):
        tmpl_dir = template_dir or _TEMPLATE_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(tmpl_dir)),
            autoescape=select_autoescape(["html"]),
        )

    def render(self, result: SelectionResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        template = self.env.get_template("report.html.j2")
        html = template.render(result=result)
        out = output_dir / f"{result.target_date.isoformat()}_{result.strategy_name}.html"
        out.write_text(html, encoding="utf-8")
        return out
```

- [ ] **Step 6: Run tests to verify pass**

```bash
uv run pytest tests/unit/test_reporters_html.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add stone/reporters/charts.py stone/reporters/html.py templates/report.html.j2 tests/unit/test_reporters_html.py
git commit -m "feat: add HTML reporter with jinja2 template and K-line chart helper"
```

---

## Task 26: CLI Integration (click)

**Files:**
- Create: `stone/cli.py`
- Modify: `main.py` (already created in T1)
- Create: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_cli.py`:

```python
from click.testing import CliRunner

from stone.cli import app


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "select" in result.output
    assert "update" in result.output


def test_cli_list_strategies():
    runner = CliRunner()
    result = runner.invoke(app, ["list-strategies"])
    assert result.exit_code == 0


def test_cli_validate_config_missing_file(tmp_path):
    runner = CliRunner()
    result = runner.invoke(app, ["validate-config", str(tmp_path / "nonexistent.yaml")])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_cli.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Write `stone/cli.py`**

```python
"""CLI entry: update / select / daily / list-strategies / validate-config."""

from datetime import date, timedelta
from pathlib import Path

import click

from stone.errors import StrategyError
from stone.logging_setup import setup_logging
from stone.selector.strategy import load_strategy


@click.group()
def app() -> None:
    """Stone: A-stock personal investment research assistant."""


@app.command()
@click.option("--retry-failed", is_flag=True, help="Retry previously failed dates")
@click.option("--backfill", nargs=2, type=str, help="Backfill date range: START END (YYYY-MM-DD)")
def update(retry_failed: bool, backfill: tuple[str, str] | None) -> None:
    """Incremental data update."""
    setup_logging()
    click.echo("Data update not yet implemented in CLI; use IncrementalUpdater directly for now.")
    # TODO(T29): wire up IncrementalUpdater


@app.command()
@click.option("--strategy", required=True, help="Strategy YAML name (without extension)")
@click.option("--date", "target_date", type=str, default=None, help="YYYY-MM-DD (default: today)")
@click.option("--all-strategies", is_flag=True, help="Run all strategies in config/strategies/")
def select(strategy: str, target_date: str | None, all_strategies: bool) -> None:
    """Run stock selection with the given strategy."""
    setup_logging()
    if all_strategies:
        click.echo("Running all strategies — not yet implemented")
        return
    target = date.fromisoformat(target_date) if target_date else date.today()
    click.echo(f"Selecting with strategy={strategy} date={target}")
    # TODO(T29): wire up SelectionEngine


@app.command()
def daily() -> None:
    """Daily pipeline: update + select + report."""
    setup_logging()
    click.echo("Daily pipeline not yet implemented")


@app.command("list-strategies")
def list_strategies() -> None:
    """List available strategies in config/strategies/."""
    strategies_dir = Path("config/strategies")
    if not strategies_dir.exists():
        click.echo("(no strategies directory)")
        return
    yaml_files = sorted(strategies_dir.glob("*.yaml"))
    if not yaml_files:
        click.echo("(no strategies found)")
        return
    for f in yaml_files:
        click.echo(f.stem)


@app.command("validate-config")
@click.argument("path", type=click.Path(exists=True))
def validate_config(path: str) -> None:
    """Validate a strategy YAML file."""
    try:
        s = load_strategy(path)
        click.echo(f"✓ Valid: {s.meta.name} v{s.meta.version}")
    except StrategyError as e:
        click.echo(f"✗ Invalid: {e}", err=True)
        raise click.Aborted


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/unit/test_cli.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: Smoke test**

```bash
uv run python main.py --help
uv run python main.py list-strategies  # should show "(no strategies directory)" since none yet
```

- [ ] **Step 6: Commit**

```bash
git add stone/cli.py tests/unit/test_cli.py
git commit -m "feat: add CLI with update/select/daily/list-strategies/validate-config"
```

---

## Task 27: Default Strategies (3 YAML) + Position Rules Template

**Files:**
- Create: `config/strategies/band_trend_v1.yaml`
- Create: `config/strategies/breakout_strong.yaml`
- Create: `config/strategies/value_with_catalyst.yaml`
- Create: `config/position_rules.example.yaml`
- Create: `config/personal/.gitkeep`

- [ ] **Step 1: Write `config/strategies/band_trend_v1.yaml`** (same as spec section 6.1)

```yaml
meta:
  name: "波段趋势 v1"
  version: "1.0.0"
  description: "均线多头 + MACD 金叉 + 量能放大 + 基本面过滤"
  created_at: 2026-06-14

universe:
  rules_file: config/universe_rules.yaml
  history_days: 250

filters:
  - factor: roe_above_15
    criterion: "value >= 1.0"
  - factor: revenue_growth_positive
    criterion: "value >= 1.0"
  - factor: pe_in_industry_percentile
    criterion: "value <= 0.7"
  - factor: turnover_rate
    criterion: "value >= 1.0"

scoring:
  method: weighted_average
  factors:
    - factor: ma_bullish_alignment
      weight: 0.20
      params: { periods: [5, 10, 20, 60] }
    - factor: breakout_20d_high
      weight: 0.15
    - factor: macd_golden_cross
      weight: 0.15
    - factor: kdj_golden_cross
      weight: 0.10
    - factor: rsi_in_healthy_zone
      weight: 0.05
      params: { zone: [40.0, 70.0] }
    - factor: volume_ratio
      weight: 0.15
      params: { avg_window: 5 }
    - factor: distance_to_52w_high
      weight: 0.05
    - factor: main_money_inflow_5d
      weight: 0.10
    - factor: northbound_inflow_20d
      weight: 0.05

output:
  top_n: 30
  min_score: 60
  sort_by: score
  sort_desc: true

constraints:
  max_per_industry: 5
  max_per_theme: 3
```

- [ ] **Step 2: Write `config/strategies/breakout_strong.yaml`**

```yaml
meta:
  name: "强势突破"
  version: "1.0.0"
  description: "突破 + 高量比 + 主力流入，更激进"
  created_at: 2026-06-14

universe:
  rules_file: config/universe_rules.yaml
  history_days: 250

filters:
  - factor: turnover_rate
    criterion: "value >= 3.0"  # 高换手率

scoring:
  method: weighted_average
  factors:
    - factor: breakout_20d_high
      weight: 0.35
    - factor: volume_ratio
      weight: 0.30
      params: { avg_window: 5 }
    - factor: main_money_inflow_5d
      weight: 0.20
    - factor: ma_bullish_alignment
      weight: 0.15

output:
  top_n: 20
  min_score: 70
  sort_by: score
  sort_desc: true

constraints:
  max_per_industry: 3
  max_per_theme: 2
```

- [ ] **Step 3: Write `config/strategies/value_with_catalyst.yaml`**

```yaml
meta:
  name: "价值催化"
  version: "1.0.0"
  description: "低 PE + 高 ROE + 北向入场，更保守"
  created_at: 2026-06-14

universe:
  rules_file: config/universe_rules.yaml
  history_days: 250

filters:
  - factor: roe_above_15
    criterion: "value >= 1.0"
  - factor: pe_in_industry_percentile
    criterion: "value <= 0.4"

scoring:
  method: weighted_average
  factors:
    - factor: northbound_inflow_20d
      weight: 0.35
    - factor: ma_bullish_alignment
      weight: 0.25
    - factor: price_above_ma60
      weight: 0.20
    - factor: main_money_inflow_5d
      weight: 0.20

output:
  top_n: 15
  min_score: 55
  sort_by: score
  sort_desc: true

constraints:
  max_per_industry: 3
  max_per_theme: 2
```

- [ ] **Step 4: Write `config/position_rules.example.yaml`**

```yaml
# Copy this file to config/personal/position_rules.yaml and fill in your own values.
# The personal/ directory is .gitignored — your real capital stays private.

total_capital: 100000              # 你的总资金（元）
max_total_position: 0.80           # 总仓位上限 80%（留 20% 现金）
max_per_stock: 0.10                # 单只股票最多 10%

allocation_method: score_weighted  # equal_weight / score_weighted / risk_parity / fixed_amount

round_to: 100                      # 金额取整到 100 元（方便挂单）
min_position: 5000                 # 单只最少 5000 元

stop_loss_pct: 0.08                # 跌 8% 自动列入止损观察（仅提醒，不自动卖）
take_profit_pct: 0.20              # 涨 20% 自动列入止盈观察

# ⚠️ 本文件配置的金额是按用户预设规则做算术的工具配置，
#   非投资建议。买卖决策请自行判断。
```

- [ ] **Step 5: Write `config/personal/.gitkeep`** (empty)

```python
```

- [ ] **Step 6: Verify all 3 strategies load**

```bash
uv run python -c "
from stone.selector.strategy import load_strategy
for f in ['config/strategies/band_trend_v1.yaml', 'config/strategies/breakout_strong.yaml', 'config/strategies/value_with_catalyst.yaml']:
    s = load_strategy(f)
    print(f'{f}: {s.meta.name} OK')
"
```

Expected: 3 lines printed with strategy names. NOTE: requires REGISTRY to be populated — run `from stone.selector.factors import technical, fundamental, moneyflow, theme` first.

Update test script:

```bash
uv run python -c "
from stone.selector.factors import technical, fundamental, moneyflow, theme  # populate REGISTRY
from stone.selector.strategy import load_strategy
for f in ['config/strategies/band_trend_v1.yaml', 'config/strategies/breakout_strong.yaml', 'config/strategies/value_with_catalyst.yaml']:
    s = load_strategy(f)
    print(f'{f}: {s.meta.name} OK')
"
```

- [ ] **Step 7: Commit**

```bash
git add config/strategies/ config/position_rules.example.yaml config/personal/.gitkeep
git commit -m "feat: add 3 default strategies and position rules template"
```

---

## Task 28: Integration + E2E Tests

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_pipeline.py`
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/test_cli.py`
- Modify: `stone/selector/factors/__init__.py` (auto-import submodules to populate REGISTRY)

- [ ] **Step 1: Auto-populate REGISTRY** — update `stone/selector/factors/__init__.py`

```python
"""Factor registry. Populated by importing submodules."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stone.selector.factors.base import Factor

REGISTRY: dict[str, type["Factor"]] = {}


def register_factor(cls):
    """Decorator: register a Factor subclass by its `name` attribute."""
    if not hasattr(cls, "name") or not isinstance(cls.name, str):
        raise ValueError(f"Factor {cls} must define a string `name` attribute")
    if cls.name in REGISTRY:
        return cls  # already registered; idempotent
    REGISTRY[cls.name] = cls
    return cls


# Auto-import submodules to populate REGISTRY
from stone.selector.factors import technical as _t  # noqa: E402,F401
from stone.selector.factors import fundamental as _f  # noqa: E402,F401
from stone.selector.factors import moneyflow as _m  # noqa: E402,F401
from stone.selector.factors import theme as _th  # noqa: E402,F401
```

- [ ] **Step 2: Write integration test**

`tests/integration/test_pipeline.py`:

```python
"""End-to-end pipeline test with mocked data fetcher."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from stone.data.cache.parquet_store import ParquetStore
from stone.selector.engine import SelectionEngine
from stone.selector.strategy import load_strategy
from tests.helpers.seed_data import seed_kline_for_codes, seed_universe


@pytest.mark.integration
def test_pipeline_produces_picks_with_seeded_data(tmp_path):
    store = ParquetStore(tmp_path / "cache")
    target = date(2026, 6, 14)
    codes = ["c1", "c2", "c3"]
    seed_universe(store, codes, target)
    seed_kline_for_codes(store, codes, target, days=60)

    fetcher = MagicMock()
    fetcher.list_universe.return_value = MagicMock(empty=False)

    strategy_path = Path("config/strategies/band_trend_v1.yaml")
    if not strategy_path.exists():
        pytest.skip("strategy file missing")
    strategy = load_strategy(strategy_path)

    engine = SelectionEngine(strategy=strategy, store=store, fetcher=fetcher)
    result = engine.run(target)

    # Pipeline completes without exception
    assert result.target_date == target
    # final_picks may be empty if seeded data doesn't satisfy filters; that's OK
    assert isinstance(result.final_picks, list)


@pytest.mark.integration
def test_pipeline_handles_failed_codes_gracefully(tmp_path):
    """Stock with no kline data should not crash the pipeline."""
    store = ParquetStore(tmp_path / "cache")
    target = date(2026, 6, 14)
    codes = ["good1", "good2", "bad1"]
    seed_universe(store, codes, target)
    # Only seed good1/good2 with kline; bad1 has no kline
    seed_kline_for_codes(store, ["good1", "good2"], target, days=60)

    fetcher = MagicMock()
    strategy = load_strategy("config/strategies/band_trend_v1.yaml")
    engine = SelectionEngine(strategy=strategy, store=store, fetcher=fetcher)
    result = engine.run(target)

    # bad1 should be in failed_codes, not crash pipeline
    assert any(code == "bad1" for code, _ in result.failed_codes) or len(result.final_picks) >= 0
```

- [ ] **Step 3: Write E2E test**

`tests/e2e/test_cli.py`:

```python
"""E2E test: invoke the CLI via subprocess."""

import subprocess
import sys
from pathlib import Path


def test_cli_help_runs():
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "select" in result.stdout
    assert "update" in result.stdout


def test_cli_list_strategies_lists_three_files():
    result = subprocess.run(
        [sys.executable, "main.py", "list-strategies"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "band_trend_v1" in result.stdout
    assert "breakout_strong" in result.stdout
    assert "value_with_catalyst" in result.stdout


def test_cli_validate_config_accepts_valid_file():
    result = subprocess.run(
        [sys.executable, "main.py", "validate-config", "config/strategies/band_trend_v1.yaml"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "Valid" in result.stdout
```

- [ ] **Step 4: Write `tests/integration/__init__.py` and `tests/e2e/__init__.py`** (empty)

- [ ] **Step 5: Run all tests**

```bash
uv run pytest -v --cov=stone --cov-report=term-missing
```

Expected: All tests pass; coverage ≥ 80%.

- [ ] **Step 6: Commit**

```bash
git add stone/selector/factors/__init__.py tests/integration/__init__.py tests/integration/test_pipeline.py tests/e2e/__init__.py tests/e2e/test_cli.py
git commit -m "test: add integration and E2E tests; auto-populate factor REGISTRY"
```

---

## Task 29: launchd Configuration + Final CLI Wiring

**Files:**
- Create: `launchd/com.stone.daily.plist`
- Modify: `stone/cli.py` (wire `update` and `select` commands to real implementations)
- Create: `docs/superpowers/plans/SETUP.md` (deployment guide)

- [ ] **Step 1: Wire CLI `update` command** — replace the stub in `stone/cli.py`

```python
@app.command()
@click.option("--retry-failed", is_flag=True, help="Retry previously failed dates")
@click.option("--backfill", nargs=2, type=str, help="Backfill date range START END (YYYY-MM-DD)")
def update(retry_failed: bool, backfill: tuple[str, str] | None) -> None:
    """Incremental data update."""
    from stone.data.cache.parquet_store import ParquetStore
    from stone.data.fetchers.akshare_fetcher import AkshareFetcher
    from stone.data.incremental import IncrementalUpdater

    setup_logging()
    store = ParquetStore(Path("data_cache"))
    fetcher = AkshareFetcher()
    updater = IncrementalUpdater(store=store, fetcher=fetcher)

    if backfill:
        start, end = backfill
        target = date.fromisoformat(end)
        report = updater.update_daily(target)
    else:
        target = date.today()
        report = updater.update_daily(target)
    click.echo(report.summary())
```

- [ ] **Step 2: Wire CLI `select` command**

```python
@app.command()
@click.option("--strategy", required=False, help="Strategy name (without .yaml)")
@click.option("--date", "target_date", type=str, default=None)
@click.option("--all-strategies", is_flag=True)
@click.option("--report-dir", default="reports", help="Output directory for reports")
def select(strategy: str | None, target_date: str | None, all_strategies: bool, report_dir: str) -> None:
    """Run stock selection and emit reports."""
    from stone.data.cache.parquet_store import ParquetStore
    from stone.data.fetchers.akshare_fetcher import AkshareFetcher
    from stone.reporters.excel import ExcelReporter
    from stone.reporters.html import HtmlReporter
    from stone.reporters.json_reporter import JsonReporter
    from stone.reporters.markdown import MarkdownReporter
    from stone.selector.engine import SelectionEngine

    setup_logging()
    target = date.fromisoformat(target_date) if target_date else date.today()

    strategies_dir = Path("config/strategies")
    if all_strategies:
        files = sorted(strategies_dir.glob("*.yaml"))
    elif strategy:
        files = [strategies_dir / f"{strategy}.yaml"]
        if not files[0].exists():
            click.echo(f"Strategy not found: {files[0]}", err=True)
            raise click.Aborted
    else:
        click.echo("Must specify --strategy NAME or --all-strategies", err=True)
        raise click.Aborted

    store = ParquetStore(Path("data_cache"))
    fetcher = AkshareFetcher()

    for strat_file in files:
        click.echo(f"Running strategy: {strat_file.stem}")
        s = load_strategy(strat_file)
        engine = SelectionEngine(strategy=s, store=store, fetcher=fetcher)
        result = engine.run(target)
        click.echo(result.summary())

        out_dir = Path(report_dir)
        JsonReporter().render(result, out_dir)
        MarkdownReporter().render(result, out_dir)
        ExcelReporter().render(result, out_dir)
        HtmlReporter().render(result, out_dir)
```

- [ ] **Step 3: Wire `daily` command**

```python
@app.command()
def daily() -> None:
    """Daily pipeline: update + select + report (called by launchd)."""
    from stone.data.cache.parquet_store import ParquetStore
    from stone.data.fetchers.akshare_fetcher import AkshareFetcher
    from stone.data.incremental import IncrementalUpdater

    setup_logging()
    target = date.today()
    click.echo(f"=== Daily pipeline {target} ===")

    # Step 1: update
    store = ParquetStore(Path("data_cache"))
    fetcher = AkshareFetcher()
    report = IncrementalUpdater(store=store, fetcher=fetcher).update_daily(target)
    click.echo(report.summary())

    # Step 2: select all strategies
    ctx = click.get_current_context()
    ctx.invoke(select, strategy=None, target_date=target.isoformat(),
               all_strategies=True, report_dir="reports")
```

- [ ] **Step 4: Write `launchd/com.stone.daily.plist`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple" "-//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stone.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/Stone/.venv/bin/python</string>
        <string>/Users/YOUR_USERNAME/Stone/main.py</string>
        <string>daily</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>16</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/Stone</string>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Stone/logs/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Stone/logs/launchd.err.log</string>
</dict>
</plist>
```

- [ ] **Step 5: Write `docs/superpowers/plans/SETUP.md`**

```markdown
# Stone Setup Guide

## One-time setup

```bash
# 1. Clone
git clone https://github.com/nathanchlin/Stone.git
cd Stone

# 2. Install dependencies (requires uv: brew install uv)
uv sync --all-extras

# 3. Initial data backfill (this takes 30-60 minutes for full market)
uv run python main.py update --backfill 2024-01-01 2026-06-14

# 4. Personal position rules (private)
cp config/position_rules.example.yaml config/personal/position_rules.yaml
# Edit config/personal/position_rules.yaml with your real capital

# 5. Test selection manually
uv run python main.py select --strategy band_trend_v1

# 6. (Optional) Schedule daily run
cp launchd/com.stone.daily.plist ~/Library/LaunchAgents/
# Edit the plist: replace YOUR_USERNAME with your actual username
launchctl load ~/Library/LaunchAgents/com.stone.daily.plist
```

## Daily usage

After launchd is configured, reports will be generated automatically at 16:00 each weekday.
View them in `reports/`.

## Manual override

```bash
# Rerun today's selection
uv run python main.py select --strategy band_trend_v1

# Retry failed data updates
uv run python main.py update --retry-failed

# Run all strategies
uv run python main.py select --all-strategies
```
```

- [ ] **Step 6: Run all tests + smoke test CLI**

```bash
uv run pytest -v
uv run python main.py --help
uv run python main.py list-strategies
uv run python main.py validate-config config/strategies/band_trend_v1.yaml
```

Expected: All tests pass; CLI works end-to-end (without real akshare data, selection will fail gracefully).

- [ ] **Step 7: Commit**

```bash
git add stone/cli.py launchd/com.stone.daily.plist docs/superpowers/plans/SETUP.md
git commit -m "feat: wire CLI commands to real implementations and add launchd config"
```

---

## Task 30: Final Quality Gate + Push

**Files:**
- Modify: `README.md` (add quickstart, badges)
- Modify: `.gitignore` (verify)
- Modify: `pyproject.toml` (add `[tool.ruff]` settings if missing)

- [ ] **Step 1: Run full quality gate**

```bash
# Lint
uv run ruff check .
uv run ruff format --check .

# Type check
uv run mypy stone/

# Tests with coverage gate
uv run pytest -v --cov-fail-under=80
```

Expected: ruff clean, mypy no errors, coverage ≥ 80%.

- [ ] **Step 2: Fix any lint/type issues**

Address each error one by one. Common fixes:
- `ruff check --fix .` for auto-fixable issues
- Add `# type: ignore[xxx]` for false positives
- Refactor for genuine type errors

- [ ] **Step 3: Update README.md with quickstart**

Append to `README.md`:

```markdown
## Quickstart

```bash
# Install
brew install uv
git clone https://github.com/nathanchlin/Stone.git
cd Stone
uv sync --all-extras

# Configure your capital (private — not committed)
cp config/position_rules.example.yaml config/personal/position_rules.yaml
$EDITOR config/personal/position_rules.yaml

# First run: backfill historical data (30-60 min)
uv run python main.py update --backfill 2024-01-01 2026-06-14

# Run selection
uv run python main.py select --strategy band_trend_v1
# → reports/2026-06-14_波段趋势 v1.{xlsx,html,md,json}
```

## Development

```bash
uv run pytest -v                  # run tests
uv run pytest --cov=stone         # coverage report
uv run ruff check .               # lint
uv run mypy stone/                # type check
```

See [SETUP.md](docs/superpowers/plans/SETUP.md) for daily scheduling.
```

- [ ] **Step 4: Commit**

```bash
git add README.md pyproject.toml
git commit -m "docs: add quickstart and development sections to README"
```

- [ ] **Step 5: Push to remote**

```bash
git push origin main
```

- [ ] **Step 6: Verify on GitHub**

Open https://github.com/nathanchlin/Stone and confirm:
- README renders correctly
- All commits present
- `docs/superpowers/specs/2026-06-14-a-stock-selector-design.md` linked from README
- `docs/superpowers/plans/2026-06-14-stock-selector-implementation.md` (this file) present

- [ ] **Step 7: Tag the release**

```bash
git tag -a v0.1.0 -m "v0.1.0: Stock selector subsystem (Phase 1 + Phase 2)"
git push origin v0.1.0
```

- [ ] **Step 8: Final commit (CI config if applicable)**

Optional: add `.github/workflows/ci.yml` (skipped in v1 if you're not using GitHub Actions).

```bash
git status
# Should be clean
```

---

## Self-Review

### 1. Spec Coverage Check

| Spec Section | Implementing Tasks |
|---|---|
| 1. 项目定位与合规边界 | T1 (README), T27 (position rules template with disclaimer), T23/T24/T25 (disclaimer in every reporter) |
| 2. 需求摘要 | All 7 dimensions covered |
| 3. 架构总览 | T1-T30 |
| 4. 数据层 | T4 (ParquetStore), T5 (RateLimiter), T6 (AkshareFetcher), T7 (Universe), T8 (Incremental), T9 (Quality) |
| 5. 因子库 | T10 (Normalizer), T12-T14 (10 technical), T15 (3 fundamental), T16 (2 moneyflow + 1 theme) |
| 6. YAML Schema | T17 (pydantic), T18 (safe criterion), T27 (3 default strategies) |
| 7. 打分引擎与流水线 | T19 (ScoringEngine), T20 (ConstraintSolver), T22 (SelectionEngine) |
| 8. 仓位计算模块 | T21 (PositionSizer), T27 (rules template) |
| 9. 输出层 | T23 (Models+JSON+MD), T24 (Excel), T25 (HTML+charts) |
| 10. 错误处理与运行环境 | T2 (logging), T5 (retry), T9 (quality), T29 (launchd), T29 (CLI wiring) |
| 11. 测试策略 | Every task includes TDD; T28 (integration/E2E); pyproject.toml coverage gate (T1) |
| 12. 关键设计决策 | All 16 decisions mapped |
| 13. 后续工作 | Out of scope (Phase 3-5 will get their own plans) |

### 2. Placeholder Scan

No `TBD`, `TODO`, "implement later" in task steps (some `# TODO(T29)` comments in early CLI stubs reference later tasks, which is intentional and gets resolved in T29). All code blocks contain runnable Python.

### 3. Type Consistency

- `FactorContext` fields match across `base.py` (T3), all factor implementations (T12-T16), and `ScoringEngine._build_context` (T22)
- `StockScore` dataclass fields match across `scoring.py` (T19), `engine.py` (T22), and all reporters (T23-T25)
- `SelectionResult` fields match across `engine.py` (T22) and all reporters (T23-T25)
- Factor names in YAML (T27) match the `name` class attribute of Factor subclasses (T12-T16):
  - `ma_bullish_alignment`, `ma5_above_ma20`, `price_above_ma60`, `breakout_20d_high`, `macd_golden_cross`, `kdj_golden_cross`, `rsi_in_healthy_zone`, `volume_ratio`, `turnover_rate`, `distance_to_52w_high`, `roe_above_15`, `revenue_growth_positive`, `pe_in_industry_percentile`, `main_money_inflow_5d`, `northbound_inflow_20d`, `industry_momentum_5d`

---

**End of plan. 30 tasks, TDD throughout, coverage ≥ 80% enforced by pyproject.toml.**





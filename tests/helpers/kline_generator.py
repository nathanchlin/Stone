"""Synthetic K-line generators for factor testing."""

from datetime import date, timedelta

import numpy as np
import pandas as pd


def _make_df(
    dates: list[date],
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "amount": closes * volumes,
        }
    )


def generate_uptrend_kline(
    days: int = 250,
    start_price: float = 10.0,
    drift: float = 0.01,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = [start_price]
    for _ in range(days - 1):
        daily_return = drift + rng.normal(0, 0.015)
        closes.append(closes[-1] * (1 + daily_return))

    close_arr = np.array(closes, dtype=float)
    open_arr = close_arr * (1 - rng.uniform(0, 0.01, days))
    high_arr = np.maximum(open_arr, close_arr) * (1 + rng.uniform(0.005, 0.02, days))
    low_arr = np.minimum(open_arr, close_arr) * (1 - rng.uniform(0.005, 0.02, days))
    volume_arr = rng.integers(1_000_000, 10_000_000, days)
    dates = [date(2025, 1, 1) + timedelta(days=index) for index in range(days)]
    return _make_df(dates, open_arr, high_arr, low_arr, close_arr, volume_arr)


def generate_downtrend_kline(
    days: int = 250,
    start_price: float = 50.0,
    drift: float = -0.005,
    seed: int = 42,
) -> pd.DataFrame:
    return generate_uptrend_kline(days=days, start_price=start_price, drift=drift, seed=seed)


def generate_sideways_kline(
    days: int = 100,
    base_price: float = 10.0,
    volatility: float = 0.01,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close_arr = base_price * (1 + rng.normal(0, volatility, days))
    open_arr = close_arr * (1 - rng.uniform(0, 0.005, days))
    high_arr = np.maximum(open_arr, close_arr) * (1 + rng.uniform(0.002, 0.01, days))
    low_arr = np.minimum(open_arr, close_arr) * (1 - rng.uniform(0.002, 0.01, days))
    volume_arr = rng.integers(1_000_000, 5_000_000, days)
    dates = [date(2025, 1, 1) + timedelta(days=index) for index in range(days)]
    return _make_df(dates, open_arr, high_arr, low_arr, close_arr, volume_arr)


def generate_volatile_kline(
    days: int = 100,
    base_price: float = 10.0,
    volatility: float = 0.35,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, volatility, days)
    close_arr = np.empty(days, dtype=float)
    close_arr[0] = base_price
    for index in range(1, days):
        close_arr[index] = max(0.5, close_arr[index - 1] * (1 + returns[index]))
    open_arr = close_arr * (1 - rng.uniform(0, 0.02, days))
    high_arr = np.maximum(open_arr, close_arr) * (1 + rng.uniform(0.01, 0.05, days))
    low_arr = np.minimum(open_arr, close_arr) * (1 - rng.uniform(0.01, 0.05, days))
    volume_arr = rng.integers(1_000_000, 8_000_000, days)
    dates = [date(2025, 1, 1) + timedelta(days=index) for index in range(days)]
    return _make_df(dates, open_arr, high_arr, low_arr, close_arr, volume_arr)


def generate_breakout_kline(
    days: int = 250,
    breakout_at: int = 200,
    seed: int = 42,
) -> pd.DataFrame:
    """Sideways first, then a strong breakout uptrend."""
    rng = np.random.default_rng(seed)
    base = 10.0
    closes = list(base * (1 + rng.normal(0, 0.01, breakout_at)))
    last = closes[-1]
    for _ in range(days - breakout_at):
        last = last * (1 + 0.015 + rng.normal(0, 0.02))
        closes.append(last)

    close_arr = np.array(closes, dtype=float)
    open_arr = close_arr * (1 - rng.uniform(0, 0.01, days))
    high_arr = np.maximum(open_arr, close_arr) * (1 + rng.uniform(0.005, 0.02, days))
    low_arr = np.minimum(open_arr, close_arr) * (1 - rng.uniform(0.005, 0.02, days))
    volume_arr = rng.integers(1_000_000, 10_000_000, days)
    dates = [date(2025, 1, 1) + timedelta(days=index) for index in range(days)]
    return _make_df(dates, open_arr, high_arr, low_arr, close_arr, volume_arr)

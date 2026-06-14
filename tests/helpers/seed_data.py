"""Helpers to seed ParquetStore with synthetic test data."""

from datetime import date, timedelta

import pandas as pd

from stone.data.cache.parquet_store import ParquetStore
from tests.helpers.kline_generator import generate_uptrend_kline


def seed_universe(store: ParquetStore, codes: list[str], target_date: date) -> None:
    df = pd.DataFrame({"code": codes, "name": [f"S{index}" for index in range(len(codes))]})
    store.write("universe", target_date, df)


def seed_kline_for_codes(
    store: ParquetStore,
    codes: list[str],
    end_date: date,
    days: int = 250,
) -> None:
    for offset in range(days):
        current_date = end_date - timedelta(days=offset)
        frames: list[pd.DataFrame] = []
        for code in codes:
            kdf = generate_uptrend_kline(days=1, start_price=10.0 + hash(code) % 100)
            kdf["code"] = code
            kdf["date"] = [current_date]
            frames.append(kdf)
        store.write_kline(current_date, pd.concat(frames, ignore_index=True))

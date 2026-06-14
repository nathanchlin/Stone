from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from stone.data.cache.parquet_store import ParquetStore
from stone.data.incremental import IncrementalUpdater, UpdateReport


def _mock_fetcher():
    fetcher = MagicMock()
    fetcher.get_trade_calendar.return_value = [date(2026, 6, 13), date(2026, 6, 14)]
    fetcher.list_universe.return_value = pd.DataFrame(
        {
            "code": ["600519", "000001"],
            "name": ["贵州茅台", "平安银行"],
        }
    )
    fetcher.get_daily_kline.return_value = pd.DataFrame(
        {
            "code": ["600519"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [100],
            "amount": [1000.0],
        }
    )
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
    store.write_kline(
        date(2026, 6, 13),
        pd.DataFrame(
            {
                "code": ["600519"],
                "open": [10.0],
                "high": [11.0],
                "low": [9.0],
                "close": [10.5],
                "volume": [100],
                "amount": [1000.0],
            }
        ),
    )

    fetcher = _mock_fetcher()
    updater = IncrementalUpdater(store=store, fetcher=fetcher)

    report = updater.update_daily(date(2026, 6, 14))

    assert date(2026, 6, 13) in report.skipped_dates
    assert date(2026, 6, 14) in report.success_dates

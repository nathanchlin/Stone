from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from stone.data.fetchers.akshare_fetcher import AkshareFetcher
from stone.errors import DataError


def _mock_kline_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "日期": ["2026-06-12", "2026-06-13"],
            "开盘": [10.0, 10.5],
            "收盘": [10.5, 11.0],
            "最高": [11.0, 11.5],
            "最低": [9.5, 10.0],
            "成交量": [1000, 1200],
            "成交额": [10500.0, 13200.0],
        }
    )


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
    fake = pd.DataFrame(
        {
            "代码": ["600519", "000001"],
            "名称": ["贵州茅台", "平安银行"],
            "最新价": [1800.0, 12.0],
        }
    )
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_info_a_code_name.return_value = fake
        df = fetcher.list_universe(date(2026, 6, 14))

    assert "code" in df.columns
    assert "name" in df.columns
    assert len(df) == 2

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
            "股票代码": ["000001", "000001"],
            "开盘": [10.0, 10.5],
            "收盘": [10.5, 11.0],
            "最高": [11.0, 11.5],
            "最低": [9.5, 10.0],
            "成交量": [1000, 1200],
            "成交额": [10500.0, 13200.0],
            "换手率": [0.6, 0.7],
        }
    )


def test_get_daily_kline_returns_canonical_columns():
    fetcher = AkshareFetcher()
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_zh_a_hist.return_value = _mock_kline_df()
        df = fetcher.get_daily_kline("000001", date(2026, 6, 12), date(2026, 6, 13))

    assert list(df.columns) == [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover_rate",
    ]
    assert len(df) == 2
    assert df.iloc[0]["close"] == 10.5
    assert df.iloc[0]["turnover_rate"] == 0.6


def test_get_daily_kline_raises_on_empty_result():
    fetcher = AkshareFetcher(snapshot_dir="/tmp/stone_test_empty_kline")
    cached = fetcher._read_snapshot("kline", "000001")
    if not cached.empty:
        fetcher._snapshot_path("kline", "000001").unlink(missing_ok=True)
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
            "成交额": [8e8, 5e8],
        }
    )
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_zh_a_spot.return_value = fake
        df = fetcher.list_universe(date(2026, 6, 14))

    assert "code" in df.columns
    assert "name" in df.columns
    assert "close" in df.columns
    assert "avg_amount" in df.columns
    assert len(df) == 2


def test_list_universe_uses_cached_snapshot_when_live_fetch_fails(tmp_path):
    fetcher = AkshareFetcher(snapshot_dir=tmp_path)
    cached = pd.DataFrame({"code": ["000001"], "name": ["平安银行"], "close": [12.0], "avg_amount": [5e8]})
    fetcher._write_snapshot("universe", "latest", cached)

    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_zh_a_spot.side_effect = ConnectionError("boom")
        df = fetcher.list_universe(date(2026, 6, 14))

    assert len(df) == 1
    assert df.iloc[0]["code"] == "000001"


def test_get_basic_financial_normalizes_columns():
    fetcher = AkshareFetcher()
    fake = pd.DataFrame(
        {
            "日期": ["2026-03-31", "2026-06-30"],
            "净资产收益率(%)": [15.0, 16.0],
            "主营业务收入增长率(%)": [8.0, 9.5],
        }
    )
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_financial_analysis_indicator.return_value = fake
        df = fetcher.get_basic_financial("000001")

    assert list(df.columns) == ["date", "roe", "revenue_yoy"]
    assert df.iloc[-1]["roe"] == 16.0


def test_get_money_flow_returns_empty_on_connection_error():
    fetcher = AkshareFetcher()
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_individual_fund_flow.side_effect = ConnectionError("boom")
        df = fetcher.get_money_flow("000001")

    assert list(df.columns) == ["main_net", "north_net"]
    assert df.empty


def test_get_daily_kline_falls_back_to_cached_snapshot(tmp_path):
    fetcher = AkshareFetcher(snapshot_dir=tmp_path)
    cached = pd.DataFrame(
        {
            "date": [date(2026, 6, 12), date(2026, 6, 13)],
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.5, 10.0],
            "close": [10.5, 11.0],
            "volume": [1000, 1200],
            "amount": [10500.0, 13200.0],
            "turnover_rate": [0.6, 0.7],
        }
    )
    fetcher._write_snapshot("kline", "000001", cached)

    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_zh_a_hist.side_effect = ConnectionError("boom")
        df = fetcher.get_daily_kline("000001", date(2026, 6, 12), date(2026, 6, 13))

    assert len(df) == 2
    assert df.iloc[-1]["close"] == 11.0

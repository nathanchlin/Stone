from datetime import date, timedelta
from unittest.mock import MagicMock, patch

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


def _mock_netease_kline_df() -> pd.DataFrame:
    """netease stock_zh_a_daily returns English columns; turnover is decimal (0.006 = 0.6%)."""
    return pd.DataFrame(
        {
            "date": ["2026-06-12", "2026-06-13"],
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.5, 10.0],
            "close": [10.5, 11.0],
            "volume": [1000, 1200],
            "amount": [10500.0, 13200.0],
            "outstanding_share": [1e8, 1e8],
            "turnover": [0.006, 0.007],
        }
    )


def _mock_sina_hq_response(
    name: str = "华安证券",
    open_p: float = 8.00,
    prev_close: float = 7.96,
    current: float = 8.39,
    high: float = 8.43,
    low: float = 7.89,
    volume: float = 349754480,
    amount: float = 2858960517.0,
    quote_date: str = None,
) -> str:
    """Format that matches real sina hq_sinajs response."""
    from datetime import date as _date

    quote_date = quote_date or _date.today().isoformat()
    parts = [name, str(open_p), str(prev_close), str(current), str(high), str(low)]
    parts += [str(current), f"{current + 0.01:.2f}", str(volume), str(amount)]
    # 10 bid/ask levels (fields 10-29): each pair is volume + price
    for i in range(10):
        parts += [str(100 + i), f"{current - 0.01 * (i + 1):.2f}"]
    parts += [quote_date, "15:00:01", "00"]
    payload = ",".join(parts)
    return f'var hq_str_sh600909="{payload}";'


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


def test_get_money_flow_returns_empty_when_all_sources_fail():
    """Both akshare wrapper AND push2 fallback fail → return empty."""
    fetcher = AkshareFetcher()
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak, patch(
        "requests.get"
    ) as mock_get:
        mock_ak.stock_individual_fund_flow.side_effect = ConnectionError("boom")
        mock_get.side_effect = ConnectionError("push2 also failed")
        df = fetcher.get_money_flow("000001")

    assert list(df.columns) == ["main_net", "north_net"]
    assert df.empty


def test_get_money_flow_falls_back_to_push2_when_akshare_fails():
    """When akshare raises ConnectionError, push2 direct API is tried."""
    fetcher = AkshareFetcher()
    fake_klines = [
        "2026-06-14,1000000.0,-50000.0,-950000.0,-300000.0,1300000.0,1.0,-0.05,-0.95",
        "2026-06-15,2000000.0,100000.0,-2100000.0,-700000.0,2700000.0,2.0,0.1,-2.1",
    ]
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"data": {"klines": fake_klines}}
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak, patch(
        "requests.get", return_value=fake_response
    ) as mock_get:
        mock_ak.stock_individual_fund_flow.side_effect = ConnectionError("eastmoney blocked")
        df = fetcher.get_money_flow("300308", days=5)

    assert len(df) == 2
    assert "main_net" in df.columns
    assert "north_net" in df.columns
    assert df.iloc[-1]["main_net"] == 2000000.0
    # verify push2 was called with correct secid (sz prefix for 300308)
    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs["params"]["secid"] == "0.300308"


def test_get_money_flow_falls_back_to_push2_for_sh_stock():
    fetcher = AkshareFetcher()
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"data": {"klines": ["2026-06-15,500000.0,0.0,0.0,0.0,0.0,0,0,0"]}}
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak, patch(
        "requests.get", return_value=fake_response
    ) as mock_get:
        mock_ak.stock_individual_fund_flow.side_effect = ConnectionError("blocked")
        fetcher.get_money_flow("601288", days=1)

    # secid should use 1.sh prefix for SH stocks
    assert mock_get.call_args.kwargs["params"]["secid"] == "1.601288"


def test_get_money_flow_push2_handles_empty_response():
    """push2 returns no data → empty DataFrame."""
    fetcher = AkshareFetcher()
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"data": None}
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak, patch(
        "requests.get", return_value=fake_response
    ):
        mock_ak.stock_individual_fund_flow.side_effect = ConnectionError("blocked")
        df = fetcher.get_money_flow("000001", days=5)

    assert df.empty


def test_get_money_flow_falls_back_to_snapshot_when_daykline_blocked():
    """When akshare AND push2 daykline both fail, use ulist snapshot (today only)."""
    fetcher = AkshareFetcher()
    # daykline returns empty (blocked), snapshot returns valid data
    daykline_resp = MagicMock()
    daykline_resp.raise_for_status.return_value = None
    daykline_resp.json.return_value = {"data": {"klines": []}}
    snapshot_resp = MagicMock()
    snapshot_resp.raise_for_status.return_value = None
    snapshot_resp.json.return_value = {
        "data": {
            "diff": [
                {
                    "f12": "300308",
                    "f55": 16e9,
                    "f62": 3590207488.0,
                    "f66": 4898012416.0,
                    "f72": -1307804928.0,
                    "f78": -3589654016.0,
                    "f84": -553350.0,
                }
            ]
        }
    }
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak, patch(
        "requests.get", side_effect=[daykline_resp, snapshot_resp]
    ):
        mock_ak.stock_individual_fund_flow.side_effect = ConnectionError("blocked")
        df = fetcher.get_money_flow("300308", days=5)

    assert len(df) == 1  # snapshot is today only
    assert "main_net" in df.columns
    assert df.iloc[0]["main_net"] == 3590207488.0
    assert df.iloc[0]["super_large_net"] == 4898012416.0
    assert df.iloc[0]["large_net"] == -1307804928.0


def test_get_money_flow_snapshot_returns_empty_on_failure():
    """When all 3 sources fail → empty DataFrame."""
    fetcher = AkshareFetcher()
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak, patch(
        "requests.get", side_effect=ConnectionError("all blocked")
    ):
        mock_ak.stock_individual_fund_flow.side_effect = ConnectionError("blocked")
        df = fetcher.get_money_flow("000001", days=5)

    assert list(df.columns) == ["main_net", "north_net"]
    assert df.empty


# ---------------------------------------------------------------------------
# Bug C5 fix: sina realtime merge for today's data
# ---------------------------------------------------------------------------

def test_fetch_kline_realtime_sina_parses_hq_response():
    """Direct call to sina realtime method parses today's OHLCV correctly."""
    fetcher = AkshareFetcher()
    fake_resp = MagicMock()
    fake_resp.raise_for_status.return_value = None
    fake_resp.text = _mock_sina_hq_response(current=8.39, high=8.43, low=7.89, volume=349754480)
    with patch("requests.get", return_value=fake_resp):
        df = fetcher._fetch_kline_realtime_sina("600909")

    assert len(df) == 1
    row = df.iloc[0]
    assert row["close"] == 8.39
    assert row["open"] == 8.00
    assert row["high"] == 8.43
    assert row["low"] == 7.89
    assert row["volume"] == 349754480
    assert row["date"] == date.today()


def test_fetch_kline_realtime_sina_returns_empty_on_request_failure():
    fetcher = AkshareFetcher()
    with patch("requests.get", side_effect=ConnectionError("sina blocked")):
        df = fetcher._fetch_kline_realtime_sina("600909")
    assert df.empty


def test_fetch_kline_realtime_sina_returns_empty_on_parse_failure():
    """Malformed response → empty DataFrame, no exception."""
    fetcher = AkshareFetcher()
    fake_resp = MagicMock()
    fake_resp.raise_for_status.return_value = None
    fake_resp.text = 'garbage without proper format'
    with patch("requests.get", return_value=fake_resp):
        df = fetcher._fetch_kline_realtime_sina("600909")
    assert df.empty


def test_get_daily_kline_merges_sina_realtime_when_today_missing():
    """When historical source returns up to yesterday and end=today, sina is queried."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    fetcher = AkshareFetcher(snapshot_dir=MagicMock())

    # Historical cache has through yesterday only (simulates T+1 delay)
    cached = pd.DataFrame(
        {
            "date": [yesterday],
            "open": [8.00],
            "high": [8.10],
            "low": [7.90],
            "close": [8.05],
            "volume": [1000],
            "amount": [8050.0],
        }
    )
    fetcher._read_snapshot = lambda kind, key: cached.copy() if kind == "kline" else pd.DataFrame()
    fetcher._write_snapshot = lambda kind, key, df: None
    fetcher._hist_limiter = MagicMock()
    fetcher._require_client = MagicMock(return_value=MagicMock())
    # netease returns nothing new (already have yesterday)
    fetcher._fetch_kline_with_fallback = lambda *args: (pd.DataFrame(), "none")
    # sina returns today
    fetcher._fetch_kline_realtime_sina = lambda code: pd.DataFrame(
        [{"date": today, "open": 8.20, "high": 8.43, "low": 8.10, "close": 8.39, "volume": 349754480, "amount": 2.86e9}]
    )

    df = fetcher.get_daily_kline("600909", yesterday, today, adjust="qfq")

    assert today in df["date"].tolist()
    assert df[df["date"] == today].iloc[0]["close"] == 8.39


def test_get_daily_kline_skips_sina_when_end_is_in_past():
    """end < today → sina not called, cache used directly."""
    today = date.today()
    past_date = today - timedelta(days=10)
    fetcher = AkshareFetcher(snapshot_dir=MagicMock())

    cached = pd.DataFrame(
        {
            "date": [past_date],
            "open": [8.00], "high": [8.10], "low": [7.90], "close": [8.05],
            "volume": [1000], "amount": [8050.0],
        }
    )
    fetcher._read_snapshot = lambda kind, key: cached.copy() if kind == "kline" else pd.DataFrame()
    fetcher._write_snapshot = lambda kind, key, df: None

    # If sina is called, this would raise (MagicMock __call__)
    fetcher._fetch_kline_realtime_sina = MagicMock(side_effect=AssertionError("sina should not be called"))

    df = fetcher.get_daily_kline("600909", past_date, past_date, adjust="qfq")
    assert len(df) == 1
    assert df.iloc[0]["date"] == past_date
    fetcher._fetch_kline_realtime_sina.assert_not_called()


def test_get_daily_kline_overwrites_historical_today_with_sina_when_end_is_today():
    """When end >= today, sina always wins over historical eastmoney/netease.

    Bug C5 v2: the previous design skipped sina when historical already contained
    today's row. That assumed historical's "today" was fresh, but eastmoney can
    return a stale intraday snapshot. For monitoring, sina is the source of truth.
    """
    today = date.today()
    fetcher = AkshareFetcher(snapshot_dir=MagicMock())

    fetcher._read_snapshot = lambda kind, key: pd.DataFrame()
    fetcher._write_snapshot = lambda kind, key, df: None
    fetcher._hist_limiter = MagicMock()
    fetcher._require_client = MagicMock(return_value=MagicMock())
    # Historical returns today with a different close
    fetcher._fetch_kline_with_fallback = lambda *args: (
        pd.DataFrame(
            [{"date": today, "open": 8.0, "high": 8.4, "low": 7.9, "close": 8.3, "volume": 1, "amount": 8.3}]
        ),
        "eastmoney",
    )
    fetcher._fetch_kline_realtime_sina = lambda code: pd.DataFrame(
        [{"date": today, "open": 8.20, "high": 9.05, "low": 8.26, "close": 8.77, "volume": 258276309, "amount": 2.26e9}]
    )

    df = fetcher.get_daily_kline("600909", today, today, adjust="qfq")
    assert df.iloc[0]["close"] == 8.77  # sina wins, not historical 8.3


def test_get_daily_kline_overwrites_stale_today_with_sina_realtime():
    """Bug C5 v2: cached intraday snapshot of today must be overwritten by fresh sina quote.

    Reproduces the real-world failure: an earlier run wrote today's intraday price
    into the snapshot, so later runs saw `merged.date.max() == today` and skipped
    sina — serving stale intraday prices as if they were fresh.
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    fetcher = AkshareFetcher(snapshot_dir=MagicMock())

    # Cache contains a stale intraday snapshot of today (e.g. written at 10:01)
    cached = pd.DataFrame(
        {
            "date": [yesterday, today],
            "open": [8.00, 8.20],
            "high": [8.10, 9.05],
            "low": [7.90, 8.26],
            "close": [8.05, 8.92],  # stale intraday snapshot
            "volume": [1000, 5000],
            "amount": [8050.0, 45000.0],
        }
    )
    fetcher._read_snapshot = lambda kind, key: cached.copy() if kind == "kline" else pd.DataFrame()
    fetcher._write_snapshot = lambda kind, key, df: None
    fetcher._hist_limiter = MagicMock()
    fetcher._require_client = MagicMock(return_value=MagicMock())
    # Historical returns nothing new (netease T+1, eastmoney may also be empty)
    fetcher._fetch_kline_with_fallback = lambda *args: (pd.DataFrame(), "none")
    # Sina returns fresh today (14:31 price)
    fetcher._fetch_kline_realtime_sina = lambda code: pd.DataFrame(
        [{"date": today, "open": 8.20, "high": 9.05, "low": 8.26, "close": 8.77, "volume": 258276309, "amount": 2.26e9}]
    )

    df = fetcher.get_daily_kline("600909", yesterday, today, adjust="qfq")

    today_row = df[df["date"] == today].iloc[0]
    assert today_row["close"] == 8.77  # fresh sina price, not stale 8.92


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


def test_get_daily_kline_falls_back_to_netease_when_eastmoney_fails(tmp_path):
    """When eastmoney raises ConnectionError, netease is tried and its data is used."""
    fetcher = AkshareFetcher(snapshot_dir=tmp_path)
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_zh_a_hist.side_effect = ConnectionError("eastmoney blocked")
        mock_ak.stock_zh_a_daily.return_value = _mock_netease_kline_df()
        df = fetcher.get_daily_kline("000725", date(2026, 6, 12), date(2026, 6, 13))

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
    # netease decimal 0.006 → percent 0.6 (matches eastmoney unit)
    assert df.iloc[0]["turnover_rate"] == pytest.approx(0.6)
    assert df.iloc[1]["turnover_rate"] == pytest.approx(0.7)
    # verify netease was called with sh/sz prefix for SZ stock
    mock_ak.stock_zh_a_daily.assert_called_once()
    assert mock_ak.stock_zh_a_daily.call_args.kwargs["symbol"] == "sz000725"


def test_get_daily_kline_netease_uses_sh_prefix_for_shanghai_codes(tmp_path):
    fetcher = AkshareFetcher(snapshot_dir=tmp_path)
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_zh_a_hist.side_effect = ConnectionError("eastmoney blocked")
        mock_ak.stock_zh_a_daily.return_value = _mock_netease_kline_df()
        fetcher.get_daily_kline("601288", date(2026, 6, 12), date(2026, 6, 13))

    assert mock_ak.stock_zh_a_daily.call_args.kwargs["symbol"] == "sh601288"


def test_get_daily_kline_prefers_eastmoney_when_available(tmp_path):
    """When eastmoney succeeds, netease should not be called."""
    fetcher = AkshareFetcher(snapshot_dir=tmp_path)
    with patch("stone.data.fetchers.akshare_fetcher.ak") as mock_ak:
        mock_ak.stock_zh_a_hist.return_value = _mock_kline_df()
        df = fetcher.get_daily_kline("000001", date(2026, 6, 12), date(2026, 6, 13))

    mock_ak.stock_zh_a_daily.assert_not_called()
    assert df.iloc[-1]["close"] == 11.0

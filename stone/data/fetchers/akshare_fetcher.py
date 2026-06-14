"""Akshare-backed implementation of the data fetcher protocol."""

from datetime import date

import pandas as pd

from stone.constants import AKSHARE_MAX_RATE
from stone.data.fetchers._rate_limiter import RateLimiter
from stone.data.fetchers._retry import with_retry
from stone.errors import DataError

try:
    import akshare as ak
except ImportError:  # pragma: no cover - handled at runtime in environments without akshare
    ak = None

_KLINE_RENAME = {
    "日期": "date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
}


class AkshareFetcher:
    """Market data fetcher using akshare's public endpoints."""

    def __init__(self, rate_limiter: RateLimiter | None = None):
        self._limiter = rate_limiter or RateLimiter(max_rate=AKSHARE_MAX_RATE)

    def _require_client(self):
        if ak is None:
            raise DataError("akshare is not installed")
        return ak

    @with_retry()
    def list_universe(self, target_date: date) -> pd.DataFrame:
        self._limiter.acquire()
        client = self._require_client()
        df = client.stock_info_a_code_name()
        if df.empty:
            raise DataError(f"Empty universe for {target_date}")
        renamed = df.rename(columns={"代码": "code", "名称": "name"})
        return renamed[["code", "name"]]

    @with_retry()
    def get_daily_kline(
        self, code: str, start: date, end: date, adjust: str = "qfq"
    ) -> pd.DataFrame:
        self._limiter.acquire()
        client = self._require_client()
        df = client.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust=adjust,
        )
        if df.empty:
            raise DataError(f"Empty kline for {code} from {start} to {end}")
        renamed = df.rename(columns=_KLINE_RENAME)
        canonical = renamed[["date", "open", "high", "low", "close", "volume", "amount"]].copy()
        canonical["date"] = pd.to_datetime(canonical["date"]).dt.date
        return canonical

    @with_retry()
    def get_basic_financial(self, code: str) -> pd.DataFrame:
        self._limiter.acquire()
        client = self._require_client()
        return client.stock_financial_analysis_indicator(symbol=code.zfill(6))

    @with_retry()
    def get_money_flow(self, code: str, days: int = 30) -> pd.DataFrame:
        self._limiter.acquire()
        client = self._require_client()
        market = "sh" if code.startswith(("6", "9")) else "sz"
        return client.stock_individual_fund_flow(stock=code, market=market).tail(days)

    @with_retry()
    def get_industry_mapping(self) -> dict[str, str]:
        self._limiter.acquire()
        client = self._require_client()
        boards = client.stock_board_industry_name_em()
        mapping: dict[str, str] = {}
        for board_name in boards.get("板块名称", []):
            try:
                constituents = client.stock_board_industry_cons_em(symbol=board_name)
            except Exception:
                continue
            for _, row in constituents.iterrows():
                mapping[str(row["代码"])] = str(board_name)
        return mapping

    @with_retry()
    def get_trade_calendar(self, start: date, end: date) -> list[date]:
        self._limiter.acquire()
        client = self._require_client()
        df = client.tool_trade_date_hist_sina()
        dates = pd.to_datetime(df["trade_date"]).dt.date.tolist()
        return [target for target in dates if start <= target <= end]

"""Fetcher protocol used by the selector and update pipelines."""

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class DataFetcher(Protocol):
    """Common interface for market data backends."""

    def list_universe(self, target_date: date) -> pd.DataFrame:
        """Return the stock universe for the target date."""

    def get_daily_kline(
        self, code: str, start: date, end: date, adjust: str = "qfq"
    ) -> pd.DataFrame:
        """Return daily OHLCV data in canonical columns."""

    def get_basic_financial(self, code: str) -> pd.DataFrame:
        """Return recent basic financial indicators for a stock."""

    def get_money_flow(self, code: str, days: int = 30) -> pd.DataFrame:
        """Return recent money flow data for a stock."""

    def get_industry_mapping(self) -> dict[str, str]:
        """Return a code-to-industry mapping."""

    def get_trade_calendar(self, start: date, end: date) -> list[date]:
        """Return trading dates between start and end, inclusive."""

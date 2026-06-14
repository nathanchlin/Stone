"""Data quality checks for cached kline data."""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from stone.errors import DataError


@dataclass
class QualityReport:
    """Result of a dataset quality check."""

    target_date: date | None = None
    ok: bool = True
    errors: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)


def check_kline(df: pd.DataFrame, target_date: date | None = None) -> QualityReport:
    """Run basic consistency checks on OHLCV daily data."""
    report = QualityReport(target_date=target_date)

    if df.empty:
        report.add("empty dataframe")
        return report

    if {"low", "high"}.issubset(df.columns):
        bad = df[df["low"] > df["high"]]
        if not bad.empty:
            report.add(f"low > high in {len(bad)} rows")

    if {"low", "open", "close"}.issubset(df.columns):
        bad = df[df["low"] > df[["open", "close"]].min(axis=1)]
        if not bad.empty:
            report.add(f"low > min(open, close) in {len(bad)} rows")

    for column in ["open", "high", "low", "close"]:
        if column in df.columns and df[column].isna().any():
            report.add(f"{column} has NaN values")

    if "volume" in df.columns and (df["volume"] < 0).any():
        report.add("volume < 0 in some rows")

    return report


def assert_kline_quality(df: pd.DataFrame, target_date: date) -> None:
    """Raise when kline data fails quality checks."""
    report = check_kline(df, target_date)
    if not report.ok:
        raise DataError(f"Quality check failed for {target_date}: {report.errors}")

from datetime import date

import pandas as pd
import pytest

from stone.data.quality import QualityReport, assert_kline_quality, check_kline
from stone.errors import DataError


def _good_df():
    return pd.DataFrame(
        {
            "code": ["600519"] * 2,
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.5, 10.0],
            "close": [10.5, 11.0],
            "volume": [1000, 1200],
            "amount": [10500.0, 13200.0],
        }
    )


def test_good_dataframe_passes():
    report = check_kline(_good_df(), date(2026, 6, 14))
    assert isinstance(report, QualityReport)
    assert report.ok
    assert report.errors == []


def test_low_greater_than_high_fails():
    df = _good_df().copy()
    df.loc[0, "low"] = 12.0
    report = check_kline(df, date(2026, 6, 14))
    assert not report.ok
    assert any("low > high" in error for error in report.errors)


def test_negative_volume_fails():
    df = _good_df().copy()
    df.loc[0, "volume"] = -1
    report = check_kline(df, date(2026, 6, 14))
    assert not report.ok
    assert any("volume < 0" in error for error in report.errors)


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

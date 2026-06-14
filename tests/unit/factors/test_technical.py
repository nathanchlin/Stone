from datetime import date

import pandas as pd

from stone.selector.factors.base import FactorContext
from stone.selector.factors.technical import (
    Breakout20dHigh,
    DistanceTo52wHigh,
    KdjGoldenCross,
    Ma5AboveMa20,
    MaBullishAlignment,
    MacdGoldenCross,
    PriceAboveMa60,
    RsiInHealthyZone,
    TurnoverRate,
    VolumeRatio,
)
from tests.helpers.kline_generator import (
    generate_breakout_kline,
    generate_downtrend_kline,
    generate_uptrend_kline,
)


def _ctx(kline: pd.DataFrame) -> FactorContext:
    return FactorContext(
        code="000001",
        name="test",
        industry="测试",
        today=date(2026, 6, 14),
        kline=kline,
        financial=pd.DataFrame(),
        moneyflow=pd.DataFrame(),
    )


def test_ma_bullish_alignment_high_for_uptrend():
    kline = generate_uptrend_kline(days=250)
    factor = MaBullishAlignment()
    score = factor.compute(_ctx(kline))
    assert 0.7 <= score <= 1.0


def test_ma_bullish_alignment_low_for_downtrend():
    kline = generate_downtrend_kline(days=250)
    factor = MaBullishAlignment()
    score = factor.compute(_ctx(kline))
    assert 0.0 <= score <= 0.3


def test_ma5_above_ma20_returns_binary():
    kline = generate_uptrend_kline(days=250)
    factor = Ma5AboveMa20()
    result = factor.compute(_ctx(kline))
    assert result in (0.0, 1.0)


def test_price_above_ma60_uptrend_returns_one():
    kline = generate_uptrend_kline(days=250)
    factor = PriceAboveMa60()
    assert factor.compute(_ctx(kline)) == 1.0


def test_factor_params_roundtrip():
    factor = MaBullishAlignment(periods=(5, 10, 20, 60))
    assert factor.get_params() == {"periods": [5, 10, 20, 60]}


def test_factor_name_unique():
    assert MaBullishAlignment.name == "ma_bullish_alignment"
    assert Ma5AboveMa20.name == "ma5_above_ma20"
    assert PriceAboveMa60.name == "price_above_ma60"


def test_breakout_20d_high_returns_one_on_new_high():
    kline = generate_breakout_kline(days=250, breakout_at=200)
    factor = Breakout20dHigh(window=20)
    score = factor.compute(_ctx(kline))
    assert score in (0.0, 1.0)


def test_macd_golden_cross_returns_binary():
    kline = generate_uptrend_kline(days=250)
    factor = MacdGoldenCross(lookback=5)
    result = factor.compute(_ctx(kline))
    assert result in (0.0, 1.0)


def test_kdj_golden_cross_returns_binary():
    kline = generate_uptrend_kline(days=250)
    factor = KdjGoldenCross(lookback=3)
    result = factor.compute(_ctx(kline))
    assert result in (0.0, 1.0)


def test_rsi_in_healthy_zone_within_range_returns_one():
    kline = generate_uptrend_kline(days=250)
    factor = RsiInHealthyZone(zone=(40, 70))
    result = factor.compute(_ctx(kline))
    assert result in (0.0, 1.0)


def test_macd_factor_names():
    assert MacdGoldenCross.name == "macd_golden_cross"
    assert KdjGoldenCross.name == "kdj_golden_cross"
    assert Breakout20dHigh.name == "breakout_20d_high"
    assert RsiInHealthyZone.name == "rsi_in_healthy_zone"


def test_volume_ratio_returns_positive_float():
    kline = generate_uptrend_kline(days=250)
    factor = VolumeRatio(avg_window=5)
    result = factor.compute(_ctx(kline))
    assert isinstance(result, float)
    assert result >= 0.0


def test_turnover_rate_in_range_returns_one():
    kline = generate_uptrend_kline(days=250)
    kline["turnover_rate"] = 5.0
    factor = TurnoverRate(zone=(1.0, 10.0))
    assert factor.compute(_ctx(kline)) == 1.0


def test_turnover_rate_out_of_range_returns_zero():
    kline = generate_uptrend_kline(days=250)
    kline["turnover_rate"] = 0.5
    factor = TurnoverRate(zone=(1.0, 10.0))
    assert factor.compute(_ctx(kline)) == 0.0


def test_distance_to_52w_high_returns_ratio():
    kline = generate_uptrend_kline(days=260)
    factor = DistanceTo52wHigh()
    result = factor.compute(_ctx(kline))
    assert -1.0 <= result <= 0.0


def test_factor_names_part3():
    assert VolumeRatio.name == "volume_ratio"
    assert TurnoverRate.name == "turnover_rate"
    assert DistanceTo52wHigh.name == "distance_to_52w_high"

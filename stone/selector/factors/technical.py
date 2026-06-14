"""Technical factors."""

import pandas as pd

from stone.constants import FactorCategory
from stone.errors import FactorError
from stone.selector.factors import register_factor
from stone.selector.factors.base import Factor, FactorContext


def _sma(series, window: int):
    if len(series) < window:
        raise FactorError(f"insufficient data: need {window} rows, got {len(series)}")
    return series.rolling(window=window, min_periods=window).mean().iloc[-1]


@register_factor
class MaBullishAlignment(Factor):
    """Fraction of ordered moving averages satisfied."""

    name = "ma_bullish_alignment"
    category = FactorCategory.TECHNICAL
    higher_is_better = True

    def __init__(self, periods: tuple[int, ...] = (5, 10, 20, 60)):
        self.periods = tuple(periods)

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        mas = [_sma(close, period) for period in self.periods]
        total = len(mas) - 1
        aligned = sum(1 for index in range(total) if mas[index] > mas[index + 1])
        return aligned / total if total > 0 else 0.0

    def get_params(self) -> dict[str, object]:
        return {"periods": list(self.periods)}


@register_factor
class Ma5AboveMa20(Factor):
    """Binary factor: 1 when MA5 is above MA20."""

    name = "ma5_above_ma20"
    category = FactorCategory.TECHNICAL
    higher_is_better = True

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        return 1.0 if _sma(close, 5) > _sma(close, 20) else 0.0

    def get_params(self) -> dict[str, object]:
        return {}


@register_factor
class PriceAboveMa60(Factor):
    """Binary factor: 1 when latest close is above MA60."""

    name = "price_above_ma60"
    category = FactorCategory.TECHNICAL
    higher_is_better = True

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        return 1.0 if close.iloc[-1] > _sma(close, 60) else 0.0

    def get_params(self) -> dict[str, object]:
        return {}


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


@register_factor
class Breakout20dHigh(Factor):
    """Binary factor: latest close breaks the recent N-day high."""

    name = "breakout_20d_high"
    category = FactorCategory.TECHNICAL
    higher_is_better = True

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        if len(close) < self.window:
            raise FactorError(f"insufficient data: need {self.window} rows")
        recent = close.tail(self.window)
        return 1.0 if close.iloc[-1] >= recent.max() * 0.999 else 0.0

    def get_params(self) -> dict[str, object]:
        return {"window": self.window}


@register_factor
class MacdGoldenCross(Factor):
    """Binary factor: MACD crosses above signal and stays above zero."""

    name = "macd_golden_cross"
    category = FactorCategory.TECHNICAL
    higher_is_better = True

    def __init__(self, lookback: int = 5, fast: int = 12, slow: int = 26, signal: int = 9):
        self.lookback = lookback
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        if len(close) < self.slow + self.signal:
            raise FactorError("insufficient data for MACD")
        macd_line = _ema(close, self.fast) - _ema(close, self.slow)
        signal_line = _ema(macd_line, self.signal)
        diff = macd_line - signal_line
        recent_diff = diff.tail(self.lookback + 1)
        crossed = (recent_diff.iloc[:-1] <= 0).any() and recent_diff.iloc[-1] > 0
        above_zero = macd_line.iloc[-1] > 0
        return 1.0 if crossed and above_zero else 0.0

    def get_params(self) -> dict[str, object]:
        return {
            "lookback": self.lookback,
            "fast": self.fast,
            "slow": self.slow,
            "signal": self.signal,
        }


@register_factor
class KdjGoldenCross(Factor):
    """Binary factor: K crosses above D in the recent lookback window."""

    name = "kdj_golden_cross"
    category = FactorCategory.TECHNICAL
    higher_is_better = True

    def __init__(self, lookback: int = 3, window: int = 9):
        self.lookback = lookback
        self.window = window

    def compute(self, ctx: FactorContext) -> float:
        high = ctx.kline["high"]
        low = ctx.kline["low"]
        close = ctx.kline["close"]
        if len(close) < self.window:
            raise FactorError("insufficient data for KDJ")
        hh = high.rolling(self.window).max()
        ll = low.rolling(self.window).min()
        rsv = (close - ll) / (hh - ll).replace(0, float("nan")) * 100
        k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
        d = k.ewm(alpha=1 / 3, adjust=False).mean()
        diff = k - d
        recent = diff.tail(self.lookback + 1)
        crossed = (recent.iloc[:-1] <= 0).any() and recent.iloc[-1] > 0
        return 1.0 if crossed else 0.0

    def get_params(self) -> dict[str, object]:
        return {"lookback": self.lookback, "window": self.window}


@register_factor
class RsiInHealthyZone(Factor):
    """Binary factor: RSI stays inside a configured healthy zone."""

    name = "rsi_in_healthy_zone"
    category = FactorCategory.TECHNICAL
    higher_is_better = True

    def __init__(self, zone: tuple[float, float] = (40.0, 70.0), window: int = 14):
        self.low, self.high = zone
        self.window = window

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        if len(close) < self.window + 1:
            raise FactorError("insufficient data for RSI")
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(self.window).mean()
        loss = -delta.clip(upper=0).rolling(self.window).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi = 100 - 100 / (1 + rs)
        last = rsi.iloc[-1]
        if pd.isna(last):
            return 0.0
        return 1.0 if self.low <= last <= self.high else 0.0

    def get_params(self) -> dict[str, object]:
        return {"zone": [self.low, self.high], "window": self.window}


@register_factor
class VolumeRatio(Factor):
    """Today's volume divided by the average recent volume."""

    name = "volume_ratio"
    category = FactorCategory.TECHNICAL
    higher_is_better = True

    def __init__(self, avg_window: int = 5):
        self.avg_window = avg_window

    def compute(self, ctx: FactorContext) -> float:
        volume = ctx.kline["volume"]
        if len(volume) < self.avg_window + 1:
            raise FactorError("insufficient data for volume ratio")
        today = volume.iloc[-1]
        avg = volume.iloc[-self.avg_window - 1 : -1].mean()
        if avg == 0:
            return 0.0
        return float(today / avg)

    def get_params(self) -> dict[str, object]:
        return {"avg_window": self.avg_window}


@register_factor
class TurnoverRate(Factor):
    """Binary factor: turnover rate lies inside a configured zone."""

    name = "turnover_rate"
    category = FactorCategory.TECHNICAL
    higher_is_better = True

    def __init__(self, zone: tuple[float, float] = (1.0, 10.0)):
        self.low, self.high = zone

    def compute(self, ctx: FactorContext) -> float:
        if "turnover_rate" not in ctx.kline.columns:
            return 0.0
        last = ctx.kline["turnover_rate"].iloc[-1]
        if pd.isna(last):
            return 0.0
        return 1.0 if self.low <= last <= self.high else 0.0

    def get_params(self) -> dict[str, object]:
        return {"zone": [self.low, self.high]}


@register_factor
class DistanceTo52wHigh(Factor):
    """Distance to the trailing 52-week high, in [-1, 0]."""

    name = "distance_to_52w_high"
    category = FactorCategory.TECHNICAL
    higher_is_better = True

    def compute(self, ctx: FactorContext) -> float:
        close = ctx.kline["close"]
        if len(close) < 252:
            raise FactorError("insufficient data for 52w high")
        high_52w = close.tail(252).max()
        today = close.iloc[-1]
        if high_52w == 0:
            return -1.0
        return float((today - high_52w) / high_52w)

    def get_params(self) -> dict[str, object]:
        return {}

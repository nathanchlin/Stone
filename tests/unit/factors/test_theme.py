from datetime import date

import pandas as pd

from stone.selector.factors.base import FactorContext
from stone.selector.factors.theme import IndustryMomentum5d


def _ctx() -> FactorContext:
    return FactorContext(
        code="000001",
        name="test",
        industry="白酒",
        today=date(2026, 6, 14),
        kline=pd.DataFrame({"industry_return_5d": [0.05]}),
        financial=pd.DataFrame(),
        moneyflow=pd.DataFrame(),
    )


def test_industry_momentum_returns_float():
    factor = IndustryMomentum5d()
    result = factor.compute(_ctx())
    assert result == 0.05


def test_factor_name():
    assert IndustryMomentum5d.name == "industry_momentum_5d"

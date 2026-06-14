from datetime import date

import pandas as pd

from stone.selector.factors.base import FactorContext
from stone.selector.factors.moneyflow import MainMoneyInflow5d, NorthboundInflow20d


def _ctx(moneyflow: pd.DataFrame) -> FactorContext:
    return FactorContext(
        code="000001",
        name="test",
        industry="测试",
        today=date(2026, 6, 14),
        kline=pd.DataFrame(),
        financial=pd.DataFrame(),
        moneyflow=moneyflow,
    )


def test_main_money_inflow_positive_returns_positive_value():
    mf = pd.DataFrame({"main_net": [100, 200, 150, 300, 250]})
    factor = MainMoneyInflow5d()
    result = factor.compute(_ctx(mf))
    assert result > 0


def test_main_money_inflow_negative_returns_negative_value():
    mf = pd.DataFrame({"main_net": [-100, -200, -150, -300, -250]})
    factor = MainMoneyInflow5d()
    result = factor.compute(_ctx(mf))
    assert result < 0


def test_northbound_inflow_returns_float():
    mf = pd.DataFrame({"north_net": list(range(20))})
    factor = NorthboundInflow20d()
    result = factor.compute(_ctx(mf))
    assert isinstance(result, float)


def test_factor_names():
    assert MainMoneyInflow5d.name == "main_money_inflow_5d"
    assert NorthboundInflow20d.name == "northbound_inflow_20d"

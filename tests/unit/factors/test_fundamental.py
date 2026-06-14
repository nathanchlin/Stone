from datetime import date

import pandas as pd
import pytest

from stone.selector.factors.base import FactorContext
from stone.selector.factors.fundamental import (
    PeInIndustryPercentile,
    RevenueGrowthPositive,
    RoeAbove15,
)


def _ctx(financial: pd.DataFrame) -> FactorContext:
    return FactorContext(
        code="000001",
        name="test",
        industry="测试",
        today=date(2026, 6, 14),
        kline=pd.DataFrame(),
        financial=financial,
        moneyflow=pd.DataFrame(),
    )


def test_roe_above_15_passes_when_high():
    fin = pd.DataFrame({"roe": [16.0, 17.0, 18.0, 19.0]})
    factor = RoeAbove15()
    assert factor.compute(_ctx(fin)) == 1.0


def test_roe_above_15_fails_when_low():
    fin = pd.DataFrame({"roe": [10.0, 11.0, 12.0, 13.0]})
    factor = RoeAbove15()
    assert factor.compute(_ctx(fin)) == 0.0


def test_revenue_growth_positive_passes():
    fin = pd.DataFrame({"revenue_yoy": [15.0, 20.0, 18.0, 25.0]})
    factor = RevenueGrowthPositive()
    assert factor.compute(_ctx(fin)) == 1.0


def test_revenue_growth_positive_fails_on_negative():
    fin = pd.DataFrame({"revenue_yoy": [-5.0, -10.0, -3.0, -8.0]})
    factor = RevenueGrowthPositive()
    assert factor.compute(_ctx(fin)) == 0.0


def test_pe_in_industry_percentile_low_is_good():
    fin = pd.DataFrame({"pe_industry_pct": [0.3]})
    factor = PeInIndustryPercentile()
    assert factor.compute(_ctx(fin)) == pytest.approx(0.3)


def test_factor_names():
    assert RoeAbove15.name == "roe_above_15"
    assert RevenueGrowthPositive.name == "revenue_growth_positive"
    assert PeInIndustryPercentile.name == "pe_in_industry_percentile"

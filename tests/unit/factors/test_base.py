from datetime import date

import pandas as pd
import pytest

from stone.selector.factors.base import Factor, FactorContext


class StubFactor(Factor):
    name = "stub_factor"

    def compute(self, ctx: FactorContext) -> float:
        return 42.0

    def get_params(self) -> dict[str, object]:
        return {}


def test_factor_compute_returns_float():
    factor = StubFactor()
    ctx = FactorContext(
        code="000001",
        name="test",
        industry="测试",
        today=date(2026, 6, 14),
        kline=pd.DataFrame(),
        financial=pd.DataFrame(),
        moneyflow=pd.DataFrame(),
    )
    assert factor.compute(ctx) == 42.0


def test_factor_context_required_fields():
    ctx = FactorContext(
        code="000001",
        name="test",
        industry="测试",
        today=date(2026, 6, 14),
        kline=pd.DataFrame(),
        financial=pd.DataFrame(),
        moneyflow=pd.DataFrame(),
    )
    assert ctx.code == "000001"
    assert ctx.industry == "测试"


def test_factor_subclass_must_implement_compute():
    with pytest.raises(TypeError):
        Factor()  # type: ignore[abstract]

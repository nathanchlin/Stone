from datetime import date

import pandas as pd
import pytest
from pydantic import ValidationError

from stone.selector.factors import register_factor
from stone.selector.factors.base import Factor, FactorContext
from stone.selector.scoring import ScoringEngine, StockScore
from stone.selector.strategy import Scoring, ScoringFactor


@register_factor
class StubFactorAlways100(Factor):
    name = "stub_always_100"
    category = "technical"
    higher_is_better = True

    def compute(self, ctx):
        return 100.0

    def get_params(self):
        return {}


@register_factor
class StubFactorAlways0(Factor):
    name = "stub_always_0"
    category = "technical"
    higher_is_better = True

    def compute(self, ctx):
        return 0.0

    def get_params(self):
        return {}


def _ctx():
    return FactorContext(
        code="000001",
        name="test",
        industry="测试",
        today=date(2026, 6, 14),
        kline=pd.DataFrame({"close": list(range(10, 275))}),
        financial=pd.DataFrame(),
        moneyflow=pd.DataFrame(),
    )


def test_scoring_engine_initializes_from_config():
    cfg = Scoring(
        factors=[
            ScoringFactor(factor="stub_always_100", weight=0.5),
            ScoringFactor(factor="stub_always_0", weight=0.5),
        ]
    )
    engine = ScoringEngine(cfg)
    assert len(engine.factors) == 2


def test_score_in_range_0_to_100():
    cfg = Scoring(factors=[ScoringFactor(factor="stub_always_100", weight=1.0)])
    engine = ScoringEngine(cfg)
    score = engine.score_one(_ctx())
    assert isinstance(score, StockScore)
    assert 0 <= score.score <= 100


def test_single_factor_failure_doesnt_crash():
    @register_factor
    class _CrashingFactor(Factor):
        name = "_crashing_factor"
        category = "technical"
        higher_is_better = True

        def compute(self, ctx):
            raise RuntimeError("boom")

        def get_params(self):
            return {}

    cfg = Scoring(
        factors=[
            ScoringFactor(factor="_crashing_factor", weight=0.5),
            ScoringFactor(factor="stub_always_100", weight=0.5),
        ]
    )
    engine = ScoringEngine(cfg)
    score = engine.score_one(_ctx())
    assert score.score < 100
    assert score.raw_values["_crashing_factor"] is None


def test_weights_must_sum_to_one():
    with pytest.raises(ValidationError):
        Scoring(factors=[ScoringFactor(factor="stub_always_100", weight=0.5)])

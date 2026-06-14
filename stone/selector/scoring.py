"""Scoring engine based on weighted normalized factor values."""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from stone.errors import FactorError
from stone.selector.factors import REGISTRY
from stone.selector.factors.base import Factor, FactorContext
from stone.selector.factors.normalize import Normalizer
from stone.selector.strategy import Scoring


@dataclass
class StockScore:
    """Per-stock scoring result."""

    code: str
    name: str
    industry: str
    today: date
    score: float
    raw_values: dict[str, float | None] = field(default_factory=dict)
    normalized_values: dict[str, float] = field(default_factory=dict)


class ScoringEngine:
    """Compute weighted-average scores for a single stock context."""

    def __init__(self, scoring_config: Scoring, history_window: int = 250):
        self.factors: list[tuple[Factor, float]] = [
            (REGISTRY[factor.factor](**factor.params), factor.weight)
            for factor in scoring_config.factors
        ]
        self.history_window = history_window
        self.normalizer = Normalizer()

    def score_one(self, ctx: FactorContext) -> StockScore:
        raw_values: dict[str, float | None] = {}
        normalized_values: dict[str, float] = {}

        for factor, _weight in self.factors:
            try:
                raw_value = factor.compute(ctx)
                raw_values[factor.name] = raw_value
                history = self._extract_history(ctx, factor)
                normalized = self.normalizer.normalize(
                    raw_value=raw_value,
                    history=history,
                    higher_is_better=getattr(factor, "higher_is_better", True),
                )
                normalized_values[factor.name] = normalized
            except (FactorError, Exception):
                raw_values[factor.name] = None
                normalized_values[factor.name] = 0.0

        final_score = sum(
            normalized_values[factor.name] * weight for factor, weight in self.factors
        )
        final_score = max(0.0, min(100.0, final_score))

        return StockScore(
            code=ctx.code,
            name=ctx.name,
            industry=ctx.industry,
            today=ctx.today,
            score=final_score,
            raw_values=raw_values,
            normalized_values=normalized_values,
        )

    def _extract_history(self, ctx: FactorContext, factor: Factor) -> pd.Series:
        values: list[float] = []
        window = min(self.history_window, len(ctx.kline))
        start = max(0, len(ctx.kline) - window)

        for index in range(start, len(ctx.kline) + 1):
            sliced = ctx.kline.iloc[:index]
            if len(sliced) < 30:
                continue
            tmp_ctx = FactorContext(
                code=ctx.code,
                name=ctx.name,
                industry=ctx.industry,
                today=ctx.today,
                kline=sliced,
                financial=ctx.financial,
                moneyflow=ctx.moneyflow,
                theme=ctx.theme,
                metadata=ctx.metadata,
            )
            try:
                values.append(float(factor.compute(tmp_ctx)))
            except Exception:
                continue

        return pd.Series(values, dtype=float)

"""Fundamental factors."""

import pandas as pd

from stone.constants import FactorCategory
from stone.errors import FactorError
from stone.selector.factors import register_factor
from stone.selector.factors.base import Factor, FactorContext


@register_factor
class RoeAbove15(Factor):
    """Binary factor: average trailing ROE above 15%."""

    name = "roe_above_15"
    category = FactorCategory.FUNDAMENTAL
    higher_is_better = True

    def compute(self, ctx: FactorContext) -> float:
        if ctx.financial.empty or "roe" not in ctx.financial.columns:
            return 0.0
        roe = ctx.financial["roe"].tail(4).mean()
        if pd.isna(roe):
            return 0.0
        return 1.0 if roe > 15.0 else 0.0

    def get_params(self) -> dict[str, object]:
        return {}


@register_factor
class RevenueGrowthPositive(Factor):
    """Binary factor: recent revenue YoY growth stays positive."""

    name = "revenue_growth_positive"
    category = FactorCategory.FUNDAMENTAL
    higher_is_better = True

    def compute(self, ctx: FactorContext) -> float:
        if ctx.financial.empty or "revenue_yoy" not in ctx.financial.columns:
            return 0.0
        recent = ctx.financial["revenue_yoy"].tail(2)
        if recent.empty or recent.isna().any():
            return 0.0
        return 1.0 if (recent > 0).all() else 0.0

    def get_params(self) -> dict[str, object]:
        return {}


@register_factor
class PeInIndustryPercentile(Factor):
    """Lower percentile means cheaper relative valuation inside the industry."""

    name = "pe_in_industry_percentile"
    category = FactorCategory.FUNDAMENTAL
    higher_is_better = False

    def compute(self, ctx: FactorContext) -> float:
        if ctx.financial.empty or "pe_industry_pct" not in ctx.financial.columns:
            raise FactorError("missing pe_industry_pct in financial")
        value = ctx.financial["pe_industry_pct"].iloc[-1]
        if pd.isna(value):
            return 1.0
        return float(value)

    def get_params(self) -> dict[str, object]:
        return {}

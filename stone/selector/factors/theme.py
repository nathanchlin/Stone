"""Theme and industry momentum factors."""

from stone.constants import FactorCategory
from stone.selector.factors import register_factor
from stone.selector.factors.base import Factor, FactorContext


@register_factor
class IndustryMomentum5d(Factor):
    """Use injected 5-day industry return when available."""

    name = "industry_momentum_5d"
    category = FactorCategory.THEME
    higher_is_better = True

    def compute(self, ctx: FactorContext) -> float:
        if "industry_return_5d" in ctx.kline.columns:
            return float(ctx.kline["industry_return_5d"].iloc[-1])
        return 0.0

    def get_params(self) -> dict[str, object]:
        return {}

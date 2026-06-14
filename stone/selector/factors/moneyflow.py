"""Money flow factors."""

from stone.constants import FactorCategory
from stone.selector.factors import register_factor
from stone.selector.factors.base import Factor, FactorContext


@register_factor
class MainMoneyInflow5d(Factor):
    """Raw sum of main fund net inflow over the last 5 days."""

    name = "main_money_inflow_5d"
    category = FactorCategory.MONEYFLOW
    higher_is_better = True

    def compute(self, ctx: FactorContext) -> float:
        if ctx.moneyflow.empty or "main_net" not in ctx.moneyflow.columns:
            return 0.0
        recent = ctx.moneyflow["main_net"].tail(5)
        if recent.empty or recent.isna().all():
            return 0.0
        return float(recent.sum())

    def get_params(self) -> dict[str, object]:
        return {}


@register_factor
class NorthboundInflow20d(Factor):
    """Raw sum of northbound net flow over the last 20 days."""

    name = "northbound_inflow_20d"
    category = FactorCategory.MONEYFLOW
    higher_is_better = True

    def compute(self, ctx: FactorContext) -> float:
        if ctx.moneyflow.empty or "north_net" not in ctx.moneyflow.columns:
            return 0.0
        recent = ctx.moneyflow["north_net"].tail(20)
        if recent.empty or recent.isna().all():
            return 0.0
        return float(recent.sum())

    def get_params(self) -> dict[str, object]:
        return {}

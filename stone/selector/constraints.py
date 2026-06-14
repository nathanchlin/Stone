"""Selection constraints such as per-industry caps."""

from collections import defaultdict

from stone.selector.scoring import StockScore
from stone.selector.strategy import Constraints


class ConstraintSolver:
    """Greedy diversification constraint solver."""

    def __init__(self, config: Constraints):
        self.config = config

    def apply(self, ranked: list[StockScore]) -> list[StockScore]:
        counts: dict[str, int] = defaultdict(int)
        result: list[StockScore] = []
        for stock in ranked:
            industry = stock.industry.strip() if stock.industry else ""
            if industry in {"", "unknown"}:
                result.append(stock)
                continue
            if counts[industry] < self.config.max_per_industry:
                result.append(stock)
                counts[industry] += 1
        return result

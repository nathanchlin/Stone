"""Position sizing arithmetic based on user-defined rules."""

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from stone.selector.scoring import StockScore


class PositionRules(BaseModel):
    """User-defined position sizing rules."""

    total_capital: float = Field(gt=0)
    max_total_position: float = Field(default=0.8, ge=0.0, le=1.0)
    max_per_stock: float = Field(default=0.1, ge=0.0, le=1.0)
    allocation_method: str = "equal_weight"
    round_to: int = 100
    min_position: float = 0.0
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None

    @classmethod
    def _normalize_legacy_keys(cls, raw: dict) -> dict:
        remapped = dict(raw)
        if "capital_base" in remapped and "total_capital" not in remapped:
            remapped["total_capital"] = remapped.pop("capital_base")
        if "max_single_position_pct" in remapped and "max_per_stock" not in remapped:
            remapped["max_per_stock"] = remapped.pop("max_single_position_pct")
        if "max_total_positions" in remapped and "max_total_position" not in remapped:
            max_positions = remapped.pop("max_total_positions")
            if isinstance(max_positions, (int, float)) and max_positions > 0:
                remapped["max_total_position"] = min(
                    1.0,
                    float(max_positions) * float(remapped.get("max_per_stock", 0.1)),
                )
        return remapped

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if isinstance(obj, dict):
            obj = cls._normalize_legacy_keys(obj)
        return super().model_validate(obj, *args, **kwargs)

    @field_validator("allocation_method")
    @classmethod
    def method_must_be_supported(cls, value: str) -> str:
        if value not in ("equal_weight", "score_weighted", "risk_parity", "fixed_amount"):
            raise ValueError(f"unsupported allocation_method: {value}")
        return value

    @classmethod
    def from_yaml(cls, path: Path | str) -> "PositionRules":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.model_validate(raw)


@dataclass
class PositionPlan:
    """Concrete position sizing result for one stock."""

    code: str
    amount: float
    shares: int
    pct_of_total: float
    stop_loss_price: float | None
    take_profit_price: float | None


class PositionSizer:
    """Pure arithmetic allocator, not investment advice."""

    def __init__(self, rules: PositionRules):
        self.rules = rules

    def allocate(
        self,
        picks: list[StockScore],
        close_prices: list[float] | None = None,
    ) -> list[PositionPlan]:
        if not picks:
            return []

        total_budget = self.rules.total_capital * self.rules.max_total_position
        per_cap = self.rules.total_capital * self.rules.max_per_stock
        weights = self._compute_weights(picks)

        plans: list[PositionPlan] = []
        for index, (pick, weight) in enumerate(zip(picks, weights, strict=False)):
            raw_amount = total_budget * weight
            capped = min(raw_amount, per_cap)
            rounded = (capped // self.rules.round_to) * self.rules.round_to
            if rounded < self.rules.min_position:
                continue

            price = close_prices[index] if close_prices and index < len(close_prices) else None
            shares = int(rounded / price) if price else 0
            stop_loss = (
                price * (1 - self.rules.stop_loss_pct)
                if price and self.rules.stop_loss_pct
                else None
            )
            take_profit = (
                price * (1 + self.rules.take_profit_pct)
                if price and self.rules.take_profit_pct
                else None
            )
            plans.append(
                PositionPlan(
                    code=pick.code,
                    amount=float(rounded),
                    shares=shares,
                    pct_of_total=rounded / self.rules.total_capital,
                    stop_loss_price=stop_loss,
                    take_profit_price=take_profit,
                )
            )

        return plans

    def _compute_weights(self, picks: list[StockScore]) -> list[float]:
        method = self.rules.allocation_method
        count = len(picks)
        if method in {"equal_weight", "risk_parity", "fixed_amount"}:
            return [1.0 / count] * count
        if method == "score_weighted":
            scores = [max(pick.score, 1.0) ** 1.5 for pick in picks]
            total = sum(scores)
            return [score / total for score in scores]
        return [1.0 / count] * count

"""Reporter-facing data models."""

from dataclasses import dataclass, field


@dataclass
class PickRecord:
    """Unified record shape for report outputs."""

    rank: int
    code: str
    name: str
    industry: str
    close: float
    score: float
    factor_scores: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    pe: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    roe: float | None = None
    volume_ratio: float | None = None
    turnover_rate: float | None = None
    suggested_amount: float | None = None
    suggested_shares: int | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None

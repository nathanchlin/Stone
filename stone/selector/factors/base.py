"""Base abstractions for factor implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass(slots=True)
class FactorContext:
    """Input bundle shared by all factor computations."""

    code: str
    name: str
    industry: str
    today: date
    kline: pd.DataFrame
    financial: pd.DataFrame
    moneyflow: pd.DataFrame
    theme: pd.DataFrame = field(default_factory=pd.DataFrame)
    metadata: dict[str, object] = field(default_factory=dict)


class Factor(ABC):
    """Abstract factor interface."""

    name: str

    @abstractmethod
    def compute(self, ctx: FactorContext) -> float:
        """Compute the factor score for a single security."""

    @abstractmethod
    def get_params(self) -> dict[str, object]:
        """Return the factor configuration for reporting/debugging."""

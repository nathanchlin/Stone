"""Strategy YAML schema with pydantic validation."""

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from stone.errors import StrategyError
from stone.selector.factors import REGISTRY


class Meta(BaseModel):
    """Strategy metadata."""

    name: str
    version: str
    description: str = ""
    created_at: date = Field(default_factory=date.today)


class UniverseConfig(BaseModel):
    """Universe and history settings."""

    rules_file: Path = Path("config/universe_rules.yaml")
    history_days: int = Field(default=250, ge=60, le=1000)
    include_boards: list[str] = Field(default_factory=list)
    exclude_st: bool = True


class FilterRule(BaseModel):
    """Single filter rule before scoring/ranking."""

    factor: str
    params: dict[str, Any] = Field(default_factory=dict)
    criterion: str

    @field_validator("factor")
    @classmethod
    def must_exist_in_registry(cls, value: str) -> str:
        if REGISTRY and value not in REGISTRY:
            raise ValueError(
                f"factor '{value}' not in registry. Available: {list(REGISTRY.keys())}"
            )
        return value


class ScoringFactor(BaseModel):
    """A factor and its scoring weight."""

    factor: str
    weight: float = Field(ge=0.0, le=1.0)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("factor")
    @classmethod
    def must_exist_in_registry(cls, value: str) -> str:
        if REGISTRY and value not in REGISTRY:
            raise ValueError(f"factor '{value}' not in registry")
        return value


class Scoring(BaseModel):
    """Scoring section of a strategy."""

    method: str = "weighted_average"
    factors: list[ScoringFactor]

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> "Scoring":
        if not self.factors:
            raise ValueError("scoring.factors cannot be empty")
        total = sum(factor.weight for factor in self.factors)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"权重总和必须 = 1.0，当前 = {total}")
        return self


class OutputConfig(BaseModel):
    """Output and ranking controls."""

    top_n: int = Field(default=30, ge=1, le=500)
    min_score: float = Field(default=0.0, ge=0.0, le=100.0)
    sort_by: str = "score"
    sort_desc: bool = True
    formats: list[str] = Field(default_factory=lambda: ["markdown"])


class Constraints(BaseModel):
    """Diversification constraints."""

    max_per_industry: int = Field(default=5, ge=1, le=100)
    max_per_theme: int = Field(default=3, ge=1, le=100)


class Strategy(BaseModel):
    """Full strategy definition."""

    model_config = ConfigDict(extra="forbid")

    meta: Meta
    universe: UniverseConfig
    filters: list[FilterRule] = Field(default_factory=list)
    scoring: Scoring
    output: OutputConfig
    constraints: Constraints = Field(default_factory=Constraints)


def _upgrade_legacy_strategy(raw: dict[str, Any]) -> dict[str, Any]:
    if "scoring" in raw and "output" in raw:
        return raw

    factor_entries = raw.pop("factors", [])
    output_formats = raw.pop("outputs", ["markdown"])
    top_n = raw.pop("top_n", 30)

    scoring_factors = []
    for entry in factor_entries:
        scoring_factors.append(
            {
                "factor": entry.get("factor", entry.get("name")),
                "weight": entry.get("weight", 0.0),
                "params": entry.get("params", {}),
            }
        )

    raw["filters"] = raw.get("filters", [])
    raw["scoring"] = raw.get("scoring") or {
        "method": "weighted_average",
        "factors": scoring_factors,
    }
    raw["output"] = raw.get("output") or {
        "top_n": top_n,
        "min_score": 0.0,
        "sort_by": "score",
        "sort_desc": True,
        "formats": output_formats,
    }
    raw["constraints"] = raw.get("constraints") or {"max_per_industry": 5, "max_per_theme": 3}
    return raw


def load_strategy(path: Path | str) -> Strategy:
    """Load and validate a strategy YAML file."""
    strategy_path = Path(path)
    if not strategy_path.exists():
        raise StrategyError(f"strategy file not found: {strategy_path}")

    raw = yaml.safe_load(strategy_path.read_text(encoding="utf-8")) or {}
    upgraded = _upgrade_legacy_strategy(raw)

    try:
        return Strategy.model_validate(upgraded)
    except ValidationError as exc:
        raise StrategyError(f"invalid strategy {strategy_path}: {exc}") from exc

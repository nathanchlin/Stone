"""Universe filtering rules and helpers."""

from datetime import date
from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel


class UniverseRules(BaseModel):
    """Rule set used to filter the raw market universe."""

    exclude_st: bool = True
    exclude_new_listing_days: int = 60
    exclude_paused: bool = True
    exclude_delisting_risk: bool = True
    exclude_beijing_exchange: bool = False
    min_market_cap: float | None = None

    @classmethod
    def from_yaml(cls, path: Path | str) -> "UniverseRules":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(**raw)


def get_active_universe(raw: pd.DataFrame, target_date: date, rules: UniverseRules) -> list[str]:
    """Apply configured filters and return active stock codes."""
    df = raw.copy()

    if rules.exclude_st:
        if "is_st" in df.columns:
            df = df[~df["is_st"]]
        if "name" in df.columns:
            names = df["name"].astype(str)
            df = df[~names.str.startswith("ST")]
            df = df[~names.str.startswith("*ST")]

    if rules.exclude_new_listing_days > 0 and "list_date" in df.columns:
        cutoff = pd.Timestamp(target_date) - pd.Timedelta(days=rules.exclude_new_listing_days)
        df = df[pd.to_datetime(df["list_date"]) <= cutoff]

    if rules.exclude_beijing_exchange and "code" in df.columns:
        df = df[~df["code"].astype(str).str.startswith(("8", "4"))]

    return df["code"].astype(str).tolist() if "code" in df.columns else []

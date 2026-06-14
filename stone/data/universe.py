"""Universe filtering rules and helpers."""

from datetime import date
from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel


class UniverseRules(BaseModel):
    """Rule set used to filter the raw market universe."""

    include_boards: list[str] = []
    exclude_st: bool = True
    exclude_new_listing_days: int = 60
    exclude_paused: bool = True
    exclude_delisting_risk: bool = True
    exclude_beijing_exchange: bool = False
    min_market_cap: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_avg_amount: float | None = None
    top_by_avg_amount: int | None = None

    @classmethod
    def from_yaml(cls, path: Path | str) -> "UniverseRules":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(**raw)


def get_active_universe(raw: pd.DataFrame, target_date: date, rules: UniverseRules) -> list[str]:
    """Apply configured filters and return active stock codes."""
    df = raw.copy()

    if rules.include_boards and "board" in df.columns:
        df = df[df["board"].isin(rules.include_boards)]

    if rules.exclude_st:
        if "is_st" in df.columns:
            df = df[~df["is_st"]]
        if "name" in df.columns:
            names = df["name"].astype(str)
            df = df[~names.str.startswith("ST")]
            df = df[~names.str.startswith("*ST")]

    if rules.exclude_delisting_risk and "name" in df.columns:
        names = df["name"].astype(str)
        df = df[~names.str.contains("退")]

    if rules.exclude_new_listing_days > 0 and "list_date" in df.columns:
        cutoff = pd.Timestamp(target_date) - pd.Timedelta(days=rules.exclude_new_listing_days)
        df = df[pd.to_datetime(df["list_date"]) <= cutoff]

    if rules.exclude_beijing_exchange and "code" in df.columns:
        df = df[~df["code"].astype(str).str.startswith(("8", "4"))]

    if rules.exclude_paused and "is_paused" in df.columns:
        df = df[~df["is_paused"]]

    if rules.min_market_cap is not None and "market_cap" in df.columns:
        df = df[pd.to_numeric(df["market_cap"], errors="coerce") >= rules.min_market_cap]

    if rules.min_price is not None and "close" in df.columns:
        df = df[pd.to_numeric(df["close"], errors="coerce") >= rules.min_price]

    if rules.max_price is not None and "close" in df.columns:
        df = df[pd.to_numeric(df["close"], errors="coerce") <= rules.max_price]

    if rules.min_avg_amount is not None and "avg_amount" in df.columns:
        df = df[pd.to_numeric(df["avg_amount"], errors="coerce") >= rules.min_avg_amount]

    if rules.top_by_avg_amount is not None and rules.top_by_avg_amount > 0 and "avg_amount" in df.columns:
        df = df.sort_values("avg_amount", ascending=False).head(rules.top_by_avg_amount)

    return df["code"].astype(str).tolist() if "code" in df.columns else []

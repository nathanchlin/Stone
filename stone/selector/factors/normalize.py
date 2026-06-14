"""Normalize raw factor values to [0, 100] using historical percentile."""

import numpy as np
import pandas as pd


class Normalizer:
    """Historical percentile rank normalizer."""

    def normalize(
        self,
        raw_value: float,
        history: pd.Series,
        higher_is_better: bool = True,
    ) -> float:
        """Return percentile rank of raw_value in history, scaled to [0, 100]."""
        if pd.isna(raw_value):
            return 0.0
        if history.empty:
            return 50.0

        clean = history.dropna()
        if clean.empty:
            return 50.0

        rank = (clean < raw_value).sum() / len(clean) * 100.0
        if not higher_is_better:
            rank = 100.0 - rank
        return float(np.clip(rank, 0.0, 100.0))

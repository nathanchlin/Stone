from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from stone.data.cache.parquet_store import ParquetStore
from stone.selector.engine import SelectionEngine, SelectionResult


def _fake_scores(universe, target):
    from stone.selector.scoring import StockScore

    return [
        StockScore(code=code, name=code, industry="X", today=target, score=50.0 + index)
        for index, code in enumerate(universe)
    ], []


def test_engine_runs_end_to_end_with_mocked_data(tmp_path, monkeypatch):
    from stone.selector.factors import register_factor
    from stone.selector.factors.base import Factor
    from stone.selector.strategy import (
        Constraints,
        Meta,
        OutputConfig,
        Scoring,
        ScoringFactor,
        Strategy,
        UniverseConfig,
    )

    @register_factor
    class _Stub(Factor):
        name = "_stub_engine_test"
        category = "technical"
        higher_is_better = True

        def compute(self, ctx):
            return 1.0

        def get_params(self):
            return {}

    strategy = Strategy(
        meta=Meta(name="test", version="1.0.0", created_at=date(2026, 6, 14)),
        universe=UniverseConfig(rules_file=tmp_path / "rules.yaml", history_days=60),
        filters=[],
        scoring=Scoring(factors=[ScoringFactor(factor="_stub_engine_test", weight=1.0)]),
        output=OutputConfig(top_n=5, min_score=0.0),
        constraints=Constraints(max_per_industry=10, max_per_theme=10),
    )

    store = ParquetStore(tmp_path)
    fetcher = MagicMock()
    fetcher.list_universe.return_value = pd.DataFrame(
        {"code": ["c1", "c2", "c3"], "name": ["n1", "n2", "n3"]}
    )

    engine = SelectionEngine(strategy=strategy, store=store, fetcher=fetcher)
    monkeypatch.setattr(engine, "_load_universe", lambda d: ["c1", "c2", "c3"])
    monkeypatch.setattr(engine, "_compute_scores_parallel", lambda u, d: _fake_scores(u, d))

    result = engine.run(date(2026, 6, 14))
    assert isinstance(result, SelectionResult)
    assert len(result.final_picks) == 3
    assert result.target_date == date(2026, 6, 14)

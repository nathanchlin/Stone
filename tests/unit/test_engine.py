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


def test_build_context_uses_cached_name_and_industry(tmp_path):
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
    class _StubContext(Factor):
        name = "_stub_context_test"
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
        scoring=Scoring(factors=[ScoringFactor(factor="_stub_context_test", weight=1.0)]),
        output=OutputConfig(top_n=5, min_score=0.0),
        constraints=Constraints(max_per_industry=10, max_per_theme=10),
    )

    store = ParquetStore(tmp_path)
    target = date(2026, 6, 14)
    store.write(
        "universe",
        target,
        pd.DataFrame({"code": ["c1"], "name": ["测试股"], "industry": ["白酒"]}),
    )
    store.write_kline(
        target,
        pd.DataFrame(
            {
                "code": ["c1"],
                "date": [target],
                "open": [10.0],
                "high": [11.0],
                "low": [9.0],
                "close": [10.5],
                "volume": [1000],
                "amount": [10500.0],
            }
        ),
    )

    fetcher = MagicMock()
    engine = SelectionEngine(strategy=strategy, store=store, fetcher=fetcher)
    engine._load_universe(target)
    ctx = engine._build_context("c1", target)

    assert ctx is not None
    assert ctx.name == "测试股"
    assert ctx.industry == "白酒"


def test_build_context_uses_latest_available_financial_snapshot(tmp_path):
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
    class _StubFinancial(Factor):
        name = "_stub_financial_test"
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
        scoring=Scoring(factors=[ScoringFactor(factor="_stub_financial_test", weight=1.0)]),
        output=OutputConfig(top_n=5, min_score=0.0),
        constraints=Constraints(max_per_industry=10, max_per_theme=10),
    )

    store = ParquetStore(tmp_path)
    target = date(2026, 6, 14)
    store.write("universe", target, pd.DataFrame({"code": ["c1"], "name": ["测试股"]}))
    store.write_kline(
        target,
        pd.DataFrame(
            {
                "code": ["c1"],
                "date": [target],
                "open": [10.0],
                "high": [11.0],
                "low": [9.0],
                "close": [10.5],
                "volume": [1000],
                "amount": [10500.0],
            }
        ),
    )
    store.write(
        "financial",
        date(2026, 6, 13),
        pd.DataFrame({"code": ["c1"], "date": [date(2026, 3, 31)], "roe": [18.0], "revenue_yoy": [9.0]}),
    )

    fetcher = MagicMock()
    engine = SelectionEngine(strategy=strategy, store=store, fetcher=fetcher)
    engine._load_universe(target)
    ctx = engine._build_context("c1", target)

    assert ctx is not None
    assert not ctx.financial.empty
    assert ctx.financial.iloc[0]["roe"] == 18.0

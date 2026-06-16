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


def test_load_universe_applies_rules_file(tmp_path):
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
    class _StubUniverse(Factor):
        name = "_stub_universe_test"
        category = "technical"
        higher_is_better = True

        def compute(self, ctx):
            return 1.0

        def get_params(self):
            return {}

    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(
        "\n".join(
            [
                "include_boards:",
                "  - sh_main",
                "exclude_st: true",
                "exclude_new_listing_days: 250",
                "exclude_paused: true",
                "exclude_delisting_risk: true",
                "exclude_beijing_exchange: true",
                "min_market_cap: 8000000000",
                "min_price: 5.0",
                "min_avg_amount: 200000000",
            ]
        ),
        encoding="utf-8",
    )
    strategy = Strategy(
        meta=Meta(name="test", version="1.0.0", created_at=date(2026, 6, 14)),
        universe=UniverseConfig(rules_file=rules_file, history_days=60),
        filters=[],
        scoring=Scoring(factors=[ScoringFactor(factor="_stub_universe_test", weight=1.0)]),
        output=OutputConfig(top_n=5, min_score=0.0),
        constraints=Constraints(max_per_industry=10, max_per_theme=10),
    )

    store = ParquetStore(tmp_path)
    target = date(2026, 6, 14)
    store.write(
        "universe",
        target,
        pd.DataFrame(
            {
                "code": ["600519", "830001", "600666"],
                "name": ["贵州茅台", "永顺生物", "退市测试"],
                "board": ["sh_main", "bse", "sh_main"],
                "is_st": [False, False, False],
                "is_paused": [False, False, False],
                "list_date": [date(2001, 8, 27), date(2026, 5, 1), date(2015, 1, 1)],
                "market_cap": [2e11, 3e9, 9e9],
                "close": [1700.0, 8.0, 3.0],
                "avg_amount": [8e8, 5e7, 1e8],
            }
        ),
    )

    engine = SelectionEngine(strategy=strategy, store=store, fetcher=MagicMock())
    codes = engine._load_universe(target)

    assert codes == ["600519"]


def test_build_context_fetches_and_caches_kline_when_store_is_empty(tmp_path):
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
    class _StubLiveFetch(Factor):
        name = "_stub_live_fetch_test"
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
        scoring=Scoring(factors=[ScoringFactor(factor="_stub_live_fetch_test", weight=1.0)]),
        output=OutputConfig(top_n=5, min_score=0.0),
        constraints=Constraints(max_per_industry=10, max_per_theme=10),
    )

    store = ParquetStore(tmp_path)
    target = date(2026, 6, 14)
    store.write("universe", target, pd.DataFrame({"code": ["c1"], "name": ["测试股"]}))

    hist = pd.DataFrame(
        {
            "date": pd.date_range("2026-03-01", periods=80, freq="D").date,
            "open": [10.0 + i * 0.1 for i in range(80)],
            "high": [10.5 + i * 0.1 for i in range(80)],
            "low": [9.5 + i * 0.1 for i in range(80)],
            "close": [10.2 + i * 0.1 for i in range(80)],
            "volume": [1000 + i for i in range(80)],
            "amount": [10000.0 + i * 100 for i in range(80)],
        }
    )

    fetcher = MagicMock()
    fetcher.get_daily_kline.return_value = hist
    engine = SelectionEngine(strategy=strategy, store=store, fetcher=fetcher)
    engine._load_universe(target)

    ctx = engine._build_context("c1", target)

    assert ctx is not None
    assert len(ctx.kline) == 80
    assert store.list_cached_dates("kline")


def test_fetch_close_prices_falls_back_to_latest_trading_day(tmp_path):
    """target_date has no kline (e.g., weekend) — should use most recent cached trading day."""
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
    class _StubClose(Factor):
        name = "_stub_close_test"
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
        scoring=Scoring(factors=[ScoringFactor(factor="_stub_close_test", weight=1.0)]),
        output=OutputConfig(top_n=5, min_score=0.0),
        constraints=Constraints(max_per_industry=10, max_per_theme=10),
    )

    store = ParquetStore(tmp_path)
    friday = date(2026, 6, 12)
    target = date(2026, 6, 14)  # Sunday — no kline cached

    store.write_kline(
        friday,
        pd.DataFrame(
            {
                "code": ["c1", "c2"],
                "date": [friday, friday],
                "open": [10.0, 20.0],
                "high": [11.0, 21.0],
                "low": [9.0, 19.0],
                "close": [10.5, 20.5],
                "volume": [1000, 2000],
                "amount": [10500.0, 41000.0],
            }
        ),
    )

    engine = SelectionEngine(strategy=strategy, store=store, fetcher=MagicMock())
    prices = engine._fetch_close_prices(["c1", "c2"], target)

    assert prices == [10.5, 20.5]

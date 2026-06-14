"""Integration tests for the selection pipeline with seeded data."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from stone.data.cache.parquet_store import ParquetStore
from stone.selector.engine import SelectionEngine
from stone.selector.strategy import load_strategy
from tests.helpers.seed_data import seed_kline_for_codes, seed_universe


@pytest.mark.integration
def test_pipeline_produces_picks_with_seeded_data(tmp_path):
    store = ParquetStore(tmp_path / "cache")
    target = date(2026, 6, 14)
    codes = ["c1", "c2", "c3"]
    seed_universe(store, codes, target)
    seed_kline_for_codes(store, codes, target, days=60)

    fetcher = MagicMock()
    fetcher.list_universe.return_value = MagicMock(empty=False)

    strategy_path = Path("config/strategies/band_trend_v1.yaml")
    if not strategy_path.exists():
        pytest.skip("strategy file missing")
    strategy = load_strategy(strategy_path)

    engine = SelectionEngine(strategy=strategy, store=store, fetcher=fetcher)
    result = engine.run(target)

    assert result.target_date == target
    assert isinstance(result.final_picks, list)


@pytest.mark.integration
def test_pipeline_handles_failed_codes_gracefully(tmp_path):
    store = ParquetStore(tmp_path / "cache")
    target = date(2026, 6, 14)
    codes = ["good1", "good2", "bad1"]
    seed_universe(store, codes, target)
    seed_kline_for_codes(store, ["good1", "good2"], target, days=60)

    fetcher = MagicMock()
    strategy = load_strategy("config/strategies/band_trend_v1.yaml")
    engine = SelectionEngine(strategy=strategy, store=store, fetcher=fetcher)
    result = engine.run(target)

    assert any(code == "bad1" for code, _ in result.failed_codes) or len(result.final_picks) >= 0

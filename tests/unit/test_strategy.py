import pytest

from stone.errors import StrategyError
from stone.selector.strategy import Strategy, load_strategy


def _minimal_strategy_yaml() -> str:
    return """
meta:
  name: "test strategy"
  version: "1.0.0"
  description: "for testing"
  created_at: 2026-06-14
universe:
  rules_file: config/universe_rules.yaml
  history_days: 250
filters: []
scoring:
  method: weighted_average
  factors:
    - factor: ma_bullish_alignment
      weight: 1.0
output:
  top_n: 30
  min_score: 60
  sort_by: score
  sort_desc: true
constraints:
  max_per_industry: 5
  max_per_theme: 3
"""


def test_load_strategy_from_yaml(tmp_path, monkeypatch):
    from stone.selector.factors import REGISTRY

    monkeypatch.setitem(REGISTRY, "ma_bullish_alignment", object)
    path = tmp_path / "s.yaml"
    path.write_text(_minimal_strategy_yaml(), encoding="utf-8")
    strategy = load_strategy(path)
    assert isinstance(strategy, Strategy)
    assert strategy.meta.name == "test strategy"
    assert strategy.scoring.factors[0].factor == "ma_bullish_alignment"


def test_weights_must_sum_to_one(tmp_path, monkeypatch):
    from stone.selector.factors import REGISTRY

    monkeypatch.setitem(REGISTRY, "ma_bullish_alignment", object)
    monkeypatch.setitem(REGISTRY, "ma5_above_ma20", object)
    yaml_str = _minimal_strategy_yaml().replace("weight: 1.0", "weight: 0.5")
    yaml_str = yaml_str.replace(
        "factors:\n    - factor: ma_bullish_alignment\n      weight: 0.5",
        """factors:
    - factor: ma_bullish_alignment
      weight: 0.5
    - factor: ma5_above_ma20
      weight: 0.4""",
    )
    path = tmp_path / "s.yaml"
    path.write_text(yaml_str, encoding="utf-8")
    with pytest.raises(StrategyError, match="权重总和"):
        load_strategy(path)


def test_unknown_factor_rejected(tmp_path, monkeypatch):
    from stone.selector.factors import REGISTRY

    monkeypatch.setitem(REGISTRY, "known_factor", object)
    yaml_str = _minimal_strategy_yaml().replace("ma_bullish_alignment", "nonexistent_factor")
    path = tmp_path / "s.yaml"
    path.write_text(yaml_str, encoding="utf-8")
    with pytest.raises(StrategyError):
        load_strategy(path)


def test_top_n_must_be_positive(tmp_path, monkeypatch):
    from stone.selector.factors import REGISTRY

    monkeypatch.setitem(REGISTRY, "ma_bullish_alignment", object)
    yaml_str = _minimal_strategy_yaml().replace("top_n: 30", "top_n: 0")
    path = tmp_path / "s.yaml"
    path.write_text(yaml_str, encoding="utf-8")
    with pytest.raises(StrategyError):
        load_strategy(path)

from datetime import date

import pandas as pd

from stone.data.universe import UniverseRules, get_active_universe


def _make_universe_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "code": ["600519", "000001", "300001", "688001", "830001", "ST001", "600666"],
            "name": ["贵州茅台", "平安银行", "特锐德", "华兴源创", "永顺生物", "ST测试", "退市测试"],
            "board": ["sh_main", "sz_main", "chinext", "star", "bse", "sh_main", "sh_main"],
            "is_st": [False, False, False, False, False, True, False],
            "is_paused": [False, False, False, False, False, False, False],
            "list_date": [
                date(2001, 8, 27),
                date(1991, 4, 3),
                date(2010, 1, 1),
                date(2019, 7, 22),
                date(2026, 5, 1),
                date(2020, 1, 1),
                date(2015, 1, 1),
            ],
            "market_cap": [2e11, 1.2e11, 1.5e10, 2.0e10, 3.0e9, 1.0e10, 9.0e9],
            "close": [1700.0, 12.0, 18.0, 24.0, 8.0, 6.0, 3.0],
            "avg_amount": [8e8, 5e8, 3e8, 4e8, 5e7, 2e8, 1e8],
        }
    )


def test_exclude_st():
    rules = UniverseRules(exclude_st=True, exclude_new_listing_days=60)
    codes = get_active_universe(_make_universe_df(), date(2026, 6, 14), rules)
    assert "ST001" not in codes
    assert "600519" in codes


def test_exclude_new_listing():
    rules = UniverseRules(exclude_new_listing_days=60)
    codes = get_active_universe(_make_universe_df(), date(2026, 6, 14), rules)
    assert "830001" not in codes
    assert "688001" in codes


def test_load_universe_rules_from_yaml(tmp_path):
    yaml_content = """
include_boards:
  - sh_main
  - sz_main
exclude_st: true
exclude_new_listing_days: 250
exclude_paused: true
exclude_delisting_risk: true
exclude_beijing_exchange: true
min_market_cap: 8000000000
min_price: 5.0
min_avg_amount: 200000000
"""
    path = tmp_path / "rules.yaml"
    path.write_text(yaml_content, encoding="utf-8")
    rules = UniverseRules.from_yaml(path)
    assert rules.include_boards == ["sh_main", "sz_main"]
    assert rules.exclude_st is True
    assert rules.exclude_new_listing_days == 250
    assert rules.min_market_cap == 8_000_000_000
    assert rules.min_price == 5.0
    assert rules.min_avg_amount == 200_000_000


def test_basic_pool_filters_out_bse_delisting_smallcap_and_illiquid():
    rules = UniverseRules(
        include_boards=["sh_main", "sz_main", "chinext", "star"],
        exclude_st=True,
        exclude_new_listing_days=250,
        exclude_paused=True,
        exclude_delisting_risk=True,
        exclude_beijing_exchange=True,
        min_market_cap=8_000_000_000,
        min_price=5.0,
        min_avg_amount=200_000_000,
    )
    codes = get_active_universe(_make_universe_df(), date(2026, 6, 14), rules)
    assert "600519" in codes
    assert "000001" in codes
    assert "300001" in codes
    assert "688001" in codes
    assert "830001" not in codes
    assert "ST001" not in codes
    assert "600666" not in codes

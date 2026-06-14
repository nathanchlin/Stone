import pytest

from stone.selector.position_sizing import PositionRules, PositionSizer


def _picks(n: int, scores: list[float] | None = None):
    from datetime import date

    from stone.selector.scoring import StockScore

    if scores is None:
        scores = [100 - i for i in range(n)]
    return [
        StockScore(code=f"c{i}", name=f"c{i}", industry="X", today=date(2026, 6, 14), score=score)
        for i, score in enumerate(scores)
    ]


def test_equal_weight_5_picks_80pct_total():
    rules = PositionRules(
        total_capital=100000,
        allocation_method="equal_weight",
        max_per_stock=0.5,
        max_total_position=0.8,
        round_to=100,
    )
    plans = PositionSizer(rules).allocate(_picks(5))
    assert len(plans) == 5
    assert all(plan.amount == 16000 for plan in plans)


def test_max_per_stock_cap_enforced_single_pick():
    rules = PositionRules(
        total_capital=100000,
        allocation_method="equal_weight",
        max_per_stock=0.10,
        max_total_position=0.8,
        round_to=100,
    )
    plans = PositionSizer(rules).allocate(_picks(1))
    assert plans[0].amount == 10000


def test_score_weighted_gives_higher_score_more():
    rules = PositionRules(
        total_capital=100000,
        allocation_method="score_weighted",
        max_per_stock=0.5,
        max_total_position=0.8,
        round_to=100,
    )
    plans = PositionSizer(rules).allocate(_picks(2, scores=[100.0, 50.0]))
    assert plans[0].amount > plans[1].amount


def test_round_to_100():
    rules = PositionRules(
        total_capital=99500,
        allocation_method="equal_weight",
        max_per_stock=0.5,
        max_total_position=0.8,
        round_to=100,
    )
    plans = PositionSizer(rules).allocate(_picks(5))
    assert all(plan.amount % 100 == 0 for plan in plans)


def test_total_within_max_position():
    rules = PositionRules(
        total_capital=100000,
        allocation_method="equal_weight",
        max_per_stock=0.10,
        max_total_position=0.8,
        round_to=100,
    )
    plans = PositionSizer(rules).allocate(_picks(20))
    total = sum(plan.amount for plan in plans)
    assert total <= 80000 + 100


def test_stop_loss_take_profit_prices():
    rules = PositionRules(
        total_capital=100000,
        allocation_method="equal_weight",
        max_per_stock=0.10,
        max_total_position=0.8,
        round_to=100,
        stop_loss_pct=0.08,
        take_profit_pct=0.20,
    )
    plans = PositionSizer(rules).allocate(_picks(1), close_prices=[10.0])
    assert plans[0].stop_loss_price == pytest.approx(9.2)
    assert plans[0].take_profit_price == pytest.approx(12.0)


def test_a_share_positions_use_100_share_lots():
    rules = PositionRules(
        total_capital=1000,
        allocation_method="equal_weight",
        max_per_stock=0.5,
        max_total_position=0.8,
        round_to=100,
    )
    plans = PositionSizer(rules).allocate(_picks(2), close_prices=[3.8, 3.9])
    assert len(plans) == 2
    assert plans[0].shares == 100
    assert plans[0].amount == pytest.approx(380.0)
    assert plans[1].shares == 100
    assert plans[1].amount == pytest.approx(390.0)


def test_skip_position_when_budget_cannot_buy_one_lot():
    rules = PositionRules(
        total_capital=1000,
        allocation_method="equal_weight",
        max_per_stock=0.4,
        max_total_position=0.8,
        round_to=100,
    )
    plans = PositionSizer(rules).allocate(_picks(2), close_prices=[12.0, 3.5])
    assert len(plans) == 1
    assert plans[0].code == "c1"
    assert plans[0].shares == 100
    assert plans[0].amount == pytest.approx(350.0)


def test_legacy_position_rules_yaml_keys_are_accepted(tmp_path):
    rules_file = tmp_path / "position_rules.yaml"
    rules_file.write_text(
        "\n".join(
            [
                "capital_base: 100000",
                "max_single_position_pct: 0.1",
                "max_total_positions: 8",
            ]
        ),
        encoding="utf-8",
    )
    rules = PositionRules.from_yaml(rules_file)
    assert rules.total_capital == 100000
    assert rules.max_per_stock == 0.1
    assert rules.max_total_position == pytest.approx(0.8)

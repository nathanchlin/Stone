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

from datetime import date

from stone.selector.constraints import ConstraintSolver
from stone.selector.scoring import StockScore
from stone.selector.strategy import Constraints


def _score(code: str, industry: str, score: float) -> StockScore:
    return StockScore(code=code, name=code, industry=industry, today=date(2026, 6, 14), score=score)


def test_no_constraint_passes_all():
    solver = ConstraintSolver(Constraints(max_per_industry=100, max_per_theme=100))
    ranked = [_score(f"c{i}", "X", 100 - i) for i in range(10)]
    assert len(solver.apply(ranked)) == 10


def test_max_per_industry_5_limits_to_5():
    solver = ConstraintSolver(Constraints(max_per_industry=5, max_per_theme=100))
    ranked = [_score(f"c{i}", "白酒", 100 - i) for i in range(20)]
    result = solver.apply(ranked)
    assert len(result) == 5


def test_keeps_highest_scored_in_industry():
    solver = ConstraintSolver(Constraints(max_per_industry=2, max_per_theme=100))
    ranked = [
        _score("c1", "X", 95),
        _score("c2", "X", 90),
        _score("c3", "X", 85),
        _score("c4", "Y", 80),
    ]
    result = solver.apply(ranked)
    codes = [score.code for score in result]
    assert "c1" in codes
    assert "c2" in codes
    assert "c3" not in codes
    assert "c4" in codes


def test_mixed_industries():
    solver = ConstraintSolver(Constraints(max_per_industry=2, max_per_theme=100))
    ranked = [
        _score("a1", "X", 100),
        _score("a2", "X", 90),
        _score("a3", "X", 80),
        _score("b1", "Y", 95),
        _score("b2", "Y", 85),
        _score("b3", "Y", 75),
    ]
    result = solver.apply(ranked)
    assert len(result) == 4

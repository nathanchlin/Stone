import pandas as pd

from stone.selector.factors.normalize import Normalizer


def test_value_at_high_percentile_returns_high_score():
    history = pd.Series(list(range(100)))
    norm = Normalizer()
    score = norm.normalize(raw_value=95.0, history=history)
    assert 90 <= score <= 100


def test_value_at_low_percentile_returns_low_score():
    history = pd.Series(list(range(100)))
    norm = Normalizer()
    score = norm.normalize(raw_value=2.0, history=history)
    assert score <= 10


def test_higher_is_better_false_inverts():
    history = pd.Series(list(range(100)))
    norm = Normalizer()
    score_low_pe = norm.normalize(raw_value=2.0, history=history, higher_is_better=False)
    score_high_pe = norm.normalize(raw_value=95.0, history=history, higher_is_better=False)
    assert score_low_pe > score_high_pe


def test_empty_history_returns_50():
    norm = Normalizer()
    assert norm.normalize(raw_value=1.0, history=pd.Series([], dtype=float)) == 50.0


def test_nan_raw_value_returns_zero():
    history = pd.Series(list(range(100)))
    norm = Normalizer()
    score = norm.normalize(raw_value=float("nan"), history=history)
    assert score == 0.0

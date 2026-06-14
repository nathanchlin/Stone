from tests.helpers.kline_generator import (
    generate_downtrend_kline,
    generate_sideways_kline,
    generate_uptrend_kline,
    generate_volatile_kline,
)


def test_uptrend_kline_has_increasing_close():
    df = generate_uptrend_kline(days=250)
    assert len(df) == 250
    assert df["close"].tail(50).mean() > df["close"].head(50).mean()


def test_downtrend_kline_has_decreasing_close():
    df = generate_downtrend_kline(days=250)
    assert df["close"].tail(50).mean() < df["close"].head(50).mean()


def test_kline_has_required_columns():
    df = generate_uptrend_kline(days=10)
    for col in ["date", "open", "high", "low", "close", "volume", "amount"]:
        assert col in df.columns


def test_kline_low_le_high():
    df = generate_uptrend_kline(days=50)
    assert (df["low"] <= df["high"]).all()


def test_volatile_kline_has_wider_range():
    up = generate_uptrend_kline(days=100)
    vol = generate_volatile_kline(days=100)
    assert vol["close"].pct_change().dropna().std() > up["close"].pct_change().dropna().std()


def test_sideways_kline_is_flat():
    df = generate_sideways_kline(days=100, base_price=10.0)
    assert abs(df["close"].mean() - 10.0) < 0.5

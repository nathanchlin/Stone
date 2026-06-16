from datetime import date

import pandas as pd

from stone.data.cache.parquet_store import ParquetStore


def _make_kline_df(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "code": ["000001"] * n,
            "open": [10.0] * n,
            "high": [11.0] * n,
            "low": [9.0] * n,
            "close": [10.5] * n,
            "volume": [1000] * n,
        }
    )


def test_write_and_read_kline_roundtrip(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    target = date(2026, 6, 14)
    store.write_kline(target, _make_kline_df(3))

    df = store.read_kline(target)
    assert len(df) == 3
    assert list(df.columns) == ["code", "open", "high", "low", "close", "volume"]


def test_read_kline_missing_date_returns_empty(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    df = store.read_kline(date(2099, 1, 1))
    assert df.empty


def test_read_kline_range_returns_concatenated(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 13), _make_kline_df(2))
    store.write_kline(date(2026, 6, 14), _make_kline_df(3))
    df = store.read_kline_range(date(2026, 6, 13), date(2026, 6, 14))
    assert len(df) == 5


def test_list_cached_dates(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 13), _make_kline_df(1))
    store.write_kline(date(2026, 6, 14), _make_kline_df(1))
    dates = store.list_cached_dates("kline")
    assert date(2026, 6, 13) in dates
    assert date(2026, 6, 14) in dates


def test_get_missing_dates(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 13), _make_kline_df(1))
    missing = store.get_missing_dates("kline", [date(2026, 6, 13), date(2026, 6, 14)])
    assert missing == [date(2026, 6, 14)]


def test_read_latest_before_returns_target_when_present(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 12), _make_kline_df(1))
    store.write_kline(date(2026, 6, 13), _make_kline_df(2))
    df = store.read_latest_before("kline", date(2026, 6, 13))
    assert len(df) == 2  # exact match for target_date


def test_read_latest_before_falls_back_when_target_missing(tmp_path):
    """target_date is a weekend/holiday — should return the most recent trading day."""
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 11), _make_kline_df(1))
    store.write_kline(date(2026, 6, 12), _make_kline_df(3))
    # 2026-06-13 Sat, 2026-06-14 Sun, 2026-06-15 Mon — none cached
    df = store.read_latest_before("kline", date(2026, 6, 15))
    assert len(df) == 3  # falls back to 2026-06-12 (Friday)


def test_read_kline_latest_before_convenience_method(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 12), _make_kline_df(2))
    df = store.read_kline_latest_before(date(2026, 6, 14))
    assert len(df) == 2


def test_read_latest_before_returns_empty_when_no_data(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    df = store.read_latest_before("kline", date(2026, 6, 14))
    assert df.empty


def test_read_latest_before_returns_empty_when_target_before_all_cache(tmp_path):
    """target_date is earlier than any cached date — no fallback possible."""
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 14), _make_kline_df(1))
    df = store.read_latest_before("kline", date(2026, 6, 13))
    assert df.empty


def _make_multi_code_kline_df(codes: list[str], target_date: date) -> pd.DataFrame:
    """Build kline DataFrame with multiple codes for one date."""
    return pd.DataFrame(
        {
            "code": codes,
            "date": [target_date] * len(codes),
            "open": [10.0] * len(codes),
            "high": [11.0] * len(codes),
            "low": [9.0] * len(codes),
            "close": [10.5] * len(codes),
            "volume": [1000] * len(codes),
        }
    )


def test_read_kline_range_grouped_returns_dict_by_code(tmp_path):
    """Returns dict[code, DataFrame] from multi-date, multi-code parquet partitions."""
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 13), _make_multi_code_kline_df(["c1", "c2"], date(2026, 6, 13)))
    store.write_kline(date(2026, 6, 14), _make_multi_code_kline_df(["c1", "c2"], date(2026, 6, 14)))

    grouped = store.read_kline_range_grouped(date(2026, 6, 13), date(2026, 6, 14))

    assert set(grouped.keys()) == {"c1", "c2"}
    assert len(grouped["c1"]) == 2  # 2 dates
    assert len(grouped["c2"]) == 2
    assert list(grouped["c1"]["date"]) == [date(2026, 6, 13), date(2026, 6, 14)]


def test_read_kline_range_grouped_filters_by_date(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 12), _make_multi_code_kline_df(["c1"], date(2026, 6, 12)))
    store.write_kline(date(2026, 6, 13), _make_multi_code_kline_df(["c1"], date(2026, 6, 13)))
    store.write_kline(date(2026, 6, 14), _make_multi_code_kline_df(["c1"], date(2026, 6, 14)))

    grouped = store.read_kline_range_grouped(date(2026, 6, 13), date(2026, 6, 14))
    assert list(grouped["c1"]["date"]) == [date(2026, 6, 13), date(2026, 6, 14)]


def test_read_kline_range_grouped_empty_when_no_data(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    grouped = store.read_kline_range_grouped(date(2026, 6, 13), date(2026, 6, 14))
    assert grouped == {}


def test_read_kline_range_grouped_preserves_all_columns(tmp_path):
    store = ParquetStore(base_dir=tmp_path)
    df = pd.DataFrame(
        {
            "code": ["c1"],
            "date": [date(2026, 6, 14)],
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [1000],
            "amount": [10500.0],
            "turnover_rate": [0.6],
        }
    )
    store.write_kline(date(2026, 6, 14), df)

    grouped = store.read_kline_range_grouped(date(2026, 6, 14), date(2026, 6, 14))
    assert "turnover_rate" in grouped["c1"].columns
    assert grouped["c1"].iloc[0]["close"] == 10.5


def test_read_kline_range_grouped_skips_missing_partitions(tmp_path):
    """If list_cached_dates returns a date but the file is missing, skip gracefully."""
    store = ParquetStore(base_dir=tmp_path)
    store.write_kline(date(2026, 6, 13), _make_multi_code_kline_df(["c1"], date(2026, 6, 13)))
    # Manually remove the file but leave the dir
    (tmp_path / "kline" / "date=2026-06-14").mkdir(parents=True)

    grouped = store.read_kline_range_grouped(date(2026, 6, 13), date(2026, 6, 14))
    assert "c1" in grouped
    assert len(grouped["c1"]) == 1

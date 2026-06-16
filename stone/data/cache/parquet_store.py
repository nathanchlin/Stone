"""Parquet-backed cache partitioned by date."""

from datetime import date
from pathlib import Path

import pandas as pd


class ParquetStore:
    """Read and write tabular cache files with a date partition layout."""

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir)

    def _path(self, kind: str, target: date) -> Path:
        return self.base_dir / kind / f"date={target.isoformat()}" / "data.parquet"

    def write(self, kind: str, target: date, df: pd.DataFrame) -> None:
        path = self._path(kind, target)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    def write_kline(self, target: date, df: pd.DataFrame) -> None:
        self.write("kline", target, df)

    def read(self, kind: str, target: date) -> pd.DataFrame:
        path = self._path(kind, target)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    def read_kline(self, target: date) -> pd.DataFrame:
        return self.read("kline", target)

    def read_latest_before(self, kind: str, target: date) -> pd.DataFrame:
        """Return the latest cached partition for `kind` on or before `target`.

        Falls back to the most recent trading day when `target` is a weekend,
        holiday, or uncached date. Returns empty DataFrame if no partition
        exists at or before `target`.
        """
        for cached_date in reversed(self.list_cached_dates(kind)):
            if cached_date <= target:
                return self.read(kind, cached_date)
        return pd.DataFrame()

    def read_kline_latest_before(self, target: date) -> pd.DataFrame:
        return self.read_latest_before("kline", target)

    def read_range(self, kind: str, start: date, end: date) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for target in self.list_cached_dates(kind):
            if start <= target <= end:
                frame = self.read(kind, target)
                if not frame.empty:
                    frames.append(frame)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def read_kline_range(self, start: date, end: date) -> pd.DataFrame:
        return self.read_range("kline", start, end)

    def read_kline_range_grouped(
        self, start: date, end: date
    ) -> dict[str, pd.DataFrame]:
        """Read all klines in [start, end] and group by code.

        Single-pass read via pyarrow ParquetDataset is much faster than
        N × pd.read_parquet for large date ranges. Used by SelectionEngine
        to preload all klines once instead of N times (C2/C4 fix).
        """
        paths = [
            self._path("kline", d)
            for d in self.list_cached_dates("kline")
            if start <= d <= end and self._path("kline", d).exists()
        ]
        if not paths:
            return {}

        try:
            import pyarrow.parquet as pq

            table = pq.ParquetDataset(paths).read()
            df = table.to_pandas()
        except Exception:
            # Fallback to per-file read if pyarrow path fails
            frames = [pd.read_parquet(p) for p in paths]
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        if df.empty or "code" not in df.columns:
            return {}

        # Normalize date column type
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
            df = df.dropna(subset=["date"])

        return {
            str(code): group.sort_values("date").reset_index(drop=True)
            for code, group in df.groupby("code")
        }

    def list_cached_dates(self, kind: str) -> list[date]:
        kind_dir = self.base_dir / kind
        if not kind_dir.exists():
            return []

        cached_dates: list[date] = []
        for child in kind_dir.iterdir():
            if not child.is_dir() or not child.name.startswith("date="):
                continue
            try:
                cached_dates.append(date.fromisoformat(child.name.removeprefix("date=")))
            except ValueError:
                continue
        return sorted(cached_dates)

    def get_missing_dates(self, kind: str, expected: list[date]) -> list[date]:
        cached = set(self.list_cached_dates(kind))
        return [target for target in expected if target not in cached]

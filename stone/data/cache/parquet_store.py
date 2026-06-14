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

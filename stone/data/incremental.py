"""Daily incremental data update."""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from tqdm import tqdm

from stone.data.cache.parquet_store import ParquetStore
from stone.data.fetchers.base import DataFetcher


@dataclass
class UpdateReport:
    """Summary of one incremental update run."""

    target_date: date
    success_dates: list[date] = field(default_factory=list)
    failed_dates: list[date] = field(default_factory=list)
    skipped_dates: list[date] = field(default_factory=list)
    failed_codes: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Update {self.target_date}: "
            f"success={len(self.success_dates)}, "
            f"failed={len(self.failed_dates)}, "
            f"skipped={len(self.skipped_dates)}"
        )


class IncrementalUpdater:
    """Backfill and daily-update kline cache by trading day."""

    def __init__(self, store: ParquetStore, fetcher: DataFetcher, lookback_days: int = 365):
        self.store = store
        self.fetcher = fetcher
        self.lookback_days = lookback_days

    def update_daily(self, target_date: date) -> UpdateReport:
        report = UpdateReport(target_date=target_date)
        start = pd.Timestamp(target_date) - pd.Timedelta(days=self.lookback_days)

        calendar = self.fetcher.get_trade_calendar(start.date(), target_date)
        missing_dates = self.store.get_missing_dates("kline", calendar)
        cached_dates = set(self.store.list_cached_dates("kline"))
        report.skipped_dates = [target for target in calendar if target in cached_dates]

        for current_date in tqdm(missing_dates, desc="Updating dates"):
            try:
                self._fetch_and_store_one_day(current_date, report)
                report.success_dates.append(current_date)
            except Exception as exc:  # pragma: no cover - exercised via report behavior
                report.failed_dates.append(current_date)
                report.failed_codes.append((current_date.isoformat(), str(exc)))

        return report

    def _fetch_and_store_one_day(self, target_date: date, report: UpdateReport) -> None:
        universe_df = self.fetcher.list_universe(target_date)
        if universe_df.empty:
            raise RuntimeError(f"empty universe for {target_date}")

        frames: list[pd.DataFrame] = []
        for code in universe_df["code"].astype(str):
            try:
                kline = self.fetcher.get_daily_kline(code, target_date, target_date)
                if kline.empty:
                    report.failed_codes.append((code, "empty kline"))
                    continue
                day_frame = kline.copy()
                day_frame["code"] = code
                frames.append(day_frame)
            except Exception as exc:
                report.failed_codes.append((code, str(exc)))

        if not frames:
            raise RuntimeError(f"no kline data for {target_date}")

        combined = pd.concat(frames, ignore_index=True)
        self.store.write_kline(target_date, combined)

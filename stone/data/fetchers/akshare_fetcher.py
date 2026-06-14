"""Akshare-backed implementation of the data fetcher protocol."""

from datetime import date
from json import JSONDecodeError
from pathlib import Path

import pandas as pd

from stone.constants import AKSHARE_MAX_RATE
from stone.data.fetchers._rate_limiter import RateLimiter
from stone.data.fetchers._retry import with_retry
from stone.errors import DataError

try:
    import akshare as ak
except ImportError:  # pragma: no cover - handled at runtime in environments without akshare
    ak = None

_KLINE_RENAME = {
    "日期": "date",
    "股票代码": "code",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
    "换手率": "turnover_rate",
}

_FINANCIAL_RENAME_CANDIDATES = {
    "roe": ["净资产收益率(%)", "加权净资产收益率(%)"],
    "revenue_yoy": ["主营业务收入增长率(%)", "营业收入增长率(%)"],
}

_MONEYFLOW_RENAME_CANDIDATES = {
    "main_net": ["主力净流入-净额", "主力净流入净额", "主力净流入"],
    "north_net": ["北向资金净流入", "北向净流入", "陆股通净流入"],
}


class AkshareFetcher:
    """Market data fetcher using akshare's public endpoints."""

    def __init__(
        self,
        rate_limiter: RateLimiter | None = None,
        snapshot_dir: Path | str = "data_cache/fetcher_cache",
    ):
        self._limiter = rate_limiter or RateLimiter(max_rate=AKSHARE_MAX_RATE)
        self._hist_limiter = RateLimiter(max_rate=1.0)
        self._snapshot_dir = Path(snapshot_dir)

    def _require_client(self):
        if ak is None:
            raise DataError("akshare is not installed")
        return ak

    def _snapshot_path(self, kind: str, key: str) -> Path:
        return self._snapshot_dir / kind / f"{key}.parquet"

    def _read_snapshot(self, kind: str, key: str) -> pd.DataFrame:
        path = self._snapshot_path(kind, key)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    def _write_snapshot(self, kind: str, key: str, df: pd.DataFrame) -> None:
        path = self._snapshot_path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    def _classify_board(self, code: str) -> str:
        if code.startswith(("688", "689")):
            return "star"
        if code.startswith(("300", "301")):
            return "chinext"
        if code.startswith(("8", "4")):
            return "bse"
        if code.startswith(("6", "9")):
            return "sh_main"
        return "sz_main"

    def _normalize_spot_universe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["code", "name", "board", "is_st", "close", "avg_amount"])

        renamed = df.rename(columns={"代码": "code", "名称": "name", "最新价": "close", "成交额": "avg_amount"})
        normalized = renamed[[column for column in ["code", "name", "close", "avg_amount"] if column in renamed.columns]].copy()
        normalized["code"] = normalized["code"].astype(str).str.extract(r"(\d{6})", expand=False)
        normalized = normalized.dropna(subset=["code", "name"])
        normalized["code"] = normalized["code"].astype(str).str.zfill(6)
        normalized["close"] = pd.to_numeric(normalized.get("close"), errors="coerce")
        normalized["avg_amount"] = pd.to_numeric(normalized.get("avg_amount"), errors="coerce")
        normalized["board"] = normalized["code"].map(self._classify_board)
        names = normalized["name"].astype(str)
        normalized["is_st"] = names.str.startswith("ST") | names.str.startswith("*ST")
        return normalized[["code", "name", "board", "is_st", "close", "avg_amount"]]

    def _normalize_financial(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["date", "roe", "revenue_yoy"])

        normalized = pd.DataFrame()
        if "日期" in df.columns:
            normalized["date"] = pd.to_datetime(df["日期"], errors="coerce").dt.date

        for target, candidates in _FINANCIAL_RENAME_CANDIDATES.items():
            for candidate in candidates:
                if candidate in df.columns:
                    normalized[target] = pd.to_numeric(df[candidate], errors="coerce")
                    break

        for required in ["roe", "revenue_yoy"]:
            if required not in normalized.columns:
                normalized[required] = pd.Series(dtype=float)

        if "date" not in normalized.columns:
            normalized["date"] = pd.Series(dtype=object)

        return normalized[["date", "roe", "revenue_yoy"]]

    def _normalize_moneyflow(self, df: pd.DataFrame) -> pd.DataFrame:
        normalized = pd.DataFrame(columns=["main_net", "north_net"])
        if df.empty:
            return normalized

        for target, candidates in _MONEYFLOW_RENAME_CANDIDATES.items():
            for candidate in candidates:
                if candidate in df.columns:
                    normalized[target] = pd.to_numeric(df[candidate], errors="coerce")
                    break

        for required in ["main_net", "north_net"]:
            if required not in normalized.columns:
                normalized[required] = pd.Series(dtype=float)

        return normalized[["main_net", "north_net"]]

    @with_retry()
    def list_universe(self, target_date: date) -> pd.DataFrame:
        self._limiter.acquire()
        client = self._require_client()
        try:
            spot = client.stock_zh_a_spot()
            normalized = self._normalize_spot_universe(spot)
            if normalized.empty:
                raise DataError(f"Empty spot universe for {target_date}")
            self._write_snapshot("universe", "latest", normalized)
            return normalized
        except Exception:
            cached = self._read_snapshot("universe", "latest")
            if not cached.empty:
                return cached

        df = client.stock_info_a_code_name()
        if df.empty:
            raise DataError(f"Empty universe for {target_date}")
        renamed = df.rename(columns={"代码": "code", "名称": "name"})
        fallback = renamed[["code", "name"]].copy()
        fallback["code"] = fallback["code"].astype(str).str.zfill(6)
        fallback["board"] = fallback["code"].map(self._classify_board)
        names = fallback["name"].astype(str)
        fallback["is_st"] = names.str.startswith("ST") | names.str.startswith("*ST")
        self._write_snapshot("universe", "latest", fallback)
        return fallback

    @with_retry()
    def get_daily_kline(
        self, code: str, start: date, end: date, adjust: str = "qfq"
    ) -> pd.DataFrame:
        cached = self._read_snapshot("kline", code)
        if not cached.empty:
            cached["date"] = pd.to_datetime(cached["date"], errors="coerce").dt.date
            cached = cached.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
            subset = cached[(cached["date"] >= start) & (cached["date"] <= end)].reset_index(drop=True)
            if not subset.empty and cached["date"].min() <= start and cached["date"].max() >= end:
                return subset

        self._hist_limiter.acquire()
        client = self._require_client()
        try:
            df = client.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust=adjust,
            )
        except Exception:
            if not cached.empty:
                subset = cached[(cached["date"] >= start) & (cached["date"] <= end)].reset_index(drop=True)
                if not subset.empty:
                    return subset
            raise

        if df.empty:
            if not cached.empty:
                subset = cached[(cached["date"] >= start) & (cached["date"] <= end)].reset_index(drop=True)
                if not subset.empty:
                    return subset
            raise DataError(f"Empty kline for {code} from {start} to {end}")

        renamed = df.rename(columns=_KLINE_RENAME)
        canonical_columns = ["date", "open", "high", "low", "close", "volume", "amount"]
        if "turnover_rate" in renamed.columns:
            canonical_columns.append("turnover_rate")
        canonical = renamed[canonical_columns].copy()
        canonical["date"] = pd.to_datetime(canonical["date"]).dt.date
        canonical = canonical.sort_values("date").reset_index(drop=True)
        if cached.empty:
            merged = canonical
        else:
            merged = pd.concat([cached, canonical], ignore_index=True)
            merged = merged.drop_duplicates(subset=["date"], keep="last")
            merged = merged.sort_values("date").reset_index(drop=True)
        self._write_snapshot("kline", code, merged)
        subset = merged[(merged["date"] >= start) & (merged["date"] <= end)].reset_index(drop=True)
        if subset.empty:
            raise DataError(f"Empty kline for {code} from {start} to {end}")
        return subset

    @with_retry()
    def get_basic_financial(self, code: str) -> pd.DataFrame:
        self._limiter.acquire()
        client = self._require_client()
        start_year = str(max(date.today().year - 5, 2000))
        raw = client.stock_financial_analysis_indicator(symbol=code.zfill(6), start_year=start_year)
        return self._normalize_financial(raw)

    @with_retry()
    def get_money_flow(self, code: str, days: int = 30) -> pd.DataFrame:
        self._limiter.acquire()
        client = self._require_client()
        market = "sh" if code.startswith(("6", "9")) else "sz"
        try:
            raw = client.stock_individual_fund_flow(stock=code, market=market)
        except (ConnectionError, TimeoutError, JSONDecodeError):
            return pd.DataFrame(columns=["main_net", "north_net"])
        return self._normalize_moneyflow(raw.tail(days))

    @with_retry()
    def get_industry_mapping(self) -> dict[str, str]:
        self._limiter.acquire()
        client = self._require_client()
        boards = client.stock_board_industry_name_em()
        mapping: dict[str, str] = {}
        for board_name in boards.get("板块名称", []):
            try:
                constituents = client.stock_board_industry_cons_em(symbol=board_name)
            except Exception:
                continue
            for _, row in constituents.iterrows():
                mapping[str(row["代码"])] = str(board_name)
        return mapping

    @with_retry()
    def get_trade_calendar(self, start: date, end: date) -> list[date]:
        self._limiter.acquire()
        client = self._require_client()
        df = client.tool_trade_date_hist_sina()
        dates = pd.to_datetime(df["trade_date"]).dt.date.tolist()
        return [target for target in dates if start <= target <= end]

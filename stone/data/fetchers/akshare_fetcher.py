"""Akshare-backed implementation of the data fetcher protocol."""

from datetime import date
from pathlib import Path

import pandas as pd

from stone.constants import AKSHARE_MAX_RATE
from stone.data.fetchers._rate_limiter import RateLimiter
from stone.data.fetchers._retry import TRANSIENT_EXCEPTIONS, with_retry
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

KLINE_SOURCES = ("eastmoney", "netease")


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
        today = date.today()
        cached = self._read_snapshot("kline", code)
        if not cached.empty:
            cached["date"] = pd.to_datetime(cached["date"], errors="coerce").dt.date
            cached = cached.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
            subset = cached[(cached["date"] >= start) & (cached["date"] <= end)].reset_index(drop=True)
            # Skip early-return when today is in range — sina may have fresher data
            # than the cached snapshot (netease is T+1 delayed).
            if (
                end < today
                and not subset.empty
                and cached["date"].min() <= start
                and cached["date"].max() >= end
            ):
                return subset

        self._hist_limiter.acquire()
        client = self._require_client()
        try:
            df, source = self._fetch_kline_with_fallback(client, code, start, end, adjust)
        except Exception:
            if not cached.empty:
                subset = cached[(cached["date"] >= start) & (cached["date"] <= end)].reset_index(drop=True)
                if not subset.empty:
                    # Fall through to sina merge below instead of returning
                    merged = cached
                    return self._merge_realtime_and_return(merged, code, start, end, today)
            raise

        if not isinstance(df, pd.DataFrame) or df.empty:
            if not cached.empty:
                merged = cached
            else:
                raise DataError(f"Empty kline for {code} from {start} to {end}")
        else:
            if source == "eastmoney":
                renamed = df.rename(columns=_KLINE_RENAME)
            else:  # netease already returns English columns
                renamed = df.rename(columns={"turnover": "turnover_rate"})
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

        return self._merge_realtime_and_return(merged, code, start, end, today)

    def _merge_realtime_and_return(
        self,
        merged: pd.DataFrame,
        code: str,
        start: date,
        end: date,
        today: date,
    ) -> pd.DataFrame:
        """Append today's sina realtime quote if missing from merged, then return subset.

        netease daily kline is T+1 delayed (returns data through yesterday). This
        merge ensures callers always see today's data when end >= today.
        """
        if end >= today and (merged.empty or merged["date"].max() < today):
            sina_row = self._fetch_kline_realtime_sina(code)
            if not sina_row.empty and sina_row.iloc[0]["date"] == today:
                merged = merged[merged["date"] != today]
                merged = pd.concat([merged, sina_row], ignore_index=True)
                merged = merged.sort_values("date").reset_index(drop=True)

        self._write_snapshot("kline", code, merged)
        subset = merged[(merged["date"] >= start) & (merged["date"] <= end)].reset_index(drop=True)
        if subset.empty:
            raise DataError(f"Empty kline for {code} from {start} to {end}")
        return subset

    def _fetch_kline_eastmoney(
        self, client, code: str, start: date, end: date, adjust: str
    ) -> pd.DataFrame:
        """Primary source: eastmoney stock_zh_a_hist."""
        return client.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust=adjust,
        )

    def _fetch_kline_netease(
        self, client, code: str, start: date, end: date, adjust: str
    ) -> pd.DataFrame:
        """Fallback source: netease stock_zh_a_daily. Symbol needs sh/sz prefix."""
        prefix = "sh" if code.startswith(("6", "9")) else "sz"
        raw = client.stock_zh_a_daily(
            symbol=f"{prefix}{code}",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust=adjust,
        )
        # netease turnover is decimal (0.005 = 0.5%); eastmoney 换手率 is percent (0.5)
        # normalize to percent so downstream turnover_rate factor behaves consistently
        if isinstance(raw, pd.DataFrame) and not raw.empty and "turnover" in raw.columns:
            raw = raw.copy()
            raw["turnover"] = pd.to_numeric(raw["turnover"], errors="coerce") * 100
        return raw

    def _fetch_kline_realtime_sina(self, code: str) -> pd.DataFrame:
        """Fetch today's OHLCV snapshot from sina hq endpoint.

        netease daily kline has T+1 delay (only returns data through yesterday).
        This method fetches today's realtime data so callers can access the
        freshest available close. Returns empty DataFrame on any failure.

        Note: during market hours (9:30-15:00), the "close" field is actually
        the current intraday price. After 15:00, it is the official close.
        """
        import re

        import requests

        prefix = "sh" if code.startswith(("6", "9")) else "sz"
        url = "https://hq.sinajs.cn"
        headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        try:
            resp = requests.get(
                url,
                params={"list": f"{prefix}{code}"},
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
        except Exception:  # noqa: BLE001 — best-effort realtime fetch
            return pd.DataFrame()

        match = re.search(r'"([^"]+)"', resp.text)
        if not match:
            return pd.DataFrame()
        parts = match.group(1).split(",")
        if len(parts) < 32:
            return pd.DataFrame()

        try:
            from datetime import datetime as _dt

            sina_date = _dt.strptime(parts[30], "%Y-%m-%d").date()
            return pd.DataFrame(
                [
                    {
                        "date": sina_date,
                        "open": float(parts[1]),
                        "close": float(parts[3]),
                        "high": float(parts[4]),
                        "low": float(parts[5]),
                        "volume": float(parts[8]),
                        "amount": float(parts[9]),
                    }
                ]
            )
        except (ValueError, IndexError):
            return pd.DataFrame()

    def _fetch_kline_with_fallback(
        self, client, code: str, start: date, end: date, adjust: str
    ) -> tuple[pd.DataFrame, str]:
        """Try each source in order. Re-raise last transient exception if all fail transiently."""
        last_exc: Exception | None = None
        for source_name in KLINE_SOURCES:
            try:
                fn = getattr(self, f"_fetch_kline_{source_name}")
                df = fn(client, code, start, end, adjust)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    return df, source_name
            except TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                continue
        if last_exc is not None:
            raise last_exc
        return pd.DataFrame(), "none"

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
            if not raw.empty:
                return self._normalize_moneyflow(raw.tail(days))
        except TRANSIENT_EXCEPTIONS:
            pass
        # Fallback 1: eastmoney push2 daykline endpoint (multi-day, sometimes blocked)
        df = self._fetch_moneyflow_push2(code, market, days)
        if not df.empty:
            return df
        # Fallback 2: eastmoney push2 ulist snapshot (today only — most reliable)
        return self._fetch_moneyflow_push2_snapshot(code, market)

    def _fetch_moneyflow_push2(
        self, code: str, market: str, days: int
    ) -> pd.DataFrame:
        """Fetch daily fund flow via eastmoney push2 daykline endpoint."""
        import requests

        secid = f"{'1' if market == 'sh' else '0'}.{code}"
        url = "https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get"
        params: dict[str, str] = {
            "lmt": str(days),
            "klt": "101",  # daily
            "secid": secid,
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
        }
        try:
            resp = requests.get(
                url,
                params=params,
                headers={
                    "Referer": "https://data.eastmoney.com/",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:  # noqa: BLE001 — best-effort fallback
            return pd.DataFrame(columns=["main_net", "north_net"])

        klines = data.get("data", {}).get("klines", []) if data.get("data") else []
        if not klines:
            return pd.DataFrame(columns=["main_net", "north_net"])

        rows: list[dict] = []
        for line in klines:
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                rows.append(
                    {
                        "date": pd.to_datetime(parts[0]).date(),
                        "main_net": float(parts[1]),  # 主力净流入
                        "small_net": float(parts[2]),
                        "medium_net": float(parts[3]),
                        "large_net": float(parts[4]),
                        "super_large_net": float(parts[5]),
                        "north_net": float("nan"),
                    }
                )
            except (ValueError, IndexError):
                continue

        if not rows:
            return pd.DataFrame(columns=["main_net", "north_net"])

        return pd.DataFrame(rows).tail(days)

    def _fetch_moneyflow_push2_snapshot(
        self, code: str, market: str
    ) -> pd.DataFrame:
        """Fetch today's fund flow snapshot via eastmoney push2 ulist endpoint.

        Less preferred than the daykline endpoint (only today's value, no
        history), but more reliable when anti-bot is aggressive.
        """
        from datetime import date as _date

        import requests

        secid = f"{'1' if market == 'sh' else '0'}.{code}"
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
        params: dict[str, str] = {
            "secids": secid,
            "fields": "f12,f55,f62,f66,f72,f78,f84",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
        }
        try:
            resp = requests.get(
                url,
                params=params,
                headers={
                    "Referer": "https://data.eastmoney.com/",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:  # noqa: BLE001
            return pd.DataFrame(columns=["main_net", "north_net"])

        diff = data.get("data", {}).get("diff", []) if data.get("data") else []
        if not diff:
            return pd.DataFrame(columns=["main_net", "north_net"])

        row = diff[0]
        try:
            return pd.DataFrame(
                [
                    {
                        "date": _date.today(),
                        "main_net": float(row.get("f62", 0)),  # 主力净流入
                        "super_large_net": float(row.get("f66", 0)),
                        "large_net": float(row.get("f72", 0)),
                        "medium_net": float(row.get("f78", 0)),
                        "small_net": float(row.get("f84", 0)),
                        "north_net": float("nan"),
                    }
                ]
            )
        except (ValueError, TypeError):
            return pd.DataFrame(columns=["main_net", "north_net"])

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

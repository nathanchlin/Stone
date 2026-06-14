"""Chart rendering helpers."""

import base64
import io

import mplfinance as mpf
import pandas as pd


def render_kline_b64(kline: pd.DataFrame, code: str, name: str, days: int = 60) -> str:
    """Render a candlestick chart and return base64 PNG."""
    if kline.empty or len(kline) < 30:
        return ""

    df = kline.tail(days).copy()
    if "date" in df.columns:
        df["Date"] = pd.to_datetime(df["date"])
    elif "Date" not in df.columns:
        df["Date"] = pd.date_range(end="today", periods=len(df))
    df = df.set_index("Date")
    if not all(column in df.columns for column in ["Open", "High", "Low", "Close"]):
        df = df.rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )

    try:
        fig, _ = mpf.plot(
            df,
            type="candle",
            style="charles",
            volume="Volume" in df.columns,
            mav=(5, 20) if len(df) >= 20 else None,
            title=f"{code} {name}",
            returnfig=True,
            figsize=(10, 6),
        )
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
        return base64.b64encode(buffer.getvalue()).decode()
    except Exception:
        return ""

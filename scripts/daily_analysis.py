"""Daily position analysis automation.

Three modes:
  pre-market  (8:30 launchd)  — 昨日复盘 + 今日预警
  intraday    (14:00 launchd) — 盘中实时监控 + 决策支持
  review      (16:00 launchd) — 收盘复盘 + 明日清单

Legal: tool computes P&L + risk metrics from user-preset positions in
config/positions.yaml. Tool does NOT recommend buys/sells.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import akshare as ak
import pandas as pd
import yaml

from stone.data.fetchers.akshare_fetcher import AkshareFetcher

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_config(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"Config not found: {path}. Copy positions.example.yaml → positions.yaml.")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def fetch_stock_data(fetcher: AkshareFetcher, code: str, days: int = 10) -> dict:
    """Get latest OHLCV via project fetcher (auto sina-realtime for today)."""
    today = date.today()
    try:
        df = fetcher.get_daily_kline(code, today - timedelta(days=days * 2), today, adjust="qfq")
    except Exception as exc:
        log.warning("fetch failed for %s: %s", code, exc)
        return {}
    if df.empty:
        return {}
    df["date"] = pd.to_datetime(df["date"]).dt.date
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None
    return {
        "close": float(latest["close"]),
        "prev_close": float(prev["close"]) if prev is not None else float(latest["close"]),
        "open": float(latest["open"]),
        "high": float(latest["high"]),
        "low": float(latest["low"]),
        "volume": float(latest["volume"]),
        "date": latest["date"],
        "yest_vol": float(df["volume"].iloc[-2]) if len(df) >= 2 else 0,
        "prev5_avg_vol": float(df["volume"].iloc[-6:-1].mean()) if len(df) >= 6 else 0,
        "change_pct": (
            (float(latest["close"]) - float(prev["close"])) / float(prev["close"]) * 100
            if prev is not None
            else 0
        ),
    }


def parse_sina_index_quote(text: str) -> dict | None:
    """Parse sina hq response into an index quote dict.

    Sina hq format: `var hq_str_sh000001="名称,今开,昨收,最新,最高,最低,买1,卖1,成交量,成交额,...,日期,时间";`
    Returns None on any parse failure so callers can fall back to other sources.
    """
    import re

    match = re.search(r'"([^"]+)"', text)
    if not match:
        return None
    parts = match.group(1).split(",")
    if len(parts) < 32:
        return None
    try:
        from datetime import datetime as _dt

        return {
            "name": parts[0],
            "open": float(parts[1]),
            "prev_close": float(parts[2]),
            "close": float(parts[3]),
            "high": float(parts[4]),
            "low": float(parts[5]),
            "volume": float(parts[8]),
            "amount": float(parts[9]),
            "date": _dt.strptime(parts[30], "%Y-%m-%d").date(),
        }
    except (ValueError, IndexError):
        return None


def fetch_index_realtime_sina(symbol: str) -> dict:
    """Fetch index realtime quote from sina hq endpoint.

    symbol must be prefixed (e.g. 'sh000001', 'sh000300'). Returns {} on any
    failure — callers should fall back to the tencent daily endpoint.
    """
    import requests

    try:
        resp = requests.get(
            "https://hq.sinajs.cn",
            params={"list": symbol},
            headers={
                "Referer": "https://finance.sina.com.cn",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
            timeout=10,
        )
        resp.raise_for_status()
    except Exception:  # noqa: BLE001 — best-effort realtime fetch
        return {}

    quote = parse_sina_index_quote(resp.text)
    if quote is None:
        return {}
    quote["change_pct"] = (
        (quote["close"] - quote["prev_close"]) / quote["prev_close"] * 100
        if quote["prev_close"] > 0
        else 0
    )
    return quote


def fetch_index(symbol: str, days: int = 10) -> dict:
    """Get index quote, preferring sina realtime, falling back to tencent daily.

    Why: tencent (ak.stock_zh_a_hist_tx) is T+1 delayed — during intraday it
    returns yesterday's close as if it were latest, which silently corrupts
    the report's market context. Sina hq is the authoritative realtime source.
    """
    quote = fetch_index_realtime_sina(symbol)
    if quote and quote.get("date") == date.today():
        return {
            "close": quote["close"],
            "change_pct": quote["change_pct"],
            "date": quote["date"],
        }

    # Fallback: tencent daily kline (T+1 delayed but better than nothing)
    today = date.today()
    try:
        df = ak.stock_zh_a_hist_tx(
            symbol=symbol,
            start_date=(today - timedelta(days=days * 2)).strftime("%Y%m%d"),
            end_date=today.strftime("%Y%m%d"),
        )
    except Exception:
        return {}
    if df.empty:
        return {}
    df["date"] = pd.to_datetime(df["date"]).dt.date
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None
    chg = (
        (float(latest["close"]) - float(prev["close"])) / float(prev["close"]) * 100
        if prev is not None
        else 0
    )
    return {"close": float(latest["close"]), "change_pct": chg, "date": latest["date"]}


# ---------------------------------------------------------------------------
# P&L computation
# ---------------------------------------------------------------------------

def compute_position_metrics(pos: dict, data: dict) -> dict:
    """Combine position config with market data into one metrics dict."""
    if not data:
        return {**pos, "missing": True}
    close = data["close"]
    cost = pos["buy_price"] * pos["shares"]
    value = close * pos["shares"]
    pnl = value - cost
    sl_price = pos["buy_price"] * (1 - pos["stop_loss_pct"])
    tp_price = pos["buy_price"] * (1 + pos["take_profit_pct"])
    vr_5d = data["volume"] / data["prev5_avg_vol"] if data["prev5_avg_vol"] > 0 else 0
    return {
        **pos,
        **data,
        "cost": cost,
        "value": value,
        "pnl": pnl,
        "pnl_pct": pnl / cost * 100,
        "stop_loss_price": sl_price,
        "take_profit_price": tp_price,
        "dist_be_pct": (close - pos["buy_price"]) / close * 100,
        "dist_sl_pct": (close - sl_price) / close * 100,
        "dist_tp_pct": (tp_price - close) / close * 100,
        "vol_ratio_5d": vr_5d,
    }


def status_label(m: dict) -> str:
    if m.get("missing"):
        return "❓数据缺失"
    close = m["close"]
    if close <= m["stop_loss_price"]:
        return "🚨破止损"
    if m["dist_sl_pct"] < 5:
        return "⚠接近止损"
    if close >= m["take_profit_price"]:
        return "🎯触止盈"
    if m["dist_tp_pct"] < 5:
        return "🔥接近止盈"
    if close > m["buy_price"]:
        return "✓浮盈安全"
    return "→浮亏区"


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

LEGAL_HEADER = """
⚠️ 法律声明

本报告是 Stone 工具按用户预设持仓（config/positions.yaml）做的算术分析，
**不是**：荐股、买卖指令、收益保证。决策由用户自行负责。
"""


def mode_pre_market(config: dict, fetcher: AkshareFetcher) -> str:
    today = date.today()
    out = [f"# 盘前分析 — {today}", LEGAL_HEADER]

    # Indices
    out.append("\n## 1. 大盘环境（昨日收盘）\n")
    out.append("| 指数 | 收盘 | 当日涨跌 |")
    out.append("|---|---|---|")
    for idx in config.get("indices", []):
        d = fetch_index(idx["symbol"])
        if d:
            out.append(f"| {idx['name']} | {d['close']:.2f} | {d['change_pct']:+.2f}% |")

    # Positions yesterday close + key levels
    out.append("\n## 2. 持仓昨日表现 + 今日关键价位\n")
    out.append("| 代码 | 名称 | 买入 | 昨收 | 浮盈亏 | 止损价 | 止盈价 | 保本线 | 状态 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    total_pnl = 0
    total_cost = 0
    for pos in config["positions"]:
        d = fetch_stock_data(fetcher, pos["code"])
        m = compute_position_metrics(pos, d)
        if m.get("missing"):
            out.append(f"| {pos['code']} | {pos['name']} | ¥{pos['buy_price']} | - | 数据缺失 | - | - | - | - |")
            continue
        out.append(
            f"| {pos['code']} | {pos['name']} | ¥{pos['buy_price']} | ¥{m['close']:.2f} | "
            f"{'+' if m['pnl'] >= 0 else ''}¥{m['pnl']:.2f} ({m['pnl_pct']:+.2f}%) | "
            f"¥{m['stop_loss_price']:.2f} | ¥{m['take_profit_price']:.2f} | "
            f"¥{pos['buy_price']:.3f} | {status_label(m)} |"
        )
        total_pnl += m["pnl"]
        total_cost += m["cost"]
    pnl_pct = total_pnl / config["total_capital"] * 100 if total_cost else 0
    out.append(f"\n**总浮盈亏**: {'+' if total_pnl >= 0 else ''}¥{total_pnl:.2f} ({pnl_pct:+.2f}% of ¥{config['total_capital']})")

    # Watchlist
    out.append("\n## 3. 观察名单（昨日收盘）\n")
    out.append("| 代码 | 名称 | 昨收 | 5日量比 |")
    out.append("|---|---|---|---|")
    for w in config.get("watchlist", []):
        d = fetch_stock_data(fetcher, w["code"])
        if not d:
            continue
        vr = d["volume"] / d["prev5_avg_vol"] if d["prev5_avg_vol"] > 0 else 0
        out.append(f"| {w['code']} | {w['name']} | ¥{d['close']:.2f} | {vr:.2f} |")

    # Today's plan
    out.append("""
## 4. 今日观察要点

### 盘前 9:00 前
- 隔夜美股（金融股动向）
- 富时 A50 期货方向
- 政策新闻（央行/证监会动态）

### 开盘 9:25-9:30
- 集体高开 +1%+ → 行情延续
- 平开/小高开 → 正常持有
- 低开 -2%+ → 警戒减仓

### 盘中关键价位（见上表）
- 触止损价 → 无条件卖
- 触止盈价 → 卖 50% 锁利润
- 跌破保本线 → 全平该只
""")

    return "\n".join(out)


def mode_intraday(config: dict, fetcher: AkshareFetcher) -> str:
    now = pd.Timestamp.now().strftime("%H:%M")
    out = [f"# 盘中分析 — {date.today()} {now}", LEGAL_HEADER]

    # Indices (live)
    out.append("\n## 1. 大盘实时\n")
    out.append("| 指数 | 最新 | 涨跌 |")
    out.append("|---|---|---|")
    for idx in config.get("indices", []):
        d = fetch_index(idx["symbol"])
        if d:
            out.append(f"| {idx['name']} | {d['close']:.2f} | {d['change_pct']:+.2f}% |")

    # Position live P&L
    out.append("\n## 2. 持仓实时盈亏\n")
    out.append("| 代码 | 名称 | 现价 | 当日% | 浮盈亏 | 距保本 | 距止损 | 距止盈 | 状态 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    total_pnl = 0
    alerts = []
    for pos in config["positions"]:
        d = fetch_stock_data(fetcher, pos["code"])
        m = compute_position_metrics(pos, d)
        if m.get("missing"):
            continue
        out.append(
            f"| {pos['code']} | {pos['name']} | ¥{m['close']:.2f} | {m['change_pct']:+.2f}% | "
            f"{'+' if m['pnl'] >= 0 else ''}¥{m['pnl']:.2f} | "
            f"{m['dist_be_pct']:+.2f}% | {m['dist_sl_pct']:+.2f}% | "
            f"{m['dist_tp_pct']:+.2f}% | {status_label(m)} |"
        )
        total_pnl += m["pnl"]
        # Alert if near key level
        if m["dist_sl_pct"] < 5:
            alerts.append(f"⚠️ {pos['name']} 距止损仅 {m['dist_sl_pct']:.2f}%")
        elif m["dist_tp_pct"] < 5:
            alerts.append(f"🎯 {pos['name']} 距止盈仅 {m['dist_tp_pct']:.2f}%")
        elif m["dist_be_pct"] < 1 and m["dist_be_pct"] > -1:
            alerts.append(f"⚠️ {pos['name']} 接近保本线 ¥{pos['buy_price']}")

    pnl_pct = total_pnl / config["total_capital"] * 100
    out.append(f"\n**总浮盈亏**: {'+' if total_pnl >= 0 else ''}¥{total_pnl:.2f} ({pnl_pct:+.2f}%)")

    # Alerts
    out.append("\n## 3. 关键提醒\n")
    if alerts:
        out.extend(alerts)
    else:
        out.append("✓ 所有持仓都在安全区间，无需立即操作")

    # 1-hour decision support
    out.append("""
## 4. 收盘前 1 小时决策

| 情景 | 操作 |
|---|---|
| 任一触止损价 | 无条件卖该只 |
| 任一触止盈价 | 卖 50% 锁利润 |
| 任一跌破保本线 | 全平该只 |
| 大盘 -1.5%+ | 减仓一半 |
| 量比(5日) < 0.7 | 减仓 1/3 |
""")

    return "\n".join(out)


def mode_review(config: dict, fetcher: AkshareFetcher) -> str:
    today = date.today()
    out = [f"# 收盘复盘 — {today}", LEGAL_HEADER]

    # Indices
    out.append("\n## 1. 大盘环境\n")
    out.append("| 指数 | 收盘 | 当日涨跌 |")
    out.append("|---|---|---|")
    for idx in config.get("indices", []):
        d = fetch_index(idx["symbol"])
        if d:
            out.append(f"| {idx['name']} | {d['close']:.2f} | {d['change_pct']:+.2f}% |")

    # Position review
    out.append("\n## 2. 持仓复盘\n")
    out.append("| 代码 | 名称 | 买入 | 今收 | 当日% | 浮盈亏 | 市值 |")
    out.append("|---|---|---|---|---|---|---|")
    total_cost = 0
    total_value = 0
    total_pnl = 0
    metrics_list = []
    for pos in config["positions"]:
        d = fetch_stock_data(fetcher, pos["code"])
        m = compute_position_metrics(pos, d)
        if m.get("missing"):
            continue
        metrics_list.append(m)
        out.append(
            f"| {pos['code']} | {pos['name']} | ¥{pos['buy_price']} | ¥{m['close']:.2f} | "
            f"{m['change_pct']:+.2f}% | {'+' if m['pnl'] >= 0 else ''}¥{m['pnl']:.2f} ({m['pnl_pct']:+.2f}%) | ¥{m['value']:.2f} |"
        )
        total_cost += m["cost"]
        total_value += m["value"]
        total_pnl += m["pnl"]

    pnl_pct = total_pnl / config["total_capital"] * 100
    out.append(
        f"\n**持仓成本**: ¥{total_cost:.2f}  **市值**: ¥{total_value:.2f}  "
        f"**浮盈亏**: {'+' if total_pnl >= 0 else ''}¥{total_pnl:.2f} ({pnl_pct:+.2f}%)"
    )

    # Volume analysis
    out.append("\n## 3. 量能分析\n")
    out.append("| 代码 | 名称 | 今日量 | 5日均量 | 量比 | 评估 |")
    out.append("|---|---|---|---|---|---|")
    for m in metrics_list:
        vr = m["vol_ratio_5d"]
        eval_str = "放量 ✓" if vr >= 1.5 else "温和 ✓" if vr >= 1.0 else "缩量 ⚠" if vr >= 0.7 else "极度缩 ✗"
        out.append(
            f"| {m['code']} | {m['name']} | {m['volume']:,.0f} | {m['prev5_avg_vol']:,.0f} | "
            f"{vr:.2f} | {eval_str} |"
        )

    # Distance to key levels
    out.append("\n## 4. 距离关键价位\n")
    out.append("| 代码 | 名称 | 今收 | 保本线 | 止损价 | 止盈价 | 距保本 | 距止损 | 距止盈 | 状态 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for m in metrics_list:
        out.append(
            f"| {m['code']} | {m['name']} | ¥{m['close']:.2f} | ¥{m['buy_price']:.3f} | "
            f"¥{m['stop_loss_price']:.2f} | ¥{m['take_profit_price']:.2f} | "
            f"{m['dist_be_pct']:+.2f}% | {m['dist_sl_pct']:+.2f}% | {m['dist_tp_pct']:+.2f}% | "
            f"{status_label(m)} |"
        )

    # Risk scan
    max_loss = sum(m["cost"] * m["stop_loss_pct"] for m in metrics_list)
    max_gain = sum(m["cost"] * m["take_profit_pct"] for m in metrics_list)
    out.append(f"""
## 5. 风险扫描

- 当前浮盈亏: {'+' if total_pnl >= 0 else ''}¥{total_pnl:.2f}
- 若全部止损: -¥{max_loss:.2f} (-{max_loss/config['total_capital']*100:.2f}%)
- 若全部止盈: +¥{max_gain:.2f} (+{max_gain/config['total_capital']*100:.2f}%)
- 风险收益比: 1:{max_gain/max(max_loss, 0.01):.2f}

## 6. 明日观察清单

### 盘前 9:00
- 隔夜美股 + 政策新闻 + A50 期货

### 开盘 9:25-9:30
- 集体高开 +1%+ → 行情延续
- 平开 → 持有
- 低开 -2%+ → 减仓警戒

### 盘中关键价位
- 触止损价 → 卖
- 触止盈价 → 卖 50%
- 跌破保本线 → 全平

### 量能监控
- 5日量比 > 1.0 是底线
- 连续 2 天 < 0.7 → 减仓

## 7. 综合判断

持仓基于工具算术，{len(metrics_list)} 只全部数据完整。
决策由用户自行负责。
""")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["pre-market", "intraday", "review"],
        required=True,
        help="Analysis mode",
    )
    parser.add_argument("--config", default="config/positions.yaml", help="Positions YAML path")
    parser.add_argument("--out-dir", default="reports", help="Output directory")
    args = parser.parse_args()

    from stone.logging_setup import setup_logging

    setup_logging()

    config = load_config(Path(args.config))
    fetcher = AkshareFetcher()

    if args.mode == "pre-market":
        content = mode_pre_market(config, fetcher)
    elif args.mode == "intraday":
        content = mode_intraday(config, fetcher)
    else:
        content = mode_review(config, fetcher)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = args.mode.replace("-", "_")
    out_path = out_dir / f"{date.today()}_{suffix}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Saved: {out_path}")
    print()
    print(content)


if __name__ == "__main__":
    main()

"""Unit tests for scripts/daily_analysis.py — pure parse helpers only.

Network and akshare calls are intentionally not covered here; they live in
the script layer. We lock down the field-index-sensitive sina parser so the
same Bug C5 class (stale data treated as fresh) does not slip back in.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path

# Import the script as a module (it lives outside the stone package)
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
import daily_analysis  # type: ignore  # noqa: E402


def _mock_sina_index_response(
    name: str = "上证指数",
    open_p: float = 4094.20,
    prev_close: float = 4091.89,
    current: float = 4074.29,
    high: float = 4098.70,
    low: float = 4073.73,
    volume: float = 540280632,
    amount: float = 1250029671367,
    quote_date: str | None = None,
) -> str:
    quote_date = quote_date or date.today().isoformat()
    # Real sina index response shape: 33 fields, date at index 30
    parts = [name, str(open_p), str(prev_close), str(current), str(high), str(low)]
    parts += ["0", "0", str(volume), str(amount)]
    parts += ["0"] * 20  # bid/ask pairs + placeholders (indices 10-29)
    parts += [quote_date, "14:31:56", "00"]
    return f'var hq_str_sh000001="{",".join(parts)}";'


def test_parse_sina_index_quote_extracts_fields_correctly():
    text = _mock_sina_index_response(current=4074.29, prev_close=4091.89)
    quote = daily_analysis.parse_sina_index_quote(text)
    assert quote is not None
    assert quote["name"] == "上证指数"
    assert quote["close"] == 4074.29
    assert quote["prev_close"] == 4091.89
    assert quote["open"] == 4094.20
    assert quote["high"] == 4098.70
    assert quote["low"] == 4073.73
    assert quote["date"] == date.today()


def test_parse_sina_index_quote_returns_none_on_missing_payload():
    assert daily_analysis.parse_sina_index_quote("var x=") is None


def test_parse_sina_index_quote_returns_none_on_short_payload():
    # Fewer than 32 fields → not a valid index line
    assert daily_analysis.parse_sina_index_quote('"名称,1,2,3"') is None


def test_parse_sina_index_quote_returns_none_on_bad_number():
    text = _mock_sina_index_response(current="not_a_number")  # type: ignore[arg-type]
    assert daily_analysis.parse_sina_index_quote(text) is None


def test_fetch_index_realtime_sina_computes_change_pct_from_prev_close():
    fake_text = _mock_sina_index_response(current=4074.29, prev_close=4091.89)
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = fake_text
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        quote = daily_analysis.fetch_index_realtime_sina("sh000001")
    expected = (4074.29 - 4091.89) / 4091.89 * 100
    assert abs(quote["change_pct"] - expected) < 1e-6
    assert quote["close"] == 4074.29
    assert quote["date"] == date.today()


def test_fetch_index_realtime_sina_returns_empty_on_request_failure():
    with patch("requests.get", side_effect=ConnectionError("sina blocked")):
        quote = daily_analysis.fetch_index_realtime_sina("sh000001")
    assert quote == {}


def test_fetch_index_prefers_sina_realtime_over_tencent_when_today_available():
    """Bug C5 v2 (indices): report must show today's realtime, not yesterday's close."""
    sina_text = _mock_sina_index_response(current=4074.29, prev_close=4091.89)
    with patch("requests.get") as mock_get, patch.object(
        daily_analysis.ak, "stock_zh_a_hist_tx"
    ) as mock_tx:
        mock_resp = MagicMock()
        mock_resp.text = sina_text
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = daily_analysis.fetch_index("sh000001")

    mock_tx.assert_not_called()  # tencent T+1 endpoint must not be hit
    assert result["close"] == 4074.29
    assert result["date"] == date.today()


def test_fetch_index_falls_back_to_tencent_when_sina_returns_yesterday():
    """When sina's quote date is not today (e.g. weekend), fall back to tencent."""
    import pandas as pd

    yesterday = date(2026, 6, 16)
    sina_text = _mock_sina_index_response(
        current=4091.89, prev_close=4096.47, quote_date=yesterday.isoformat()
    )
    fake_tx_df = pd.DataFrame(
        {
            "date": ["2026-06-15", "2026-06-16"],
            "open": [4053.58, 4094.21],
            "close": [4096.47, 4091.89],
            "high": [4097.17, 4103.93],
            "low": [4051.07, 4077.87],
            "amount": [678907811.0, 615668296.0],
        }
    )
    with patch("requests.get") as mock_get, patch.object(
        daily_analysis.ak, "stock_zh_a_hist_tx", return_value=fake_tx_df
    ) as mock_tx:
        mock_resp = MagicMock()
        mock_resp.text = sina_text
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = daily_analysis.fetch_index("sh000001")

    mock_tx.assert_called_once()  # fallback engaged
    assert result["close"] == 4091.89
    assert result["date"] == date(2026, 6, 16)

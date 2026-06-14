import json
from datetime import date

from stone.reporters.json_reporter import JsonReporter
from stone.selector.engine import SelectionResult
from stone.selector.scoring import StockScore


def _make_result() -> SelectionResult:
    picks = [
        StockScore(
            code="600519",
            name="贵州茅台",
            industry="白酒",
            today=date(2026, 6, 14),
            score=92.3,
            raw_values={"ma_bullish_alignment": 1.0},
            normalized_values={"ma_bullish_alignment": 95.0},
        )
    ]
    return SelectionResult(
        strategy_name="波段趋势 v1",
        target_date=date(2026, 6, 14),
        universe_size=100,
        scored_size=99,
        passed_size=50,
        final_picks=picks,
    )


def test_json_reporter_writes_valid_json(tmp_path):
    reporter = JsonReporter()
    reporter.render(_make_result(), output_dir=tmp_path)
    expected = tmp_path / "2026-06-14_波段趋势 v1.json"
    assert expected.exists()
    data = json.loads(expected.read_text(encoding="utf-8"))
    assert data["meta"]["target_date"] == "2026-06-14"
    assert data["picks"][0]["code"] == "600519"

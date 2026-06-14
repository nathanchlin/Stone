from datetime import date

from stone.reporters.html import HtmlReporter
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


def test_html_reporter_creates_html(tmp_path):
    reporter = HtmlReporter()
    out = reporter.render(_make_result(), output_dir=tmp_path)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<html" in content.lower()


def test_html_contains_strategy_name(tmp_path):
    reporter = HtmlReporter()
    out = reporter.render(_make_result(), output_dir=tmp_path)
    content = out.read_text(encoding="utf-8")
    assert "波段趋势 v1" in content


def test_html_contains_disclaimer(tmp_path):
    reporter = HtmlReporter()
    out = reporter.render(_make_result(), output_dir=tmp_path)
    content = out.read_text(encoding="utf-8")
    assert "非投资建议" in content


def test_html_contains_pick_row(tmp_path):
    reporter = HtmlReporter()
    out = reporter.render(_make_result(), output_dir=tmp_path)
    content = out.read_text(encoding="utf-8")
    assert "600519" in content
    assert "贵州茅台" in content

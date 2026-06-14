from datetime import date

from stone.reporters.markdown import MarkdownReporter
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


def test_markdown_reporter_contains_strategy_name(tmp_path):
    reporter = MarkdownReporter()
    reporter.render(_make_result(), output_dir=tmp_path)
    md_file = tmp_path / "2026-06-14_波段趋势 v1.md"
    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")
    assert "波段趋势 v1" in content
    assert "600519" in content
    assert "贵州茅台" in content


def test_markdown_includes_top_picks_table(tmp_path):
    reporter = MarkdownReporter()
    reporter.render(_make_result(), output_dir=tmp_path)
    md_file = tmp_path / "2026-06-14_波段趋势 v1.md"
    content = md_file.read_text(encoding="utf-8")
    assert "| 1 |" in content or "| 1|" in content

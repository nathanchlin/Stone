"""Markdown reporter."""

from collections import Counter
from pathlib import Path

from stone.selector.engine import SelectionResult


class MarkdownReporter:
    """Render git-friendly markdown reports."""

    DISCLAIMER = "> ⚠️ 本报告仅为按预设规则的算法计算结果，**非投资建议**。买卖决策请自行判断。"

    def render(self, result: SelectionResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        lines: list[str] = [
            f"# 选股报告 - {result.target_date} - {result.strategy_name}",
            "",
            f"> 股池: {result.universe_size} → 评分: {result.scored_size} → 过滤: {result.passed_size} → 最终: {len(result.final_picks)}",
            "",
            "## Top 候选股",
            "",
            "| # | 代码 | 名称 | 行业 | 评分 |",
            "|---|---|---|---|---|",
        ]
        for index, score in enumerate(result.final_picks, start=1):
            lines.append(
                f"| {index} | {score.code} | {score.name} | {score.industry} | **{score.score:.1f}** |"
            )

        lines.extend(["", "## 行业分布", "", "| 行业 | 数量 |", "|---|---|"])
        for industry, count in Counter(
            score.industry for score in result.final_picks
        ).most_common():
            lines.append(f"| {industry} | {count} |")

        if result.position_plans:
            lines.extend(
                [
                    "",
                    "## 仓位建议（按预设规则算术，非投资建议）",
                    "",
                    "| 代码 | 建议金额 | 建议股数 | 止损价 | 止盈价 |",
                    "|---|---|---|---|---|",
                ]
            )
            for plan in result.position_plans:
                stop_loss = f"{plan.stop_loss_price:.2f}" if plan.stop_loss_price else "-"
                take_profit = f"{plan.take_profit_price:.2f}" if plan.take_profit_price else "-"
                lines.append(
                    f"| {plan.code} | ¥{plan.amount:,.0f} | {plan.shares} | {stop_loss} | {take_profit} |"
                )

        if result.failed_codes:
            lines.extend(["", "## 失败股票", "", f"{len(result.failed_codes)} 只计算失败。"])

        lines.extend(["", self.DISCLAIMER, ""])

        out = output_dir / f"{result.target_date.isoformat()}_{result.strategy_name}.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        return out
